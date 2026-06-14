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
    assert Path(service.get_status()["persist_dir"]).name == ".vector_index_lancedb"
    assert service.reset()["removed"] is True
