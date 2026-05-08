"""聊天附件引用制纯函数测试

覆盖 ``server/agents/routes/chat_attachment.py`` 的对外纯函数：

- extract_imported_file_meta / extract_imported_files_meta
- build_imported_file_context_label
- build_user_message_metadata（单数 + 多数双写）
- expand_active_context_with_attachment（单附件：partial 分片说明 + 工具调用提示）
- expand_active_context_with_attachments（多附件：仅注入清单 + 工具提示）
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
    expand_active_context_with_attachments,
    extract_imported_file_meta,
    extract_imported_files_meta,
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


# ==================== 多附件：extract_imported_files_meta ====================


def test_extract_imported_files_meta_returns_empty_for_missing():
    assert extract_imported_files_meta(None) == []
    assert extract_imported_files_meta({}) == []


def test_extract_imported_files_meta_falls_back_to_legacy_single_field():
    """activeMeta.importedFile（旧字段）→ 自动转为 [importedFile]。"""
    metas = extract_imported_files_meta({
        'importedFile': {'attachmentId': 'a', 'filename': 'a.txt'},
    })
    assert len(metas) == 1
    assert metas[0]['attachmentId'] == 'a'


def test_extract_imported_files_meta_handles_list_with_dedupe_and_invalid():
    """importedFiles 列表 → 校验 / 去重 / 保留顺序。"""
    metas = extract_imported_files_meta({
        'importedFiles': [
            {'attachmentId': 'a', 'filename': 'a.txt'},
            {'attachmentId': 'b', 'filename': 'b.txt'},
            {'attachmentId': 'a', 'filename': 'a.txt'},  # 重复 id 应去重
            {'attachmentId': '', 'filename': 'invalid.txt'},  # 缺失 id 应丢弃
            'not a dict',  # 非 dict 应丢弃
        ],
    })
    assert [m['attachmentId'] for m in metas] == ['a', 'b']


def test_extract_imported_file_meta_legacy_returns_first():
    """老接口（单数）应返回多附件列表的第一个。"""
    result = extract_imported_file_meta({
        'importedFiles': [
            {'attachmentId': 'a', 'filename': 'a.txt'},
            {'attachmentId': 'b', 'filename': 'b.txt'},
        ],
    })
    assert result is not None
    assert result['attachmentId'] == 'a'


# ==================== 多附件：build_user_message_metadata ====================


def test_build_user_message_metadata_supports_list_payload():
    """多附件入参时同时写 importedFiles 列表 + importedFile 单数（向后兼容）。"""
    metadata = build_user_message_metadata(
        channel='global',
        active_context='ctx',
        imported_file_meta=[
            {'attachmentId': 'a', 'filename': 'a.txt'},
            {'attachmentId': 'b', 'filename': 'b.txt'},
        ],
    )
    assert metadata['active_context'] == 'ctx'
    assert metadata['importedFiles'] == [
        {'attachmentId': 'a', 'filename': 'a.txt'},
        {'attachmentId': 'b', 'filename': 'b.txt'},
    ]
    # 老 reader 仍能拿到首个
    assert metadata['importedFile'] == {'attachmentId': 'a', 'filename': 'a.txt'}


def test_build_user_message_metadata_dict_payload_still_writes_list():
    """单 dict 入参也会落到 importedFiles[0]，保证 reader 路径统一。"""
    metadata = build_user_message_metadata(
        channel='c',
        active_context='',
        imported_file_meta={'attachmentId': 'x', 'filename': 'x.txt'},
    )
    assert metadata['importedFiles'] == [{'attachmentId': 'x', 'filename': 'x.txt'}]
    assert metadata['importedFile'] == {'attachmentId': 'x', 'filename': 'x.txt'}


# ==================== 多附件：expand_active_context_with_attachments ====================


def test_expand_attachments_single_uses_single_attachment_branch(attachment_storage):
    """1 附件场景：行为应与单附件 expand 完全一致（partial=False 灌全文）。"""
    meta = _save_test_attachment(
        'user1', 'demo', full_text='完整正文', chunks=['完整正文'],
    )
    files = [{
        'attachmentId': meta.attachment_id,
        'filename': 'novel.txt',
        'isPartial': False,
    }]
    result = expand_active_context_with_attachments('user1', 'demo', '', files)
    assert '完整正文' in result
    assert '【已上传文件：novel.txt】' in result
    # 多附件清单文案不应出现
    assert '【已上传 1 个附件】' not in result


def test_expand_attachments_multi_only_emits_manifest_no_full_text(attachment_storage):
    """≥ 2 附件场景：只注入文件清单 + 工具提示，绝不预注入任何附件正文。"""
    meta_a = _save_test_attachment(
        'user1', 'demo', full_text='AAA1AAA2AAA3',
        chunks=['AAA1', 'AAA2', 'AAA3'], filename='A.txt',
    )
    meta_b = _save_test_attachment(
        'user1', 'demo', full_text='BBB1BBB2',
        chunks=['BBB1', 'BBB2'], filename='B.txt',
    )
    files = [
        {'attachmentId': meta_a.attachment_id, 'filename': 'A.txt', 'isPartial': True},
        {'attachmentId': meta_b.attachment_id, 'filename': 'B.txt', 'isPartial': False},
    ]
    result = expand_active_context_with_attachments('user1', 'demo', '前置', files)

    # 每个附件文件名 + chunk 数都应出现在清单
    assert '【已上传 2 个附件】' in result
    assert 'A.txt' in result
    assert 'B.txt' in result
    assert '共 3 个分片' in result
    assert '共 2 个分片' in result
    # 工具调用提示出现
    assert 'read_attachment_chunk' in result
    # 关键：任何附件正文都不应被预注入
    assert 'AAA1' not in result
    assert 'AAA2' not in result
    assert 'AAA3' not in result
    assert 'BBB1' not in result
    assert 'BBB2' not in result
    # 前置 active_context 仍保留并通过 \n\n 分隔
    assert result.startswith('前置')


def test_expand_attachments_multi_marks_cache_missing_in_manifest(attachment_storage):
    """多附件清单中混合"缓存已失效"项应明示标记，不影响其余项。"""
    meta_a = _save_test_attachment(
        'user1', 'demo', full_text='ok', chunks=['ok'], filename='A.txt',
    )
    files = [
        {'attachmentId': meta_a.attachment_id, 'filename': 'A.txt'},
        {'attachmentId': 'gone_id', 'filename': 'B.txt'},
    ]
    result = expand_active_context_with_attachments('user1', 'demo', '', files)

    assert 'A.txt' in result
    assert 'B.txt' in result
    assert '缓存已失效' in result
    # 提醒用户重新上传的引导出现
    assert '重新上传' in result


def test_expand_attachments_filters_deleted_entries(attachment_storage):
    """deleted=True 的附件不应进入清单/正文。"""
    meta_a = _save_test_attachment(
        'user1', 'demo', full_text='活跃', chunks=['活跃'], filename='Live.txt',
    )
    meta_b = _save_test_attachment(
        'user1', 'demo', full_text='已删', chunks=['已删'], filename='Del.txt',
    )
    files = [
        {'attachmentId': meta_a.attachment_id, 'filename': 'Live.txt', 'isPartial': False},
        {'attachmentId': meta_b.attachment_id, 'filename': 'Del.txt', 'isPartial': False, 'deleted': True},
    ]
    result = expand_active_context_with_attachments('user1', 'demo', '', files)
    # 只剩 1 个有效附件 → 走单附件分支注入全文
    assert '活跃' in result
    # 已删除项的正文 / 文件名都不应出现
    assert '已删' not in result
    assert 'Del.txt' not in result


def test_expand_attachments_returns_base_when_all_deleted(attachment_storage):
    """全部 deleted → 返回 base，不注入任何块。"""
    meta = _save_test_attachment(
        'user1', 'demo', full_text='X', chunks=['X'], filename='X.txt',
    )
    files = [
        {'attachmentId': meta.attachment_id, 'filename': 'X.txt', 'deleted': True},
    ]
    result = expand_active_context_with_attachments('user1', 'demo', 'BASE', files)
    assert result == 'BASE'


def test_expand_legacy_wrapper_routes_list_to_multi_branch(attachment_storage):
    """老入口接到 list → 自动走多附件分支，不再当作 dict。"""
    meta_a = _save_test_attachment(
        'user1', 'demo', full_text='aa', chunks=['aa'], filename='A.txt',
    )
    meta_b = _save_test_attachment(
        'user1', 'demo', full_text='bb', chunks=['bb'], filename='B.txt',
    )
    files = [
        {'attachmentId': meta_a.attachment_id, 'filename': 'A.txt'},
        {'attachmentId': meta_b.attachment_id, 'filename': 'B.txt'},
    ]
    result = expand_active_context_with_attachment('u', 'demo', '', files)  # type: ignore[arg-type]
    assert '【已上传 2 个附件】' in result
    # 多附件分支：正文不预注入
    assert 'aa' not in result
    assert 'bb' not in result
