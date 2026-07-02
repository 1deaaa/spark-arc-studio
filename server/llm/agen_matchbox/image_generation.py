"""在线生图统一适配层。"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote, urlparse

from . import matchbox
from .models import CAP_IMAGE_EDIT, CAP_IMAGE_REFERENCE_INPUT
from .utils import _build_endpoint


class ImageGenerationError(RuntimeError):
    """在线生图调用失败。"""


@dataclass
class ImageReference:
    """图生图参考图。"""

    data: bytes
    mime_type: str
    filename: str = "reference.png"


@dataclass
class SparkImageRequest:
    """SparkArc 内部统一生图请求。"""

    prompt: str
    size: str = "1536x1024"
    references: list[ImageReference] = field(default_factory=list)


@dataclass
class SparkImageResult:
    """SparkArc 内部统一生图结果。"""

    image: bytes
    mime_type: str
    provider: str
    model_name: str
    model_id: Optional[int] = None
    platform_id: Optional[int] = None
    revised_prompt: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _clean_prompt(prompt: str) -> str:
    text = str(prompt or "").strip()
    if not text:
        raise ImageGenerationError("生图提示词不能为空")
    if len(text) > 8000:
        raise ImageGenerationError("生图提示词过长，请压缩到 8000 字以内")
    return text


def _normalize_size(size: str) -> str:
    text = str(size or "").strip().lower()
    if not text:
        return "1536x1024"
    if not re.fullmatch(r"\d{2,5}x\d{2,5}", text):
        raise ImageGenerationError("图片尺寸格式必须类似 1536x1024")
    return text


def _image_extra(config: dict[str, Any]) -> dict[str, Any]:
    extra = config.get("extra_body")
    if not isinstance(extra, dict):
        return {}
    image_extra = extra.get("image_generation")
    if isinstance(image_extra, dict):
        inherited = {key: value for key, value in extra.items() if key != "image_generation"}
        return {**inherited, **image_extra}
    return extra


def _select_adapter(config: dict[str, Any]) -> str:
    extra = config.get("extra_body")
    image_extra = extra.get("image_generation") if isinstance(extra, dict) else None
    explicit = str(image_extra.get("adapter") if isinstance(image_extra, dict) else "").strip().lower()
    if explicit in {"openai", "openai_images", "openai_compatible"}:
        return "openai_images"
    if explicit in {"xai", "xai_images", "grok", "grok_image", "grok_images", "grok_imagine"}:
        return "xai_images"
    if explicit in {"gemini", "google", "google_gemini", "gemini_interactions", "google_interactions"}:
        return "gemini_interactions"
    if explicit in {"gemini_generate_content", "google_generate_content"}:
        return "gemini_generate_content"

    # 不按域名或模型名推断供应商：大量用户会使用中转站、反代、自托管网关。
    # 协议适配器必须由模型配置中的 extra_body.image_generation.adapter 显式指定。
    # 旧的 provider/top-level adapter 字段不会参与选择，避免把供应商概念和真实协议混在一起。
    # 未配置时使用 OpenAI Images 兼容协议作为低惊讶默认值。
    return "openai_images"


def _request_timeout(config: dict[str, Any]) -> float:
    value = _image_extra(config).get("timeout")
    try:
        return max(float(value), 5.0)
    except (TypeError, ValueError):
        return 180.0


def _compact_error_response(response: Any) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("code")
                if message:
                    return str(message)
            if isinstance(error, str):
                return error
            message = data.get("message")
            if message:
                return str(message)
    except Exception:
        pass
    text = getattr(response, "text", "") or ""
    return text[:500] or f"HTTP {getattr(response, 'status_code', '?')}"


def _download_image_url(url: str, *, timeout: float) -> tuple[bytes, str]:
    try:
        import requests
    except ImportError as exc:
        raise ImageGenerationError("缺少 requests 库，无法下载图片结果") from exc

    response = requests.get(url, timeout=timeout)
    if not response.ok:
        raise ImageGenerationError(f"下载图片结果失败: HTTP {response.status_code}")
    mime_type = str(response.headers.get("content-type") or "image/png").split(";")[0].strip() or "image/png"
    return response.content, mime_type


def _decode_b64_image(data: str, mime_type: str = "image/png") -> tuple[bytes, str]:
    text = str(data or "").strip()
    if not text:
        raise ImageGenerationError("图片结果为空")
    if text.startswith("data:"):
        header, _, payload = text.partition(",")
        mime_match = re.match(r"data:([^;]+);base64", header)
        if mime_match:
            mime_type = mime_match.group(1)
        text = payload
    return base64.b64decode(text), mime_type


def _parse_openai_image_response(data: dict[str, Any], *, timeout: float) -> tuple[bytes, str, str]:
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ImageGenerationError("生图接口没有返回图片数据")

    first = items[0]
    if not isinstance(first, dict):
        raise ImageGenerationError("生图接口返回格式无法识别")

    revised_prompt = str(first.get("revised_prompt") or "")
    b64_json = first.get("b64_json")
    if isinstance(b64_json, str) and b64_json.strip():
        image, mime_type = _decode_b64_image(b64_json, "image/png")
        return image, mime_type, revised_prompt

    url = first.get("url")
    if isinstance(url, str) and url.strip():
        image, mime_type = _download_image_url(url, timeout=timeout)
        return image, mime_type, revised_prompt

    raise ImageGenerationError("生图接口没有返回 b64_json 或 url")


def _allowed_openai_extra(extra: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "adapter",
        "provider",
        "timeout",
        "image_generation",
        "endpoint",
        "generation_endpoint",
        "edit_endpoint",
        "reference_mode",
    }
    return {key: value for key, value in extra.items() if key not in blocked}


def _allowed_xai_extra(extra: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "adapter",
        "provider",
        "timeout",
        "image_generation",
        "endpoint",
        "generation_endpoint",
        "edit_endpoint",
        "mime_type",
    }
    return {key: value for key, value in extra.items() if key not in blocked}


def _reference_to_data_uri(reference: ImageReference) -> str:
    mime_type = reference.mime_type or "image/png"
    payload = base64.b64encode(reference.data).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def _generate_openai_compatible_image(
    config: dict[str, Any],
    request: SparkImageRequest,
    *,
    provider: str = "openai_images",
) -> SparkImageResult:
    try:
        import requests
    except ImportError as exc:
        raise ImageGenerationError("缺少 requests 库，无法调用生图接口") from exc

    timeout = _request_timeout(config)
    extra = _image_extra(config)
    model_name = str(config["model_name"])
    headers = {"Authorization": f"Bearer {config['api_key']}"}

    if request.references:
        capabilities = set(config.get("capabilities") or [])
        if CAP_IMAGE_REFERENCE_INPUT not in capabilities and CAP_IMAGE_EDIT not in capabilities:
            raise ImageGenerationError("该生图模型未标记为支持参考图，请在模型设置中勾选参考图/编辑能力")
        endpoint = str(extra.get("edit_endpoint") or "").strip() or _build_endpoint(config["base_url"], "/images/edits")
        data: dict[str, Any] = {
            "model": model_name,
            "prompt": request.prompt,
            "size": request.size,
        }
        data.update(_allowed_openai_extra(extra))
        files = [
            (
                "image",
                (
                    reference.filename or f"reference-{idx + 1}.png",
                    reference.data,
                    reference.mime_type or "image/png",
                ),
            )
            for idx, reference in enumerate(request.references)
        ]
        response = requests.post(endpoint, headers=headers, data=data, files=files, timeout=timeout)
    else:
        endpoint = str(extra.get("generation_endpoint") or "").strip() or _build_endpoint(config["base_url"], "/images/generations")
        headers["Content-Type"] = "application/json"
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": request.prompt,
            "size": request.size,
            "n": 1,
        }
        payload.update(_allowed_openai_extra(extra))
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)

    if not response.ok:
        raise ImageGenerationError(f"生图接口调用失败: HTTP {response.status_code}: {_compact_error_response(response)}")

    try:
        data = response.json()
    except Exception as exc:
        raise ImageGenerationError("生图接口返回的不是 JSON") from exc

    image, mime_type, revised_prompt = _parse_openai_image_response(data, timeout=timeout)
    return SparkImageResult(
        image=image,
        mime_type=mime_type,
        provider=provider,
        model_name=model_name,
        model_id=config.get("model_id"),
        platform_id=config.get("platform_id"),
        revised_prompt=revised_prompt,
        raw={"response_shape": provider},
    )


def _generate_xai_image(config: dict[str, Any], request: SparkImageRequest) -> SparkImageResult:
    try:
        import requests
    except ImportError as exc:
        raise ImageGenerationError("缺少 requests 库，无法调用 xAI 生图接口") from exc

    timeout = _request_timeout(config)
    extra = _image_extra(config)
    model_name = str(config["model_name"])
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": request.prompt,
        "aspect_ratio": str(extra.get("aspect_ratio") or _size_to_aspect_ratio(request.size)),
    }
    payload.update(_allowed_xai_extra(extra))

    if request.references:
        capabilities = set(config.get("capabilities") or [])
        if CAP_IMAGE_REFERENCE_INPUT not in capabilities and CAP_IMAGE_EDIT not in capabilities:
            raise ImageGenerationError("该生图模型未标记为支持参考图，请在模型设置中勾选参考图/编辑能力")
        if len(request.references) > 3:
            raise ImageGenerationError("xAI Grok 图片编辑最多支持 3 张参考图")
        endpoint = str(extra.get("edit_endpoint") or "").strip() or _build_endpoint(config["base_url"], "/images/edits")
        image_payloads = [
            {
                "type": "image_url",
                "url": _reference_to_data_uri(reference),
            }
            for reference in request.references
        ]
        if len(image_payloads) == 1:
            payload["image"] = image_payloads[0]
        else:
            payload["images"] = image_payloads
    else:
        endpoint = str(extra.get("generation_endpoint") or "").strip() or _build_endpoint(config["base_url"], "/images/generations")

    response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        raise ImageGenerationError(f"xAI 生图接口调用失败: HTTP {response.status_code}: {_compact_error_response(response)}")

    try:
        data = response.json()
    except Exception as exc:
        raise ImageGenerationError("xAI 生图接口返回的不是 JSON") from exc

    image, mime_type, revised_prompt = _parse_openai_image_response(data, timeout=timeout)
    return SparkImageResult(
        image=image,
        mime_type=mime_type,
        provider="xai_images",
        model_name=model_name,
        model_id=config.get("model_id"),
        platform_id=config.get("platform_id"),
        revised_prompt=revised_prompt,
        raw={"response_shape": "xai_images"},
    )


def _gemini_root_and_version(base_url: str) -> tuple[str, str]:
    parsed = urlparse(str(base_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        raise ImageGenerationError("Gemini 平台 base_url 无效")
    path = parsed.path.strip("/")
    version = "v1beta"
    for part in path.split("/"):
        if part in {"v1", "v1beta"}:
            version = part
            break
    root = f"{parsed.scheme}://{parsed.netloc}"
    return root, version


def _gemini_generate_content_endpoint(base_url: str, model_name: str) -> str:
    root, version = _gemini_root_and_version(base_url)
    return f"{root}/{version}/models/{quote(model_name, safe='')}:generateContent"


def _gemini_interactions_endpoint(base_url: str) -> str:
    root, version = _gemini_root_and_version(base_url)
    return f"{root}/{version}/interactions"


def _collect_inline_images(value: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        output_image = value.get("output_image") or value.get("outputImage")
        if isinstance(output_image, dict):
            data = output_image.get("data")
            mime_type = output_image.get("mime_type") or output_image.get("mimeType") or "image/png"
            if isinstance(data, str) and data.strip():
                found.append((data, str(mime_type)))

        inline_data = value.get("inline_data") or value.get("inlineData")
        if isinstance(inline_data, dict):
            data = inline_data.get("data")
            mime_type = inline_data.get("mime_type") or inline_data.get("mimeType") or "image/png"
            if isinstance(data, str) and data.strip():
                found.append((data, str(mime_type)))

        if value.get("type") == "image":
            data = value.get("data")
            mime_type = value.get("mime_type") or value.get("mimeType") or "image/png"
            if isinstance(data, str) and data.strip():
                found.append((data, str(mime_type)))

        for child in value.values():
            found.extend(_collect_inline_images(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_inline_images(item))
    return found


def _size_to_aspect_ratio(size: str) -> str:
    match = re.fullmatch(r"(\d{2,5})x(\d{2,5})", str(size or "").strip().lower())
    if not match:
        return "16:9"
    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        return "16:9"
    ratio = width / height
    candidates = {
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:2": 3 / 2,
        "16:9": 16 / 9,
        "2:3": 2 / 3,
        "3:4": 3 / 4,
        "9:16": 9 / 16,
    }
    return min(candidates, key=lambda key: abs(candidates[key] - ratio))


def _generate_gemini_interactions_image(config: dict[str, Any], request: SparkImageRequest) -> SparkImageResult:
    try:
        import requests
    except ImportError as exc:
        raise ImageGenerationError("缺少 requests 库，无法调用 Gemini 生图接口") from exc

    extra = _image_extra(config)
    timeout = _request_timeout(config)
    model_name = str(config["model_name"])
    input_parts: list[dict[str, Any]] = [{"type": "text", "text": request.prompt}]
    for reference in request.references:
        input_parts.append({
            "type": "image",
            "mime_type": reference.mime_type or "image/png",
            "data": base64.b64encode(reference.data).decode("ascii"),
        })

    payload: dict[str, Any] = {
        "model": model_name,
        "input": input_parts,
        "response_format": {
            "type": "image",
            "mime_type": str(extra.get("mime_type") or "image/png"),
            "aspect_ratio": str(extra.get("aspect_ratio") or _size_to_aspect_ratio(request.size)),
        },
    }

    response_format = extra.get("response_format")
    if isinstance(response_format, dict):
        payload["response_format"] = {
            **payload["response_format"],
            **response_format,
        }
    for key in ("generation_config", "tools", "previous_interaction_id"):
        if key in extra:
            payload[key] = extra[key]
    extra_payload = extra.get("payload")
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)

    response = requests.post(
        _gemini_interactions_endpoint(config["base_url"]),
        headers={
            "x-goog-api-key": str(config["api_key"]),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        raise ImageGenerationError(f"Gemini 生图接口调用失败: HTTP {response.status_code}: {_compact_error_response(response)}")

    try:
        data = response.json()
    except Exception as exc:
        raise ImageGenerationError("Gemini 生图接口返回的不是 JSON") from exc

    images = _collect_inline_images(data)
    if not images:
        raise ImageGenerationError("Gemini 生图接口没有返回图片")

    image, mime_type = _decode_b64_image(images[0][0], images[0][1])
    return SparkImageResult(
        image=image,
        mime_type=mime_type,
        provider="gemini_interactions",
        model_name=model_name,
        model_id=config.get("model_id"),
        platform_id=config.get("platform_id"),
        raw={"response_shape": "gemini_interactions"},
    )


def _generate_gemini_generate_content_image(config: dict[str, Any], request: SparkImageRequest) -> SparkImageResult:
    try:
        import requests
    except ImportError as exc:
        raise ImageGenerationError("缺少 requests 库，无法调用 Gemini 生图接口") from exc

    extra = _image_extra(config)
    timeout = _request_timeout(config)
    model_name = str(config["model_name"])
    parts: list[dict[str, Any]] = [{"text": request.prompt}]
    for reference in request.references:
        parts.append({
            "inline_data": {
                "mime_type": reference.mime_type or "image/png",
                "data": base64.b64encode(reference.data).decode("ascii"),
            }
        })

    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }
    extra_payload = extra.get("payload")
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)
    generation_config = extra.get("generationConfig")
    if isinstance(generation_config, dict):
        payload["generationConfig"] = {
            **payload.get("generationConfig", {}),
            **generation_config,
        }

    response = requests.post(
        _gemini_generate_content_endpoint(config["base_url"], model_name),
        headers={
            "x-goog-api-key": str(config["api_key"]),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    if not response.ok:
        raise ImageGenerationError(f"Gemini 生图接口调用失败: HTTP {response.status_code}: {_compact_error_response(response)}")

    try:
        data = response.json()
    except Exception as exc:
        raise ImageGenerationError("Gemini 生图接口返回的不是 JSON") from exc

    images = _collect_inline_images(data)
    if not images:
        raise ImageGenerationError("Gemini 生图接口没有返回图片")

    image, mime_type = _decode_b64_image(images[0][0], images[0][1])
    return SparkImageResult(
        image=image,
        mime_type=mime_type,
        provider="gemini_generate_content",
        model_name=model_name,
        model_id=config.get("model_id"),
        platform_id=config.get("platform_id"),
        raw={"response_shape": "gemini_generate_content"},
    )


def _generate_gemini_image(config: dict[str, Any], request: SparkImageRequest, *, adapter: str) -> SparkImageResult:
    if adapter == "gemini_generate_content":
        return _generate_gemini_generate_content_image(config, request)
    return _generate_gemini_interactions_image(config, request)


def generate_image_for_user(
    *,
    user_id: str,
    prompt: str,
    size: str = "1536x1024",
    platform_id: Optional[int] = None,
    model_id: Optional[int] = None,
    references: Optional[list[ImageReference]] = None,
) -> SparkImageResult:
    """使用 Matchbox 中当前用户可用的生图模型生成图片。"""
    manager = matchbox()
    config = manager.resolve_user_image_generation_model(
        user_id=user_id,
        platform_id=platform_id,
        model_id=model_id,
    )
    request = SparkImageRequest(
        prompt=_clean_prompt(prompt),
        size=_normalize_size(size),
        references=list(references or []),
    )
    adapter = _select_adapter(config)
    if adapter in {"gemini_interactions", "gemini_generate_content"}:
        return _generate_gemini_image(config, request, adapter=adapter)
    if adapter == "xai_images":
        return _generate_xai_image(config, request)
    return _generate_openai_compatible_image(config, request, provider="openai_images")
