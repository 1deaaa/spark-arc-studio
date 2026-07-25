"""聊天上下文压缩、检查点与历史搜索回归。"""

from __future__ import annotations

import json
import threading
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.chat_manager import ChatManager
from agents.context_budget import (
    CONTEXT_CHECKPOINT_READY_EVENT,
    ContextBudgetResult,
    ContextCompactionFailedError,
    ContextWindowIncompatibleError,
    partition_history_for_manual_compaction,
    prepare_chat_messages_with_budget,
    rebudget_existing_messages,
    stream_context_budget_events,
)
from agents.routes.chat import _run_chat_stream_with_retry
from agents.routes.chat_task import ChatTaskEntry
from agents.tools.chat_history import search_chat_history
from agents.tools.registry import get_tools_for_agent
from agents.text_search import (
    RegexSearchTimeoutError,
    compile_search_pattern,
    iter_search_matches,
)
from core.models import ChatMessage, User, UserInfo
from core.request_context import (
    current_project_name,
    current_user_id,
    reset_current_chat_session,
    set_current_chat_session,
)


@pytest.fixture()
def isolated_chat_db(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UserInfo.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        session.add(User(id=1, username="checkpoint-user", password_hash="x", salt="x"))
        session.commit()
    monkeypatch.setattr("agents.chat_manager.UserInfoSession", session_factory)
    return session_factory


def _checkpoint(boundary: int, *, summary: str = "早期摘要", original_messages: int = 2) -> dict:
    return {
        "summary": {"summary": summary},
        "metadata": {
            "kind": "context_checkpoint",
            "schema_version": 1,
            "source": "test",
            "compacted_through_message_id": boundary,
            "source_message_id_start": 1,
            "source_message_id_end": boundary,
            "original_messages": original_messages,
        },
    }


def test_runtime_history_uses_latest_checkpoint_and_keeps_original_searchable(isolated_chat_db) -> None:
    manager = ChatManager(user_id=1, project_name="项目")
    first_user = manager.append_message(agent_id="agent_director", context_key="global", role="user", content="最早的蓝色钟楼设定")
    first_assistant = manager.append_message(agent_id="agent_director", context_key="global", role="assistant", content="已经记录钟楼设定")
    recent_user = manager.append_message(agent_id="agent_director", context_key="global", role="user", content="继续当前场景")
    recent_assistant = manager.append_message(agent_id="agent_director", context_key="global", role="assistant", content="当前场景回复")

    saved = manager.persist_context_checkpoint(
        agent_id="agent_director",
        context_key="global",
        checkpoint=_checkpoint(first_assistant.id),
    )
    duplicate = manager.persist_context_checkpoint(
        agent_id="agent_director",
        context_key="global",
        checkpoint=_checkpoint(first_assistant.id, summary="重复候选"),
    )

    assert saved is not None
    assert duplicate is not None
    assert duplicate["id"] == saved["id"]
    runtime = manager.get_context_history(agent_id="agent_director", context_key="global")
    assert [item["role"] for item in runtime] == ["system", "user", "assistant"]
    assert [item["id"] for item in runtime[1:]] == [recent_user.id, recent_assistant.id]
    assert manager.search_history(
        agent_id="agent_director",
        context_key="global",
        query="蓝色钟楼",
    )[0]["id"] == first_user.id

    with isolated_chat_db() as session:
        checkpoints = session.execute(
            select(ChatMessage).where(ChatMessage.role == "system")
        ).scalars().all()
    assert len(checkpoints) == 1


def test_editing_compacted_original_invalidates_covering_checkpoint(isolated_chat_db) -> None:
    manager = ChatManager(user_id=1, project_name="项目")
    first = manager.append_message(agent_id="agent_director", context_key="global", role="user", content="旧原话")
    second = manager.append_message(agent_id="agent_director", context_key="global", role="assistant", content="旧回复")
    saved = manager.persist_context_checkpoint(
        agent_id="agent_director",
        context_key="global",
        checkpoint=_checkpoint(second.id),
    )
    assert saved is not None
    manager.append_message(
        agent_id="agent_director",
        context_key="global",
        role="assistant",
        content="",
        metadata={
            "kind": "context_compaction_notice",
            "segments": [{"type": "context_compaction_summary", "summary_message_id": saved["id"]}],
        },
    )

    assert manager.update_message(first.id, "改过的原话") is True
    runtime = manager.get_context_history(agent_id="agent_director", context_key="global")

    assert [item["role"] for item in runtime] == ["user", "assistant"]
    assert runtime[0]["content"] == "改过的原话"
    assert not any(
        item.get("metadata", {}).get("kind") == "context_compaction_notice"
        for item in manager.get_history(agent_id="agent_director", context_key="global", limit=20)
    )


def test_history_search_tool_is_bound_only_inside_server_owned_chat_session(isolated_chat_db) -> None:
    manager = ChatManager(user_id=1, project_name="项目")
    before = manager.append_message(
        agent_id="agent_director",
        context_key="room-a",
        role="assistant",
        content="上一轮确认：保留结尾的悬念。",
    )
    target = manager.append_message(
        agent_id="agent_director",
        context_key="room-a",
        role="user",
        content="用户原话：不要让钟楼在结尾倒塌",
    )
    after = manager.append_message(
        agent_id="agent_director",
        context_key="room-a",
        role="assistant",
        content="收到，将按这条约束处理。",
    )
    manager.append_message(
        agent_id="agent_director",
        context_key="room-b",
        role="user",
        content="另一个房间的钟楼",
    )

    user_token = current_user_id.set("1")
    project_token = current_project_name.set("项目")
    try:
        assert "search_chat_history" not in {tool.name for tool in get_tools_for_agent("agent_director", user_id="1")}
        chat_tokens = set_current_chat_session("agent_director", "room-a")
        try:
            assert "search_chat_history" in {tool.name for tool in get_tools_for_agent("agent_director", user_id="1")}
            payload = json.loads(search_chat_history.invoke({"query": "钟楼", "limit": 8}))
        finally:
            reset_current_chat_session(chat_tokens)
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert payload["match_count"] == 1
    assert payload["matches"][0]["message_id"] == target.id
    assert [item["message_id"] for item in payload["context_messages"]] == [before.id, target.id, after.id]


def test_history_search_tool_supports_bounded_regex_and_reports_invalid_pattern(isolated_chat_db) -> None:
    manager = ChatManager(user_id=1, project_name="项目")
    target = manager.append_message(
        agent_id="agent_director",
        context_key="room-a",
        role="user",
        content="用户原话：不要让钟楼在最终章节倒塌",
    )

    user_token = current_user_id.set("1")
    project_token = current_project_name.set("项目")
    chat_tokens = set_current_chat_session("agent_director", "room-a")
    try:
        payload = json.loads(search_chat_history.invoke({
            "query": "钟楼.*倒塌",
            "mode": "regex",
            "limit": 8,
        }))
        invalid = json.loads(search_chat_history.invoke({
            "query": "([未闭合",
            "mode": "regex",
        }))
    finally:
        reset_current_chat_session(chat_tokens)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert payload["match_count"] == 1
    assert payload["matches"][0]["message_id"] == target.id
    assert payload["mode"] == "regex"
    assert invalid["match_count"] == 0
    assert invalid["error"]


def test_regex_search_timeout_is_enforced() -> None:
    compiled = compile_search_pattern(r"(a+)+$")
    with pytest.raises(RegexSearchTimeoutError):
        list(iter_search_matches(compiled, "a" * 100_000 + "!", timeout_seconds=0.001))


class _SmallLLM:
    max_context_tokens = 2048
    max_output_tokens = 256
    model_name = "offline-small"


def test_automatic_compaction_emits_persistable_internal_candidate(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))
    monkeypatch.setattr(
        "agents.utility_agent.UtilityAgent.compress_chat_history",
        lambda self, **kwargs: {
            "summary": "早期创作上下文",
            "user_intent_anchors": [{"intent": "保留角色关系"}],
        },
    )
    history = [
        {"id": index, "role": "user" if index % 2 else "assistant", "content": f"历史{index}-" + "x" * 180, "metadata": {}}
        for index in range(1, 15)
    ]
    events: list[dict] = []

    result = prepare_chat_messages_with_budget(
        user_id="1",
        project_name="项目",
        agent_id="agent_director",
        system_instruction="系统指令",
        history=history,
        user_message="继续",
        llm_client=_SmallLLM(),
        emit_event=events.append,
    )

    assert result.compacted is True
    assert result.checkpoint is not None
    assert result.checkpoint["metadata"]["compacted_through_message_id"] < history[-1]["id"]
    assert any(event.get("event") == CONTEXT_CHECKPOINT_READY_EVENT for event in events)
    assert isinstance(result.messages[1], SystemMessage)


