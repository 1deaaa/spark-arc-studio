"""
聊天附件引用制：active_context / metadata 的纯函数集
====================================================

把附件全文从 DB 与请求体里完全剥离：
- 上传时由 ``server/core/routes_import.py`` 落盘到
  ``{project}/.attachments/{attachment_id}/`` 并返回 attachment_id；
- 前端 chatStore 把 attachmentId 写进 ``activeMeta.importedFile``，
  请求体与 DB 都不存全文；
- 本模块的 ``expand_active_context_with_attachment`` 在调用 LLM 前按
  attachmentId 从磁盘动态注入全文，缓存缺失时注入失效占位。

为什么单独成模块？
- 让 chat.py 路由层维持瘦身，避免"全文注入"、"DB 写入"、"占位生成"散开；
- 让单元测试不依赖 FastAPI / langchain 这些重度路由依赖，直接覆盖纯函数。
"""

from __future__ import annotations

from typing import Any, Dict


# ==================== 元信息抽取 / 标签 ====================

def extract_imported_file_meta(active_meta: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """把 ``activeMeta.importedFile`` 归一化成内部 dict。

    必须同时携带 ``attachmentId`` 与 ``filename``，缺一返回 None。"""
    if not isinstance(active_meta, dict):
        return None
    imported_file = active_meta.get('importedFile')
    if not isinstance(imported_file, dict):
        return None
    filename = str(imported_file.get('filename') or '').strip()
    attachment_id = str(imported_file.get('attachmentId') or imported_file.get('attachment_id') or '').strip()
    if not filename or not attachment_id:
        return None
    warnings = imported_file.get('warnings')
    normalized_warnings = []
    if isinstance(warnings, list):
        for item in warnings:
            if not isinstance(item, dict):
                continue
            code = str(item.get('code') or '').strip()
            message = str(item.get('message') or '').strip()
            if code or message:
                normalized_warnings.append({'code': code, 'message': message})
    return {
        'attachmentId': attachment_id,
        'filename': filename,
        'sourceFormat': str(imported_file.get('sourceFormat') or '').strip(),
        'totalTokens': int(imported_file.get('totalTokens') or 0),
        'chunkTokens': int(imported_file.get('chunkTokens') or 0),
        'isPartial': bool(imported_file.get('isPartial')),
        'warnings': normalized_warnings,
        'uploadedAt': int(imported_file.get('uploadedAt') or 0),
    }


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
    imported_file_meta: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """构造 user 消息的 metadata。仅存 attachmentId 引用 + 元信息。"""
    metadata: Dict[str, Any] = {'channel': channel}
    if isinstance(active_context, str):
        stored_context = active_context.strip()
        if stored_context:
            metadata['active_context'] = stored_context
    if imported_file_meta:
        metadata['importedFile'] = dict(imported_file_meta)
    return metadata


# ==================== 调用 LLM 前的动态全文拼接 ====================

def expand_active_context_with_attachment(
    user_id: str,
    project_name: str,
    active_context: str,
    imported_file_meta: Dict[str, Any] | None,
) -> str:
    """按 attachmentId 从磁盘加载附件正文并拼接到 active_context。

    - ``isPartial=True``：仅加载首个 chunk（与前端约定的 64K token 上限保持一致），
      避免大文件直接灌满 LLM context。
    - ``isPartial=False``：加载 full_text（小文件场景）。
    - 缓存缺失 → 注入失效占位；deleted / 无 attachmentId / 无 project → 原样返回。
    """
    base = str(active_context or '').strip()
    if not isinstance(imported_file_meta, dict):
        return base
    if imported_file_meta.get('deleted'):
        return base
    attachment_id = str(imported_file_meta.get('attachmentId') or '').strip()
    if not attachment_id or not project_name:
        return base

    label = build_imported_file_context_label(imported_file_meta)
    is_partial = bool(imported_file_meta.get('isPartial'))
    try:
        from agents.attachment import (
            AttachmentNotFoundError,
            load_attachment_text,
            load_chunks,
            touch_last_referenced,
        )

        if is_partial:
            chunks = load_chunks(user_id, project_name, attachment_id)
            text = chunks[0] if chunks else ''
        else:
            text = load_attachment_text(user_id, project_name, attachment_id)
        try:
            touch_last_referenced(user_id, project_name, attachment_id)
        except Exception:
            pass
    except AttachmentNotFoundError:
        filename = str(imported_file_meta.get('filename') or '').strip() or '未知文件'
        placeholder = f'{label}\n[附件 "{filename}" 缓存已失效，无法读取原文]' if label else f'[附件 "{filename}" 缓存已失效]'
        return '\n\n'.join(seg for seg in [base, placeholder] if seg)
    except Exception as exc:
        print(f"[chat] 加载附件 {attachment_id} 失败: {exc}")
        return base

    text = (text or '').strip()
    if not text:
        return base
    block = f'{label}\n{text}' if label else text
    return '\n\n'.join(seg for seg in [base, block] if seg)


__all__ = [
    'extract_imported_file_meta',
    'build_imported_file_context_label',
    'build_user_message_metadata',
    'expand_active_context_with_attachment',
]
