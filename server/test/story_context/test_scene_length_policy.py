from __future__ import annotations

from core.project_settings import get_project_story_tags, set_project_story_tags
from agents.routes.context_builder import build_story_tags_hint


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

