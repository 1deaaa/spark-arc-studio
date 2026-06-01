from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.context_budget import prepare_chat_messages_with_budget, rebudget_existing_messages
from agents.routes.chat_persistence import ChatStreamAccumulator


class _Usage:
    model_name = "gpt-4o"


class _DummyLlm:
    usage = _Usage()
    max_context_tokens = 9000
    max_output_tokens = 1024


def test_context_budget_compacts_long_history(monkeypatch):
    def fake_compress(self, **kwargs):
        return {
            "summary": "早期历史摘要",
            "user_goal": ["继续完成任务"],
            "current_progress": ["已经读取过早期上下文"],
            "important_facts": [],
            "decisions": [],
            "open_tasks": [],
            "recent_turns": [],
            "tool_results": [],
            "handoff_notes": ["继续生成即可"],
        }

    monkeypatch.setattr(
        "agents.utility_agent.UtilityAgent.compress_chat_history",
        fake_compress,
    )

    history = [
        {"role": "user", "content": f"第 {idx} 轮：" + ("很长的历史内容。" * 260)}
        for idx in range(18)
    ]
    events = []

    result = prepare_chat_messages_with_budget(
        user_id="1",
        project_name="测试项目",
        agent_id="agent_director",
        system_instruction="你是导演。",
        history=history,
        user_message="请继续刚才的任务。",
        llm_client=_DummyLlm(),
        emit_event=events.append,
    )

    assert result.compacted is True
    assert result.original_tokens > result.compacted_tokens
    assert any(evt["event"] == "context_compaction_started" for evt in events)
    assert any(evt["event"] == "context_compaction_finished" for evt in events)
    stats = [evt for evt in events if evt["event"] == "context_window_stats"]
    assert stats
    assert stats[-1]["input_tokens"] == result.compacted_tokens
    assert stats[-1]["agent_id"] == "agent_director"
    assert "早期历史摘要" in "\n".join(str(m.content) for m in result.messages)
    assert result.messages[-1].content == "请继续刚才的任务。"


def test_context_compaction_events_are_persisted_as_segments():
    acc = ChatStreamAccumulator(channel="direct_reply_stream", task_id="task-1")

    acc.append_event({"event": "context_compaction_started", "original_tokens": 12000, "model": "gpt-4o"}, seq=1)
    acc.append_event({
        "event": "context_compaction_finished",
        "original_tokens": 12000,
        "compacted_tokens": 3500,
        "retained_messages": 8,
        "model": "gpt-4o",
    }, seq=2)

    metadata = acc.build_metadata(stream_status="completed")
    segments = metadata["segments"]
    assert len(segments) == 1
    assert segments[0]["type"] == "context_compaction"
    assert segments[0]["status"] == "finished"
    assert segments[0]["compacted_tokens"] == 3500


def test_visible_history_keeps_context_summary_notice_in_order():
    from agents.routes.chat import _visible_chat_history

    history = [
        {"id": 1, "role": "user", "content": "旧请求"},
        {
            "id": 2,
            "role": "system",
            "content": '{"summary": "内部摘要"}',
            "metadata": {"kind": "context_summary"},
        },
        {
            "id": 3,
            "role": "assistant",
            "content": "",
            "metadata": {
                "kind": "context_compaction_notice",
                "segments": [
                    {
                        "type": "context_compaction_summary",
                        "status": "finished",
                        "summary_text": "摘要：\n- 已归档旧上下文",
                    }
                ],
            },
        },
        {"id": 4, "role": "assistant", "content": "继续执行。"},
    ]

    visible = _visible_chat_history(history)

    assert [item["id"] for item in visible] == [1, 3, 4]
    assert visible[1]["metadata"]["segments"][0]["type"] == "context_compaction_summary"
    assert "已归档旧上下文" in visible[1]["metadata"]["segments"][0]["summary_text"]


def test_rebudget_keeps_tool_call_boundary(monkeypatch):
    def fake_estimate(text, model=None):
        return max(1, len(str(text)) // 10)

    def fake_compress(self, **kwargs):
        return {
            "summary": "早期历史摘要",
            "user_goal": [],
            "current_progress": [],
            "important_facts": [],
            "decisions": [],
            "open_tasks": [],
            "recent_turns": [],
            "tool_results": [],
            "handoff_notes": [],
        }

    monkeypatch.setattr("agents.context_budget.estimate_tokens", fake_estimate)
    monkeypatch.setattr("agents.utility_agent.UtilityAgent.compress_chat_history", fake_compress)

    ai_tool_call = AIMessage(
        content="准备调用两个工具。" + ("需要保留工具调用边界。" * 800),
        tool_calls=[
            {"name": "tool_a", "args": {}, "id": "call-a"},
            {"name": "tool_b", "args": {}, "id": "call-b"},
        ],
    )
    messages = [
        SystemMessage(content="系统提示"),
        HumanMessage(content="早期长历史。" + ("x" * 60000)),
        ai_tool_call,
        ToolMessage(content="工具 A 结果", tool_call_id="call-a"),
        ToolMessage(content="工具 B 结果", tool_call_id="call-b"),
    ]

    result = rebudget_existing_messages(
        user_id="1",
        project_name="测试项目",
        agent_id="agent_director",
        messages=messages,
        llm_client=_DummyLlm(),
        current_user_message="继续",
    )

    retained_types = [getattr(message, "type", "") for message in result.messages]
    first_tool_index = retained_types.index("tool")
    assert retained_types[first_tool_index - 1] == "ai"
    assert result.messages[first_tool_index - 1].tool_calls
