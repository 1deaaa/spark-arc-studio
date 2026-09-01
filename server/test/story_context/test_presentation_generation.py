from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from starlette.requests import ClientDisconnect

from story import presentation_generation as generation


def test_visual_generation_prompt_combines_project_context_and_reference_roles(monkeypatch) -> None:
    monkeypatch.setattr(generation, "load_worldview", lambda user_id, project_name: "近未来海港城，终年多雨。")
    monkeypatch.setattr(
        generation,
        "get_visual_style_settings",
        lambda user_id, project_name: {
            "seed_prompt": "清透赛璐璐，冷暖霓虹对比",
            "reference_asset_ids": ["style_demo"],
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
        lambda user_id, project_name: {"seed_prompt": "手绘动画", "reference_asset_ids": []},
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
        lambda user_id, project_name: {"seed_prompt": "", "reference_asset_ids": []},
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


def test_five_saved_style_references_are_injected_before_other_reference_roles(monkeypatch) -> None:
    from story import routes_presentation as routes

    style_ids = [f"style_{index}" for index in range(1, 7)]

    monkeypatch.setattr(
        routes,
        "load_project_manifest",
        lambda user_id, project_name: {
            "assets": {
                **{
                    asset_id: {"id": asset_id, "type": "style_reference", "title": f"风格 {asset_id}"}
                    for asset_id in style_ids
                },
                "scene_manual": {"id": "scene_manual", "type": "background", "title": "场景参考"},
                "character_manual": {"id": "character_manual", "type": "character_sprite", "title": "角色参考"},
                "continuity_manual": {"id": "continuity_manual", "type": "scene_illustration", "title": "连续性参考"},
            }
        },
    )
    monkeypatch.setattr(
        routes,
        "get_visual_style_settings",
        lambda user_id, project_name: {"reference_asset_ids": style_ids},
    )
    monkeypatch.setattr(routes, "load_character_id_name_map", lambda *args, **kwargs: {})

    resolved = routes._resolve_reference_descriptors(
        "u1",
        "demo",
        asset_ids=[],
        references=[
            routes.VisualReferenceRequest(assetId="scene_manual", role="scene"),
            routes.VisualReferenceRequest(assetId="character_manual", role="character"),
            routes.VisualReferenceRequest(assetId="continuity_manual", role="continuity"),
        ],
    )

    assert [(item["assetId"], item["role"]) for item in resolved] == [
        *((asset_id, "style") for asset_id in style_ids[:5]),
        ("scene_manual", "scene"),
        ("character_manual", "character"),
        ("continuity_manual", "continuity"),
    ]


def test_visual_asset_resolves_model_once_and_drops_references_for_text_only_model(monkeypatch) -> None:
    from story import routes_presentation as routes

    model_config = {
        "base_url": "https://ai.example.test/v1",
        "api_key": "test-key",
        "model_name": "gemini-3.1-flash-lite-image",
        "input_modalities": ["text"],
        "output_modalities": ["image"],
        "image_generation_adapter": "gemini_generate_content",
    }
    resolve_calls: list[dict] = []
    descriptor_calls: list[dict] = []
    generation_call: dict = {}

    class FakeMatchbox:
        def resolve_user_image_generation_model(self, **kwargs):
            resolve_calls.append(kwargs)
            return model_config

    monkeypatch.setattr(routes, "matchbox", lambda: FakeMatchbox())

    def capture_descriptors(*args, **kwargs):
        descriptor_calls.append(kwargs)
        return []

    monkeypatch.setattr(routes, "_resolve_reference_descriptors", capture_descriptors)
    monkeypatch.setattr(
        routes,
        "build_visual_generation_prompt",
        lambda **kwargs: ("已拼好的背景提示词", {"references": kwargs["references"]}),
    )
    monkeypatch.setattr(
        routes,
        "_load_reference_assets",
        lambda _user_id, _project_name, descriptors: [] if not descriptors else pytest.fail("文本模型不应加载参考图"),
    )

    def capture_generation(**kwargs):
        generation_call.update(kwargs)
        return SimpleNamespace(
            image=b"png",
            mime_type="image/png",
            revised_prompt="",
            provider="gemini_generate_content",
            platform_id=7,
            model_id=8,
            model_name="gemini-3.1-flash-lite-image",
        )

    monkeypatch.setattr(routes, "generate_image_for_user", capture_generation)
    monkeypatch.setattr(
        routes,
        "upload_background_asset",
        lambda **kwargs: {"id": "bg_test", "path": "presentation/bg_test.png", **kwargs},
    )
    monkeypatch.setattr(routes, "_persist_generated_asset_metadata", lambda **_kwargs: {"assets": {}})

    data = routes.GenerateBackgroundRequest(
        prompt="雨夜书店背景",
        platformId=7,
        modelId=8,
        referenceAssetIds=["style_seed"],
        referenceAssets=[routes.VisualReferenceRequest(assetId="scene_ref", role="scene")],
    )
    asset, manifest = asyncio.run(routes._generate_visual_asset(
        user_id="u1",
        project_name="demo",
        asset_type="background",
        data=data,
    ))

    assert asset["id"] == "bg_test"
    assert manifest == {"assets": {}}
    assert resolve_calls == [{"user_id": "u1", "platform_id": 7, "model_id": 8}]
    assert descriptor_calls == [{
        "asset_ids": ["style_seed"],
        "references": data.referenceAssets,
        "allow_image_references": False,
    }]
    assert generation_call["resolved_config"] is model_config
    assert generation_call["references"] == []


def test_visual_asset_skips_commit_when_client_is_already_disconnected(monkeypatch) -> None:
    from story import routes_presentation as routes

    calls: list[str] = []

    class DisconnectedRequest:
        async def is_disconnected(self):
            calls.append("disconnect-check")
            return True

    monkeypatch.setattr(
        routes,
        "matchbox",
        lambda: pytest.fail("客户端已断开时不应解析生图模型"),
    )
    data = routes.GenerateBackgroundRequest(prompt="雨夜书店背景")

    with pytest.raises(ClientDisconnect):
        asyncio.run(routes._generate_visual_asset(
            user_id="u1",
            project_name="demo",
            asset_type="background",
            data=data,
            request=DisconnectedRequest(),
        ))

    assert calls == ["disconnect-check"]


def test_visual_asset_cleans_up_after_client_disconnects_post_commit(monkeypatch) -> None:
    from story import routes_presentation as routes

    model_config = {
        "model_name": "gemini-3.1-flash-lite-image",
        "input_modalities": ["text"],
        "output_modalities": ["image"],
        "image_generation_adapter": "gemini_generate_content",
    }
    cleanup_calls: list[tuple[tuple, dict]] = []

    class DisconnectingRequest:
        def __init__(self):
            self.checks = 0

        async def is_disconnected(self):
            self.checks += 1
            return self.checks > 2

    class FakeMatchbox:
        def resolve_user_image_generation_model(self, **kwargs):
            return model_config

    monkeypatch.setattr(routes, "matchbox", lambda: FakeMatchbox())
    monkeypatch.setattr(routes, "_resolve_reference_descriptors", lambda *args, **kwargs: [])
    monkeypatch.setattr(routes, "build_visual_generation_prompt", lambda **kwargs: ("提示词", {}))
    monkeypatch.setattr(routes, "_load_reference_assets", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        routes,
        "generate_image_for_user",
        lambda **kwargs: SimpleNamespace(
            image=b"png",
            mime_type="image/png",
            revised_prompt="",
            provider="gemini_generate_content",
            platform_id=7,
            model_id=8,
            model_name="gemini-3.1-flash-lite-image",
        ),
    )
    monkeypatch.setattr(
        routes,
        "upload_background_asset",
        lambda **kwargs: {"id": "bg_test", "source": "ai", "path": "assets/presentation/bg_test.png"},
    )
    monkeypatch.setattr(routes, "_persist_generated_asset_metadata", lambda **kwargs: {"assets": {"bg_test": {}}})
    monkeypatch.setattr(
        routes,
        "remove_presentation_asset",
        lambda *args, **kwargs: cleanup_calls.append((args, kwargs)) or True,
    )

    with pytest.raises(ClientDisconnect):
        asyncio.run(routes._generate_visual_asset(
            user_id="u1",
            project_name="demo",
            asset_type="background",
            data=routes.GenerateBackgroundRequest(prompt="雨夜书店背景"),
            request=DisconnectingRequest(),
        ))

    assert cleanup_calls == [
        (("u1", "demo", "bg_test"), {"expected_source": "ai"}),
    ]


def test_image_generation_route_preserves_upstream_status_code() -> None:
    from llm.agen_matchbox.image_generation import ImageGenerationError
    from story import routes_presentation as routes

    response = routes._image_generation_error_response(
        "生成背景图失败",
        ImageGenerationError("上游节点故障", status_code=500),
    )

    assert response.status_code == 500
    payload = json.loads(response.body)
    assert payload["upstreamStatusCode"] == 500
    assert payload["error"] == "生成背景图失败: 上游节点故障"


def test_model_error_status_parser_accepts_wrapped_upstream_error() -> None:
    from story import routes_presentation as routes

    assert routes._extract_http_status(RuntimeError("Error code: 401 - unauthorized")) == 401
    assert routes._extract_http_status(RuntimeError("status_code=429")) == 429


def test_illustration_conception_prompt_combines_project_context_and_target_node(monkeypatch) -> None:
    monkeypatch.setattr(
        generation,
        "load_worldview",
        lambda user_id, project_name: "近未来海港城，雨季持续三个月。",
    )
    monkeypatch.setattr(
        generation,
        "get_visual_style_settings",
        lambda user_id, project_name: {"seed_prompt": "清透赛璐璐，冷暖霓虹", "reference_asset_ids": []},
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

    prompt, snapshot = generation.build_illustration_conception_prompt(
        user_id="u1",
        project_name="demo",
        scene_name="雨夜书店",
        node_id="42",
        context={
            "sceneIntro": "追兵正在接近。",
            "sceneConception": "让门内外形成强烈的安全感反差。",
            "nodeText": "林澈：别回头。",
            "nearbyDialogue": ["旁白：霓虹映在积水中。"],
            "characterIds": ["7", "7"],
        },
        existing_prompt="保留门口的雨幕。",
    )

    assert "近未来海港城" in prompt
    assert "清透赛璐璐" in prompt
    assert "雨夜书店" in prompt
    assert "追兵正在接近" in prompt
    assert "林澈" in prompt
    assert "保留门口的雨幕" in prompt
    assert snapshot["schema"] == "sparkarc.illustration-conception.v1"
    assert snapshot["nodeId"] == "42"
    assert snapshot["characterIds"] == ["7"]
    assert snapshot["nearbyDialogue"] == ["旁白：霓虹映在积水中。"]


def test_scriptwriter_illustration_conception_uses_agent_model_and_budget(monkeypatch) -> None:
    from agents import agent_scriptwriter as scriptwriter_module
    from agents.agent_scriptwriter import ScriptwriterAgent

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        generation,
        "build_illustration_conception_prompt",
        lambda **kwargs: ("动态叙事现场", {"nodeId": kwargs["node_id"]}),
    )

    class FakeLlm:
        def invoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content="演出构思：雨夜书店门外，林澈在霓虹雨幕中回望，低机位中景。")

    fake_llm = FakeLlm()
    agent = object.__new__(ScriptwriterAgent)
    agent.user_id = "u1"
    agent._get_invoke_llm = lambda: fake_llm

    def fake_budget(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(messages=["prepared-message"])

    monkeypatch.setattr(scriptwriter_module, "prepare_specialized_prompt_messages_with_budget", fake_budget)

    result = agent.generate_illustration_conception(
        project_name="demo",
        scene_name="雨夜书店",
        node_id="42",
        context={"nodeText": "林澈：别回头。"},
    )

    assert result == "雨夜书店门外，林澈在霓虹雨幕中回望，低机位中景。"
    assert captured["agent_id"] == "agent_scriptwriter"
    assert captured["user_prompt"] == "动态叙事现场"
    assert captured["llm_client"] is fake_llm
    assert captured["messages"] == ["prepared-message"]
    assert "视觉演出构思助手" in str(captured["system_prompt"])


def test_illustration_conception_route_sets_context_and_passes_model_input(monkeypatch) -> None:
    from story import routes_presentation as routes

    calls: dict[str, object] = {}
    monkeypatch.setattr(routes, "_presentation_project_error", lambda *_args: None)
    monkeypatch.setattr(routes, "is_visual_illustration_enabled", lambda *_args: True)
    monkeypatch.setattr(
        routes,
        "set_agent_context",
        lambda user_id, project_name: calls.update({"context": (user_id, project_name)}),
    )

    class FakeAgent:
        def __init__(self, user_id):
            calls["agent_user_id"] = user_id

        def generate_illustration_conception(self, **kwargs):
            calls["generation"] = kwargs
            return "雨夜书店门外的低机位画面。"

    monkeypatch.setattr("agents.agent_scriptwriter.ScriptwriterAgent", FakeAgent)
    data = routes.GenerateIllustrationConceptionRequest(
        sceneName="雨夜书店",
        nodeId="42",
        currentPrompt="保留雨幕",
        context=routes.VisualGenerationContextRequest(
            nodeText="林澈：别回头。",
            characterIds=["7"],
        ),
    )

    result = asyncio.run(
        routes.generate_presentation_illustration_conception(
            "demo",
            data,
            user={"user_id": "u1"},
        )
    )

    assert result == {
        "success": True,
        "prompt": "雨夜书店门外的低机位画面。",
        "sceneName": "雨夜书店",
        "nodeId": "42",
    }
    assert calls["context"] == ("u1", "demo")
    assert calls["agent_user_id"] == "u1"
    assert calls["generation"] == {
        "project_name": "demo",
        "scene_name": "雨夜书店",
        "node_id": "42",
        "context": {"sceneName": "", "sceneIntro": "", "sceneConception": "", "nodeText": "林澈：别回头。", "nearbyDialogue": None, "characterIds": ["7"]},
        "existing_prompt": "保留雨幕",
    }


def test_illustration_conception_route_marks_upstream_500(monkeypatch) -> None:
    from story import routes_presentation as routes

    monkeypatch.setattr(routes, "_presentation_project_error", lambda *_args: None)
    monkeypatch.setattr(routes, "is_visual_illustration_enabled", lambda *_args: True)

    class UpstreamModelError(RuntimeError):
        status_code = 500

    class FailingAgent:
        def __init__(self, user_id):
            pass

        def generate_illustration_conception(self, **kwargs):
            raise UpstreamModelError("上游节点返回 HTTP 500")

    monkeypatch.setattr("agents.agent_scriptwriter.ScriptwriterAgent", FailingAgent)
    response = asyncio.run(
        routes.generate_presentation_illustration_conception(
            "demo",
            routes.GenerateIllustrationConceptionRequest(sceneName="雨夜书店", nodeId="42"),
            user={"user_id": "u1"},
        )
    )

    assert response.status_code == 500
    assert response.headers["X-Spark-Upstream-Error"] == "true"
    assert response.headers["X-Spark-Upstream-Status"] == "500"
    payload = json.loads(response.body)
    assert payload["success"] is False
    assert payload["error"] == "生成演出构思失败: 上游节点返回 HTTP 500"
