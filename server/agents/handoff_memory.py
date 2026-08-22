"""Director 委派给子 Agent 时使用的隔离会话记忆。"""

from __future__ import annotations

import hashlib
import json
from typing import List

from agents.chat_manager import ChatManager
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict


HANDOFF_MEMORY_KIND = "director_handoff_memory"
HANDOFF_CONTEXT_VERSION = 1


def build_handoff_context_key(room_agent_id: str, context_key: str) -> str:
    """为当前聊天房间生成不会与普通聊天碰撞的内部 context key。"""
    identity = json.dumps(
        {
            "version": HANDOFF_CONTEXT_VERSION,
            "room_agent_id": str(room_agent_id or "agent_director"),
            "context_key": str(context_key or "global"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"__director_handoff_v{HANDOFF_CONTEXT_VERSION}__:{digest}"


class DirectorHandoffMemory:
    """复用 ChatManager 保存同一导演房间内各专家的委派历史。"""

    def __init__(
        self,
        *,
        user_id: str,
        project_name: str,
        room_agent_id: str,
        context_key: str,
    ) -> None:
        self._chat_manager = ChatManager(
            user_id=str(user_id),
            project_name=str(project_name),
        )
        self.context_key = build_handoff_context_key(room_agent_id, context_key)

    def load_transcript(self, target_agent: str) -> List[BaseMessage]:
        """读取最近一次完整 LangChain 消息快照，保留工具调用边界。"""
        snapshots = self._chat_manager.get_history(
            agent_id=str(target_agent),
            context_key=self.context_key,
            limit=500,
        )
        for item in reversed(snapshots):
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if metadata.get("kind") != HANDOFF_MEMORY_KIND:
                continue
            transcript = metadata.get("transcript")
            if not isinstance(transcript, list):
                continue
            try:
                return list(messages_from_dict(transcript))
            except Exception:
                continue
        return []

    def save_transcript(
        self,
        *,
        target_agent: str,
        messages: List[BaseMessage],
        task_id: str = "",
    ) -> None:
        """保存完整消息快照；下一轮可原样恢复前缀和工具协议。"""
        metadata = {
            "kind": HANDOFF_MEMORY_KIND,
            "schema_version": HANDOFF_CONTEXT_VERSION,
            "task_id": str(task_id or ""),
            "hidden": True,
            "transcript": [message_to_dict(message) for message in messages],
        }
        snapshots = self._chat_manager.get_history(
            agent_id=str(target_agent),
            context_key=self.context_key,
            limit=500,
        )
        for item in reversed(snapshots):
            item_metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if item_metadata.get("kind") != HANDOFF_MEMORY_KIND:
                continue
            self._chat_manager.update_message_content_metadata(
                int(item["id"]),
                "子 Agent 委派历史快照",
                metadata,
            )
            return
        self._chat_manager.append_message(
            agent_id=str(target_agent),
            context_key=self.context_key,
            role="system",
            content="子 Agent 委派历史快照",
            metadata=metadata,
        )
