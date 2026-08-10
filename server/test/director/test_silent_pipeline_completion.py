from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.communication import SparkBaseAgent, is_pipeline_tool_result_failure
from agents.director_graph import sub_agent_node
from agents.tools.pipeline import PIPELINE_COMPLETION_MARKER
from agents.tools.registry import TOOLS_BY_NAME, get_tools_for_agent


def _tool_turn(*tool_names: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": tool_name,
                "args": (
                    {"overwrite_content": "# 新世界观"}
                    if tool_name == "rewrite_worldview"
                    else {}
                ),
                "id": f"call-{index}",
                "type": "tool_call",
            }
            for index, tool_name in enumerate(tool_names)
        ],
    )


def _run_agent_stream(
    monkeypatch,
    responses: list[AIMessage],
    tool_results: list[str],
    *,
    stop_after_pipeline_completion: bool,
) -> tuple[list[dict], dict]:
    state = {
        "turns": 0,
        "tool_calls": 0,
        "bound_tools": [],
    }
    pending_responses = list(responses)
    pending_tool_results = list(tool_results)

    class FakeLlm:
        def bind_tools(self, tools):
            state["bound_tools"] = [tool.name for tool in tools]
            return self

    class FakeMatchbox:
        def get_user_llm(self, *_args, **_kwargs):
            return FakeLlm()

    def fake_stream_model_turn(*_args, **_kwargs):
        state["turns"] += 1
        yield pending_responses.pop(0)

    def fake_budget_stream(_func, **_kwargs):
        if False:
            yield None
        return SimpleNamespace(
            messages=[SystemMessage(content="系统"), HumanMessage(content="任务")],
            checkpoint=None,
        )

    def fake_execute(_self, _tool_calls):
        state["tool_calls"] += 1
        return pending_tool_results.pop(0)

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    monkeypatch.setattr("agents.communication.stream_model_turn_with_retry", fake_stream_model_turn)
    monkeypatch.setattr("agents.context_budget.stream_context_budget_events", fake_budget_stream)
    monkeypatch.setattr(SparkBaseAgent, "_execute_tool_calls", fake_execute)

    agent = SparkBaseAgent(
        "agent_lorebook",
        user_id="pipeline-test",
        project_name="demo",
    )
    events = list(agent.chat_stream(
        "生成世界观",
        active_context="completion_mode: silent_continue",
        skip_tool_confirmation=True,
        stop_after_pipeline_completion=stop_after_pipeline_completion,
    ))
    return events, state


def test_pipeline_control_tool_is_only_bound_in_pipeline_mode() -> None:
    normal_names = {tool.name for tool in get_tools_for_agent("agent_lorebook")}
    pipeline_names = {
        tool.name
        for tool in get_tools_for_agent("agent_lorebook", pipeline_mode=True)
    }

    assert "complete_pipeline_step" not in normal_names
    assert "complete_pipeline_step" in pipeline_names
    assert "complete_pipeline_step" not in {
        tool.name
        for tool in get_tools_for_agent("agent_director", pipeline_mode=True)
    }
    assert TOOLS_BY_NAME["complete_pipeline_step"].invoke({}) == PIPELINE_COMPLETION_MARKER


def test_pipeline_failure_guard_only_broadens_persist_tool_detection() -> None:
    assert is_pipeline_tool_result_failure(
        "rewrite_worldview",
        "重写世界观失败：内容为空。",
    ) is True
    assert is_pipeline_tool_result_failure(
        "search_project",
        "未找到匹配的项目内容。",
    ) is False


def test_silent_pipeline_returns_tool_receipt_without_summary_turn(monkeypatch) -> None:
    events, state = _run_agent_stream(
        monkeypatch,
        [_tool_turn("rewrite_worldview", "complete_pipeline_step")],
        ["已使用工具参数中的完整文本覆盖世界观。", PIPELINE_COMPLETION_MARKER],
        stop_after_pipeline_completion=True,
    )

    completion_events = [
        event for event in events
        if event.get("event") == "pipeline_step_completed"
    ]
    assert state["turns"] == 1
    assert state["tool_calls"] == 2
    assert "complete_pipeline_step" in state["bound_tools"]
    assert len(completion_events) == 1
    assert "rewrite_worldview" in completion_events[0]["receipt"]
    assert "项目真相源已更新" in completion_events[0]["receipt"]
    assert not any(
        event.get("tool_name") == "complete_pipeline_step"
        for event in events
    )


