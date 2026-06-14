"""
守护对象：
- 项目级向量索引默认使用 LanceDB 本地后端
- 向量索引构建、按 format_key 过滤查询、重置流程可在无真实上游 API 时跑通

本测试禁止：
- 调用真实 Embedding 或 LLM
- 读取用户真实项目数据
- 把索引产物写入受 Git 跟踪的测试目录
"""

from __future__ import annotations

from pathlib import Path

from agents.vector_index.service import VectorIndexService
from agents.vector_index.embedding_contract import (
    QWEN3_EMBEDDING_DIMENSIONS,
    build_query_text,
    embedding_contract_metadata,
)
from story.semantic_chunker import SemanticChunk


class _FakeEmbeddings:
    def _vector(self, text: str) -> list[float]:
        seed = sum(ord(ch) for ch in text)
        return [float(seed % 7), float((seed // 7) % 7), 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_lancedb_vector_index_build_query_and_reset(tmp_path, monkeypatch):
    project_path = tmp_path / "uid_1" / "projects" / "demo"
    project_path.mkdir(parents=True)
    (project_path / "世界观.txt").write_text("星城有一座会记忆梦境的塔。", encoding="utf-8")

    chunks = [
        SemanticChunk(
            text="星城 梦境 塔",
            metadata={"format_key": "txt"},
            start_line=1,
            end_line=1,
            narrative_ref="世界观",
        )
    ]
    chunk_state = {
        "chunks_by_file": {"世界观.txt": chunks},
        "chunks": chunks,
        "file_hashes": {"世界观.txt": "hash1"},
    }

    class _FakeChunker:
        def chunk_project_state(self, *_args, **_kwargs):
            return chunk_state

    monkeypatch.setattr("agents.vector_index.service.get_project_path", lambda *_args: str(project_path))
    monkeypatch.setattr("agents.vector_index.service.SemanticChunker", _FakeChunker)
    monkeypatch.setattr(VectorIndexService, "_get_embeddings", lambda _self: _FakeEmbeddings())

    service = VectorIndexService("1", "demo")
    metadata = service.build_index(force_rebuild=True)
    hits = service.query("梦境 塔", k=3, filter={"format_key": "txt"})

    assert metadata["chunk_count"] == 1
    assert service.get_status()["backend"] == "lancedb"
    assert [(hit.rel_path, hit.format_key, hit.match_text) for hit in hits] == [
        ("世界观.txt", "txt", "星城 梦境 塔")
    ]
    assert metadata["embedding"] == embedding_contract_metadata()
    assert Path(service.get_status()["persist_dir"]).name == ".vector_index_lancedb"
    assert service.reset()["removed"] is True


def test_vector_index_embedding_contract_and_query_prefix():
    assert QWEN3_EMBEDDING_DIMENSIONS == 1024
    assert embedding_contract_metadata()["metric"] == "cosine"
    assert build_query_text("女主角哭泣") == "为这个句子生成表示以用于检索相关文章：女主角哭泣"

    stale_metadata = {
        "file_hashes": {"a.txt": "hash"},
        "file_doc_ids": {"a.txt": ["chunk_1"]},
        "embedding": {**embedding_contract_metadata(), "dimensions": 768},
    }
    assert VectorIndexService._is_embedding_contract_compatible(stale_metadata) is False


def test_vector_index_normalizes_vectors():
    normalized = VectorIndexService._normalize_vector([3.0, 4.0])
    assert normalized == [0.6, 0.8]
    assert VectorIndexService._normalize_vector([0.0, 0.0]) == [0.0, 0.0]


def test_vector_index_prefers_local_embedding_when_enabled(monkeypatch):
    created = {}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr("agents.vector_index.service.OpenAIEmbeddings", FakeOpenAIEmbeddings)
    monkeypatch.setattr("core.system_settings.get_local_embedding_enabled", lambda: True)
    monkeypatch.setattr("agents.vector_index.local_embedding.is_local_embedding_alive", lambda timeout=1.0: True)
    monkeypatch.setattr("agents.vector_index.local_embedding.LOCAL_EMBEDDING_BASE_URL", "http://127.0.0.1:18080/v1")
    monkeypatch.setattr("agents.vector_index.local_embedding.LOCAL_EMBEDDING_API_KEY", "local-key")

    service = VectorIndexService("1", "demo")
    service._get_embeddings()

    assert created["base_url"] == "http://127.0.0.1:18080/v1"
    assert created["api_key"] == "local-key"
    assert created["extra_body"]["dimensions"] == 1024


def test_local_embedding_command_is_cross_platform_and_waits_until_alive(tmp_path, monkeypatch):
    from agents.vector_index import local_embedding

    model_path = tmp_path / "Qwen3-Embedding-0.6B-Q8_0.gguf"
    model_path.write_bytes(b"0" * local_embedding.QWEN3_GGUF_MIN_BYTES)
    runtime_dir = tmp_path / "llama.cpp"
    server_exe = runtime_dir / "cached" / ("llama-server.exe" if local_embedding.os.name == "nt" else "llama-server")
    server_exe.parent.mkdir(parents=True)
    server_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(local_embedding, "LOCAL_EMBEDDING_MODEL_PATH", str(model_path))
    monkeypatch.setattr(local_embedding, "LOCAL_EMBEDDING_SERVER_EXE", "llama-server")
    monkeypatch.setattr(local_embedding, "LOCAL_EMBEDDING_STARTUP_TIMEOUT", 2.0)
    monkeypatch.setattr(local_embedding, "_process", None)
    monkeypatch.setattr(local_embedding, "_alive_cache", (0.0, False))
    monkeypatch.setattr(local_embedding, "get_llama_cpp_runtime_dir", lambda: runtime_dir)
    monkeypatch.setattr(local_embedding.shutil, "which", lambda _name: None)

    command = local_embedding.build_local_embedding_command()
    assert command[0] == str(server_exe)
    assert "--embedding" in command
    assert command[command.index("--pooling") + 1] == "last"
    assert command[command.index("--ctx-size") + 1] == "32768"

    class FakeProcess:
        pid = 123

        def poll(self):
            return None

    alive_calls = {"count": 0}

    def fake_alive(*_args, **_kwargs):
        alive_calls["count"] += 1
        return alive_calls["count"] >= 2

    monkeypatch.setattr(local_embedding.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    monkeypatch.setattr(local_embedding, "is_local_embedding_alive", fake_alive)

    status = local_embedding.start_local_embedding_service()

    assert status["running"] is True
    assert status["alive"] is True
    assert alive_calls["count"] >= 2
