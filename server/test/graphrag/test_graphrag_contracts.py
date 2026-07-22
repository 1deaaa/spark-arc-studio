from __future__ import annotations

import json
import hashlib
from pathlib import Path

from agents.graphrag.service import GRAPHRAG_CHUNKING_STRATEGY_VERSION, GraphRAGService
from story.project_files import collect_project_files, load_outline_data
from story.semantic_chunker.chunker import SemanticChunker


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
