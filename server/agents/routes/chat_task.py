"""
聊天后台任务管理器。

核心职责：
- 维护活跃聊天任务的注册表、可重放事件日志与运行时快照
- 提供注册 / 查询 / 取消 / 清理操作
- 前端断连后任务继续运行，只有显式 cancel 才会停止
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .chat_persistence import ChatStreamAccumulator


@dataclass
class ChatTaskEntry:
    """单个聊天后台任务的元数据与运行时状态。"""

    task_key: str  # user_id:project_name:agent_id:context_key
    user_id: str
    project_name: str
    agent_id: str
    context_key: str
    stop_event: threading.Event
    status: str  # running | completed | cancelled | error
    started_at: float

    # 完成后的元数据（供 task-status 查询）
    result_message_id: Optional[int] = None
    result_content: str = ''
    result_metadata: Dict[str, Any] = field(default_factory=dict)
    llm_usage: Optional[Dict[str, Any]] = None
    error_message: str = ''

    # 重试次数（0 表示未重试，1-3 表示已重试次数）
    retry_count: int = 0

    # 事件类型标记：send 或 edit
    channel: str = 'direct_reply_stream'

    # 稳定任务 ID 与可重放事件日志
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    assistant_message_id: Optional[int] = None
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    next_seq: int = 0
    accumulator: Optional[ChatStreamAccumulator] = None
    log_lock: threading.RLock = field(default_factory=threading.RLock)
    last_checkpoint_seq: int = 0
    last_checkpoint_at: float = 0.0

    def __post_init__(self) -> None:
        if self.accumulator is None:
            self.accumulator = ChatStreamAccumulator(channel=self.channel, task_id=self.task_id)

    def append_event(self, event: Any, *, accumulate: bool = True) -> Dict[str, Any]:
        """Append one NDJSON event to the replay log and update the accumulator."""
        if isinstance(event, dict):
            payload = dict(event)
        elif isinstance(event, str):
            payload = {"event": "assistant_delta", "text": event}
        else:
            payload = {"event": "assistant_delta", "text": str(event)}

        with self.log_lock:
            self.next_seq += 1
            payload["seq"] = self.next_seq
            payload["task_id"] = self.task_id
            if self.assistant_message_id is not None and "assistant_message_id" not in payload:
                payload["assistant_message_id"] = self.assistant_message_id
            self.event_log.append(payload)
            if accumulate and self.accumulator is not None:
                self.accumulator.append_event(payload, seq=self.next_seq)
            return dict(payload)

    def append_control_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return self.append_event(event, accumulate=False)

    def get_events_after(self, after_seq: int = 0) -> List[Dict[str, Any]]:
        cursor = int(after_seq or 0)
        with self.log_lock:
            return [dict(evt) for evt in self.event_log if int(evt.get("seq") or 0) > cursor]

    def build_snapshot(self) -> Dict[str, Any]:
        with self.log_lock:
            seq = self.next_seq
            if self.accumulator is None:
                self.accumulator = ChatStreamAccumulator(channel=self.channel, task_id=self.task_id)
            snapshot = self.accumulator.build_snapshot(
                status=self.status,
                assistant_message_id=self.assistant_message_id,
                seq=seq,
                error_message=self.error_message,
            )
            if self.llm_usage:
                snapshot["metadata"]["llm_usage"] = dict(self.llm_usage)
                snapshot["llm_usage"] = dict(self.llm_usage)
            return snapshot

    def build_metadata(self, *, stream_status: str | None = None) -> Dict[str, Any]:
        with self.log_lock:
            if self.accumulator is None:
                self.accumulator = ChatStreamAccumulator(channel=self.channel, task_id=self.task_id)
            metadata = self.accumulator.build_metadata(
                stream_status=stream_status or self.status,
                assistant_message_id=self.assistant_message_id,
            )
            if self.llm_usage:
                metadata["llm_usage"] = dict(self.llm_usage)
            return metadata

    def reset_for_retry(self) -> None:
        with self.log_lock:
            if self.accumulator is None:
                self.accumulator = ChatStreamAccumulator(channel=self.channel, task_id=self.task_id)
            self.accumulator.reset_for_retry()


# ─────────────────────────────────────────────────────────────────────────────
# 全局注册表
# ─────────────────────────────────────────────────────────────────────────────

_active_chat_tasks: Dict[str, ChatTaskEntry] = {}
_registry_lock = threading.Lock()


def _make_task_key(user_id: str, project_name: str, agent_id: str, context_key: str) -> str:
    return f"{user_id}:{project_name}:{agent_id}:{context_key}"


def register_task(entry: ChatTaskEntry) -> None:
    """注册新的聊天后台任务。如果同 key 已有 running 任务则抛 ValueError。"""
    with _registry_lock:
        existing = _active_chat_tasks.get(entry.task_key)
        if existing and existing.status == 'running':
            raise ValueError(f'聊天任务 {entry.task_key} 已在运行中')
        _active_chat_tasks[entry.task_key] = entry


def get_task(task_key: str) -> Optional[ChatTaskEntry]:
    """查询指定 key 的任务。"""
    with _registry_lock:
        return _active_chat_tasks.get(task_key)


def get_task_by_parts(user_id: str, project_name: str, agent_id: str, context_key: str) -> Optional[ChatTaskEntry]:
    """按组成部分查询任务。"""
    return get_task(_make_task_key(user_id, project_name, agent_id, context_key))


def cancel_task(task_key: str) -> bool:
    """取消指定任务（设置 stop_event）。返回 True 表示成功取消，False 表示任务不存在或已结束。"""
    with _registry_lock:
        entry = _active_chat_tasks.get(task_key)
    if not entry or entry.status != 'running':
        return False
    entry.stop_event.set()
    entry.append_control_event({"event": "task_cancel_requested", "status": "cancelled"})
    entry.status = 'cancelled'
    return True


def update_task_status(task_key: str, status: str, **fields: Any) -> None:
    """更新任务状态和字段。"""
    with _registry_lock:
        entry = _active_chat_tasks.get(task_key)
    if entry:
        entry.status = status
        for k, v in fields.items():
            if hasattr(entry, k):
                setattr(entry, k, v)


def cleanup_task(task_key: str, delay: float = 60.0) -> None:
    """延迟清理已结束的任务（给前端/观察者足够时间查询结果并重连）。"""
    def _do_cleanup():
        with _registry_lock:
            _active_chat_tasks.pop(task_key, None)
    threading.Timer(delay, _do_cleanup).start()


def list_recent_tasks(user_id: str, project_name: str) -> list[ChatTaskEntry]:
    """列出指定用户+项目下所有未清理的任务（running + completed/cancelled/error 尚未被 cleanup）。
    供前端恢复场景使用：running → 重连流；completed → 刷新历史获取结果。
    """
    with _registry_lock:
        return [
            entry for entry in _active_chat_tasks.values()
            if entry.user_id == user_id and entry.project_name == project_name
        ]


def build_task_status_payload(entry: ChatTaskEntry) -> Dict[str, Any]:
    """构建 task-status API 的返回载荷。"""
    payload: Dict[str, Any] = {
        'hasTask': True,
        'status': entry.status,
        'agentId': entry.agent_id,
        'contextKey': entry.context_key,
        'channel': entry.channel,
        'startedAt': entry.started_at,
        'error': entry.error_message,
        'retryCount': entry.retry_count,
        'taskId': entry.task_id,
        'assistantMessageId': entry.assistant_message_id,
        'lastSeq': entry.next_seq,
    }
    if entry.result_message_id is not None:
        payload['resultMessageId'] = entry.result_message_id
    if entry.result_content:
        payload['resultContent'] = entry.result_content
    if entry.llm_usage:
        payload['llmUsage'] = dict(entry.llm_usage)
    return payload
