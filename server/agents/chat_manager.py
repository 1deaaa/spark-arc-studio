"""Chat/session history storage.

Goals:
- Per-user + per-project isolation
- Per-agent + per-contextKey session separation
- Append-only storage (jsonl) to avoid rewriting large JSON blobs
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.utils import get_project_path, ensure_project_directory


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9_\-\.\u4e00-\u9fff]+")


def _safe_path_segment(value: str, *, fallback: str = "global") -> str:
    if not value:
        return fallback
    value = str(value).strip()
    if not value:
        return fallback
    value = _SAFE_SEGMENT_RE.sub("_", value)
    value = value.strip("._ ")
    return value or fallback


@dataclass
class ChatMessage:
    role: str
    content: Any
    timestamp: int
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata or {},
        }


class ChatManager:
    """File-backed chat history.

    Layout:
      {project}/chat_history/{agent_id}/{context_key}.jsonl
    """

    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = str(project_name)
        ensure_project_directory(self.user_id, self.project_name)

    def _session_file(self, agent_id: str, context_key: str) -> str:
        agent_seg = _safe_path_segment(agent_id, fallback="agent")
        ctx_seg = _safe_path_segment(context_key, fallback="global")
        root = os.path.join(get_project_path(self.user_id, self.project_name), "chat_history", agent_seg)
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, f"{ctx_seg}.jsonl")

    def append_message(
        self,
        *,
        agent_id: str,
        context_key: str,
        role: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            role=str(role),
            content=content,
            timestamp=int(timestamp or time.time()),
            metadata=metadata or {},
        )

        path = self._session_file(agent_id, context_key)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(msg.to_dict(), ensure_ascii=False))
            f.write("\n")
        return msg

    def get_history(self, *, agent_id: str, context_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        limit = int(limit or 50)
        if limit <= 0:
            return []
        if limit > 500:
            limit = 500

        path = self._session_file(agent_id, context_key)
        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception:
            return []

        if not lines:
            return []

        items: List[Dict[str, Any]] = []
        for raw in lines[-limit:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                items.append(json.loads(raw))
            except Exception:
                continue
        return items

    def clear_session(self, *, agent_id: str, context_key: str) -> bool:
        path = self._session_file(agent_id, context_key)
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            return False
