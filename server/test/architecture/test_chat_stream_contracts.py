from __future__ import annotations

import asyncio
import contextvars
import json
import queue
import threading
import time
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage

from agents.communication import (
    ModelStreamIdleTimeoutError,
    ModelStreamRetryExhaustedError,
    ModelTurnRetryNotice,
    SparkBaseAgent,
    get_tool_event_sink,
    set_tool_event_sink,
    stream_model_turn_with_retry,
)

from agents.routes.chat import (
    _finalize_chat_task,
    _merge_context_window_stats_with_usage,
    _observe_chat_task_events,
    _run_chat_background_context,
    _run_chat_stream_with_retry,
)
from agents.routes.chat_task import (
    ChatTaskEntry,
    cancel_task,
    cleanup_task,
    get_task,
    register_task,
)
from agents.chat_manager import mark_stream_metadata_interrupted
from core.request_context import (
    current_export_format,
    current_llm_usage_reporter,
    current_scriptwriter_prewrite_receipt,
    get_current_export_format,
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


def test_chat_task_replacement_waits_for_real_exit_and_cleanup_is_generation_safe() -> None:
    task_key = f"u:p:agent_director:generation-{time.time_ns()}"
    first = make_entry()
    first.task_key = task_key
    register_task(first)

    assert cancel_task(task_key) is True
    assert first.stop_event.is_set()
    assert first.cancel_requested is True
    assert first.status == "running"

    second = make_entry()
    second.task_key = task_key
    with pytest.raises(ValueError, match="已在运行中"):
        register_task(second)

    first.status = "cancelled"
    first.finished_event.set()
    register_task(second)
    cleanup_task(task_key, delay=0, task_id=first.task_id)
    time.sleep(0.02)
    assert get_task(task_key) is second

    second.finished_event.set()
    cleanup_task(task_key, delay=0, task_id=second.task_id)


def test_chat_background_context_shares_prewrite_receipt_with_tool_subcontexts() -> None:
    outer_state = {"receipt": {"receipt_id": "outer"}}
    outer_token = current_scriptwriter_prewrite_receipt.set(outer_state)
    outer_format_token = current_export_format.set("arc")

    def callback() -> None:
        assert get_current_export_format() == "novel"
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
            export_format="novel",
            callback=callback,
        )

        assert current_scriptwriter_prewrite_receipt.get() is outer_state
        assert get_scriptwriter_prewrite_receipt() == {"receipt_id": "outer"}
        assert get_current_export_format() == "arc"
    finally:
        current_export_format.reset(outer_format_token)
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
            export_format="arc",
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
    entry.user_message_id = 41

    assert [event["seq"] for event in entry.event_log] == [1, 2, 3, 4, 5, 6]
    assert [event["seq"] for event in entry.get_events_after(3)] == [4, 5, 6]

    snapshot = entry.build_snapshot()
    assert snapshot["event"] == "task_snapshot"
    assert snapshot["seq"] == 6
    assert snapshot["assistant_message_id"] == 42
    assert snapshot["user_message_id"] == 41
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
    entry.finished_event.set()

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


def test_observer_is_woken_by_background_event_without_polling() -> None:
    entry = make_entry()

    class Request:
        async def is_disconnected(self) -> bool:
            return False

    async def collect_rows():
        rows = []

        async def produce() -> None:
            await asyncio.sleep(0.01)
            entry.append_event({"event": "assistant_delta", "text": "即时事件"})
            entry.append_control_event({"event": "task_done", "status": "completed"})
            entry.status = "completed"
            entry.finished_event.set()
            entry.notify_observers()

        producer = asyncio.create_task(produce())
        async for line in _observe_chat_task_events(Request(), entry, include_snapshot=False):
            rows.append(json.loads(line))
        await producer
        return rows

    rows = asyncio.run(collect_rows())

    assert [row["event"] for row in rows] == ["assistant_delta", "task_done"]
    assert rows[0]["text"] == "即时事件"


