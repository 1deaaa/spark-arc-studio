import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from core.auth import get_current_user
from core.project_settings import (
    get_workspace_mode,
    get_visual_illustration_settings,
    get_visual_style_settings,
    is_visual_illustration_enabled,
    set_visual_illustration_settings,
    set_visual_style_settings,
)
from core.request_context import normalize_project_name
from core.utils import get_project_path
from llm.agen_matchbox import matchbox
from llm.agen_matchbox.image_generation import (
    ImageGenerationError,
    ImageReference,
    generate_image_for_user,
)
from story.presentation_manifest import (
    PresentationAssetError,
    get_project_asset_path,
    load_project_manifest,
    update_presentation_asset_metadata,
    upload_background_asset,
    upload_character_sprite_asset,
    upload_presentation_asset,
    upload_scene_illustration_asset,
)
from story.presentation_generation import (
    REFERENCE_ROLES,
    build_visual_generation_prompt,
    infer_reference_role,
    normalize_reference_descriptors,
)
from story.project_files import load_character_id_name_map


presentation_router = APIRouter()


class VisualReferenceRequest(BaseModel):
    assetId: str
    role: str = "continuity"


class VisualGenerationContextRequest(BaseModel):
    sceneName: str = ""
    sceneIntro: str = ""
    sceneConception: str = ""
    nodeText: str = ""
    nearbyDialogue: list[str] | None = None
    characterIds: list[str] | None = None


class GenerateImageRequest(BaseModel):
    prompt: str
    title: str = ""
    size: str = "1536x1024"
    platformId: int | None = None
    modelId: int | None = None
    referenceAssetIds: list[str] | None = None
    referenceAssets: list[VisualReferenceRequest] | None = None
    context: VisualGenerationContextRequest | None = None


class GenerateBackgroundRequest(GenerateImageRequest):
    library: bool = False


class GenerateSpriteRequest(GenerateImageRequest):
    characterId: str = ""
    expression: str = "default"
    size: str = "1024x1536"


class GenerateReferenceRequest(GenerateImageRequest):
    assetType: str = "style_reference"


class GenerateIllustrationRequest(GenerateImageRequest):
    sceneName: str = ""
    nodeId: str = ""


class UpdatePresentationSettingsRequest(BaseModel):
    visualIllustrationEnabled: bool | None = None
    styleSeedPrompt: str | None = None
    styleReferenceAssetIds: list[str] | None = None


REFERENCE_ASSET_TYPES = {"style_reference", "scene_reference"}


def _presentation_project_error(user_id: str, project_name: str) -> JSONResponse | None:
    """统一校验 Web 视觉演出项目边界；管理员与普通用户遵循相同规则。"""
    project_root = get_project_path(user_id, project_name)
    if not os.path.isdir(project_root):
        return JSONResponse(status_code=404, content={"success": False, "error": "项目不存在"})
    if get_workspace_mode(user_id, project_name) != "script":
        return JSONResponse(
            status_code=409,
            content={"success": False, "error": "Web 视觉演出仅适用于剧本项目"},
        )
    return None


def _normalize_reference_asset_type(asset_type: str) -> str:
    normalized = str(asset_type or "style_reference").strip() or "style_reference"
    if normalized not in REFERENCE_ASSET_TYPES:
        raise PresentationAssetError(f"不支持的参考图类型: {asset_type}")
    return normalized


def _asset_url(project_name: str, rel_path: str) -> str:
    encoded_project = quote(project_name, safe="")
    safe_path = "/".join(quote(part, safe="") for part in str(rel_path or "").replace("\\", "/").split("/") if part)
    return f"/api/presentation/{encoded_project}/assets/{safe_path}"


def _asset_with_url(project_name: str, asset: dict) -> dict:
    path = asset.get("path")
    return {
        **asset,
        "url": _asset_url(project_name, path) if path else "",
    }


