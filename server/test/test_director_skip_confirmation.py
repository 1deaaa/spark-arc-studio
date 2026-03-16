from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.communication import HANDOFF_CONFIRMATION_CONFIRMED
from agents.director_graph import sub_agent_node


class _DummySubAgent:
    def __init__(self):
        self.calls = []
        self.signals = type("Signals", (), {"is_beacon_open": True, "has_baton": True, "has_horn": True})()

    def chat_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"event": "assistant_delta", "text": "已直接执行，不再重复确认。"}


def test_sub_agent_node_passes_skip_tool_confirmation_and_collaboration_context(monkeypatch):
    dummy_agent = _DummySubAgent()

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: dummy_agent)
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "### 当前灵感\n旧灵感内容")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: None)

    state = {
        "user_id": "1",
        "project_name": "默认项目",
        "messages": [],
        "active_context": "",
        "pending_delegate": {
            "target_agent": "agent_muse",
            "task_description": "请直接重写灵感，不要再问用户确认。",
            "delivery_mode": "direct_to_user",
            "return_to": "agent_director",
            "grant_baton_to": "agent_muse",
            "delegated_by": "agent_director",
            "user_confirmation_state": HANDOFF_CONFIRMATION_CONFIRMED,
            "skip_tool_confirmation": True,
        },
        "sub_agent_result": None,
        "baton_holder": "agent_muse",
        "stream_events": [],
    }

    result = sub_agent_node(state)

    assert result["sub_agent_result"] == "已直接执行，不再重复确认。"
    assert len(dummy_agent.calls) == 1
    call = dummy_agent.calls[0]
    assert call["skip_tool_confirmation"] is True
    assert "delegated_by: agent_director" in call["active_context"]
    assert "user_confirmation_state: already_confirmed" in call["active_context"]
