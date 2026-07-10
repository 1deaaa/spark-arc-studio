from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any

import pytest

from llm.agen_matchbox.image_generation import (
    ImageReference,
    ImageGenerationError,
    SparkImageRequest,
    _generate_gemini_interactions_image,
    _generate_openai_chat_image,
    _generate_openai_compatible_image,
    _generate_openai_responses_image,
    _generate_xai_image,
    _select_adapter,
)
from llm.agen_matchbox.models import MODALITY_IMAGE, MODALITY_TEXT
from llm.agen_matchbox.image_adapters import IMAGE_GENERATION_ADAPTERS
from llm.agen_matchbox.gui.dialogs import DialogsMixin


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], *, ok: bool = True, status_code: int = 200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = ""
        self.headers = {"content-type": "image/png"}
        self.content = b""

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeRequests:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse(self.payload)


def _png_b64() -> str:
    return base64.b64encode(b"\x89PNG\r\n\x1a\nadapter-test").decode("ascii")


def test_image_adapter_registry_is_visible_in_web_gui_and_readmes() -> None:
    root = Path(__file__).resolve().parents[3]
    surfaces = {
        "Web 协议镜像": root / "client/src/services/imageGenerationAdapters.ts",
        "中文 README": root / "server/llm/agen_matchbox/README.md",
        "英文 README": root / "server/llm/agen_matchbox/README.en.md",
    }

    for label, path in surfaces.items():
        content = path.read_text(encoding="utf-8")
        missing = sorted(adapter for adapter in IMAGE_GENERATION_ADAPTERS if adapter not in content)
        assert not missing, f"{label} 缺少生图协议: {missing}"

    assert set(DialogsMixin.IMAGE_ADAPTER_OPTIONS.values()) == IMAGE_GENERATION_ADAPTERS


def test_image_adapter_selection_keeps_supported_provider_names_explicit() -> None:
    assert _select_adapter({"base_url": "https://api.openai.com/v1", "extra_body": {}}) == "openai_images"
    assert _select_adapter({"base_url": "https://api.x.ai/v1", "extra_body": {}}) == "openai_images"
    assert _select_adapter({"base_url": "https://generativelanguage.googleapis.com/v1beta", "extra_body": {}}) == "openai_images"
    assert _select_adapter({
        "base_url": "https://ai.1dea.top/v1",
        "image_generation_adapter": "xai",
        "extra_body": {},
    }) == "xai_images"
    assert _select_adapter({
        "base_url": "https://ai.1dea.top/v1",
        "image_generation_adapter": "gemini_generate_content",
        "extra_body": {},
    }) == "gemini_generate_content"
    assert _select_adapter({
        "base_url": "https://ai.1dea.top/v1",
        "image_generation_adapter": "openai_chat_image",
        "extra_body": {},
    }) == "openai_chat_image"
    assert _select_adapter({
        "base_url": "https://api.openai.com/v1",
        "image_generation_adapter": "openai_responses_image",
        "extra_body": {},
    }) == "openai_responses_image"
    assert _select_adapter({
        "base_url": "https://ai.1dea.top/v1",
        "extra_body": {"provider": "xai", "adapter": "gemini_interactions"},
    }) == "openai_images"
    assert _select_adapter({
        "base_url": "https://ai.1dea.top/v1",
        "extra_body": {"image_generation": {"adapter": "xai", "provider": "xai"}},
    }) == "openai_images"


def test_openai_compatible_adapter_uses_generation_endpoint_without_leaking_control_fields(monkeypatch) -> None:
    fake = _FakeRequests({"data": [{"b64_json": _png_b64(), "revised_prompt": "更好的提示词"}]})
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_openai_compatible_image(
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model_name": "gpt-image-1",
            "extra_body": {
                "adapter": "openai",
                "timeout": 30,
                "generation_endpoint": "https://proxy.example.test/v1/images/generations",
                "quality": "high",
            },
        },
        SparkImageRequest(prompt="横版校园黄昏", size="1536x1024"),
        provider="openai_images",
    )

    assert result.provider == "openai_images"
    assert result.revised_prompt == "更好的提示词"
    call = fake.calls[0]
    assert call["url"] == "https://proxy.example.test/v1/images/generations"
    assert call["json"]["model"] == "gpt-image-1"
    assert call["json"]["quality"] == "high"
    assert "generation_endpoint" not in call["json"]
    assert "adapter" not in call["json"]


