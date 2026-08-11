from __future__ import annotations

from langchain_core.messages import HumanMessage, ToolMessage

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


def test_long_read_tool_history_keeps_scene_source_across_current_tool_retries() -> None:
    messages = [
        HumanMessage(content="请局部修改当前场景"),
        ToolMessage(content="当前场景完整原文", tool_call_id="read-current", name="read_chapter_scene"),
        ToolMessage(content="局部修改失败：未找到片段", tool_call_id="patch-failed", name="patch_script"),
    ]

    collapsed = collapse_long_read_tool_history(messages, fresh_call_ids={"patch-failed"})

    assert collapsed == 0
    assert messages[1].content == "当前场景完整原文"


def test_long_read_tool_history_collapses_scene_source_from_previous_user_turn() -> None:
    messages = [
        HumanMessage(content="先读取场景"),
        ToolMessage(content="上一轮场景完整原文", tool_call_id="read-old", name="read_chapter_scene"),
        HumanMessage(content="开始另一个任务"),
        ToolMessage(content="当前工具结果", tool_call_id="current", name="list_chapters"),
    ]

    collapsed = collapse_long_read_tool_history(messages, fresh_call_ids={"current"})

    assert collapsed == 1
    assert messages[1].content == LONG_READ_TOOL_PLACEHOLDERS["read_chapter_scene"]
