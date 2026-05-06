"""聊天附件引用制纯函数测试

覆盖 ``server/agents/routes/chat_attachment.py`` 的四个对外纯函数：

- extract_imported_file_meta
- build_imported_file_context_label
- build_user_message_metadata
- expand_active_context_with_attachment（含 partial 分片说明 + 工具调用提示）
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.routes.chat_attachment import (
    build_imported_file_context_label,
    build_user_message_metadata,
    expand_active_context_with_attachment,
    extract_imported_file_meta,
)


# ==================== 纯函数：extract_imported_file_meta ====================


def test_extract_imported_file_meta_returns_none_when_active_meta_missing():
    assert extract_imported_file_meta(None) is None
    assert extract_imported_file_meta({}) is None


def test_extract_imported_file_meta_requires_attachment_id_and_filename():
    assert extract_imported_file_meta({'importedFile': {}}) is None
    assert extract_imported_file_meta({'importedFile': {'attachmentId': 'a1'}}) is None
    assert extract_imported_file_meta({'importedFile': {'filename': 'a.txt'}}) is None


def test_extract_imported_file_meta_normalizes_full_payload():
    result = extract_imported_file_meta({
        'importedFile': {
            'attachmentId': 'abc123',
            'filename': '原作.epub',
            'sourceFormat': 'epub',
            'totalTokens': 12345,
            'chunkTokens': 60000,
            'isPartial': True,
            'warnings': [
                {'code': 'too_large', 'message': '文件过大已分片'},
                {'code': '', 'message': ''},  # 应被过滤
                'invalid string',  # 非 dict 应被过滤
            ],
            'uploadedAt': 1700000000,
        },
    })
    assert result == {
        'attachmentId': 'abc123',
        'filename': '原作.epub',
        'sourceFormat': 'epub',
        'totalTokens': 12345,
        'chunkTokens': 60000,
        'isPartial': True,
        'warnings': [{'code': 'too_large', 'message': '文件过大已分片'}],
        'uploadedAt': 1700000000,
    }


def test_extract_imported_file_meta_accepts_snake_case_attachment_id():
    """前端使用 attachmentId，少数旧调用方使用 attachment_id。"""
    result = extract_imported_file_meta({
        'importedFile': {'attachment_id': 'abc', 'filename': 'a.txt'},
    })
    assert result is not None
    assert result['attachmentId'] == 'abc'


# ==================== 纯函数：build_imported_file_context_label ====================


def test_build_imported_file_context_label_partial_vs_full():
    assert build_imported_file_context_label(None) == ''
    assert build_imported_file_context_label({'filename': ''}) == ''
    assert build_imported_file_context_label({'filename': '原作.epub', 'isPartial': False}) == '【已上传文件：原作.epub】'
    assert build_imported_file_context_label({'filename': '原作.epub', 'isPartial': True}) == '【已上传文件首个分片：原作.epub】'


# ==================== 纯函数：build_user_message_metadata ====================


def test_build_user_message_metadata_strips_active_context_and_includes_imported_file():
    metadata = build_user_message_metadata(
        channel='global',
        active_context='   带空格的上下文  ',
        imported_file_meta={'attachmentId': 'a', 'filename': 'a.txt'},
    )
    assert metadata['channel'] == 'global'
    assert metadata['active_context'] == '带空格的上下文'
    assert metadata['importedFile'] == {'attachmentId': 'a', 'filename': 'a.txt'}


def test_build_user_message_metadata_omits_empty_active_context():
    metadata = build_user_message_metadata(
        channel='extra',
        active_context='   ',
        imported_file_meta=None,
    )
    assert metadata == {'channel': 'extra'}


# ==================== expand_active_context_with_attachment：基础边界 ====================


def test_expand_returns_base_when_no_imported_file_meta():
    assert expand_active_context_with_attachment('u', 'p', '原文', None) == '原文'
    assert expand_active_context_with_attachment('u', 'p', '原文', 'not a dict') == '原文'  # type: ignore[arg-type]


def test_expand_returns_base_when_deleted_flag_set():
    meta = {'attachmentId': 'a', 'filename': 'a.txt', 'deleted': True}
    assert expand_active_context_with_attachment('u', 'p', '原文', meta) == '原文'


def test_expand_returns_base_when_attachment_id_missing():
    meta = {'attachmentId': '', 'filename': 'a.txt'}
    assert expand_active_context_with_attachment('u', 'p', '原文', meta) == '原文'


def test_expand_returns_base_when_project_name_missing():
    meta = {'attachmentId': 'a', 'filename': 'a.txt'}
    assert expand_active_context_with_attachment('u', '', '原文', meta) == '原文'


# ==================== expand_active_context_with_attachment：磁盘 fixture ====================


@pytest.fixture
def attachment_storage(tmp_path, monkeypatch):
    """把附件目录隔离到 tmp_path 下，保证磁盘干净。"""
    project_path = tmp_path / 'projects' / 'demo'
    project_path.mkdir(parents=True, exist_ok=True)

    def _fake_get_project_path(user_id: str, project_name: str) -> str:  # noqa: ARG001
        return str(project_path)

    # storage.py 在模块层 import 了 get_project_path，monkeypatch 模块属性
    monkeypatch.setattr(
        'agents.attachment.storage.get_project_path', _fake_get_project_path
    )
    return project_path


def _save_test_attachment(
    user_id: str,
    project_name: str,
    *,
    full_text: str,
    chunks: list[str],
    filename: str = 'novel.txt',
):
    from agents.attachment import save_attachment

    return save_attachment(
        user_id=user_id,
        project_name=project_name,
        filename=filename,
        source_format='txt',
        full_text=full_text,
        chunks=chunks,
        total_tokens=sum(len(c) for c in chunks),
    )


# ==================== expand：partial 分片说明（核心新增覆盖） ====================


def test_expand_partial_injects_chunk_count_and_tool_hint(attachment_storage):
    """partial=True 且 chunk_count > 1 时，必须注入分片说明 + 工具调用提示。"""
    meta = _save_test_attachment(
        'user1',
        'demo',
        full_text='第一段第二段第三段',
        chunks=['第一段', '第二段', '第三段'],
    )
    imported_file_meta = {
        'attachmentId': meta.attachment_id,
        'filename': 'novel.txt',
        'isPartial': True,
    }

    result = expand_active_context_with_attachment(
        'user1', 'demo', '前置上下文', imported_file_meta,
    )

    # 首片正文必须出现
    assert '第一段' in result
    # 后续分片不应被直接附带
    assert '第二段' not in result
    assert '第三段' not in result
    # 分片说明文本必须出现，且包含具体数字
    assert '第 1 部分' in result
    assert '共 3 部分' in result
    assert '剩余 2 部分' in result
    # 工具调用提示必须明确出现工具名 + 参数说明
    assert 'read_attachment_chunk' in result
    assert meta.attachment_id in result
    assert 'chunk_index' in result
    # 标签仍然存在
    assert '【已上传文件首个分片：novel.txt】' in result


def test_expand_partial_with_single_chunk_does_not_inject_split_hint(attachment_storage):
    """partial=True 但 chunk_count=1（实际不应该出现，但要鲁棒）→ 不注入分片说明。"""
    meta = _save_test_attachment(
        'user1', 'demo',
        full_text='短文本',
        chunks=['短文本'],
    )
    imported_file_meta = {
        'attachmentId': meta.attachment_id,
        'filename': 'short.txt',
        'isPartial': True,
    }

    result = expand_active_context_with_attachment(
        'user1', 'demo', '', imported_file_meta,
    )

    assert '短文本' in result
    # 单片场景：分片说明文案不应出现
    assert '分片说明' not in result
    assert 'read_attachment_chunk' not in result


def test_expand_full_mode_injects_full_text_without_split_hint(attachment_storage):
    """isPartial=False → 注入 full_text，无分片说明。"""
    meta = _save_test_attachment(
        'user1', 'demo',
        full_text='第一段第二段第三段',
        chunks=['第一段', '第二段', '第三段'],
    )
    imported_file_meta = {
        'attachmentId': meta.attachment_id,
        'filename': 'novel.txt',
        'isPartial': False,
    }

    result = expand_active_context_with_attachment(
        'user1', 'demo', '', imported_file_meta,
    )

    assert '第一段第二段第三段' in result
    # 完整模式：分片说明文案不应出现
    assert '分片说明' not in result
    assert 'read_attachment_chunk' not in result
    # 标签也不是 partial 版本
    assert '【已上传文件：novel.txt】' in result
    assert '首个分片' not in result


def test_expand_returns_placeholder_when_attachment_cache_missing(attachment_storage):
    """attachmentId 在 meta 中但磁盘缓存已被清除 → 注入失效占位，不抛。"""
    imported_file_meta = {
        'attachmentId': 'nonexistent_id',
        'filename': '已失效.txt',
        'isPartial': True,
    }

    result = expand_active_context_with_attachment(
        'user1', 'demo', '原文', imported_file_meta,
    )

    assert '原文' in result
    assert '缓存已失效' in result
    assert '已失效.txt' in result


def test_expand_appends_to_existing_active_context(attachment_storage):
    """已有 active_context 时，附件块用 \\n\\n 分隔追加，而不是覆盖。"""
    meta = _save_test_attachment(
        'user1', 'demo',
        full_text='正文',
        chunks=['正文'],
    )
    imported_file_meta = {
        'attachmentId': meta.attachment_id,
        'filename': 'a.txt',
        'isPartial': False,
    }

    result = expand_active_context_with_attachment(
        'user1', 'demo', '已有上下文', imported_file_meta,
    )

    assert result.startswith('已有上下文')
    assert '\n\n' in result
    assert '正文' in result
