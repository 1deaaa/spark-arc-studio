from __future__ import annotations

import asyncio
import threading
import time

from agents.routes.chat import (
    _merge_context_window_stats_with_usage,
    _observe_chat_task_events,
    _run_chat_stream_with_retry,
)
from agents.routes.chat_task import ChatTaskEntry


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
