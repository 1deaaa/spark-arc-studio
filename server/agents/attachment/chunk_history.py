"""附件分片工具结果的历史折叠策略。"""

ATTACHMENT_CHUNK_TOOL_NAME = "read_attachment_chunk"
ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER = (
    "[附件分片原文已折叠 - AI 已在后续回复中提炼相关要点；如需重新阅读请再次调用 read_attachment_chunk]"
)


def collapse_attachment_chunk_history(messages: list, *, fresh_call_ids: set[str] | None = None) -> int:
    """对 read_attachment_chunk 的 ToolMessage 做“只保留最新一片”的滑窗折叠。"""
    from langchain_core.messages import ToolMessage as _ToolMessage

    fresh = fresh_call_ids or set()
    collapsed = 0
    for i, message in enumerate(messages):
        if not isinstance(message, _ToolMessage):
            continue
        if (getattr(message, "name", "") or "") != ATTACHMENT_CHUNK_TOOL_NAME:
            continue
        if getattr(message, "tool_call_id", None) in fresh:
            continue
        if str(message.content or "") == ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER:
            continue
        messages[i] = _ToolMessage(
            content=ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
        collapsed += 1
    return collapsed