def test_compaction_started_event_is_streamed_before_budget_operation_finishes() -> None:
    release = threading.Event()

    def slow_budget(*, emit_event):
        emit_event({"event": "context_compaction_started", "original_tokens": 9000})
        assert release.wait(timeout=2)
        emit_event({"event": "context_compaction_finished", "compacted_tokens": 2000})
        return ContextBudgetResult(messages=[])

    stream = stream_context_budget_events(slow_budget)
    first = next(stream)

    assert first["event"] == "context_compaction_started"
    assert release.is_set() is False
    release.set()
    remaining = list(stream)
    assert [event["event"] for event in remaining] == ["context_compaction_finished"]


def test_required_context_overflow_is_non_retryable_and_does_not_call_compactor(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))
    called = {"value": False}

    def fail_if_called(self, **kwargs):
        called["value"] = True
        raise AssertionError("不应调用压缩模型")

    monkeypatch.setattr("agents.utility_agent.UtilityAgent.compress_chat_history", fail_if_called)

    with pytest.raises(ContextWindowIncompatibleError):
        prepare_chat_messages_with_budget(
            user_id="1",
            project_name="项目",
            agent_id="agent_director",
            system_instruction="S" * 500,
            history=[],
            user_message="U" * 500,
            llm_client=type("TinyLLM", (), {"max_context_tokens": 1024, "max_output_tokens": 256, "model_name": "tiny"})(),
        )
    assert called["value"] is False


