from __future__ import annotations

import asyncio

import pytest

from agents.routes import semantic_search_routes as routes
from agents.vector_index import local_embedding
from agents.vector_index import service as vector_service
from agents.vector_index.embedding_contract import (
    QWEN3_EMBEDDING_DIMENSIONS,
    embedding_extra_body,
)


class _FakeLocalEmbeddings:
    def __init__(self, **kwargs):
        self.model = kwargs.get("model", "local")

    def embed_query(self, text: str) -> list[float]:
        return [0.01] * QWEN3_EMBEDDING_DIMENSIONS


class _FakeCloudEmbeddings:
    model = "Qwen/Qwen3-Embedding-0.6B"

    def embed_query(self, text: str) -> list[float]:
        return [0.01] * QWEN3_EMBEDDING_DIMENSIONS


class _EmptyQuery:
    def filter_by(self, **kwargs):
        return self

    def first(self):
        return None


class _EmptySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self, *args, **kwargs):
        return _EmptyQuery()


class _CloudMatchbox:
    Session = _EmptySession

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def get_user_embedding(self, user_id: str, **kwargs):
        self.calls.append((user_id, kwargs))
        return _FakeCloudEmbeddings()


def test_enable_semantic_search_uses_local_runtime_without_cloud_key(monkeypatch) -> None:
    cloud_calls = {"count": 0}

    def fail_if_cloud_selected():
        cloud_calls["count"] += 1
        raise AssertionError("本地嵌入已启用，不应读取云端平台")

    async def fake_refresh(user_id: str, project_name: str) -> dict:
        return {
            "index_exists": False,
            "needs_rebuild": False,
            "build_state": routes._empty_build_state(),
        }

    monkeypatch.setattr(routes, "get_local_embedding_enabled", lambda: True)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", lambda **kwargs: True)
    monkeypatch.setattr(local_embedding, "local_embedding_model_name", lambda: "Qwen3-Embedding-Local")
    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", _FakeLocalEmbeddings)
    monkeypatch.setattr("llm.agen_matchbox.matchbox", fail_if_cloud_selected)
    monkeypatch.setattr(routes, "set_project_setting", lambda *args, **kwargs: {"semantic_search_enabled": True})
    monkeypatch.setattr(routes, "_trigger_project_semantic_refresh", fake_refresh)

    result = asyncio.run(routes.enable_semantic_search(
        routes.ProjectNameRequest(projectName="本地项目"),
        user={"user_id": "u-local"},
    ))

    assert result["success"] is True
    assert result["embedding_platform_name"] == "local"
    assert result["embedding_model_name"] == "Qwen3-Embedding-Local"
    assert cloud_calls["count"] == 0


def test_local_runtime_not_ready_does_not_fall_back_to_cloud(monkeypatch) -> None:
    cloud_calls = {"count": 0}

    def fail_if_cloud_selected():
        cloud_calls["count"] += 1
        raise AssertionError("本地嵌入未就绪时也不应静默回退云端")

    monkeypatch.setattr(routes, "get_local_embedding_enabled", lambda: True)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", lambda **kwargs: False)
    monkeypatch.setattr("llm.agen_matchbox.matchbox", fail_if_cloud_selected)

    with pytest.raises(ValueError, match="本地嵌入服务尚未就绪"):
        asyncio.run(routes._test_active_embedding_runtime("u-local"))

    assert cloud_calls["count"] == 0


def test_disabled_local_runtime_tests_matchbox_default_embedding(monkeypatch) -> None:
    cloud_matchbox = _CloudMatchbox()

    monkeypatch.setattr(routes, "get_local_embedding_enabled", lambda: False)
    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: cloud_matchbox)

    result = asyncio.run(routes._test_active_embedding_runtime("u-cloud"))

    assert result["success"] is True
    assert result["model_name"] == "Qwen/Qwen3-Embedding-0.6B"
    assert cloud_matchbox.calls == [
        ("u-cloud", {"extra_body": embedding_extra_body()}),
    ]


def test_vector_service_does_not_use_cloud_when_local_runtime_is_selected(
    monkeypatch,
    tmp_path,
) -> None:
    cloud_calls = {"count": 0}

    class _CloudMatchbox:
        def get_user_embedding(self, *args, **kwargs):
            cloud_calls["count"] += 1
            raise AssertionError("实际索引构建不应静默回退云端")

    monkeypatch.setattr(vector_service, "get_project_path", lambda *args: str(tmp_path))
    monkeypatch.setattr("core.system_settings.get_local_embedding_enabled", lambda: True)
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", lambda **kwargs: False)
    monkeypatch.setattr(vector_service, "matchbox", lambda: _CloudMatchbox())

    service = vector_service.VectorIndexService("u-local", "本地项目")
    with pytest.raises(RuntimeError, match="本地嵌入服务尚未就绪"):
        service._get_embeddings()

    assert cloud_calls["count"] == 0


def test_vector_service_uses_matchbox_default_when_local_runtime_is_disabled(
    monkeypatch,
    tmp_path,
) -> None:
    cloud_matchbox = _CloudMatchbox()

    monkeypatch.setattr(vector_service, "get_project_path", lambda *args: str(tmp_path))
    monkeypatch.setattr("core.system_settings.get_local_embedding_enabled", lambda: False)
    monkeypatch.setattr(vector_service, "matchbox", lambda: cloud_matchbox)

    service = vector_service.VectorIndexService("u-cloud", "在线项目")
    embeddings = service._get_embeddings()

    assert embeddings.model == "Qwen/Qwen3-Embedding-0.6B"
    assert cloud_matchbox.calls == [
        ("u-cloud", {"extra_body": embedding_extra_body()}),
    ]


def test_vector_index_hashes_include_arc_after_large_root_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "core.project_settings.is_visual_illustration_enabled",
        lambda user_id, project_name: False,
    )
    monkeypatch.setattr(
        "core.project_settings.is_attachment_index_enabled",
        lambda user_id, project_name: False,
    )
    project_path = tmp_path / "uid_u-large" / "projects" / "长文本项目"
    stories_path = project_path / "stories" / "一 · 开端"
    stories_path.mkdir(parents=True)
    (project_path / "世界观.txt").write_text("世" * 610_000, encoding="utf-8")
    arc_path = stories_path / "1-1 初遇.__spark__chap=001.scene=001.order=001001.arc"
    arc_path.write_text("# 1-1 初遇\n[旁白]\n必须进入语义索引的正文。", encoding="utf-8")

    service = vector_service.VectorIndexService("u-large", "长文本项目")
    hashes = service._compute_file_hashes()

    assert "stories/一 · 开端/1-1 初遇.__spark__chap=001.scene=001.order=001001.arc" in hashes
