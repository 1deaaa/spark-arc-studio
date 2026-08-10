from __future__ import annotations

from pathlib import Path

from story.arc_safety import (
    sanitize_arc_ai_fragment,
    sanitize_arc_ai_output,
    sanitize_arc_for_ai_context,
    validate_arc_visual_prompt_candidate,
)


def test_visual_illustration_context_is_strictly_gated() -> None:
    raw = "\n".join([
        "# 1-1 雨夜",
        "[旁白]",
        "她停在门外。",
        "@presentation illustration_prompt:雨夜书店门外，林澈回望，低机位中景",
        "@presentation illustration:ill_secret_asset",
        "@presentation bg:bg_secret_asset",
        "@presentation sprite:sprite_secret_asset",
        "@web illustration_prompt:废弃标签不可见",
        "@act sound:rain",
        "@next 下一场",
    ])

    disabled = sanitize_arc_for_ai_context(raw)
    enabled = sanitize_arc_for_ai_context(raw, allow_visual_illustration=True)

    assert "illustration_prompt" not in disabled
    assert "@presentation illustration_prompt:雨夜书店门外，林澈回望，低机位中景" in enabled
    assert "废弃标签不可见" not in enabled
    assert "ill_secret_asset" not in enabled
    assert "bg_secret_asset" not in enabled
    assert "sprite_secret_asset" not in enabled
    assert "@act" not in enabled
    assert "@next" not in enabled


def test_scriptwriter_visual_protocol_is_absent_when_disabled_and_shared_by_tool_reference(monkeypatch) -> None:
    from agents.agent_scriptwriter import ScriptwriterAgent
    from agents.communication import SparkBaseAgent

    agent = object.__new__(ScriptwriterAgent)
    agent.user_id = "u1"
    monkeypatch.setattr(
        SparkBaseAgent,
        "_build_tool_prompt_reference_block",
        lambda self, *, tools_override=None: "基础工具规范",
    )
    monkeypatch.setattr(
        ScriptwriterAgent,
        "_visual_illustration_settings",
        lambda self: {"enabled": False, "max_per_scene": 2},
    )

    assert agent._prepare_script_system_prompt("基础系统提示") == "基础系统提示"
    assert agent._build_tool_prompt_reference_block() == "基础工具规范"

    monkeypatch.setattr(
        ScriptwriterAgent,
        "_visual_illustration_settings",
        lambda self: {"enabled": True, "max_per_scene": 2},
    )
    specialized = agent._prepare_script_system_prompt("基础系统提示")
    tool_reference = agent._build_tool_prompt_reference_block()

    for prompt in (specialized, tool_reference):
        assert "@presentation illustration_prompt:" in prompt
        assert "@web" not in prompt
        assert "@presentation bg:背景资产ID" in prompt
        assert "只能从下方白名单逐字选择" in prompt
        assert "不得生成 `illustration`、`sprite`、`@act` 或 `@next`" in prompt


def test_visual_illustration_output_enforces_whitelist_scene_limit_and_gap() -> None:
    raw = "\n".join([
        "# 1-1 雨夜",
        "[旁白]",
        "节点零。",
        "@presentation illustration_prompt:第一张",
        "@presentation illustration:ill_fake",
        "@web illustration_prompt:废弃标签应丢弃",
        "[林澈]",
        "节点一。",
        "@presentation illustration_prompt:相邻节点应丢弃",
        "[旁白]",
        "节点二。",
        "@presentation illustration_prompt:第二张，包含逗号",
        "[林澈]",
        "节点三。",
        "@presentation illustration_prompt:超过上限",
        "@act bg:forbidden",
        "@next forbidden",
        "# 1-2 清晨",
        "[旁白]",
        "新场景。",
        "@presentation illustration_prompt:新场景重新计数",
    ])

    cleaned = sanitize_arc_ai_output(
        raw,
        allow_visual_illustration=True,
        max_per_scene=2,
        min_node_gap=1,
    )

    assert cleaned.count("@presentation illustration_prompt:") == 3
    assert "@presentation illustration_prompt:第一张" in cleaned
    assert "@presentation illustration_prompt:第二张，包含逗号" in cleaned
    assert "@presentation illustration_prompt:新场景重新计数" in cleaned
    assert "废弃标签应丢弃" not in cleaned
    assert "相邻节点应丢弃" not in cleaned
    assert "超过上限" not in cleaned
    assert "ill_fake" not in cleaned
    assert "@act" not in cleaned
    assert "@next" not in cleaned


