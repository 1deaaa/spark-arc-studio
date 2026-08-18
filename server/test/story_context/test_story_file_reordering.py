from __future__ import annotations

import json
from pathlib import Path

import pytest


def _story_path(root: Path, name: str, *, chapter: int, scene: int, order: int | None = None) -> Path:
    from story.file_naming import build_story_filename

    filename = build_story_filename(
        name,
        chapter_num=chapter,
        scene_num=scene,
        order=order if order is not None else chapter * 1000 + scene,
    )
    path = root / filename
    path.write_text(f"# {name}\n[-1]\n正文-{chapter}-{scene}", encoding="utf-8")
    return path


def test_story_sort_key_uses_numeric_title_identity_before_unicode(tmp_path: Path) -> None:
    from story.file_naming import list_story_files

    stories = tmp_path / "stories"
    stories.mkdir()
    for number, title in enumerate(
        ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"),
        start=1,
    ):
        (stories / f"{title} · 章节.arc").write_text(title, encoding="utf-8")

    result = [item[2]["display_name"].split(" ", 1)[0] for item in list_story_files(str(stories))]
    assert result == ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]


def test_story_sort_key_prioritizes_order_then_chapter_and_scene(tmp_path: Path) -> None:
    from story.file_naming import build_story_filename, list_story_files

    stories = tmp_path / "stories"
    stories.mkdir()
    (stories / build_story_filename("章节五", chapter_num=5, scene_num=1, order=20)).write_text("5", encoding="utf-8")
    (stories / build_story_filename("章节九", chapter_num=9, scene_num=1, order=10)).write_text("9", encoding="utf-8")
    (stories / build_story_filename("章节一", chapter_num=1, scene_num=2)).write_text("1", encoding="utf-8")

    result = [item[2]["chapter_num"] for item in list_story_files(str(stories))]
    assert result == [9, 5, 1]


def test_batch_metadata_update_rejects_identity_conflict_without_partial_write(tmp_path: Path) -> None:
    from story.file_naming import StoryRenameConflictError, batch_update_story_file_metadata

    stories = tmp_path / "stories"
    stories.mkdir()
    first = _story_path(stories, "一场", chapter=1, scene=1)
    second = _story_path(stories, "二场", chapter=1, scene=2)

    with pytest.raises(StoryRenameConflictError):
        batch_update_story_file_metadata(
            str(stories),
            [{"path": str(first), "scene_num": 2, "order": 1002}],
        )

    assert first.exists()
    assert second.exists()
    assert "scene=001" in first.name
    assert "scene=002" in second.name


def test_batch_rename_runtime_failure_rolls_back_all_files(monkeypatch, tmp_path: Path) -> None:
    import story.file_naming as file_naming

    stories = tmp_path / "stories"
    stories.mkdir()
    first = stories / "甲.arc"
    second = stories / "乙.arc"
    first.write_text("甲", encoding="utf-8")
    second.write_text("乙", encoding="utf-8")
    first_target = stories / "丙.arc"
    second_target = stories / "丁.arc"
    real_replace = file_naming.os.replace

    def fail_on_second_target(source: str, target: str) -> None:
        if target == str(second_target):
            raise OSError("模拟提交失败")
        real_replace(source, target)

    monkeypatch.setattr(file_naming.os, "replace", fail_on_second_target)
    with pytest.raises(file_naming.StoryRenameTransactionError):
        file_naming.batch_rename_story_files(
            [(str(first), str(first_target)), (str(second), str(second_target))],
            stories_path=str(stories),
        )

    assert first.read_text(encoding="utf-8") == "甲"
    assert second.read_text(encoding="utf-8") == "乙"
    assert not first_target.exists()
    assert not second_target.exists()


