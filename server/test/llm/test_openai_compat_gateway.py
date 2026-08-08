"""OpenAI 兼容网关的离线协议契约。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def test_tool_schema_required_is_always_an_array() -> None:
    from agents.tools.registry import TOOLS_BY_NAME
    from llm.agen_matchbox.gateway import ChatUniversal

    llm = ChatUniversal(
        model="offline-schema-check",
        api_key="offline-key",
        base_url="https://example.invalid/v1",
    )
    bound = llm.bind_tools(list(TOOLS_BY_NAME.values()))
    payload = llm._get_request_payload(
        [HumanMessage(content="离线检查")],
        **bound.kwargs,
    )

    parameters_by_name = {
        item["function"]["name"]: item["function"]["parameters"]
        for item in payload["tools"]
    }
    assert set(parameters_by_name) == set(TOOLS_BY_NAME)
    assert all(
        isinstance(parameters.get("required"), list)
        for parameters in parameters_by_name.values()
    )
    assert parameters_by_name["list_chapters"]["required"] == []
    assert parameters_by_name["delegate_task"]["required"] == [
        "target_agent",
        "task_description",
    ]


def test_tool_schema_required_is_completed_recursively_without_mutating_input() -> None:
    from llm.agen_matchbox.gateway import normalize_openai_tool_schemas

    tools = [
        {
            "type": "function",
            "function": {
                "name": "inspect_scene",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "properties": {
                                "keyword": {"type": "string"},
                            },
                        }
                    },
                },
            },
        }
    ]

    normalized = normalize_openai_tool_schemas(tools)

    assert "required" not in tools[0]["function"]["parameters"]
    parameters = normalized[0]["function"]["parameters"]
    assert parameters["required"] == []
    assert parameters["properties"]["filters"]["required"] == []


def test_schema_validation_400_is_not_reported_as_content_moderation(monkeypatch) -> None:
    from agents.routes.schemas import format_ai_error

    monkeypatch.setattr("core.request_context.get_current_locale", lambda: "zh-CN")
    raw = (
        "Error code: 400 - Invalid request content: Schema validation failed: "
        '[standard_violation] /required: null is not of type "array"'
    )

    message = format_ai_error(RuntimeError(raw))

    assert "Schema 校验" in message
    assert "内容安全" not in message
    assert raw in message


def test_explicit_content_filter_error_keeps_content_safety_guidance(monkeypatch) -> None:
    from agents.routes.schemas import format_ai_error

    monkeypatch.setattr("core.request_context.get_current_locale", lambda: "zh-CN")

    message = format_ai_error(RuntimeError("400 content_filter policy violation"))

    assert "内容安全策略" in message


def test_generic_400_uses_neutral_invalid_request_guidance(monkeypatch) -> None:
    from agents.routes.schemas import format_ai_error

    monkeypatch.setattr("core.request_context.get_current_locale", lambda: "zh-CN")

    message = format_ai_error(RuntimeError("Error code: 400 - unsupported parameter"))

    assert "请求无效" in message
    assert "内容安全" not in message


def test_gateway_rejects_incomplete_tool_history_before_upstream_request() -> None:
    from llm.agen_matchbox.gateway import ChatUniversal
    from llm.agen_matchbox.tool_protocol import ToolMessageProtocolError

    llm = ChatUniversal(
        model="offline-tool-protocol-check",
        api_key="offline-key",
        base_url="https://example.invalid/v1",
    )
    messages = [
        HumanMessage(content="继续任务"),
        AIMessage(content="", tool_calls=[{
            "id": "call_delegate",
            "name": "delegate_task",
            "args": {},
            "type": "tool_call",
        }]),
        AIMessage(content="", tool_calls=[{
            "id": "call_tracker",
            "name": "work_tracker",
            "args": {},
            "type": "tool_call",
        }]),
        ToolMessage(content="已更新", tool_call_id="call_tracker", name="work_tracker"),
    ]

    with pytest.raises(ToolMessageProtocolError, match="call_delegate"):
        llm._get_request_payload(messages)
