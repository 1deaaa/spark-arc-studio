"""结构产物与大纲历史的统一持久化门面。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Any

from core.utils import get_project_path


STRUCTURE_ARTIFACT_FILENAMES = {
    "synopsis": "梗概.txt",
    "beat_sheet": "节拍表.txt",
    "outline": "大纲.txt",
}


def get_outline_history_dir(user_id: str, project_name: str) -> str:
    """返回项目大纲历史目录，不产生文件系统副作用。"""
    return os.path.join(get_project_path(user_id, project_name), "history")


def _ensure_outline_history_dir(user_id: str, project_name: str) -> str:
    history_dir = get_outline_history_dir(user_id, project_name)
    os.makedirs(history_dir, exist_ok=True)
    return history_dir


def save_outline_to_history(user_id: str, project_name: str, markup_text: str) -> None:
    """保存大纲 Markup 文本到历史记录。"""
    from story.outline_parser import parse_outline_markup

    history_dir = _ensure_outline_history_dir(user_id, project_name)
    history_file = os.path.join(history_dir, "outline_history.json")

    history: list[dict[str, Any]] = []
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as file:
            history = json.load(file)

    parsed = parse_outline_markup(markup_text)
    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "title": parsed.get("title", "未命名大纲"),
        "nodeCount": len(parsed.get("nodes", [])),
        "markup": markup_text,
    }
    history.insert(0, entry)
    history = history[:20]

    with open(history_file, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def save_structure_artifact(
    user_id: str,
    project_name: str,
    artifact_name: str,
    markup_text: str,
) -> None:
    """写入结构产物，并同步记录结构版本关系。"""
    try:
        filename = STRUCTURE_ARTIFACT_FILENAMES[artifact_name]
    except KeyError as exc:
        raise ValueError(f"未知结构产物：{artifact_name}") from exc

    filepath = os.path.join(get_project_path(user_id, project_name), filename)
    artifact_existed_before = os.path.isfile(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, "w", encoding="utf-8") as file:
        file.write(markup_text)

    from agents.structure_state import record_structure_save

    record_structure_save(
        user_id,
        project_name,
        artifact_name,
        artifact_existed_before=artifact_existed_before,
    )


def save_project_outline(user_id: str, project_name: str, markup_text: str) -> None:
    """保存项目大纲。"""
    save_structure_artifact(user_id, project_name, "outline", markup_text)


def save_project_synopsis(user_id: str, project_name: str, markup_text: str) -> None:
    """保存项目梗概。"""
    save_structure_artifact(user_id, project_name, "synopsis", markup_text)


def save_project_beat_sheet(user_id: str, project_name: str, markup_text: str) -> None:
    """保存项目节拍表。"""
    save_structure_artifact(user_id, project_name, "beat_sheet", markup_text)
