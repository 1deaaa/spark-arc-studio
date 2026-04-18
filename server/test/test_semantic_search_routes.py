import asyncio
import sys
import types
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.routes import semantic_search_routes as routes


def _queued_build_state() -> dict:
    return {
        "status": "queued",
        "stage": "queued",
        "error": "",
        "started_at": "",
        "finished_at": "",
        "progress": {
            "total_files": 0,
            "done_files": 0,
            "total_chunks": 0,
            "embedded_chunks": 0,
            "changed_files": 0,
            "removed_files": 0,
            "reused_files": 0,
        },
    }


def _ready_build_state() -> dict:
    return {
        "status": "ready",
        "stage": "ready",
        "error": "",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:00+00:00",
        "progress": {
            "total_files": 3,
            "done_files": 3,
            "total_chunks": 12,
            "embedded_chunks": 12,
            "changed_files": 0,
            "removed_files": 0,
            "reused_files": 3,
        },
    }


def test_resolve_project_semantic_status_starts_background_build_for_enabled_project(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeService:
        def __init__(self, user_id: str, project_name: str):
            assert user_id == "user_1"
            assert project_name == "project_1"

        def get_status(self, check_freshness: bool = True):
            calls.append(("get_status", check_freshness))
            return {
                "exists": False,
                "needs_rebuild": False,
                "build_state": routes._empty_build_state(),
            }

        def start_background_build(self, force_rebuild: bool = False):
            calls.append(("start_background_build", force_rebuild))
            return _queued_build_state()

    monkeypatch.setitem(
        sys.modules,
        "agents.vector_index",
        types.SimpleNamespace(VectorIndexService=FakeService),
    )

    result = routes._resolve_project_semantic_status("user_1", "project_1", True)

    assert result["index_exists"] is False
    assert result["needs_rebuild"] is False
    assert result["build_state"]["status"] == "queued"
    assert calls == [
        ("get_status", False),
        ("get_status", True),
        ("start_background_build", False),
    ]


def test_disable_semantic_search_returns_existing_build_state(monkeypatch):
    monkeypatch.setattr(
        routes,
        "set_project_setting",
        lambda user_id, project_name, key, value: {"semantic_search_enabled": value},
    )
    monkeypatch.setattr(
        routes,
        "_resolve_project_semantic_status",
        lambda user_id, project_name, enabled: {
            "index_exists": True,
            "needs_rebuild": False,
            "build_state": _ready_build_state(),
        },
    )

    result = asyncio.run(
        routes.disable_semantic_search(
            routes.ProjectNameRequest(projectName="project_1"),
            {"user_id": "user_1"},
        )
    )

    assert result["success"] is True
    assert result["enabled"] is False
    assert result["index_exists"] is True
    assert result["needs_rebuild"] is False
    assert result["build_state"]["status"] == "ready"
