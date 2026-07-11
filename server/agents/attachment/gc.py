from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from core.models import ChatMessage, UserInfoSession

from .storage import _attachments_root, delete_attachment, get_attachment_meta


def _referenced_attachment_ids(user_id: str, project_name: str) -> set[str]:
    referenced: set[str] = set()
    with UserInfoSession() as session:
        rows = session.query(ChatMessage.metadata_json).filter(
            ChatMessage.user_id == int(user_id),
            ChatMessage.project_name == project_name,
        ).all()
    for row in rows:
        metadata = row[0] if isinstance(row, tuple) else getattr(row, "metadata_json", row)
        if not isinstance(metadata, dict):
            continue
        files = metadata.get("importedFiles")
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, dict) or item.get("deleted"):
                continue
            attachment_id = str(item.get("attachmentId") or "").strip()
            if attachment_id:
                referenced.add(attachment_id)
    return referenced


def collect_orphan_attachments(
    user_id: str,
    project_name: str,
    *,
    grace_seconds: int = 0,
) -> dict[str, Any]:
    """删除无聊天消息引用且超过宽限期的项目附件缓存。"""
    root = _attachments_root(str(user_id), project_name)
    if not os.path.isdir(root):
        return {"scanned": 0, "deleted": [], "retained": []}

    referenced = _referenced_attachment_ids(str(user_id), project_name)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(0, int(grace_seconds)))
    deleted: list[str] = []
    retained: list[str] = []

    for attachment_id in sorted(os.listdir(root)):
        attachment_root = os.path.join(root, attachment_id)
        if not os.path.isdir(attachment_root):
            continue
        if attachment_id in referenced:
            retained.append(attachment_id)
            continue
        meta = get_attachment_meta(str(user_id), project_name, attachment_id)
        timestamp_text = (meta.last_referenced_at or meta.uploaded_at) if meta else ""
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except Exception:
            timestamp = datetime.fromtimestamp(os.path.getmtime(attachment_root), tz=timezone.utc)
        if timestamp > cutoff:
            retained.append(attachment_id)
            continue
        if delete_attachment(str(user_id), project_name, attachment_id):
            deleted.append(attachment_id)
        else:
            retained.append(attachment_id)

    return {"scanned": len(deleted) + len(retained), "deleted": deleted, "retained": retained}
