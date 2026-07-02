from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_story_file_tree_keeps_empty_folder_when_format_filtered(monkeypatch, tmp_path: Path) -> None:
    """新建分卷是空文件夹，格式过滤时也必须显示，否则前端看起来像创建无反应。"""
    from story import routes_files

    project_path = tmp_path / "project"
    stories_path = project_path / "stories"
    empty_volume = stories_path / "一 · 空分卷"
    empty_volume.mkdir(parents=True)

    monkeypatch.setattr(routes_files, "ensure_project_stories_directory", lambda *_args, **_kwargs: str(stories_path))
    monkeypatch.setattr(routes_files, "get_project_path", lambda *_args, **_kwargs: str(project_path))

    result = asyncio.run(
        routes_files.get_story_files(
            "demo",
            format="novel",
            user={"user_id": "user_1"},
        )
    )

    assert result == [
        {
            "name": "一 · 空分卷",
            "type": "folder",
            "path": "一 · 空分卷",
            "children": [],
        }
    ]


def test_create_existing_folder_returns_conflict(monkeypatch, tmp_path: Path) -> None:
    """重复创建同名分卷应返回冲突，避免前端显示为静默成功。"""
    from story import routes_files

    stories_path = tmp_path / "project" / "stories"
    existing = stories_path / "一 · 空分卷"
    existing.mkdir(parents=True)

    monkeypatch.setattr(routes_files, "ensure_project_stories_directory", lambda *_args, **_kwargs: str(stories_path))

    response = asyncio.run(
        routes_files.create_file_or_folder(
            routes_files.FileOperation(
                projectName="demo",
                type="folder",
                path="一 · 空分卷",
            ),
            user={"user_id": "user_1"},
        )
    )

    assert response.status_code == 409
    assert json.loads(response.body.decode("utf-8")) == {
        "success": False,
        "message": "分卷 '一 · 空分卷' 已存在",
    }
