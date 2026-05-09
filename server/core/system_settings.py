"""系统级配置存储。

当前用于保存与模型无关的全局开关，例如公开分享总开关。
配置文件路径：server/data/system_settings.json
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(BASE_DIR, "data", "system_settings.json")

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "disable_public_share": True,
    "force_public_share_review": True,
}

_lock = threading.Lock()


def _ensure_parent_dir() -> None:
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)


def _normalize(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    data = dict(_DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        data["disable_public_share"] = bool(raw.get("disable_public_share", _DEFAULT_SETTINGS["disable_public_share"]))
        data["force_public_share_review"] = bool(raw.get("force_public_share_review", _DEFAULT_SETTINGS["force_public_share_review"]))
    return data


def _load_settings() -> Dict[str, Any]:
    if not os.path.exists(SETTINGS_PATH):
        return dict(_DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _normalize(raw)
    except Exception:
        return dict(_DEFAULT_SETTINGS)


def _save_settings(data: Dict[str, Any]) -> None:
    _ensure_parent_dir()
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(_normalize(data), f, ensure_ascii=False, indent=2)


def get_system_settings() -> Dict[str, Any]:
    """读取系统配置。"""
    with _lock:
        return _load_settings()


def get_disable_public_share() -> bool:
    """读取“禁用公开分享”开关。"""
    with _lock:
        return bool(_load_settings().get("disable_public_share", _DEFAULT_SETTINGS["disable_public_share"]))


def get_force_public_share_review() -> bool:
    """读取“公开分享强制审核”开关。"""
    with _lock:
        return bool(_load_settings().get("force_public_share_review", _DEFAULT_SETTINGS["force_public_share_review"]))


def set_disable_public_share(disabled: bool) -> Dict[str, Any]:
    """更新“禁用公开分享”开关并持久化。"""
    with _lock:
        current = _load_settings()
        current["disable_public_share"] = bool(disabled)
        _save_settings(current)
        return dict(current)


def set_force_public_share_review(enabled: bool) -> Dict[str, Any]:
    """更新“公开分享强制审核”开关并持久化。"""
    with _lock:
        current = _load_settings()
        current["force_public_share_review"] = bool(enabled)
        _save_settings(current)
        return dict(current)
