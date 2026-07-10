"""Chat/session history storage using SQLite.

Goals:
- Per-user + per-project isolation
- Per-agent + per-contextKey session separation
- Persistent storage in users.db via SQLAlchemy
"""

from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional
from core.models import UserInfoSession, ChatMessage
from sqlalchemy import delete, func, select

from agents.context_budget import CONTEXT_CHECKPOINT_KIND, LEGACY_CONTEXT_SUMMARY_KIND
from agents.text_search import compile_search_pattern, search_first_match

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

    @staticmethod
    def _serialize_message(message: ChatMessage, *, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "timestamp": int(message.timestamp.timestamp()),
            "metadata": dict(metadata if metadata is not None else (message.metadata_json or {})),
        }

    def _session_filters(self, *, agent_id: str, context_key: str) -> tuple[Any, ...]:
        return (
            ChatMessage.user_id == self.user_id,
            ChatMessage.project_name == self.project_name,
            ChatMessage.agent_id == agent_id,
            ChatMessage.context_key == context_key,
        )

    def _latest_context_checkpoint(
        self,
        session: Any,
        *,
        agent_id: str,
        context_key: str,
    ) -> tuple[ChatMessage | None, Dict[str, Any]]:
        stmt = (
            select(ChatMessage)
            .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
            .where(ChatMessage.role == "system")
            .order_by(ChatMessage.id.desc())
        )
        for message in session.execute(stmt).scalars():
            metadata = dict(message.metadata_json or {})
            if metadata.get("kind") not in {CONTEXT_CHECKPOINT_KIND, LEGACY_CONTEXT_SUMMARY_KIND}:
                continue

            boundary = metadata.get("compacted_through_message_id")
            try:
                boundary = int(boundary)
            except (TypeError, ValueError):
                boundary = 0

            # 旧 context_summary 没有边界；按其写入时已经存在的最后一条原始消息补齐。
            if boundary <= 0:
                previous_stmt = (
                    select(
                        func.min(ChatMessage.id),
                        func.max(ChatMessage.id),
                        func.count(ChatMessage.id),
                    )
                    .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                    .where(ChatMessage.role.in_(("user", "assistant")))
                    .where(ChatMessage.id < message.id)
                )
                first_id, last_id, original_count = session.execute(previous_stmt).one()
                boundary = int(last_id or 0)
                if boundary > 0:
                    metadata["compacted_through_message_id"] = boundary
                    metadata.setdefault("source_message_id_start", int(first_id or boundary))
                    metadata.setdefault("source_message_id_end", boundary)
                    metadata.setdefault("original_messages", int(original_count or 0))
            return message, metadata
        return None, {}

    def get_context_history(self, *, agent_id: str, context_key: str) -> List[Dict[str, Any]]:
        """返回模型运行时视图：最新 checkpoint 加其边界之后的全部原始消息。"""
        with UserInfoSession() as session:
            checkpoint, checkpoint_metadata = self._latest_context_checkpoint(
                session,
                agent_id=agent_id,
                context_key=context_key,
            )
            boundary = int(checkpoint_metadata.get("compacted_through_message_id") or 0)
            stmt = (
                select(ChatMessage)
                .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                .where(ChatMessage.role.in_(("user", "assistant")))
                .where(ChatMessage.id > boundary)
                .order_by(ChatMessage.id.asc())
            )
            result: List[Dict[str, Any]] = []
            if checkpoint is not None and boundary > 0:
                result.append(self._serialize_message(checkpoint, metadata=checkpoint_metadata))
            result.extend(self._serialize_message(message) for message in session.execute(stmt).scalars())
            return result

    def persist_context_checkpoint(
        self,
        *,
        agent_id: str,
        context_key: str,
        checkpoint: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """幂等保存上下文 checkpoint；旧边界或同边界候选不会产生重复记录。"""
        payload = dict(checkpoint or {})
        summary = payload.get("summary")
        metadata = dict(payload.get("metadata") or {})
        try:
            boundary = int(metadata.get("compacted_through_message_id") or 0)
        except (TypeError, ValueError):
            boundary = 0
        if boundary <= 0 or not isinstance(summary, dict):
            return None

        with UserInfoSession() as session:
            latest, latest_metadata = self._latest_context_checkpoint(
                session,
                agent_id=agent_id,
                context_key=context_key,
            )
            latest_boundary = int(latest_metadata.get("compacted_through_message_id") or 0)
            if latest is not None and latest_boundary >= boundary:
                return self._serialize_message(latest, metadata=latest_metadata)

            boundary_stmt = (
                select(ChatMessage.id)
                .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                .where(ChatMessage.id == boundary)
                .where(ChatMessage.role.in_(("user", "assistant")))
            )
            if session.execute(boundary_stmt).scalar_one_or_none() is None:
                return None

            metadata.update({
                "kind": CONTEXT_CHECKPOINT_KIND,
                "schema_version": 1,
                "compacted_through_message_id": boundary,
                "created_at": int(metadata.get("created_at") or time.time()),
            })
            message = ChatMessage(
                user_id=self.user_id,
                project_name=self.project_name,
                agent_id=agent_id,
                context_key=context_key,
                role="system",
                content=summary,
                metadata_json=metadata,
            )
            session.add(message)
            session.commit()
            session.refresh(message)
            return self._serialize_message(message)

    def search_history(
        self,
        *,
        agent_id: str,
        context_key: str,
        query: str,
        mode: str = "literal",
        case_sensitive: bool = False,
        limit: int = 8,
        before_message_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """搜索保留在数据库中的原始用户/助手消息，包括已被 checkpoint 覆盖的历史。"""
        clean_query = str(query or "").strip()
        if not clean_query:
            return []
        normalized_mode = str(mode or "literal").strip().lower()
        if normalized_mode not in {"literal", "regex"}:
            raise ValueError(f"不支持的聊天历史搜索模式: {mode}")
        compiled = (
            compile_search_pattern(clean_query, case_sensitive=case_sensitive)
            if normalized_mode == "regex"
            else None
        )
        needle = clean_query if case_sensitive else clean_query.casefold()
        safe_limit = max(1, min(int(limit or 8), 20))

        with UserInfoSession() as session:
            stmt = (
                select(ChatMessage)
                .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                .where(ChatMessage.role.in_(("user", "assistant")))
                .order_by(ChatMessage.id.desc())
            )
            if before_message_id is not None:
                stmt = stmt.where(ChatMessage.id < int(before_message_id))

            matches: List[Dict[str, Any]] = []
            for message in session.execute(stmt).scalars():
                content = message.content
                if isinstance(content, str):
                    searchable = content
                else:
                    searchable = json.dumps(content, ensure_ascii=False)
                if compiled is not None:
                    match = search_first_match(compiled, searchable)
                    if match is None:
                        continue
                    match_start, match_end = match.start(), match.end()
                else:
                    haystack = searchable if case_sensitive else searchable.casefold()
                    match_start = haystack.find(needle)
                    if match_start < 0:
                        continue
                    match_end = match_start + len(clean_query)
                matches.append({
                    "id": message.id,
                    "role": message.role,
                    "content": searchable,
                    "timestamp": int(message.timestamp.timestamp()),
                    "match_start": match_start,
                    "match_end": match_end,
                })
                if len(matches) >= safe_limit:
                    break
            return matches

    def get_message_context(
        self,
        *,
        agent_id: str,
        context_key: str,
        message_id: int,
        radius: int = 1,
    ) -> List[Dict[str, Any]]:
        """读取命中消息及同房间相邻原始消息，不包含 checkpoint 或提示卡。"""
        safe_radius = max(0, min(int(radius or 0), 3))
        with UserInfoSession() as session:
            target_stmt = (
                select(ChatMessage)
                .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                .where(ChatMessage.role.in_(("user", "assistant")))
                .where(ChatMessage.id == int(message_id))
            )
            target = session.execute(target_stmt).scalar_one_or_none()
            if target is None:
                return []

            before: list[ChatMessage] = []
            after: list[ChatMessage] = []
            if safe_radius:
                before_stmt = (
                    select(ChatMessage)
                    .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                    .where(ChatMessage.role.in_(("user", "assistant")))
                    .where(ChatMessage.id < target.id)
                    .order_by(ChatMessage.id.desc())
                    .limit(safe_radius)
                )
                after_stmt = (
                    select(ChatMessage)
                    .where(*self._session_filters(agent_id=agent_id, context_key=context_key))
                    .where(ChatMessage.role.in_(("user", "assistant")))
                    .where(ChatMessage.id > target.id)
                    .order_by(ChatMessage.id.asc())
                    .limit(safe_radius)
                )
                before = list(reversed(session.execute(before_stmt).scalars().all()))
                after = list(session.execute(after_stmt).scalars().all())

            return [self._serialize_message(message) for message in [*before, target, *after]]

    def _invalidate_covering_checkpoints(self, session: Any, *, message: ChatMessage) -> None:
        stmt = (
            select(ChatMessage)
            .where(*self._session_filters(agent_id=message.agent_id, context_key=message.context_key))
            .where(ChatMessage.role == "system")
        )
        checkpoint_ids: List[int] = []
        for checkpoint in session.execute(stmt).scalars():
            metadata = dict(checkpoint.metadata_json or {})
            if metadata.get("kind") not in {CONTEXT_CHECKPOINT_KIND, LEGACY_CONTEXT_SUMMARY_KIND}:
                continue
            try:
                boundary = int(metadata.get("compacted_through_message_id") or checkpoint.id - 1)
            except (TypeError, ValueError):
                boundary = checkpoint.id - 1
            if message.id <= boundary:
                checkpoint_ids.append(checkpoint.id)
        if checkpoint_ids:
            notice_stmt = (
                select(ChatMessage)
                .where(*self._session_filters(agent_id=message.agent_id, context_key=message.context_key))
                .where(ChatMessage.role == "assistant")
            )
            notice_ids: List[int] = []
            checkpoint_id_set = set(checkpoint_ids)
            for notice in session.execute(notice_stmt).scalars():
                metadata = dict(notice.metadata_json or {})
                if metadata.get("kind") != "context_compaction_notice":
                    continue
                segments = metadata.get("segments") if isinstance(metadata.get("segments"), list) else []
                summary_ids = {
                    int(segment.get("summary_message_id"))
                    for segment in segments
                    if isinstance(segment, dict) and str(segment.get("summary_message_id") or "").isdigit()
                }
                if summary_ids & checkpoint_id_set:
                    notice_ids.append(notice.id)
            session.execute(delete(ChatMessage).where(ChatMessage.id.in_(checkpoint_ids)))
            if notice_ids:
                session.execute(delete(ChatMessage).where(ChatMessage.id.in_(notice_ids)))

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
                .order_by(ChatMessage.timestamp.desc(), ChatMessage.id.desc())
                .limit(limit)
            )
            messages = session.execute(stmt).scalars().all()
            
            # 转换为字典并恢复时间正序（SQL 是倒序拿最新的，展示需要正序）
            result = []
            for m in reversed(messages):
                result.append(self._serialize_message(m))
            return result

    def delete_message(self, message_id: int) -> bool:
        try:
            with UserInfoSession() as session:
                message = session.get(ChatMessage, message_id)
                if not message or message.user_id != self.user_id or message.project_name != self.project_name:
                    return False
                self._invalidate_covering_checkpoints(session, message=message)
                session.delete(message)
                session.commit()
            return True
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False

    def update_message(self, message_id: int, content: Any) -> bool:
        try:
            with UserInfoSession() as session:
                msg = session.get(ChatMessage, message_id)
                if msg and msg.user_id == self.user_id and msg.project_name == self.project_name:
                    self._invalidate_covering_checkpoints(session, message=msg)
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
                    print("delete_after: must provide message_id or timestamp")
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
