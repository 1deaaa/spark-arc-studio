from __future__ import annotations

import threading

from langchain_core.messages import AIMessage, ToolMessage

from agents.director_graph import _retain_only_pending_delegate_tool_call, run_director_stream


def _tool_call_ids(message: AIMessage) -> set[str]:
    ids: set[str] = set()
    for item in getattr(message, "tool_calls", None) or []:
        ids.add(str(item.get("id") or ""))
    for item in getattr(message, "additional_kwargs", {}).get("tool_calls", []) or []:
        if isinstance(item, dict):
            ids.add(str(item.get("id") or ""))
    return ids


def test_pending_delegate_history_keeps_only_matching_tool_call() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_tracker",
                "name": "work_tracker",
                "args": {"action": "update"},
                "type": "tool_call",
            },
            {
                "id": "call_delegate",
                "name": "delegate_task",
                "args": {"target_agent": "agent_lorebook"},
                "type": "tool_call",
            },
        ],
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_tracker",
                    "type": "function",
                    "function": {"name": "work_tracker", "arguments": "{\"action\":\"update\"}"},
                },
                {
                    "id": "call_delegate",
                    "type": "function",
                    "function": {"name": "delegate_task", "arguments": "{\"target_agent\":\"agent_lorebook\"}"},
                },
            ]
        },
    )

    pruned = _retain_only_pending_delegate_tool_call(
        message,
        selected_spec={
            "raw": message.tool_calls[1],
            "name": "delegate_task",
            "args": {"target_agent": "agent_lorebook"},
            "index": 1,
        },
        call_id="call_delegate",
        tool_name="delegate_task",
    )

    assert [item["id"] for item in pruned.tool_calls] == ["call_delegate"]
    assert [item["id"] for item in pruned.additional_kwargs["tool_calls"]] == ["call_delegate"]
    assert _tool_call_ids(pruned) == {"call_delegate"}


def test_pending_delegate_history_injects_fallback_tool_call_id() -> None:
    message = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "",
                "name": "delegate_task",
                "args": {"target_agent": "agent_lorebook"},
                "type": "tool_call",
            }
        ],
        additional_kwargs={
            "tool_calls": [
                {
                    "type": "function",
                    "function": {"name": "delegate_task", "arguments": "{\"target_agent\":\"agent_lorebook\"}"},
                }
            ]
        },
    )

    pruned = _retain_only_pending_delegate_tool_call(
        message,
        selected_spec={
            "raw": message.tool_calls[0],
            "name": "delegate_task",
            "args": {"target_agent": "agent_lorebook"},
            "index": 0,
        },
        call_id="agent_director:delegate_task:0",
        tool_name="delegate_task",
    )
    response = ToolMessage(
        content="世界观已完成",
        tool_call_id="agent_director:delegate_task:0",
        name="delegate_task",
    )

    assert pruned.tool_calls[0]["id"] == response.tool_call_id
    assert pruned.additional_kwargs["tool_calls"][0]["id"] == response.tool_call_id


def test_director_uses_full_history_budget_pipeline_and_emits_checkpoint(monkeypatch) -> None:
    class FakeLLM:
        max_context_tokens = 2048
        max_output_tokens = 256
        model_name = "offline-director"

    class FakeMatchbox:
        @staticmethod
        def get_user_llm(user_id, agent_name):
            return FakeLLM()

    captured = {}

    class FakeGraph:
        def stream(self, initial_state, **kwargs):
            captured["state"] = initial_state
            return iter(())

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    monkeypatch.setattr("agents.director_graph.create_director_graph", lambda: FakeGraph())
    monkeypatch.setattr(
        "agents.director_graph._build_director_prompt_context",
        lambda *args, **kwargs: ("稳定导演前缀", "动态项目现场"),
    )
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))
    monkeypatch.setattr(
        "agents.utility_agent.UtilityAgent.compress_chat_history",
        lambda self, **kwargs: {"summary": "完整早期历史摘要"},
    )
    history = [
        {
            "id": index,
            "role": "user" if index % 2 else "assistant",
            "content": f"历史{index}-" + "x" * 180,
            "metadata": {},
        }
        for index in range(1, 15)
    ]

    events = list(run_director_stream(
        user_id="1",
        project_name="项目",
        user_message="继续创作",
        history=history,
        active_context="编辑区",
        stop_event=threading.Event(),
    ))

    checkpoint_events = [
        event for event in events if event.get("event") == "context_checkpoint_ready"
    ]
    assert len(checkpoint_events) == 1
    assert checkpoint_events[0]["checkpoint"]["metadata"]["compacted_through_message_id"] < history[-1]["id"]
    state = captured["state"]
    assert state["current_user_message"] == "继续创作"
    assert any(
        getattr(message, "type", "") == "system"
        and "完整早期历史摘要" in str(message.content)
        for message in state["messages"]
    )
    assert any(
        getattr(message, "type", "") == "human"
        and "继续创作" in str(message.content)
        for message in state["messages"]
    )
