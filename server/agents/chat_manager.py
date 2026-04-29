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
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": int(m.timestamp.timestamp()),
                    "metadata": m.metadata_json or {},
                })
            return result

    def delete_message(self, message_id: int) -> bool:
        try:
            with UserInfoSession() as session:
                stmt = delete(ChatMessage).filter_by(id=message_id, user_id=self.user_id)
                session.execute(stmt)
                session.commit()
            return True
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False

    def update_message(self, message_id: int, content: Any) -> bool:
        try:
            with UserInfoSession() as session:
                msg = session.get(ChatMessage, message_id)
                if msg and msg.user_id == self.user_id:
                    msg.content = content
                    session.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating message: {e}")
            return False

    def update_message_metadata(self, message_id: int, metadata: Optional[Dict[str, Any]]) -> bool:
        try:
            with UserInfoSession() as session:
                msg = session.get(ChatMessage, message_id)
                if msg and msg.user_id == self.user_id:
                    msg.metadata_json = metadata or {}
                    session.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating message metadata: {e}")
            return False

    def update_message_content_metadata(self, message_id: int, content: Any, metadata: Optional[Dict[str, Any]]) -> bool:
        try:
            with UserInfoSession() as session:
                msg = session.get(ChatMessage, message_id)
                if msg and msg.user_id == self.user_id and msg.project_name == self.project_name:
                    msg.content = content
                    msg.metadata_json = metadata or {}
                    session.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating message content/metadata: {e}")
            return False

    def delete_after(self, *, agent_id: str, context_key: str, timestamp: float = None, message_id: int = None) -> bool:
        """删除指定会话中，在某个时间点/消息之后的所有消息。
        
        优先使用 message_id 作为边界（更可靠），若无则使用 timestamp。
        """
        try:
            with UserInfoSession() as session:
                if message_id is not None:
                    # 基于消息 ID 删除（更可靠）
                    stmt = delete(ChatMessage).filter(
                        ChatMessage.user_id == self.user_id,
                        ChatMessage.project_name == self.project_name,
                        ChatMessage.agent_id == agent_id,
                        ChatMessage.context_key == context_key,
                        ChatMessage.id > message_id
                    )
                elif timestamp is not None:
                    from datetime import datetime, timezone
                    # 数据库存储的是 UTC naive datetime，直接用 utcfromtimestamp
                    dt = datetime.utcfromtimestamp(timestamp)
                    stmt = delete(ChatMessage).filter(
                        ChatMessage.user_id == self.user_id,
                        ChatMessage.project_name == self.project_name,
                        ChatMessage.agent_id == agent_id,
                        ChatMessage.context_key == context_key,
                        ChatMessage.timestamp > dt
                    )
                else:
                    print("delete_after: 必须提供 message_id 或 timestamp")
                    return False
                session.execute(stmt)
                session.commit()
            return True
        except Exception as e:
            print(f"Error deleting messages after: {e}")
            return False

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

    def clear_project_sessions(self) -> bool:
        """清除该项目下所有聊天记录（所有 agent + contextKey）。"""
        try:
            with UserInfoSession() as session:
                stmt = delete(ChatMessage).filter_by(
                    user_id=self.user_id,
                    project_name=self.project_name,
                )
                session.execute(stmt)
                session.commit()
            return True
        except Exception as e:
            print(f"Error clearing project chat history: {e}")
            return False

    @staticmethod
    def rename_project(user_id: str | int, old_name: str, new_name: str) -> bool:
        """重命名项目时更新聊天记录中的 project_name。"""
        try:
            with UserInfoSession() as session:
                session.query(ChatMessage).filter_by(
                    user_id=int(user_id),
                    project_name=old_name,
                ).update({"project_name": new_name})
                session.commit()
            return True
        except Exception as e:
            print(f"Error renaming project in chat history: {e}")
            return False
