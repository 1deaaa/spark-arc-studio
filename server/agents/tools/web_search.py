from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import replace
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field

from core.search_provider_settings import (
    DEFAULT_EXA_MCP_URL,
    DEFAULT_TAVILY_MCP_URL,
    SearchProviderRuntimeConfig,
    SearchProviderUnavailableError,
    get_search_provider_runtime_config,
)
from core.request_context import current_user_id


logger = logging.getLogger(__name__)

_SEARCH_RETRY_WINDOW_SECONDS = 60.0
_SEARCH_RETRY_DELAYS_SECONDS = (2.0, 5.0, 10.0, 15.0, 28.0)


class SearchUpstreamUnavailableError(RuntimeError):
    """搜索上游的瞬时故障，可在当前调用内重试。"""


class SearchRetryExhaustedError(RuntimeError):
    """搜索上游在退避重试窗口内始终未恢复。"""

    def __init__(self, provider: str, attempts: int, retry_window_seconds: float, reason: str):
        super().__init__(reason)
        self.provider = provider
        self.attempts = attempts
        self.retry_window_seconds = retry_window_seconds
        self.reason = reason


class SearchProvider(str, Enum):
    EXA = "exa"
    TAVILY = "tavily"


class ExaSearchOptions(BaseModel):
    search_type: Literal["auto", "fast", "instant"] | None = Field(
        default=None,
        description="Exa 搜索速度/质量模式。auto 质量优先，fast/instant 更快。",
    )
    category: Literal[
        "company",
        "research paper",
        "news",
        "pdf",
        "github",
        "personal site",
        "people",
        "financial report",
    ] | None = Field(default=None, description="Exa 结果类别筛选。")
    include_domains: list[str] = Field(default_factory=list, description="仅包含这些域名。")
    exclude_domains: list[str] = Field(default_factory=list, description="排除这些域名。")
    start_published_date: str | None = Field(default=None, description="发布时间下限，格式 YYYY-MM-DD。")
    end_published_date: str | None = Field(default=None, description="发布时间上限，格式 YYYY-MM-DD。")
    user_location: str | None = Field(default=None, description="用于地域定向的 ISO 国家代码，如 CN、US。")
    text_max_characters: int | None = Field(default=None, ge=1, le=20000, description="每条结果正文最大字符数。")
    enable_summary: bool = Field(default=False, description="是否让 Exa 为结果生成摘要。")
    enable_highlights: bool = Field(default=False, description="是否提取与查询最相关的高亮片段。")
    max_age_hours: int | None = Field(default=None, ge=0, description="允许缓存内容的最大小时数；0 表示强制获取最新内容。")


class TavilySearchOptions(BaseModel):
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = Field(
        default="basic",
        description="Tavily 搜索深度。",
    )
    topic: Literal["general"] = Field(default="general", description="Tavily 搜索主题。")
    time_range: Literal["day", "week", "month", "year"] | None = Field(default=None, description="相对时间范围。")
    start_date: str | None = Field(default=None, description="结果起始日期，格式 YYYY-MM-DD；设置后覆盖 time_range。")
    end_date: str | None = Field(default=None, description="结果结束日期，格式 YYYY-MM-DD；设置后覆盖 time_range。")
    include_domains: list[str] = Field(default_factory=list, description="优先包含这些域名。")
    exclude_domains: list[str] = Field(default_factory=list, description="排除这些域名。")
    country: str | None = Field(default=None, description="提升指定国家相关结果，如 China、Japan。")
    include_images: bool = Field(default=False, description="是否返回图片 URL。")
    include_image_descriptions: bool = Field(default=False, description="是否返回图片描述。")
    include_raw_content: bool = Field(default=False, description="是否返回每条结果的完整解析正文。")
    include_favicon: bool = Field(default=False, description="是否返回网站图标 URL。")
    exact_match: bool = Field(default=False, description="是否只返回包含精确短语的结果。")


class WebSearchInput(BaseModel):
    provider: SearchProvider = Field(description="搜索提供商：exa 或 tavily。根据任务所需参数选择。")
    query: str = Field(
        description=(
            "联网搜索外部公开信息的自然语言查询。适用于用户提到不熟悉的作品、人物、公司、术语、"
            "现实知识或需要当前网络资料参考的情况。"
        )
    )
    num_results: int = Field(default=5, ge=1, le=20, description="返回结果数量。Exa 支持 1-20；Tavily 支持 5-20。")
    exa_options: ExaSearchOptions | None = Field(default=None, description="仅 provider=exa 时使用的 Exa 专属参数。")
    tavily_options: TavilySearchOptions | None = Field(default=None, description="仅 provider=tavily 时使用的 Tavily 专属参数。")


