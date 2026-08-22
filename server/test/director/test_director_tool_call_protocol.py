from __future__ import annotations

import threading

from langchain_core.messages import AIMessage, ToolMessage

from agents.director_graph import (
    _build_director_message_update,
    _director_tracker_update_required,
    _is_tracker_progress_update,
    _tracker_update_required_message,
    route_after_director,
    run_director_stream,
)
from agents.work_tracker import update_work_tracker
from agents.communication import SparkBaseAgent
from llm.agen_matchbox.tool_protocol import validate_tool_message_history


def test_tracker_progress_update_requires_explicit_overwrite_or_operations() -> None:
    assert _is_tracker_progress_update(
        "work_tracker",
        {
            "overwrite": True,
            "items": [
                {"task": "生成梗概", "status": "completed"},
                {"task": "生成节拍", "status": "in_progress"},
            ],
        },
        "共 2 个任务",
    ) is True
    assert _is_tracker_progress_update(
        "work_tracker",
        {
            "operations": [
                {"operation": "set_status", "item_id": "task_1", "status": "completed"},
            ],
        },
        '{"items": []}',
    ) is True
    assert _is_tracker_progress_update(
        "work_tracker",
        {
            "items": [{"task": "不允许隐式覆盖", "status": "completed"}],
        },
        "共 1 个任务",
    ) is False
    assert _is_tracker_progress_update(
        "work_tracker",
        {},
        "共 2 个任务",
    ) is False
    assert _is_tracker_progress_update(
        "work_tracker",
        {},
        "共 2 个任务",
    ) is False


def test_progress_protocol_error_returns_to_director() -> None:
    state = {
        "pending_delegate": None,
        "force_return_to_director": True,
        "messages": [
            ToolMessage(
                content="请先更新任务板再委派",
                tool_call_id="call_delegate",
                name="delegate_task",
            )
        ],
    }

    assert route_after_director(state) == "director"


def test_director_stops_model_loop_after_background_auto_write_starts() -> None:
    state = {
        "pending_delegate": None,
        "force_return_to_director": False,
        "background_task_started": True,
        "messages": [
            ToolMessage(
                content="自动写作任务已在后台启动",
                tool_call_id="call_auto_write",
                name="trigger_auto_write",
            )
        ],
    }

    assert route_after_director(state) == "__end__"


def test_tracker_protocol_keeps_failed_or_unsatisfactory_task_retryable() -> None:
    message = _tracker_update_required_message()

    assert "成功才标为 completed" in message
    assert "质量不达标时保持 in_progress" in message
    assert "notes 记录失败原因和重做要求" in message
    assert "重新委派原专家重做" in message
    assert "不会终止当前流程" in message


def test_reconciled_handoff_does_not_require_duplicate_tracker_tool_call(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    update_work_tracker(
        "u-reconciled",
        "demo",
        "agent_director",
        overwrite=True,
        items=[
            {"task": "已完成步骤", "status": "completed"},
            {"task": "后续步骤", "status": "in_progress"},
        ],
    )

    assert _director_tracker_update_required(
        "u-reconciled",
        "demo",
        "专家已回交",
        True,
    ) is False
    assert _director_tracker_update_required(
        "u-reconciled",
        "demo",
        "专家已回交",
        False,
    ) is True


def test_sub_agent_result_is_persisted_before_tracker_turn() -> None:
    director = SparkBaseAgent(
        "agent_director",
        user_id="tool-history-test",
        project_name="demo",
    )
    previous_state = [
        AIMessage(content="", tool_calls=[{
            "id": "call_delegate",
            "name": "delegate_task",
            "args": {},
            "type": "tool_call",
        }]),
    ]
    handoff_result = ToolMessage(
        content="专家已回交",
        tool_call_id="call_delegate",
        name="delegate_task",
    )
    tracker_response = AIMessage(content="", tool_calls=[{
        "id": "call_tracker",
        "name": "work_tracker",
        "args": {"operations": []},
        "type": "tool_call",
    }])
    tracker_specs = director._prepare_tool_specs_for_execution(
        director._extract_tool_call_specs_from_message(tracker_response)
    )

    update = _build_director_message_update(
        persisted_prefix=[handoff_result],
        director=director,
        response=tracker_response,
        tool_specs=tracker_specs,
        tool_results=[("call_tracker", "work_tracker", "任务板已更新")],
    )
    next_state = previous_state + update

    assert update[0] is handoff_result
    validate_tool_message_history(next_state)


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
    assert not any(
        getattr(message, "type", "") == "human"
        and "继续创作" in str(message.content)
        for message in state["messages"]
    )
    assert state["director_runtime_message"] == ""
