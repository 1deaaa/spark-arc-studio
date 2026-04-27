from pathlib import Path
import sys
import threading


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from agents.agent_scriptwriter import ScriptwriterAgent
from agents.communication import SparkBaseAgent
from agents.director_graph import run_director_stream, sub_agent_node


class _CancelAwareSubAgent:
    def __init__(self):
        self.calls = []
        self.pulled_after_cancel = False
        self.signals = type("Signals", (), {"is_beacon_open": True, "has_baton": True, "has_horn": True})()

    def chat_stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"event": "assistant_delta", "text": "first"}
        self.pulled_after_cancel = True
        yield {"event": "assistant_delta", "text": "second"}


def test_sub_agent_node_passes_stop_event_and_stops_after_cancel(monkeypatch):
    stop_event = threading.Event()
    dummy_agent = _CancelAwareSubAgent()
    written_events = []

    def _writer(event):
        written_events.append(event)
        if event.get("event") == "assistant_delta":
            stop_event.set()

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: dummy_agent)
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "### 当前正文")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: _writer)

    result = sub_agent_node({
        "user_id": "1",
        "project_name": "默认项目",
        "messages": [],
        "active_context": "",
        "pending_delegate": {
            "target_agent": "agent_scriptwriter",
            "task_description": "大范围改写正文。",
            "delivery_mode": "direct_to_user",
            "return_to": "agent_director",
            "grant_baton_to": "agent_scriptwriter",
            "delegated_by": "agent_director",
            "skip_tool_confirmation": True,
        },
        "sub_agent_result": None,
        "baton_holder": "agent_scriptwriter",
        "stream_events": [],
        "stop_event": stop_event,
    })

    assert dummy_agent.calls[0]["stop_event"] is stop_event
    assert dummy_agent.pulled_after_cancel is False
    assert result["pending_delegate"] is None
    assert result["sub_agent_result"] == "[agent_scriptwriter] 委派任务已取消"
    assert not any(event.get("text") == "second" for event in written_events)


def test_run_director_stream_passes_stop_event_to_graph(monkeypatch):
    stop_event = threading.Event()
    captured_state = {}

    class _FakeGraph:
        def stream(self, state, **kwargs):
            captured_state.update(state)
            yield ("custom", {"event": "assistant_delta", "text": "ok"})

    monkeypatch.setattr("agents.director_graph.create_director_graph", lambda: _FakeGraph())

    events = list(run_director_stream(
        user_id="1",
        project_name="默认项目",
        user_message="请导演规划。",
        history=[],
        active_context="",
        stop_event=stop_event,
    ))

    assert captured_state["stop_event"] is stop_event
    assert events == [{"event": "assistant_delta", "text": "ok"}]


def test_scriptwriter_chat_stream_forwards_stop_event(monkeypatch):
    stop_event = threading.Event()
    captured_kwargs = {}

    class _DummyMatchbox:
        def get_user_llm(self, *args, **kwargs):
            return object()

    def _fake_base_chat_stream(self, user_message, history=None, active_context=None, **kwargs):
        captured_kwargs.update(kwargs)
        yield {"event": "assistant_delta", "text": "ok"}

    monkeypatch.setattr("agents.agent_scriptwriter.matchbox", lambda: _DummyMatchbox())
    monkeypatch.setattr(SparkBaseAgent, "chat_stream", _fake_base_chat_stream)

    agent = ScriptwriterAgent(user_id="1")
    events = list(agent.chat_stream(
        "请根据上下文做一段较长的改写。",
        history=[],
        active_context="",
        stop_event=stop_event,
    ))

    assert captured_kwargs["stop_event"] is stop_event
    assert events == [{"event": "assistant_delta", "text": "ok"}]