def test_openai_images_edit_uses_official_image_array_multipart_field(monkeypatch) -> None:
    fake = _FakeRequests({"data": [{"b64_json": _png_b64()}]})
    monkeypatch.setitem(sys.modules, "requests", fake)

    _generate_openai_compatible_image(
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model_name": "gpt-image-2",
            "input_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
            "output_modalities": [MODALITY_IMAGE],
            "extra_body": {},
        },
        SparkImageRequest(
            prompt="保持两个参考对象的身份，生成同一张横版画面",
            references=[
                ImageReference(data=b"reference-a", mime_type="image/png", filename="a.png"),
                ImageReference(data=b"reference-b", mime_type="image/png", filename="b.png"),
            ],
        ),
    )

    call = fake.calls[0]
    assert [field for field, _ in call["files"]] == ["image[]", "image[]"]


def test_openai_responses_image_adapter_uses_ephemeral_data_urls_and_parses_tool_result(monkeypatch) -> None:
    fake = _FakeRequests({
        "id": "resp_test",
        "output": [
            {
                "id": "ig_test",
                "type": "image_generation_call",
                "status": "completed",
                "revised_prompt": "统一赛璐璐风格的雨夜书店",
                "result": _png_b64(),
            }
        ],
    })
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_openai_responses_image(
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test",
            "model_name": "gpt-5.6",
            "input_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
            "output_modalities": [MODALITY_IMAGE],
            "extra_body": {
                "quality": "high",
                "reasoning": {"effort": "low"},
            },
        },
        SparkImageRequest(
            prompt="保持风格种子的线条与配色，生成雨夜书店",
            size="1536x1024",
            references=[
                ImageReference(data=b"reference-style", mime_type="image/png", filename="style.png"),
            ],
        ),
    )

    assert result.provider == "openai_responses_image"
    assert result.revised_prompt == "统一赛璐璐风格的雨夜书店"
    call = fake.calls[0]
    assert call["url"] == "https://api.openai.com/v1/responses"
    assert call["json"]["model"] == "gpt-5.6"
    assert call["json"]["reasoning"] == {"effort": "low"}
    assert call["json"]["tools"] == [{
        "type": "image_generation",
        "action": "edit",
        "quality": "high",
        "size": "1536x1024",
    }]
    content = call["json"]["input"][0]["content"]
    assert content[0] == {
        "type": "input_text",
        "text": "保持风格种子的线条与配色，生成雨夜书店",
    }
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert "files" not in call


def test_openai_chat_image_adapter_preserves_model_name_and_parses_markdown_data_image(monkeypatch) -> None:
    fake = _FakeRequests({
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"![Generated Image](data:image/jpeg;base64,{_png_b64()})",
                }
            }
        ]
    })
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_openai_chat_image(
        {
            "base_url": "https://ai.1dea.top/v1",
            "api_key": "sk-test",
            "model_name": "gemini-3.1-flash-lite-image-fake",
            "extra_body": {
                "chat_endpoint": "https://ai.1dea.top/v1/chat/completions",
                "temperature": 0.1,
            },
        },
        SparkImageRequest(prompt="横版雨夜书店", size="1536x1024"),
    )

    assert result.provider == "openai_chat_image"
    assert result.model_name == "gemini-3.1-flash-lite-image-fake"
    assert result.mime_type == "image/jpeg"
    call = fake.calls[0]
    assert call["url"] == "https://ai.1dea.top/v1/chat/completions"
    assert call["json"]["model"] == "gemini-3.1-flash-lite-image-fake"
    assert call["json"]["temperature"] == 0.1
    assert call["json"]["stream"] is False
    assert "chat_endpoint" not in call["json"]


