from __future__ import annotations

import json
import os
import pickle
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Literal

import networkx as nx
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from agents.language_policy import prepend_prompt_language_policy

GraphRAGQueryMode = Literal["local", "global", "drift"]


@dataclass
class GraphRAGArtifactPaths:
    base_dir: str
    pickle_path: str
    graphml_path: str
    json_path: str
    metadata_path: str


class GraphRAGService:
    """Production GraphRAG service for project-scoped indexing and retrieval."""

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self._chunk_size = int(os.getenv("SPARKARC_GRAPHRAG_CHUNK_SIZE", "1200"))
        self._chunk_overlap = int(os.getenv("SPARKARC_GRAPHRAG_CHUNK_OVERLAP", "160"))
        self._max_chunks = int(os.getenv("SPARKARC_GRAPHRAG_MAX_CHUNKS", "120"))
        self._max_source_chars = int(os.getenv("SPARKARC_GRAPHRAG_MAX_SOURCE_CHARS", "240000"))
        self._max_triplets_per_chunk = int(os.getenv("SPARKARC_GRAPHRAG_MAX_TRIPLETS_PER_CHUNK", "24"))
        self._max_constraints = int(os.getenv("SPARKARC_GRAPHRAG_MAX_CONSTRAINTS", "12"))
        self._build_usage_key = "fast"

    @property
    def _project_path(self) -> str:
        return get_project_path(self.user_id, self.project_name)

    @property
    def _artifacts(self) -> GraphRAGArtifactPaths:
        base_dir = os.path.join(self._project_path, ".graphrag")
        return GraphRAGArtifactPaths(
            base_dir=base_dir,
            pickle_path=os.path.join(base_dir, "graph.pkl"),
            graphml_path=os.path.join(base_dir, "graph.graphml"),
            json_path=os.path.join(base_dir, "graph.json"),
            metadata_path=os.path.join(base_dir, "meta.json"),
        )

    def _ensure_project_exists(self) -> None:
        if not os.path.isdir(self._project_path):
            raise FileNotFoundError(f"项目不存在: {self._project_path}")

    def _get_build_llm(self):
        # 建图阶段固定走 fast。
        return matchbox().get_user_llm(
            self.user_id,
            usage_key=self._build_usage_key,
        )

    def _get_query_llm(self, query_agent_name: str | None):
        # 查询阶段跟随调用者 agent 绑定；无调用者时回退默认主模型。
        if query_agent_name:
            return matchbox().get_user_llm(
                self.user_id,
                agent_name=query_agent_name,
            )
        return matchbox().get_user_llm(self.user_id)

    @staticmethod
    def _extract_text_from_message(message: Any) -> str:
        if message is None:
            return ""
        if isinstance(message, str):
            return message

        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            out: list[str] = []
            for item in content:
                if isinstance(item, str):
                    out.append(item)
                    continue
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        out.append(text)
            return "\n".join(part for part in out if part).strip()

        return str(content or "")

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        raw = (text or "").strip()
        if raw.startswith("```") and raw.endswith("```"):
            lines = raw.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[1:-1]).strip()
        return raw

    @staticmethod
    def _safe_json_loads(raw: str, fallback: Any) -> Any:
        text = GraphRAGService._strip_markdown_fence(raw)
        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"(\[.*\]|\{.*\})", text, flags=re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        return fallback

    def _invoke_text(self, llm_client: Any, system_prompt: str, user_prompt: str) -> str:
        response = llm_client.invoke(
            [
                SystemMessage(content=prepend_prompt_language_policy(system_prompt)),
                HumanMessage(content=user_prompt),
            ]
        )
        return self._extract_text_from_message(response)

    @staticmethod
    def _normalize_entity_name(value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"\s+", "", text)
        return text.lower()

    @staticmethod
    def _extract_aliases_from_text(text: str) -> list[str]:
        aliases: list[str] = []
        if not text:
            return aliases

        for raw_line in text.splitlines()[:8]:
            line = raw_line.strip().lstrip("#").strip()
            if not line:
                continue
            if line.startswith("别名") or line.lower().startswith("alias"):
                _, _, right = line.partition(":")
                if not right:
                    _, _, right = line.partition("：")
                if right:
                    for item in re.split(r"[、,，/|；;]", right):
                        alias = item.strip()
                        if alias:
                            aliases.append(alias)
            if len(aliases) >= 8:
                break
        return aliases[:8]

    def _load_character_alias_index(self) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        chr_dir = os.path.join(self._project_path, "chr")
        bind_path = os.path.join(chr_dir, "chr.bind")
        if not os.path.exists(bind_path):
            return alias_map

        try:
            with open(bind_path, "r", encoding="utf-8") as f:
                mapping = json.load(f) or {}
        except Exception:
            mapping = {}

        if not isinstance(mapping, dict):
            return alias_map

        for cid, raw_name in mapping.items():
            if isinstance(raw_name, dict):
                canonical = str(raw_name.get("name") or "").strip()
            else:
                canonical = str(raw_name or "").strip()

            if not canonical:
                continue

            aliases = [canonical]

            # 兼容常见的“主名(别名)”或“主名/别名”写法
            for part in re.split(r"[()（）/|,，、]", canonical):
                item = part.strip()
                if item and item not in aliases:
                    aliases.append(item)

            detail_paths = [
                os.path.join(chr_dir, f"{cid}.md"),
                os.path.join(chr_dir, f"{cid}.txt"),
            ]
            for detail_path in detail_paths:
                if not os.path.exists(detail_path):
                    continue
                try:
                    with open(detail_path, "r", encoding="utf-8", errors="ignore") as f:
                        detail_text = f.read()
                    for alias in self._extract_aliases_from_text(detail_text):
                        if alias not in aliases:
                            aliases.append(alias)
                    break
                except Exception:
                    continue

            for alias in aliases:
                key = self._normalize_entity_name(alias)
                if key and key not in alias_map:
                    alias_map[key] = canonical

        return alias_map

    def _collect_source_documents(self) -> list[Document]:
        self._ensure_project_exists()

        project_path = self._project_path
        candidate_files: list[str] = [
            os.path.join(project_path, "世界观.txt"),
            os.path.join(project_path, "梗概.txt"),
            os.path.join(project_path, "节拍表.txt"),
            os.path.join(project_path, "大纲.txt"),
        ]

        chr_dir = os.path.join(project_path, "chr")
        if os.path.isdir(chr_dir):
            for name in sorted(os.listdir(chr_dir)):
                if name.endswith((".txt", ".md")):
                    candidate_files.append(os.path.join(chr_dir, name))

        stories_dir = os.path.join(project_path, "stories")
        if os.path.isdir(stories_dir):
            for name in sorted(os.listdir(stories_dir)):
                if name.endswith(".arc"):
                    candidate_files.append(os.path.join(stories_dir, name))

        documents: list[Document] = []
        total_chars = 0

        for file_path in candidate_files:
            if not os.path.isfile(file_path):
                continue
            if total_chars >= self._max_source_chars:
                break

            try:
                text = self._read_source_file(file_path)
            except Exception:
                continue

            text = (text or "").strip()
            if not text:
                continue

            remaining = self._max_source_chars - total_chars
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining]

            total_chars += len(text)
            rel_source = os.path.relpath(file_path, project_path).replace("\\", "/")
            documents.append(Document(page_content=text, metadata={"source": rel_source}))

        return documents

    @staticmethod
    def _read_source_file(file_path: str) -> str:
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return json.dumps(data, ensure_ascii=False, indent=2)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _parse_triplets_from_payload(self, payload: Any) -> list[tuple[str, str, str]]:
        if not isinstance(payload, list):
            return []

        triplets: list[tuple[str, str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            subj = str(item.get("subject", "")).strip()
            rel = str(item.get("relation", "")).strip()
            obj = str(item.get("object", "")).strip()

            if len(subj) < 2 or len(obj) < 2 or not rel:
                continue
            if len(subj) > 24 or len(obj) > 24 or len(rel) > 32:
                continue
            if subj == obj:
                continue
            triplets.append((subj, rel, obj))

        return triplets[: self._max_triplets_per_chunk]

    def _extract_triplets(self, text: str) -> list[tuple[str, str, str]]:
        if not text.strip():
            return []

        system_prompt = (
            "你是小说知识图谱构建器。"
            "任务标签:[TASK:TRIPLET_EXTRACTION]。"
            "只返回 JSON 数组，每项结构为 {\"subject\":\"\",\"relation\":\"\",\"object\":\"\"}。"
            "只保留具体实体与明确关系；禁止代词、空泛概念、句子片段。"
        )
        user_prompt = (
            f"请从以下文本提取不超过 {self._max_triplets_per_chunk} 条高质量三元组。"
            "仅返回 JSON，不要额外解释。\n\n"
            f"文本:\n{text}"
        )

        raw = self._invoke_text(self._get_build_llm(), system_prompt, user_prompt)
        payload = self._safe_json_loads(raw, fallback=[])
        triplets = self._parse_triplets_from_payload(payload)
        if triplets:
            return triplets

        # 一次结构化重试，提升脏输出场景下的稳定性。
        retry_prompt = (
            "你上一轮输出未通过 JSON 结构校验。"
            "请只返回合法 JSON 数组，不要 markdown，不要解释。\n"
            f"文本:\n{text}"
        )
        retry_raw = self._invoke_text(self._get_build_llm(), system_prompt, retry_prompt)
        retry_payload = self._safe_json_loads(retry_raw, fallback=[])
        return self._parse_triplets_from_payload(retry_payload)

    @staticmethod
    def _merge_relation(existing: str, new_relation: str) -> str:
        parts = [p for p in (existing or "").split(" | ") if p]
        if new_relation not in parts:
            parts.append(new_relation)
        return " | ".join(parts[:6])

    @staticmethod
    def _merge_edge_source(existing: str, new_source: str) -> str:
        items = [p for p in (existing or "").split(" | ") if p]
        if new_source and new_source not in items:
            items.append(new_source)
        return " | ".join(items[:8])

    @staticmethod
    def _merge_edge_sample(existing: str, new_sample: str) -> str:
        items = [p for p in (existing or "").split(" || ") if p]
        sample = (new_sample or "").strip()
        if sample and sample not in items:
            items.append(sample)
        return " || ".join(items[:4])

    def _canonicalize_entity(self, raw_name: str, alias_map: dict[str, str]) -> str:
        name = str(raw_name or "").strip()
        if not name:
            return name
        return alias_map.get(self._normalize_entity_name(name), name)

    def _build_graph(self, chunks: list[Document], alias_map: dict[str, str]) -> tuple[nx.Graph, int]:
        graph = nx.Graph()
        triplet_count = 0

        for idx, chunk in enumerate(chunks):
            triplets = self._extract_triplets(chunk.page_content)
            source = str(chunk.metadata.get("source") or "")
            sample = chunk.page_content.replace("\n", " ").strip()[:120]
            for subj, rel, obj in triplets:
                subj = self._canonicalize_entity(subj, alias_map)
                obj = self._canonicalize_entity(obj, alias_map)
                if not subj or not obj or subj == obj:
                    continue
                graph.add_node(subj)
                graph.add_node(obj)
                if graph.has_edge(subj, obj):
                    edge = graph[subj][obj]
                    edge["relation"] = self._merge_relation(str(edge.get("relation", "")), rel)
                    edge["sources"] = self._merge_edge_source(str(edge.get("sources", "")), source)
                    edge["evidence_samples"] = self._merge_edge_sample(str(edge.get("evidence_samples", "")), sample)
                    edge["last_source"] = source
                    edge["evidence_count"] = int(edge.get("evidence_count", 1)) + 1
                    edge["last_chunk_id"] = idx
                else:
                    graph.add_edge(
                        subj,
                        obj,
                        relation=rel,
                        sources=source,
                        last_source=source,
                        evidence_samples=sample,
                        evidence_count=1,
                        last_chunk_id=idx,
                    )
                triplet_count += 1

        return graph, triplet_count

    @staticmethod
    def _build_communities(graph: nx.Graph, top_k: int = 8) -> list[dict[str, Any]]:
        communities: list[dict[str, Any]] = []
        components = sorted(nx.connected_components(graph), key=len, reverse=True)

        for idx, comp in enumerate(components[:top_k], start=1):
            sub = graph.subgraph(comp)
            top_nodes = sorted(sub.degree(), key=lambda pair: pair[1], reverse=True)[:8]
            communities.append(
                {
                    "id": idx,
                    "size": int(sub.number_of_nodes()),
                    "edges": int(sub.number_of_edges()),
                    "top_nodes": [name for name, _ in top_nodes],
                }
            )

        return communities

    def _persist(self, graph: nx.Graph, metadata: dict[str, Any]) -> None:
        artifacts = self._artifacts
        os.makedirs(artifacts.base_dir, exist_ok=True)

        with open(artifacts.pickle_path, "wb") as f:
            pickle.dump(graph, f)

        with open(artifacts.json_path, "w", encoding="utf-8") as f:
            json.dump(nx.node_link_data(graph, edges="edges"), f, ensure_ascii=False, indent=2)

        nx.write_graphml(graph, artifacts.graphml_path)

        with open(artifacts.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _load_graph(self) -> nx.Graph:
        artifacts = self._artifacts
        if os.path.exists(artifacts.pickle_path):
            with open(artifacts.pickle_path, "rb") as f:
                loaded = pickle.load(f)
            if isinstance(loaded, nx.Graph):
                return loaded

        if os.path.exists(artifacts.graphml_path):
            return nx.read_graphml(artifacts.graphml_path)

        raise FileNotFoundError("GraphRAG 索引不存在，请先执行 build。")

    def _load_metadata(self) -> dict[str, Any]:
        artifacts = self._artifacts
        if not os.path.exists(artifacts.metadata_path):
            return {}
        with open(artifacts.metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def get_status(self) -> dict[str, Any]:
        artifacts = self._artifacts
        metadata = self._load_metadata()

        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "exists": os.path.isdir(artifacts.base_dir),
            "graph_ready": os.path.exists(artifacts.pickle_path)
            or os.path.exists(artifacts.graphml_path),
            "metadata_ready": os.path.exists(artifacts.metadata_path),
            "artifacts_dir": artifacts.base_dir,
            "metadata": metadata,
            "build_usage_key": self._build_usage_key,
            "query_agent_policy": "follow_caller_agent",
        }

    def reset(self) -> dict[str, Any]:
        artifacts = self._artifacts
        removed = False
        if os.path.isdir(artifacts.base_dir):
            shutil.rmtree(artifacts.base_dir)
            removed = True
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "removed": removed,
            "artifacts_dir": artifacts.base_dir,
        }

    def build_index(self, force_rebuild: bool = False) -> dict[str, Any]:
        self._ensure_project_exists()

        status = self.get_status()
        if status.get("graph_ready") and not force_rebuild:
            metadata = status.get("metadata") or {}
            metadata["reused"] = True
            return metadata

        docs = self._collect_source_documents()
        if not docs:
            raise RuntimeError("未找到可用于构建 GraphRAG 的项目文本（世界观/角色/梗概/大纲/剧本）。")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )
        chunks = splitter.split_documents(docs)
        chunks = chunks[: self._max_chunks]

        alias_map = self._load_character_alias_index()
        graph, triplet_count = self._build_graph(chunks, alias_map)
        communities = self._build_communities(graph)

        metadata: dict[str, Any] = {
            "version": "1.0",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "project": self.project_name,
            "user_id": self.user_id,
            "build_usage_key": self._build_usage_key,
            "query_agent_policy": "follow_caller_agent",
            "alias_count": len(alias_map),
            "source_docs": len(docs),
            "chunks": len(chunks),
            "triplets": triplet_count,
            "nodes": int(graph.number_of_nodes()),
            "edges": int(graph.number_of_edges()),
            "communities": communities,
            "reused": False,
        }

        self._persist(graph, metadata)
        return metadata

    def _extract_query_entities(self, question: str, query_agent_name: str | None, alias_map: dict[str, str]) -> list[str]:
        system_prompt = (
            "你是问题实体抽取器。任务标签:[TASK:ENTITY_EXTRACTION]。"
            "输出 JSON 数组，仅包含问题中的人物/地点/组织/物品实体名。"
            "若没有实体，返回空数组。"
        )
        raw = self._invoke_text(self._get_query_llm(query_agent_name), system_prompt, f"问题: {question}")
        payload = self._safe_json_loads(raw, fallback=[])
        if isinstance(payload, list):
            values = [str(item).strip() for item in payload if str(item).strip()]
            return [self._canonicalize_entity(v, alias_map) for v in values[:8]]

        # fallback: 粗略按中英文词片切分
        tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9_]{2,16}", question or "")
        return [self._canonicalize_entity(v, alias_map) for v in tokens[:8]]

    @staticmethod
    def _match_entity(name: str, graph: nx.Graph, alias_map: dict[str, str]) -> str | None:
        if not name:
            return None

        canonical_name = alias_map.get(GraphRAGService._normalize_entity_name(name), name)
        if canonical_name in graph:
            return canonical_name

        if name in graph:
            return name

        low = name.lower()
        exact_candidates: list[str] = []
        fuzzy_best: tuple[float, str] | None = None

        for node in graph.nodes:
            node_str = str(node)
            node_low = node_str.lower()
            if low in node_low or node_low in low:
                exact_candidates.append(node_str)

            ratio = SequenceMatcher(None, low, node_low).ratio()
            if ratio >= 0.74 and (fuzzy_best is None or ratio > fuzzy_best[0]):
                fuzzy_best = (ratio, node_str)

        if exact_candidates:
            return sorted(exact_candidates, key=len)[0]
        return fuzzy_best[1] if fuzzy_best else None

    def _build_fact_constraints(
        self,
        graph: nx.Graph,
        matched_entities: list[str],
        max_items: int,
    ) -> dict[str, list[str]]:
        must_keep: list[str] = []
        avoid_conflicts: list[str] = []
        unresolved: list[str] = []

        if not matched_entities:
            unresolved.append("未匹配到明确实体，建议先补充人物/地点/组织名后再写。")
            return {
                "must_keep": must_keep,
                "avoid_conflicts": avoid_conflicts,
                "unresolved": unresolved,
            }

        seen: set[tuple[str, str]] = set()
        for center in matched_entities:
            if center not in graph:
                continue
            for neighbor in graph.neighbors(center):
                edge_key = tuple(sorted((str(center), str(neighbor))))
                if edge_key in seen:
                    continue
                seen.add(edge_key)

                edge = graph.get_edge_data(center, neighbor) or {}
                relation = str(edge.get("relation", "相关"))
                source = str(edge.get("last_source") or edge.get("sources") or "未知来源")
                must_keep.append(f"{center} 与 {neighbor} 的关系：{relation}（证据: {source}）")
                avoid_conflicts.append(f"避免写出与“{center} 与 {neighbor}：{relation}”相反的描述。")

                if len(must_keep) >= max_items:
                    break
            if len(must_keep) >= max_items:
                break

        if not must_keep:
            unresolved.append("命中实体缺少稳定关系，建议先 build 并补充项目设定。")

        return {
            "must_keep": must_keep,
            "avoid_conflicts": avoid_conflicts,
            "unresolved": unresolved,
        }

    @staticmethod
    def _global_context(graph: nx.Graph, metadata: dict[str, Any]) -> str:
        lines: list[str] = []
        lines.append("[GLOBAL SUMMARY]")
        lines.append(f"实体数: {graph.number_of_nodes()}")
        lines.append(f"关系数: {graph.number_of_edges()}")

        top_nodes = sorted(graph.degree(), key=lambda pair: pair[1], reverse=True)[:20]
        if top_nodes:
            lines.append("核心实体:")
            for name, degree in top_nodes:
                lines.append(f"- {name} (连接数: {degree})")

        communities = metadata.get("communities") or []
        if isinstance(communities, list) and communities:
            lines.append("社区结构:")
            for comm in communities[:8]:
                if not isinstance(comm, dict):
                    continue
                nodes = ", ".join(comm.get("top_nodes") or [])
                lines.append(
                    f"- 社区{comm.get('id')}: size={comm.get('size')} edges={comm.get('edges')} top={nodes}"
                )

        return "\n".join(lines)

    @staticmethod
    def _local_context(
        graph: nx.Graph,
        matched_entities: list[str],
        max_hops: int,
        max_edges: int,
    ) -> str:
        lines: list[str] = ["[LOCAL CONTEXT]"]
        if not matched_entities:
            lines.append("未匹配到实体。")
            return "\n".join(lines)

        lines.append("匹配实体: " + ", ".join(matched_entities))

        emitted = 0
        seen_edges: set[tuple[str, str]] = set()

        for center in matched_entities:
            sub = nx.ego_graph(graph, center, radius=max_hops)
            lines.append(f"\n实体 [{center}] 周边关系:")
            for src, dst, attrs in sub.edges(data=True):
                edge_key = tuple(sorted((str(src), str(dst))))
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                relation = str(attrs.get("relation", "相关"))
                lines.append(f"- {src} --[{relation}]--> {dst}")
                emitted += 1
                if emitted >= max_edges:
                    lines.append("- ... (已达到关系条数上限)")
                    return "\n".join(lines)

        return "\n".join(lines)

    def _generate_answer(
        self,
        question: str,
        query_mode: GraphRAGQueryMode,
        context: str,
        query_agent_name: str | None,
    ) -> str:
        system_prompt = (
            "你是编剧系统的 GraphRAG 问答助手。任务标签:[TASK:ANSWER]。"
            "仅根据提供的检索上下文回答；若信息不足，请明确说不知道。"
            "回答要简洁、结构化，优先给出可执行的创作建议。"
        )
        user_prompt = (
            f"检索模式: {query_mode}\n"
            f"问题: {question}\n\n"
            f"检索上下文:\n{context}\n\n"
            "请给出最终回答。"
        )
        return self._invoke_text(self._get_query_llm(query_agent_name), system_prompt, user_prompt).strip()

    def query(
        self,
        question: str,
        query_agent_name: str | None = None,
        query_mode: GraphRAGQueryMode = "drift",
        max_hops: int = 2,
        max_edges: int = 56,
    ) -> dict[str, Any]:
        if not question or not question.strip():
            raise ValueError("问题不能为空。")

        graph = self._load_graph()
        metadata = self._load_metadata()
        alias_map = self._load_character_alias_index()
        entities = self._extract_query_entities(question, query_agent_name, alias_map)

        matched_entities: list[str] = []
        for entity in entities:
            matched = self._match_entity(entity, graph, alias_map)
            if matched and matched not in matched_entities:
                matched_entities.append(matched)

        local_context = self._local_context(
            graph,
            matched_entities,
            max_hops=max_hops,
            max_edges=max_edges,
        )
        global_context = self._global_context(graph, metadata)

        mode = query_mode
        if mode == "local":
            context = local_context
        elif mode == "global":
            context = global_context
        else:
            context = f"{global_context}\n\n{local_context}"

        answer = self._generate_answer(question, mode, context, query_agent_name)
        constraints = self._build_fact_constraints(
            graph,
            matched_entities,
            max_items=self._max_constraints,
        )

        return {
            "mode": mode,
            "question": question,
            "query_agent_name": query_agent_name,
            "entities": entities,
            "matched_entities": matched_entities,
            "context": context,
            "answer": answer,
            "fact_constraints": constraints,
        }
