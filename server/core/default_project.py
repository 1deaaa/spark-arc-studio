from __future__ import annotations

import shutil
from pathlib import Path

from .project_settings import initialize_project_workspace_mode, set_project_story_tags
from .utils import (
    ensure_project_characters_directory,
    ensure_project_directory,
    ensure_project_stories_directory,
)


DEFAULT_PROJECT_NAME = "默认项目"
DEFAULT_PROJECT_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "data" / "default_project"


def initialize_default_project(user_id: str, project_name: str = DEFAULT_PROJECT_NAME) -> str:
    """为新用户创建可直接阅读和拆解的完整剧本示例项目。"""
    if not DEFAULT_PROJECT_TEMPLATE_ROOT.is_dir():
        raise FileNotFoundError(f"默认项目模板不存在：{DEFAULT_PROJECT_TEMPLATE_ROOT}")

    project_path = Path(ensure_project_directory(str(user_id), project_name))
    shutil.copytree(DEFAULT_PROJECT_TEMPLATE_ROOT, project_path, dirs_exist_ok=True)

    # 统一初始化会校验系统角色，并保证模板角色仓库结构完整。
    ensure_project_characters_directory(str(user_id), project_name)
    ensure_project_stories_directory(str(user_id), project_name)
    initialize_project_workspace_mode(str(user_id), project_name, "script")
    set_project_story_tags(
        str(user_id),
        project_name,
        style="克制写实",
        genres=["日常", "现实主义"],
        tones=["温和", "治愈"],
        worldviews=["现代日本小城"],
        pov="第三人称",
        length_hint="中篇",
        scene_length_hint="expanded",
    )
    return str(project_path)