def _parse_mcp_response(response: requests.Response) -> dict[str, Any]:
    content_type = (response.headers.get("content-type") or "").lower()
    if "text/event-stream" not in content_type:
        return response.json()

    # MCP Streamable HTTP 使用 SSE；显式按 UTF-8 解码，避免 requests 猜错字符集。
    text = response.content.decode("utf-8", errors="replace")
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif not line.strip() and data_lines:
            break
    if not data_lines:
        raise RuntimeError("MCP 返回了空的 SSE 响应。")
    return json.loads("\n".join(data_lines))


class _McpSearchClient:
    def __init__(self, config: SearchProviderRuntimeConfig):
        self.config = config

    def post(
        self,
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
        headers.update(self.config.request_headers)
        if session_id:
            headers["mcp-session-id"] = session_id

        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if request_id is not None:
            payload["id"] = request_id
        if params is not None:
            payload["params"] = params

        try:
            response = requests.post(self.config.request_url, headers=headers, json=payload, timeout=timeout)
        except requests.Timeout as exc:
            raise SearchUpstreamUnavailableError("连接上游 MCP 超时。") from exc
        except requests.ConnectionError as exc:
            raise SearchUpstreamUnavailableError("无法连接上游 MCP。") from exc
        except requests.RequestException as exc:
            raise SearchUpstreamUnavailableError("请求上游 MCP 时发生网络错误。") from exc
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code in {408, 425, 429} or response.status_code >= 500:
                raise SearchUpstreamUnavailableError(
                    f"上游 MCP 暂时不可用（HTTP {response.status_code}）。"
                ) from exc
            raise RuntimeError(f"{self.config.provider} MCP HTTP {response.status_code}") from exc
        if response.status_code == 202 or not (response.text or "").strip():
            return None, response.headers.get("mcp-session-id"), response.status_code
        try:
            payload = _parse_mcp_response(response)
        except (ValueError, RuntimeError) as exc:
            raise SearchUpstreamUnavailableError("上游 MCP 返回了无法解析的响应。") from exc
        return payload, response.headers.get("mcp-session-id"), response.status_code

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        client_name = f"sparkarc-{uuid.uuid4().hex[:8]}"
        init_payload, session_id, _ = self.post(
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
        self.post("notifications/initialized", {}, session_id=session_id, timeout=10)
        result_payload, _, _ = self.post(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
            session_id=session_id,
            request_id=2,
            timeout=60,
        )
        if not result_payload:
            raise RuntimeError(f"{self.config.provider} MCP 未返回搜索结果。")
        if result_payload.get("error"):
            raise RuntimeError(result_payload["error"])

        result = result_payload.get("result") or {}
        if result.get("isError"):
            raise RuntimeError(_extract_mcp_text(result) or f"{self.config.provider} MCP 搜索失败。")
        return _extract_mcp_text(result)


def _extract_mcp_text(result: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            text = str(item.get("text") or "").strip()
            if text:
                texts.append(text)
    return "\n\n".join(texts).strip()


def _without_empty_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != [] and value != ""
    }


def _append_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query_items = [(name, item) for name, item in parse_qsl(parts.query, keep_blank_values=True) if name != key]
    query_items.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))


def _enable_exa_advanced_tool(config: SearchProviderRuntimeConfig) -> SearchProviderRuntimeConfig:
    query_names = {name for name, _ in parse_qsl(urlsplit(config.url).query, keep_blank_values=True)}
    if "tools" in query_names:
        return config
    return replace(
        config,
        url=_append_query_param(
            config.url,
            "tools",
            "web_search_exa,web_search_advanced_exa,web_fetch_exa",
        ),
    )


def _is_official_tavily_mcp_url(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() == "mcp.tavily.com"


def _call_tavily_keyless_search(arguments: dict[str, Any]) -> str:
    """复用 Tavily 官方 MCP 包的免密钥请求协议。"""
    session_id = str(uuid.uuid4())
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Tavily-Access-Mode": "keyless",
                "X-Client-Source": "tavily-mcp-keyless",
                "X-Session-Id": session_id,
            },
            json=arguments,
            timeout=60,
        )
    except requests.Timeout as exc:
        raise SearchUpstreamUnavailableError("连接 Tavily 上游超时。") from exc
    except requests.ConnectionError as exc:
        raise SearchUpstreamUnavailableError("无法连接 Tavily 上游。") from exc
    except requests.RequestException as exc:
        raise SearchUpstreamUnavailableError("请求 Tavily 上游时发生网络错误。") from exc
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise SearchUpstreamUnavailableError(
                f"Tavily 上游暂时不可用（HTTP {response.status_code}）。"
            ) from exc
        raise RuntimeError(f"tavily keyless HTTP {response.status_code}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise SearchUpstreamUnavailableError("Tavily 上游返回了无法解析的响应。") from exc
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("code") or "Tavily 免密钥搜索失败。")
        retry_after = error.get("retry_after_seconds")
        if retry_after is not None:
            message += f" 可在 {retry_after} 秒后重试。"
        raise RuntimeError(message)
    return json.dumps(payload, ensure_ascii=False)