def _presentation_settings_payload(user_id: str, project_name: str) -> dict:
    visual = get_visual_illustration_settings(user_id, project_name)
    missing_characters = _missing_character_sprites(user_id, project_name)
    return {
        "visualIllustration": {
            **visual,
            "effectiveEnabled": is_visual_illustration_enabled(user_id, project_name),
        },
        "visualStyle": get_visual_style_settings(user_id, project_name),
        "readiness": {
            "missingCharacterSprites": missing_characters,
            "characterSpritesReady": not missing_characters,
        },
    }


def _missing_character_sprites(user_id: str, project_name: str) -> list[dict[str, str]]:
    characters = load_character_id_name_map(
        user_id,
        project_name,
        include_narrator=False,
        include_system=False,
    )
    if not characters:
        return []
    assets = load_project_manifest(user_id, project_name).get("assets", {})
    covered: set[str] = set()
    if isinstance(assets, dict):
        for asset in assets.values():
            if not isinstance(asset, dict) or asset.get("type") != "character_sprite":
                continue
            character_key = str(asset.get("characterId") or "").strip()
            if character_key:
                covered.add(character_key)
    return [
        {"id": character_id, "name": character_name}
        for character_id, character_name in characters.items()
        if character_id not in covered and character_name not in covered
    ]


def _persist_generated_asset_metadata(
    *,
    user_id: str,
    project_name: str,
    asset: dict,
    provider: str,
    platform_id: int | None,
    model_id: int | None,
    model_name: str,
    size: str,
    reference_descriptors: list[dict[str, str]],
    context_snapshot: dict | None = None,
    requested_prompt: str = "",
) -> dict:
    generation = {
        "provider": provider,
        "platformId": platform_id,
        "modelId": model_id,
        "modelName": model_name,
        "size": size,
        "referenceAssetIds": [item["assetId"] for item in reference_descriptors],
        "references": reference_descriptors,
        "requestedPrompt": requested_prompt,
        "context": context_snapshot or {},
    }
    stored_asset, manifest = update_presentation_asset_metadata(
        user_id,
        project_name,
        str(asset.get("id") or ""),
        {"generation": generation},
    )
    asset.clear()
    asset.update(stored_asset)
    return manifest


def _resolve_reference_descriptors(
    user_id: str,
    project_name: str,
    *,
    asset_ids: list[str] | None,
    references: list[VisualReferenceRequest] | None,
) -> list[dict[str, str]]:
    manifest = load_project_manifest(user_id, project_name)
    assets = manifest.get("assets") if isinstance(manifest, dict) else {}
    if not isinstance(assets, dict):
        assets = {}

    requested: list[dict[str, str]] = []
    style_settings = get_visual_style_settings(user_id, project_name)
    style_asset_ids = style_settings.get("reference_asset_ids") or []
    for style_asset_id in style_asset_ids[:5]:
        requested.append({"assetId": str(style_asset_id), "role": "style"})
    for item in references or []:
        requested.append({"assetId": item.assetId, "role": item.role})
    for asset_id in asset_ids or []:
        requested.append({"assetId": str(asset_id or ""), "role": ""})

    character_names = load_character_id_name_map(
        user_id,
        project_name,
        include_narrator=False,
        include_system=False,
    )
    enriched: list[dict[str, str]] = []
    for raw in requested:
        asset_id = str(raw.get("assetId") or "").strip()
        if not asset_id:
            continue
        asset = assets.get(asset_id)
        if not isinstance(asset, dict):
            raise PresentationAssetError(f"参考图不存在: {asset_id}")
        role = str(raw.get("role") or "").strip().lower()
        if role not in REFERENCE_ROLES:
            role = infer_reference_role(asset)
        enriched.append({
            "assetId": asset_id,
            "role": role,
            "title": str(asset.get("title") or "").strip(),
            "characterId": str(asset.get("characterId") or "").strip(),
            "characterName": character_names.get(str(asset.get("characterId") or "").strip(), ""),
        })
    return normalize_reference_descriptors(enriched)


