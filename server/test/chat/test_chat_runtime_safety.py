"""聊天运行时取消、重试与错误语义回归。"""

from __future__ import annotations

import threading
import time

import pytest

from agents.communication import SparkBaseAgent
from agents.context_budget import (
    ContextBudgetCancelledError,
    ContextBudgetResult,
    stream_context_budget_events,
)
from agents.routes.chat import _run_chat_stream_with_retry
from agents.routes.chat_task import ChatTaskEntry


def _make_entry() -> ChatTaskEntry:
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


def test_context_budget_wait_stops_when_chat_is_cancelled() -> None:
    release = threading.Event()
    stop_event = threading.Event()

    def slow_budget(*, emit_event):
        emit_event({"event": "context_compaction_started"})
        release.wait(timeout=2)
        return ContextBudgetResult(messages=[])

    stream = stream_context_budget_events(slow_budget, stop_event=stop_event)
    assert next(stream)["event"] == "context_compaction_started"

    stop_event.set()
    started_at = time.monotonic()
    try:
        with pytest.raises(ContextBudgetCancelledError):
            next(stream)
    finally:
        release.set()

    assert time.monotonic() - started_at < 0.5


def test_whole_chat_retry_is_blocked_after_tool_execution(monkeypatch) -> None:
    entry = _make_entry()
    attempts = 0

    class FakeAgent:
        def chat_stream(self, *args, **kwargs):
            nonlocal attempts
            attempts += 1
            yield {"event": "tool_exec_started", "tool_name": "rewrite_outline"}
            yield {"event": "error", "message": "工具执行后的上游错误"}

    class FakeChatManager:
        def update_message_content_metadata(self, *args, **kwargs):
            return True

    monkeypatch.setattr("agents.routes.chat.update_task_status", lambda *args, **kwargs: None)
    monkeypatch.setattr("agents.routes.chat.cleanup_task", lambda *args, **kwargs: None)

    terminated, final_error, retry_count = _run_chat_stream_with_retry(
        agent_inst=FakeAgent(),
        message="继续",
        history=[],
        active_context=None,
        cm=FakeChatManager(),
        entry=entry,
        task_key=entry.task_key,
        stop_event=entry.stop_event,
        max_retries=3,
        retry_delay=0,
    )

    assert terminated is False
    assert "工具执行后的上游错误" in final_error
    assert retry_count == 0
    assert attempts == 1
    assert not any(event.get("event") == "retry_attempt" for event in entry.event_log)


def test_non_stream_chat_propagates_runtime_errors(monkeypatch) -> None:
    class BrokenMatchbox:
        def get_user_llm(self, *args, **kwargs):
            raise RuntimeError("模型配置损坏")

    monkeypatch.setattr("llm.agen_matchbox.matchbox", lambda: BrokenMatchbox())
    monkeypatch.setattr("agents.tools.registry.get_tools_for_agent", lambda *args, **kwargs: [])

    agent = SparkBaseAgent.__new__(SparkBaseAgent)
    agent.agent_id = "agent_director"
    agent.user_id = "u"
    agent.project_name = "p"
    agent.name = "导演"
    agent.intro = "测试"
    agent._context_checkpoint_candidate = None

    with pytest.raises(RuntimeError, match="模型配置损坏"):
        agent.chat("你好", history=[])
