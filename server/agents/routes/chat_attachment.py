"""
聊天附件引用制：active_context / metadata 的纯函数集
====================================================

把附件全文从 DB 与请求体里完全剥离：
- 上传时由 ``server/core/routes_import.py`` 落盘到
  ``{project}/.attachments/{attachment_id}/`` 并返回 attachment_id；
- 前端 chatStore 把 attachmentId 写进 ``activeMeta.importedFiles`` 列表，
  请求体与 DB 都不存全文；
- 本模块的 ``expand_active_context_with_attachments`` 在调用 LLM 前按
  attachmentId 从磁盘动态注入正文，缓存缺失时注入失效占位。

多附件统一策略
-------------
- 0 附件：原样返回 active_context。
- 1 附件：注入正文（partial=True 灌首片+分片说明，partial=False 灌全文），
  保留单附件场景下的轻量交互。
- ≥ 2 附件：仅注入「文件清单 + 引导提示」让 LLM 用滑窗工具
  按需读取，避免每个附件都堆叠一份首片导致 token 爆炸；
  滑窗底座（``agents.longread``）保证旧窗口折叠为“线索 + 回跳指针”，
  本轮新读窗口原文完整保留。
- 超窗附件（``isOversized=True``，全文超过上传时模型窗口）：
  单附件也不预注入首片，直接走清单分支，只能滑窗按需读取。
  超窗附件照常切分落盘，不再拒绝上传。

为什么单独成模块？
- 让 chat.py 路由层维持瘦身，避免"全文注入"、"DB 写入"、"占位生成"散开；
- 让单元测试不依赖 FastAPI / langchain 这些重度路由依赖，直接覆盖纯函数。
"""

from __future__ import annotations

from typing import Any, Dict, List


# ==================== 元信息抽取 / 标签 ====================

def _normalize_attachment_meta(attachment_meta: Any) -> Dict[str, Any] | None:
    """把单条附件元信息归一化为内部规范结构。

    必须同时携带 ``attachmentId`` 与 ``filename``，缺一返回 None。
    """
    if not isinstance(attachment_meta, dict):
        return None
    filename = str(attachment_meta.get('filename') or '').strip()
    attachment_id = str(attachment_meta.get('attachmentId') or '').strip()
    if not filename or not attachment_id:
        return None
    warnings = attachment_meta.get('warnings')
    normalized_warnings = []
    if isinstance(warnings, list):
        for item in warnings:
            if not isinstance(item, dict):
                continue
            code = str(item.get('code') or '').strip()
            message = str(item.get('message') or '').strip()
            if code or message:
                normalized_warnings.append({'code': code, 'message': message})
    total_tokens = int(attachment_meta.get('totalTokens') or 0)
    from core.project_settings import CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS

    payload: Dict[str, Any] = {
        'attachmentId': attachment_id,
        'filename': filename,
        'sourceFormat': str(attachment_meta.get('sourceFormat') or '').strip(),
        'totalTokens': total_tokens,
        'chunkTokens': int(attachment_meta.get('chunkTokens') or 0),
        'isPartial': bool(attachment_meta.get('isPartial')) or total_tokens > CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS,
        # 全文超过当时模型窗口：附件仍可上传落盘，但永远不预注入正文。
        'isOversized': bool(attachment_meta.get('isOversized')),
        'warnings': normalized_warnings,
        'uploadedAt': int(attachment_meta.get('uploadedAt') or 0),
    }
    if attachment_meta.get('deleted'):
        payload['deleted'] = True
        deleted_at = attachment_meta.get('deletedAt')
        if deleted_at is not None:
            try:
                payload['deletedAt'] = int(deleted_at)
            except (TypeError, ValueError):
                pass
    return payload