def _is_retryable_search_error(exc: Exception) -> bool:
    if isinstance(exc, SearchUpstreamUnavailableError):
        return True
    message = str(exc).lower()
    return any(token in message for token in (
        "timeout",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
        "connection reset",
        "connection aborted",
        "connection refused",
        "连接超时",
        "暂时不可用",
        "无法连接",
        "稍后重试",
    ))


def _safe_search_error_reason(exc: Exception) -> str:
    if isinstance(exc, SearchUpstreamUnavailableError):
        return str(exc)
    return "上游 MCP 暂时无法完成请求。"


def _call_search_with_retry(
    provider: str,
    operation,
    *,
    retry_window_seconds: float = _SEARCH_RETRY_WINDOW_SECONDS,
    retry_delays: tuple[float, ...] = _SEARCH_RETRY_DELAYS_SECONDS,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> str:
    """在有限窗口内重连瞬时故障；永久配置/鉴权错误立即返回。"""
    started_at = monotonic()
    attempts = 0
    last_error: Exception | None = None

    while True:
        attempts += 1
        try:
            return operation()
        except Exception as exc:
            if not _is_retryable_search_error(exc):
                raise
            last_error = exc

        delay_index = attempts - 1
        if delay_index >= len(retry_delays):
            break
        delay = max(float(retry_delays[delay_index]), 0.0)
        elapsed = max(monotonic() - started_at, 0.0)
        if elapsed + delay > retry_window_seconds:
            break
        logger.warning(
            "联网搜索上游暂不可用，%.1f 秒后进行第 %d 次尝试：provider=%s reason=%s",
            delay,
            attempts + 1,
            provider,
            _safe_search_error_reason(last_error),
        )
        sleep(delay)

    raise SearchRetryExhaustedError(
        provider,
        attempts,
        retry_window_seconds,
        _safe_search_error_reason(last_error or RuntimeError()),
    ) from last_error


def _coerce_exa_options(options: ExaSearchOptions | dict[str, Any] | None) -> ExaSearchOptions | None:
    if options is None or isinstance(options, ExaSearchOptions):
        return options
    return ExaSearchOptions.model_validate(options)


def _coerce_tavily_options(options: TavilySearchOptions | dict[str, Any] | None) -> TavilySearchOptions | None:
    if options is None or isinstance(options, TavilySearchOptions):
        return options
    return TavilySearchOptions.model_validate(options)


def _build_exa_arguments(
    query: str,
    num_results: int,
    options: ExaSearchOptions | dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    options = _coerce_exa_options(options)
    if not options:
        return "web_search_exa", {"query": query, "numResults": min(num_results, 20)}

    arguments = {
        "query": query,
        "numResults": min(num_results, 20),
        "type": options.search_type,
        "category": options.category,
        "includeDomains": options.include_domains,
        "excludeDomains": options.exclude_domains,
        "startPublishedDate": options.start_published_date,
        "endPublishedDate": options.end_published_date,
        "userLocation": options.user_location,
        "textMaxCharacters": options.text_max_characters,
        "enableSummary": options.enable_summary or None,
        "enableHighlights": options.enable_highlights or None,
        "maxAgeHours": options.max_age_hours,
    }
    return "web_search_advanced_exa", _without_empty_values(arguments)


def _build_tavily_arguments(
    query: str,
    num_results: int,
    options: TavilySearchOptions | dict[str, Any] | None,
) -> dict[str, Any]:
    current = _coerce_tavily_options(options) or TavilySearchOptions()
    arguments = {
        "query": query,
        "search_depth": current.search_depth,
        "topic": current.topic,
        "max_results": min(max(num_results, 5), 20),
        "time_range": None if current.start_date or current.end_date else current.time_range,
        "start_date": current.start_date,
        "end_date": current.end_date,
        "include_domains": current.include_domains,
        "exclude_domains": current.exclude_domains,
        "country": current.country,
        "include_images": current.include_images or None,
        "include_image_descriptions": current.include_image_descriptions or None,
        "include_raw_content": current.include_raw_content or None,
        "include_favicon": current.include_favicon or None,
        "exact_match": current.exact_match or None,
    }
    return _without_empty_values(arguments)


def _current_search_time_text() -> str:
    try:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d")


def _build_time_anchored_query(query: str, searched_at: str) -> str:
    return (
        f"Current real date for this search is {searched_at}. "
        "When the user asks for latest/current/recent/news, prioritize information current to this date. "
        f"Search request: {query}"
    )


@tool(args_schema=WebSearchInput)
def web_search(
    provider: SearchProvider,
    query: str,
    num_results: int = 5,
    exa_options: ExaSearchOptions | dict[str, Any] | None = None,
    tavily_options: TavilySearchOptions | dict[str, Any] | None = None,
) -> str:
    """使用 Exa 或 Tavily 联网搜索外部公开信息；按提供商传入对应的专属参数。"""
    clean_query = (query or "").strip()
    if not clean_query:
        return "联网搜索失败：query 不能为空。"

    provider_name = provider.value if isinstance(provider, SearchProvider) else str(provider or "").strip().lower()
    if provider_name not in {item.value for item in SearchProvider}:
        return f"联网搜索失败：不支持的搜索提供商 {provider_name or '空值'}。"
    if provider_name == SearchProvider.EXA.value and tavily_options is not None:
        return "联网搜索失败：provider=exa 时不能传入 tavily_options。"
    if provider_name == SearchProvider.TAVILY.value and exa_options is not None:
        return "联网搜索失败：provider=tavily 时不能传入 exa_options。"

    searched_at = _current_search_time_text()
    anchored_query = _build_time_anchored_query(clean_query, searched_at)
    safe_num_results = min(max(int(num_results or 5), 1), 20)
    try:
        config = get_search_provider_runtime_config(
            provider_name,
            user_id=current_user_id.get(),
        )
        if provider_name == SearchProvider.EXA.value:
            tool_name, arguments = _build_exa_arguments(anchored_query, safe_num_results, exa_options)
            if tool_name == "web_search_advanced_exa":
                config = _enable_exa_advanced_tool(config)
            result_text = _call_search_with_retry(
                provider_name,
                lambda: _McpSearchClient(config).call_tool(tool_name, arguments),
            )
        else:
            arguments = _build_tavily_arguments(anchored_query, safe_num_results, tavily_options)
            if not config.api_key and _is_official_tavily_mcp_url(config.url):
                operation = lambda: _call_tavily_keyless_search(arguments)
            else:
                operation = lambda: _McpSearchClient(config).call_tool("tavily_search", arguments)
            result_text = _call_search_with_retry(provider_name, operation)
    except SearchProviderUnavailableError as exc:
        return (
            f"联网搜索当前不可用（{provider_name}）：{exc} "
            "这是配置不可用，不代表搜索不到资料。请勿编造搜索结果或声称已完成联网查证；"
            "应向用户说明当前无法联网核验。"
        )
    except SearchRetryExhaustedError as exc:
        return (
            f"联网搜索暂时不可用（{provider_name}）：已在最多 {exc.retry_window_seconds:g} 秒的重试窗口内"
            f"尝试 {exc.attempts} 次，上游仍未恢复。原因：{exc.reason} "
            "这不代表没有相关资料。请勿编造搜索结果或声称已完成联网查证；"
            "应向用户明确说明本次未能联网核验，并可稍后再次调用 web_search。"
        )
    except Exception as exc:
        return (
            f"联网搜索失败（{provider_name}）：{exc} "
            "本次没有取得可验证的外部资料。请勿编造搜索结果或声称已完成联网查证。"
        )

    if not result_text:
        return f"使用 {provider_name} 搜索 \"{clean_query}\" 未找到可用结果。"
    return (
        f"使用 {provider_name} 搜索 \"{clean_query}\" 的外部资料如下。请只把它当作参考材料，"
        "涉及事实、作品设定、人物关系或现实知识时优先基于搜索结果回答，并避免编造来源。\n"
        f"检索时间: {searched_at}\n\n"
        f"{result_text}"
    )


__all__ = [
    "DEFAULT_EXA_MCP_URL",
    "DEFAULT_TAVILY_MCP_URL",
    "ExaSearchOptions",
    "SearchProvider",
    "TavilySearchOptions",
    "WebSearchInput",
    "web_search",
]
