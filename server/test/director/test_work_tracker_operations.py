from __future__ import annotations

import asyncio
import json

from agents.routes.runtime import get_work_trackers_api
from agents.tools.automation import work_tracker
from agents.work_tracker import list_work_trackers, load_work_tracker, update_work_tracker
from core.request_context import current_agent_id, set_current_context


def test_work_tracker_supports_incremental_batch_operations(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    initial = update_work_tracker(
        "u1",
        "demo",
        "agent_director",
        overwrite=True,
        summary="完成项目",
        items=[
            {"task": "世界观", "status": "in_progress", "priority": "high", "notes": ""},
            {"task": "角色", "status": "pending", "priority": "medium", "notes": ""},
        ],
    )
    world_id = initial["items"][0]["id"]
    character_id = initial["items"][1]["id"]

    updated = update_work_tracker(
        "u1",
        "demo",
        "agent_director",
        operations=[
            {"operation": "set_status", "item_ids": [world_id, character_id], "status": "completed"},
            {
                "operation": "insert",
                "position": 2,
                "item": {"task": "节拍表", "status": "in_progress", "priority": "high", "notes": ""},
            },
            {
                "operation": "edit",
                "item_id": world_id,
                "item": {"id": "task_illegal_replacement", "notes": "已通过审核"},
            },
        ],
    )

    assert [item["task"] for item in updated["items"]] == ["世界观", "节拍表", "角色"]
    assert updated["items"][0]["status"] == "completed"
    assert updated["items"][0]["id"] == world_id
    assert updated["items"][0]["notes"] == "已通过审核"
    assert updated["items"][2]["status"] == "completed"


def test_delete_is_distinct_from_completed_and_persists_board(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    initial = update_work_tracker(
        "u2",
        "demo",
        "agent_scriptwriter",
        overwrite=True,
        items=[
            {"task": "保留完成记录", "status": "pending"},
            {"task": "用户取消的任务", "status": "pending"},
        ],
    )
    completed_id = initial["items"][0]["id"]
    deleted_id = initial["items"][1]["id"]

    result = update_work_tracker(
        "u2",
        "demo",
        "agent_scriptwriter",
        operations=[
            {"operation": "set_status", "item_id": completed_id, "status": "completed"},
            {"operation": "delete", "item_id": deleted_id},
        ],
    )

    assert [(item["id"], item["status"]) for item in result["items"]] == [(completed_id, "completed")]
    assert load_work_tracker("u2", "demo", "agent_scriptwriter")["items"][0]["id"] == completed_id
    assert list_work_trackers("u2", "demo", ["agent_scriptwriter"])["agent_scriptwriter"]["items"]


def test_incremental_items_require_explicit_overwrite(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    try:
        update_work_tracker(
            "u3",
            "demo",
            "agent_director",
            items=[{"task": "不应隐式覆盖"}],
        )
    except ValueError as exc:
        assert "overwrite=true" in str(exc)
    else:
        raise AssertionError("未显式 overwrite 时不应接受完整 items")


def test_langchain_tool_accepts_structured_items_and_operations(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    set_current_context("u4", "demo")
    token = current_agent_id.set("agent_director")
    try:
        created = json.loads(work_tracker.invoke({
            "action": "update",
            "overwrite": True,
            "summary": "真实工具调用",
            "items": [{"task": "第一步", "status": "in_progress", "priority": "high"}],
        }))
        item_id = created["items"][0]["id"]
        completed = json.loads(work_tracker.invoke({
            "action": "update",
            "operations": [{
                "operation": "set_status",
                "item_ids": [item_id],
                "status": "completed",
            }],
        }))
    finally:
        current_agent_id.reset(token)

    assert completed["items"][0]["status"] == "completed"


def test_runtime_api_returns_persisted_agent_boards(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    update_work_tracker(
        "u5",
        "demo",
        "agent_director",
        overwrite=True,
        items=[{"task": "导演任务", "status": "in_progress"}],
    )
    update_work_tracker(
        "u5",
        "demo",
        "agent_scriptwriter",
        overwrite=True,
        items=[{"task": "编剧任务", "status": "completed"}],
    )

    payload = asyncio.run(get_work_trackers_api(projectName="demo", user={"user_id": "u5"}))

    assert payload["projectName"] == "demo"
    assert set(payload["trackers"]) >= {"agent_director", "agent_scriptwriter"}
    assert payload["trackers"]["agent_director"]["items"][0]["task"] == "导演任务"
