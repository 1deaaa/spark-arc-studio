"""
聊天后台任务管理器。

核心职责：
- 维护活跃聊天任务的注册表（后台线程 + 进度队列）
- 提供注册 / 查询 / 取消 / 清理操作
- 前端断连后任务继续运行，只有显式 cancel 才会停止

设计参考：auto_write.py 的 _auto_write_stop_events / _auto_write_progress_queues 模式，
但针对聊天场景做了简化（无需章节/场景进度，只需事件队列 + 状态）。
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChatTaskEntry:
    """单个聊天后台任务的元数据与运行时状态。"""

    task_key: str  # user_id:project_name:agent_id:context_key
    user_id: str
    project_name: str
    agent_id: str
    context_key: str
    stop_event: threading.Event
    progress_queue: queue.Queue  # 事件队列，None 为结束哨兵
    status: str  # running | completed | cancelled | error
    started_at: float

    # 完成后的元数据（供 task-status 查询）
    result_message_id: Optional[int] = None
    result_content: str = ''
    result_metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ''

    # 重试次数（0 表示未重试，1-3 表示已重试次数）
    retry_count: int = 0

    # 事件类型标记：send 或 edit
    channel: str = 'direct_reply_stream'


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


def list_running_tasks(user_id: str, project_name: str) -> list[ChatTaskEntry]:
    """列出指定用户+项目下所有 running 状态的任务。"""
    with _registry_lock:
        return [
            entry for entry in _active_chat_tasks.values()
            if entry.user_id == user_id and entry.project_name == project_name and entry.status == 'running'
        ]


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
    }
    if entry.result_message_id is not None:
        payload['resultMessageId'] = entry.result_message_id
    if entry.result_content:
        payload['resultContent'] = entry.result_content
    return payload
