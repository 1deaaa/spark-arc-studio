"""兼容入口：业务流语义协议已下沉到 ``agents.stream_semantics``。"""

from agents.stream_semantics import (
    merge_semantics,
    on_cancelled,
    on_delta,
    on_done,
    on_error,
    on_progress,
    on_start,
    on_stats,
    semantic_event_data,
    semantic_payload,
    semantic_sse_data,
)


__all__ = [
    "merge_semantics",
    "on_cancelled",
    "on_delta",
    "on_done",
    "on_error",
    "on_progress",
    "on_start",
    "on_stats",
    "semantic_event_data",
    "semantic_payload",
    "semantic_sse_data",
]
