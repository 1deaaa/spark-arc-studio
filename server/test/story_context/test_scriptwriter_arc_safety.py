from __future__ import annotations

from pathlib import Path

from story.arc_safety import sanitize_arc_for_ai_context


def test_arc_safety_removes_runtime_control_directives_from_ai_context() -> None:
    raw = "\n".join(
        [
            "# 1-1 初遇",
            "[-1]",
            "雨声压低了街角的霓虹。",
            "@act bg:rainy_alley",
            "@act BG:rainy_alley",
            "@act sprite:hero_default",
            "@act sound:rain_loop",
            "@web bg:web_alley",
            "@presentation sprite:web_hero",
            "@next 旧仓库",
            "[0]",
            "我们得快点离开。",
        ]
    )

    cleaned = sanitize_arc_for_ai_context(raw)

    assert "@act bg:" not in cleaned
    assert "@act BG:" not in cleaned
    assert "@act sprite:" not in cleaned
    assert "@act sound:rain_loop" not in cleaned
    assert "@web bg:" not in cleaned
    assert "@presentation sprite:" not in cleaned
    assert "@next" not in cleaned
    assert "雨声压低了街角的霓虹。" in cleaned


def test_production_context_pack_sanitizes_arc_controls_before_prompt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    project_path = tmp_path / "uid_41" / "projects" / "demo"
    stories_path = project_path / "stories" / "一 · 开端"
    stories_path.mkdir(parents=True)
    (stories_path / "1-1 初遇.arc").write_text(
        "\n".join(
            [
                "# 1-1 初遇",
                "@guide",
                "街角相遇。",
                "[-1]",
                "雨幕落下。",
                "@act bg:rainy_alley",
                "@act sprite:hero_default",
                "@web bg:web_rainy_alley",
                "@presentation sprite:web_hero_default",
                "@next 1-2 旧仓库",
                "[0]",
                "跟我走。",
            ]
        ),
        encoding="utf-8",
    )

    from agents.routes.production import build_scriptwriter_context_pack

    pack = build_scriptwriter_context_pack(
        user_id="41",
        project_name="demo",
        operation="continue",
        file_path="一 · 开端/1-1 初遇.arc",
        scene_name="1-1 初遇",
        context="@act bg:manual_context\n@act sound:manual_sound\n@web bg:manual_web\n@presentation sprite:manual_sprite\n@next 某处\n[-1]\n额外上下文。",
    )

    combined = "\n".join([pack["context"], pack["local_script"]])
    assert "@act bg:" not in combined
    assert "@act sprite:" not in combined
    assert "@act sound:" not in combined
    assert "@web bg:" not in combined
    assert "@presentation sprite:" not in combined
    assert "@next" not in combined
    assert "雨幕落下。" in combined
    assert "额外上下文。" in combined


def test_arc_context_sanitizer_keeps_narrative_lines() -> None:
    text = "[-1]\n背景灯一盏盏暗下去。\n@act sound:灯灭\n@web bg:dark_room\n@next 隐藏场景"
    assert sanitize_arc_for_ai_context(text) == "[-1]\n背景灯一盏盏暗下去。"


def test_project_file_arc_enrichment_uses_clean_model_visible_view() -> None:
    from story.project_files import enrich_arc_content_for_model

    text = "\n".join(
        [
            "# 1-1 初遇",
            "[0]",
            "窗外雨声渐近。",
            "@act sound:rain_loop",
            "@web bg:rainy_window",
            "@presentation sprite:hero_default",
            "@next 1-2",
        ]
    )

    enriched = enrich_arc_content_for_model(text, {"0": "林澈"})

    assert "【可用说话人】" in enriched
    assert "[0] =" not in enriched
    assert "[林澈]" in enriched
    assert "窗外雨声渐近。" in enriched
    assert "@act" not in enriched
    assert "@web" not in enriched
    assert "@presentation" not in enriched
    assert "@next" not in enriched


def test_scriptwriter_tool_results_use_clean_model_visible_arc_view(monkeypatch) -> None:
    from agents.agent_scriptwriter import ScriptwriterAgent
    from agents.communication import SparkBaseAgent

    dirty_tool_result = "\n".join(
        [
            "## 剧本文件: 旧场景.arc",
            "[-1]",
            "雨落在玻璃上。",
            "@act bg:old_background",
            "@act sprite:old_sprite",
            "@act sound:old_rain",
            "@web bg:old_web_background",
            "@next 下一场",
        ]
    )

    monkeypatch.setattr(
        SparkBaseAgent,
        "_execute_tool_calls",
        lambda self, tool_calls: dirty_tool_result,
    )

    agent = object.__new__(ScriptwriterAgent)
    cleaned = agent._execute_tool_calls([])

    assert "@act bg:" not in cleaned
    assert "@act sprite:" not in cleaned
    assert "@act sound:" not in cleaned
    assert "@web bg:" not in cleaned
    assert "@next" not in cleaned
    assert "雨落在玻璃上。" in cleaned


def test_scriptwriter_chat_context_uses_clean_model_visible_arc_view(monkeypatch) -> None:
    from agents.agent_scriptwriter import ScriptwriterAgent
    from agents.communication import SparkBaseAgent

    captured: dict[str, str] = {}

    def fake_chat(self, user_message, history=None, active_context=None):
        captured["active_context"] = active_context or ""
        captured["history_content"] = ((history or [{}])[0].get("content") or "")
        return "ok"

    monkeypatch.setattr(SparkBaseAgent, "chat", fake_chat)

    agent = object.__new__(ScriptwriterAgent)
    result = agent.chat(
        "帮我看一下这段。",
        history=[{"content": "[-1]\n旧文本\n@next 历史跳转"}],
        active_context="[-1]\n当前文本\n@act bg:old_background\n@act sound:old_rain\n@act sprite:old_sprite\n@web bg:old_web_background",
    )

    assert result == "ok"
    assert "@act bg:" not in captured["active_context"]
    assert "@act sound:" not in captured["active_context"]
    assert "@act sprite:" not in captured["active_context"]
    assert "@web bg:" not in captured["active_context"]
    assert "@next" not in captured["history_content"]
    assert "当前文本" in captured["active_context"]
    assert "旧文本" in captured["history_content"]