def test_observer_waits_for_task_done_after_terminal_claim() -> None:
    entry = make_entry()

    class Request:
        async def is_disconnected(self) -> bool:
            return False

    async def collect_rows():
        rows = []

        async def produce() -> None:
            await asyncio.sleep(0.01)
            assert entry.claim_terminal_status("cancelled") is True
            entry.notify_observers()
            await asyncio.sleep(0.01)
            entry.append_control_event(
                {"event": "task_done", "status": "cancelled"},
                allow_terminal=True,
            )
            entry.finished_event.set()
            entry.notify_observers()

        producer = asyncio.create_task(produce())
        async for line in _observe_chat_task_events(Request(), entry, include_snapshot=False):
            rows.append(json.loads(line))
        await producer
        return rows

    rows = asyncio.run(collect_rows())

    assert [row["event"] for row in rows] == ["task_done"]
    assert rows[0]["status"] == "cancelled"


def test_stale_running_chat_metadata_becomes_interrupted_without_losing_progress() -> None:
    original = {
        "stream_status": "running",
        "stream_seq": 12,
        "segments": [
            {"type": "text", "text": "已生成正文"},
            {"type": "tool_trace", "tool_name": "rewrite_outline", "status": "running"},
        ],
        "tool_traces": [
            {"tool_name": "rewrite_outline", "status": "running"},
        ],
    }

    repaired, changed = mark_stream_metadata_interrupted(original)

    assert changed is True
    assert original["stream_status"] == "running"
    assert repaired["stream_status"] == "error"
    assert repaired["finish_reason"] == "interrupted"
    assert repaired["stream_seq"] == 12
    assert repaired["segments"][0]["text"] == "已生成正文"
    assert repaired["segments"][1]["status"] == "failed"
    assert repaired["tool_traces"][0]["status"] == "failed"

    unchanged, changed_again = mark_stream_metadata_interrupted(repaired)
    assert changed_again is False
    assert unchanged == repaired


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


def test_model_stream_stop_event_interrupts_blocking_upstream() -> None:
    started = threading.Event()
    release = threading.Event()
    stop_event = threading.Event()

    class BlockingLlm:
        def stream(self, _messages):
            started.set()
            release.wait()
            yield "迟到正文"

    result = []

    def consume() -> None:
        result.extend(list(stream_model_turn_with_retry(
            BlockingLlm(),
            [],
            stop_event=stop_event,
            max_attempts=1,
            idle_timeout=60,
        )))

    thread = threading.Thread(target=consume)
    thread.start()
    assert started.wait(1)
    stop_event.set()
    thread.join(1)
    release.set()

    assert not thread.is_alive()
    assert result == []


def test_model_stream_idle_timeout_is_wrapped_after_configurable_short_window() -> None:
    release = threading.Event()

    class SilentLlm:
        def stream(self, _messages):
            release.wait()
            yield "迟到正文"

    with pytest.raises(ModelStreamRetryExhaustedError) as raised:
        list(stream_model_turn_with_retry(
            SilentLlm(),
            [],
            max_attempts=1,
            retry_delay=0,
            idle_timeout=0.03,
        ))
    release.set()

    assert isinstance(raised.value.__cause__, ModelStreamIdleTimeoutError)
    assert "0.03 秒" in str(raised.value)


def test_model_stream_first_activity_disables_idle_deadline() -> None:
    def stream():
        yield {"additional_kwargs": {"reasoning_content": "思考"}}
        time.sleep(0.08)
        yield {"content": "正文"}

    chunks = list(stream_model_turn_with_retry(
        type("Llm", (), {"stream": lambda self, _messages: stream()})(),
        [],
        max_attempts=1,
        idle_timeout=0.02,
    ))

    assert chunks == [
        {"additional_kwargs": {"reasoning_content": "思考"}},
        {"content": "正文"},
    ]