def extract_imported_files_meta(active_meta: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    """从 ``activeMeta`` 取出所有附件元信息，统一归一化为列表。

    返回的列表保持入参顺序；未通过 ``_normalize_attachment_meta``
    校验的元素被静默丢弃，调用方拿到的永远是合法 dict。
    """
    if not isinstance(active_meta, dict):
        return []

    imported_files = active_meta.get('importedFiles')
    if isinstance(imported_files, list):
        result: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in imported_files:
            normalized = _normalize_attachment_meta(item)
            if not normalized:
                continue
            attachment_id = normalized['attachmentId']
            if attachment_id in seen_ids:
                continue  # 防止上游误传入重复 id
            seen_ids.add(attachment_id)
            result.append(normalized)
        return result

    return []


def build_imported_file_context_label(imported_file: Dict[str, Any] | None) -> str:
    if not isinstance(imported_file, dict):
        return ''
    filename = str(imported_file.get('filename') or '').strip()
    if not filename:
        return ''
    if imported_file.get('isPartial'):
        return f'【已上传文件首个分片：{filename}】'
    return f'【已上传文件：{filename}】'


# ==================== 写 DB 时的 metadata ====================

def build_user_message_metadata(
    channel: str,
    active_context: Any,
    imported_file_meta: List[Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """构造 user 消息的 metadata。仅存 attachmentId 引用 + 元信息。

    ``importedFiles`` 列表是附件引用的唯一真相源。
    只写代表“附件存在”的字段；空列表 / None 不写任何附件字段。
    """
    metadata: Dict[str, Any] = {'channel': channel}
    if isinstance(active_context, str):
        stored_context = active_context.strip()
        if stored_context:
            metadata['active_context'] = stored_context

    files = [dict(item) for item in (imported_file_meta or []) if isinstance(item, dict)]

    if files:
        metadata['importedFiles'] = files
    return metadata


# ==================== 调用 LLM 前的动态全文拼接 ====================

def _load_attachment_payload(
    user_id: str,
    project_name: str,
    imported_file_meta: Dict[str, Any],
) -> tuple[str, int, str | None]:
    """按 imported_file_meta 从磁盘拉单个附件正文：

    返回 ``(text, chunk_count, error_kind)``：
      - ``error_kind = None`` 成功拿到正文。
      - ``error_kind = 'cache_missing'`` 附件在 importedFiles 中但磁盘已清理。
      - ``error_kind = 'load_failed'`` 加载过程其它意外。
    """
    attachment_id = str(imported_file_meta.get('attachmentId') or '').strip()
    if not attachment_id:
        return '', 0, 'load_failed'
    is_partial = bool(imported_file_meta.get('isPartial'))

    try:
        from agents.attachment import (
            AttachmentNotFoundError,
            get_attachment_meta,
            load_attachment_text,
            load_chunks,
            touch_last_referenced,
        )

        if is_partial:
            meta = get_attachment_meta(user_id, project_name, attachment_id)
            chunk_count = int(meta.chunk_count) if meta else 0
            chunks = load_chunks(user_id, project_name, attachment_id)
            text = chunks[0] if chunks else ''
        else:
            text = load_attachment_text(user_id, project_name, attachment_id)
            meta = get_attachment_meta(user_id, project_name, attachment_id)
            chunk_count = int(meta.chunk_count) if meta else 0
        try:
            touch_last_referenced(user_id, project_name, attachment_id)
        except Exception:
            pass
        return (text or '').strip(), chunk_count, None
    except AttachmentNotFoundError:
        return '', 0, 'cache_missing'
    except Exception as exc:
        print(f"[chat] Failed to load attachment {attachment_id}: {exc}")
        return '', 0, 'load_failed'


def _build_single_attachment_block(
    user_id: str,
    project_name: str,
    imported_file_meta: Dict[str, Any],
) -> str:
    """单附件场景：维持现有体验（full 灌全文、partial 灌首片 + 分片说明）。"""
    label = build_imported_file_context_label(imported_file_meta)
    is_partial = bool(imported_file_meta.get('isPartial'))
    text, chunk_count, err = _load_attachment_payload(user_id, project_name, imported_file_meta)
    if err == 'cache_missing':
        filename = str(imported_file_meta.get('filename') or '').strip() or '未知文件'
        return (
            f'{label}\n[附件 "{filename}" 缓存已失效，无法读取原文]'
            if label
            else f'[附件 "{filename}" 缓存已失效]'
        )
    if err == 'load_failed' or not text:
        return ''

    block_parts: list[str] = []
    if label:
        block_parts.append(label)
    block_parts.append(text)

    if is_partial and chunk_count > 1:
        remaining = chunk_count - 1
        attachment_id = str(imported_file_meta.get('attachmentId') or '').strip()
        hint = (
            f'\n[分片说明] 以上是该附件的第 1 部分（共 {chunk_count} 部分），'
            f'剩余 {remaining} 部分未直接附带在上下文中。'
            f'\n如需阅读后续内容，请调用工具 '
            f'`read_attachment_chunk(attachment_id="{attachment_id}", chunk_index=1)` 读取第 2 部分；'
            f'可用 `describe_longread_source(source_id="{attachment_id}")` 先看全局地图。'
            f'\n读完后请先调用 `note_window_clues` 记录该分片的关键线索'
            f'（人物 / 伏笔 / 矛盾 / 时间 + 出处引用），再决定是否继续读取下一片。'
        )
        block_parts.append(hint)

    return '\n'.join(block_parts)


def _build_multi_attachment_manifest(
    user_id: str,
    project_name: str,
    imported_files: List[Dict[str, Any]],
) -> str:
    """多附件场景：只注入「文件清单 + 按需读取提示」，不预注入正文。

    文件清单包含：filename、chunk_count、状态（如缓存已失效会明示标记），
    让 LLM 能判断何时调 ``read_attachment_chunk(attachment_id=..., chunk_index=...)``。
    """
    rows: List[str] = []
    valid_attachment_ids: List[str] = []
    cache_missing: List[str] = []

    for imported_file_meta in imported_files:
        filename = str(imported_file_meta.get('filename') or '').strip() or '未知文件'
        attachment_id = str(imported_file_meta.get('attachmentId') or '').strip()
        if not attachment_id:
            continue

        # touch 索引不依赖于读取正文；只需 meta。
        # 注意：get_attachment_meta 在缓存缺失时返回 None（而不是抛异常）——
        # 多附件清单专用兜底：meta 为 None 视为缓存已失效。
        try:
            from agents.attachment import (
                get_attachment_meta,
                touch_last_referenced,
            )
            meta = get_attachment_meta(user_id, project_name, attachment_id)
        except Exception as exc:
            print(f"[chat] Failed to read attachment meta {attachment_id}: {exc}")
            continue

        if meta is None:
            cache_missing.append(filename)
            rows.append(f'- "{filename}" （attachment_id={attachment_id}）⚠️ 缓存已失效')
            continue

        try:
            touch_last_referenced(user_id, project_name, attachment_id)
        except Exception:
            pass

        chunk_count = int(meta.chunk_count) if meta else 0
        valid_attachment_ids.append(attachment_id)
        if chunk_count > 0:
            rows.append(
                f'- "{filename}" （attachment_id={attachment_id}，共 {chunk_count} 个分片）'
            )
        else:
            rows.append(f'- "{filename}" （attachment_id={attachment_id}）')

    if not rows:
        return ''

    header = f'【已上传 {len(imported_files)} 个附件】'
    instructions: List[str] = []
    if valid_attachment_ids:
        instructions.append(
            '上述附件未预载正文；需要阅读某个附件时请调用 '
            '`read_attachment_chunk(attachment_id="...", chunk_index=0)` 从第 0 个分片开始，'
            '或先用 `describe_longread_source(source_id="...")` 查看全局地图。\n'
            '读完后请先调用 `note_window_clues` 记录该分片的关键线索，再决定是否继续。\n'
            '滑窗底座会把旧窗口折叠为“线索 + 回跳指针”占位符，本轮新读窗口原文完整保留；'
            '需要回看时按账本里的窗口号跳转，不要线性逐片重扫。'
        )
    if cache_missing:
        instructions.append(
            '⚠️ 以下附件缓存已失效，调工具读取时会报错，请提醒用户重新上传：'
            + '、'.join(f'《{name}》' for name in cache_missing)
        )

    return '\n'.join([header, *rows, *instructions]) if instructions else '\n'.join([header, *rows])


def expand_active_context_with_attachments(
    user_id: str,
    project_name: str,
    active_context: str,
    imported_files: List[Dict[str, Any]] | None,
) -> str:
    """多附件感知的上下文拼接入口。

    策略：
    - 0 附件：原样返回 base。
    - 1 附件（非超窗）：走单附件分支（保留现有体验）。
    - 1 附件（超窗）或 ≥ 2 附件：走多附件分支，仅注入文件清单。
    """
    base = str(active_context or '').strip()
    if not isinstance(imported_files, list) or not imported_files:
        return base
    if not project_name:
        return base

    # 过滤已删除项，但保留 cache_missing 提示 —— 这个区别在单附件里也存在。
    active_files = [
        item for item in imported_files
        if isinstance(item, dict) and not item.get('deleted')
        and str(item.get('attachmentId') or '').strip()
    ]
    if not active_files:
        return base

    if len(active_files) == 1 and not bool(active_files[0].get('isOversized')):
        block = _build_single_attachment_block(user_id, project_name, active_files[0])
    else:
        block = _build_multi_attachment_manifest(user_id, project_name, active_files)

    if not block:
        return base
    return '\n\n'.join(seg for seg in [base, block] if seg)


__all__ = [
    'extract_imported_files_meta',
    'build_imported_file_context_label',
    'build_user_message_metadata',
    'expand_active_context_with_attachments',
]
