import asyncio
import inspect
import sys
import types
import threading
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


def test_unified_entry_helpers_are_async():
    """两个统一入口必须是 async：保证不会在 async 路由里同步阻塞 event loop。"""
    assert inspect.iscoroutinefunction(routes._resolve_project_semantic_status)
    assert inspect.iscoroutinefunction(routes._trigger_project_semantic_refresh)


def test_trigger_project_semantic_refresh_runs_blocking_io_off_event_loop(monkeypatch):
    """统一入口必须把阻塞 IO 委派到线程池：调用线程 != 主 event loop 线程。"""
    seen_threads: list[int] = []
    main_thread_id = threading.get_ident()

    class FakeService:
        def __init__(self, user_id: str, project_name: str):
            assert user_id == "user_1"
            assert project_name == "project_1"

        def get_status(self, check_freshness: bool = True):
            seen_threads.append(threading.get_ident())
            return {
                "exists": True,
                "needs_rebuild": True,
                "build_state": {**_ready_build_state(), "status": "stale", "stage": "stale"},
            }

        def _compute_file_hashes(self):
            seen_threads.append(threading.get_ident())
            return {"世界观.txt": "abc"}

        def ensure_background_build_started(self, check_freshness: bool = True):
            seen_threads.append(threading.get_ident())
            return {
                "exists": True,
                "needs_rebuild": False,
                "build_state": _queued_build_state(),
            }

    monkeypatch.setitem(
        sys.modules,
        "agents.vector_index",
        types.SimpleNamespace(VectorIndexService=FakeService),
    )
    monkeypatch.setattr(
        routes,
        "get_project_settings",
        lambda user_id, project_name: {"semantic_search_enabled": True},
    )

    asyncio.run(routes._trigger_project_semantic_refresh("user_1", "project_1"))

    assert seen_threads, "service stub 应该至少被调用一次"
    assert all(tid != main_thread_id for tid in seen_threads), (
        "阻塞 IO 必须在 run_in_threadpool 里执行，不能跑在事件循环主线程上"
    )


def test_resolve_project_semantic_status_is_read_only(monkeypatch):
    """状态查询只读：不能触发后台构建。"""
    calls: list[tuple[str, object]] = []

    class FakeService:
        def __init__(self, user_id: str, project_name: str):
            assert user_id == "user_1"
            assert project_name == "project_1"

        def get_status(self, check_freshness: bool = True):
            calls.append(("get_status", check_freshness))
            return {
                "exists": True,
                "needs_rebuild": False,
                "build_state": _ready_build_state(),
            }

        def ensure_background_build_started(self, check_freshness: bool = True):
            calls.append(("ensure_background_build_started", check_freshness))
            raise AssertionError("status 路径不应触发后台构建")

    monkeypatch.setitem(
        sys.modules,
        "agents.vector_index",
        types.SimpleNamespace(VectorIndexService=FakeService),
    )

    result = asyncio.run(routes._resolve_project_semantic_status("user_1", "project_1", True))

    assert result["index_exists"] is True
    assert result["needs_rebuild"] is False
    assert result["build_state"]["status"] == "ready"
    assert calls == [("get_status", True)]


def test_trigger_project_semantic_refresh_starts_build_when_stale(monkeypatch):
    """显式刷新入口在 stale/缺失时启动后台构建，否则不触发。"""
    calls: list[tuple[str, object]] = []

    class FakeService:
        def __init__(self, user_id: str, project_name: str):
            assert user_id == "user_1"
            assert project_name == "project_1"

        def get_status(self, check_freshness: bool = True):
            calls.append(("get_status", check_freshness))
            return {
                "exists": True,
                "needs_rebuild": True,
                "build_state": {**_ready_build_state(), "status": "stale", "stage": "stale"},
            }

        def _compute_file_hashes(self):
            return {"世界观.txt": "abc"}

        def ensure_background_build_started(self, check_freshness: bool = True):
            calls.append(("ensure_background_build_started", check_freshness))
            return {
                "exists": True,
                "needs_rebuild": False,
                "build_state": _queued_build_state(),
            }

    monkeypatch.setitem(
        sys.modules,
        "agents.vector_index",
        types.SimpleNamespace(VectorIndexService=FakeService),
    )
    monkeypatch.setattr(
        routes,
        "get_project_settings",
        lambda user_id, project_name: {"semantic_search_enabled": True},
    )

    result = asyncio.run(routes._trigger_project_semantic_refresh("user_1", "project_1"))

    assert result["enabled"] is True
    assert result["triggered"] is True
    assert result["build_state"]["status"] == "queued"
    assert ("ensure_background_build_started", True) in calls


def test_trigger_project_semantic_refresh_skips_when_disabled(monkeypatch):
    """开关未开启时，刷新入口不应触发后台构建。"""
    calls: list[tuple[str, object]] = []

    class FakeService:
        def __init__(self, user_id: str, project_name: str):
            assert user_id == "user_1"
            assert project_name == "project_1"

        def get_status(self, check_freshness: bool = True):
            calls.append(("get_status", check_freshness))
            return {
                "exists": True,
                "needs_rebuild": True,
                "build_state": _ready_build_state(),
            }

        def ensure_background_build_started(self, check_freshness: bool = True):
            calls.append(("ensure_background_build_started", check_freshness))
            raise AssertionError("禁用时不应触发后台构建")

    monkeypatch.setitem(
        sys.modules,
        "agents.vector_index",
        types.SimpleNamespace(VectorIndexService=FakeService),
    )
    monkeypatch.setattr(
        routes,
        "get_project_settings",
        lambda user_id, project_name: {"semantic_search_enabled": False},
    )

    result = asyncio.run(routes._trigger_project_semantic_refresh("user_1", "project_1"))

    assert result["enabled"] is False
    assert result["triggered"] is False
    # 仍然允许做一次只读 status，但禁止触发构建
    assert all(name != "ensure_background_build_started" for name, _ in calls)


def test_disable_semantic_search_returns_existing_build_state(monkeypatch):
    monkeypatch.setattr(
        routes,
        "set_project_setting",
        lambda user_id, project_name, key, value: {"semantic_search_enabled": value},
    )
    async def _fake_resolve(user_id, project_name, enabled):
        return {
            "index_exists": True,
            "needs_rebuild": False,
            "build_state": _ready_build_state(),
        }

    monkeypatch.setattr(
        routes,
        "_resolve_project_semantic_status",
        _fake_resolve,
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
