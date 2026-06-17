"""
MCP 导演任务管理器。

这里把 MCP 侧的导演调用建模为“远程工单”，而不是同步聊天返回。
外部客户端提交任务后立即拿到 task_id，再通过查询接口读取状态、事件和结果。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.routes.chat_persistence import ChatStreamAccumulator
from mcp_server.shared.tool_adapter import ensure_query_context


TERMINAL_STATUSES = {"completed", "cancelled", "error"}


@dataclass
class DirectorTaskEntry:
    """一个 MCP 导演远程工单的运行态。"""

    task_id: str
    user_id: str
    project_name: str
    instruction: str
    intent: str
    return_style: str
    stop_event: threading.Event
    status: str = "queued"
    phase: str = "queued"
    current_agent: str = ""
    summary: str = "任务已排队。"
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    error_message: str = ""
    event_log: list[dict[str, Any]] = field(default_factory=list)
    next_seq: int = 0
    accumulator: ChatStreamAccumulator = field(init=False)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        self.accumulator = ChatStreamAccumulator(
            channel="mcp_director_task",
            task_id=self.task_id,
        )

    def append_event(self, event: Any) -> dict[str, Any]:
        if isinstance(event, dict):
            payload = dict(event)
        elif isinstance(event, str):
            payload = {"event": "assistant_delta", "text": event}
        else:
            payload = {"event": "assistant_delta", "text": str(event)}

        with self.lock:
            self.next_seq += 1
            payload["seq"] = self.next_seq
            payload["task_id"] = self.task_id
            self.event_log.append(payload)
            self.accumulator.append_event(payload, seq=self.next_seq)
            self.updated_at = time.time()
            self._refresh_progress_from_event(payload)
            return dict(payload)

    def _refresh_progress_from_event(self, event: dict[str, Any]) -> None:
        event_name = str(event.get("event") or "").strip()
        source_agent = str(event.get("source_agent") or "").strip()
        if source_agent:
            self.current_agent = source_agent

        if event_name == "agent_turn_started":
            self.phase = "agent_turn"
            self.summary = f"{source_agent or 'Agent'} 正在处理任务。"
        elif event_name in {"tool_intent_started", "tool_exec_started"}:
            tool_name = str(event.get("tool_name") or "").strip()
            self.phase = "tool_running"
            self.summary = f"正在调用工具 {tool_name}。" if tool_name else "正在调用工具。"
        elif event_name == "tool_exec_finished":
            tool_name = str(event.get("tool_name") or "").strip()
            self.phase = "tool_finished"
            self.summary = f"工具 {tool_name} 已完成。" if tool_name else "工具调用已完成。"
        elif event_name == "tool_exec_failed":
            tool_name = str(event.get("tool_name") or "").strip()
            self.phase = "tool_failed"
            self.summary = f"工具 {tool_name} 调用失败。" if tool_name else "工具调用失败。"
        elif event_name == "director_auto_write_started":
            self.phase = "background_auto_write_started"
            self.summary = "导演已启动后台自动写作任务。"
        elif event_name == "error":
            self.phase = "error"
            self.summary = "导演任务发生错误。"

    def events_after(self, after_seq: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        cursor = max(0, int(after_seq or 0))
        capped = max(1, min(int(limit or 50), 200))
        with self.lock:
            return [dict(evt) for evt in self.event_log if int(evt.get("seq") or 0) > cursor][:capped]

    def status_payload(self, *, include_latest_events: bool = True) -> dict[str, Any]:
        with self.lock:
            payload = {
                "task_id": self.task_id,
                "project_name": self.project_name,
                "status": self.status,
                "phase": self.phase,
                "current_agent": self.current_agent,
                "summary": self.summary,
                "started_at": self.started_at,
                "updated_at": self.updated_at,
                "finished_at": self.finished_at,
                "last_seq": self.next_seq,
                "error": self.error_message,
                "result_available": self.status in TERMINAL_STATUSES,
            }
            if include_latest_events:
                payload["latest_events"] = [dict(evt) for evt in self.event_log[-10:]]
            return payload

    def result_payload(self) -> dict[str, Any]:
        with self.lock:
            metadata = self.accumulator.build_metadata(stream_status=self.status)
            changed_artifacts = _collect_changed_artifacts(self.event_log)
            return {
                "task_id": self.task_id,
                "project_name": self.project_name,
                "status": self.status,
                "user_summary": self.accumulator.content,
                "operator_summary": self.summary,
                "changed_artifacts": changed_artifacts,
                "tool_calls": metadata.get("tool_traces", []),
                "warnings": _collect_warnings(self.event_log, self.error_message),
                "last_seq": self.next_seq,
                "error": self.error_message,
            }


_tasks: dict[str, DirectorTaskEntry] = {}
_lock = threading.RLock()


def submit_director_task(
    *,
    user_id: str,
    project_name: str,
    instruction: str,
    intent: str = "execute",
    return_style: str = "brief",
) -> dict[str, Any]:
    """提交导演远程工单，立即返回任务状态。"""
    task_id = f"dt_{uuid.uuid4().hex}"
    entry = DirectorTaskEntry(
        task_id=task_id,
        user_id=str(user_id),
        project_name=str(project_name or "").strip(),
        instruction=str(instruction or "").strip(),
        intent=_normalize_intent(intent),
        return_style=_normalize_return_style(return_style),
        stop_event=threading.Event(),
    )
    with _lock:
        _tasks[task_id] = entry
    entry.append_event({
        "event": "task_submitted",
        "status": "queued",
        "message": "导演任务已提交。",
    })
    thread = threading.Thread(
        target=_run_task,
        args=(entry,),
        daemon=True,
        name=f"mcp_director_{task_id}",
    )
    thread.start()
    return entry.status_payload(include_latest_events=False)


def get_director_task(task_id: str) -> dict[str, Any]:
    entry = _get_task_or_none(task_id)
    if not entry:
        return {"error": f"未找到导演任务：{task_id}"}
    return entry.status_payload()


def list_director_tasks(
    *,
    user_id: str,
    project_name: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    wanted_project = str(project_name or "").strip()
    wanted_status = str(status or "").strip()
    with _lock:
        entries = list(_tasks.values())
    result = []
    for entry in entries:
        if entry.user_id != str(user_id):
            continue
        if wanted_project and entry.project_name != wanted_project:
            continue
        if wanted_status and entry.status != wanted_status:
            continue
        result.append(entry.status_payload(include_latest_events=False))
    result.sort(key=lambda item: float(item.get("started_at") or 0), reverse=True)
    return result


def read_director_task_events(task_id: str, after_seq: int = 0, limit: int = 50) -> dict[str, Any]:
    entry = _get_task_or_none(task_id)
    if not entry:
        return {"error": f"未找到导演任务：{task_id}", "events": []}
    return {
        "task_id": entry.task_id,
        "status": entry.status,
        "last_seq": entry.next_seq,
        "events": entry.events_after(after_seq=after_seq, limit=limit),
    }


def read_director_task_result(task_id: str) -> dict[str, Any]:
    entry = _get_task_or_none(task_id)
    if not entry:
        return {"error": f"未找到导演任务：{task_id}"}
    return entry.result_payload()


def cancel_director_task(task_id: str) -> dict[str, Any]:
    entry = _get_task_or_none(task_id)
    if not entry:
        return {"error": f"未找到导演任务：{task_id}", "cancelled": False}
    with entry.lock:
        if entry.status in TERMINAL_STATUSES:
            return {
                "task_id": entry.task_id,
                "status": entry.status,
                "cancelled": False,
                "message": "任务已经结束，无法取消。",
            }
        entry.stop_event.set()
        entry.status = "cancelled"
        entry.phase = "cancel_requested"
        entry.summary = "已请求取消导演任务。"
        entry.finished_at = time.time()
    entry.append_event({"event": "task_cancel_requested", "status": "cancelled"})
    return {
        "task_id": entry.task_id,
        "status": entry.status,
        "cancelled": True,
        "message": "已请求取消导演任务。",
    }


def _run_task(entry: DirectorTaskEntry) -> None:
    from agents.agent_factory import create_agent_instance

    ensure_query_context(entry.user_id, entry.project_name)
    with entry.lock:
        entry.status = "running"
        entry.phase = "director_starting"
        entry.summary = "导演正在接收远程工单。"
        entry.updated_at = time.time()
    entry.append_event({
        "event": "task_started",
        "status": "running",
        "intent": entry.intent,
        "return_style": entry.return_style,
    })

    try:
        director = create_agent_instance("agent_director", entry.user_id, entry.project_name)
        user_message = _build_director_instruction(entry)
        for event in director.chat_stream(
            user_message=user_message,
            history=None,
            active_context="",
            skip_tool_confirmation=entry.intent == "execute",
            stop_event=entry.stop_event,
        ):
            if entry.stop_event.is_set():
                break
            entry.append_event(event)

        if entry.stop_event.is_set():
            with entry.lock:
                entry.status = "cancelled"
                entry.phase = "cancelled"
                entry.summary = "导演任务已取消。"
                entry.finished_at = time.time()
                entry.updated_at = entry.finished_at
            entry.append_event({"event": "task_cancelled", "status": "cancelled"})
            return

        with entry.lock:
            entry.status = "completed"
            entry.phase = "completed"
            entry.summary = "导演任务已完成。"
            entry.finished_at = time.time()
            entry.updated_at = entry.finished_at
        entry.append_event({"event": "task_done", "status": "completed"})
    except Exception as exc:
        with entry.lock:
            entry.status = "error"
            entry.phase = "error"
            entry.error_message = str(exc)
            entry.summary = "导演任务执行失败。"
            entry.finished_at = time.time()
            entry.updated_at = entry.finished_at
        entry.append_event({"event": "error", "data": str(exc), "status": "error"})


def _build_director_instruction(entry: DirectorTaskEntry) -> str:
    style_instruction = (
        "请用面向远程操作者的简短执行报告收束，列出已完成事项、改动位置、后续建议。"
        if entry.return_style == "report"
        else "请用简短结果摘要收束，避免长篇寒暄。"
    )
    intent_instruction = {
        "discuss": "本次是远程讨论任务：优先澄清方案和风险，除非用户明确要求，不主动落盘。",
        "plan": "本次是远程规划任务：优先形成执行计划和检查清单，必要时可读取项目内容。",
        "execute": "本次是远程执行任务：若意图明确，请按导演调度链路委派专家并完成必要落盘。",
    }.get(entry.intent, "本次是远程执行任务。")
    return "\n".join([
        "【MCP 远程工单】",
        intent_instruction,
        style_instruction,
        "",
        "用户指令：",
        entry.instruction,
    ])


def _normalize_intent(value: str) -> str:
    normalized = str(value or "execute").strip().lower()
    return normalized if normalized in {"discuss", "plan", "execute"} else "execute"


def _normalize_return_style(value: str) -> str:
    normalized = str(value or "brief").strip().lower()
    return normalized if normalized in {"brief", "report"} else "brief"


def _get_task_or_none(task_id: str) -> DirectorTaskEntry | None:
    with _lock:
        return _tasks.get(str(task_id or "").strip())


def _collect_changed_artifacts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for event in events:
        if str(event.get("event") or "") != "tool_exec_finished":
            continue
        scope = str(event.get("ui_scope") or "").strip()
        target = str(event.get("ui_target") or "").strip()
        refresh_events = event.get("ui_refresh_events") or []
        if not scope and not refresh_events:
            continue
        key = (scope, target)
        if key in seen:
            continue
        seen.add(key)
        artifacts.append({
            "scope": scope,
            "target": target,
            "refresh_events": list(refresh_events) if isinstance(refresh_events, list) else [],
            "tool_name": event.get("tool_name", ""),
        })
    return artifacts


def _collect_warnings(events: list[dict[str, Any]], error_message: str = "") -> list[str]:
    warnings: list[str] = []
    if error_message:
        warnings.append(error_message)
    for event in events:
        if str(event.get("event") or "") == "tool_exec_failed":
            tool_name = str(event.get("tool_name") or "工具").strip()
            message = str(event.get("message") or event.get("error") or "调用失败").strip()
            warnings.append(f"{tool_name}: {message}")
    return warnings