def _load_reference_assets(
    user_id: str,
    project_name: str,
    descriptors: list[dict[str, str]],
) -> list[ImageReference]:
    if not descriptors:
        return []
    manifest = load_project_manifest(user_id, project_name)
    assets = manifest.get("assets") if isinstance(manifest, dict) else {}
    if not isinstance(assets, dict):
        assets = {}

    references: list[ImageReference] = []
    for descriptor in descriptors[:10]:
        asset_id = descriptor["assetId"]
        asset = assets.get(asset_id)
        if not isinstance(asset, dict):
            raise PresentationAssetError(f"参考图不存在: {asset_id}")
        rel_path = str(asset.get("path") or "").strip()
        if not rel_path:
            raise PresentationAssetError(f"参考图缺少资源路径: {asset_id}")
        abs_path = get_project_asset_path(user_id, project_name, rel_path)
        if not os.path.isfile(abs_path):
            raise PresentationAssetError(f"参考图文件不存在: {asset_id}")
        with open(abs_path, "rb") as f:
            data = f.read()
        references.append(ImageReference(
            data=data,
            mime_type=str(asset.get("mimeType") or "image/png"),
            filename=os.path.basename(rel_path) or f"{asset_id}.png",
        ))
    return references


async def _generate_visual_asset(
    *,
    user_id: str,
    project_name: str,
    asset_type: str,
    data: GenerateImageRequest,
    character_id: str = "",
    expression: str = "default",
    scene_name: str = "",
    node_id: str = "",
) -> tuple[dict, dict]:
    """统一执行上下文构建、图生图调用、资产写入和生成溯源。"""
    reference_descriptors = _resolve_reference_descriptors(
        user_id,
        project_name,
        asset_ids=data.referenceAssetIds,
        references=data.referenceAssets,
    )
    context = data.context.model_dump() if data.context else {}
    if character_id:
        character_ids = [str(value) for value in (context.get("characterIds") or [])]
        if character_id not in character_ids:
            character_ids.append(character_id)
        context["characterIds"] = character_ids
    if scene_name and not context.get("sceneName"):
        context["sceneName"] = scene_name

    final_prompt, context_snapshot = build_visual_generation_prompt(
        user_id=user_id,
        project_name=project_name,
        asset_type=asset_type,
        creative_prompt=data.prompt,
        context=context,
        references=reference_descriptors,
    )
    image_references = _load_reference_assets(user_id, project_name, reference_descriptors)
    generated = await run_in_threadpool(
        generate_image_for_user,
        user_id=user_id,
        prompt=final_prompt,
        size=data.size,
        platform_id=data.platformId,
        model_id=data.modelId,
        references=image_references,
    )

    common = {
        "user_id": user_id,
        "project_name": project_name,
        "data": generated.image,
        "filename": f"{data.title or f'ai-{asset_type}'}.png",
        "content_type": generated.mime_type,
        "source": "ai",
        "prompt": generated.revised_prompt or final_prompt,
    }
    if asset_type == "background":
        asset = upload_background_asset(
            **common,
            title=data.title or "AI 背景图",
            library=bool(getattr(data, "library", False)),
        )
    elif asset_type == "character_sprite":
        asset = upload_character_sprite_asset(
            **common,
            title=data.title or "AI 角色立绘",
            character_id=character_id,
            expression=expression,
        )
    elif asset_type == "scene_illustration":
        asset = upload_scene_illustration_asset(
            **common,
            title=data.title or "AI 场景插图",
            scene_name=scene_name,
            node_id=node_id,
        )
    else:
        default_title = "AI 风格参考图" if asset_type == "style_reference" else "AI 场景参考图"
        asset = upload_presentation_asset(
            **common,
            title=data.title or default_title,
            asset_type=asset_type,
        )

    manifest = _persist_generated_asset_metadata(
        user_id=user_id,
        project_name=project_name,
        asset=asset,
        provider=generated.provider,
        platform_id=generated.platform_id,
        model_id=generated.model_id,
        model_name=generated.model_name,
        size=data.size,
        reference_descriptors=reference_descriptors,
        context_snapshot=context_snapshot,
        requested_prompt=final_prompt,
    )
    return asset, manifest