def test_model_stream_empty_chunk_after_activity_does_not_rearm_idle_deadline() -> None:
    def stream():
        yield {"content": "正文"}
        yield {"content": ""}
        time.sleep(0.08)

    chunks = list(stream_model_turn_with_retry(
        type("Llm", (), {"stream": lambda self, _messages: stream()})(),
        [],
        max_attempts=1,
        idle_timeout=0.02,
    ))

    assert chunks == [{"content": "正文"}, {"content": ""}]


def test_model_stream_tool_call_chunk_does_not_replace_reasoning_or_content_activity() -> None:
    tool_chunk = AIMessageChunk(
        content="",
        tool_call_chunks=[{
            "name": "work_tracker",
            "args": "{\"operation\":",
            "id": "call-1",
            "index": 0,
        }],
    )

    def stream():
        yield tool_chunk
        time.sleep(0.08)
        second_tool_chunk = AIMessageChunk(
            content="",
            tool_call_chunks=[{
                "args": "\"set_status\"}",
                "index": 0,
            }],
        )
        yield second_tool_chunk

    with pytest.raises(ModelStreamRetryExhaustedError) as raised:
        list(stream_model_turn_with_retry(
            type("Llm", (), {"stream": lambda self, _messages: stream()})(),
            [],
            max_attempts=1,
            idle_timeout=0.02,
        ))

    assert isinstance(raised.value.__cause__, ModelStreamIdleTimeoutError)


def test_model_stream_non_streaming_fallback_still_obeys_first_activity_timeout() -> None:
    class NonStreamingLlm:
        def _should_stream(self, **_kwargs):
            return False

        def stream(self, _messages):
            time.sleep(0.08)
            yield "非流式工具调用结果"

    with pytest.raises(ModelStreamRetryExhaustedError) as raised:
        list(stream_model_turn_with_retry(
            NonStreamingLlm(),
            [],
            max_attempts=1,
            idle_timeout=0.02,
        ))

    assert isinstance(raised.value.__cause__, ModelStreamIdleTimeoutError)


def test_model_stream_first_activity_timeout_does_not_retry() -> None:
    attempts = 0

    class SilentLlm:
        def stream(self, _messages):
            nonlocal attempts
            attempts += 1
            threading.Event().wait(0.08)
            yield "迟到正文"

    with pytest.raises(ModelStreamRetryExhaustedError) as raised:
        list(stream_model_turn_with_retry(
            SilentLlm(),
            [],
            max_attempts=3,
            retry_delay=0,
            idle_timeout=0.02,
        ))

    assert attempts == 1
    assert isinstance(raised.value.__cause__, ModelStreamIdleTimeoutError)


def test_model_stream_plain_string_counts_as_visible_activity() -> None:
    def stream():
        yield "第一段"
        time.sleep(0.03)
        yield "第二段"
        time.sleep(0.03)

    chunks = list(stream_model_turn_with_retry(
        type("Llm", (), {"stream": lambda self, _messages: stream()})(),
        [],
        max_attempts=1,
        idle_timeout=0.05,
    ))

    assert chunks == ["第一段", "第二段"]


def test_model_stream_worker_preserves_contextvars() -> None:
    marker = contextvars.ContextVar("model_stream_marker", default=None)
    token = marker.set("当前聊天任务")
    seen = []
    try:
        class ContextAwareLlm:
            def stream(self, _messages):
                seen.append(marker.get())
                yield "正文"

        list(stream_model_turn_with_retry(
            ContextAwareLlm(),
            [],
            max_attempts=1,
            idle_timeout=0.1,
        ))
    finally:
        marker.reset(token)

    assert seen == ["当前聊天任务"]


