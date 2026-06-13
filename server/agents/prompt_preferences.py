"""Agent 提示词质量偏好服务。

本模块只管理用户可编辑的“质量偏好层”，不允许覆盖格式协议、工具协议、
三模态运行协议或任何解析所依赖的字段。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

import yaml

from core.utils import USERDATA_ROOT


PREFERENCE_FILE_NAME = "agent_prompt_overrides.json"
PREFERENCE_VERSION = 2

QUALITY_GUARDRAIL = (
    "质量偏好只用于描述审美、风格、取舍与严格程度。"
    "如果其中出现输出格式、字段、工具调用、JSON/XML/Markup 结构或落盘协议要求，"
    "这些格式类内容不得覆盖上方系统协议和工具协议。"
)


def normalize_agent_id(agent_id: str) -> str:
    """把 prompt 名或 Agent ID 统一为 agent_xxx。"""
    raw = str(agent_id or "").strip()
    if not raw:
        raise ValueError("agent_id 不能为空")
    return raw if raw.startswith("agent_") else f"agent_{raw}"


def prompt_name_from_agent_id(agent_id: str) -> str:
    """把 Agent ID 转为 prompts 目录中的 YAML 文件名。"""
    normalized = normalize_agent_id(agent_id)
    return normalized[len("agent_") :]


def _preference_file_path(user_id: str) -> str:
    return os.path.join(
        USERDATA_ROOT,
        f"uid_{user_id}",
        ".sparkarc",
        PREFERENCE_FILE_NAME,
    )


def _read_preference_file(user_id: str) -> Dict[str, Any]:
    path = _preference_file_path(user_id)
    if not os.path.exists(path):
        return {"version": PREFERENCE_VERSION, "agents": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {"version": PREFERENCE_VERSION, "agents": {}}
        agents = raw.get("agents")
        if not isinstance(agents, dict):
            agents = {}
        return {"version": raw.get("version") or PREFERENCE_VERSION, "agents": agents}
    except Exception:
        return {"version": PREFERENCE_VERSION, "agents": {}}


def _write_preference_file(user_id: str, data: Dict[str, Any]) -> None:
    path = _preference_file_path(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _quality_profile_file_path(prompt_name: str) -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "prompts",
        "quality_profiles",
        f"{prompt_name}.yaml",
    )


def _load_quality_profile_yaml(prompt_name: str) -> Dict[str, Any]:
    path = _quality_profile_file_path(prompt_name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw if isinstance(raw, dict) else {}


def get_quality_default_preference(prompt_or_agent_name: str) -> str:
    """读取仓库内置的单一质量偏好默认值。"""
    prompt_name = prompt_name_from_agent_id(prompt_or_agent_name)
    data = _load_quality_profile_yaml(prompt_name)
    default_content = data.get("preference")
    return default_content.strip() if isinstance(default_content, str) else ""


def _get_user_agent_overrides(user_id: str, agent_id: str) -> Dict[str, Any]:
    data = _read_preference_file(user_id)
    agents = data.get("agents") if isinstance(data, dict) else {}
    if not isinstance(agents, dict):
        return {}
    raw = agents.get(normalize_agent_id(agent_id))
    return raw if isinstance(raw, dict) else {}


def _coerce_legacy_override(raw: Dict[str, Any]) -> Dict[str, Any]:
    """兼容旧版槽位结构，将多个质量槽位合并为一个覆盖。"""
    if "content" in raw or "enabled" in raw:
        return raw

    parts = []
    enabled_values = []
    for key in ("root", "system", "chat", "pipeline", "characters", "synopsis", "beat_sheet", "outline", "novel"):
        item = raw.get(key)
        if not isinstance(item, dict):
            continue
        text = str(item.get("content") or "").strip()
        if text:
            parts.append(text)
        if "enabled" in item:
            enabled_values.append(bool(item.get("enabled", True)))

    if not parts:
        return {}
    return {
        "enabled": all(enabled_values) if enabled_values else True,
        "content": "\n\n".join(parts),
        "updated_at": raw.get("updated_at"),
    }


def build_quality_placeholder_values(
    prompt_or_agent_name: str,
    user_id: str | None = None,
) -> Dict[str, str]:
    """构造 `{quality.xxx}` 占位符值。"""
    prompt_name = prompt_name_from_agent_id(prompt_or_agent_name)
    agent_id = normalize_agent_id(prompt_name)
    default_content = get_quality_default_preference(prompt_name)
    override = _coerce_legacy_override(_get_user_agent_overrides(user_id, agent_id)) if user_id else {}
    final_content = default_content
    if isinstance(override, dict) and override.get("enabled", True):
        candidate = str(override.get("content") or "").strip()
        if candidate:
            final_content = candidate
    return {
        "quality.guard": QUALITY_GUARDRAIL,
        "quality.preference": final_content,
    }


def get_agent_prompt_preferences(user_id: str, agent_id: str) -> Dict[str, Any]:
    """返回某个 Agent 的单一可编辑质量偏好。"""
    normalized_agent_id = normalize_agent_id(agent_id)
    default_content = get_quality_default_preference(normalized_agent_id)
    override = _coerce_legacy_override(_get_user_agent_overrides(user_id, normalized_agent_id))
    override_content = str(override.get("content") or "") if isinstance(override, dict) else ""
    enabled = bool(override.get("enabled", True)) if isinstance(override, dict) else True
    updated_at = override.get("updated_at") if isinstance(override, dict) else None
    effective = override_content.strip() if enabled and override_content.strip() else default_content

    return {
        "agent_id": normalized_agent_id,
        "guardrail": QUALITY_GUARDRAIL,
        "default_content": default_content,
        "override_content": override_content,
        "effective_content": effective,
        "enabled": enabled,
        "customized": bool(enabled and override_content.strip()),
        "updated_at": updated_at,
    }


def _assert_agent_has_default(agent_id: str) -> None:
    if not get_quality_default_preference(agent_id):
        raise ValueError(f"该 Agent 暂无可编辑质量偏好: {agent_id}")


def save_agent_prompt_preference(
    user_id: str,
    agent_id: str,
    content: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    """保存用户对单一质量偏好的覆盖。"""
    normalized_agent_id = normalize_agent_id(agent_id)
    _assert_agent_has_default(normalized_agent_id)

    data = _read_preference_file(user_id)
    data["version"] = PREFERENCE_VERSION
    agents = data.setdefault("agents", {})
    if not isinstance(agents, dict):
        agents = {}
        data["agents"] = agents
    agents[normalized_agent_id] = {
        "enabled": bool(enabled),
        "content": str(content or "").strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_preference_file(user_id, data)
    return get_agent_prompt_preferences(user_id, normalized_agent_id)


def reset_agent_prompt_preference(user_id: str, agent_id: str) -> Dict[str, Any]:
    """删除用户覆盖，恢复仓库默认质量偏好。"""
    normalized_agent_id = normalize_agent_id(agent_id)

    data = _read_preference_file(user_id)
    agents = data.get("agents")
    if isinstance(agents, dict):
        agents.pop(normalized_agent_id, None)
        data["version"] = PREFERENCE_VERSION
        _write_preference_file(user_id, data)
    return get_agent_prompt_preferences(user_id, normalized_agent_id)


def iter_prompt_agents_with_quality_profiles() -> Iterable[str]:
    """列出已声明质量偏好的 Agent ID。"""
    prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "quality_profiles")
    if not os.path.isdir(prompts_dir):
        return []
    agent_ids = []
    for file_name in sorted(os.listdir(prompts_dir)):
        if not file_name.endswith(".yaml"):
            continue
        prompt_name = file_name[:-5]
        if get_quality_default_preference(prompt_name):
            agent_ids.append(normalize_agent_id(prompt_name))
    return agent_ids
