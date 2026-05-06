"""read_attachment_chunk 工具单元测试

覆盖工具的"按需滑窗读取附件分片"行为：

- 命中分片 → 返回 header + 正文 + footer，footer 包含明确的下一步指引
- 最后一个分片 → footer 切换为"已完整读取"
- chunk_index 越界 → 返回错误说明，不抛
- 缓存缺失 → 返回错误说明，不抛
- attachment_id 为空 → 返回错误说明
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.tools.attachment import read_attachment_chunk


# ==================== fixture：磁盘隔离 + ToolExecutionContext mock ====================


@pytest.fixture
def isolated_attachment(tmp_path, monkeypatch):
    """把附件目录隔离到 tmp_path 下 + 模拟 ToolExecutionContext。"""
    project_path = tmp_path / 'projects' / 'demo'
    project_path.mkdir(parents=True, exist_ok=True)

    def _fake_get_project_path(user_id: str, project_name: str) -> str:  # noqa: ARG001
        return str(project_path)

    monkeypatch.setattr(
        'agents.attachment.storage.get_project_path', _fake_get_project_path
    )

    # ToolExecutionContext.get_context() 使用 contextvars，测试里用 monkeypatch 替换
    monkeypatch.setattr(
        'agents.tools.attachment.ToolExecutionContext.get_context',
        lambda: ('user1', 'demo'),
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


# ==================== 命中分片 ====================


def test_read_attachment_chunk_returns_header_body_and_next_step_hint(isolated_attachment):
    """读取非末尾分片：必须包含正文 + 下一步指引（带具体 chunk_index）。"""
    meta = _save_test_attachment(
        'novel.txt',
        full_text='AAA' + 'BBB' + 'CCC',
        chunks=['AAA', 'BBB', 'CCC'],
    )

    result = read_attachment_chunk.invoke({
        'attachment_id': meta.attachment_id,
        'chunk_index': 1,
    })

    assert isinstance(result, str)
    # 头部包含分片元信息
    assert '第 2 部分' in result
    assert '共 3 部分' in result
    assert 'novel.txt' in result
    # 正文出现
    assert 'BBB' in result
    # 不应混入其他分片正文
    assert 'AAA' not in result
    assert 'CCC' not in result
    # 末尾说明：明确指引下一步 chunk_index=2
    assert '剩余' in result
    assert 'chunk_index=2' in result
    assert meta.attachment_id in result


def test_read_attachment_chunk_last_chunk_marks_complete(isolated_attachment):
    """读取最后一个分片：footer 切换为已完整读取。"""
    meta = _save_test_attachment(
        'novel.txt',
        full_text='AAA' + 'BBB',
        chunks=['AAA', 'BBB'],
    )

    result = read_attachment_chunk.invoke({
        'attachment_id': meta.attachment_id,
        'chunk_index': 1,
    })

    assert 'BBB' in result
    assert '第 2 部分' in result
    assert '已完整读取' in result
    # 末尾分片不应再给出"下一步指引"
    assert 'chunk_index=2' not in result


def test_read_attachment_chunk_first_chunk_index_zero(isolated_attachment):
    """读取首个分片（chunk_index=0）也必须正常工作。"""
    meta = _save_test_attachment(
        'novel.txt',
        full_text='AAA' + 'BBB',
        chunks=['AAA', 'BBB'],
    )

    result = read_attachment_chunk.invoke({
        'attachment_id': meta.attachment_id,
        'chunk_index': 0,
    })

    assert 'AAA' in result
    assert '第 1 部分' in result
    assert '剩余 1 部分' in result
    assert 'chunk_index=1' in result


# ==================== 错误路径 ====================


def test_read_attachment_chunk_returns_error_when_index_out_of_range(isolated_attachment):
    """chunk_index 越界 → 错误说明，不抛。"""
    meta = _save_test_attachment(
        'novel.txt',
        full_text='AAA',
        chunks=['AAA'],
    )

    result = read_attachment_chunk.invoke({
        'attachment_id': meta.attachment_id,
        'chunk_index': 5,
    })

    assert '[读取失败]' in result
    assert '超出范围' in result
    assert 'novel.txt' in result


def test_read_attachment_chunk_returns_error_when_attachment_missing(isolated_attachment):
    """缓存不存在 → 错误说明。"""
    result = read_attachment_chunk.invoke({
        'attachment_id': 'nonexistent_attachment_id',
        'chunk_index': 0,
    })

    assert '[读取失败]' in result
    assert 'nonexistent_attachment_id' in result


def test_read_attachment_chunk_returns_error_when_attachment_id_empty(isolated_attachment):
    """attachment_id 为空 → 错误说明。"""
    # pydantic 会校验空字符串吗？我们的 schema 没设 min_length，所以空串能通过
    result = read_attachment_chunk.invoke({
        'attachment_id': '',
        'chunk_index': 0,
    })

    assert '[读取失败]' in result
    assert 'attachment_id' in result
