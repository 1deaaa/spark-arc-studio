"""Chat/session history storage using SQLite.

Goals:
- Per-user + per-project isolation
- Per-agent + per-contextKey session separation
- Persistent storage in users.db via SQLAlchemy
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional
from core.models import UserInfoSession, ChatMessage
from sqlalchemy import select, delete

class ChatManager:
    """Database-backed chat history."""

    def __init__(self, user_id: str | int, project_name: str):
        self.user_id = int(user_id)
        self.project_name = str(project_name)

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
        with UserInfoSession() as session:
            msg = ChatMessage(
                user_id=self.user_id,
                project_name=self.project_name,
                agent_id=agent_id,
                context_key=context_key,
                role=role,
                content=content,
                metadata_json=metadata or {},
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            return msg

    def get_history(self, *, agent_id: str, context_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        limit = max(0, min(int(limit or 50), 500))
        if limit == 0:
            return []

        with UserInfoSession() as session:
            stmt = (
                select(ChatMessage)
                .filter_by(
                    user_id=self.user_id,
                    project_name=self.project_name,
                    agent_id=agent_id,
                    context_key=context_key
                )
                .order_by(ChatMessage.timestamp.desc())
                .limit(limit)
            )
            messages = session.execute(stmt).scalars().all()
            
            # 转换为字典并恢复时间正序（SQL 是倒序拿最新的，展示需要正序）
            result = []
            for m in reversed(messages):
                result.append({
                    "role": m.role,
                    "content": m.content,
                    "timestamp": int(m.timestamp.timestamp()),
                    "metadata": m.metadata_json or {},
                })
            return result

    def clear_session(self, *, agent_id: str, context_key: str) -> bool:
        try:
            with UserInfoSession() as session:
                stmt = delete(ChatMessage).filter_by(
                    user_id=self.user_id,
                    project_name=self.project_name,
                    agent_id=agent_id,
                    context_key=context_key
                )
                session.execute(stmt)
                session.commit()
            return True
        except Exception as e:
            print(f"Error clearing chat history: {e}")
            return False
