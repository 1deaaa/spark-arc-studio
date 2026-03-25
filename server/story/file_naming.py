from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple


STORY_META_MARKER = ".__spark__"


def normalize_story_format(file_format: str | None) -> str:
    return "novel" if str(file_format or "").strip().lower() in {"novel", "md"} else "arc"


def story_extension(file_format: str | None) -> str:
    return ".md" if normalize_story_format(file_format) == "novel" else ".arc"


def sanitize_story_display_name(name: str, fallback: str = "未命名故事") -> str:
    safe = str(name or "").strip() or fallback
    return (
        safe.replace(":", "")
        .replace("：", "")
        .replace("/", "_")
        .replace("\\", "_")
        .replace("|", "_")
    )


def _meta_int(meta: Dict[str, Any], key: str) -> Optional[int]:
    raw = meta.get(key)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def parse_story_filename(filename: str) -> Optional[Dict[str, Any]]:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".arc", ".md"}:
        return None

    stem = os.path.splitext(os.path.basename(filename))[0]
    display_name = stem
    meta: Dict[str, str] = {}
    if STORY_META_MARKER in stem:
        display_name, meta_blob = stem.split(STORY_META_MARKER, 1)
        for token in meta_blob.split("."):
            token = token.strip()
            if not token:
                continue
            if "=" in token:
                key, value = token.split("=", 1)
                meta[key.strip()] = value.strip()
            else:
                meta[token] = "1"

    normalized_display_name = sanitize_story_display_name(display_name, "未命名故事")
    file_format = "novel" if ext == ".md" else "arc"
    return {
        "filename": filename,
        "display_name": normalized_display_name,
        "format": file_format,
        "extension": ext,
        "meta": meta,
        "chapter_num": _meta_int(meta, "chap"),
        "scene_num": _meta_int(meta, "scene"),
        "order": _meta_int(meta, "order"),
        "group": meta.get("group") or "",
        "free": str(meta.get("free", "")).strip().lower() in {"1", "true", "yes"},
    }


def build_story_filename(
    display_name: str,
    *,
    file_format: str = "arc",
    chapter_num: Optional[int] = None,
    scene_num: Optional[int] = None,
    order: Optional[int] = None,
    group: Optional[str] = None,
    free: bool = False,
) -> str:
    safe_display_name = sanitize_story_display_name(display_name)
    tokens: list[str] = []
    if chapter_num is not None:
        tokens.append(f"chap={int(chapter_num):03d}")
    if scene_num is not None:
        tokens.append(f"scene={int(scene_num):03d}")
    if order is not None:
        tokens.append(f"order={int(order):06d}")
    if group:
        normalized_group = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(group).strip())
        if normalized_group:
            tokens.append(f"group={normalized_group}")
    if free:
        tokens.append("free=1")
    suffix = f"{STORY_META_MARKER}{'.'.join(tokens)}" if tokens else ""
    return f"{safe_display_name}{suffix}{story_extension(file_format)}"


def build_scene_story_filename(
    chapter_num: int,
    scene_num: int,
    display_name: str,
    *,
    file_format: str = "arc",
) -> str:
    return build_story_filename(
        display_name,
        file_format=file_format,
        chapter_num=int(chapter_num),
        scene_num=int(scene_num),
        order=int(chapter_num) * 1000 + int(scene_num),
    )


def strip_story_filename_meta(filename: str, *, keep_extension: bool = True) -> str:
    parsed = parse_story_filename(filename)
    if not parsed:
        return filename
    return f"{parsed['display_name']}{parsed['extension'] if keep_extension else ''}"


def build_display_story_path(relative_dir: str, filename: str) -> str:
    parsed = parse_story_filename(filename)
    if not parsed:
        rel = os.path.join(relative_dir, filename) if relative_dir else filename
        return rel.replace(os.sep, "/")

    leaf = parsed["display_name"]
    if parsed["format"] == "novel":
        leaf = f"{leaf}{parsed['extension']}"
    rel = os.path.join(relative_dir, leaf) if relative_dir else leaf
    return rel.replace(os.sep, "/")


def rebuild_story_filename(filename: str, *, display_name: Optional[str] = None, order: Optional[int] = None) -> str:
    parsed = parse_story_filename(filename)
    if not parsed:
        base = sanitize_story_display_name(display_name or os.path.splitext(filename)[0])
        return f"{base}{os.path.splitext(filename)[1] or '.arc'}"
    effective_order = parsed["order"] if order is None else int(order)
    return build_story_filename(
        display_name or parsed["display_name"],
        file_format=parsed["format"],
        chapter_num=parsed["chapter_num"],
        scene_num=parsed["scene_num"],
        order=effective_order,
        group=parsed["group"],
        free=parsed["free"],
    )


def story_sort_key(rel_path: str) -> tuple:
    parsed = parse_story_filename(os.path.basename(rel_path))
    if not parsed:
        return (999999, 999, 999, rel_path.lower())
    return (
        parsed["order"] if parsed["order"] is not None else 999999,
        parsed["chapter_num"] if parsed["chapter_num"] is not None else 999,
        parsed["scene_num"] if parsed["scene_num"] is not None else 999,
        str(parsed["display_name"] or "").lower(),
        rel_path.lower(),
    )


def next_story_order(stories_path: str, relative_dir: str = "") -> int:
    directory = os.path.join(stories_path, relative_dir) if relative_dir else stories_path
    max_order = 0
    if not os.path.exists(directory):
        return 1
    for item in os.listdir(directory):
        parsed = parse_story_filename(item)
        if parsed and parsed["order"] is not None:
            max_order = max(max_order, parsed["order"])
    return max_order + 1


def resolve_story_file_path(stories_path: str, path: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    normalized_path = str(path or "").replace("\\", "/").strip("/")
    if not normalized_path:
        return None, None, None

    direct_candidate = os.path.join(stories_path, normalized_path)
    if os.path.exists(direct_candidate) and os.path.isfile(direct_candidate):
        parsed = parse_story_filename(os.path.basename(direct_candidate))
        if parsed:
            return direct_candidate, parsed["format"], parsed

    desired_dir = os.path.join(stories_path, os.path.dirname(normalized_path))
    if not os.path.isdir(desired_dir):
        return None, None, None

    desired_leaf = os.path.basename(normalized_path)
    desired_stem, desired_ext = os.path.splitext(desired_leaf)
    desired_display = sanitize_story_display_name(desired_stem if desired_ext.lower() in {".arc", ".md"} else desired_leaf)
    expected_exts = [desired_ext.lower()] if desired_ext.lower() in {".arc", ".md"} else [".arc", ".md"]

    for item in os.listdir(desired_dir):
        parsed = parse_story_filename(item)
        if not parsed:
            continue
        if parsed["extension"] not in expected_exts:
            continue
        if parsed["display_name"] != desired_display:
            continue
        actual_path = os.path.join(desired_dir, item)
        return actual_path, parsed["format"], parsed
    return None, None, None


def make_temp_story_filename(filename: str) -> str:
    stem, ext = os.path.splitext(filename)
    return f"{stem}.__tmp__{uuid.uuid4().hex}{ext}"