def test_ai_fragment_keeps_isolated_prompt_but_removes_runtime_controls() -> None:
    fragment = "\n".join([
        "@act sound:rain",
        "@next 下一场",
        "@presentation bg:bg_secret",
        "@presentation illustration_prompt:  雨夜书店   低机位  ",
    ])

    cleaned = sanitize_arc_ai_fragment(fragment, allow_visual_illustration=True)

    assert cleaned == "@presentation illustration_prompt:雨夜书店 低机位"


def test_incremental_visual_policy_preserves_existing_manual_violation_but_rejects_new_one() -> None:
    original = "\n".join([
        "# 1-1",
        "[旁白]",
        "节点零。",
        "@presentation illustration_prompt:第一张",
        "[林澈]",
        "节点一。",
    ])
    safe_candidate = original.replace("节点一。", "节点一，改写。")
    unsafe_candidate = safe_candidate + "\n@presentation illustration_prompt:相邻新增"

    validate_arc_visual_prompt_candidate(
        original,
        safe_candidate,
        max_per_scene=2,
        min_node_gap=1,
    )

    try:
        validate_arc_visual_prompt_candidate(
            original,
            unsafe_candidate,
            max_per_scene=2,
            min_node_gap=1,
        )
    except ValueError as exc:
        assert "视觉插图描述" in str(exc)
    else:
        raise AssertionError("新增相邻插图描述应被硬门禁拒绝")


def test_patch_script_validates_merged_scene_without_removing_manual_cues(monkeypatch, tmp_path: Path) -> None:
    from agents.tools.scriptwriter import patch_script
    from core.request_context import current_project_name, current_user_id
    from core.utils import get_project_stories_path

    monkeypatch.setattr("core.utils.USERDATA_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "core.project_settings.get_visual_illustration_settings",
        lambda user_id, project_name: {"max_per_scene": 2, "min_node_gap": 1},
    )
    monkeypatch.setattr(
        "core.project_settings.is_visual_illustration_enabled",
        lambda user_id, project_name: True,
    )
    stories_path = Path(get_project_stories_path("7", "demo"))
    stories_path.mkdir(parents=True, exist_ok=True)
    story_path = stories_path / "001_雨夜.arc"
    original = "\n".join([
        "# 1-1 雨夜",
        "[旁白]",
        "节点零。",
        "@presentation bg:bg_keep",
        "@presentation illustration_prompt:第一张",
        "[林澈]",
        "节点一。",
        "[旁白]",
        "节点二。",
        "@presentation illustration_prompt:第二张",
        "[林澈]",
        "节点三。",
        "@act sound:rain",
        "@next 下一场",
    ])
    story_path.write_text(original, encoding="utf-8")

    user_token = current_user_id.set("7")
    project_token = current_project_name.set("demo")
    try:
        result = patch_script.invoke({
            "search_text": "@presentation illustration_prompt:第二张",
            "replace_text": "@act bg:forbidden\n@presentation illustration_prompt:第二张新描述",
        })
        assert "已成功局部更新" in result
        updated = story_path.read_text(encoding="utf-8")
        assert "@presentation illustration_prompt:第二张新描述" in updated
        assert "forbidden" not in updated
        assert "@presentation bg:bg_keep" in updated
        assert "@act sound:rain" in updated
        assert "@next 下一场" in updated

        rejected = patch_script.invoke({
            "search_text": "[林澈]\n节点三。",
            "replace_text": "[林澈]\n节点三。\n@presentation illustration_prompt:第三张",
        })
        assert rejected.startswith("局部修改失败")
        assert story_path.read_text(encoding="utf-8") == updated
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)


