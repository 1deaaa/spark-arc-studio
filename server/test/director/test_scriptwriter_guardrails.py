from __future__ import annotations

import json
import queue
import threading

from langchain_core.messages import AIMessage, HumanMessage
import pytest

from agents.communication import (
    HANDOFF_CONFIRMATION_NOT_REQUIRED,
    get_tool_event_sink,
    reset_tool_event_sink,
    set_tool_event_sink,
)
from agents.director_graph import route_after_sub_agent, sub_agent_node
from agents.routes.auto_write_state import begin_auto_write_run


def test_director_returns_to_self_when_scriptwriter_did_not_persist() -> None:
    state = {
        "pending_delegate": {
            "target_agent": "agent_scriptwriter",
            "delivery_mode": "direct_to_user",
            "completion_mode": "report_to_user",
        },
        "sub_agent_result": "[agent_scriptwriter] Execution failed:\nScriptwriter 未完成落盘：本轮只生成了正文草稿，但没有调用 create_or_rewrite_script。",
        "stop_event": threading.Event(),
    }

    assert route_after_sub_agent(state) == "director"


def test_begin_auto_write_run_persists_from_director(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_31" / "projects" / "demo"
    project_path.mkdir(parents=True)

    state = begin_auto_write_run(
        "31",
        "demo",
        mode="continuous_write",
        export_format="arc",
        start_chapter_index=0,
        start_scene_index=0,
        total_chapters=3,
        total_scenes=9,
        from_director=True,
    )

    assert state["fromDirector"] is True


def test_sub_agent_node_hides_scriptwriter_draft_without_persist(monkeypatch) -> None:
    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            yield {"event": "assistant_delta", "text": "这里是一大段未保存正文"}

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: FakeSubAgent())
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: None)
    monkeypatch.setattr("agents.director_graph.transfer_baton", lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"})

    state = {
        "user_id": "u1",
        "project_name": "p1",
        "pending_delegate": {
            "target_agent": "agent_scriptwriter",
            "task_description": "写第1章第1场",
            "delivery_mode": "direct_to_user",
            "completion_mode": "report_to_user",
            "return_to": "agent_director",
            "grant_baton_to": "agent_scriptwriter",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
        "baton_holder": "agent_scriptwriter",
        "active_context": "",
        "messages": [HumanMessage(content="开始")],
        "stop_event": threading.Event(),
    }

    result = sub_agent_node(state)

    assert "未完成落盘" in result["sub_agent_result"]
    assert result["baton_holder"] == "agent_director"


@pytest.mark.parametrize("fail", [False, True])
def test_sub_agent_node_restores_outer_tool_event_sink(monkeypatch, fail: bool) -> None:
    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            if fail:
                raise RuntimeError("子 Agent 执行失败")
            yield {"event": "assistant_delta", "text": "已完成"}

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: FakeSubAgent())
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: None)
    monkeypatch.setattr("agents.director_graph.transfer_baton", lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"})
    state = {
        "user_id": "u1",
        "project_name": "p1",
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成世界观",
            "delivery_mode": "return_to_director",
            "completion_mode": "return_to_director",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
        "baton_holder": "agent_lorebook",
        "active_context": "",
        "messages": [HumanMessage(content="开始")],
        "stop_event": threading.Event(),
    }
    outer_sink = queue.Queue()
    outer_token = set_tool_event_sink(outer_sink)

    try:
        if fail:
            with pytest.raises(RuntimeError, match="子 Agent 执行失败"):
                sub_agent_node(state)
        else:
            sub_agent_node(state)
        assert get_tool_event_sink() is outer_sink
    finally:
        reset_tool_event_sink(outer_token)


def test_repeated_delegation_reuses_append_only_sub_agent_history(monkeypatch) -> None:
    calls = []

    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            calls.append(kwargs)
            prior = list(kwargs.get("prepared_history_messages") or [])
            current = HumanMessage(content=f"PROMPT:{kwargs['user_message']}")
            response = AIMessage(content=f"RESULT:{kwargs['user_message']}")
            kwargs["conversation_recorder"]([*prior, current, response])
            yield {"event": "assistant_delta", "text": response.content}

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: FakeSubAgent())
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: None)
    monkeypatch.setattr("agents.director_graph.transfer_baton", lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"})

    base_state = {
        "user_id": "u-history",
        "project_name": "p-history",
        "baton_holder": "agent_lorebook",
        "active_context": "",
        "messages": [HumanMessage(content="开始")],
        "stop_event": threading.Event(),
        "workflow_tools": {"agent_lorebook": [object()]},
        "handoff_histories": {},
    }
    first = sub_agent_node({
        **base_state,
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成世界观",
            "completion_mode": "return_to_director",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
    })
    second = sub_agent_node({
        **base_state,
        "handoff_histories": first["handoff_histories"],
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成角色",
            "completion_mode": "return_to_director",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
    })

    first_history = first["handoff_histories"]["agent_lorebook"]
    second_history = second["handoff_histories"]["agent_lorebook"]
    assert calls[0]["prepared_history_messages"] is None
    assert calls[1]["prepared_history_messages"] == first_history
    assert second_history[: len(first_history)] == first_history
    assert second_history[-2].content == "PROMPT:生成角色"


def test_nested_sub_agent_checkpoint_does_not_escape_to_director_stream(monkeypatch) -> None:
    events = []

    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            kwargs["conversation_recorder"]([HumanMessage(content="任务"), AIMessage(content="完成")])
            yield {"event": "context_checkpoint_ready", "checkpoint": {"metadata": {"agent_id": "agent_lorebook"}}}
            yield {"event": "context_compaction_finished", "source_agent": "agent_lorebook"}
            yield {"event": "assistant_delta", "text": "完成"}

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: FakeSubAgent())
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: events.append)
    monkeypatch.setattr("agents.director_graph.transfer_baton", lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"})

    result = sub_agent_node({
        "user_id": "u-nested-checkpoint",
        "project_name": "p-nested-checkpoint",
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成世界观",
            "completion_mode": "return_to_director",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
        "baton_holder": "agent_lorebook",
        "active_context": "",
        "stop_event": threading.Event(),
        "workflow_tools": {"agent_lorebook": [object()]},
        "handoff_histories": {},
    })

    assert result["sub_agent_result"]
    assert not any(event.get("event") == "context_checkpoint_ready" for event in events)
    assert any(event.get("event") == "context_compaction_finished" for event in events)


def test_sub_agent_returns_to_director_when_tracker_has_open_items(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_u1" / "projects" / "p1"
    project_path.mkdir(parents=True)
    (project_path / "work_tracker_agent_director.json").write_text(
        json.dumps({
            "summary": "全流程创作",
            "items": [
                {"task": "生成世界观", "status": "completed", "priority": "high", "notes": ""},
                {"task": "生成角色", "status": "pending", "priority": "high", "notes": ""},
            ],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    class FakeSubAgent:
        def chat_stream(self, *args, **kwargs):
            yield {"event": "assistant_delta", "text": "世界观已完成"}

    monkeypatch.setattr("agents.director_graph._ensure_graph_agent_registered", lambda *args, **kwargs: FakeSubAgent())
    monkeypatch.setattr("agents.context_provider.get_agent_context", lambda *args, **kwargs: "")
    monkeypatch.setattr("agents.director_graph.get_stream_writer", lambda: None)
    monkeypatch.setattr("agents.director_graph.transfer_baton", lambda *args, **kwargs: {"status": "ok", "baton_holder": "agent_director"})

    state = {
        "user_id": "u1",
        "project_name": "p1",
        "pending_delegate": {
            "target_agent": "agent_lorebook",
            "task_description": "生成世界观",
            "delivery_mode": "direct_to_user",
            "completion_mode": "report_to_user",
            "return_to": "agent_director",
            "grant_baton_to": "agent_lorebook",
            "user_confirmation_state": HANDOFF_CONFIRMATION_NOT_REQUIRED,
            "skip_tool_confirmation": True,
        },
        "baton_holder": "agent_lorebook",
        "active_context": "",
        "messages": [HumanMessage(content="开始")],
        "stop_event": threading.Event(),
    }

    result = sub_agent_node(state)

    assert result["force_return_to_director"] is True
    assert result["baton_holder"] == "agent_director"
    assert route_after_sub_agent({**state, **result}) == "director"
