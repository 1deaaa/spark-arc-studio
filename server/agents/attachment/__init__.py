"""
agents.attachment
=================

聊天附件的落盘/读取/清理服务。

附件文件不进 DB，而是以 content_hash 为 id 存到
``{project_path}/.attachments/{attachment_id}/``：

    meta.json        # filename, source_format, total_tokens, uploaded_at, chunk_count
    full.txt         # 完整文本（UTF-8）
    chunks/chunk_0.txt, chunk_1.txt, ...
    summary.json     # （可选）AttachmentAnalyzer 生成的目录/主旨（PR4 产出）
    cache/           # （可选）analyze_attachment 工具按 focus 缓存的分析结果

聊天记录只保存 ``attachment_id`` 引用，发送消息时动态读盘拼到上下文；
附件文件缺失时注入 "[引用已失效]" 提示，不中断对话。
"""

from .storage import (
    AttachmentMeta,
    AttachmentNotFoundError,
    delete_attachment,
    ensure_attachments_root,
    get_attachment_meta,
    get_attachment_root,
    get_chunk_paths,
    load_attachment_text,
    load_chunks,
    save_attachment,
    touch_last_referenced,
)

__all__ = [
    "AttachmentMeta",
    "AttachmentNotFoundError",
    "delete_attachment",
    "ensure_attachments_root",
    "get_attachment_meta",
    "get_attachment_root",
    "get_chunk_paths",
    "load_attachment_text",
    "load_chunks",
    "save_attachment",
    "touch_last_referenced",
]
