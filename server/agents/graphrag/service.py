from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import re
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Literal

import networkx as nx
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from agents.language_policy import prepend_prompt_language_policy
from story.project_files import collect_project_files
from story.semantic_chunker import SemanticChunker

GraphRAGQueryMode = Literal["local", "global", "drift"]
logger = logging.getLogger(__name__)
GRAPHRAG_CHUNKING_STRATEGY_VERSION = "semantic-v1"


# ==================== 全局后台构建状态注册表 ====================
# 与 VectorIndexService 同构：用进程内字典 + 锁追踪每个 (user_id, project_name)
# 的后台构建生命周期，supports 重入排队（构建中再次触发会自动补一轮）。

_build_state_registry: dict[str, dict] = {}
_build_state_lock = threading.Lock()
_ACTIVE_BUILD_STATUSES = {"queued", "building", "cancelling"}


def _build_task_key(user_id: str, project_name: str) -> str:
    return f"{user_id}:{project_name}"


class GraphRAGBuildCancelledError(RuntimeError):
    """知识图谱构建被上游高优先级操作取消。"""


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
        self._build_usage_key = (os.getenv("SPARKARC_GRAPHRAG_BUILD_USAGE_KEY", "fast") or "fast").strip().lower() or "fast"
        self._llm_timeout = float(os.getenv("SPARKARC_GRAPHRAG_LLM_TIMEOUT", "90"))

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
        # 建图阶段默认走 fast，也允许部署者通过环境变量切换到自定义用途。
        return matchbox().get_user_llm(
            self.user_id,
            usage_key=self._build_usage_key,
            timeout=self._llm_timeout,
        )

    def _get_query_llm(self, query_agent_name: str | None):
        # 查询阶段跟随调用者 agent 绑定；无调用者时回退默认主模型。
        if query_agent_name:
            return matchbox().get_user_llm(
                self.user_id,
                agent_name=query_agent_name,
                timeout=self._llm_timeout,
            )
        return matchbox().get_user_llm(self.user_id, timeout=self._llm_timeout)

    # ==================== 后台构建状态管理 ====================

    @staticmethod
    def _public_build_state(payload: dict | None) -> dict:
        """剥离内部字段，输出前端可消费的 build_state。"""
        state = {
            key: value
            for key, value in dict(payload or {}).items()
            if not str(key).startswith("_")
        }
        state["progress"] = dict(state.get("progress") or {})
        return state

    @staticmethod
    def _empty_progress() -> dict:
        return {
            "total_chunks": 0,
            "done_chunks": 0,
            "triplets_collected": 0,
            "source_docs": 0,
            "nodes": 0,
            "edges": 0,
        }

    def _set_build_state(self, **fields) -> dict:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            if "progress" in fields:
                fields["progress"] = dict(fields.get("progress") or {})
            current.update(fields)
            _build_state_registry[task_key] = current
            return dict(current)

    def _get_cancel_event(self) -> threading.Event | None:
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            event = (_build_state_registry.get(task_key) or {}).get("_cancel_event")
        return event if isinstance(event, threading.Event) else None

    def _check_cancelled(self) -> None:
        event = self._get_cancel_event()
        if event and event.is_set():
            raise GraphRAGBuildCancelledError("知识图谱构建已取消")

    def cancel_background_build(self, wait_timeout: float = 5.0) -> dict:
        """请求取消后台图谱构建，并在限定时间内等待线程主动退出。"""
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            status = current.get("status")
            event = current.get("_cancel_event")
            thread = current.get("_thread")
            if status not in _ACTIVE_BUILD_STATUSES or not isinstance(event, threading.Event):
                return self._public_build_state(current)
            event.set()
            current.update({
                "status": "cancelling",
                "stage": "cancelling",
                "error": "正在取消知识图谱构建",
                "_pending_refresh": False,
                "_pending_force_rebuild": False,
            })
            _build_state_registry[task_key] = current

        if isinstance(thread, threading.Thread) and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(wait_timeout)))
        return self.get_build_state()

    def get_build_state(self) -> dict:
        """读取当前后台构建状态。

        - 进程内有进行中 / 已完成快照时直接返回；
        - 否则回退到磁盘 metadata 推断（ready / not_built）。
        """
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            stored = dict(_build_state_registry.get(task_key) or {})
        if stored:
            return self._public_build_state(stored)

        artifacts = self._artifacts
        if os.path.exists(artifacts.pickle_path) or os.path.exists(artifacts.graphml_path):
            metadata = self._load_metadata()
            built_at = metadata.get("built_at", "")
            return {
                "status": "ready",
                "stage": "ready",
                "error": "",
                "started_at": built_at,
                "finished_at": built_at,
                "progress": {
                    "total_chunks": int(metadata.get("chunks", 0) or 0),
                    "done_chunks": int(metadata.get("chunks", 0) or 0),
                    "triplets_collected": int(metadata.get("triplets", 0) or 0),
                    "source_docs": int(metadata.get("source_docs", 0) or 0),
                    "nodes": int(metadata.get("nodes", 0) or 0),
                    "edges": int(metadata.get("edges", 0) or 0),
                },
            }
        return {
            "status": "not_built",
            "stage": "idle",
            "error": "",
            "started_at": "",
            "finished_at": "",
            "progress": self._empty_progress(),
        }

    def start_background_build(self, force_rebuild: bool = False) -> dict:
        """在 daemon 线程中触发后台构建；重复触发自动排队补一轮。"""
        task_key = _build_task_key(self.user_id, self.project_name)
        now = datetime.now(timezone.utc).isoformat()
        cancel_event = threading.Event()
        with _build_state_lock:
            current = dict(_build_state_registry.get(task_key) or {})
            if current.get("status") in _ACTIVE_BUILD_STATUSES:
                current["_pending_refresh"] = True
                current["_pending_force_rebuild"] = bool(current.get("_pending_force_rebuild")) or bool(force_rebuild)
                _build_state_registry[task_key] = current
                return self._public_build_state(current)
            current.update({
                "status": "queued",
                "stage": "queued",
                "error": "",
                "started_at": now,
                "finished_at": "",
                "_pending_refresh": False,
                "_pending_force_rebuild": False,
                "_cancel_event": cancel_event,
                "_thread": None,
                "progress": self._empty_progress(),
            })
            _build_state_registry[task_key] = current

        def _run() -> None:
            next_force_rebuild = force_rebuild
            while True:
                try:
                    self.build_index(force_rebuild=next_force_rebuild)
                except GraphRAGBuildCancelledError:
                    pass
                except Exception:
                    # build_index 自身已写 error 状态，这里吞掉避免线程崩
                    pass
                with _build_state_lock:
                    latest = dict(_build_state_registry.get(task_key) or {})
                    cancelled = bool(cancel_event.is_set())
                    rerun = bool(latest.get("_pending_refresh")) and not cancelled
                    next_force_rebuild = bool(latest.get("_pending_force_rebuild"))
                    latest["_pending_refresh"] = False
                    latest["_pending_force_rebuild"] = False
                    if cancelled and latest.get("status") not in {"cancelled", "error"}:
                        latest.update({
                            "status": "cancelled",
                            "stage": "cancelled",
                            "error": "知识图谱构建已取消",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        })
                    _build_state_registry[task_key] = latest
                if not rerun:
                    break

        thread = threading.Thread(
            target=_run,
            daemon=True,
            name=f"graphrag_build_{task_key}",
        )
        thread.start()
        with _build_state_lock:
            latest = dict(_build_state_registry.get(task_key) or {})
            if latest.get("_cancel_event") is cancel_event:
                latest["_thread"] = thread
                _build_state_registry[task_key] = latest
        return self.get_build_state()

    def ensure_background_build_started(self, check_freshness: bool = True) -> dict:
        """若索引不存在或已过期，则后台启动构建；否则原样返回当前状态。"""
        status = self.get_status(check_freshness=check_freshness)
        build_state = dict(status.get("build_state") or {})
        if build_state.get("status") in _ACTIVE_BUILD_STATUSES:
            return status
        if not status.get("graph_ready") or status.get("needs_rebuild"):
            build_state = self.start_background_build(force_rebuild=False)
            return {
                **status,
                "build_state": build_state,
            }
        return status

    # ==================== 文件哈希 / 过期判定 ====================

    @staticmethod
    def _hash_text(text: str) -> str:
        try:
            return hashlib.md5((text or "").encode("utf-8")).hexdigest()
        except Exception:
            return ""

    def _compute_file_hashes(self) -> dict[str, str]:
        """计算当前构建源的内容哈希（仅含真正喂给图谱的文件）。

        与 :meth:`_collect_source_documents` 的过滤边界一致；同时把
        ``chr/chr.bind`` 单独纳入指纹——它本身不入图谱，但会通过
        ``collect_project_files`` 影响每个角色文件的"# 角色：xxx" 前缀，
        进而改变图谱抽取结果，必须参与 freshness 比对。
        """
        hashes: dict[str, str] = {}

        try:
            project_files = collect_project_files(
                self.user_id,
                self.project_name,
                max_source_chars=self._max_source_chars,
            )
        except Exception:
            project_files = []

        for pf in project_files:
            # 只对 GraphRAG 真正消费的文件做 freshness 比对，
            # 节拍表 / chr.bind 等不入图谱的文件单独处理（chr.bind 见下方），
            # 避免用户改节拍表触发无谓的图谱重建。
            if pf.format_key not in self._GRAPHRAG_INDEX_FORMAT_KEYS:
                continue
            hashes[pf.rel_path] = self._hash_text(pf.content)

        # 别名表 chr.bind 自身不入图谱，但它驱动 enrich_character_content 的
        # 名字注入；改了它，所有角色文件的实际 content 会变。所以单独指纹化。
        try:
            bind_path = os.path.join(self._project_path, "chr", "chr.bind")
            if os.path.exists(bind_path):
                with open(bind_path, "r", encoding="utf-8") as f:
                    hashes["chr/chr.bind"] = self._hash_text(f.read())
        except Exception:
            pass

        return hashes

    def _needs_rebuild(self, metadata: dict[str, Any]) -> bool:
        """对比 metadata 中存的 file_hashes 与当前源文件哈希。"""
        if not isinstance(metadata, dict):
            return True
        if metadata.get("chunking_strategy") != GRAPHRAG_CHUNKING_STRATEGY_VERSION:
            return True
        stored = metadata.get("file_hashes")
        if not isinstance(stored, dict):
            # 旧版 metadata 没有 file_hashes，视为需要重建
            return True
        current = self._compute_file_hashes()
        if set(stored.keys()) != set(current.keys()):
            return True
        return any(stored.get(key) != current.get(key) for key in current)

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
        """构建"别名 → 主名"映射，用于图谱节点归一化。

        基础映射（ID → 主名）来自统一工具 ``load_character_id_name_map``；
        本方法在此之上额外扩展两类别名：
        1. 从主名本身解析（"主名(别名)"、"主名/别名"等写法）；
        2. 从角色 .md/.txt 头部的"别名："行解析。
        """
        from story.project_files import load_character_id_name_map

        alias_map: dict[str, str] = {}
        chr_dir = os.path.join(self._project_path, "chr")
        # 旁白角色对实体合并没有意义，去掉
        id_to_name = load_character_id_name_map(
            self.user_id, self.project_name, include_narrator=False, include_system=False,
        )
        if not id_to_name:
            return alias_map

        for cid, canonical in id_to_name.items():
            aliases = [canonical]

            # 兼容常见的“主名(别名)”或“主名/别名”写法
            for part in re.split(r"[()（）/|,，、]", canonical):
                item = part.strip()
                if item and item not in aliases:
                    aliases.append(item)

            # 从角色档案头部抽取显式声明的别名
            detail_path = os.path.join(chr_dir, f"{cid}.txt")
            if os.path.exists(detail_path):
                try:
                    with open(detail_path, "r", encoding="utf-8", errors="ignore") as f:
                        detail_text = f.read()
                    for alias in self._extract_aliases_from_text(detail_text):
                        if alias not in aliases:
                            aliases.append(alias)
                except Exception:
                    pass

            for alias in aliases:
                key = self._normalize_entity_name(alias)
                if key and key not in alias_map:
                    alias_map[key] = canonical

        return alias_map

    # GraphRAG 索引只关心叙事内容：世界观 / 梗概 / 大纲 / 角色设定 / 剧本或小说正文。
    # 其余 format_key（chrbind 元数据、beats 节拍表）一律不入图谱：
    #   - chrbind 是 ID→名字 JSON，没有叙事信息，且角色名已经通过 collect_project_files
    #     的 enrich_character_content 写入到每个角色文件 content 头部；
    #   - beats 节拍表与大纲信息高度重叠，会让 LLM 抽出大量重复关系。
    _GRAPHRAG_INDEX_FORMAT_KEYS: frozenset[str] = frozenset(
        {"worldview", "synopsis", "outline", "character", "arc", "novel"}
    )

    def _collect_source_documents(self) -> list[Document]:
        self._ensure_project_exists()

        # 复用项目级语义分块器，按场景 / 大纲节点 / 角色档案等叙事单元建图。
        # 这避免字符切片把关键人物关系切在两个 chunk 里，是 GraphRAG 与语义搜索的统一底座。
        chunker = SemanticChunker(
            max_chunk_tokens=max(100, self._chunk_size),
            sub_chunk_size=max(200, self._chunk_size),
            sub_chunk_overlap=max(0, self._chunk_overlap),
        )
        semantic_state = chunker.chunk_project_state(
            self.user_id,
            self.project_name,
            use_cache=True,
        )
        semantic_chunks = semantic_state.get("chunks") or []

        documents: list[Document] = []
        for chunk in semantic_chunks:
            metadata = dict(getattr(chunk, "metadata", {}) or {})
            format_key = str(metadata.get("format_key") or "")
            # 仅纳入叙事相关文件
            if format_key not in self._GRAPHRAG_INDEX_FORMAT_KEYS:
                continue
            text = str(getattr(chunk, "text", "") or "").strip()
            if not text:
                continue
            documents.append(Document(
                page_content=text,
                metadata={
                    **metadata,
                    "source": str(metadata.get("source") or ""),
                    "format_key": format_key,
                    "narrative_ref": getattr(chunk, "narrative_ref", "") or metadata.get("narrative_ref", ""),
                    "start_line": int(getattr(chunk, "start_line", 0) or 0),
                    "end_line": int(getattr(chunk, "end_line", 0) or 0),
                    "chunking_strategy": GRAPHRAG_CHUNKING_STRATEGY_VERSION,
                },
            ))

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

    @staticmethod
    def _format_chunk_source(chunk: Document) -> str:
        metadata = dict(getattr(chunk, "metadata", {}) or {})
        source = str(metadata.get("source") or "未知来源")
        ref = str(metadata.get("narrative_ref") or "").strip()
        start_line = int(metadata.get("start_line") or 0)
        end_line = int(metadata.get("end_line") or 0)
        location = ""
        if start_line and end_line:
            location = f"L{start_line}-L{end_line}"
        parts = [source]
        if ref:
            parts.append(ref)
        if location:
            parts.append(location)
        return " :: ".join(parts)

    def _canonicalize_entity(self, raw_name: str, alias_map: dict[str, str]) -> str:
        name = str(raw_name or "").strip()
        if not name:
            return name
        return alias_map.get(self._normalize_entity_name(name), name)

    def _build_graph(
        self,
        chunks: list[Document],
        alias_map: dict[str, str],
        on_chunk_done: Any = None,
    ) -> tuple[nx.Graph, int]:
        """从 chunks 抽取三元组并合并入图。

        ``on_chunk_done(done_chunks, total_chunks, triplets_collected, nodes, edges)``
        会在每个 chunk 处理完成后回调，用于上报后台构建进度。
        """
        graph = nx.Graph()
        triplet_count = 0
        total = len(chunks)

        for idx, chunk in enumerate(chunks):
            self._check_cancelled()
            source = self._format_chunk_source(chunk)
            logger.info(
                "[GraphRAG] 提取三元组 chunk=%s/%s source=%s chars=%s",
                idx + 1,
                total,
                source,
                len(chunk.page_content or ""),
            )
            triplets = self._extract_triplets(chunk.page_content)
            self._check_cancelled()
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

            logger.info(
                "[GraphRAG] chunk=%s/%s 完成，triplets=%s",
                idx + 1,
                total,
                len(triplets),
            )

            if callable(on_chunk_done):
                try:
                    on_chunk_done(
                        idx + 1,
                        total,
                        triplet_count,
                        int(graph.number_of_nodes()),
                        int(graph.number_of_edges()),
                    )
                except Exception:
                    # 进度回调不应影响构建主流程
                    pass

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

    def get_status(self, check_freshness: bool = True) -> dict[str, Any]:
        artifacts = self._artifacts
        metadata = self._load_metadata()
        graph_ready = (
            os.path.exists(artifacts.pickle_path)
            or os.path.exists(artifacts.graphml_path)
        )
        metadata_ready = os.path.exists(artifacts.metadata_path)
        build_state = self.get_build_state()

        needs_rebuild = False
        if graph_ready and metadata_ready:
            if check_freshness and build_state.get("status") not in (_ACTIVE_BUILD_STATUSES | {"error"}):
                try:
                    needs_rebuild = self._needs_rebuild(metadata)
                except Exception:
                    needs_rebuild = False
                if needs_rebuild:
                    build_state = {
                        **build_state,
                        "status": "stale",
                        "stage": "stale",
                    }
        else:
            # 无图谱文件：not_built（若没有进行中的构建状态）
            if build_state.get("status") not in (_ACTIVE_BUILD_STATUSES | {"error"}):
                build_state = {
                    **build_state,
                    "status": "not_built",
                    "stage": "idle",
                }
            needs_rebuild = False

        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "exists": os.path.isdir(artifacts.base_dir),
            "graph_ready": graph_ready,
            "metadata_ready": metadata_ready,
            "needs_rebuild": needs_rebuild,
            "build_state": build_state,
            "artifacts_dir": artifacts.base_dir,
            "metadata": metadata,
            "build_usage_key": self._build_usage_key,
            "query_agent_policy": "follow_caller_agent",
        }

    def reset(self) -> dict[str, Any]:
        self.cancel_background_build(wait_timeout=2.0)
        artifacts = self._artifacts
        removed = False
        if os.path.isdir(artifacts.base_dir):
            shutil.rmtree(artifacts.base_dir)
            removed = True
        # 同步清掉进程内的 build_state，避免 UI 上残留 ready/stale
        task_key = _build_task_key(self.user_id, self.project_name)
        with _build_state_lock:
            _build_state_registry.pop(task_key, None)
        return {
            "project": self.project_name,
            "user_id": self.user_id,
            "removed": removed,
            "artifacts_dir": artifacts.base_dir,
        }

    def build_index(self, force_rebuild: bool = False) -> dict[str, Any]:
        """同步执行索引构建。建议通过 ``start_background_build`` 在后台触发，
        前端可通过 ``get_status()`` 轮询 ``build_state`` 字段获取进度。
        """
        self._ensure_project_exists()
        started_at = datetime.now(timezone.utc).isoformat()

        # 入口：状态切到 building/prepare
        self._set_build_state(
            status="building",
            stage="prepare",
            error="",
            started_at=started_at,
            finished_at="",
            progress=self._empty_progress(),
        )

        try:
            self._check_cancelled()
            # 哈希与文件采集统一在这里完成，避免后续多次扫盘
            current_hashes = self._compute_file_hashes()
            self._check_cancelled()
            existing_metadata = self._load_metadata()
            artifacts = self._artifacts
            graph_ready = (
                os.path.exists(artifacts.pickle_path)
                or os.path.exists(artifacts.graphml_path)
            )

            # 复用判定：图谱文件已在 + 不强制重建 + 哈希与上次一致
            if graph_ready and not force_rebuild:
                stored_hashes = existing_metadata.get("file_hashes") if isinstance(existing_metadata, dict) else None
                if (
                    isinstance(stored_hashes, dict)
                    and set(stored_hashes.keys()) == set(current_hashes.keys())
                    and all(stored_hashes.get(k) == current_hashes.get(k) for k in current_hashes)
                ):
                    metadata = dict(existing_metadata or {})
                    metadata["reused"] = True
                    finished_at = metadata.get("built_at", started_at)
                    self._set_build_state(
                        status="ready",
                        stage="ready",
                        error="",
                        started_at=started_at,
                        finished_at=finished_at,
                        progress={
                            "total_chunks": int(metadata.get("chunks", 0) or 0),
                            "done_chunks": int(metadata.get("chunks", 0) or 0),
                            "triplets_collected": int(metadata.get("triplets", 0) or 0),
                            "source_docs": int(metadata.get("source_docs", 0) or 0),
                            "nodes": int(metadata.get("nodes", 0) or 0),
                            "edges": int(metadata.get("edges", 0) or 0),
                        },
                    )
                    return metadata

            docs = self._collect_source_documents()
            self._check_cancelled()
            if not docs:
                raise RuntimeError("未找到可用于构建 GraphRAG 的项目文本（世界观/角色/梗概/大纲/剧本）。")
            source_doc_count = len({str(doc.metadata.get("source") or "") for doc in docs if doc.metadata.get("source")})

            logger.info(
                "[GraphRAG] 开始构建 project=%s user_id=%s source_docs=%s timeout=%ss",
                self.project_name,
                self.user_id,
                source_doc_count,
                self._llm_timeout,
            )

            # 语义分块阶段：_collect_source_documents 已经产出场景/事件/角色等叙事单元
            self._set_build_state(
                status="building",
                stage="semantic_splitting",
                progress={
                    **self._empty_progress(),
                    "source_docs": source_doc_count,
                },
            )
            chunks = docs[: self._max_chunks]
            self._check_cancelled()
            logger.info(
                "[GraphRAG] 语义分块完成 project=%s chunks=%s max_tokens=%s overlap=%s",
                self.project_name,
                len(chunks),
                self._chunk_size,
                self._chunk_overlap,
            )

            # 抽取阶段：按 chunk 上报进度
            self._set_build_state(
                status="building",
                stage="extracting",
                progress={
                    "total_chunks": len(chunks),
                    "done_chunks": 0,
                    "triplets_collected": 0,
                    "source_docs": source_doc_count,
                    "nodes": 0,
                    "edges": 0,
                },
            )
            alias_map = self._load_character_alias_index()
            self._check_cancelled()

            def _report_chunk(done: int, total: int, triplets: int, nodes: int, edges: int) -> None:
                self._set_build_state(
                    status="building",
                    stage="extracting",
                    progress={
                        "total_chunks": total,
                        "done_chunks": done,
                        "triplets_collected": triplets,
                        "source_docs": source_doc_count,
                        "nodes": nodes,
                        "edges": edges,
                    },
                )

            graph, triplet_count = self._build_graph(chunks, alias_map, on_chunk_done=_report_chunk)
            self._check_cancelled()
            communities = self._build_communities(graph)

            # 持久化阶段
            self._set_build_state(
                status="building",
                stage="persisting",
                progress={
                    "total_chunks": len(chunks),
                    "done_chunks": len(chunks),
                    "triplets_collected": triplet_count,
                    "source_docs": len(docs),
                    "nodes": int(graph.number_of_nodes()),
                    "edges": int(graph.number_of_edges()),
                },
            )

            built_at = datetime.now(timezone.utc).isoformat()
            metadata: dict[str, Any] = {
                "version": "1.1",
                "built_at": built_at,
                "project": self.project_name,
                "user_id": self.user_id,
                "build_usage_key": self._build_usage_key,
                "query_agent_policy": "follow_caller_agent",
                "chunking_strategy": GRAPHRAG_CHUNKING_STRATEGY_VERSION,
                "alias_count": len(alias_map),
                "source_docs": source_doc_count,
                "chunks": len(chunks),
                "triplets": triplet_count,
                "nodes": int(graph.number_of_nodes()),
                "edges": int(graph.number_of_edges()),
                "communities": communities,
                "file_hashes": current_hashes,
                "reused": False,
            }

            self._persist(graph, metadata)
            logger.info(
                "[GraphRAG] 构建完成 project=%s triplets=%s nodes=%s edges=%s",
                self.project_name,
                triplet_count,
                graph.number_of_nodes(),
                graph.number_of_edges(),
            )

            self._set_build_state(
                status="ready",
                stage="ready",
                error="",
                started_at=started_at,
                finished_at=built_at,
                progress={
                    "total_chunks": len(chunks),
                    "done_chunks": len(chunks),
                    "triplets_collected": triplet_count,
                    "source_docs": source_doc_count,
                    "nodes": int(graph.number_of_nodes()),
                    "edges": int(graph.number_of_edges()),
                },
            )
            return metadata
        except GraphRAGBuildCancelledError as e:
            self._set_build_state(
                status="cancelled",
                stage="cancelled",
                error=str(e),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            raise
        except Exception as e:
            self._set_build_state(
                status="error",
                stage="error",
                error=str(e),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            raise

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
