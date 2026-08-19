from __future__ import annotations

from core.project_settings import get_project_story_tags, set_project_story_tags
from agents.routes.context_builder import build_story_tags_hint
from agents.agent_utils import build_length_hint_str, load_prompt
from agents.story_terminology import build_story_structure_quantity_guidance


def test_specific_scene_target_chars_overrides_preset_range_in_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))

    tags = set_project_story_tags(
        "9",
        "demo",
        scene_length_hint="expanded",
        scene_target_chars=1000,
    )
    prompt = build_story_tags_hint(tags)

    assert tags["scene_target_chars"] == 1000
    assert "目标约 1000 个可见正文字符" in prompt
    assert "1800-3000" not in prompt
    assert "不是硬性验收条件" in prompt
    assert "自行判断" in prompt

    updated = set_project_story_tags("9", "demo", scene_length_hint="concise")
    assert updated["scene_target_chars"] == 1000

    cleared = set_project_story_tags("9", "demo", scene_target_chars=None)
    assert cleared["scene_target_chars"] is None
    assert get_project_story_tags("9", "demo")["scene_target_chars"] is None
    assert "约 600-1000 个中文字符" in build_story_tags_hint({**cleared, "workspace_mode": "novel"})


def test_story_length_and_structure_guidance_use_mode_specific_terms() -> None:
    script_length = build_length_hint_str("中篇", "script")
    novel_length = build_length_hint_str("中篇", "novel")
    assert "3个剧幕" in script_length
    assert "3个分卷" in novel_length
    assert "章节" not in script_length
    assert "剧幕" not in novel_length

    script_guidance = build_story_structure_quantity_guidance("script", 3, 5)
    novel_guidance = build_story_structure_quantity_guidance("novel", 3, 12)
    assert "3 个剧幕" in script_guidance
    assert "每幕场景数参考约 5 个" in script_guidance
    assert "3 个分卷" in novel_guidance
    assert "每卷章节数参考约 12 个" in novel_guidance
    for guidance in (script_guidance, novel_guidance):
        assert "历史兼容" in guidance
        assert "语义混乱" in guidance


def test_story_tags_hint_explains_legacy_counts_without_crossing_modes() -> None:
    script_hint = build_story_tags_hint({"workspace_mode": "script"})
    novel_hint = build_story_tags_hint({"workspace_mode": "novel"})

    assert "故事文件夹/故事分组称为“剧幕”" in script_hint
    assert "单个正文文件称为“场景”" in script_hint
    assert "故事文件夹/故事分组称为“分卷”" in novel_hint
    assert "单个正文文件称为“章节”" in novel_hint
    assert "当前场景正文" in script_hint
    assert "当前章节正文" in novel_hint
    assert "剧本中的有效叙事单元" in script_hint
    assert "剧本中的有效叙事单元" not in novel_hint


def test_showrunner_outline_prompt_injects_mode_specific_quantity_guidance() -> None:
    script_terms = build_story_structure_quantity_guidance("script", 3, 5)
    novel_terms = build_story_structure_quantity_guidance("novel", 3, 12)
    common = {
        "story_tags": "",
        "worldview": "",
        "roles": "",
        "style_profile": "",
        "context": "",
        "beat_sheet": "",
        "guidance": "",
        "chapter_count": 3,
        "scene_count_per_chapter": 5,
    }
    script_prompt = load_prompt(
        "showrunner", "generate_outline", **common, structure_terms=script_terms
    )
    novel_prompt = load_prompt(
        "showrunner", "generate_outline", **common, structure_terms=novel_terms
    )
    assert "3 个剧幕" in script_prompt["user"]
    assert "每幕场景数参考约 5 个" in script_prompt["user"]
    assert "3 个分卷" in novel_prompt["user"]
    assert "每卷章节数参考约 12 个" in novel_prompt["user"]

