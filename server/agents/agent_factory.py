from __future__ import annotations

from typing import Any

from core.request_context import normalize_project_name

from .communication import SparkBaseAgent


# 这些 Agent 的现有构造器明确支持 project_name；其他专家构造器必须保持旧签名。
_AGENT_CONSTRUCTOR_PROJECT_NAME_SUPPORT: dict[str, bool] = {
    "agent_showrunner": False,
    "agent_scriptwriter": False,
    "agent_critic": False,
    "agent_lorebook": False,
    "agent_muse": True,
    "agent_style": True,
}


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


def _normalize_factory_project_name(project_name: str | None) -> str:
    """把工厂入口的项目名固定为实例与工具共用的规范值。"""
    return normalize_project_name(project_name) or ""


def _bind_agent_project_name(agent: Any, project_name: str) -> Any:
    """把规范化项目名绑定到实例，不改变调用者的请求上下文。"""
    if hasattr(agent, "project_name"):
        agent.project_name = project_name
    return agent


def create_agent_instance(agent_id: str, user_id: str, project_name: str | None = ""):
    """按固定构造契约创建 Agent，并绑定显式项目身份。"""
    normalized_project_name = _normalize_factory_project_name(project_name)

    if agent_id == "agent_director":
        return _bind_agent_project_name(
            DirectorGraphWrapper(user_id, normalized_project_name),
            normalized_project_name,
        )

    agent_class_map = get_agent_class_map()
    cls = agent_class_map.get(agent_id, SparkBaseAgent)
    if cls == SparkBaseAgent:
        # SparkBaseAgent 的构造器支持 project_name，兜底 Agent 也必须保持项目隔离。
        agent = cls(
            agent_id=agent_id,
            user_id=user_id,
            project_name=normalized_project_name,
        )
    elif _AGENT_CONSTRUCTOR_PROJECT_NAME_SUPPORT.get(agent_id, False):
        agent = cls(user_id=user_id, project_name=normalized_project_name)
    else:
        # Showrunner、Scriptwriter、Critic、Worldview 的旧构造器不接受 project_name。
        agent = cls(user_id=user_id)

    return _bind_agent_project_name(agent, normalized_project_name)
