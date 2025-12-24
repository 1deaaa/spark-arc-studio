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

import json
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .communication import SparkBaseAgent
from .chat_manager import ChatManager
from .registry import get_agent_registry
from .agent_router import RouterAgent
from llm.llm_mgr import LLM_Manager


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


class DirectorAgent(SparkBaseAgent):
    def __init__(self, user_id: str, project_name: str):
        super().__init__(agent_id="agent_director", user_id=user_id)
        self.project_name = project_name
        # The director uses a high-quality model for summaries/context management
        self.llm = LLM_Manager.get_user_llm(
            user_id,
            agent_name="agent_director",
            streaming=False,
            temperature=0.1
        )
        # The director delegates routing to a specialized RouterAgent (using a fast model)
        self.router = RouterAgent(user_id)

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

    def _decide_targets(
        self,
        user_message: str,
        explicit_targets: Optional[List[str]] = None,
        history: List[Dict[str, Any]] = None
    ) -> List[str]:
        """Encapsulated routing decision logic."""
        targets: List[str] = []

        # 1. Explicit targets have highest priority
        if explicit_targets:
            for t in explicit_targets:
                if t and t not in targets and t != "agent_director":
                    targets.append(t)
            if targets:
                return targets

        # 2. Mention-based targets (strong signal)
        targets.extend(self._match_agents_by_mention(user_message))
        
        # 3. LLM-based routing (Delegated to RouterAgent)
        llm_targets = self.router.decide_targets(user_message, history=history)
        for t in llm_targets:
            if t not in targets:
                targets.append(t)

        # 4. Fallback: default to scriptwriter
        if not targets:
            targets = ["agent_scriptwriter"]
            
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
        # Fetch recent history for context-aware routing
        history = cm.get_history(agent_id="agent_director", context_key=context_key, limit=5)
        targets = self._decide_targets(user_message, explicit_targets, history=history)

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
