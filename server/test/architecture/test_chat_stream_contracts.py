from __future__ import annotations

import asyncio
import contextvars
import json
import threading
import time

from langchain_core.messages import HumanMessage, ToolMessage

from agents.communication import (
    ModelStreamRetryExhaustedError,
    ModelTurnRetryNotice,
    SparkBaseAgent,
    stream_model_turn_with_retry,
)

from agents.routes.chat import (
    _merge_context_window_stats_with_usage,
    _observe_chat_task_events,
    _run_chat_background_context,
    _run_chat_stream_with_retry,
)
from agents.routes.chat_task import ChatTaskEntry
from core.request_context import (
    current_llm_usage_reporter,
    current_scriptwriter_prewrite_receipt,
    get_scriptwriter_prewrite_receipt,
    set_scriptwriter_prewrite_receipt,
)


def make_entry() -> ChatTaskEntry:
    return ChatTaskEntry(
        task_key="u:p:agent_director:global",
        user_id="u",
        project_name="p",
        agent_id="agent_director",
        context_key="global",
        stop_event=threading.Event(),
        status="running",
        started_at=time.time(),
        assistant_message_id=42,
    )


def test_chat_background_context_shares_prewrite_receipt_with_tool_subcontexts() -> None:
    outer_state = {"receipt": {"receipt_id": "outer"}}
    outer_token = current_scriptwriter_prewrite_receipt.set(outer_state)

    def callback() -> None:
        tool_context = contextvars.copy_context()
        tool_context.run(set_scriptwriter_prewrite_receipt, {"receipt_id": "prewrite-ready"})

        assert get_scriptwriter_prewrite_receipt() == {"receipt_id": "prewrite-ready"}

    try:
        _run_chat_background_context(
            user_id="u",
            project_name="p",
            is_admin=False,
            locale="zh-CN",
            llm_usage_context="task:test",
            chat_agent_id="agent_director",
            chat_context_key="global",
            callback=callback,
        )

        assert current_scriptwriter_prewrite_receipt.get() is outer_state
        assert get_scriptwriter_prewrite_receipt() == {"receipt_id": "outer"}
    finally:
        current_scriptwriter_prewrite_receipt.reset(outer_token)


def test_chat_background_context_routes_committed_usage_and_restores_reporter() -> None:
    captured = []
    outer_reporter = lambda payload: None
    outer_token = current_llm_usage_reporter.set(outer_reporter)

    def callback() -> None:
        from llm.matchbox_adapter import _usage_recorded

        _usage_recorded({"agent_name": "agent_director", "prompt_tokens": 120})

    try:
        _run_chat_background_context(
            user_id="u",
            project_name="p",
            is_admin=False,
            locale="zh-CN",
            llm_usage_context="task:usage-live",
            llm_usage_reporter=captured.append,
            chat_agent_id="agent_director",
            chat_context_key="global",
            callback=callback,
        )
        assert captured == [{"agent_name": "agent_director", "prompt_tokens": 120}]
        assert current_llm_usage_reporter.get() is outer_reporter
    finally:
        current_llm_usage_reporter.reset(outer_token)


def test_chat_task_entry_accumulates_live_usage_by_agent() -> None:
    entry = make_entry()

    first = entry.record_llm_usage({
        "agent_name": "agent_director",
        "prompt_tokens": 1000,
        "completion_tokens": 100,
        "total_tokens": 1100,
        "cached_prompt_tokens": 600,
        "cache_miss_prompt_tokens": 400,
        "success": True,
    })
    second = entry.record_llm_usage({
        "agent_name": "agent_lorebook",
        "prompt_tokens": 800,
        "completion_tokens": 200,
        "total_tokens": 1000,
        "cached_prompt_tokens": 0,
        "cache_miss_prompt_tokens": None,
        "success": True,
    })

    assert first["total_tokens"] == 1100
    assert second["prompt_tokens"] == 1800
    assert second["completion_tokens"] == 300
    assert second["total_tokens"] == 2100
    assert second["requests"] == 2
    assert second["by_agent"]["agent_director"]["cache_hit_rate"] == 0.6
    assert second["by_agent"]["agent_lorebook"]["cache_hit_rate"] is None

    entry.append_control_event({"event": "llm_usage", "llm_usage": second})
    assert entry.event_log[-1]["event"] == "llm_usage"
    assert entry.build_snapshot()["llm_usage"]["by_agent"]["agent_lorebook"]["total_tokens"] == 1000


