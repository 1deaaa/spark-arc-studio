from __future__ import annotations

from typing import Any

from .communication import SparkBaseAgent


class DirectorGraphWrapper:
    def __init__(self, user_id: str, project_name: str):
        self.user_id = str(user_id)
        self.project_name = project_name
        self.agent_id = "agent_director"
        self.name = "主控导演"

        class MockBeacon:
            is_open = True

        self.beacon = MockBeacon()

    def chat_stream(self, user_message: str, history=None, active_context: str = None, **kwargs):
        from agents.director_graph import run_director_stream

        return run_director_stream(
            user_id=self.user_id,
            project_name=self.project_name,
            user_message=user_message,
            history=history,
            active_context=active_context or "",
            **kwargs,
        )

    def chat(self, user_message: str, history=None, active_context: str = None, **kwargs) -> str:
        chunks: list[str] = []
        error_text = ""
        for event in self.chat_stream(
            user_message,
            history=history,
            active_context=active_context,
            **kwargs,
        ):
            if isinstance(event, dict):
                event_name = str(event.get("event") or "")
                if event_name == "assistant_delta":
                    chunks.append(str(event.get("text") or ""))
                elif event_name == "error":
                    error_payload = event.get("data")
                    error_text = str(error_payload or event)
            elif isinstance(event, str):
                chunks.append(event)
        text = "".join(chunks).strip()
        return text or error_text


def get_agent_class_map() -> dict[str, type[Any]]:
    from agents import CriticAgent, ScriptwriterAgent, ShowrunnerAgent
    from agents.agent_lorebook import WorldviewAgent
    from agents.agent_style_chat import StyleChatAgent
    from agents.setup_agents import MuseAgent

    return {
        "agent_showrunner": ShowrunnerAgent,
        "agent_scriptwriter": ScriptwriterAgent,
        "agent_critic": CriticAgent,
        "agent_lorebook": WorldviewAgent,
        "agent_muse": MuseAgent,
        "agent_style": StyleChatAgent,
    }


def create_agent_instance(agent_id: str, user_id: str, project_name: str):
    if agent_id == "agent_director":
        return DirectorGraphWrapper(user_id, project_name)

    from agents.agent_style_chat import StyleChatAgent

    agent_class_map = get_agent_class_map()
    cls = agent_class_map.get(agent_id, SparkBaseAgent)
    if cls == SparkBaseAgent:
        return cls(agent_id=agent_id, user_id=user_id)
    if cls is StyleChatAgent:
        return cls(user_id=user_id, project_name=project_name)
    if agent_id == "agent_muse":
        return cls(user_id=user_id, project_name=project_name)
    return cls(user_id=user_id)