@presentation_router.get("/api/presentation/image-models")
async def list_presentation_image_models(user: dict = Depends(get_current_user)):
    """列出当前用户可用的生图模型，供创作面板做轻量提示。"""
    user_id = str(user["user_id"])
    try:
        models = await run_in_threadpool(matchbox().list_user_image_generation_models, user_id)
        return {"models": models}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"models": [], "error": f"读取生图模型失败: {exc}"})


@presentation_router.get("/api/presentation/{project_name}")
async def get_presentation_manifest(project_name: str, user: dict = Depends(get_current_user)):
    """读取当前剧本项目的 Web 专用演出资源 manifest。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    manifest = load_project_manifest(user_id, normalized_project)
    return {
        "manifest": manifest,
        "assetBaseUrl": f"/api/presentation/{quote(normalized_project, safe='')}/assets",
        "settings": _presentation_settings_payload(user_id, normalized_project),
    }


@presentation_router.put("/api/presentation/{project_name}/settings")
async def update_presentation_settings(
    project_name: str,
    data: UpdatePresentationSettingsRequest,
    user: dict = Depends(get_current_user),
):
    """更新项目级视觉开关与风格种子，所有项目编辑者使用同一接口。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    fields = data.model_fields_set
    try:
        if "visualIllustrationEnabled" in fields:
            visual = get_visual_illustration_settings(user_id, normalized_project)
            if data.visualIllustrationEnabled and visual.get("require_character_sprite", True):
                missing = _missing_character_sprites(user_id, normalized_project)
                if missing:
                    names = "、".join(item["name"] or item["id"] for item in missing[:8])
                    raise PresentationAssetError(f"请先为以下角色准备基础立绘：{names}")
            visual["enabled"] = bool(data.visualIllustrationEnabled)
            set_visual_illustration_settings(user_id, normalized_project, visual)

        if {"styleSeedPrompt", "styleReferenceAssetIds"} & fields:
            style = get_visual_style_settings(user_id, normalized_project)
            if "styleSeedPrompt" in fields:
                style["seed_prompt"] = data.styleSeedPrompt or ""
            if "styleReferenceAssetIds" in fields:
                requested_ids: list[str] = []
                for raw_id in data.styleReferenceAssetIds or []:
                    asset_id = str(raw_id or "").strip()
                    if asset_id and asset_id not in requested_ids:
                        requested_ids.append(asset_id)
                    if len(requested_ids) >= 5:
                        break
                assets = load_project_manifest(user_id, normalized_project).get("assets", {})
                for asset_id in requested_ids:
                    asset = assets.get(asset_id) if isinstance(assets, dict) else None
                    if not isinstance(asset, dict) or asset.get("type") != "style_reference":
                        raise PresentationAssetError(f"选中的风格种子图不存在或类型不正确: {asset_id}")
                style["reference_asset_ids"] = requested_ids
            set_visual_style_settings(user_id, normalized_project, style)

        return {
            "success": True,
            "settings": _presentation_settings_payload(user_id, normalized_project),
        }
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"保存视觉设置失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/backgrounds/upload")
async def upload_presentation_background(
    project_name: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    library: bool = Form(False),
    user: dict = Depends(get_current_user),
):
    """上传背景图并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        data = await file.read()
        asset = upload_background_asset(
            user_id=user_id,
            project_name=normalized_project,
            data=data,
            filename=file.filename or "",
            content_type=file.content_type,
            title=title,
            source="upload",
            library=library,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": load_project_manifest(user_id, normalized_project),
        }
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"上传背景图失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/backgrounds/generate")
async def generate_presentation_background(
    project_name: str,
    data: GenerateBackgroundRequest,
    user: dict = Depends(get_current_user),
):
    """调用在线生图模型生成背景图，并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        asset, manifest = await _generate_visual_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type="background",
            data=data,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": manifest,
        }
    except (PresentationAssetError, ImageGenerationError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"生成背景图失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/references/upload")