def _configure_tool_event_sink_chat_stream(monkeypatch, execute_tool):
    agent = object.__new__(SparkBaseAgent)
    agent.agent_id = "agent_director"
    agent.user_id = "u"
    agent.project_name = "p"
    agent.name = "导演"
    agent.intro = ""

    turns = {"count": 0}
    tool_spec = {
        "name": "nested_tool",
        "args": {},
        "call_id": "call-nested",
        "raw": {"id": "call-nested", "name": "nested_tool", "args": {}},
    }

    monkeypatch.setattr(agent, "_set_context_checkpoint_candidate", lambda _checkpoint: None)
    monkeypatch.setattr(agent, "_build_tool_system_prompt", lambda *_args, **_kwargs: "系统提示")
    monkeypatch.setattr(agent, "_build_runtime_tail", lambda: "")
    monkeypatch.setattr(
        agent,
        "_extract_tool_call_specs_from_message",
        lambda _message: [tool_spec] if turns["count"] == 1 else [],
    )
    monkeypatch.setattr(agent, "_hydrate_tool_specs_from_chunk_buffers", lambda specs, _buffers: specs)
    monkeypatch.setattr(agent, "_prepare_tool_specs_for_execution", lambda specs: specs)
    monkeypatch.setattr(agent, "_tool_call_event_key", lambda *_args: "call-key")
    monkeypatch.setattr(agent, "_tool_progress_text", lambda _tool_name: "正在执行工具")
    monkeypatch.setattr(agent, "_tool_event_metadata", lambda *_args: {})
    monkeypatch.setattr(agent, "_execute_tool_calls", execute_tool)

    monkeypatch.setattr("agents.agent_utils.load_prompt", lambda *_args, **_kwargs: {"chat_system": "对话提示"})
    monkeypatch.setattr("agents.tools.registry.get_tools_for_agent", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        "agents.prompt_layout.build_chat_prompt_layout",
        lambda **_kwargs: SimpleNamespace(system_instruction="系统提示", user_message="用户请求"),
    )
    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: SimpleNamespace(
        get_user_llm=lambda *_args, **_kwargs: object(),
    ))

    def fake_budget_events(*_args, **_kwargs):
        if False:
            yield {}
        return SimpleNamespace(checkpoint=None, messages=[])

    def fake_model_stream(*_args, **_kwargs):
        turns["count"] += 1
        yield AIMessageChunk(content="")

    monkeypatch.setattr("agents.context_budget.stream_context_budget_events", fake_budget_events)
    monkeypatch.setattr("agents.communication.stream_model_turn_with_retry", fake_model_stream)
    monkeypatch.setattr("agents.communication.is_pipeline_tool_result_failure", lambda *_args: False)
    return agent


def test_chat_stream_restores_outer_tool_event_sink_after_nested_tools(monkeypatch) -> None:
    seen_sinks = []

    def execute_tool(_tool_calls):
        seen_sinks.append(get_tool_event_sink())
        return "工具完成"

    agent = _configure_tool_event_sink_chat_stream(monkeypatch, execute_tool)

    def run_in_isolated_context() -> None:
        outer_sink = queue.Queue()
        set_tool_event_sink(outer_sink)
        events = list(agent.chat_stream("测试请求", active_context="测试上下文"))

        assert seen_sinks and seen_sinks[0] is not outer_sink
        assert get_tool_event_sink() is outer_sink
        assert [event["event"] for event in events] == [
            "tool_intent_started",
            "tool_exec_started",
            "tool_exec_finished",
        ]

    contextvars.Context().run(run_in_isolated_context)


def test_chat_stream_restores_outer_tool_event_sink_after_tool_exception(monkeypatch) -> None:
    def execute_tool(_tool_calls):
        raise RuntimeError("工具执行异常")

    agent = _configure_tool_event_sink_chat_stream(monkeypatch, execute_tool)
    monkeypatch.setattr("traceback.print_exc", lambda: None)

    def run_in_isolated_context() -> None:
        outer_sink = queue.Queue()
        set_tool_event_sink(outer_sink)

        events = list(agent.chat_stream("测试请求", active_context="测试上下文"))

        assert events[-1]["event"] == "error"
        assert get_tool_event_sink() is outer_sink

    contextvars.Context().run(run_in_isolated_context)


