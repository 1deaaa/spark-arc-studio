from __future__ import annotations

import base64
import sys
from typing import Any

from llm.agen_matchbox.image_generation import (
    ImageReference,
    SparkImageRequest,
    _generate_gemini_interactions_image,
    _generate_openai_chat_image,
    _generate_openai_compatible_image,
    _generate_xai_image,
    _select_adapter,
)
from llm.agen_matchbox.models import CAP_IMAGE_EDIT, CAP_IMAGE_GENERATION, CAP_IMAGE_REFERENCE_INPUT


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
            "capabilities": [CAP_IMAGE_REFERENCE_INPUT, CAP_IMAGE_EDIT],
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
            "capabilities": [CAP_IMAGE_GENERATION, CAP_IMAGE_REFERENCE_INPUT, CAP_IMAGE_EDIT],
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
