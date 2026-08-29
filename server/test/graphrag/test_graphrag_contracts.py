from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import networkx as nx

from agents.graphrag.service import GRAPHRAG_CHUNKING_STRATEGY_VERSION, GraphRAGService
from story.project_files import collect_project_files, load_outline_data
from story.semantic_chunker.chunker import SemanticChunker


def test_character_graph_route_is_registered_as_read_only_get() -> None:
    from agents.routes.graphrag_routes import graphrag_router

    route = next(
        item for item in graphrag_router.routes
        if getattr(item, "path", "") == "/api/graphrag/character-graph"
    )
    assert route.methods == {"GET"}


def test_graphrag_reuses_build_llm_client_with_stable_protocol(monkeypatch) -> None:
    calls = []
    client = object()

    class FakeMatchbox:
        def get_user_llm(self, *args, **kwargs):
            calls.append((args, kwargs))
            return client

    monkeypatch.setattr(
        "agents.graphrag.service.matchbox",
        lambda: FakeMatchbox(),
    )
    service = GraphRAGService("12", "demo")

    assert service._get_build_llm() is client
    assert service._get_build_llm() is client
    assert service._build_triplet_system_prompt() == service._build_triplet_system_prompt()
    assert len(calls) == 1
    assert calls[0][1]["usage_key"] == service._build_usage_key


def test_character_subgraph_reuses_character_ids_aliases_and_graph_evidence(
    monkeypatch,
) -> None:
    graph = nx.Graph()
    graph.add_edge(
        "阿棠",
        "林烬",
        relation="盟友",
        sources="角色/沈棠 :: 角色档案 | stories/第一章.arc :: 第一场",
        evidence_samples="并肩调查旧案 || 林烬替沈棠隐瞒行踪",
        evidence_count=2,
    )
    graph.add_edge("林烬", "旧钥匙", relation="持有", evidence_count=1)
    records = {
        "-1": {"name": "旁白", "content": ""},
        "1": {"name": "沈棠", "content": "别名：阿棠\n阵营：档案局"},
        "2": {"name": "林烬", "content": "身份：调查员"},
        "3": {"name": "周望", "content": "身份：记者"},
    }
    service = GraphRAGService("12", "demo")
    monkeypatch.setattr(service, "_ensure_project_exists", lambda: None)
    monkeypatch.setattr(service, "_load_graph", lambda: graph)
    monkeypatch.setattr(service, "_load_metadata", lambda: {"built_at": "2026-08-05T00:00:00Z", "nodes": 4, "edges": 2})
    monkeypatch.setattr("agents.graphrag.service.read_character_records", lambda *_: records)
    monkeypatch.setattr(
        service,
        "_load_character_alias_index",
        lambda: {"沈棠": "沈棠", "阿棠": "沈棠", "林烬": "林烬", "周望": "周望"},
    )

    payload = service.get_character_subgraph()

    assert [node["id"] for node in payload["nodes"]] == ["1", "2", "3"]
    assert payload["nodes"][0]["graph_name"] == "阿棠"
    assert payload["nodes"][2]["in_graph"] is False
    assert payload["edges"] == [
        {
            "id": "1:2",
            "source": "1",
            "target": "2",
            "relation": "盟友",
            "evidence_count": 2,
            "sources": ["角色/沈棠 :: 角色档案", "stories/第一章.arc :: 第一场"],
            "evidence_samples": ["并肩调查旧案", "林烬替沈棠隐瞒行踪"],
        }
    ]