def test_tool_args_hydration_replaces_streamed_null_placeholders() -> None:
    agent = object.__new__(SparkBaseAgent)
    agent.agent_id = "agent_scriptwriter"
    specs = [{
        "name": "prepare_script_creation",
        "args": {
            "task_description": "落盘两个场景",
            "chapter_name": None,
            "scene_name": None,
        },
        "index": 0,
        "raw": {"id": "call-prewrite", "name": "prepare_script_creation"},
    }]
    expected_args = {
        "task_description": "落盘两个场景",
        "chapter_name": "十三 · 择途",
        "scene_name": "13-1 曲径",
    }
    chunk_buffers = {
        0: {
            "index": 0,
            "id": "call-prewrite",
            "name": "prepare_script_creation",
            "args_parts": [json.dumps(expected_args, ensure_ascii=False)],
            "raw": [],
        },
    }

    hydrated = agent._hydrate_tool_specs_from_chunk_buffers(specs, chunk_buffers)

    assert hydrated[0]["args"] == expected_args


def test_chat_task_entry_replays_seq_and_builds_snapshot_segments() -> None:
    entry = make_entry()

    entry.append_event({"event": "reasoning_delta", "text": "思考"})
    entry.append_event({"event": "assistant_delta", "text": "正文一", "source_agent": "agent_director"})
    entry.append_event({
        "event": "tool_intent_started",
        "tool_name": "rewrite_worldview",
        "tool_call_key": "call-1",
        "message": "准备修改",
    })
    entry.append_event({
        "event": "tool_exec_started",
        "tool_name": "rewrite_worldview",
        "tool_call_key": "call-1",
    })
    entry.append_event({
        "event": "tool_exec_finished",
        "tool_name": "rewrite_worldview",
        "tool_call_key": "call-1",
        "tool_result": "完成",
    })
    entry.append_event({"event": "assistant_delta", "text": "正文二", "source_agent": "agent_lorebook"})

    assert [event["seq"] for event in entry.event_log] == [1, 2, 3, 4, 5, 6]
    assert [event["seq"] for event in entry.get_events_after(3)] == [4, 5, 6]

    snapshot = entry.build_snapshot()
    assert snapshot["event"] == "task_snapshot"
    assert snapshot["seq"] == 6
    assert snapshot["assistant_message_id"] == 42
    assert snapshot["content"] == "正文一正文二"
    assert snapshot["reasoning"] == "思考"

    segments = snapshot["segments"]
    assert [seg["type"] for seg in segments] == ["reasoning", "text", "tool_trace", "text"]
    assert segments[2]["tool_name"] == "rewrite_worldview"
    assert segments[2]["status"] == "finished"

    metadata = entry.build_metadata(stream_status="completed")
    assert metadata["stream_seq"] == 6
    assert metadata["finish_reason"] == "stop"
    assert metadata["tool_traces"][0]["status"] == "finished"


def test_observer_replays_snapshot_then_events_after_cursor() -> None:
    entry = make_entry()
    entry.append_event({"event": "assistant_delta", "text": "一"})
    entry.append_event({"event": "assistant_delta", "text": "二"})
    entry.status = "completed"

    class Request:
        async def is_disconnected(self) -> bool:
            return False

    async def collect_rows():
        rows = []
        async for line in _observe_chat_task_events(Request(), entry, after_seq=1, include_snapshot=False):
            rows.append(line)
        return rows

    rows = asyncio.run(collect_rows())

    assert len(rows) == 1
    assert '"seq": 2' in rows[0]
    assert '"二"' in rows[0]


