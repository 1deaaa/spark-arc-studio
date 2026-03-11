from __future__ import annotations

import time
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from .stream_semantics import (
    merge_semantics,
    on_cancelled,
    on_done,
    on_error,
    on_start,
    on_stats,
)


def task_cancelled_event(message: str = "任务已取消", **extra: Any) -> dict[str, Any]:
    return {
        "event": "cancelled",
        "data": {
            "status": "cancelled",
            **merge_semantics(on_cancelled(message, **extra)),
        },
    }


def task_done_event(message: str = "", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "complete"}
    payload.update(extra)
    payload.update(merge_semantics(on_done(message, **extra)))
    return {
        "event": "done",
        "data": payload,
    }


def task_error_event(message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": "error", "error": message}
    payload.update(extra)
    payload.update(merge_semantics(on_error(message, **extra)))
    return {
        "event": "error",
        "data": payload,
    }


async def maybe_emit_cancelled(
    *,
    stop_event: threading.Event,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
    message: str = "任务已取消",
    **extra: Any,
) -> bool:
    if not stop_event.is_set():
        return False
    await emit(task_cancelled_event(message, **extra))
    return True


def build_stats_payload(started_at: float, chars: int | float = 0) -> dict[str, Any]:
    elapsed = max(time.monotonic() - started_at, 0.001)
    total_chars = max(float(chars or 0), 0.0)
    speed = round(total_chars / elapsed, 2)
    return merge_semantics(
        on_stats(chars=int(total_chars), elapsed=round(elapsed, 2), speed=speed)
    )


def build_started_payload(message: str, **extra: Any) -> dict[str, Any]:
    return {
        "status": "started",
        **merge_semantics(on_start(message, **extra)),
    }
