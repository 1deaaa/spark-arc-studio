"""工具参数结构兼容、事件详情和聊天轨迹回放的回归测试。"""

import pytest
from pydantic import ValidationError

from agents.routes.chat_persistence import ChatStreamAccumulator
from agents.tools.delegation import delegate_task
from agents.tools.stream_events import build_tool_stream_event, is_tool_result_failure
from agents.tools.automation import work_tracker
from llm.agen_matchbox.tool_protocol import (
    normalize_tool_args,
    prepare_tool_specs_for_execution,
)


def test_work_tracker_nested_json_strings_are_normalized_by_schema() -> None:
    raw_args = {
        "overwrite": "true",
        "items": '[{"task":"搭建冲突","status":"pending"}]',
        "contract": '{"required_scene_fields":["goal","turn"]}',
    }

    normalized = normalize_tool_args(raw_args, tool=work_tracker)

    assert normalized["items"] == [{"task": "搭建冲突", "status": "pending"}]
    assert normalized["contract"] == {"required_scene_fields": ["goal", "turn"]}
    assert normalized["overwrite"] == "true"

    validated = work_tracker.args_schema.model_validate(normalized)
    assert validated.items[0].task == "搭建冲突"

    operations = normalize_tool_args({
        "operations": '[{"operation":"add","item":"{\\"task\\":\\"补充场景\\"}"}]',
    }, tool=work_tracker)
    assert operations["operations"][0]["item"] == {"task": "补充场景"}


def test_prepare_specs_writes_normalized_args_back_to_history_spec() -> None:
    specs = prepare_tool_specs_for_execution(
        [{
            "raw": {
                "id": "call_tracker",
                "name": "work_tracker",
                "args": {
                    "operations": '[{"operation":"set_status","item_id":"item-1","status":"completed"}]',
                },
            },
            "name": "work_tracker",
            "args": {
                "operations": '[{"operation":"set_status","item_id":"item-1","status":"completed"}]',
            },
            "index": 0,
        }],
        tool_lookup={"work_tracker": work_tracker},
    )

    assert specs[0]["args"]["operations"][0]["operation"] == "set_status"
    assert specs[0]["raw"]["args"] == specs[0]["args"]


def test_delegate_scene_characters_are_unwrapped_but_task_description_stays_text() -> None:
    normalized = normalize_tool_args({
        "target_agent": "agent_scriptwriter",
        "task_description": "[文本]",
        "scene_characters": '["林舟","沈棠"]',
    }, tool=delegate_task)

    assert normalized["scene_characters"] == ["林舟", "沈棠"]
    assert normalized["task_description"] == "[文本]"


def test_invalid_structured_value_is_left_for_existing_validation() -> None:
    normalized = normalize_tool_args({
        "target_agent": "agent_scriptwriter",
        "task_description": "写场景",
        "scene_characters": "不是 JSON 数组",
    }, tool=delegate_task)

    assert normalized["scene_characters"] == "不是 JSON 数组"
    with pytest.raises(ValidationError):
        delegate_task.args_schema.model_validate(normalized)


def test_prepare_specs_uses_tool_lookup_for_prewrite_style_direct_execution() -> None:
    specs = prepare_tool_specs_for_execution(
        [{
            "raw": {
                "id": "call-prewrite",
                "name": "work_tracker",
                "args": {
                    "operations": '[{"operation":"add","item":"{\\"task\\":\\"补充资料\\"}"}]',
                },
            },
            "name": "work_tracker",
            "args": {
                "operations": '[{"operation":"add","item":"{\\"task\\":\\"补充资料\\"}"}]',
            },
        }],
        tool_lookup={"work_tracker": work_tracker},
    )

    assert specs[0]["args"]["operations"][0]["item"] == {"task": "补充资料"}


def test_tool_event_details_are_allowlisted_redacted_and_limited() -> None:
    event = build_tool_stream_event(
        "tool_exec_failed",
        "patch_script",
        tool_input={
            "search_text": "原文",
            "replace_text": "x" * 10000,
            "api_key": "secret-value",
        },
        tool_error="校验失败 token=private-value",
    )

    assert "tool_input" in event
    assert "api_key" not in event["tool_input"]
    assert len(str(event["tool_input"])) < 5000
    assert "private-value" not in event["tool_error"]
    assert "校验失败" in event["tool_error"]

    redacted_variants = build_tool_stream_event(
        "tool_exec_finished",
        "web_search",
        tool_input={
            "query": "资料",
            "exa_options": {"openai_api_key": "secret", "api_token": "secret", "safe": "ok"},
        },
    )
    assert redacted_variants["tool_input"]["exa_options"] == {
        "openai_api_key": "[已隐藏]",
        "api_token": "[已隐藏]",
        "safe": "ok",
    }

    hidden = build_tool_stream_event(
        "tool_exec_finished",
        "list_files",
        tool_input={"path": "stories"},
        tool_result="内部结果",
    )
    assert "tool_input" not in hidden
    assert "tool_result" not in hidden
    assert is_tool_result_failure("work_tracker", "任务板更新失败：参数不完整") is True

    rename_event = build_tool_stream_event(
        "tool_exec_started",
        "rename_scene",
        tool_input={
            "scene_path": "一 · 开端/1.1 · 开场.arc",
            "new_scene_name": "新的开场",
            "internal_prompt": "不应展示",
        },
    )
    assert rename_event["tool_input"] == {
        "scene_path": "一 · 开端/1.1 · 开场.arc",
        "new_scene_name": "新的开场",
    }


def test_tool_details_are_retained_in_trace_segment_and_snapshot() -> None:
    accumulator = ChatStreamAccumulator(channel="test", task_id="task-1")
    accumulator.append_event({
        "event": "tool_exec_started",
        "tool_name": "delegate_task",
        "source_agent": "agent_director",
        "tool_call_key": "call-1",
        "tool_input": {"target_agent": "agent_muse", "task_description": "找灵感"},
    }, seq=1, now_ts=10.0)
    accumulator.append_event({
        "event": "tool_exec_failed",
        "tool_name": "delegate_task",
        "source_agent": "agent_director",
        "tool_call_key": "call-1",
        "tool_error": "参数校验失败",
        "message": "调用失败",
    }, seq=2, now_ts=11.0)

    metadata = accumulator.build_metadata(stream_status="error")
    trace = metadata["tool_traces"][0]
    segment = metadata["segments"][0]
    assert trace["tool_input"]["target_agent"] == "agent_muse"
    assert trace["tool_error"] == "参数校验失败"
    assert segment["tool_input"]["task_description"] == "找灵感"
    assert segment["tool_error"] == "参数校验失败"
