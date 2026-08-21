from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

from core.request_context import (
    current_project_name,
    current_user_id,
    set_current_export_format,
)


AUTO_WRITE_EVENT_LOG_LIMIT = 2048
AutoWriteTaskKey = tuple[str, str]


@dataclass
class AutoWriteTaskEntry:
    user_id: str
    project_name: str
    stop_event: threading.Event = field(default_factory=threading.Event)
    events: list[tuple[int, str]] = field(default_factory=list)
    next_seq: int = 1
    done: bool = False
    thread: threading.Thread | None = None
    condition: threading.Condition = field(default_factory=threading.Condition)

    def append(self, event: str) -> None:
        with self.condition:
            self.events.append((self.next_seq, event))
            self.next_seq += 1
            if len(self.events) > AUTO_WRITE_EVENT_LOG_LIMIT:
                del self.events[: len(self.events) - AUTO_WRITE_EVENT_LOG_LIMIT]
            self.condition.notify_all()

    def finish(self) -> None:
        with self.condition:
            self.done = True
            self.condition.notify_all()

    def wait_after(self, after_seq: int, timeout: float) -> tuple[list[tuple[int, str]], bool]:
        with self.condition:
            available = [item for item in self.events if item[0] > after_seq]
            if not available and not self.done:
                self.condition.wait(timeout=timeout)
                available = [item for item in self.events if item[0] > after_seq]
            return available, self.done


@dataclass(frozen=True)
class AutoWriteStartResult:
    started: bool
    entry: AutoWriteTaskEntry | None = None
    error: str = ""


_TASKS: dict[AutoWriteTaskKey, AutoWriteTaskEntry] = {}
_TASKS_LOCK = threading.RLock()
_AUTO_WRITE_RUNNER: Callable[..., Any] | None = None


def _task_key(user_id: str, project_name: str) -> AutoWriteTaskKey:
    return str(user_id), str(project_name)


def get_auto_write_task(user_id: str, project_name: str) -> AutoWriteTaskEntry | None:
    with _TASKS_LOCK:
        return _TASKS.get(_task_key(user_id, project_name))


def is_auto_write_running(user_id: str, project_name: str) -> bool:
    entry = get_auto_write_task(user_id, project_name)
    return bool(entry and not entry.done and entry.thread and entry.thread.is_alive())


def configure_auto_write_runner(runner: Callable[..., Any]) -> None:
    """由应用层注册自动写作执行器，避免后台服务反向依赖 HTTP 路由。"""
    if not callable(runner):
        raise TypeError("自动写作执行器必须可调用")
    global _AUTO_WRITE_RUNNER
    with _TASKS_LOCK:
        _AUTO_WRITE_RUNNER = runner


def start_auto_write_background(
    *,
    user_id: str,
    project_name: str,
    outline: Dict[str, Any],
    mode: str,
    start_chapter_index: int,
    start_scene_index: int,
    export_format: str,
    context_strategy: str = "accumulate",
    auto_review: bool = False,
    from_director: bool = True,
) -> AutoWriteStartResult:
    """通过唯一后台任务服务启动自动写作。"""
    key = _task_key(user_id, project_name)
    with _TASKS_LOCK:
        runner = _AUTO_WRITE_RUNNER
        if runner is None:
            return AutoWriteStartResult(
                started=False,
                error="自动写作执行器尚未初始化",
            )
        existing = _TASKS.get(key)
        if existing and not existing.done and existing.thread and existing.thread.is_alive():
            return AutoWriteStartResult(started=False, entry=existing, error="该项目已有自动撰写任务正在运行")

        entry = AutoWriteTaskEntry(user_id=str(user_id), project_name=project_name)
        _TASKS[key] = entry

        thread = threading.Thread(
            target=_run_auto_write,
            kwargs={
                "entry": entry,
                "runner": runner,
                "outline": outline,
                "mode": mode,
                "start_chapter_index": start_chapter_index,
                "start_scene_index": start_scene_index,
                "export_format": export_format,
                "context_strategy": context_strategy,
                "auto_review": auto_review,
                "from_director": from_director,
            },
            daemon=True,
            name=f"auto_write_{user_id}_{project_name}",
        )
        entry.thread = thread
        thread.start()
        return AutoWriteStartResult(started=True, entry=entry)


