from __future__ import annotations

import re
from typing import Any


"""OpenAI 兼容推理字段适配。

仅保留当前主链路里已被官方文档或主流兼容平台明确证实的最小集合：

1. `reasoning_content`
   - DeepSeek 已文档化；
   - 通义/百炼兼容实现广泛复用；
   - 许多中文 OpenAI 兼容平台（Kimi / GLM / MiniMax 一类中转实现）通常也沿用这一路。

2. `reasoning`
   - 用于兼容 OpenAI / LangChain 已结构化过的 reasoning block。

同时兼容一批实际已在当前项目接入模型中出现的 think/thinking 形态：

3. `think` / `thinking`
    - 某些兼容网关会把推理文本放到这两个字段；
    - 也有模型直接把推理包装在 `<think>...</think>` 或 `<thinking>...</thinking>` 文本标签里。
"""


_NONSTANDARD_REASONING_KEYS = (
    "reasoning_content",
    "reasoning",
    "think",
    "thinking",
)

_REASONING_BLOCK_TYPES = {"reasoning", "think", "thinking"}

_TEXT_BLOCK_TYPES = {
    "text",
    "output_text",
    "input_text",
}

_THINK_TAG_RE = re.compile(r"<\s*(think|thinking)\s*>([\s\S]*?)<\s*/\s*\1\s*>", re.IGNORECASE)
_THINK_OPEN_TAGS = ("<thinking>", "<think>")
_THINK_TAG_NAMES = {
    "<think>": "think",
    "<thinking>": "thinking",
}


def _find_partial_tag_suffix(
    text: str, candidates: tuple[str, ...] | list[str]
) -> int:
    source = str(text or "").lower()
    max_length = min(
        len(source),
        max((len(tag) - 1 for tag in candidates), default=0),
    )

    for size in range(max_length, 0, -1):
        suffix = source[-size:]
        if any(tag.startswith(suffix) for tag in candidates):
            return size
    return 0


class PrefixReasoningStreamParser:
    """仅在正文起始阶段识别 <think>/<thinking> 的流式拆分器。"""

    def __init__(self) -> None:
        self._pending = ""
        self._pending_kind = ""
        self._mode = "prefix"
        self._active_tag_name = ""

    def _consume(self, input_text: str = "", *, flush: bool) -> tuple[str, str]:
        source = self._pending + str(input_text or "")
        self._pending = ""
        self._pending_kind = ""

        reasoning = ""
        visible = ""

        while source:
            if self._mode == "visible":
                visible += source
                source = ""
                continue

            if self._mode == "reasoning":
                close_tag = f"</{self._active_tag_name}>"
                lower = source.lower()
                close_index = lower.find(close_tag)

                if close_index >= 0:
                    reasoning += source[:close_index]
                    source = source[close_index + len(close_tag) :]
                    self._mode = "visible"
                    self._active_tag_name = ""
                    continue

                partial_length = (
                    0
                    if flush
                    else _find_partial_tag_suffix(source, (close_tag,))
                )
                safe_length = len(source) - partial_length
                if safe_length > 0:
                    reasoning += source[:safe_length]
                self._pending = source[safe_length:]
                self._pending_kind = "close_tag"
                source = ""
                continue

            stripped = source.lstrip()
            if not stripped:
                if flush:
                    visible += source
                else:
                    self._pending = source
                    self._pending_kind = "prefix_whitespace"
                source = ""
                continue

            lowered = stripped.lower()
            matched_open = next(
                (tag for tag in _THINK_OPEN_TAGS if lowered.startswith(tag)),
                "",
            )
            if matched_open:
                self._mode = "reasoning"
                self._active_tag_name = _THINK_TAG_NAMES[matched_open]
                source = stripped[len(matched_open) :]
                continue

            # 跳过孤立的 </think> / </thinking> 闭合标签（LLM 多轮推理后有时只输出闭合标签，无对应开放标签）
            _THINK_CLOSE_TAGS = ("</think>", "</thinking>")
            matched_close = next(
                (tag for tag in _THINK_CLOSE_TAGS if lowered.startswith(tag)),
                "",
            )
            if matched_close:
                source = stripped[len(matched_close):]
                continue

            if not flush and any(tag.startswith(lowered) for tag in _THINK_OPEN_TAGS):
                self._pending = source
                self._pending_kind = "open_tag"
                source = ""
                continue

            self._mode = "visible"
            visible += source
            source = ""

        if flush and self._pending:
            if self._mode == "reasoning":
                if self._pending_kind != "close_tag":
                    reasoning += self._pending
            else:
                visible += self._pending
            self._pending = ""
            self._pending_kind = ""

        if flush and self._mode == "reasoning":
            self._mode = "visible"
            self._active_tag_name = ""

        return reasoning, visible

    def push(self, text: str) -> tuple[str, str]:
        return self._consume(text, flush=False)

    def flush(self) -> tuple[str, str]:
        return self._consume("", flush=True)


