from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from pathlib import Path

from core import default_project
from core import utils as core_utils
from core.project_settings import get_project_story_tags, get_workspace_mode
from story.arc_parser import parse_arc
from story.file_naming import parse_story_filename
from story.outline_parser import parse_beat_sheet_markup, parse_outline_markup
from story.routes_project import (
    _SPARK_XOR_KEY_LEN,
    _xor_transform,
    ProjectCreate,
    create_project,
    export_project,
)


def test_initialize_default_project_creates_complete_script_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(core_utils, "USERDATA_ROOT", str(tmp_path / "userdata"))

    project_path = Path(default_project.initialize_default_project("17"))

    for filename in ("世界观.txt", "梗概.txt", "节拍表.txt", "大纲.txt"):
        assert (project_path / filename).is_file()

    character_store = project_path / "chr" / "characters.json"
    characters = json.loads(character_store.read_text(encoding="utf-8"))
    assert list((project_path / "chr").iterdir()) == [character_store]
    assert characters["-1"]["name"] == "旁白"
    assert characters["-2"]["name"] == "?"
    assert [characters[str(index)]["name"] for index in range(4)] == ["岛村灯", "安西澄江", "田边陆", "田边美纪"]

    outline = parse_outline_markup((project_path / "大纲.txt").read_text(encoding="utf-8"))
    beats = parse_beat_sheet_markup((project_path / "节拍表.txt").read_text(encoding="utf-8"))
    assert outline["title"] == "雨停在四点十七分"
    assert outline["estimatedScenes"] == 15
    assert len([node for node in outline["nodes"] if node.get("type") == "chapter"]) == 5
    assert len(beats["beats"]) == 15

    story_files = sorted((project_path / "stories").rglob("*.arc"))
    assert len(story_files) == 15
    assert all("<conception>" not in story_file.read_text(encoding="utf-8") for story_file in story_files)
    chapter_scene_counts: dict[int, int] = {}
    known_speakers = {record["name"] for record in characters.values()}
    for story_file in story_files:
        text = story_file.read_text(encoding="utf-8")
        metadata = parse_story_filename(story_file.name)
        scenes = parse_arc(text)
        assert metadata is not None
        chapter_scene_counts[metadata["chapter_num"]] = chapter_scene_counts.get(metadata["chapter_num"], 0) + 1
        assert len(scenes) == 1
        assert scenes[0]["dia"]
        assert len(text) >= 1500
        speakers = set(re.findall(r"^\[([^\]]+)\]\s*$", text, flags=re.MULTILINE))
        assert speakers <= known_speakers
    assert chapter_scene_counts == {1: 3, 2: 3, 3: 3, 4: 3, 5: 3}

    assert get_workspace_mode("17", default_project.DEFAULT_PROJECT_NAME) == "script"
    tags = get_project_story_tags("17", default_project.DEFAULT_PROJECT_NAME)
    assert tags["style"] == "克制写实"
    assert tags["genres"] == ["日常", "现实主义"]
    assert tags["tones"] == ["温和", "治愈"]
    assert tags["pov"] == "第三人称"
    assert tags["length_hint"] == "中篇"
    assert tags["scene_length_hint"] == "expanded"
    assert tags["scene_target_chars"] is None


def test_default_project_template_contains_no_placeholder_copy():
    template_files = {path.name for path in default_project.DEFAULT_PROJECT_TEMPLATE_ROOT.rglob("*") if path.is_file()}

    assert "ARC_Example.arc" not in template_files
    assert "示例剧本.arc" not in template_files
    assert not list(default_project.DEFAULT_PROJECT_TEMPLATE_ROOT.rglob("chr.bind"))
    assert not list((default_project.DEFAULT_PROJECT_TEMPLATE_ROOT / "chr").glob("*.txt"))
    assert all("在这里描述" not in path.read_text(encoding="utf-8") for path in default_project.DEFAULT_PROJECT_TEMPLATE_ROOT.rglob("*.*"))


def test_manually_created_script_project_has_no_bundled_story(tmp_path, monkeypatch):
    monkeypatch.setattr(core_utils, "USERDATA_ROOT", str(tmp_path / "userdata"))

    result = asyncio.run(
        create_project(
            ProjectCreate(projectName="我的新剧本", workspaceMode="script"),
            user={"user_id": 23},
        )
    )

    project_path = Path(core_utils.get_project_path("23", "我的新剧本"))
    assert result["success"] is True
    assert list((project_path / "stories").iterdir()) == []
    assert (project_path / "世界观.txt").is_file()
    assert (project_path / "chr" / "characters.json").is_file()
    assert get_workspace_mode("23", "我的新剧本") == "script"


def test_default_project_export_contains_only_character_store(tmp_path, monkeypatch):
    monkeypatch.setattr(core_utils, "USERDATA_ROOT", str(tmp_path / "userdata"))
    default_project.initialize_default_project("31")

    response = asyncio.run(
        export_project(
            default_project.DEFAULT_PROJECT_NAME,
            user={"user_id": 31},
        )
    )
    payload = response.body
    key = payload[:_SPARK_XOR_KEY_LEN]
    zip_bytes = _xor_transform(payload[_SPARK_XOR_KEY_LEN:], key)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
        names = set(archive.namelist())

    assert "chr/characters.json" in names
    assert all(not name.endswith("chr.bind") for name in names)
    assert all(not (name.startswith("chr/") and name.endswith(".txt")) for name in names)