def test_chat_stream_retry_suppresses_intermediate_error_events(monkeypatch) -> None:
    entry = make_entry()
    attempts = {"count": 0}

    class FakeAgent:
        def chat_stream(self, *args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                yield {"event": "assistant_delta", "text": "会被重置"}
                yield {"event": "error", "message": "上游临时错误"}
            else:
                yield {"event": "assistant_delta", "text": "最终成功"}

    class FakeChatManager:
        def update_message_content_metadata(self, *args, **kwargs):
            return True

    monkeypatch.setattr("agents.routes.chat.update_task_status", lambda *args, **kwargs: None)

    terminated, final_error, retry_count = _run_chat_stream_with_retry(
        agent_inst=FakeAgent(),
        message="你好",
        history=[],
        active_context=None,
        cm=FakeChatManager(),
        entry=entry,
        task_key=entry.task_key,
        stop_event=threading.Event(),
        max_retries=2,
        retry_delay=0,
    )

    assert terminated is False
    assert final_error == ""
    assert retry_count == 1
    assert attempts["count"] == 2
    assert [event["event"] for event in entry.event_log] == [
        "assistant_delta",
        "retry_attempt",
        "task_snapshot",
        "assistant_delta",
    ]
    assert not any(event.get("event") == "error" for event in entry.event_log)
    assert entry.build_snapshot()["content"] == "最终成功"


def test_model_turn_retry_preserves_completed_tool_history() -> None:
    messages = [
        HumanMessage(content="生成全部角色"),
        ToolMessage(content="前五个角色已写入", tool_call_id="call-1", name="rewrite_all_characters"),
    ]

    class FlakyLlm:
        def __init__(self):
            self.calls = []

        def stream(self, current_messages):
            self.calls.append(current_messages)
            if len(self.calls) == 1:
                raise RuntimeError("上游流截断")
            yield "从第六个角色继续"

    llm = FlakyLlm()
    chunks = list(stream_model_turn_with_retry(
        llm,
        messages,
        retry_delay=0,
    ))

    assert isinstance(chunks[0], ModelTurnRetryNotice)
    assert (chunks[0].attempt, chunks[0].max_attempts, chunks[0].error) == (1, 3, "上游流截断")
    assert chunks[1:] == ["从第六个角色继续"]
    assert llm.calls == [messages, messages]
    assert llm.calls[1][1].content == "前五个角色已写入"


def test_model_turn_retry_exhaustion_blocks_whole_task_replay() -> None:
    class BrokenLlm:
        def stream(self, _messages):
            raise RuntimeError("持续截断")
            yield

    try:
        list(stream_model_turn_with_retry(BrokenLlm(), [], max_attempts=2, retry_delay=0))
    except ModelStreamRetryExhaustedError as exc:
        assert "持续截断" in str(exc)
    else:
        raise AssertionError("应在当前轮次续跑耗尽后终止")


def test_context_window_stats_merges_agent_cache_usage() -> None:
    stats = {
        "agent_id": "agent_lorebook",
        "input_tokens": 1200,
        "output_tokens": 0,
    }
    usage = {
        "by_agent": {
            "agent_lorebook": {
                "completion_tokens": 240,
                "cached_prompt_tokens": 900,
                "cache_miss_prompt_tokens": 300,
                "cache_hit_rate": 0.75,
            }
        }
    }

    merged = _merge_context_window_stats_with_usage(stats, usage)

    assert merged is not None
    assert merged["output_tokens"] == 240
    assert merged["cached_prompt_tokens"] == 900
    assert merged["cache_miss_prompt_tokens"] == 300
    assert merged["cache_hit_rate"] == 0.75
