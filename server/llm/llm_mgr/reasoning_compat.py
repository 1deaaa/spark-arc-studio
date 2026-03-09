from __future__ import annotations

from typing import Any


"""OpenAI 兼容推理字段适配。

仅保留当前主链路里已被官方文档或主流兼容平台明确证实的最小集合：

1. `reasoning_content`
   - DeepSeek 已文档化；
   - 通义/百炼兼容实现广泛复用；
   - 许多中文 OpenAI 兼容平台（Kimi / GLM / MiniMax 一类中转实现）通常也沿用这一路。

2. `reasoning`
   - 用于兼容 OpenAI / LangChain 已结构化过的 reasoning block。

不再继续为 `analysis`、`thinking` 等未经当前 OpenAI 兼容主链路充分证实的字段做无限兜底，
避免维护成本继续膨胀。
"""


_NONSTANDARD_REASONING_KEYS = (
    "reasoning_content",
    "reasoning",
)

_REASONING_BLOCK_TYPES = {"reasoning"}

_TEXT_BLOCK_TYPES = {
    "text",
    "output_text",
    "input_text",
}


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
        return [value] if value else []
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

    if content is None or isinstance(content, str):
        return []
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


def _extract_text_from_content_value(content: Any) -> list[str]:
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
            parts.extend(_extract_text_from_content_value(item))
        return parts
    if isinstance(content, dict):
        block_type = str(content.get("type") or "").strip().lower()
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
