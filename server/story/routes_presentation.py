import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from core.auth import get_current_user
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
    save_manifest_to_root,
    upload_background_asset,
    upload_character_sprite_asset,
    upload_presentation_asset,
)


presentation_router = APIRouter()


class GenerateBackgroundRequest(BaseModel):
    prompt: str
    title: str = ""
    size: str = "1536x1024"
    platformId: int | None = None
    modelId: int | None = None
    referenceAssetIds: list[str] | None = None


class GenerateSpriteRequest(BaseModel):
    prompt: str
    title: str = ""
    characterId: str = ""
    expression: str = "default"
    size: str = "1024x1536"
    platformId: int | None = None
    modelId: int | None = None
    referenceAssetIds: list[str] | None = None


class GenerateReferenceRequest(BaseModel):
    prompt: str
    title: str = ""
    assetType: str = "style_reference"
    size: str = "1536x1024"
    platformId: int | None = None
    modelId: int | None = None
    referenceAssetIds: list[str] | None = None


REFERENCE_ASSET_TYPES = {"style_reference", "scene_reference"}


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
    reference_asset_ids: list[str] | None,
) -> dict:
    asset["generation"] = {
        "provider": provider,
        "platformId": platform_id,
        "modelId": model_id,
        "modelName": model_name,
        "size": size,
        "referenceAssetIds": reference_asset_ids or [],
    }
    manifest = load_project_manifest(user_id, project_name)
    manifest.setdefault("assets", {})[asset["id"]] = asset
    save_manifest_to_root(get_project_path(user_id, project_name), manifest)
    return manifest


def _load_reference_assets(user_id: str, project_name: str, asset_ids: list[str] | None) -> list[ImageReference]:
    if not asset_ids:
        return []
    manifest = load_project_manifest(user_id, project_name)
    assets = manifest.get("assets") if isinstance(manifest, dict) else {}
    if not isinstance(assets, dict):
        assets = {}

    references: list[ImageReference] = []
    for raw_id in asset_ids[:4]:
        asset_id = str(raw_id or "").strip()
        if not asset_id:
            continue
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
    """读取当前项目的 Web 演出资源 manifest。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    manifest = load_project_manifest(user_id, normalized_project)
    return {
        "manifest": manifest,
        "assetBaseUrl": f"/api/presentation/{quote(normalized_project, safe='')}/assets",
    }


@presentation_router.post("/api/presentation/{project_name}/backgrounds/upload")
async def upload_presentation_background(
    project_name: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    user: dict = Depends(get_current_user),
):
    """上传背景图并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

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
    """调用在线生图模型生成背景图，并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})

    try:
        references = _load_reference_assets(user_id, normalized_project, data.referenceAssetIds)
        generated = await run_in_threadpool(
            generate_image_for_user,
            user_id=user_id,
            prompt=data.prompt,
            size=data.size,
            platform_id=data.platformId,
            model_id=data.modelId,
            references=references,
        )
        asset = upload_background_asset(
            user_id=user_id,
            project_name=normalized_project,
            data=generated.image,
            filename=f"{data.title or 'ai-background'}.png",
            content_type=generated.mime_type,
            title=data.title or "AI 背景图",
            source="ai",
            prompt=generated.revised_prompt or data.prompt,
        )
        manifest = _persist_generated_asset_metadata(
            user_id=user_id,
            project_name=normalized_project,
            asset=asset,
            provider=generated.provider,
            platform_id=generated.platform_id,
            model_id=generated.model_id,
            model_name=generated.model_name,
            size=data.size,
            reference_asset_ids=data.referenceAssetIds,
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
    """上传风格或场景参考图，并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

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
    """调用在线生图模型生成风格或场景参考图，并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})

    try:
        reference_type = _normalize_reference_asset_type(data.assetType)
        references = _load_reference_assets(user_id, normalized_project, data.referenceAssetIds)
        generated = await run_in_threadpool(
            generate_image_for_user,
            user_id=user_id,
            prompt=data.prompt,
            size=data.size,
            platform_id=data.platformId,
            model_id=data.modelId,
            references=references,
        )
        default_title = "AI 风格参考图" if reference_type == "style_reference" else "AI 场景参考图"
        asset = upload_presentation_asset(
            user_id=user_id,
            project_name=normalized_project,
            asset_type=reference_type,
            data=generated.image,
            filename=f"{data.title or 'ai-reference'}.png",
            content_type=generated.mime_type,
            title=data.title or default_title,
            source="ai",
            prompt=generated.revised_prompt or data.prompt,
        )
        manifest = _persist_generated_asset_metadata(
            user_id=user_id,
            project_name=normalized_project,
            asset=asset,
            provider=generated.provider,
            platform_id=generated.platform_id,
            model_id=generated.model_id,
            model_name=generated.model_name,
            size=data.size,
            reference_asset_ids=data.referenceAssetIds,
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
    """上传角色立绘并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

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
    """调用在线生图模型生成角色立绘，并注册为 Web 演出资产。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"success": False, "error": "缺少项目名称"})

    try:
        references = _load_reference_assets(user_id, normalized_project, data.referenceAssetIds)
        generated = await run_in_threadpool(
            generate_image_for_user,
            user_id=user_id,
            prompt=data.prompt,
            size=data.size,
            platform_id=data.platformId,
            model_id=data.modelId,
            references=references,
        )
        asset = upload_character_sprite_asset(
            user_id=user_id,
            project_name=normalized_project,
            data=generated.image,
            filename=f"{data.title or 'ai-sprite'}.png",
            content_type=generated.mime_type,
            title=data.title or "AI 角色立绘",
            source="ai",
            prompt=generated.revised_prompt or data.prompt,
            character_id=data.characterId,
            expression=data.expression,
        )
        manifest = _persist_generated_asset_metadata(
            user_id=user_id,
            project_name=normalized_project,
            asset=asset,
            provider=generated.provider,
            platform_id=generated.platform_id,
            model_id=generated.model_id,
            model_name=generated.model_name,
            size=data.size,
            reference_asset_ids=data.referenceAssetIds,
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


@presentation_router.get("/api/presentation/{project_name}/assets/{asset_path:path}")
async def get_presentation_asset(project_name: str, asset_path: str, user: dict = Depends(get_current_user)):
    """读取当前项目的演出资产，仅用于编辑器预览。"""
    user_id = str(user["user_id"])
    normalized_project = normalize_project_name(project_name)
    if not normalized_project:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    try:
        path = get_project_asset_path(user_id, normalized_project, asset_path)
    except PresentationAssetError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    if not path or not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "资源不存在"})
    return FileResponse(path)
