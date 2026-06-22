from __future__ import annotations

from langchain_core.messages import ToolMessage

from agents.attachment.chunk_history import (
    LONG_READ_TOOL_PLACEHOLDERS,
    collapse_long_read_tool_history,
)


def test_long_read_tool_history_keeps_fresh_scene_and_collapses_old_scene() -> None:
    messages = [
        ToolMessage(content="旧章节原文" * 100, tool_call_id="old-scene", name="read_chapter_scene"),
        ToolMessage(content="新章节原文" * 100, tool_call_id="fresh-scene", name="read_chapter_scene"),
    ]

    collapsed = collapse_long_read_tool_history(messages, fresh_call_ids={"fresh-scene"})

    assert collapsed == 1
    assert messages[0].content == LONG_READ_TOOL_PLACEHOLDERS["read_chapter_scene"]
    assert messages[1].content == "新章节原文" * 100


def test_long_read_tool_history_does_not_touch_regular_tool_results() -> None:
    messages = [
        ToolMessage(content="短工具结果", tool_call_id="tool-1", name="list_chapters"),
    ]

    collapsed = collapse_long_read_tool_history(messages)

    assert collapsed == 0
    assert messages[0].content == "短工具结果"
