import shutil
import sys
import uuid
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.agent_tools import _get_search_results, _store_search_results, replace_from_search, search_project
from agents.vector_index.service import IndexBuildNotReadyError, VectorIndexService
from core.request_context import current_project_name, current_user_id
from core.utils import get_project_path
from story.semantic_chunker.base import SemanticChunk


def test_search_project_returns_all_matches_in_same_chunk(monkeypatch):
    chunk = SemanticChunk(
        text="张三来到门前。张三又回头看了一眼。最后张三还是进门了。",
        metadata={"source": "世界观.txt", "format_key": "worldview"},
        start_line=1,
        end_line=1,
        narrative_ref="世界观 > 门前片段",
    )

    monkeypatch.setattr(
        "story.semantic_chunker.SemanticChunker.chunk_project",
        lambda self, user_id, project_name, use_cache=True: [chunk],
    )
    monkeypatch.setattr(
        "agents.tools.search._locate_chunk_positions",
        lambda user_id, project_name, chunks: [{
            "source": "世界观.txt",
            "content": chunk.text,
            "line_starts": [0],
            "chunk_start": 0,
            "chunk_end": len(chunk.text),
        }],
    )

    user_token = current_user_id.set(f"test_user_{uuid.uuid4().hex[:8]}")
    project_token = current_project_name.set(f"project_{uuid.uuid4().hex[:8]}")
    try:
        output = search_project.invoke({"pattern": "张三", "case_sensitive": False})
        results = _get_search_results()

        assert "找到 3 处匹配" in output
        assert len(results) == 3
        assert [item["match_text"] for item in results] == ["张三", "张三", "张三"]
    finally:
        current_user_id.reset(user_token)
        current_project_name.reset(project_token)


def test_replace_from_search_uses_selected_regex_hit_span():
    user_id = f"test_replace_{uuid.uuid4().hex[:8]}"
    project_name = f"project_{uuid.uuid4().hex[:8]}"
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)
    file_path = project_path / "世界观.txt"
    original = "颜色: 红\n颜色: 蓝\n"
    file_path.write_text(original, encoding="utf-8")

    first_start = original.index("颜色: 红")
    first_end = first_start + len("颜色: 红")
    second_start = original.index("颜色: 蓝")
    second_end = second_start + len("颜色: 蓝")

    user_token = current_user_id.set(user_id)
    project_token = current_project_name.set(project_name)
    try:
        _store_search_results([
            {
                "index": 0,
                "rel_path": "世界观.txt",
                "pattern": r"颜色: \S+",
                "case_sensitive": True,
                "file_span_start": first_start,
                "file_span_end": first_end,
                "narrative_ref": "世界观 > 第一处",
                "chunk_text": "颜色: 红",
                "match_text": "颜色: 红",
            },
            {
                "index": 1,
                "rel_path": "世界观.txt",
                "pattern": r"颜色: \S+",
                "case_sensitive": True,
                "file_span_start": second_start,
                "file_span_end": second_end,
                "narrative_ref": "世界观 > 第二处",
                "chunk_text": "颜色: 蓝",
                "match_text": "颜色: 蓝",
            },
        ])

        output = replace_from_search.invoke({"indices": [1], "replacement": "颜色: 绿"})
        updated = file_path.read_text(encoding="utf-8")

        assert "成功 1 处，失败 0 处" in output
        assert updated == "颜色: 红\n颜色: 绿\n"
    finally:
        current_user_id.reset(user_token)
        current_project_name.reset(project_token)
        shutil.rmtree(project_path, ignore_errors=True)


def test_vector_query_starts_background_build_when_index_missing(monkeypatch):
    service = VectorIndexService(user_id="user_1", project_name="project_1")
    original_isdir = Path
    calls: list[bool] = []

    monkeypatch.setattr(
        "agents.vector_index.service.os.path.isdir",
        lambda path: False if path == service._persist_dir else True,
    )
    monkeypatch.setattr(
        VectorIndexService,
        "start_background_build",
        lambda self, force_rebuild=False: calls.append(force_rebuild) or {
            "status": "queued",
            "stage": "queued",
            "error": "",
            "progress": {},
        },
    )
    monkeypatch.setattr(
        VectorIndexService,
        "get_status",
        lambda self: {
            "exists": False,
            "metadata": {},
            "needs_rebuild": False,
            "build_state": {
                "status": "queued",
                "stage": "queued",
                "error": "",
                "progress": {},
            },
        },
    )

    with pytest.raises(IndexBuildNotReadyError) as exc_info:
        service.query("测试查询")

    assert calls == [False]
    assert exc_info.value.status_payload["build_state"]["status"] == "queued"