def test_scriptwriter_rename_and_reorder_scene(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import rename_scene, reorder_scenes
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories = tmp_path / "uid_7" / "projects" / "demo" / "stories" / "一 · 开端"
    stories.mkdir(parents=True)
    first = _story_path(stories, "1-1 初遇", chapter=1, scene=1)
    second = _story_path(stories, "1-2 余波", chapter=1, scene=2)

    user_token = current_user_id.set("7")
    project_token = current_project_name.set("demo")
    try:
        renamed = rename_scene.invoke({
            "scene_path": "一 · 开端/1-1 初遇.arc",
            "new_scene_name": "初遇改名",
        })
        assert "场景已重命名" in renamed
        assert not first.exists()
        renamed_path = next(stories.glob("*初遇改名*arc"))
        assert "scene=001" in renamed_path.name

        result = reorder_scenes.invoke({
            "chapter_path": "一 · 开端",
            "scene_paths": ["一 · 开端/1-2 余波.arc", f"一 · 开端/{renamed_path.name}"],
        })
        assert "场景重排完成" in result
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    files = sorted(stories.glob("*.arc"))
    assert any("scene=002" in path.name and "余波" in path.name for path in files)
    assert any("scene=001" in path.name and "初遇改名" in path.name for path in files)
    # 重排只交换 order 槽位，不改写大纲匹配用的 chap/scene 或文件路径。
    from story.file_naming import parse_story_filename
    by_name = {path.name: parse_story_filename(path.name) for path in files}
    assert next(meta["order"] for name, meta in by_name.items() if "余波" in name) < next(
        meta["order"] for name, meta in by_name.items() if "初遇改名" in name
    )


def test_scriptwriter_rename_and_reorder_chapters_updates_order_file(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import rename_chapter, reorder_chapters
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project = tmp_path / "uid_8" / "projects" / "demo"
    stories = project / "stories"
    chapter_one = stories / "一 · 开端"
    chapter_two = stories / "二 · 转折"
    chapter_one.mkdir(parents=True)
    chapter_two.mkdir(parents=True)
    _story_path(chapter_one, "1-1 开端", chapter=1, scene=1)
    _story_path(chapter_two, "2-1 转折", chapter=2, scene=1)
    (project / "stories_order.json").write_text(
        json.dumps({"": ["一 · 开端", "二 · 转折"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    user_token = current_user_id.set("8")
    project_token = current_project_name.set("demo")
    try:
        renamed = rename_chapter.invoke({
            "chapter_path": "一 · 开端",
            "new_chapter_name": "新的开端",
        })
        assert "章节已重命名" in renamed
        assert (stories / "一 · 新的开端").is_dir()
        renamed_order = json.loads((project / "stories_order.json").read_text(encoding="utf-8"))
        assert renamed_order[""] == ["一 · 新的开端", "二 · 转折"]

        reordered = reorder_chapters.invoke({
            "chapter_paths": ["二 · 转折", "一 · 新的开端"],
        })
        assert "章节重排完成" in reordered
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert (stories / "一 · 新的开端").is_dir()
    assert (stories / "二 · 转折").is_dir()
    assert any("chap=001" in path.name for path in (stories / "一 · 新的开端").glob("*.arc"))
    assert any("chap=002" in path.name for path in (stories / "二 · 转折").glob("*.arc"))
    order_data = json.loads((project / "stories_order.json").read_text(encoding="utf-8"))
    assert order_data[""] == ["二 · 转折", "一 · 新的开端"]


def test_organize_scenes_updates_scene_identity_and_rejects_conflict(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import organize_scenes_to_chapter
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories = tmp_path / "uid_9" / "projects" / "demo" / "stories"
    stories.mkdir(parents=True)
    source = _story_path(stories, "散落场景", chapter=3, scene=1)
    user_token = current_user_id.set("9")
    project_token = current_project_name.set("demo")
    try:
        result = organize_scenes_to_chapter.invoke({
            "scene_paths": [source.name],
            "new_chapter_name": "新章节",
            "chapter_num": 1,
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "已成功移动" in result
    target_dir = stories / "一 · 新章节"
    target_files = list(target_dir.glob("*.arc"))
    assert len(target_files) == 1
    assert "chap=001" in target_files[0].name
    assert "scene=001" in target_files[0].name
