from __future__ import annotations

from story import presentation_generation as generation


def test_visual_generation_prompt_combines_project_context_and_reference_roles(monkeypatch) -> None:
    monkeypatch.setattr(generation, "load_worldview", lambda user_id, project_name: "近未来海港城，终年多雨。")
    monkeypatch.setattr(
        generation,
        "get_visual_style_settings",
        lambda user_id, project_name: {
            "seed_prompt": "清透赛璐璐，冷暖霓虹对比",
            "reference_asset_id": "style_demo",
        },
    )
    monkeypatch.setattr(
        generation,
        "get_visual_illustration_settings",
        lambda user_id, project_name: {
            "sprite_chroma_key": "#00FF00",
        },
    )
    monkeypatch.setattr(
        generation,
        "_load_character_contexts",
        lambda user_id, project_name, character_ids: [{
            "id": "7",
            "name": "林澈",
            "profile": "短黑发，灰蓝风衣，左眼下有泪痣。",
        }],
    )

    prompt, snapshot = generation.build_visual_generation_prompt(
        user_id="u1",
        project_name="demo",
        asset_type="scene_illustration",
        creative_prompt="林澈握住书店门把手回望。",
        context={
            "sceneName": "雨夜书店",
            "sceneIntro": "追兵正在接近。",
            "nodeText": "林澈：别回头。",
            "nearbyDialogue": ["旁白：霓虹映在积水中。"],
            "characterIds": ["7"],
        },
        references=[
            {"assetId": "style_demo", "role": "style", "title": "项目种子"},
            {"assetId": "bg_bookstore", "role": "scene", "title": "书店外景"},
            {"assetId": "sprite_lin", "role": "character", "characterId": "7"},
            {"assetId": "ill_prev", "role": "continuity"},
        ],
    )

    assert "清透赛璐璐" in prompt
    assert "近未来海港城" in prompt
    assert "雨夜书店" in prompt
    assert "林澈" in prompt
    assert "职责 style" in prompt
    assert "职责 scene" in prompt
    assert "职责 character" in prompt
    assert "职责 continuity" in prompt
    assert "中央安全区" in prompt
    assert "禁止生成 UI" in prompt
    assert snapshot["characterIds"] == ["7"]
    assert [item["role"] for item in snapshot["references"]] == [
        "style",
        "scene",
        "character",
        "continuity",
    ]


def test_sprite_prompt_requires_uniform_chroma_key(monkeypatch) -> None:
    monkeypatch.setattr(generation, "load_worldview", lambda user_id, project_name: "")
    monkeypatch.setattr(
        generation,
        "get_visual_style_settings",
        lambda user_id, project_name: {"seed_prompt": "手绘动画", "reference_asset_id": None},
    )
    monkeypatch.setattr(
        generation,
        "get_visual_illustration_settings",
        lambda user_id, project_name: {"sprite_chroma_key": "#00FF00"},
    )
    monkeypatch.setattr(generation, "_load_character_contexts", lambda *args, **kwargs: [])

    prompt, _ = generation.build_visual_generation_prompt(
        user_id="u1",
        project_name="demo",
        asset_type="character_sprite",
        creative_prompt="自然站姿",
        context={"characterIds": ["1"]},
    )

    assert "纯色 #00FF00" in prompt
    assert "无纹理、无阴影、无渐变" in prompt
    assert "不裁切肢体" in prompt


def test_style_seed_prompt_does_not_implicitly_inject_project_characters(monkeypatch) -> None:
    monkeypatch.setattr(generation, "load_worldview", lambda user_id, project_name: "近未来海港城。")
    monkeypatch.setattr(
        generation,
        "get_visual_style_settings",
        lambda user_id, project_name: {"seed_prompt": "", "reference_asset_id": None},
    )
    monkeypatch.setattr(
        generation,
        "get_visual_illustration_settings",
        lambda user_id, project_name: {"sprite_chroma_key": "#00FF00"},
    )
    monkeypatch.setattr(
        generation,
        "load_character_id_name_map",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("风格候选不应枚举项目角色")),
    )
    captured_ids: list[str] = []

    def capture_character_ids(user_id, project_name, character_ids):
        captured_ids.extend(character_ids)
        return []

    monkeypatch.setattr(generation, "_load_character_contexts", capture_character_ids)

    prompt, snapshot = generation.build_visual_generation_prompt(
        user_id="u1",
        project_name="demo",
        asset_type="style_reference",
        creative_prompt="二次元手绘，清透线条，冷暖霓虹对比",
        context={},
    )

    assert captured_ids == []
    assert snapshot["characterIds"] == []
    assert snapshot["characters"] == []
    assert "本画面涉及的角色档案" not in prompt


def test_saved_style_reference_is_always_injected_before_explicit_references(monkeypatch) -> None:
    from story import routes_presentation as routes

    monkeypatch.setattr(
        routes,
        "load_project_manifest",
        lambda user_id, project_name: {
            "assets": {
                "style_saved": {"id": "style_saved", "type": "style_reference", "title": "已定风格"},
                "scene_manual": {"id": "scene_manual", "type": "background", "title": "场景参考"},
            }
        },
    )
    monkeypatch.setattr(
        routes,
        "get_visual_style_settings",
        lambda user_id, project_name: {"reference_asset_id": "style_saved"},
    )
    monkeypatch.setattr(routes, "load_character_id_name_map", lambda *args, **kwargs: {})

    resolved = routes._resolve_reference_descriptors(
        "u1",
        "demo",
        asset_ids=[],
        references=[routes.VisualReferenceRequest(assetId="scene_manual", role="scene")],
    )

    assert [(item["assetId"], item["role"]) for item in resolved] == [
        ("style_saved", "style"),
        ("scene_manual", "scene"),
    ]
