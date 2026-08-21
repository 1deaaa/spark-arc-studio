from __future__ import annotations

import os

from core.utils import get_project_path, get_project_stories_path


STORY_CONTENT_SUFFIXES = (".arc", ".md")


def project_has_written_story_content(user_id: str, project_name: str) -> bool:
    """判断项目是否已有可作为连续性事实来源的非空正文。"""
    if not str(user_id or "").strip() or not str(project_name or "").strip():
        return False
    stories_path = get_project_stories_path(str(user_id), project_name)
    if not os.path.isdir(stories_path):
        return False
    for root, dirs, files in os.walk(stories_path):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for filename in files:
            if filename.startswith(".") or not filename.lower().endswith(STORY_CONTENT_SUFFIXES):
                continue
            path = os.path.join(root, filename)
            try:
                if os.path.getsize(path) > 0:
                    return True
            except OSError:
                continue
    return False


def load_worldview(user_id: str, project_name: str) -> str:
    path = os.path.join(get_project_path(user_id, project_name), "世界观.txt")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_worldview(user_id: str, project_name: str, content: str) -> None:
    """通过统一项目路径写入世界观正文。"""
    from core.utils import (
        ensure_project_directory,
        ensure_project_worldview_and_character_settings,
        get_project_worldview_path,
    )

    ensure_project_worldview_and_character_settings(user_id, project_name)
    worldview_path = get_project_worldview_path(user_id, project_name)
    ensure_project_directory(user_id, project_name)
    with open(worldview_path, "w", encoding="utf-8") as file:
        file.write(content)
