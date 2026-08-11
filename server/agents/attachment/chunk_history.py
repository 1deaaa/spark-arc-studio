"""长读取工具结果的历史折叠策略。"""

ATTACHMENT_CHUNK_TOOL_NAME = "read_attachment_chunk"
ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER = (
    "[附件分片原文已折叠 - AI 已在后续回复中提炼相关要点；如需重新阅读请再次调用 read_attachment_chunk]"
)

LONG_READ_TOOL_PLACEHOLDERS = {
    ATTACHMENT_CHUNK_TOOL_NAME: ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
    "read_chapter_scene": (
        "[章节/场景原文已折叠 - AI 已在随后一轮读取并处理过该内容；"
        "如需逐字核对请再次调用 read_chapter_scene]"
    ),
    "read_chapter_outline_raw": (
        "[章节大纲原文已折叠 - AI 已在随后一轮读取并处理过该内容；"
        "如需逐字核对请再次调用 read_chapter_outline_raw]"
    ),
}


def collapse_long_read_tool_history(messages: list, *, fresh_call_ids: set[str] | None = None) -> int:
    """折叠旧用户轮次的长读取结果，保留当前用户轮次内的全部原文。"""
    from langchain_core.messages import HumanMessage as _HumanMessage
    from langchain_core.messages import ToolMessage as _ToolMessage

    fresh = fresh_call_ids or set()
    current_user_index = -1
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], _HumanMessage):
            current_user_index = index
            break

    collapsed = 0
    for i, message in enumerate(messages):
        if not isinstance(message, _ToolMessage):
            continue
        tool_name = getattr(message, "name", "") or ""
        placeholder = LONG_READ_TOOL_PLACEHOLDERS.get(tool_name)
        if not placeholder:
            continue
        # 一次用户请求可能包含“读取原文 -> 局部修改失败 -> 修正参数重试”等多轮
        # 工具调用。期间必须持续保留已读取原文，不能只保护最新一批工具结果。
        if (
            (current_user_index >= 0 and i > current_user_index)
            or getattr(message, "tool_call_id", None) in fresh
        ):
            continue
        if str(message.content or "") == placeholder:
            continue
        messages[i] = _ToolMessage(
            content=placeholder,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
        collapsed += 1
    return collapsed


def collapse_attachment_chunk_history(messages: list, *, fresh_call_ids: set[str] | None = None) -> int:
    """兼容旧入口：现在统一折叠所有长读取工具结果。"""
    return collapse_long_read_tool_history(messages, fresh_call_ids=fresh_call_ids)
