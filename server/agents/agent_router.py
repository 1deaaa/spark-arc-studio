"""Router Agent - Lightweight intent classification.

Handles routing decisions using a fast model.
"""

import json
import re
from typing import List, Dict, Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from .agent_utils import load_prompt
from .registry import get_agent_registry


class RouterAgent:
    def __init__(self, user_id: str):
        self.user_id = user_id
        # Always use the "fast" model for routing to ensure low latency
        self.llm = LLM_Manager.get_user_llm(
            user_id, 
            usage_key="fast", 
            streaming=False, 
            temperature=0.1
        )

    def _get_agent_descriptions(self) -> str:
        """Build description string from registry for the LLM, excluding non-routable agents."""
        lines = []
        for agent in get_agent_registry():
            # Skip agents marked as non-routable
            if agent.get('routable') == False:
                continue
            lines.append(f"- {agent['key']}: {agent['description']}")
        return "\n".join(lines)

    def decide_targets(self, user_message: str, history: List[Dict[str, Any]] = None) -> List[str]:
        """
        Decide which agents should handle the request.
        
        Args:
            user_message: The current message from the user.
            history: Optional list of recent messages for context.
            
        Returns:
            List of target agent IDs.
        """
        if not user_message or not user_message.strip():
            return []

        # Format history for the prompt
        history_text = "（无历史记录）"
        if history:
            history_lines = []
            for msg in history[-5:]: # Only last 5 messages
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")
                # Truncate content if too long
                if isinstance(content, str) and len(content) > 100:
                    content = content[:100] + "..."
                history_lines.append(f"{role}: {content}")
            history_text = "\n".join(history_lines)

        try:
            prompts = load_prompt(
                'router', 
                user_message=user_message,
                history=history_text,
                agent_descriptions=self._get_agent_descriptions()
            )
            
            messages = [
                SystemMessage(content=prompts['system']),
                HumanMessage(content=prompts['user'])
            ]
            
            response = self.llm.invoke(messages)
            content = response.content
            
            # Extract JSON from potential markdown or garbage
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                targets = data.get("targets", [])
                if isinstance(targets, list):
                    # Filter out invalid IDs and self
                    return [
                        t for t in targets
                        if isinstance(t, str)
                        and t not in {"agent_router", "agent_director"}
                    ]
            
            return []
        except Exception as e:
            print(f"[Router] Decision failed: {e}")
            return []