async def upload_presentation_reference(
    project_name: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    assetType: str = Form("style_reference"),
    user: dict = Depends(get_current_user),
):
    """上传风格或场景参考图，并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        reference_type = _normalize_reference_asset_type(assetType)
        data = await file.read()
        asset = upload_presentation_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type=reference_type,
            data=data,
            filename=file.filename or "",
            content_type=file.content_type,
            title=title,
            source="upload",
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": load_project_manifest(user_id, normalized_project),
        }
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"上传参考图失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/references/generate")
async def generate_presentation_reference(
    project_name: str,
    data: GenerateReferenceRequest,
    user: dict = Depends(get_current_user),
):
    """调用在线生图模型生成风格或场景参考图，并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        reference_type = _normalize_reference_asset_type(data.assetType)
        asset, manifest = await _generate_visual_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type=reference_type,
            data=data,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": manifest,
        }
    except (PresentationAssetError, ImageGenerationError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"生成参考图失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/sprites/upload")
async def upload_presentation_sprite(
    project_name: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    characterId: str = Form(""),
    expression: str = Form("default"),
    user: dict = Depends(get_current_user),
):
    """上传角色立绘并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        data = await file.read()
        asset = upload_character_sprite_asset(
            user_id=user_id,
            project_name=normalized_project,
            data=data,
            filename=file.filename or "",
            content_type=file.content_type,
            title=title,
            source="upload",
            character_id=characterId,
            expression=expression,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": load_project_manifest(user_id, normalized_project),
        }
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"上传角色立绘失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/sprites/generate")
async def generate_presentation_sprite(
    project_name: str,
    data: GenerateSpriteRequest,
    user: dict = Depends(get_current_user),
):
    """调用在线生图模型生成角色立绘，并注册为 Web 播放器专用演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        asset, manifest = await _generate_visual_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type="character_sprite",
            data=data,
            character_id=data.characterId,
            expression=data.expression,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": manifest,
        }
    except (PresentationAssetError, ImageGenerationError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"生成角色立绘失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/illustrations/upload")
async def upload_presentation_illustration(
    project_name: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    sceneName: str = Form(""),
    nodeId: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """上传完整场景插图并注册到当前项目。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error
    if not is_visual_illustration_enabled(user_id, normalized_project):
        return JSONResponse(status_code=409, content={"success": False, "error": "项目尚未启用实验性视觉插图"})

    try:
        payload = await file.read()
        asset = upload_scene_illustration_asset(
            user_id=user_id,
            project_name=normalized_project,
            data=payload,
            filename=file.filename or "",
            content_type=file.content_type,
            title=title,
            source="upload",
            scene_name=sceneName,
            node_id=nodeId,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": load_project_manifest(user_id, normalized_project),
        }
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"上传场景插图失败: {exc}"})


@presentation_router.post("/api/presentation/{project_name}/illustrations/generate")
async def generate_presentation_illustration(
    project_name: str,
    data: GenerateIllustrationRequest,
    user: dict = Depends(get_current_user),
):
    """根据节点描述与项目上下文生成完整场景插图。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error
    if not is_visual_illustration_enabled(user_id, normalized_project):
        return JSONResponse(status_code=409, content={"success": False, "error": "项目尚未启用实验性视觉插图"})

    try:
        asset, manifest = await _generate_visual_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type="scene_illustration",
            data=data,
            scene_name=data.sceneName,
            node_id=data.nodeId,
        )
        return {
            "success": True,
            "asset": _asset_with_url(normalized_project, asset),
            "manifest": manifest,
        }
    except (PresentationAssetError, ImageGenerationError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"success": False, "error": f"生成场景插图失败: {exc}"})


@presentation_router.get("/api/presentation/{project_name}/assets/{asset_path:path}")
async def get_presentation_asset(project_name: str, asset_path: str, user: dict = Depends(get_current_user)):
    """读取当前项目的演出资产，仅用于编辑器预览。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})
    if error := _presentation_project_error(user_id, normalized_project):
        return error

    try:
        path = get_project_asset_path(user_id, normalized_project, asset_path)
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    if not path or not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "资源不存在"})
    return FileResponse(path)