def test_compaction_failure_stops_instead_of_silently_dropping_history(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))
    monkeypatch.setattr(
        "agents.utility_agent.UtilityAgent.compress_chat_history",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("离线压缩失败")),
    )
    history = [
        {"id": index, "role": "user", "content": "x" * 220, "metadata": {}}
        for index in range(1, 12)
    ]

    with pytest.raises(ContextCompactionFailedError):
        prepare_chat_messages_with_budget(
            user_id="1",
            project_name="项目",
            agent_id="agent_director",
            system_instruction="系统",
            history=history,
            user_message="继续",
            llm_client=_SmallLLM(),
        )


def test_tool_loop_compaction_preserves_current_user_and_complete_tool_unit(monkeypatch) -> None:
    monkeypatch.setattr("agents.context_budget.estimate_tokens", lambda text, model=None: len(text))
    monkeypatch.setattr(
        "agents.utility_agent.UtilityAgent.compress_chat_history",
        lambda self, **kwargs: {"summary": "早期工具循环摘要"},
    )
    messages = [
        SystemMessage(content="稳定系统前缀"),
        *[
            message
            for index in range(1, 9)
            for message in (
                HumanMessage(content=f"旧请求{index}-" + "x" * 150),
                AIMessage(content=f"旧回复{index}-" + "y" * 150),
            )
        ],
        HumanMessage(content="CURRENT_USER_VERBATIM"),
        AIMessage(
            content="",
            tool_calls=[{
                "id": "call_current",
                "name": "read_chapter_scene",
                "args": {"scene": "钟楼"},
                "type": "tool_call",
            }],
        ),
        ToolMessage(
            content="CURRENT_TOOL_RESULT",
            tool_call_id="call_current",
            name="read_chapter_scene",
        ),
    ]

    result = rebudget_existing_messages(
        user_id="1",
        project_name="项目",
        agent_id="agent_director",
        messages=messages,
        llm_client=_SmallLLM(),
        current_user_message="CURRENT_USER_VERBATIM",
    )

    assert result.compacted is True
    assert result.messages[0].content == "稳定系统前缀"
    current_index = next(
        index
        for index, message in enumerate(result.messages)
        if isinstance(message, HumanMessage) and message.content == "CURRENT_USER_VERBATIM"
    )
    assert isinstance(result.messages[current_index + 1], AIMessage)
    assert result.messages[current_index + 1].tool_calls[0]["id"] == "call_current"
    assert isinstance(result.messages[current_index + 2], ToolMessage)
    assert result.messages[current_index + 2].tool_call_id == "call_current"
    assert result.messages[current_index + 2].content == "CURRENT_TOOL_RESULT"


