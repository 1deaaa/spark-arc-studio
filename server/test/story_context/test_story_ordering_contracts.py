from __future__ import annotations

import json
from pathlib import Path

import pytest


def _story_path(root: Path, name: str, *, chapter: int, scene: int) -> Path:
    from story.file_naming import build_scene_story_filename

    path = root / build_scene_story_filename(chapter, scene, name)
    path.write_text(f"# {name}\n[-1]\n正文-{chapter}-{scene}", encoding="utf-8")
    return path


def test_copy_identity_validation_keeps_source_occupied(tmp_path: Path) -> None:
    from story.file_naming import StoryRenameConflictError, batch_copy_story_files, build_scene_story_filename

    stories = tmp_path / "stories"
    source_dir = stories / "一 · 开端"
    target_dir = stories / "复制章节"
    source_dir.mkdir(parents=True)
    source = _story_path(source_dir, "初遇", chapter=1, scene=1)
    target = target_dir / build_scene_story_filename(1, 1, "初遇副本")

    with pytest.raises(StoryRenameConflictError):
        batch_copy_story_files(
            [(str(source), str(target))],
            stories_path=str(stories),
            ensure_unique_identity=True,
        )

    assert source.exists()
    assert not target.exists()


def test_reorder_scenes_requires_complete_chapter_file_list(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import reorder_scenes
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    chapter_dir = tmp_path / "uid_1" / "projects" / "demo" / "stories" / "一 · 开端"
    chapter_dir.mkdir(parents=True)
    first = _story_path(chapter_dir, "初遇", chapter=1, scene=1)
    second = _story_path(chapter_dir, "余波", chapter=1, scene=2)

    user_token = current_user_id.set("1")
    project_token = current_project_name.set("demo")
    try:
        result = reorder_scenes.invoke({
            "chapter_path": "一 · 开端",
            "scene_paths": [f"一 · 开端/{first.name}"],
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "全部故事文件" in result
    assert first.exists()
    assert second.exists()


def test_reorder_chapters_includes_empty_numbered_chapter(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import reorder_chapters
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project = tmp_path / "uid_2" / "projects" / "demo"
    stories = project / "stories"
    empty_chapter = stories / "一 · 空章节"
    written_chapter = stories / "二 · 已写"
    empty_chapter.mkdir(parents=True)
    written_chapter.mkdir(parents=True)
    _story_path(written_chapter, "承接", chapter=2, scene=1)
    (project / "stories_order.json").write_text(
        json.dumps({"": ["一 · 空章节", "二 · 已写"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    user_token = current_user_id.set("2")
    project_token = current_project_name.set("demo")
    try:
        result = reorder_chapters.invoke({
            "chapter_paths": ["二 · 已写", "一 · 空章节"],
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "剧幕重排完成" in result
    assert empty_chapter.is_dir()
    assert written_chapter.is_dir()
    order_data = json.loads((project / "stories_order.json").read_text(encoding="utf-8"))
    assert order_data[""] == ["二 · 已写", "一 · 空章节"]


def test_project_file_collector_uses_story_metadata_sort(monkeypatch, tmp_path: Path) -> None:
    from story.file_naming import build_story_filename
    from story.project_files import collect_project_files

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories = tmp_path / "uid_3" / "projects" / "demo" / "stories"
    stories.mkdir(parents=True)
    for chapter, title in ((10, "十 · 后段"), (2, "二 · 前段")):
        path = stories / build_story_filename(title, chapter_num=chapter, scene_num=1, order=chapter * 1000 + 1)
        path.write_text("# 场景\n[-1]\n正文", encoding="utf-8")

    story_files = [
        item.rel_path
        for item in collect_project_files("3", "demo")
        if item.format_key == "arc"
    ]
    assert story_files == [
        "stories/二 · 前段.__spark__chap=002.scene=001.order=002001.arc",
        "stories/十 · 后段.__spark__chap=010.scene=001.order=010001.arc",
    ]