def _run_auto_write(
    *,
    entry: AutoWriteTaskEntry,
    runner: Callable[..., Any],
    outline: Dict[str, Any],
    mode: str,
    start_chapter_index: int,
    start_scene_index: int,
    export_format: str,
    context_strategy: str,
    auto_review: bool,
    from_director: bool,
) -> None:
    current_user_id.set(entry.user_id)
    current_project_name.set(entry.project_name)
    set_current_export_format(export_format)

    async def _drain() -> None:
        try:
            async for event in runner(
                user_id=entry.user_id,
                project_name=entry.project_name,
                outline=outline,
                request=None,
                mode=mode,
                start_chapter_index=start_chapter_index,
                start_scene_index=start_scene_index,
                context_strategy=context_strategy,
                export_format=export_format,
                auto_review=auto_review,
                from_director=from_director,
                stop_event=entry.stop_event,
                prewrite_tool_callback=lambda payload: entry.append(
                    _prewrite_tool_event(payload)
                ),
            ):
                if not event.lstrip().startswith(":"):
                    entry.append(event)
        except Exception as exc:
            from agents.error_formatting import format_ai_error
            from agents.stream_semantics import on_error, semantic_sse_data

            friendly = format_ai_error(exc)
            entry.append(semantic_sse_data("error", message=friendly, **on_error(friendly)))
        finally:
            entry.finish()

    asyncio.run(_drain())


def _prewrite_tool_event(payload: dict[str, Any]) -> str:
    """把写前调研工具调用转换为可回放的业务语义帧。"""
    from agents.stream_semantics import semantic_sse_data

    return semantic_sse_data(
        "prewrite_tool",
        tool_name=str(payload.get("tool_name") or ""),
        chapter_index=payload.get("chapter_index"),
        scene_index=payload.get("scene_index"),
        chapter_title=str(payload.get("chapter_title") or ""),
        scene_title=str(payload.get("scene_title") or ""),
    )


def stop_auto_write(user_id: str, project_name: str) -> bool:
    entry = get_auto_write_task(user_id, project_name)
    if not entry or entry.done:
        return False
    entry.stop_event.set()
    return True


def cancel_auto_write_background(
    user_id: str,
    project_name: str,
    *,
    wait_timeout: float = 4.0,
) -> bool:
    """停止项目自动写作并等待后台线程释放项目文件。"""
    entry = get_auto_write_task(user_id, project_name)
    if not entry or entry.done:
        return True
    entry.stop_event.set()
    thread = entry.thread
    if thread and thread is not threading.current_thread():
        thread.join(timeout=max(0.0, wait_timeout))
    return bool(entry.done or not thread or not thread.is_alive())


async def observe_auto_write_progress(user_id: str, project_name: str, after_seq: int = 0):
    """从追加式事件日志观察进度；断线重连可以按序号续读。"""
    entry = get_auto_write_task(user_id, project_name)
    if entry is None:
        from agents.stream_semantics import semantic_sse_data

        yield semantic_sse_data("idle", message="没有正在运行的自动撰写任务")
        return

    cursor = max(0, int(after_seq or 0))
    while True:
        events, done = await asyncio.to_thread(entry.wait_after, cursor, 3.0)
        if events:
            for seq, event in events:
                cursor = seq
                yield _with_stream_seq(event, seq)
            continue
        if done:
            return
        yield ": heartbeat\n\n"


def _with_stream_seq(event: str, seq: int) -> str:
    """给标准单帧 SSE 数据补充可恢复游标。"""
    data_lines = [line[5:].lstrip() for line in event.splitlines() if line.startswith("data:")]
    if not data_lines:
        return event
    try:
        payload = json.loads("\n".join(data_lines))
    except Exception:
        return event
    if not isinstance(payload, dict):
        return event
    payload["streamSeq"] = seq
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def load_auto_write_status(user_id: str, project_name: str) -> Dict[str, Any]:
    from agents.auto_write_state import load_auto_write_state

    return load_auto_write_state(user_id, project_name)