def _split_inline_think_tags(text: str) -> tuple[list[str], str]:
    if not isinstance(text, str) or not text:
        return [], ""

    parser = PrefixReasoningStreamParser()
    reasoning, visible = parser.push(text)
    trailing_reasoning, trailing_visible = parser.flush()
    reasoning += trailing_reasoning
    visible += trailing_visible
    return ([reasoning] if reasoning else []), visible


def extract_reasoning_text_from_plain_text(text: str) -> str:
    reasoning_parts, _ = _split_inline_think_tags(text)
    return "".join(reasoning_parts)


def extract_visible_text_from_plain_text(text: str) -> str:
    _, visible_text = _split_inline_think_tags(text)
    return visible_text


def _normalize_payload(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, dict, list, tuple)):
        return value

    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if dumped is not None:
                return dumped
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
            if dumped is not None:
                return dumped
        except Exception:
            pass

    return value


def _join_unique_text(parts: list[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, str) or not part:
            continue
        if part in seen:
            continue
        seen.add(part)
        out.append(part)
    return "".join(out)


def _extract_reasoning_from_reasoning_value(value: Any) -> list[str]:
    value = _normalize_payload(value)

    if value is None:
        return []
    if isinstance(value, str):
        inline_reasoning, visible_text = _split_inline_think_tags(value)
        if inline_reasoning:
            return inline_reasoning
        return [visible_text] if visible_text else []
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_extract_reasoning_from_reasoning_value(item))
        return parts
    if isinstance(value, dict):
        block_type = str(value.get("type") or "").strip().lower()
        parts: list[str] = []

        if block_type in _REASONING_BLOCK_TYPES:
            for key in ("reasoning", "text"):
                if key in value:
                    parts.extend(_extract_reasoning_from_reasoning_value(value.get(key)))
            return parts

        for key in _NONSTANDARD_REASONING_KEYS:
            if key in value:
                parts.extend(_extract_reasoning_from_reasoning_value(value.get(key)))

        return parts

    return []


