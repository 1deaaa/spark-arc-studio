from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from agents.director_graph import _retain_only_pending_delegate_tool_call


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
