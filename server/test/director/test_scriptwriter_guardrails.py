from __future__ import annotations

import json
import threading

from langchain_core.messages import HumanMessage

from agents.communication import (
    HANDOFF_CONFIRMATION_NOT_REQUIRED,
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
