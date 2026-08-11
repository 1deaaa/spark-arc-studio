from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

from core.json_state import json_state_lock, load_json_file, save_json_file_atomic
from core.utils import get_project_path


STRUCTURE_STATE_FILENAME = ".structure_state.json"
STRUCTURE_ARTIFACTS = ("synopsis", "beat_sheet", "outline")
STRUCTURE_FILENAMES = {
    "synopsis": "梗概.txt",
    "beat_sheet": "节拍表.txt",
    "outline": "大纲.txt",
}


def _empty_artifact() -> dict[str, Any]:
    return {
        "revision": 0,
        "updated_at": "",
        "derived_from": {},
        "stale": False,
        "stale_reason": "",
    }


def _default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "artifacts": {name: _empty_artifact() for name in STRUCTURE_ARTIFACTS},
    }


def _state_path(user_id: str, project_name: str) -> str:
    return os.path.join(get_project_path(user_id, project_name), STRUCTURE_STATE_FILENAME)


def _normalize_state(raw: Any) -> dict[str, Any]:
    state = raw if isinstance(raw, dict) else _default_state()
    artifacts = state.get("artifacts") if isinstance(state.get("artifacts"), dict) else {}
    normalized = _default_state()
    for name in STRUCTURE_ARTIFACTS:
        source = artifacts.get(name) if isinstance(artifacts.get(name), dict) else {}
        target = normalized["artifacts"][name]
        target.update({key: source.get(key, value) for key, value in target.items()})
    return normalized


def load_structure_state(user_id: str, project_name: str) -> dict[str, Any]:
    path = _state_path(str(user_id), project_name)
    return _normalize_state(load_json_file(path, _default_state))


def _mark_stale(artifact: dict[str, Any], reason: str) -> None:
    if int(artifact.get("revision") or 0) <= 0:
        return
    artifact["stale"] = True
    artifact["stale_reason"] = reason


def _hydrate_legacy_artifacts(
    state: dict[str, Any],
    *,
    user_id: str,
    project_name: str,
    saving_artifact: str,
    saving_artifact_existed: bool,
) -> None:
    project_path = get_project_path(user_id, project_name)
    artifacts = state["artifacts"]
    for name, filename in STRUCTURE_FILENAMES.items():
        artifact = artifacts[name]
        if int(artifact.get("revision") or 0) > 0:
            continue
        existed = saving_artifact_existed if name == saving_artifact else os.path.isfile(os.path.join(project_path, filename))
        if existed:
            artifact["revision"] = 1
            artifact["updated_at"] = "legacy-baseline"


def record_structure_save(
    user_id: str,
    project_name: str,
    artifact_name: str,
    *,
    artifact_existed_before: bool = False,
) -> dict[str, Any]:
    """记录三级结构产物的来源修订，并标记受影响的下游产物。"""
    if artifact_name not in STRUCTURE_ARTIFACTS:
        raise ValueError(f"未知结构产物：{artifact_name}")

    path = _state_path(str(user_id), project_name)
    with json_state_lock(path):
        state = _normalize_state(load_json_file(path, _default_state))
        _hydrate_legacy_artifacts(
            state,
            user_id=str(user_id),
            project_name=project_name,
            saving_artifact=artifact_name,
            saving_artifact_existed=artifact_existed_before,
        )
        artifacts = state["artifacts"]
        current = artifacts[artifact_name]
        current["revision"] = int(current.get("revision") or 0) + 1
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        current["stale"] = False
        current["stale_reason"] = ""

        if artifact_name == "synopsis":
            current["derived_from"] = {}
            _mark_stale(artifacts["beat_sheet"], "梗概已更新，节拍表尚未基于当前梗概重建")
            _mark_stale(artifacts["outline"], "梗概已更新，大纲尚未基于当前故事契约重建")
        elif artifact_name == "beat_sheet":
            current["derived_from"] = {"synopsis": int(artifacts["synopsis"].get("revision") or 0)}
            _mark_stale(artifacts["outline"], "节拍表已更新，大纲尚未基于当前节拍重建")
        else:
            current["derived_from"] = {
                "synopsis": int(artifacts["synopsis"].get("revision") or 0),
                "beat_sheet": int(artifacts["beat_sheet"].get("revision") or 0),
            }

        save_json_file_atomic(path, state)
        return state


def format_structure_state_warning(state: dict[str, Any]) -> str:
    artifacts = state.get("artifacts") if isinstance(state, dict) else {}
    warnings = []
    for name, label in (("beat_sheet", "节拍表"), ("outline", "大纲")):
        item = artifacts.get(name) if isinstance(artifacts, dict) else None
        if isinstance(item, dict) and item.get("stale"):
            warnings.append(f"- {label}已过期：{item.get('stale_reason') or '上游结构已更新'}")
    if not warnings:
        return ""
    return "【结构版本警告】\n" + "\n".join(warnings) + "\n- 过期产物只能作为历史参考，不得覆盖较新的上游事实。"
