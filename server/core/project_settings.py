"""项目级统一配置存储。

配置文件路径：<project_path>/.sparkarc/settings.json
这是项目级配置的唯一真相源，未来其他项目级开关（自动保存、导出偏好等）也应收拢到此处。

默认值：
  semantic_search_enabled: false
  graphrag_enabled: false
  attachment_index_enabled: true
  attachment_chunk_tokens: 64000  (附件分片 token 上限，等价于"按需读取"滑动窗口的窗口大小)
  story_tags: {}  (项目级故事主题参数：创作模式/风格/题材/基调/世界观/人称/篇幅)
  active_inspiration_id: null  (当前生效的灵感 ID，用于追溯来源)
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
    # 知识图谱（GraphRAG）开关：构建昂贵，默认关闭，由用户在设置中显式开启
    "graphrag_enabled": False,
    "attachment_index_enabled": True,
    # 聊天附件单分片 token 上限。也是滑动窗口的窗口大小：
    # 大文件按此 token 上限切片；调用 read_attachment_chunk 一次只展开一片，
    # 所以增大此值会让单次注入更长，减小则把 LLM context 让给更多其他内容。
    "attachment_chunk_tokens": 64000,
    # 项目级故事主题参数（"项目宪法"）：创作模式/风格/题材/基调/世界观/人称/篇幅
    # 这些参数贯穿整个创作周期，所有 Agent 通过 context_provider 统一读取
    "story_tags": {
        "workspace_mode": "script", # 创作模式（script=剧本 / novel=小说）
        "style": None,           # 风格（单选，如"治愈"）
        "genres": [],            # 题材（多选，如["仙侠", "冒险"]）
        "tones": [],             # 基调（多选，如["暗黑", "治愈"]）
        "worldviews": [],        # 世界观（多选，如["修真"]）
        "pov": None,             # 人称视角（单选，如"第一人称"）
        "length_hint": None,     # 篇幅（单选，如"中篇"）
    },
    # 当前生效的灵感 ID（可选，用于追溯项目参数的来源灵感）
    "active_inspiration_id": None,
}

# 与 routes_import.py 的 chunk_tokens 校验保持一致，避免极端值。
ATTACHMENT_CHUNK_TOKENS_MIN = 1000
ATTACHMENT_CHUNK_TOKENS_MAX = 120000
ATTACHMENT_CHUNK_TOKENS_DEFAULT = 64000


def _coerce_attachment_chunk_tokens(value: Any) -> int:
    """把外部传入的 chunk_tokens 收敛到合法整数区间内。"""
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return ATTACHMENT_CHUNK_TOKENS_DEFAULT
    if ivalue < ATTACHMENT_CHUNK_TOKENS_MIN:
        return ATTACHMENT_CHUNK_TOKENS_MIN
    if ivalue > ATTACHMENT_CHUNK_TOKENS_MAX:
        return ATTACHMENT_CHUNK_TOKENS_MAX
    return ivalue

_lock = threading.Lock()


def _default_settings_copy() -> Dict[str, Any]:
    """返回项目默认配置副本，避免嵌套 story_tags 被运行时修改污染。"""
    data = dict(_DEFAULT_SETTINGS)
    data["story_tags"] = dict(_DEFAULT_SETTINGS["story_tags"])
    return data


def _settings_path(project_path: str) -> str:
    return os.path.join(project_path, _SETTINGS_DIR, _SETTINGS_FILENAME)


def _normalize(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    data = _default_settings_copy()
    if isinstance(raw, dict):
        data["semantic_search_enabled"] = bool(raw.get("semantic_search_enabled", _DEFAULT_SETTINGS["semantic_search_enabled"]))
        data["graphrag_enabled"] = bool(raw.get("graphrag_enabled", _DEFAULT_SETTINGS["graphrag_enabled"]))
        data["attachment_index_enabled"] = bool(raw.get("attachment_index_enabled", _DEFAULT_SETTINGS["attachment_index_enabled"]))
        data["attachment_chunk_tokens"] = _coerce_attachment_chunk_tokens(
            raw.get("attachment_chunk_tokens", _DEFAULT_SETTINGS["attachment_chunk_tokens"])
        )
        raw_mode_from_tags = None
        # 规范化 story_tags：保留已有值，补齐缺失字段
        raw_tags = raw.get("story_tags")
        if isinstance(raw_tags, dict):
            default_tags = _DEFAULT_SETTINGS["story_tags"]
            raw_mode = raw_tags.get("workspace_mode", raw.get("workspace_mode", default_tags["workspace_mode"]))
            raw_mode_from_tags = raw_tags.get("workspace_mode")
            normalized_mode = "novel" if raw_mode == "novel" else "script"
            data["story_tags"] = {
                "workspace_mode": normalized_mode,
                "style": raw_tags.get("style", default_tags["style"]),
                "genres": raw_tags.get("genres", default_tags["genres"]) or [],
                "tones": raw_tags.get("tones", default_tags["tones"]) or [],
                "worldviews": raw_tags.get("worldviews", default_tags["worldviews"]) or [],
                "pov": raw_tags.get("pov", default_tags["pov"]),
                "length_hint": raw_tags.get("length_hint", default_tags["length_hint"]),
            }
        # 规范化 active_inspiration_id
        data["active_inspiration_id"] = raw.get("active_inspiration_id", _DEFAULT_SETTINGS["active_inspiration_id"])
        # 兼容读取旧顶层 workspace_mode，但唯一写入位置是 story_tags.workspace_mode。
        raw_mode = raw_mode_from_tags if raw_mode_from_tags is not None else raw.get(
            "workspace_mode",
            data["story_tags"].get("workspace_mode", _DEFAULT_SETTINGS["story_tags"]["workspace_mode"]),
        )
        data["story_tags"]["workspace_mode"] = "novel" if raw_mode == "novel" else "script"
    return data


def _load(project_path: str) -> Dict[str, Any]:
    path = _settings_path(project_path)
    if not os.path.exists(path):
        return _default_settings_copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _normalize(raw)
    except Exception:
        return _default_settings_copy()


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


def is_graphrag_enabled(user_id: str, project_name: str) -> bool:
    """快捷查询：项目知识图谱（GraphRAG）是否启用。"""
    return bool(get_project_setting(user_id, project_name, "graphrag_enabled", False))


def is_attachment_index_enabled(user_id: str, project_name: str) -> bool:
    """快捷查询：附件是否参与项目语义检索（默认 True）。"""
    return bool(get_project_setting(user_id, project_name, "attachment_index_enabled", True))


def get_attachment_chunk_tokens(user_id: str, project_name: str) -> int:
    """快捷查询：附件分片 token 上限（即按需读取的滑动窗口大小）。

    永远返回合法范围内的整数；缺省 / 异常一律回到默认值。
    """
    raw = get_project_setting(
        user_id, project_name, "attachment_chunk_tokens", ATTACHMENT_CHUNK_TOKENS_DEFAULT
    )
    return _coerce_attachment_chunk_tokens(raw)


def set_attachment_chunk_tokens(user_id: str, project_name: str, value: Any) -> int:
    """设置附件分片 token 上限并持久化，返回最终生效的整数值。"""
    coerced = _coerce_attachment_chunk_tokens(value)
    set_project_setting(user_id, project_name, "attachment_chunk_tokens", coerced)
    return coerced


def get_workspace_mode(user_id: str, project_name: str) -> str:
    """快捷查询：项目默认创作模式（script=剧本 / novel=小说）。"""
    tags = get_project_story_tags(user_id, project_name)
    mode = tags.get("workspace_mode")
    return "novel" if mode == "novel" else "script"


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


def list_projects_graphrag_status(user_id: str) -> List[Dict[str, Any]]:
    """批量查询用户所有项目的 GraphRAG 启用状态。

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
            "enabled": settings.get("graphrag_enabled", False),
        })

    return result