def test_agent_research_reads_author_confirmed_character_relations(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.tools.research import _manual_relation_lines
    from core.character_relations import create_character_relation
    from core.character_store import write_character_records

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    write_character_records(
        "21",
        "demo",
        {
            "0": {"name": "甲", "content": ""},
            "1": {"name": "乙", "content": ""},
        },
    )
    create_character_relation("21", "demo", source="0", target="1", relation="盟友", note="共同目标")

    assert _manual_relation_lines("21", "demo") == ["甲 ↔ 乙：盟友；备注：共同目标"]


def test_character_graph_uses_worldview_only_and_has_separate_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from agents.graphrag.character_service import CharacterGraphService
    from core.character_store import write_character_records

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_22" / "projects" / "demo"
    project_path.mkdir(parents=True)
    (project_path / "世界观.txt").write_text("甲与乙在旧城共同守护边境。", encoding="utf-8")
    (project_path / "大纲.txt").write_text("甲与乙在第三章决裂。", encoding="utf-8")
    write_character_records(
        "22",
        "demo",
        {
            "0": {"name": "甲", "content": "角色档案正文不应作为角色图输入。"},
            "1": {"name": "乙", "content": "角色档案正文不应作为角色图输入。"},
        },
    )

    service = CharacterGraphService("22", "demo")
    documents = service._collect_source_documents()

    assert [document.metadata["source"] for document in documents] == ["世界观.txt"]
    assert all("角色档案正文" not in document.page_content for document in documents)
    assert service._artifacts.base_dir.endswith(os.path.join(".graphrag", "character"))
    assert service._task_key().startswith("character:")


def test_project_file_collector_reads_nested_story_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_11" / "projects" / "demo"
    story_dir = project_path / "stories" / "一 · 开端"
    story_dir.mkdir(parents=True)
    (story_dir / "1-1 钟楼交易.arc").write_text(
        "# 钟楼交易\n[-1] 沈棠把旧钥匙交给林烬。",
        encoding="utf-8",
    )

    files = collect_project_files("11", "demo")

    assert any(item.rel_path == "stories/一 · 开端/1-1 钟楼交易.arc" for item in files)


def test_graphrag_uses_semantic_chunks_with_narrative_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_12" / "projects" / "demo"
    story_dir = project_path / "stories" / "一 · 开端"
    story_dir.mkdir(parents=True)
    from core.character_store import write_character_records
    write_character_records(
        "12",
        "demo",
        {
            "1": {"name": "沈棠", "content": "职业：档案管理员\n秘密：知道旧钥匙来历。"},
            "2": {"name": "林烬", "content": "职业：调查员"},
        },
    )
    (project_path / "大纲.txt").write_text(
        "## 一 · 开端\n### 1-1 钟楼交易\n沈棠把旧钥匙交给林烬。",
        encoding="utf-8",
    )
    (story_dir / "1-1 钟楼交易.arc").write_text(
        arc_text := "# 钟楼交易\n[-1] 沈棠把旧钥匙交给林烬。\n\n# 档案室\n[-1] 林烬用旧钥匙打开档案室。",
        encoding="utf-8",
    )
    outline_hash = SemanticChunker()._compute_outline_hash(load_outline_data("12", "demo"))
    (project_path / ".chunks_cache.json").write_text(
        json.dumps(
            {
                "version": "2.0",
                "outline_hash": outline_hash,
                "files": {
                    "stories/一 · 开端/1-1 钟楼交易.arc": {
                        "file_hash": hashlib.md5(arc_text.encode("utf-8")).hexdigest(),
                        "chunks": [
                            {
                                "text": "# 旧缓存场景\n[-1] 旧内容。",
                                "metadata": {
                                    "source": "stories/一 · 开端/1-1 钟楼交易.arc",
                                    "format_key": "arc",
                                    "scene_title": "旧缓存场景",
                                },
                                "start_line": 1,
                                "end_line": 2,
                                "narrative_ref": "剧本 > 旧缓存",
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    docs = GraphRAGService("12", "demo")._collect_source_documents()
    arc_docs = [doc for doc in docs if doc.metadata.get("format_key") == "arc"]

    assert len(arc_docs) == 2
    assert all(doc.metadata.get("chunking_strategy") == GRAPHRAG_CHUNKING_STRATEGY_VERSION for doc in docs)
    assert any(doc.metadata.get("scene_title") == "钟楼交易" for doc in arc_docs)
    assert any(doc.metadata.get("scene_title") == "档案室" for doc in arc_docs)
    assert all("narrative_ref" in doc.metadata for doc in arc_docs)
    assert all("【可用说话人】" in doc.page_content for doc in arc_docs)
    assert all("[沈棠]" in doc.page_content for doc in arc_docs)
    assert all("[林烬]" in doc.page_content for doc in arc_docs)
    assert all("[1] =" not in doc.page_content for doc in arc_docs)
    assert all("[2] =" not in doc.page_content for doc in arc_docs)


def test_graphrag_chunking_uses_same_source_budget_as_freshness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    (tmp_path / "uid_33" / "projects" / "demo").mkdir(parents=True)
    observed = []

    def fake_chunk(self, user_id, project_name, **kwargs):
        observed.append(kwargs.get("max_source_chars"))
        return {"chunks": []}

    monkeypatch.setattr(SemanticChunker, "chunk_project_state", fake_chunk)
    service = GraphRAGService("33", "demo")

    assert service._collect_source_documents() == []
    assert observed == [service._max_source_chars]


def test_arc_chunks_expose_character_names_without_changing_arc_runtime_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_16" / "projects" / "demo"
    story_dir = project_path / "stories" / "一 · 开端"
    story_dir.mkdir(parents=True)
    from core.character_store import write_character_records
    write_character_records(
        "16",
        "demo",
        {
            "1": {"name": "沈棠", "content": "# 沈棠"},
            "2": {"name": "林烬", "content": "# 林烬"},
        },
    )
    arc_text = "# 钟楼交易\n[沈棠]\n把钥匙收好。\n[林烬]\n我会查清楚。"
    (story_dir / "1-1 钟楼交易.arc").write_text(arc_text, encoding="utf-8")

    files = collect_project_files("16", "demo")
    arc_file = next(item for item in files if item.format_key == "arc")

    assert arc_file.content.startswith("【可用说话人】")
    assert "[沈棠]" in arc_file.content
    assert "[林烬]" in arc_file.content
    assert "[1] =" not in arc_file.content
    assert "[2] =" not in arc_file.content
    assert "[-1] =" not in arc_file.content
    assert "[-2] =" not in arc_file.content
    assert arc_text in arc_file.content

    chunks = SemanticChunker().chunk_file(arc_file, load_outline_data("16", "demo"))
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].text.startswith("【可用说话人】")
    assert "[沈棠]" in chunks[0].text
    assert "[沈棠]\n把钥匙收好。" in chunks[0].text
