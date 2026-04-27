import shutil
import sys
import uuid
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.tools.search import _get_search_results, _store_search_results, replace_from_search, search_project
from core.request_context import current_project_name, current_user_id
from core.utils import get_project_path


def test_search_project_returns_all_matches_in_same_file():
    user_id = f"test_search_{uuid.uuid4().hex[:8]}"
    project_name = f"project_{uuid.uuid4().hex[:8]}"
    project_path = Path(get_project_path(user_id, project_name))
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "世界观.txt").write_text(
        "张三来到门前。张三又回头看了一眼。最后张三还是进门了。",
        encoding="utf-8",
    )

    user_token = current_user_id.set(user_id)
    project_token = current_project_name.set(project_name)
    try:
        output = search_project.invoke({"pattern": "张三", "case_sensitive": False})
        results = _get_search_results()

        assert "找到 3 处匹配" in output
        assert len(results) == 3
        assert [item["match_text"] for item in results] == ["张三", "张三", "张三"]
    finally:
        current_user_id.reset(user_token)
        current_project_name.reset(project_token)
        shutil.rmtree(project_path, ignore_errors=True)


def test_search_project_scans_raw_story_files_not_cleaned_semantic_chunks():
    user_id = f"test_raw_search_{uuid.uuid4().hex[:8]}"
    project_name = f"project_{uuid.uuid4().hex[:8]}"
    project_path = Path(get_project_path(user_id, project_name))
    stories_path = project_path / "stories"
    stories_path.mkdir(parents=True, exist_ok=True)
    (stories_path / "001-001-测试.arc").write_text(
        "# 场景\n<conception>隐藏线索：银色怀表</conception>\n[-1] 他推门而入。\n",
        encoding="utf-8",
    )

    user_token = current_user_id.set(user_id)
    project_token = current_project_name.set(project_name)
    try:
        output = search_project.invoke({"pattern": "隐藏线索：银色怀表", "case_sensitive": True})
        results = _get_search_results()

        assert "找到 1 处匹配" in output
        assert len(results) == 1
        assert results[0]["rel_path"] == "stories/001-001-测试.arc"
        assert results[0]["match_text"] == "隐藏线索：银色怀表"
    finally:
        current_user_id.reset(user_token)
        current_project_name.reset(project_token)
        shutil.rmtree(project_path, ignore_errors=True)


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
    pytest.importorskip("langchain_chroma")
    from agents.vector_index.service import IndexBuildNotReadyError, VectorIndexService

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
