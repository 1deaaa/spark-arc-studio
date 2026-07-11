from __future__ import annotations

from pathlib import Path


def test_find_scene_file_by_identity_uses_filename_meta_across_project(tmp_path: Path) -> None:
    from story.file_naming import find_scene_file_by_identity

    stories_path = tmp_path / "stories"
    old_dir = stories_path / "旧章节名"
    old_dir.mkdir(parents=True)
    existing = old_dir / "旧标题.__spark__chap=001.scene=003.order=001003.arc"
    existing.write_text("# 1-3 旧标题\n[-1]\n旧正文", encoding="utf-8")

    found, parsed = find_scene_file_by_identity(
        str(stories_path),
        1,
        3,
        file_format="arc",
    )

    assert found == str(existing)
    assert parsed is not None
    assert parsed["chapter_num"] == 1
    assert parsed["scene_num"] == 3


def test_resolve_planned_scene_file_path_overwrites_existing_identity(tmp_path: Path) -> None:
    from story.file_naming import resolve_planned_scene_file_path

    stories_path = tmp_path / "stories"
    old_dir = stories_path / "一 · 开端"
    old_dir.mkdir(parents=True)
    existing = old_dir / "1-1 初遇.__spark__chap=001.scene=001.order=001001.arc"
    existing.write_text("# 1-1 初遇\n[-1]\n旧正文", encoding="utf-8")

    resolved, existed, _ = resolve_planned_scene_file_path(
        str(stories_path),
        1,
        1,
        "1-1 重写后的标题",
        chapter_dir_name="一 · 开端",
        file_format="arc",
    )

    assert resolved == str(existing)
    assert existed is True


def test_create_or_rewrite_script_overwrites_existing_planned_scene(monkeypatch, tmp_path: Path) -> None:
    from core.request_context import current_export_format, current_project_name, current_user_id
    from agents.tools.scriptwriter import create_or_rewrite_script

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories_path = tmp_path / "uid_7" / "projects" / "demo" / "stories" / "一 · 开端"
    stories_path.mkdir(parents=True)
    existing = stories_path / "1-1 初遇.__spark__chap=001.scene=001.order=001001.arc"
    existing.write_text("# 1-1 初遇\n[-1]\n旧正文", encoding="utf-8")

    user_token = current_user_id.set("7")
    project_token = current_project_name.set("demo")
    format_token = current_export_format.set("arc")
    try:
        result = create_or_rewrite_script.invoke(
            {
                "chapter_name": "一 · 开端",
                "work_name": "1-1 初遇",
                "overwrite_content": "[-1]\n新正文",
            }
        )
    finally:
        current_export_format.reset(format_token)
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    files = list(stories_path.glob("*.arc"))
    assert files == [existing]
    assert "已覆盖" in result
    assert "新正文" in existing.read_text(encoding="utf-8")
    assert "旧正文" not in existing.read_text(encoding="utf-8")


def test_read_chapter_scene_reads_nested_persisted_arc(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.shared_read import read_chapter_scene
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    stories_path = tmp_path / "uid_7" / "projects" / "demo" / "stories" / "一 · 开端"
    stories_path.mkdir(parents=True)
    story_path = stories_path / "1-1 初遇.__spark__chap=001.scene=001.order=001001.arc"
    story_path.write_text("# 1-1 初遇\n[旁白]\n嵌套目录中的正文。", encoding="utf-8")

    user_token = current_user_id.set("7")
    project_token = current_project_name.set("demo")
    try:
        result = read_chapter_scene.invoke({"chapter_index": 0, "scene_index": 0})
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "已落盘剧本" in result
    assert "一 · 开端/1-1 初遇" in result
    assert "嵌套目录中的正文" in result


def test_patch_script_updates_nested_arc(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import patch_script
    from core.request_context import current_project_name, current_user_id

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "core.project_settings.get_visual_illustration_settings",
        lambda user_id, project_name: {"max_per_scene": 2, "min_node_gap": 1},
    )
    monkeypatch.setattr(
        "core.project_settings.is_visual_illustration_enabled",
        lambda user_id, project_name: False,
    )
    stories_path = tmp_path / "uid_7" / "projects" / "demo" / "stories" / "一 · 开端"
    stories_path.mkdir(parents=True)
    story_path = stories_path / "1-1 初遇.__spark__chap=001.scene=001.order=001001.arc"
    story_path.write_text("# 1-1 初遇\n[旁白]\n修改前正文。", encoding="utf-8")

    user_token = current_user_id.set("7")
    project_token = current_project_name.set("demo")
    try:
        result = patch_script.invoke({
            "search_text": "修改前正文。",
            "replace_text": "修改后正文。",
        })
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert "已成功局部更新" in result
    assert "修改后正文" in story_path.read_text(encoding="utf-8")