def _extract_reasoning_from_content_value(content: Any) -> list[str]:
    content = _normalize_payload(content)

    if content is None:
        return []
    if isinstance(content, str):
        inline_reasoning, _ = _split_inline_think_tags(content)
        return inline_reasoning
    if isinstance(content, tuple):
        content = list(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            parts.extend(_extract_reasoning_from_content_value(item))
        return parts
    if isinstance(content, dict):
        block_type = str(content.get("type") or "").strip().lower()
        if block_type in _REASONING_BLOCK_TYPES:
            return _extract_reasoning_from_reasoning_value(content)
        if "content" in content and block_type in {"message", "item", "output"}:
            return _extract_reasoning_from_content_value(content.get("content"))
    return []


def _extract_reasoning_from_mapping(value: Any) -> list[str]:
    value = _normalize_payload(value)
    if not isinstance(value, dict):
        return []

    parts: list[str] = []
    for key in _NONSTANDARD_REASONING_KEYS:
        if key in value:
            parts.extend(_extract_reasoning_from_reasoning_value(value.get(key)))

    if "content" in value:
        parts.extend(_extract_reasoning_from_content_value(value.get("content")))

    return parts


def _extract_reasoning_from_noncontent_mapping(value: Any) -> list[str]:
    value = _normalize_payload(value)
    if not isinstance(value, dict):
        return []

    parts: list[str] = []
    for key in _NONSTANDARD_REASONING_KEYS:
        if key in value:
            parts.extend(_extract_reasoning_from_reasoning_value(value.get(key)))
    return parts


def _extract_text_from_content_value(content: Any) -> list[str]:
    content = _normalize_payload(content)

    if content is None:
        return []
    if isinstance(content, str):
        _, visible_text = _split_inline_think_tags(content)
        return [visible_text] if visible_text else []
    if isinstance(content, tuple):
        content = list(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            parts.extend(_extract_text_from_content_value(item))
        return parts
    if isinstance(content, dict):
        block_type = str(content.get("type") or "").strip().lower()
        if block_type in _REASONING_BLOCK_TYPES:
            return []
        if block_type in _TEXT_BLOCK_TYPES:
            text_value = content.get("text")
            if text_value is None:
                text_value = content.get("content")
            if text_value is None:
                text_value = content.get("value")
            return _extract_text_from_content_value(text_value)
        if "content" in content and block_type in {"message", "item", "output"}:
            return _extract_text_from_content_value(content.get("content"))
    return []


def _extract_raw_text_from_content_value(content: Any) -> list[str]:
    content = _normalize_payload(content)

    if content is None:
        return []
    if isinstance(content, str):
        return [content] if content else []
    if isinstance(content, tuple):
        content = list(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            parts.extend(_extract_raw_text_from_content_value(item))
        return parts
    if isinstance(content, dict):
        block_type = str(content.get("type") or "").strip().lower()
        if block_type in _REASONING_BLOCK_TYPES:
            return []
        if block_type in _TEXT_BLOCK_TYPES:
            text_value = content.get("text")
            if text_value is None:
                text_value = content.get("content")
            if text_value is None:
                text_value = content.get("value")
            return _extract_raw_text_from_content_value(text_value)
        if "content" in content and block_type in {"message", "item", "output"}:
            return _extract_raw_text_from_content_value(content.get("content"))
    return []


def extract_reasoning_text_from_chat_delta(delta: Any) -> str:
    """从原始 chat.completions 增量 delta 中提取非标准 reasoning 文本。"""
    return _join_unique_text(_extract_reasoning_from_mapping(delta))


def extract_reasoning_text_from_message(message: Any) -> str:
    """从 LangChain/OpenAI 消息或 chunk 中提取 reasoning 文本。"""
    message = _normalize_payload(message)

    if message is None:
        return ""

    if hasattr(message, "message"):
        inner_message = getattr(message, "message", None)
        if inner_message is not None:
            return extract_reasoning_text_from_message(inner_message)

    if isinstance(message, dict):
        parts: list[str] = []
        parts.extend(_extract_reasoning_from_content_value(message.get("content")))
        parts.extend(_extract_reasoning_from_mapping(message))
        parts.extend(_extract_reasoning_from_mapping(message.get("additional_kwargs")))
        parts.extend(_extract_reasoning_from_mapping(message.get("response_metadata")))
        return _join_unique_text(parts)

    parts: list[str] = []
    parts.extend(_extract_reasoning_from_content_value(getattr(message, "content", None)))
    parts.extend(_extract_reasoning_from_mapping(getattr(message, "additional_kwargs", None)))
    parts.extend(_extract_reasoning_from_mapping(getattr(message, "response_metadata", None)))
    return _join_unique_text(parts)


def extract_metadata_reasoning_text_from_message(message: Any) -> str:
    """仅提取 additional_kwargs / response_metadata 中的 reasoning，不解析 content 内标签。"""
    message = _normalize_payload(message)

    if message is None:
        return ""

    if hasattr(message, "message"):
        inner_message = getattr(message, "message", None)
        if inner_message is not None:
            return extract_metadata_reasoning_text_from_message(inner_message)

    if isinstance(message, dict):
        parts: list[str] = []
        parts.extend(_extract_reasoning_from_noncontent_mapping(message))
        parts.extend(_extract_reasoning_from_noncontent_mapping(message.get("additional_kwargs")))
        parts.extend(_extract_reasoning_from_noncontent_mapping(message.get("response_metadata")))
        return _join_unique_text(parts)

    parts: list[str] = []
    parts.extend(_extract_reasoning_from_noncontent_mapping(getattr(message, "additional_kwargs", None)))
    parts.extend(_extract_reasoning_from_noncontent_mapping(getattr(message, "response_metadata", None)))
    return _join_unique_text(parts)


def extract_text_content_from_message(message: Any) -> str:
    """从 LangChain/OpenAI 消息或 chunk 中提取用户可见正文文本。"""
    message = _normalize_payload(message)

    if message is None:
        return ""

    if hasattr(message, "message"):
        inner_message = getattr(message, "message", None)
        if inner_message is not None:
            return extract_text_content_from_message(inner_message)

    if isinstance(message, dict):
        return "".join(_extract_text_from_content_value(message.get("content")))

    return "".join(_extract_text_from_content_value(getattr(message, "content", None)))


def extract_raw_text_content_from_message(message: Any) -> str:
    """提取 message.content 的原始文本，不剥离内联 think 标签。"""
    message = _normalize_payload(message)

    if message is None:
        return ""

    if hasattr(message, "message"):
        inner_message = getattr(message, "message", None)
        if inner_message is not None:
            return extract_raw_text_content_from_message(inner_message)

    if isinstance(message, dict):
        return "".join(_extract_raw_text_from_content_value(message.get("content")))

    return "".join(_extract_raw_text_from_content_value(getattr(message, "content", None)))


class MessageEventStreamReasoningAdapter:
    """对聊天事件流做有状态的 reasoning / visible 拆分。"""

    def __init__(self) -> None:
        self._plain_parser = PrefixReasoningStreamParser()

    def push_message(self, message: Any) -> tuple[str, str]:
        explicit_reasoning = extract_metadata_reasoning_text_from_message(message)
        raw_text = extract_raw_text_content_from_message(message)
        inline_reasoning = ""
        visible_text = ""
        if raw_text:
            inline_reasoning, visible_text = self._plain_parser.push(raw_text)

        reasoning_parts: list[str] = []
        if explicit_reasoning:
            reasoning_parts.append(explicit_reasoning)
        if inline_reasoning and inline_reasoning not in reasoning_parts:
            reasoning_parts.append(inline_reasoning)
        return "".join(reasoning_parts), visible_text

    def flush(self) -> tuple[str, str]:
        return self._plain_parser.flush()
