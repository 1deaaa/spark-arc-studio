"""Web 播放器专用演出资源 manifest 与资产文件管理。

``presentation`` 节点及其资产不属于 Unity SDK 协议。Unity 导出统一依据
manifest 的 ``ignore.unity.nodeKeys`` 忽略整个节点字段。
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from core.utils import get_project_path


MANIFEST_FILENAME = "presentation_manifest.json"
ASSET_ROOT = "assets/presentation"
BACKGROUND_DIR = f"{ASSET_ROOT}/backgrounds"
SPRITE_DIR = f"{ASSET_ROOT}/sprites"
ILLUSTRATION_DIR = f"{ASSET_ROOT}/illustrations"

ASSET_KIND_CONFIG = {
    "background": {
        "prefix": "bg",
        "dir": BACKGROUND_DIR,
    },
    "character_sprite": {
        "prefix": "sprite",
        "dir": SPRITE_DIR,
    },
    "scene_illustration": {
        "prefix": "ill",
        "dir": ILLUSTRATION_DIR,
    },
    "style_reference": {
        "prefix": "style",
        "dir": f"{ASSET_ROOT}/references",
    },
    "scene_reference": {
        "prefix": "scene_ref",
        "dir": f"{ASSET_ROOT}/references",
    },
}

SUPPORTED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

_MANIFEST_LOCK = threading.RLock()


class PresentationAssetError(ValueError):
    """演出资源写入或读取失败。"""


def empty_manifest() -> dict[str, Any]:
    """返回 Web 专用 manifest 默认结构，并声明 Unity 的统一忽略边界。"""
    return {
        "schema": "sparkarc.presentation.v2",
        "version": 2,
        "targets": ["web"],
        "ignore": {
            "unity": {
                "actKeys": [],
                "nodeKeys": ["presentation"],
                "assetTargets": ["web"],
            }
        },
        "assets": {},
        "runtime": {
            "web": {
                "cueBindings": {
                    "bg": {
                        "type": "background",
                        "fallback": "ambient",
                    },
                    "sprite": {
                        "type": "character_sprite",
                        "fallback": "hidden",
                    },
                    "illustration": {
                        "type": "scene_illustration",
                        "fallback": "background_and_sprite",
                    }
                }
            }
        },
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root(user_id: str, project_name: str) -> str:
    return get_project_path(str(user_id), project_name)


def _manifest_path(root: str) -> str:
    return os.path.join(root, MANIFEST_FILENAME)


def _snapshot_sidecar_dir(snapshot_path: str) -> str:
    base = os.path.splitext(os.path.basename(snapshot_path))[0]
    return os.path.join(os.path.dirname(snapshot_path), f"{base}_presentation")


def snapshot_sidecar_dir(snapshot_path: str) -> str:
    """返回快照对应的演出资源 sidecar 目录。"""
    return _snapshot_sidecar_dir(snapshot_path)


def _safe_join(root: str, rel_path: str) -> str:
    root_abs = os.path.abspath(root)
    normalized = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not normalized or normalized.startswith("../") or "/../" in f"/{normalized}/":
        raise PresentationAssetError("资源路径非法")
    path = os.path.abspath(os.path.join(root_abs, normalized))
    if os.path.commonpath([root_abs, path]) != root_abs:
        raise PresentationAssetError("资源路径越界")
    return path


def _safe_presentation_asset_path(root: str, rel_path: str) -> str:
    normalized = str(rel_path or "").replace("\\", "/").lstrip("/")
    if not normalized.startswith(f"{ASSET_ROOT}/"):
        raise PresentationAssetError("只能访问演出资源目录")
    return _safe_join(root, normalized)


def _detect_image_type(data: bytes, content_type: Optional[str]) -> tuple[str, str]:
    declared = str(content_type or "").split(";")[0].strip().lower()
    if declared in SUPPORTED_IMAGE_TYPES:
        return declared, SUPPORTED_IMAGE_TYPES[declared]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise PresentationAssetError("仅支持 PNG、JPEG 或 WebP 图片")


def load_manifest_from_root(root: str) -> dict[str, Any]:
    """从项目或快照根目录读取 manifest。"""
    with _MANIFEST_LOCK:
        path = _manifest_path(root)
        if not os.path.isfile(path):
            return empty_manifest()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception:
            return empty_manifest()
        if not isinstance(data, dict):
            return empty_manifest()
        manifest = empty_manifest()
        manifest.update(data)
        manifest["schema"] = "sparkarc.presentation.v2"
        manifest["version"] = 2
        if not isinstance(manifest.get("assets"), dict):
            manifest["assets"] = {}
        if not isinstance(manifest.get("targets"), list):
            manifest["targets"] = ["web"]
        if not isinstance(manifest.get("ignore"), dict):
            manifest["ignore"] = empty_manifest()["ignore"]
        if not isinstance(manifest.get("runtime"), dict):
            manifest["runtime"] = empty_manifest()["runtime"]
        else:
            web_runtime = manifest["runtime"].setdefault("web", {})
            if isinstance(web_runtime, dict):
                web_runtime.pop("actBindings", None)
            bindings = web_runtime.setdefault("cueBindings", {}) if isinstance(web_runtime, dict) else {}
            if isinstance(bindings, dict):
                for key, value in empty_manifest()["runtime"]["web"]["cueBindings"].items():
                    bindings.setdefault(key, value)
        return manifest


def get_project_background_catalog(user_id: str, project_name: str) -> list[dict[str, str]]:
    """返回可供编辑器与 Scriptwriter 绑定的项目背景白名单。"""
    manifest = load_project_manifest(user_id, project_name)
    assets = manifest.get("assets") if isinstance(manifest, dict) else {}
    if not isinstance(assets, dict):
        return []
    result: list[dict[str, str]] = []
    for asset_id, asset in assets.items():
        if not isinstance(asset, dict) or asset.get("type") != "background":
            continue
        normalized_id = str(asset.get("id") or asset_id or "").strip()
        if not normalized_id:
            continue
        result.append({
            "id": normalized_id,
            "title": str(asset.get("title") or normalized_id).strip(),
        })
    return sorted(result, key=lambda item: (item["title"], item["id"]))


def save_manifest_to_root(root: str, manifest: dict[str, Any]) -> None:
    """以原子替换方式保存 manifest，避免并发读取半写入 JSON。"""
    with _MANIFEST_LOCK:
        os.makedirs(root, exist_ok=True)
        payload = manifest if isinstance(manifest, dict) else empty_manifest()
        path = _manifest_path(root)
        temporary_path = f"{path}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)


def get_ignored_act_keys(manifest: dict[str, Any], target: str) -> set[str]:
    """读取指定运行目标应忽略的 act 键。"""
    target_key = str(target or "").strip().lower()
    if not target_key:
        return set()
    ignore = manifest.get("ignore") if isinstance(manifest, dict) else None
    target_rules = ignore.get(target_key) if isinstance(ignore, dict) else None
    raw_keys = target_rules.get("actKeys") if isinstance(target_rules, dict) else []
    if not isinstance(raw_keys, list):
        return set()
    return {str(key).strip() for key in raw_keys if str(key).strip()}


def get_ignored_node_keys(manifest: dict[str, Any], target: str) -> set[str]:
    """读取指定运行目标应忽略的节点级字段。"""
    target_key = str(target or "").strip().lower()
    if not target_key:
        return set()
    ignore = manifest.get("ignore") if isinstance(manifest, dict) else None
    target_rules = ignore.get(target_key) if isinstance(ignore, dict) else None
    raw_keys = target_rules.get("nodeKeys") if isinstance(target_rules, dict) else []
    if not isinstance(raw_keys, list):
        return set()
    return {str(key).strip() for key in raw_keys if str(key).strip()}


def filter_act_for_target(act: Optional[dict[str, Any]], manifest: dict[str, Any], target: str) -> dict[str, Any]:
    """按 manifest 规则过滤 act，供 Unity 等目标复用。"""
    if not isinstance(act, dict) or not act:
        return {}
    ignored_keys = get_ignored_act_keys(manifest, target)
    if not ignored_keys:
        return dict(act)
    return {key: value for key, value in act.items() if key not in ignored_keys}


def load_project_manifest(user_id: str, project_name: str) -> dict[str, Any]:
    """读取项目演出资源 manifest。"""
    return load_manifest_from_root(_project_root(user_id, project_name))


def upload_presentation_asset(
    *,
    user_id: str,
    project_name: str,
    asset_type: str,
    data: bytes,
    filename: str = "",
    content_type: Optional[str] = None,
    title: str = "",
    source: str = "upload",
    prompt: str = "",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """写入 Web 播放器专用演出图片资产，并注册到 manifest。"""
    if not data:
        raise PresentationAssetError("图片内容为空")
    if len(data) > 25 * 1024 * 1024:
        raise PresentationAssetError("图片不能超过 25MB")
    kind = str(asset_type or "").strip()
    config = ASSET_KIND_CONFIG.get(kind)
    if not config:
        raise PresentationAssetError(f"不支持的演出资源类型: {asset_type}")

    mime_type, ext = _detect_image_type(data, content_type)
    root = _project_root(user_id, project_name)
    with _MANIFEST_LOCK:
        manifest = load_manifest_from_root(root)
        asset_id = f"{config['prefix']}_{uuid.uuid4().hex[:12]}"
        rel_path = f"{config['dir']}/{asset_id}{ext}"
        abs_path = _safe_join(root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        temporary_path = f"{abs_path}.{uuid.uuid4().hex}.tmp"
        try:
            with open(temporary_path, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, abs_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

        clean_title = str(title or "").strip() or os.path.splitext(os.path.basename(filename or ""))[0] or asset_id
        asset = {
            "id": asset_id,
            "type": kind,
            "targets": ["web"],
            "source": source,
            "title": clean_title,
            "path": rel_path,
            "mimeType": mime_type,
            "prompt": str(prompt or "").strip(),
            "createdAt": _now_iso(),
        }
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    asset[key] = value
        manifest.setdefault("assets", {})[asset_id] = asset
        try:
            save_manifest_to_root(root, manifest)
        except Exception:
            if os.path.isfile(abs_path):
                os.remove(abs_path)
            raise
        return dict(asset)


def update_presentation_asset_metadata(
    user_id: str,
    project_name: str,
    asset_id: str,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """在 manifest 临界区内更新单个资产元数据，并返回资产与完整 manifest。"""
    clean_asset_id = str(asset_id or "").strip()
    if not clean_asset_id:
        raise PresentationAssetError("缺少演出资源 ID")
    root = _project_root(user_id, project_name)
    with _MANIFEST_LOCK:
        manifest = load_manifest_from_root(root)
        assets = manifest.setdefault("assets", {})
        current = assets.get(clean_asset_id) if isinstance(assets, dict) else None
        if not isinstance(current, dict):
            raise PresentationAssetError(f"演出资源不存在: {clean_asset_id}")
        updated = dict(current)
        for key, value in (metadata or {}).items():
            if value is not None:
                updated[key] = value
        assets[clean_asset_id] = updated
        save_manifest_to_root(root, manifest)
        return dict(updated), manifest


def upload_background_asset(
    *,
    user_id: str,
    project_name: str,
    data: bytes,
    filename: str = "",
    content_type: Optional[str] = None,
    title: str = "",
    source: str = "upload",
    prompt: str = "",
) -> dict[str, Any]:
    """写入背景图资产，并注册到 manifest。"""
    return upload_presentation_asset(
        user_id=user_id,
        project_name=project_name,
        asset_type="background",
        data=data,
        filename=filename,
        content_type=content_type,
        title=title,
        source=source,
        prompt=prompt,
    )


def upload_character_sprite_asset(
    *,
    user_id: str,
    project_name: str,
    data: bytes,
    filename: str = "",
    content_type: Optional[str] = None,
    title: str = "",
    source: str = "upload",
    prompt: str = "",
    character_id: str = "",
    expression: str = "default",
) -> dict[str, Any]:
    """写入角色立绘资产，并注册到 manifest。"""
    clean_character_id = str(character_id or "").strip()
    clean_expression = str(expression or "default").strip() or "default"
    return upload_presentation_asset(
        user_id=user_id,
        project_name=project_name,
        asset_type="character_sprite",
        data=data,
        filename=filename,
        content_type=content_type,
        title=title,
        source=source,
        prompt=prompt,
        metadata={
            "characterId": clean_character_id,
            "expression": clean_expression,
        },
    )


def upload_scene_illustration_asset(
    *,
    user_id: str,
    project_name: str,
    data: bytes,
    filename: str = "",
    content_type: Optional[str] = None,
    title: str = "",
    source: str = "upload",
    prompt: str = "",
    scene_name: str = "",
    node_id: str = "",
) -> dict[str, Any]:
    """写入完整场景插图，并记录其创作定位。"""
    return upload_presentation_asset(
        user_id=user_id,
        project_name=project_name,
        asset_type="scene_illustration",
        data=data,
        filename=filename,
        content_type=content_type,
        title=title,
        source=source,
        prompt=prompt,
        metadata={
            "sceneName": str(scene_name or "").strip(),
            "nodeId": str(node_id or "").strip(),
        },
    )


def get_project_asset_path(user_id: str, project_name: str, rel_path: str) -> str:
    """返回项目演出资产绝对路径，并做目录边界检查。"""
    return _safe_presentation_asset_path(_project_root(user_id, project_name), rel_path)


def get_snapshot_asset_path(snapshot_path: str, rel_path: str) -> str:
    """返回快照演出资产绝对路径，并做目录边界检查。"""
    return _safe_presentation_asset_path(_snapshot_sidecar_dir(snapshot_path), rel_path)


def copy_presentation_snapshot(user_id: str, project_name: str, snapshot_path: str) -> Optional[str]:
    """把项目演出 manifest 与资产目录复制到快照 sidecar。"""
    with _MANIFEST_LOCK:
        project_root = _project_root(user_id, project_name)
        source_manifest = _manifest_path(project_root)
        source_assets = os.path.join(project_root, ASSET_ROOT.replace("/", os.sep))

        if not os.path.isfile(source_manifest) and not os.path.isdir(source_assets):
            return None

        sidecar = _snapshot_sidecar_dir(snapshot_path)
        if os.path.isdir(sidecar):
            shutil.rmtree(sidecar)
        os.makedirs(sidecar, exist_ok=True)

        if os.path.isfile(source_manifest):
            shutil.copy2(source_manifest, _manifest_path(sidecar))
        else:
            save_manifest_to_root(sidecar, empty_manifest())

        if os.path.isdir(source_assets):
            target_assets = os.path.join(sidecar, ASSET_ROOT.replace("/", os.sep))
            os.makedirs(os.path.dirname(target_assets), exist_ok=True)
            shutil.copytree(source_assets, target_assets, dirs_exist_ok=True)

        return sidecar


def load_snapshot_manifest(snapshot_path: str) -> dict[str, Any]:
    """读取快照 sidecar 中的演出 manifest。"""
    return load_manifest_from_root(_snapshot_sidecar_dir(snapshot_path))


def remove_presentation_snapshot(snapshot_path: Optional[str]) -> None:
    """删除快照 sidecar。"""
    if not snapshot_path:
        return
    sidecar = _snapshot_sidecar_dir(snapshot_path)
    if os.path.isdir(sidecar):
        shutil.rmtree(sidecar, ignore_errors=True)
