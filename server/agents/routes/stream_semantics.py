"""
流式语义事件辅助工具（Stream Semantics）

════════════════════════════════════════════════════════════════════════
【设计背景与目标】

本系统的流式响应分为两类协议，各有其用途：

  1. Chat NDJSON 流（chat.py）：
       用于聊天对话场景（POST /api/chat/send/stream 等）。
       事件以 {"event": "assistant_delta", "text": "..."} 等 NDJSON 格式推送。
       前端 chatStore.js 的 _consumeStream 负责解析并构建 segments 时序列表。

  2. 业务 SSE / NDJSON 流（本文件辅助的那类）：
       用于长耗时业务任务，如自动续写（auto_write.py）、正片生成（production.py）、
       风格分析（style.py）等。这类路由不走 chatStore，而是以独立的任务流形式
       向前端推送进度和内容。

本文件（stream_semantics.py）服务于第二类——提供一组"语义状态构造器"（on_xxx 函数），
让各业务路由以标准化方式描述任务的生命周期状态，实现前端统一消费。

════════════════════════════════════════════════════════════════════════
【onXxx 状态语义与前端消费规范】

每个 on_xxx 函数都返回一个字典，对应流中推送的单个语义帧。
前端（Vue）中的统一消费器（通常是一个 switch/if-else 块）按 key 解析这些帧：

  on_start(message)
      → { "onStart": { "message": "任务已启动" } }
      触发时机：任务开始（建立流连接后的第一帧）。
      前端动作：显示加载动画、重置进度状态。

  on_progress(message, stage="")
      → { "onProgress": { "message": "正在润色", "stage": "polish" } }
      触发时机：任务进入新阶段（如从"大纲生成"切换到"内容扩写"）。
      前端动作：更新进度条文字、阶段标签。

  on_delta(text)
      → { "onDelta": { "text": "当前生成的文字片段..." } }
      触发时机：每一块文本内容生成时（打字机效果的核心）。
      前端动作：将 text 追加到内容区域。

  on_stats(chars, elapsed, speed, label="")
      → { "onStats": { "chars": 512, "elapsed": 3.2, "speed": 160, "label": "..." } }
      触发时机：一个生成节点结束后（统计阶段性数据）。
      前端动作：更新右上角速度/字数/耗时统计显示。

  on_done(message="")
      → { "onDone": { "message": "任务完成" } }
      触发时机：流正常执行结束。
      前端动作：停止动画，标记任务完成，解锁 UI 交互。

  on_error(message)
      → { "onError": { "message": "出错原因..." } }
      触发时机：生成过程中捕获到无法恢复的异常。
      前端动作：弹出错误通知，显示红色错误状态。

  on_cancelled(message="")
      → { "onCancelled": { "message": "..." } }
      触发时机：用户或系统主动中断任务。
      前端动作：清除加载状态，更新 UI 为"已取消"。

  on_stats 可以在多个阶段分别发送，前端累加或替换显示均可。

════════════════════════════════════════════════════════════════════════
【与 Chat NDJSON 流的边界】

  聊天流（chat.py）和业务语义流（本文件）是两套独立协议，不要混用：

  - chat.py 的流事件使用 "event" 作为顶层键，值为 "assistant_delta" 等字面量；
  - 本文件的框架使用 "onStart" / "onDelta" 等作为顶层键；
  - 前端 chatStore.js 只解析 chat 流；业务页面各自解析语义流。

════════════════════════════════════════════════════════════════════════
【新增流式路由的接入规范（供开发者遵循）】

  若新增一个长耗时的业务 API（非聊天），推荐按以下模板组织 generate()：

    from .stream_semantics import on_start, on_progress, on_delta, on_stats, on_done, on_error, on_cancelled, merge_semantics
    from .streaming_utils import iterate_sync_iterable_in_thread

    async def generate():
        import json, time
        yield json.dumps(on_start("任务已启动"), ensure_ascii=False) + "\\n"
        try:
            async for chunk in iterate_sync_iterable_in_thread(lambda: agent.stream(...)):
                yield json.dumps(merge_semantics(on_delta(chunk)), ensure_ascii=False) + "\\n"
            yield json.dumps(on_done("生成完成"), ensure_ascii=False) + "\\n"
        except Exception as e:
            yield json.dumps(on_error(str(e)), ensure_ascii=False) + "\\n"

  semantic_sse_data() / semantic_event_data() 是等价的 SSE 格式辅助工具，
  如果接口走 text/event-stream 而非 NDJSON，可改用这两个函数。
════════════════════════════════════════════════════════════════════════
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
