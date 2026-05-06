from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field


DEFAULT_EXA_MCP_URL = "https://mcp.exa.ai/mcp"


class WebSearchInput(BaseModel):
    query: str = Field(
        description=(
            "联网搜索外部公开信息的自然语言查询。适用于用户提到不熟悉的作品、人物、公司、术语、"
            "现实知识或需要当前网络资料参考的情况。"
        )
    )
    num_results: int = Field(default=5, ge=1, le=10, description="返回搜索结果数量，建议 3-5，最多 10。")


def _exa_mcp_url() -> str:
    return (os.getenv("SPARKARC_EXA_MCP_URL") or DEFAULT_EXA_MCP_URL).strip() or DEFAULT_EXA_MCP_URL


def _parse_mcp_response(response: requests.Response) -> dict[str, Any]:
    text = response.text or ""
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/event-stream" not in content_type:
        return response.json()

    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif not line.strip() and data_lines:
            break
    if not data_lines:
        raise RuntimeError("MCP 返回了空的 SSE 响应。")
    return json.loads("\n".join(data_lines))


def _mcp_post(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
    request_id: int | str | None = None,
    timeout: int = 30,
) -> tuple[dict[str, Any] | None, str | None, int]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["mcp-session-id"] = session_id

    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params

    response = requests.post(_exa_mcp_url(), headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    if response.status_code == 202 or not (response.text or "").strip():
        return None, response.headers.get("mcp-session-id"), response.status_code
    return _parse_mcp_response(response), response.headers.get("mcp-session-id"), response.status_code


def _call_exa_web_search(query: str, num_results: int) -> str:
    client_name = f"sparkarc-{uuid.uuid4().hex[:8]}"
    init_payload, session_id, _ = _mcp_post(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": client_name, "version": "0.1.0"},
        },
        request_id=1,
        timeout=20,
    )
    if init_payload and init_payload.get("error"):
        raise RuntimeError(init_payload["error"])
    if not session_id:
        raise RuntimeError("Exa MCP 未返回会话 ID。")

    _mcp_post("notifications/initialized", {}, session_id=session_id, timeout=10)
    result_payload, _, _ = _mcp_post(
        "tools/call",
        {
            "name": "web_search_exa",
            "arguments": {
                "query": query,
                "numResults": num_results,
            },
        },
        session_id=session_id,
        request_id=2,
        timeout=40,
    )

    if not result_payload:
        raise RuntimeError("Exa MCP 未返回搜索结果。")
    if result_payload.get("error"):
        raise RuntimeError(result_payload["error"])

    result = result_payload.get("result") or {}
    content = result.get("content") or []
    texts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "").strip()
            if text:
                texts.append(text)
    return "\n\n".join(texts).strip()


def _current_search_time_text() -> str:
    try:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M:%S %z")


def _build_time_anchored_query(query: str, searched_at: str) -> str:
    return (
        f"Current real date/time for this search is {searched_at} (Asia/Shanghai). "
        "When the user asks for latest/current/recent/news, prioritize information current to this date. "
        f"Search request: {query}"
    )


@tool(args_schema=WebSearchInput)
def web_search(query: str, num_results: int = 5) -> str:
    """联网搜索外部公开信息，用于补充项目外知识和不熟悉作品资料。"""
    clean_query = (query or "").strip()
    if not clean_query:
        return "联网搜索失败：query 不能为空。"

    safe_num_results = min(max(int(num_results or 5), 1), 10)
    searched_at = _current_search_time_text()
    exa_query = _build_time_anchored_query(clean_query, searched_at)
    try:
        result_text = _call_exa_web_search(exa_query, safe_num_results)
    except Exception as e:
        return f"联网搜索失败：{e}"

    if not result_text:
        return f"联网搜索 \"{clean_query}\" 未找到可用结果。"
    return (
        f"联网搜索 \"{clean_query}\" 的外部资料如下。请只把它当作参考材料，"
        "涉及事实、作品设定、人物关系或现实知识时优先基于搜索结果回答，并避免编造来源。\n"
        f"检索时间: {searched_at}\n\n"
        f"{result_text}"
    )
