"""项目级统一配置存储。

配置文件路径：<project_path>/.sparkarc/settings.json
这是项目级配置的唯一真相源，未来其他项目级开关（自动保存、导出偏好等）也应收拢到此处。

默认值：
  semantic_search_enabled: false
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from core.utils import get_project_path, get_user_projects_root

_SETTINGS_DIR = ".sparkarc"
_SETTINGS_FILENAME = "settings.json"

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "semantic_search_enabled": False,
}

_lock = threading.Lock()


def _settings_path(project_path: str) -> str:
    return os.path.join(project_path, _SETTINGS_DIR, _SETTINGS_FILENAME)


def _normalize(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    data = dict(_DEFAULT_SETTINGS)
    if isinstance(raw, dict):
        data["semantic_search_enabled"] = bool(raw.get("semantic_search_enabled", _DEFAULT_SETTINGS["semantic_search_enabled"]))
    return data


def _load(project_path: str) -> Dict[str, Any]:
    path = _settings_path(project_path)
    if not os.path.exists(path):
        return dict(_DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _normalize(raw)
    except Exception:
        return dict(_DEFAULT_SETTINGS)


def _save(project_path: str, data: Dict[str, Any]) -> None:
    settings_dir = os.path.join(project_path, _SETTINGS_DIR)
    os.makedirs(settings_dir, exist_ok=True)
    path = os.path.join(settings_dir, _SETTINGS_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_normalize(data), f, ensure_ascii=False, indent=2)


# ==================== 公开 API ====================


def get_project_settings(user_id: str, project_name: str) -> Dict[str, Any]:
    """读取项目完整配置。"""
    with _lock:
        project_path = get_project_path(user_id, project_name)
        return _load(project_path)


def get_project_setting(user_id: str, project_name: str, key: str, default: Any = None) -> Any:
    """读取项目配置中的单个键。"""
    settings = get_project_settings(user_id, project_name)
    return settings.get(key, default)


def set_project_setting(user_id: str, project_name: str, key: str, value: Any) -> Dict[str, Any]:
    """更新项目配置中的单个键并持久化。返回更新后的完整配置。"""
    with _lock:
        project_path = get_project_path(user_id, project_name)
        current = _load(project_path)
        current[key] = value
        _save(project_path, current)
        return dict(current)


def is_semantic_search_enabled(user_id: str, project_name: str) -> bool:
    """快捷查询：语义搜索是否启用。"""
    return bool(get_project_setting(user_id, project_name, "semantic_search_enabled", False))


def list_projects_semantic_status(user_id: str) -> List[Dict[str, Any]]:
    """批量查询用户所有项目的语义搜索启用状态。

    返回格式：[{"project_name": str, "enabled": bool}, ...]
    """
    projects_root = get_user_projects_root(user_id)
    result: List[Dict[str, Any]] = []
    if not os.path.isdir(projects_root):
        return result

    for name in sorted(os.listdir(projects_root)):
        project_path = os.path.join(projects_root, name)
        if not os.path.isdir(project_path):
            continue
        with _lock:
            settings = _load(project_path)
        result.append({
            "project_name": name,
            "enabled": settings.get("semantic_search_enabled", False),
        })

    return result


# ==================== 用户级默认配置 ====================

_USER_SETTINGS_FILENAME = "user_settings.json"

_USER_DEFAULTS: Dict[str, Any] = {
    "default_semantic_search_enabled": False,
}


def _user_settings_path(user_id: str) -> str:
    """用户级配置文件路径：_userdata/uid_{user_id}/.sparkarc/user_settings.json"""
    from core.utils import USERDATA_ROOT
    return os.path.join(USERDATA_ROOT, f"uid_{user_id}", _SETTINGS_DIR, _USER_SETTINGS_FILENAME)


def _user_load(user_id: str) -> Dict[str, Any]:
    path = _user_settings_path(user_id)
    if not os.path.exists(path):
        return dict(_USER_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = dict(_USER_DEFAULTS)
        if isinstance(raw, dict):
            data["default_semantic_search_enabled"] = bool(
                raw.get("default_semantic_search_enabled", _USER_DEFAULTS["default_semantic_search_enabled"])
            )
        return data
    except Exception:
        return dict(_USER_DEFAULTS)


def _user_save(user_id: str, data: Dict[str, Any]) -> None:
    from core.utils import USERDATA_ROOT
    settings_dir = os.path.join(USERDATA_ROOT, f"uid_{user_id}", _SETTINGS_DIR)
    os.makedirs(settings_dir, exist_ok=True)
    path = os.path.join(settings_dir, _USER_SETTINGS_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_default_semantic_enabled(user_id: str) -> bool:
    """查询用户级默认：新项目是否默认启用语义搜索。"""
    with _lock:
        return _user_load(user_id).get("default_semantic_search_enabled", False)


def set_default_semantic_enabled(user_id: str, value: bool) -> bool:
    """设置用户级默认：新项目是否默认启用语义搜索。"""
    with _lock:
        data = _user_load(user_id)
        data["default_semantic_search_enabled"] = value
        _user_save(user_id, data)
        return value