# ==================== 用户级默认配置 ====================

_USER_SETTINGS_FILENAME = "user_settings.json"

_USER_DEFAULTS: Dict[str, Any] = {
    "default_semantic_search_enabled": False,
    "default_graphrag_enabled": False,
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
            data["default_graphrag_enabled"] = bool(
                raw.get("default_graphrag_enabled", _USER_DEFAULTS["default_graphrag_enabled"])
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


def get_default_graphrag_enabled(user_id: str) -> bool:
    """查询用户级默认：新项目是否默认启用 GraphRAG 知识图谱。"""
    with _lock:
        return _user_load(user_id).get("default_graphrag_enabled", False)


def set_default_graphrag_enabled(user_id: str, value: bool) -> bool:
    """设置用户级默认：新项目是否默认启用 GraphRAG 知识图谱。"""
    with _lock:
        data = _user_load(user_id)
        data["default_graphrag_enabled"] = value
        _user_save(user_id, data)
        return value


# ==================== 项目级故事主题参数（Story Tags）====================


def get_project_story_tags(user_id: str, project_name: str) -> Dict[str, Any]:
    """读取项目级故事主题参数（创作模式/风格/题材/基调/世界观/人称/篇幅）。
    
    返回格式：
    {
        "workspace_mode": "script" | "novel",
        "style": str | None,
        "genres": list[str],
        "tones": list[str],
        "worldviews": list[str],
        "pov": str | None,
        "length_hint": str | None,
    }
    """
    settings = get_project_settings(user_id, project_name)
    return dict(settings.get("story_tags", _DEFAULT_SETTINGS["story_tags"]))


def initialize_project_workspace_mode(
    user_id: str,
    project_name: str,
    workspace_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """创建项目时初始化创作模式；项目创建后不再通过 story tags 动态切换。"""
    with _lock:
        project_path = get_project_path(user_id, project_name)
        settings = _load(project_path)
        current_tags = dict(settings.get("story_tags", _DEFAULT_SETTINGS["story_tags"]))
        current_tags["workspace_mode"] = "novel" if workspace_mode == "novel" else "script"
        settings["story_tags"] = current_tags
        _save(project_path, settings)
        return dict(current_tags)


def set_project_story_tags(
    user_id: str,
    project_name: str,
    style: Optional[str] = None,
    genres: Optional[List[str]] = None,
    tones: Optional[List[str]] = None,
    worldviews: Optional[List[str]] = None,
    pov: Optional[str] = None,
    length_hint: Optional[str] = None,
    workspace_mode: Optional[str] = None,
    active_inspiration_id: Optional[str] = None,
) -> Dict[str, Any]:
    """设置项目级故事主题参数（部分更新，仅覆盖传入的字段）。
    
    Args:
        user_id: 用户 ID
        project_name: 项目名称
        style: 风格（单选，如"治愈"）
        genres: 题材（多选，如["仙侠", "冒险"]）
        tones: 基调（多选，如["暗黑", "治愈"]）
        worldviews: 世界观（多选，如["修真"]）
        pov: 人称视角（单选，如"第一人称"）
        length_hint: 篇幅（单选，如"中篇"）
        workspace_mode: 创作模式只读兼容参数；创建项目后会被忽略
        active_inspiration_id: 当前生效的灵感 ID（可选）
    
    Returns:
        更新后的完整 story_tags 字典
    """
    with _lock:
        project_path = get_project_path(user_id, project_name)
        settings = _load(project_path)
        current_tags = dict(settings.get("story_tags", _DEFAULT_SETTINGS["story_tags"]))
        
        # 部分更新：仅覆盖传入的字段
        if style is not None:
            current_tags["style"] = style
        if genres is not None:
            current_tags["genres"] = genres
        if tones is not None:
            current_tags["tones"] = tones
        if worldviews is not None:
            current_tags["worldviews"] = worldviews
        if pov is not None:
            current_tags["pov"] = pov
        if length_hint is not None:
            current_tags["length_hint"] = length_hint
        settings["story_tags"] = current_tags
        
        # 更新 active_inspiration_id（如果传入）
        if active_inspiration_id is not None:
            settings["active_inspiration_id"] = active_inspiration_id
        
        _save(project_path, settings)
        return dict(current_tags)