def test_chat_task_terminal_claim_publishes_task_done_once(monkeypatch) -> None:
    task_key = f"u:p:agent_director:terminal-{time.time_ns()}"
    entry = make_entry()
    entry.task_key = task_key
    register_task(entry)
    monkeypatch.setattr("agents.routes.chat.cleanup_task", lambda *args, **kwargs: None)

    class FakeChatManager:
        def update_message_content_metadata(self, *args, **kwargs):
            return True

    assert cancel_task(task_key) is True
    assert entry.stop_event.is_set()
    assert _finalize_chat_task(
        FakeChatManager(),
        entry,
        task_key,
        final_status="cancelled",
        collect_usage=False,
    ) is True
    assert _finalize_chat_task(
        FakeChatManager(),
        entry,
        task_key,
        final_status="completed",
        collect_usage=False,
    ) is False
    ignored = entry.append_event({"event": "assistant_delta", "text": "迟到正文"})
    assert ignored["ignored_after_terminal"] is True

    done_events = [event for event in entry.event_log if event.get("event") == "task_done"]
    assert len(done_events) == 1
    assert done_events[0]["status"] == "cancelled"
    assert entry.status == "cancelled"
    assert entry.finished_event.is_set()
    cleanup_task(task_key, delay=0, task_id=entry.task_id)


def test_chat_task_startup_failure_uses_standard_terminal_path(monkeypatch) -> None:
    from types import SimpleNamespace

    from agents.routes import chat

    context_key = f"startup-{time.time_ns()}"
    task_key = chat._make_task_key("u", "p", "agent_director", context_key)

    class FakeChatManager:
        def __init__(self) -> None:
            self.checkpoints = []

        def append_message(self, **kwargs):
            return SimpleNamespace(id=88)

        def update_message_content_metadata(self, message_id, content, metadata):
            self.checkpoints.append((message_id, content, metadata))
            return True

    manager = FakeChatManager()
    monkeypatch.setattr(chat, "cleanup_task", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        chat,
        "create_agent_instance",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Agent 初始化失败")),
    )

    with pytest.raises(RuntimeError, match="Agent 初始化失败"):
        chat._start_chat_stream_task(
            user={"user_id": "u"},
            user_id="u",
            project_name="p",
            agent_id="agent_director",
            context_key=context_key,
            channel="direct_reply_stream",
            message="测试",
            active_context="",
            cm=manager,
            prepare_history=lambda: ([], 77),
        )

    entry = get_task(task_key)
    assert entry is not None
    assert entry.status == "error"
    assert entry.finished_event.is_set()
    done_events = [event for event in entry.event_log if event.get("event") == "task_done"]
    assert len(done_events) == 1
    assert done_events[0]["status"] == "error"
    assert "Agent 初始化失败" in entry.error_message
    assert manager.checkpoints[-1][2]["stream_status"] == "error"
    cleanup_task(task_key, delay=0, task_id=entry.task_id)


def test_chat_task_terminal_error_is_persisted_in_assistant_metadata(monkeypatch) -> None:
    entry = make_entry()
    entry.append_event({"event": "assistant_delta", "text": "已生成部分内容"})
    monkeypatch.setattr("agents.routes.chat.cleanup_task", lambda *args, **kwargs: None)

    class FakeChatManager:
        def __init__(self) -> None:
            self.checkpoints = []

        def update_message_content_metadata(self, message_id, content, metadata):
            self.checkpoints.append((message_id, content, metadata))
            return True

    manager = FakeChatManager()

    assert _finalize_chat_task(
        manager,
        entry,
        entry.task_key,
        final_status="error",
        final_error_message="Director 图达到递归步数上限",
        retry_count=2,
        collect_usage=False,
    ) is True

    assert entry.result_metadata["stream_status"] == "error"
    assert entry.result_metadata["error"] == "Director 图达到递归步数上限"
    assert entry.result_metadata["retry_count"] == 2
    assert manager.checkpoints[-1][2]["error"] == "Director 图达到递归步数上限"
    assert manager.checkpoints[-1][2]["retry_count"] == 2


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
