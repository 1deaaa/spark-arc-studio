"""附件接入向量索引的单元测试

覆盖：
1. ``VectorIndexService._collect_attachment_chunks`` 正确扫描 .attachments
   并把每个 chunk 转成 SemanticChunk（source_type=attachment 等）
2. semantic_search 工具输出文本对附件源的标注（[附件] vs [项目]）
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


# ==================== fixture：磁盘隔离 ====================


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    """为附件存储 + vector_index 提供干净的项目目录。"""
    project_path = tmp_path / 'projects' / 'demo'
    project_path.mkdir(parents=True, exist_ok=True)

    def _fake_get_project_path(user_id: str, project_name: str) -> str:  # noqa: ARG001
        return str(project_path)

    monkeypatch.setattr(
        'agents.attachment.storage.get_project_path', _fake_get_project_path
    )
    monkeypatch.setattr(
        'agents.vector_index.service.get_project_path', _fake_get_project_path
    )

    return project_path


def _save_test_attachment(filename: str, full_text: str, chunks: list[str]):
    from agents.attachment import save_attachment

    return save_attachment(
        user_id='user1',
        project_name='demo',
        filename=filename,
        source_format='txt',
        full_text=full_text,
        chunks=chunks,
        total_tokens=sum(len(c) for c in chunks),
    )


# ==================== _collect_attachment_chunks 单元测试 ====================


def test_collect_attachment_chunks_emits_semantic_chunks_with_source_type(isolated_project):
    """每个分片应当生成一个 SemanticChunk，metadata 含 source_type=attachment。"""
    from agents.vector_index.service import VectorIndexService

    meta = _save_test_attachment(
        'novel.epub',
        full_text='AAA' + 'BBB' + 'CCC',
        chunks=['AAA part one', 'BBB part two', 'CCC part three'],
    )

    service = VectorIndexService('user1', 'demo')
    chunks_by_file, file_hashes = service._collect_attachment_chunks()

    rel_path = f'.attachments/{meta.attachment_id}/full.txt'
    assert rel_path in chunks_by_file
    assert rel_path in file_hashes
    assert file_hashes[rel_path] == meta.attachment_id

    chunks = chunks_by_file[rel_path]
    assert len(chunks) == 3

    for idx, chunk in enumerate(chunks):
        assert chunk.metadata['source_type'] == 'attachment'
        assert chunk.metadata['format_key'] == 'attachment'
        assert chunk.metadata['attachment_id'] == meta.attachment_id
        assert chunk.metadata['attachment_filename'] == 'novel.epub'
        assert chunk.metadata['attachment_chunk_index'] == idx
        assert chunk.metadata['source'] == rel_path
        assert chunk.narrative_ref == f'附件 > novel.epub > 第 {idx + 1} 部分（共 3）'

    # 第一片的 text 应该出现且不窜片
    assert chunks[0].text == 'AAA part one'
    assert chunks[1].text == 'BBB part two'
    assert chunks[2].text == 'CCC part three'


def test_collect_attachment_chunks_returns_empty_when_no_attachments_dir(isolated_project):
    """没有任何附件时返回空。"""
    from agents.vector_index.service import VectorIndexService

    service = VectorIndexService('user1', 'demo')
    chunks_by_file, file_hashes = service._collect_attachment_chunks()

    assert chunks_by_file == {}
    assert file_hashes == {}


def test_collect_attachment_chunks_skips_attachments_with_empty_chunks(isolated_project):
    """全空附件被跳过，不产生 SemanticChunk。"""
    from agents.attachment import save_attachment
    from agents.vector_index.service import VectorIndexService

    save_attachment(
        user_id='user1',
        project_name='demo',
        filename='empty.txt',
        source_format='txt',
        full_text='',
        chunks=['   ', '\n\n'],  # 全空白
        total_tokens=0,
    )

    service = VectorIndexService('user1', 'demo')
    chunks_by_file, _ = service._collect_attachment_chunks()
    assert chunks_by_file == {}


def test_collect_attachment_chunks_handles_multiple_attachments(isolated_project):
    """两个不同附件应生成两个独立的 rel_path。"""
    from agents.vector_index.service import VectorIndexService

    meta1 = _save_test_attachment('a.txt', 'A', ['A'])
    meta2 = _save_test_attachment('b.txt', 'B', ['B'])

    service = VectorIndexService('user1', 'demo')
    chunks_by_file, file_hashes = service._collect_attachment_chunks()

    rel1 = f'.attachments/{meta1.attachment_id}/full.txt'
    rel2 = f'.attachments/{meta2.attachment_id}/full.txt'

    assert {rel1, rel2}.issubset(chunks_by_file.keys())
    assert file_hashes[rel1] == meta1.attachment_id
    assert file_hashes[rel2] == meta2.attachment_id


# ==================== semantic_search 输出文本 source 标注测试 ====================


@pytest.fixture
def mock_search_context(monkeypatch):
    """覆盖 semantic_search 工具内部的上下文 + service.query。"""
    from agents.tools import search as search_module
    from agents.vector_index.service import SearchHit

    monkeypatch.setattr(search_module, 'current_user_id', SimpleNamespace(get=lambda: 'user1'))
    monkeypatch.setattr(search_module, 'get_current_project_name', lambda: 'demo')
    # is_semantic_search_enabled 是 lazy import，需 monkeypatch 源模块
    monkeypatch.setattr('core.project_settings.is_semantic_search_enabled', lambda u, p: True)
    # mock matchbox 以避开嵌入模型初始化检查
    fake_embedding_box = SimpleNamespace(get_user_embedding=lambda user_id: object())
    monkeypatch.setattr('llm.agen_matchbox.matchbox', lambda: fake_embedding_box)

    return search_module, SearchHit


def test_semantic_search_output_distinguishes_project_and_attachment(mock_search_context, monkeypatch):
    """semantic_search 输出文本必须用 [项目] / [附件] 标签明确区分两类来源。"""
    search_module, SearchHit = mock_search_context

    project_hit = SearchHit(
        index=0,
        file_path='/tmp/projects/demo/大纲.txt',
        rel_path='大纲.txt',
        format_key='outline',
        start_line=12,
        end_line=15,
        narrative_ref='大纲 > 第1章 相遇',
        match_text='主角在火种城遇见了反派。',
        score=0.85,
        source_type='project',
    )
    attachment_hit = SearchHit(
        index=1,
        file_path='/tmp/projects/demo/.attachments/abc/full.txt',
        rel_path='.attachments/abc/full.txt',
        format_key='attachment',
        start_line=0,
        end_line=0,
        narrative_ref='附件 > 原作.epub > 第 2 部分（共 3）',
        match_text='附件文本片段',
        score=0.78,
        source_type='attachment',
        attachment_id='abc',
        attachment_filename='原作.epub',
        attachment_chunk_index=1,
    )

    class _StubService:
        def __init__(self, *args, **kwargs):
            pass

        def get_status(self, check_freshness=True):  # noqa: ARG002
            return {'needs_rebuild': False, 'build_state': {'status': 'ready'}}

        def start_background_build(self, force_rebuild=False):  # noqa: ARG002
            return {}

        def query(self, query_text, k=8, filter=None, score_threshold=0.0):  # noqa: ARG002
            return [project_hit, attachment_hit]

    # VectorIndexService 是从 agents.vector_index 包导出的，search.py 用 ``from agents.vector_index import VectorIndexService``
    # 所以 monkeypatch 包上的名字才会生效
    monkeypatch.setattr('agents.vector_index.VectorIndexService', _StubService)

    result = search_module.semantic_search.invoke({'query': '相遇', 'k': 5})

    assert isinstance(result, str)
    assert '[项目]' in result
    assert '[附件]' in result
    assert '大纲 > 第1章 相遇' in result
    assert '附件 > 原作.epub > 第 2 部分' in result
    # 附件命中应附带工具调用提示
    assert 'read_attachment_chunk(attachment_id="abc", chunk_index=1)' in result
    # 项目命中不带工具调用提示
    project_section_end = result.index('附件 > 原作.epub')
    project_section = result[:project_section_end]
    assert 'read_attachment_chunk' not in project_section


def test_semantic_search_attachment_only_still_marks_as_attachment(mock_search_context, monkeypatch):
    """只有附件命中时也应正确标注。"""
    search_module, SearchHit = mock_search_context

    only_hit = SearchHit(
        index=0,
        file_path='',
        rel_path='.attachments/xyz/full.txt',
        format_key='attachment',
        start_line=0,
        end_line=0,
        narrative_ref='附件 > test.epub > 第 1 部分（共 1）',
        match_text='只有附件',
        score=0.91,
        source_type='attachment',
        attachment_id='xyz',
        attachment_filename='test.epub',
        attachment_chunk_index=0,
    )

    class _StubService:
        def __init__(self, *args, **kwargs):
            pass

        def get_status(self, check_freshness=True):  # noqa: ARG002
            return {'needs_rebuild': False, 'build_state': {'status': 'ready'}}

        def start_background_build(self, force_rebuild=False):  # noqa: ARG002
            return {}

        def query(self, query_text, k=8, filter=None, score_threshold=0.0):  # noqa: ARG002
            return [only_hit]

    monkeypatch.setattr('agents.vector_index.VectorIndexService', _StubService)

    result = search_module.semantic_search.invoke({'query': '关键词', 'k': 5})
    assert '[附件]' in result
    assert '[项目]' not in result
    assert 'chunk_index=0' in result
