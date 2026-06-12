"""OpenAI 兼容协议的用量字段归一化。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(slots=True)
class NormalizedUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_prompt_tokens: int = 0
    cache_miss_prompt_tokens: Optional[int] = None
    usage_source: str = "upstream"
    cache_source: Optional[str] = None

    @property
    def cache_hit_rate(self) -> Optional[float]:
        if self.prompt_tokens <= 0:
            return None
        return max(0.0, min(1.0, self.cached_prompt_tokens / self.prompt_tokens))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "cache_miss_prompt_tokens": self.cache_miss_prompt_tokens,
            "cache_hit_rate": self.cache_hit_rate,
            "usage_source": self.usage_source,
            "cache_source": self.cache_source,
        }


def _as_mapping(value: Any) -> Optional[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, Mapping):
                return dumped
        except Exception:
            return None
    return None


def _int_field(data: Mapping[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            continue
    return None


def _nested_mapping(data: Mapping[str, Any], *keys: str) -> Optional[Mapping[str, Any]]:
    for key in keys:
        value = _as_mapping(data.get(key))
        if value is not None:
            return value
    return None


def normalize_usage_payload(payload: Any) -> Optional[NormalizedUsage]:
    """从各类 OpenAI 兼容 usage 载荷中提取统一 token 字段。"""
    usage = _as_mapping(payload)
    if not usage:
        return None

    prompt_tokens = _int_field(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_field(usage, "completion_tokens", "output_tokens")
    total_tokens = _int_field(usage, "total_tokens")

    details = _nested_mapping(
        usage,
        "prompt_tokens_details",
        "input_tokens_details",
        "input_token_details",
    )
    cached_prompt_tokens = _int_field(
        usage,
        "prompt_cache_hit_tokens",
        "cached_prompt_tokens",
        "cache_read_input_tokens",
        "cached_content_token_count",
        "cachedContentTokenCount",
    )
    if cached_prompt_tokens is None and details:
        cached_prompt_tokens = _int_field(
            details,
            "cached_tokens",
            "cache_read_tokens",
            "cached_input_tokens",
            "cached_prompt_tokens",
        )

    cache_miss_prompt_tokens = _int_field(
        usage,
        "prompt_cache_miss_tokens",
        "cache_creation_input_tokens",
    )
    if cache_miss_prompt_tokens is None and details:
        cache_miss_prompt_tokens = _int_field(
            details,
            "cache_miss_tokens",
            "cache_creation_tokens",
            "uncached_tokens",
        )

    if prompt_tokens is None and cache_miss_prompt_tokens is not None:
        prompt_tokens = (cached_prompt_tokens or 0) + cache_miss_prompt_tokens
    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None

    normalized = NormalizedUsage(
        prompt_tokens=prompt_tokens or 0,
        completion_tokens=completion_tokens or 0,
        total_tokens=total_tokens or ((prompt_tokens or 0) + (completion_tokens or 0)),
        cached_prompt_tokens=cached_prompt_tokens or 0,
        cache_miss_prompt_tokens=cache_miss_prompt_tokens,
        usage_source="upstream",
        cache_source="upstream" if (cached_prompt_tokens or 0) > 0 or cache_miss_prompt_tokens is not None else None,
    )
    return normalized


def iter_usage_payloads_from_llm_result(response: Any):
    """从 LangChain LLMResult 的常见位置枚举 usage 载荷。"""
    llm_output = _as_mapping(getattr(response, "llm_output", None)) or {}
    for key in ("token_usage", "usage", "usage_metadata"):
        value = llm_output.get(key)
        if value:
            yield value

    generations = getattr(response, "generations", None) or []
    for generation_list in generations:
        for generation in generation_list or []:
            message = getattr(generation, "message", None)
            if message is None:
                continue
            usage_metadata = getattr(message, "usage_metadata", None)
            if usage_metadata:
                yield usage_metadata
            response_metadata = _as_mapping(getattr(message, "response_metadata", None)) or {}
            for key in ("token_usage", "usage", "usage_metadata"):
                value = response_metadata.get(key)
                if value:
                    yield value


def extract_usage_from_llm_result(response: Any) -> Optional[NormalizedUsage]:
    """按优先级从 LLMResult 中提取真实上游 usage。"""
    for payload in iter_usage_payloads_from_llm_result(response):
        usage = normalize_usage_payload(payload)
        if usage is not None:
            return usage
    return None
