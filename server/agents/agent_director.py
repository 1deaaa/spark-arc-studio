"""Director Agent - global routing + session recording.

This agent acts as the single entry point for the *global channel*:
- Understand a user's free-form request
- Decide which specialist agents should receive it
- Record the user's request into those agents' session histories
- Return a concise summary of routing decisions

Design note:
We intentionally keep execution lightweight: routing + recording first.
Specialist agents can later consume the recorded session messages as context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .communication import SparkBaseAgent
from .chat_manager import ChatManager
from .registry import get_agent_registry


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


class DirectorAgent(SparkBaseAgent):
    def __init__(self, user_id: str, project_name: str):
        super().__init__(agent_id="agent_director", user_id=user_id)
        self.project_name = project_name

    def _match_agents_by_mention(self, user_text: str) -> List[str]:
        """Match agent_id by either key or display name mention."""
        t = _normalize_text(user_text)
        if not t:
            return []

        hits: List[str] = []
        for info in get_agent_registry():
            key = (info.get("key") or "").strip()
            name = (info.get("name") or "").strip().lower()
            if not key:
                continue
            if key.lower() in t or (name and name in t):
                hits.append(key)
        # never self-route by mention unless explicitly needed
        return [k for k in hits if k != "agent_director"]

    def _route_by_keywords(self, user_text: str) -> List[str]:
        t = _normalize_text(user_text)
        if not t:
            return []

        targets: List[str] = []

        def add(agent_id: str):
            if agent_id not in targets and agent_id != "agent_director":
                targets.append(agent_id)

        # structure / outline
        if any(k in t for k in ["大纲", "梗概", "节拍", "结构", "分集", "章", "剧情结构"]):
            add("agent_showrunner")

        # writing / scene content
        if any(k in t for k in ["续写", "对话", "场景", "台词", "旁白", "桥段", "过渡"]):
            add("agent_scriptwriter")

        # style
        if any(k in t for k in ["文风", "风格", "写实", "克制", "幽默", "黑色幽默", "紧张", "轻松", "节奏", "口吻"]):
            add("agent_style")

        # lorebook
        if any(k in t for k in ["世界观", "设定", "角色", "人物", "背景", "阵营", "能力", "关系"]):
            add("agent_lorebook")

        # inspiration
        if any(k in t for k in ["灵感", "点子", "创意", "脑洞"]):
            add("agent_muse")

        # critique
        if any(k in t for k in ["逻辑", "漏洞", "不合理", "bug", "矛盾", "评审", "审核"]):
            add("agent_critic")

        return targets

    def route_and_record(
        self,
        *,
        user_id: str,
        project_name: str,
        context_key: str,
        user_message: str,
        explicit_targets: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Route a global-channel user message.

        Returns a routing summary and writes:
        - user message to director session
        - (silently) user message into each target agent session
        """
        cm = ChatManager(user_id=user_id, project_name=project_name)

        # 1) record into director session
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="user",
            content=user_message,
            metadata=metadata or {},
        )

        # 2) decide targets
        targets: List[str] = []

        # explicit targets have highest priority
        if explicit_targets:
            for t in explicit_targets:
                if t and t not in targets and t != "agent_director":
                    targets.append(t)
        else:
            # mention-based targets
            targets.extend(self._match_agents_by_mention(user_message))
            # keyword-based routing (may add more)
            for t in self._route_by_keywords(user_message):
                if t not in targets:
                    targets.append(t)

        # fallback: if nothing matched, record to scriptwriter as a safe default
        if not targets:
            targets = ["agent_scriptwriter"]

        # 3) silently record into each agent session
        routed = []
        for target in targets:
            cm.append_message(
                agent_id=target,
                context_key=context_key,
                role="user",
                content=user_message,
                metadata={
                    "routed_by": "agent_director",
                    "source_context": context_key,
                    "source_agent": "agent_director",
                    **(metadata or {}),
                },
            )
            routed.append(target)

        # 4) director assistant summary
        summary = {
            "routed_to": routed,
            "context_key": context_key,
            "note": "已将需求分发并写入各目标 Agent 的会话上下文。",
        }
        cm.append_message(
            agent_id="agent_director",
            context_key=context_key,
            role="assistant",
            content=summary,
            metadata={"type": "routing_summary"},
        )

        return summary
