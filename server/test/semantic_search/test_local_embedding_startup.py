from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from agents.routes import semantic_search_routes as routes
from agents.vector_index import local_embedding
from core.runtime_cache import configure_runtime_cache_environment, get_runtime_cache_dir


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


def test_start_local_embedding_does_not_hold_state_lock_while_building_command(monkeypatch) -> None:
    observed_progress: list[int] = []

    def fake_alive(*args, **kwargs):
        return False

    def fake_build_command():
        local_embedding._set_startup_state("downloading_model", "正在下载本地嵌入模型", progress=23)
        observed_progress.append(local_embedding._get_startup_state()["progress"])
        return ["llama-server", "--embedding"]

    class FakeProcess:
        pid = 12345

        def poll(self):
            return 0

    def fake_popen(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(local_embedding, "_process", None)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", fake_alive)
    monkeypatch.setattr(local_embedding, "build_local_embedding_command", fake_build_command)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(local_embedding, "get_local_embedding_status", lambda: {
        "configured": True,
        "running": False,
        "alive": False,
        "startup": local_embedding._get_startup_state(),
    })

    status = local_embedding.start_local_embedding_service()

    assert observed_progress == [23]
    assert status["startup"]["phase"] == "error"
    assert status["startup"]["progress"] == 100


def test_local_embedding_runtime_cache_can_be_overridden(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "runtime-cache"
    monkeypatch.setenv("SPARKARC_RUNTIME_CACHE_DIR", str(cache_root))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)
    monkeypatch.delenv("TIKTOKEN_CACHE_DIR", raising=False)
    monkeypatch.delenv("SPARKARC_LOCAL_EMBEDDING_MODEL_PATH", raising=False)
    monkeypatch.delenv("SPARKARC_LLAMA_CPP_RUNTIME_DIR", raising=False)

    configured = configure_runtime_cache_environment()

    assert get_runtime_cache_dir() == cache_root
    assert configured["HF_HOME"] == str(cache_root / "huggingface")
    assert local_embedding.get_default_model_path() == cache_root / "models" / "embedding" / local_embedding.QWEN3_GGUF_FILENAME
    assert local_embedding.get_llama_cpp_runtime_dir() == cache_root / "llama.cpp"
    assert local_embedding.get_llama_cpp_log_path() == cache_root / "logs" / "local_embedding_llama_server.log"


def test_start_local_embedding_reports_llama_server_log_tail(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "local_embedding_llama_server.log"

    def fake_alive(*args, **kwargs):
        return False

    class FakeProcess:
        pid = 12345
        returncode = 42

        def poll(self):
            return 42

    def fake_popen(*args, **kwargs):
        log_path.write_text("llama.cpp: unsupported pooling type\n", encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(local_embedding, "_process", None)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", fake_alive)
    monkeypatch.setattr(local_embedding, "build_local_embedding_command", lambda: ["llama-server", "--embedding"])
    monkeypatch.setattr(local_embedding, "get_llama_cpp_log_path", lambda: log_path)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    status = local_embedding.start_local_embedding_service()

    assert status["startup"]["phase"] == "error"
    assert "退出码 42" in status["startup"]["error"]
    assert "unsupported pooling type" in status["startup"]["error"]


def test_stopped_startup_process_does_not_overwrite_idle_state(monkeypatch) -> None:
    class FakeProcess:
        pid = 12345
        returncode = 0

        def poll(self):
            return 0

    process = FakeProcess()

    def fake_status():
        local_embedding._process = None
        local_embedding._set_startup_state(
            "idle",
            "本地嵌入服务已停止",
            progress=0,
            error="",
        )
        return {
            "configured": True,
            "running": False,
            "alive": False,
            "startup": local_embedding._get_startup_state(),
        }

    monkeypatch.setattr(local_embedding, "_process", None)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", lambda *args, **kwargs: False)
    monkeypatch.setattr(local_embedding, "build_local_embedding_command", lambda: ["llama-server", "--embedding"])
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(local_embedding, "get_local_embedding_status", fake_status)

    status = local_embedding.start_local_embedding_service()

    assert status["startup"]["phase"] == "idle"
    assert status["startup"]["error"] == ""


def test_stop_local_embedding_clears_previous_startup_error(monkeypatch) -> None:
    class FakeRunningProcess:
        pid = 12345

        def __init__(self) -> None:
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    process = FakeRunningProcess()
    monkeypatch.setattr(local_embedding, "_process", process)
    monkeypatch.setattr(local_embedding, "get_local_embedding_status", lambda: {
        "configured": True,
        "running": False,
        "alive": False,
        "startup": local_embedding._get_startup_state(),
    })
    local_embedding._set_startup_state(
        "error",
        "本地嵌入服务启动失败",
        progress=100,
        error="llama-server 已退出，退出码 0",
    )

    status = local_embedding.stop_local_embedding_service()

    assert status["startup"]["phase"] == "idle"
    assert status["startup"]["progress"] == 0
    assert status["startup"]["error"] == ""