def test_sync_pipeline_uses_the_same_single_turn_completion_protocol(monkeypatch) -> None:
    state = {"invokes": 0, "tool_results": [
        "已使用工具参数中的完整文本覆盖世界观。",
        PIPELINE_COMPLETION_MARKER,
    ]}

    class FakeLlm:
        def bind_tools(self, tools):
            assert "complete_pipeline_step" in {tool.name for tool in tools}
            return self

        def invoke(self, _messages):
            state["invokes"] += 1
            return _tool_turn("rewrite_worldview", "complete_pipeline_step")

    class FakeMatchbox:
        def get_user_llm(self, *_args, **_kwargs):
            return FakeLlm()

    def fake_prepare_budget(**_kwargs):
        return SimpleNamespace(
            messages=[SystemMessage(content="系统"), HumanMessage(content="任务")],
            checkpoint=None,
        )

    def fake_execute(_self, _tool_calls):
        return state["tool_results"].pop(0)

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: FakeMatchbox())
    monkeypatch.setattr(
        "agents.context_budget.prepare_chat_messages_with_budget",
        fake_prepare_budget,
    )
    monkeypatch.setattr(SparkBaseAgent, "_execute_tool_calls", fake_execute)

    agent = SparkBaseAgent(
        "agent_lorebook",
        user_id="sync-pipeline-test",
        project_name="demo",
    )
    result = agent.chat(
        "生成世界观",
        active_context="completion_mode: silent_continue",
        skip_tool_confirmation=True,
        stop_after_pipeline_completion=True,
    )

    assert state["invokes"] == 1
    assert "rewrite_worldview" in result
    assert "项目真相源已更新" in result


def test_silent_pipeline_does_not_finish_when_write_tool_failed(monkeypatch) -> None:
    events, state = _run_agent_stream(
        monkeypatch,
        [
            _tool_turn("rewrite_worldview", "complete_pipeline_step"),
            _tool_turn("rewrite_worldview", "complete_pipeline_step"),
        ],
        [
            "重写世界观失败：写入内容为空。",
            PIPELINE_COMPLETION_MARKER,
            "已使用工具参数中的完整文本覆盖世界观。",
            PIPELINE_COMPLETION_MARKER,
        ],
        stop_after_pipeline_completion=True,
    )

    assert state["turns"] == 2
    assert state["tool_calls"] == 4
    assert sum(
        event.get("event") == "pipeline_step_completed"
        for event in events
    ) == 1
    assert any(event.get("event") == "tool_exec_failed" for event in events)


def test_silent_pipeline_requires_control_tool_acknowledgement(monkeypatch) -> None:
    events, state = _run_agent_stream(
        monkeypatch,
        [
            _tool_turn("rewrite_worldview", "complete_pipeline_step"),
            _tool_turn("complete_pipeline_step"),
        ],
        [
            "已使用工具参数中的完整文本覆盖世界观。",
            "工具 complete_pipeline_step 执行失败：参数格式错误。",
            PIPELINE_COMPLETION_MARKER,
        ],
        stop_after_pipeline_completion=True,
    )

    assert state["turns"] == 2
    assert sum(
        event.get("event") == "pipeline_step_completed"
        for event in events
    ) == 1


def test_non_silent_pipeline_keeps_natural_language_summary_turn(monkeypatch) -> None:
    events, state = _run_agent_stream(
        monkeypatch,
        [
            _tool_turn("rewrite_worldview", "complete_pipeline_step"),
            AIMessage(content="已完成世界观更新并核对了创作约束。"),
        ],
        ["已使用工具参数中的完整文本覆盖世界观。", PIPELINE_COMPLETION_MARKER],
        stop_after_pipeline_completion=False,
    )

    assert state["turns"] == 2
    assert not any(
        event.get("event") == "pipeline_step_completed"
        for event in events
    )
    assert "已完成世界观更新" in "".join(
        str(event.get("text") or "")
        for event in events
        if event.get("event") == "assistant_delta"
    )


def test_director_consumes_internal_pipeline_receipt(monkeypatch) -> None:
    observed_kwargs = {}
    receipt = (
        "[agent_lorebook] 流水线步骤已完成，项目真相源已更新。\n"
        "- rewrite_worldview：已成功保存世界观。"
    )

    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            observed_kwargs.update(kwargs)
            yield {
                "event": "pipeline_step_completed",
                "source_agent": "agent_lorebook",
                "receipt": receipt,
            }

    streamed_events = []
    monkeypatch.setattr(
        "agents.director_graph._ensure_graph_agent_registered",
        lambda *args, **kwargs: FakeSubAgent(),
    )
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: streamed_events.append)
    monkeypatch.setattr(
        "agents.director_graph.transfer_baton",
        lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"},
    )

    result = sub_agent_node({
        "user_id": "u1",
        "project_name": "p1",
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成世界观",
            "completion_mode": "silent_continue",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": "not_required",
            "skip_tool_confirmation": True,
        },
        "baton_holder": "agent_lorebook",
        "active_context": "",
        "messages": [HumanMessage(content="开始")],
        "stop_event": None,
    })

    assert observed_kwargs["stop_after_pipeline_completion"] is True
    assert result["sub_agent_result"] == receipt
    assert result["baton_holder"] == "agent_director"
    assert not any(
        event.get("event") == "pipeline_step_completed"
        for event in streamed_events
    )
