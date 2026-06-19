from __future__ import annotations

import asyncio

from agents.routes import semantic_search_routes as routes
from agents.vector_index import local_embedding


def test_set_local_embedding_primes_startup_state_before_spawn(monkeypatch) -> None:
    status = {
        "configured": False,
        "running": False,
        "alive": False,
        "startup": {
            "phase": "idle",
            "message": "",
            "progress": 0,
            "error": "",
            "updated_at": "",
        },
    }
    calls = {"mark": 0}

    def fake_mark_starting():
        calls["mark"] += 1
        status["startup"] = {
            "phase": "starting",
            "message": "开始加载本地嵌入服务",
            "progress": 1,
            "error": "",
            "updated_at": "2026-06-20T00:00:00Z",
        }
        return dict(status)

    def fake_get_status():
        return {
            **status,
            "startup": dict(status["startup"]),
        }

    class FakeThread:
        def __init__(self, target, name=None, daemon=None):
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(routes, "set_local_embedding_enabled", lambda enabled: {"local_embedding_enabled": bool(enabled)})
    monkeypatch.setattr(routes.threading, "Thread", FakeThread)
    monkeypatch.setattr(local_embedding, "mark_local_embedding_starting", fake_mark_starting)
    monkeypatch.setattr(local_embedding, "get_local_embedding_status", fake_get_status)
    monkeypatch.setattr(local_embedding, "start_local_embedding_service", lambda: None)
    monkeypatch.setattr(local_embedding, "stop_local_embedding_service", lambda: None)

    async def invoke():
        return await routes.set_local_embedding(
            routes.LocalEmbeddingToggleRequest(enabled=True),
            admin_user={"user_id": "u-1"},
        )

    result = asyncio.run(invoke())

    assert calls["mark"] == 1
    assert result["success"] is True
    assert result["enabled"] is True
    assert result["status"]["startup"]["phase"] == "starting"
    assert result["status"]["startup"]["message"] == "开始加载本地嵌入服务"
    assert result["status"]["startup"]["progress"] == 1
