from __future__ import annotations

import asyncio
import json
import queue
import sys
import types

from langchain_core.utils.function_calling import convert_to_openai_tool

from agents.routes.runtime import get_work_trackers_api
from agents.tools.automation import work_tracker
from agents.tools.stream_events import is_tool_result_failure
from agents.prompt_layout import build_current_user_message
from agents.agent_director import DirectorAgent
from agents.communication import SparkBaseAgent, get_tool_event_sink, set_tool_event_sink
from agents.work_tracker import (
    bind_work_tracker_item_for_delegate,
    build_work_tracker_prompt_context,
    complete_bound_work_tracker_item,
    list_work_trackers,
    load_work_tracker,
    update_work_tracker,
)
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


def test_delegate_binding_and_completion_advance_tracker_atomically(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    tracker = update_work_tracker(
        "u-handoff",
        "demo",
        "agent_director",
        overwrite=True,
        items=[
            {"task": "写第一章", "status": "pending"},
            {"task": "写第二章", "status": "pending"},
        ],
    )
    first_id = tracker["items"][0]["id"]
    second_id = tracker["items"][1]["id"]

    bound = bind_work_tracker_item_for_delegate(
        "u-handoff",
        "demo",
        "agent_director",
        requested_item_id=first_id,
    )
    assert bound is not None
    assert bound["id"] == first_id
    assert bound["status"] == "in_progress"

    result = complete_bound_work_tracker_item(
        "u-handoff",
        "demo",
        "agent_director",
        first_id,
    )
    assert result["reconciled"] is True
    assert result["completed_item_id"] == first_id
    assert result["next_item_id"] == second_id
    assert [item["status"] for item in result["tracker"]["items"]] == [
        "completed",
        "in_progress",
    ]

    repeated = complete_bound_work_tracker_item(
        "u-handoff",
        "demo",
        "agent_director",
        first_id,
    )
    assert repeated["reconciled"] is True
    assert [item["status"] for item in repeated["tracker"]["items"]] == [
        "completed",
        "in_progress",
    ]


def test_delegate_binding_only_infers_unambiguous_tracker_item(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    tracker = update_work_tracker(
        "u-infer",
        "demo",
        "agent_director",
        overwrite=True,
        items=[
            {"task": "当前任务", "status": "in_progress"},
            {"task": "后续任务", "status": "pending"},
        ],
    )
    current_id = tracker["items"][0]["id"]

    inferred = bind_work_tracker_item_for_delegate(
        "u-infer",
        "demo",
        "agent_director",
    )
    assert inferred is not None
    assert inferred["id"] == current_id

    update_work_tracker(
        "u-infer",
        "demo",
        "agent_director",
        operations=[{
            "operation": "set_status",
            "item_id": tracker["items"][1]["id"],
            "status": "in_progress",
        }],
    )
    assert bind_work_tracker_item_for_delegate(
        "u-infer",
        "demo",
        "agent_director",
    ) is None


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
            "overwrite": True,
            "summary": "真实工具调用",
            "items": [{"task": "第一步", "status": "in_progress", "priority": "high"}],
        }))
        item_id = created["items"][0]["id"]
        completed = json.loads(work_tracker.invoke({
            "operations": [{
                "operation": "set_status",
                "item_ids": [item_id],
                "status": "completed",
            }],
        }))
    finally:
        current_agent_id.reset(token)

    assert completed["items"][0]["status"] == "completed"


def test_set_status_rejects_nested_item_and_top_level_notes_with_actionable_error() -> None:
    try:
        work_tracker.args_schema.model_validate({
            "operations": [{
                "operation": "set_status",
                "item_id": "task_1",
                "status": "completed",
                "notes": "错误位置",
            }],
        })
    except ValueError as exc:
        message = str(exc)
        assert "set_status 只允许" in message
        assert "edit" in message
    else:
        raise AssertionError("set_status 不应接受顶层 notes")

    try:
        work_tracker.args_schema.model_validate({
            "operations": [{
                "operation": "set_status",
                "item_id": "task_1",
                "status": "completed",
                "item": {"notes": "错误位置"},
            }],
        })
    except ValueError as exc:
        assert "set_status 不使用 item" in str(exc)
    else:
        raise AssertionError("set_status 不应接受 item")


def test_edit_rejects_top_level_notes_with_actionable_error() -> None:
    try:
        work_tracker.args_schema.model_validate({
            "operations": [{
                "operation": "edit",
                "item_id": "task_1",
                "item": {"priority": "high"},
                "notes": "错误位置",
            }],
        })
    except ValueError as exc:
        assert "item.notes" in str(exc)
    else:
        raise AssertionError("edit 不应接受顶层 notes")