def test_xai_grok_adapter_is_openai_compatible_but_keeps_provider_identity(monkeypatch) -> None:
    fake = _FakeRequests({"data": [{"b64_json": _png_b64()}]})
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_xai_image(
        {
            "base_url": "https://api.x.ai/v1",
            "api_key": "xai-test",
            "model_name": "grok-2-image",
            "extra_body": {},
        },
        SparkImageRequest(prompt="横版未来城市雨夜", size="1536x1024"),
    )

    assert result.provider == "xai_images"
    call = fake.calls[0]
    assert call["url"] == "https://api.x.ai/v1/images/generations"
    assert call["json"]["model"] == "grok-2-image"
    assert call["json"]["aspect_ratio"] == "3:2"


def test_xai_grok_adapter_sends_reference_images_as_json_data_uris(monkeypatch) -> None:
    fake = _FakeRequests({"data": [{"b64_json": _png_b64()}]})
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_xai_image(
        {
            "base_url": "https://api.x.ai/v1",
            "api_key": "xai-test",
            "model_name": "grok-2-image",
            "extra_body": {"quality": "high"},
            "input_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
            "output_modalities": [MODALITY_IMAGE],
        },
        SparkImageRequest(
            prompt="参考角色例绘，生成横版教室背景",
            size="1536x1024",
            references=[
                ImageReference(
                    data=b"\x89PNG\r\n\x1a\nreference-a",
                    mime_type="image/png",
                    filename="style-a.png",
                ),
                ImageReference(
                    data=b"\x89PNG\r\n\x1a\nreference-b",
                    mime_type="image/png",
                    filename="style-b.png",
                ),
            ],
        ),
    )

    assert result.provider == "xai_images"
    call = fake.calls[0]
    assert call["url"] == "https://api.x.ai/v1/images/edits"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"]["model"] == "grok-2-image"
    assert call["json"]["quality"] == "high"
    assert "files" not in call
    assert "image" not in call["json"]
    assert len(call["json"]["images"]) == 2
    assert call["json"]["images"][0]["type"] == "image_url"
    assert call["json"]["images"][0]["url"].startswith("data:image/png;base64,")


def test_gemini_interactions_adapter_sends_text_and_reference_parts(monkeypatch) -> None:
    fake = _FakeRequests({"output_image": {"data": _png_b64(), "mime_type": "image/png"}})
    monkeypatch.setitem(sys.modules, "requests", fake)

    result = _generate_gemini_interactions_image(
        {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "gemini-test",
            "model_name": "gemini-3.1-flash-lite-image-fake",
            "extra_body": {},
            "input_modalities": [MODALITY_TEXT, MODALITY_IMAGE],
            "output_modalities": [MODALITY_IMAGE],
        },
        SparkImageRequest(
            prompt="保持例图画风，生成横版雨夜书店背景",
            size="1536x1024",
            references=[
                ImageReference(
                    data=b"\x89PNG\r\n\x1a\nreference",
                    mime_type="image/png",
                    filename="style.png",
                )
            ],
        ),
    )

    assert result.provider == "gemini_interactions"
    call = fake.calls[0]
    assert call["url"] == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert call["json"]["model"] == "gemini-3.1-flash-lite-image-fake"
    assert call["json"]["response_format"]["aspect_ratio"] == "3:2"
    assert call["json"]["input"][0] == {"type": "text", "text": "保持例图画风，生成横版雨夜书店背景"}
    assert call["json"]["input"][1]["type"] == "image"
    assert call["headers"]["x-goog-api-key"] == "gemini-test"


def test_reference_image_is_rejected_before_network_without_image_input(monkeypatch) -> None:
    fake = _FakeRequests({"data": [{"b64_json": _png_b64()}]})
    monkeypatch.setitem(sys.modules, "requests", fake)

    with pytest.raises(ImageGenerationError, match="未声明接收图片输入"):
        _generate_openai_compatible_image(
            {
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "model_name": "text-to-image-only",
                "input_modalities": [MODALITY_TEXT],
                "output_modalities": [MODALITY_IMAGE],
                "extra_body": {},
            },
            SparkImageRequest(
                prompt="生成横版背景",
                references=[ImageReference(data=b"reference", mime_type="image/png")],
            ),
        )

    assert fake.calls == []
