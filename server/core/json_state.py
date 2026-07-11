from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator, TypeVar


_STATE_LOCKS: dict[str, threading.RLock] = {}
_STATE_LOCKS_GUARD = threading.Lock()
_T = TypeVar("_T")


def _normalized_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def get_json_state_lock(path: str) -> threading.RLock:
    """返回指定状态文件的进程内可重入锁。"""
    key = _normalized_path(path)
    with _STATE_LOCKS_GUARD:
        lock = _STATE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _STATE_LOCKS[key] = lock
        return lock


@contextmanager
def json_state_lock(path: str) -> Iterator[None]:
    """在同一进程内串行化指定 JSON 状态文件的读改写事务。"""
    with get_json_state_lock(path):
        yield


def synchronized_json_state(method: Callable[..., _T]) -> Callable[..., _T]:
    """将实例方法串行化到 ``self.state_path`` 对应的状态锁。"""
    @wraps(method)
    def wrapped(self, *args: Any, **kwargs: Any) -> _T:
        with json_state_lock(str(self.state_path)):
            return method(self, *args, **kwargs)

    return wrapped


def load_json_file(path: str, default_factory: Callable[[], _T]) -> _T:
    """在状态锁内读取 JSON；文件不存在或损坏时返回默认值。"""
    with json_state_lock(path):
        if not os.path.exists(path):
            return default_factory()
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return default_factory()


def save_json_file_atomic(path: str, payload: Any, *, indent: int = 2) -> None:
    """刷新并原子替换 JSON 文件，避免读取方看到半写入内容。"""
    with json_state_lock(path):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temporary_path = f"{path}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=indent)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
