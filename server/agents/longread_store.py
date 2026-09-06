"""任务内线索账本的内存流转层。

为什么需要这一层：
- LangChain 工具函数签名是纯函数式的，不能直接持有跨调用的内存对象；
- 但账本在任务进行中必须零 IO（否则每次记账都读写磁盘，前缀缓存和
  延迟都受影响），只在任务终态落盘一次；
- 因此用 ContextVar 承载“当前任务的账本”，工具调用只 append 内存，
  路由层在任务结束时一次性 ``LedgerStore.save``。

生命周期（调用方 = chat 路由 / director 图）：
1. 任务开始：``init_task_ledger(user_id, project_name, key)`` 从落盘恢复；
2. 任务进行：``load_task_ledger`` / ``append_ledger_entries`` 纯内存操作；
3. 任务终态：``take_task_ledger`` 取出并 ``LedgerStore.save`` 一次。
"""

from __future__ import annotations

import contextvars
from typing import Sequence

from agents.longread import ClueLedger, LedgerStore, WindowClue, ledger_key


_current_task_ledger: contextvars.ContextVar[ClueLedger | None] = (
    contextvars.ContextVar("current_task_ledger", default=None)
)
_current_task_ledger_key: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("current_task_ledger_key", default=None)
)


def init_task_ledger(
    user_id: str,
    project_name: str,
    agent_id: str,
    context_key: str,
    *,
    max_entries: int = 64,
) -> ClueLedger:
    """任务开始时从落盘恢复账本并挂到当前任务上下文。"""
    from core.project_settings import LONGREAD_LEDGER_MAX_ENTRIES

    key = ledger_key(str(user_id), str(project_name), str(agent_id), str(context_key))
    ledger = LedgerStore.load(
        str(user_id),
        str(project_name),
        key,
        max_entries=max(1, int(max_entries or LONGREAD_LEDGER_MAX_ENTRIES)),
    )
    _current_task_ledger.set(ledger)
    _current_task_ledger_key.set(key)
    return ledger


def load_task_ledger(user_id: str, project_name: str) -> ClueLedger | None:
    """返回当前任务的账本；任务外调用返回 None，工具侧自行新建内存账本。"""
    _ = (user_id, project_name)
    return _current_task_ledger.get(None)


def task_ledger_key() -> str | None:
    return _current_task_ledger_key.get(None)


def append_ledger_entries(entries: Sequence[WindowClue]) -> None:
    ledger = _current_task_ledger.get(None)
    if ledger is None or not entries:
        return
    for item in entries:
        if item not in ledger.entries:
            ledger.entries.append(item)
    overflow = len(ledger.entries) - max(1, int(ledger.max_entries or 64))
    if overflow > 0:
        del ledger.entries[:overflow]


def take_task_ledger() -> tuple[ClueLedger | None, str | None]:
    """取出当前任务账本并清空上下文；调用方负责终态落盘。"""
    ledger = _current_task_ledger.get(None)
    key = _current_task_ledger_key.get(None)
    _current_task_ledger.set(None)
    _current_task_ledger_key.set(None)
    return ledger, key


def reset_task_ledger() -> None:
    _current_task_ledger.set(None)
    _current_task_ledger_key.set(None)


__all__ = [
    "append_ledger_entries",
    "init_task_ledger",
    "load_task_ledger",
    "reset_task_ledger",
    "take_task_ledger",
    "task_ledger_key",
]