def test_utility_summary_budget_retries_once_then_fails_explicitly(monkeypatch) -> None:
    from agents.utility_agent import UtilityAgent

    monkeypatch.setattr("agents.utility_agent.estimate_tokens", lambda text, model=None: len(text))
    utility = UtilityAgent(user_id="1", project_name="项目")
    calls = {"count": 0}

    def still_too_large(**kwargs):
        calls["count"] += 1
        return {"summary": "x" * 600}

    monkeypatch.setattr(utility, "_compress_once", still_too_large)

    with pytest.raises(ValueError, match="上下文摘要超过目标预算"):
        utility._enforce_summary_budget(
            summary={"summary": "x" * 600},
            agent_id="agent_director",
            model_name="offline-small",
            target_tokens=256,
            current_user_message="继续",
        )
    assert calls["count"] == 1


def test_manual_compaction_partitions_old_history_and_keeps_two_recent_turns() -> None:
    history = [
        {"id": 1, "role": "user", "content": "第一轮问题", "metadata": {}},
        {"id": 2, "role": "assistant", "content": "第一轮回答", "metadata": {}},
        {"id": 3, "role": "user", "content": "第二轮问题", "metadata": {}},
        {"id": 4, "role": "assistant", "content": "第二轮回答", "metadata": {}},
        {"id": 5, "role": "user", "content": "第三轮问题", "metadata": {}},
        {"id": 6, "role": "assistant", "content": "第三轮回答", "metadata": {}},
    ]

    compactible, retained = partition_history_for_manual_compaction(
        history,
        keep_recent_turns=2,
    )

    assert [item["id"] for item in compactible] == [1, 2]
    assert [item["id"] for item in retained] == [3, 4, 5, 6]


def _entry() -> ChatTaskEntry:
    return ChatTaskEntry(
        task_key="1:项目:agent_director:global",
        user_id="1",
        project_name="项目",
        agent_id="agent_director",
        context_key="global",
        stop_event=threading.Event(),
        status="running",
        started_at=time.time(),
        assistant_message_id=42,
    )


def test_non_retryable_context_error_runs_once_and_never_persists_checkpoint(monkeypatch) -> None:
    attempts = {"count": 0}

    class Agent:
        def chat_stream(self, *args, **kwargs):
            attempts["count"] += 1
            yield {
                "event": "error",
                "code": "context_window_incompatible",
                "message": "窗口不足",
                "retryable": False,
            }

    class Manager:
        persisted = []

        def update_message_content_metadata(self, *args, **kwargs):
            return True

        def persist_context_checkpoint(self, **kwargs):
            self.persisted.append(kwargs)

    manager = Manager()
    monkeypatch.setattr("agents.routes.chat.update_task_status", lambda *args, **kwargs: None)

    terminated, final_error, retry_count = _run_chat_stream_with_retry(
        agent_inst=Agent(),
        message="继续",
        history=[],
        active_context=None,
        cm=manager,
        entry=_entry(),
        task_key="1:项目:agent_director:global",
        stop_event=threading.Event(),
        max_retries=3,
        retry_delay=0,
    )

    assert terminated is False
    assert final_error == "窗口不足"
    assert retry_count == 0
    assert attempts["count"] == 1
    assert manager.persisted == []
