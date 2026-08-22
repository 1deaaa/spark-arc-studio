from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.handoff_memory import DirectorHandoffMemory, build_handoff_context_key


def test_handoff_context_key_is_isolated_by_room() -> None:
    same = build_handoff_context_key("agent_director", "room-a")

    assert same == build_handoff_context_key("agent_director", "room-a")
    assert same != build_handoff_context_key("agent_director", "room-b")
    assert same != build_handoff_context_key("agent_lorebook", "room-a")
    assert "room-a" not in same


def test_handoff_transcript_round_trips_tool_messages_and_upserts(monkeypatch) -> None:
    class FakeChatManager:
        items = []

        def __init__(self, **_kwargs):
            pass

        def get_history(self, **_kwargs):
            return list(self.items)

        def append_message(self, *, role, content, metadata, **_kwargs):
            self.items.append({
                "id": len(self.items) + 1,
                "role": role,
                "content": content,
                "metadata": metadata,
            })

        def update_message_content_metadata(self, message_id, content, metadata):
            item = next(item for item in self.items if item["id"] == message_id)
            item["content"] = content
            item["metadata"] = metadata
            return True

    FakeChatManager.items = []
    monkeypatch.setattr("agents.handoff_memory.ChatManager", FakeChatManager)
    memory = DirectorHandoffMemory(
        user_id="u1",
        project_name="p1",
        room_agent_id="agent_director",
        context_key="room-a",
    )
    first = [
        HumanMessage(content="生成世界观"),
        AIMessage(content="", tool_calls=[{
            "id": "call-1",
            "name": "rewrite_worldview",
            "args": {"overwrite_content": "正文"},
            "type": "tool_call",
        }]),
        ToolMessage(content="保存成功", tool_call_id="call-1", name="rewrite_worldview"),
    ]
    memory.save_transcript(target_agent="agent_lorebook", messages=first, task_id="task-1")

    restored = memory.load_transcript("agent_lorebook")
    assert [message.type for message in restored] == ["human", "ai", "tool"]
    assert restored[1].tool_calls[0]["name"] == "rewrite_worldview"
    assert restored[2].tool_call_id == "call-1"

    second = [*first, HumanMessage(content="生成角色")]
    memory.save_transcript(target_agent="agent_lorebook", messages=second, task_id="task-2")

    assert len(FakeChatManager.items) == 1
    assert memory.load_transcript("agent_lorebook")[-1].content == "生成角色"
