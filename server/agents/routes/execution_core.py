"""
Execution Core API - 业务流语义事件的标准构造层。

════════════════════════════════════════════════════════════════════════
【架构定位：业务语义流 (Stream Semantics) 的工厂适配器】

本项目通过 `stream_semantics.py` 规定了长连接业务流（SSE/NDJSON）的标准字段结构，
而本文件则在此标准之上，为主干业务逻辑提供了开箱即用的工厂方法。

职责包括：
1. 终态封装：`task_cancelled_event` / `task_done_event` / `task_error_event`，
   为生命周期的最后一帧统一注入标准的 `status` 字段并合并语义帧。
2. 性能打点：`build_stats_payload`，封装了统一的平均速度和耗时计算逻辑，供前端展示进度仪表盘。
3. 异常截断：`maybe_emit_cancelled`，在检测到异步协程的停止信号时快速安全地向客户端发送结束帧。

这是连接【底层流协议】与【顶层业务】之间不可或缺的润滑剂，确保了各业务线吐出的事件
结构具备高度的一致性。
════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import time
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from agents.stream_semantics import (
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
