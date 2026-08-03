"""
守护对象：聊天与导演共用的工具调用消息历史协议。

本测试禁止调用真实模型或外部服务。
"""

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.messages.utils import convert_to_openai_messages

from agents.communication import SparkBaseAgent


def _agent() -> SparkBaseAgent:
    return SparkBaseAgent("agent_director", user_id="tool-history-test", project_name="demo")


def test_missing_or_duplicate_call_ids_are_replaced_with_unique_ids() -> None:
    prepared = _agent()._prepare_tool_specs_for_execution([
        {
            "raw": {"id": "", "name": "work_tracker", "args": {"operations": []}},
            "name": "work_tracker",
            "args": {"operations": []},
            "index": 0,
        },
        {
            "raw": {"id": "same", "name": "list_files", "args": {}},
            "name": "list_files",
            "args": {},
            "index": 1,
        },
        {
            "raw": {"id": "same", "name": "read_file", "args": {"path": "outline.md"}},
            "name": "read_file",
            "args": {"path": "outline.md"},
            "index": 2,
        },
    ])

    call_ids = [spec["call_id"] for spec in prepared]
    assert all(call_ids)
    assert len(call_ids) == len(set(call_ids))
    assert call_ids[1] == "same"
    assert all(spec["raw"]["id"] == spec["call_id"] for spec in prepared)


def test_rebuilt_history_declares_only_executed_calls_with_matching_tool_results() -> None:
    agent = _agent()
    original = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "",
                "name": "work_tracker",
                "args": {"operations": []},
                "type": "tool_call",
            },
            {
                "id": "call_not_executed",
                "name": "delegate_task",
                "args": {"target_agent": "agent_muse"},
                "type": "tool_call",
            },
        ],
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "work_tracker", "arguments": "{}"},
                },
                {
                    "id": "call_not_executed",
                    "type": "function",
                    "function": {"name": "delegate_task", "arguments": "{}"},
                },
            ]
        },
    )
    executed = agent._prepare_tool_specs_for_execution([
        {
            "raw": original.tool_calls[0],
            "name": "work_tracker",
            "args": {"operations": []},
            "index": 0,
        }
    ])
    assistant_message = agent._build_tool_history_message(original, executed)
    tool_message = ToolMessage(
        content="任务板已更新",
        tool_call_id=executed[0]["call_id"],
        name="work_tracker",
    )

    payload = convert_to_openai_messages([assistant_message, tool_message])
    declared_ids = [call["id"] for call in payload[0]["tool_calls"]]

    assert declared_ids == [payload[1]["tool_call_id"]]
    assert "call_not_executed" not in declared_ids
    assert "tool_calls" not in assistant_message.additional_kwargs

