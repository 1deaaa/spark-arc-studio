"""
流式语义事件辅助工具。

目标：
- 不强制所有路由统一为同一种协议；
- 但允许 SSE / NDJSON 路由以低侵入方式补充统一 onXxx 语义字段；
- 让前端统一消费器优先依赖语义层，而不是后端具体事件名。
"""

from __future__ import annotations

import json
from typing import Any, Dict


def semantic_payload(status: str | None = None, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if status is not None:
        payload["status"] = status
    payload.update(extra)
    return payload


def semantic_sse_data(status: str | None = None, **extra: Any) -> str:
    return (
        f"data: {json.dumps(semantic_payload(status, **extra), ensure_ascii=False)}\n\n"
    )


def semantic_event_data(
    event: str, status: str | None = None, **extra: Any
) -> Dict[str, str]:
    return {
        "event": event,
        "data": json.dumps(semantic_payload(status, **extra), ensure_ascii=False),
    }


def on_start(message: str, **extra: Any) -> Dict[str, Any]:
    return {"onStart": {"message": message, **extra}}


def on_progress(message: str, stage: str = "", **extra: Any) -> Dict[str, Any]:
    payload = {"message": message}
    if stage:
        payload["stage"] = stage
    payload.update(extra)
    return {"onProgress": payload}


def on_delta(text: str, **extra: Any) -> Dict[str, Any]:
    return {"onDelta": {"text": text, **extra}}


def on_stats(
    chars: int | float = 0,
    elapsed: float | int = 0,
    speed: float | int = 0,
    label: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chars": chars,
        "elapsed": elapsed,
        "speed": speed,
    }
    if label:
        payload["label"] = label
    payload.update(extra)
    return {"onStats": payload}


def on_done(message: str = "", **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if message:
        payload["message"] = message
    payload.update(extra)
    return {"onDone": payload}


def on_error(message: str, **extra: Any) -> Dict[str, Any]:
    return {"onError": {"message": message, **extra}}


def on_cancelled(message: str = "", **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if message:
        payload["message"] = message
    payload.update(extra)
    return {"onCancelled": payload}


def merge_semantics(*parts: Dict[str, Any] | None, **extra: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for part in parts:
        if part:
            merged.update(part)
    merged.update(extra)
    return merged
