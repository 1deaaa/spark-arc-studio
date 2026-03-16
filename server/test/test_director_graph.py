import json
from fastapi import Request
from fastapi.testclient import TestClient

from app import app
from core.auth import get_current_user
from core.request_context import set_current_context
from llm.llm_mgr import LLM_Manager

async def _fake_get_current_user(request: Request):
    user_id = "1"
    project_name = "默认项目"
    set_current_context(user_id, project_name)
    request.state.user = {"user_id": int(user_id), "username": "test_user"}
    return request.state.user

def test_run_director_delegation(monkeypatch):
    LLM_Manager.initialize_defaults()
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    client = TestClient(app)

    def _fake_run_director_stream(**kwargs):
        yield {"event": "tool_intent_started", "tool_name": "delegate_task", "source_agent": "agent_director"}
        yield {"event": "tool_exec_started", "tool_name": "delegate_task", "source_agent": "agent_director"}
        yield {"event": "agent_turn_started", "source_agent": "agent_lorebook", "nested": True}
        yield {
            "event": "tool_exec_started",
            "tool_name": "rewrite_worldview",
            "source_agent": "agent_lorebook",
            "nested": True,
        }
        yield {
            "event": "tool_exec_finished",
            "tool_name": "rewrite_worldview",
            "source_agent": "agent_lorebook",
            "nested": True,
        }
        yield {
            "event": "assistant_delta",
            "text": "设定已更新，魔法不能随便使用，否则会被反噬。",
            "source_agent": "agent_lorebook",
            "nested": True,
        }

    monkeypatch.setattr("agents.director_graph.run_director_stream", _fake_run_director_stream)

    payload = {
        "projectName": "默认项目",
        "agentId": "agent_director",
        "contextKey": "global",
        "message": (
            "请委派给设定专家 agent_lorebook去修改一下世界观设定，"
            "不用询问我，直接让他把最后加上设定「魔法不能随便使用，否则会被反噬。」"
        ),
    }

    print("\n=== Testing Director Graph API with Delegation ===")
    
    has_lorebook_source = False
    has_sub_agent_nested_tool = False
    has_assistant_delta = False

    # POST events
    # httpx TestClient stream yields raw chunk bytes. We need to split lines
    try:
        with client.stream("POST", "/api/chat/send/stream", json=payload) as resp:
            assert resp.status_code == 200

            for line in resp.iter_lines():
                if not line:
                    continue

                try:
                    evt = json.loads(line)

                    event_type = evt.get("event")
                    source_agent = evt.get("source_agent")
                    is_nested = evt.get("nested")

                    if source_agent == "agent_lorebook":
                        has_lorebook_source = True
                        if event_type in ("tool_intent_started", "tool_exec_started", "tool_exec_finished") and is_nested:
                            has_sub_agent_nested_tool = True

                    if event_type == "assistant_delta":
                        text = (evt.get("text") or "").strip()
                        if text:
                            has_assistant_delta = True

                    nested_str = " (nested)" if is_nested else ""
                    tool_str = f" | tool: {evt.get('tool_name')}" if evt.get('tool_name') else ""
                    text_str = f" | text: {repr(evt.get('text', ''))}" if event_type in ("assistant_delta", "reasoning_delta") else ""
                    print(f"[{source_agent}] {event_type}{nested_str}{tool_str}{text_str}")

                except json.JSONDecodeError:
                    pass
    finally:
        app.dependency_overrides.clear()

    # Assert conditions for phase 1 validation
    assert has_lorebook_source, "Did not receive events sourced from agent_lorebook"
    assert has_sub_agent_nested_tool, "Did not receive nested tool events from sub-agent"
    assert has_assistant_delta, "Did not receive assistant_delta text events"
