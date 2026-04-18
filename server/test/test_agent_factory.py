import sys
from pathlib import Path
import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.agent_factory import DirectorGraphWrapper, create_agent_instance


def test_create_agent_instance_returns_director_graph_wrapper_for_director():
    agent = create_agent_instance("agent_director", "user_1", "project_a")

    assert isinstance(agent, DirectorGraphWrapper)
    assert agent.agent_id == "agent_director"
    assert agent.project_name == "project_a"


def test_create_agent_instance_returns_style_chat_agent_with_project_name(monkeypatch: pytest.MonkeyPatch):
    class DummyStyleAgent:
        def __init__(self, user_id: str, project_name: str | None = None):
            self.user_id = user_id
            self.project_name = project_name

    monkeypatch.setattr("agents.agent_factory.get_agent_class_map", lambda: {"agent_style": DummyStyleAgent})
    monkeypatch.setattr("agents.agent_style_chat.StyleChatAgent", DummyStyleAgent)

    agent = create_agent_instance("agent_style", "user_2", "project_b")

    assert isinstance(agent, DummyStyleAgent)
    assert agent.project_name == "project_b"


def test_create_agent_instance_returns_scriptwriter_agent_for_scriptwriter(monkeypatch: pytest.MonkeyPatch):
    class DummyScriptwriterAgent:
        def __init__(self, user_id: str):
            self.user_id = user_id

    monkeypatch.setattr("agents.agent_factory.get_agent_class_map", lambda: {"agent_scriptwriter": DummyScriptwriterAgent})

    agent = create_agent_instance("agent_scriptwriter", "user_3", "project_c")

    assert isinstance(agent, DummyScriptwriterAgent)
    assert agent.user_id == "user_3"