def test_work_tracker_schema_is_update_only_and_describes_nested_item() -> None:
    schema = work_tracker.args_schema.model_json_schema()

    assert "action" not in schema["properties"]
    assert set(schema["properties"]["overwrite"]) >= {"default", "description"}
    operation_ref = schema["$defs"]["WorkTrackerOperationInput"]
    assert set(operation_ref["properties"]["operation"]["enum"]) == {
        "add",
        "insert",
        "edit",
        "delete",
        "set_status",
    }
    assert "WorkTrackerOperationItemInput" in schema["$defs"]
    assert "set_status" in operation_ref["properties"]["status"]["description"]
    assert "item.notes" in operation_ref["properties"]["item"]["description"]


def test_openai_tool_schema_preserves_work_tracker_field_guidance() -> None:
    parameters = convert_to_openai_tool(work_tracker)["function"]["parameters"]

    assert "action" not in parameters["properties"]
    operations = parameters["properties"]["operations"]["anyOf"][0]["items"]
    assert set(operations["properties"]["operation"]["enum"]) == {
        "add",
        "insert",
        "edit",
        "delete",
        "set_status",
    }
    item = operations["properties"]["item"]["anyOf"][0]
    assert item["properties"]["task"]["description"]
    assert item["properties"]["notes"]["description"]
    assert "set_status" in operations["properties"]["status"]["description"]
    assert "item.notes" in operations["properties"]["item"]["description"]


def test_work_tracker_schema_shows_independent_complete_status_operations() -> None:
    schema = work_tracker.args_schema.model_json_schema()
    operation_ref = schema["$defs"]["WorkTrackerOperationInput"]
    operation_description = operation_ref["properties"]["operation"]["description"]
    status_description = operation_ref["properties"]["status"]["description"]
    operations_description = schema["properties"]["operations"]["description"]

    assert "每一项都必须独立完整" in operation_description
    assert "每个 set_status 都必须同时提供 item_id 或 item_ids" in status_description
    assert "字段不会从其他元素继承" in operations_description
    assert schema["properties"]["operations"]["examples"] == [[
        {"operation": "set_status", "item_id": "task_x", "status": "completed"},
        {"operation": "set_status", "item_id": "task_y", "status": "in_progress"},
    ]]


def test_work_tracker_validation_error_identifies_operation_index(monkeypatch) -> None:
    agent = SparkBaseAgent("agent_director", user_id="validation-test")
    events = queue.Queue()
    previous_sink = get_tool_event_sink()
    set_tool_event_sink(events)
    # 该测试只验证统一执行器的错误回执；避免加载其他正在独立注册的工具模块。
    registry_stub = types.SimpleNamespace(TOOLS_BY_NAME={"work_tracker": work_tracker})
    monkeypatch.setitem(sys.modules, "agents.tools.registry", registry_stub)
    args = {
        "operations": [
            {"operation": "set_status", "status": "completed"},
            {"operation": "set_status", "item_id": "task_11dbca6903", "status": "in_progress"},
        ],
    }

    try:
        result = agent._execute_tool_calls([{
            "raw": {
                "id": "call_tracker_validation",
                "name": "work_tracker",
                "args": args,
            },
            "name": "work_tracker",
            "args": args,
            "call_id": "call_tracker_validation",
        }])
    finally:
        set_tool_event_sink(previous_sink)

    assert "operations[0]" in result
    assert "缺少 item_id 或 item_ids" in result
    assert "不能继承其他元素" in result
    assert result.startswith("任务板更新失败：")
    assert is_tool_result_failure("work_tracker", result) is True
    failure_event = next(event for event in list(events.queue) if event.get("event") == "tool_exec_failed")
    assert failure_event["tool_error"] == result
    assert failure_event["message"].startswith("任务板更新失败：")


def test_work_tracker_snapshot_is_appended_to_user_message_tail(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    tracker = update_work_tracker(
        "u6",
        "demo",
        "agent_director",
        overwrite=True,
        summary="完成全流程",
        items=[{"task": "生成大纲", "status": "in_progress"}],
    )

    runtime_tail = build_work_tracker_prompt_context("u6", "demo", "agent_director")
    message = build_current_user_message(
        user_message="继续推进",
        active_context="当前已有世界观",
        runtime_tail=runtime_tail,
    )

    assert tracker["items"][0]["id"] in runtime_tail
    assert "无需调用工具读取" in runtime_tail
    assert message.endswith(runtime_tail)
    assert message.index("### 本轮用户请求") < message.index("### 当前进度板（系统自动注入）")


def test_agent_runtime_tail_keeps_tracker_out_of_system_prefix(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    update_work_tracker(
        "u7",
        "demo",
        "agent_director",
        overwrite=True,
        items=[{"task": "生成角色", "status": "pending"}],
    )
    agent = DirectorAgent(user_id="u7", project_name="demo")

    system_prompt = agent._build_tool_system_prompt("固定系统规则")
    runtime_tail = agent._build_runtime_tail()

    assert "当前进度板（系统自动注入）" not in system_prompt
    assert "当前进度板（系统自动注入）" in runtime_tail


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