def test_production_node_cleaner_only_keeps_visual_prompt() -> None:
    from agents.routes.production import _clean_generated_nodes

    nodes = [{
        "id": 1,
        "speaker": "林澈",
        "txt": "别回头。",
        "act": {"bg": "forbidden"},
        "next": "forbidden",
        "presentation": {
            "bg": "bg_forbidden",
            "illustration": "ill_forbidden",
            "illustration_prompt": "  雨夜回望  ",
        },
        "unknown": "forbidden",
    }]

    cleaned = _clean_generated_nodes(nodes, allow_visual_illustration=True)

    assert cleaned == [{
        "id": 1,
        "speaker": "林澈",
        "txt": "别回头。",
        "presentation": {"illustration_prompt": "雨夜回望"},
    }]


def test_illustration_prompt_with_commas_remains_scalar_in_arc_parser() -> None:
    from story.arc_parser import parse_arc, serialize_to_arc

    raw = "# 雨夜\n[旁白]\n她停在门外。\n@presentation illustration_prompt:雨夜书店，低机位，中景"
    parsed = parse_arc(raw)

    assert parsed[0]["dia"][0]["presentation"]["illustration_prompt"] == "雨夜书店，低机位，中景"
    assert "@presentation illustration_prompt:雨夜书店，低机位，中景" in serialize_to_arc(parsed)


def test_ai_background_binding_requires_project_asset_whitelist() -> None:
    raw = "\n".join([
        "# 校园",
        "[旁白]",
        "雨停了。",
        "@presentation illustration_prompt:雨后的教学楼走廊，傍晚",
        "@presentation bg:bg_school_corridor",
        "[旁白]",
        "镜头转向不存在的地点。",
        "@presentation bg:bg_hallucinated",
    ])

    cleaned = sanitize_arc_ai_output(
        raw,
        allow_visual_illustration=True,
        allowed_background_ids={"bg_school_corridor"},
    )

    assert "@presentation bg:bg_school_corridor" in cleaned
    assert "bg_hallucinated" not in cleaned


def test_model_context_exposes_only_whitelisted_background_binding() -> None:
    raw = "\n".join([
        "[旁白]",
        "走廊空无一人。",
        "@presentation bg:bg_school_corridor",
        "@presentation bg:bg_private",
    ])

    cleaned = sanitize_arc_for_ai_context(
        raw,
        allow_visual_illustration=True,
        allowed_background_ids={"bg_school_corridor"},
    )

    assert "@presentation bg:bg_school_corridor" in cleaned
    assert "bg_private" not in cleaned


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


def test_scriptwriter_novel_stream_never_exposes_split_conception_field(monkeypatch) -> None:
    from types import SimpleNamespace

    from agents import agent_scriptwriter as scriptwriter_module
    from agents.agent_scriptwriter import ScriptwriterAgent
    from story.novel_parser import clean_novel_visible_text

    class FakeLlm:
        def stream(self, _messages):
            for content in (
                "concep",
                "tion: 隐藏构思\n",
                "\n正文第一",
                "段。\n",
                "正文第二段。",
            ):
                yield SimpleNamespace(content=content)

    monkeypatch.setattr(
        scriptwriter_module,
        "load_prompt",
        lambda *_args, **_kwargs: {"system": "system", "user": "user"},
    )
    agent = object.__new__(ScriptwriterAgent)
    agent.llm = FakeLlm()
    agent._get_arc_example = lambda: ""
    agent._build_chr_reference = lambda _chr_map: ""
    agent._build_write_messages = lambda **_kwargs: []
    agent._extract_arc_script = clean_novel_visible_text

    events = list(
        agent.write_script_stream(
            context="",
            worldview="",
            roles="",
            export_format="novel",
        )
    )
    visible_chunks = "".join(event["content"] for event in events if event["type"] == "chunk")
    done = events[-1]

    assert visible_chunks == "正文第一段。\n正文第二段。"
    assert done["arc_script"] == visible_chunks
    assert "隐藏构思" not in visible_chunks
