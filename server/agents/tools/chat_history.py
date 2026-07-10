from __future__ import annotations

import json
from typing import Any, Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from agents.chat_manager import ChatManager
from core.request_context import get_current_chat_session

from .common import ToolExecutionContext


class SearchChatHistoryInput(BaseModel):
    query: str = Field(description="要在本会话原始历史中查找的关键词或连续短语")
    mode: Literal["literal", "regex"] = Field(
        default="literal",
        description="默认 literal 为普通文本搜索；仅在需要同义词并列或模式匹配时使用 regex",
    )
    case_sensitive: bool = Field(default=False, description="是否区分英文大小写")
    limit: int = Field(default=8, ge=1, le=20, description="最多返回多少条匹配消息，范围 1-20")
    before_message_id: int | None = Field(
        default=None,
        ge=1,
        description="可选分页游标；仅搜索此消息 ID 之前的更早记录",
    )


def _match_excerpt(
    content: str,
    query: str,
    *,
    match_start: int | None = None,
    match_end: int | None = None,
    radius: int = 450,
) -> str:
    """保留命中点附近原文，防止一次工具结果重新撑爆上下文。"""
    text = str(content or "")
    needle = str(query or "").strip()
    if not needle or len(text) <= radius * 2:
        return text
    index = int(match_start) if isinstance(match_start, int) else text.casefold().find(needle.casefold())
    if index < 0:
        return text[: radius * 2] + "..."
    resolved_end = int(match_end) if isinstance(match_end, int) and match_end >= index else index + len(needle)
    start = max(0, index - radius)
    end = min(len(text), resolved_end + radius)
    return ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")


def _context_excerpt(content: Any, limit: int = 500) -> str:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


@tool(args_schema=SearchChatHistoryInput)
def search_chat_history(
    query: str,
    mode: Literal["literal", "regex"] = "literal",
    case_sensitive: bool = False,
    limit: int = 8,
    before_message_id: int | None = None,
) -> str:
    """搜索当前聊天房间的原始历史。压缩摘要不确定或遗漏细节时，使用它找回用户原话、既有决策与旧回复。"""
    user_id, project_name = ToolExecutionContext.get_context()
    room_agent_id, context_key = get_current_chat_session()
    if not room_agent_id or not context_key:
        return "当前不是可检索的聊天会话，无法读取历史记录。"

    clean_query = str(query or "").strip()
    if not clean_query:
        return "请提供具体关键词或短语后再搜索聊天历史。"

    manager = ChatManager(user_id=user_id, project_name=project_name)
    try:
        matches = manager.search_history(
            agent_id=room_agent_id,
            context_key=context_key,
            query=clean_query,
            mode=mode,
            case_sensitive=case_sensitive,
            limit=limit,
            before_message_id=before_message_id,
        )
    except (ValueError, TimeoutError) as exc:
        return json.dumps({
            "query": clean_query,
            "mode": mode,
            "error": str(exc),
            "matches": [],
            "match_count": 0,
        }, ensure_ascii=False, indent=2)

    rows: list[dict[str, Any]] = []
    context_by_id: dict[int, dict[str, Any]] = {}
    for item in matches:
        rows.append({
            "message_id": item.get("id"),
            "role": item.get("role"),
            "timestamp": item.get("timestamp"),
            "excerpt": _match_excerpt(
                str(item.get("content") or ""),
                clean_query,
                match_start=item.get("match_start"),
                match_end=item.get("match_end"),
            ),
        })
        if len(rows) <= 8:
            for context_message in manager.get_message_context(
                agent_id=room_agent_id,
                context_key=context_key,
                message_id=int(item["id"]),
                radius=1,
            ):
                context_id = int(context_message["id"])
                context_by_id.setdefault(context_id, {
                    "message_id": context_id,
                    "role": context_message.get("role"),
                    "timestamp": context_message.get("timestamp"),
                    "excerpt": _context_excerpt(context_message.get("content")),
                })

    payload = {
        "query": clean_query,
        "mode": mode,
        "case_sensitive": bool(case_sensitive),
        "matches": rows,
        "match_count": len(rows),
        "context_messages": [context_by_id[key] for key in sorted(context_by_id)],
        "next_before_message_id": min((int(row["message_id"]) for row in rows), default=None),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
