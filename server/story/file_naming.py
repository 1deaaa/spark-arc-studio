from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple


STORY_META_MARKER = ".__spark__"

_CHINESE_DIGIT_VALUES = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


class DuplicateSceneIdentityError(ValueError):
    """同一规划身份对应多个正文文件，禁止静默覆盖。"""

    def __init__(self, chapter_num: int, scene_num: int, paths: list[str]) -> None:
        self.chapter_num = int(chapter_num)
        self.scene_num = int(scene_num)
        self.paths = paths
        joined = "、".join(paths)
        super().__init__(f"场景 {self.chapter_num}-{self.scene_num} 存在多个文件：{joined}")


def _parse_number_token(value: str) -> Optional[int]:
    """解析阿拉伯数字或常用中文数字，返回正整数。"""
    token = str(value or "").strip()
    if token.isdigit():
        number = int(token)
        return number if number > 0 else None
    if not token or any(char not in _CHINESE_DIGIT_VALUES and char != "十" for char in token):
        return None
    if token == "十":
        return 10
    if "十" in token:
        left, right = token.split("十", 1)
        tens = _CHINESE_DIGIT_VALUES.get(left, 1) if left else 1
        ones = _CHINESE_DIGIT_VALUES.get(right, 0) if right else 0
        number = tens * 10 + ones
    else:
        number = 0
        for char in token:
            number = number * 10 + _CHINESE_DIGIT_VALUES[char]
    return number if number > 0 else None


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


def parse_scene_identity_from_title(value: str | None) -> tuple[Optional[int], Optional[int]]:
    """从多种历史标题写法中解析规划场景身份。"""
    text = str(value or "").strip()
    if not text:
        return None, None
    match = re.match(
        r"^\s*(?:场景\s*)?第?\s*(\d{1,4}|[零〇一二两三四五六七八九十]+)\s*[-－—_]\s*"
        r"(\d{1,4}|[零〇一二两三四五六七八九十]+)(?=\D|$)",
        text,
    )
    if not match:
        return None, None
    return _parse_number_token(match.group(1)), _parse_number_token(match.group(2))


def parse_chapter_identity_from_title(value: str | None) -> Optional[int]:
    """从章节/分卷目录名中解析编号，用于跨标题复用目录。"""
    text = str(value or "").strip()
    match = re.match(
        r"^\s*(?:第\s*)?(?:卷\s*)?(\d{1,4}|[零〇一二两三四五六七八九十]+)"
        r"\s*(?:章|卷)?(?:\s*[·•:：._-]|\s+|$)",
        text,
    )
    return _parse_number_token(match.group(1)) if match else None


def canonical_scene_display_name(value: str | None, chapter_num: int, scene_num: int) -> str:
    """把场景标题归一化为稳定的“章号-场号 标题”显示名。"""
    chapter = int(chapter_num)
    scene = int(scene_num)
    if chapter <= 0 or scene <= 0:
        raise ValueError("章节号和场景号必须是大于 0 的整数。")
    text = sanitize_story_display_name(str(value or "").strip(), "")
    text = re.sub(
        r"^\s*(?:场景\s*)?第?\s*(?:\d{1,4}|[零〇一二两三四五六七八九十]+)\s*[-－—_]\s*"
        r"(?:第?\s*)?(?:\d{1,4}|[零〇一二两三四五六七八九十]+)\s*(?:[:：·.]\s*|\s+)?",
        "",
        text,
    ).strip()
    if not text:
        raise ValueError("场景标题必须包含可读标题，不能只有编号。")
    return f"{chapter}-{scene} {text}"


def find_scene_file_by_identity(
    stories_path: str,
    chapter_num: int,
    scene_num: int,
    *,
    file_format: str = "arc",
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """递归按文件名 meta 查找规划场景文件。"""
    matches = find_scene_files_by_identity(
        stories_path,
        chapter_num,
        scene_num,
        file_format=file_format,
    )
    if not matches:
        return None, None
    return matches[0]


def find_scene_files_by_identity(
    stories_path: str,
    chapter_num: int,
    scene_num: int,
    *,
    file_format: str = "arc",
) -> list[tuple[str, Dict[str, Any]]]:
    """返回同一规划身份的全部文件，兼容历史无元数据文件。"""
    target_ext = story_extension(file_format)
    if not os.path.isdir(stories_path):
        return []

    matches: list[tuple[tuple, str, Dict[str, Any]]] = []
    for root, _, files in os.walk(stories_path):
        for filename in files:
            parsed = parse_story_filename(filename)
            if not parsed:
                continue
            if parsed.get("extension") != target_ext:
                continue
            if parsed.get("free"):
                continue
            parsed_chapter = parsed.get("chapter_num")
            parsed_scene = parsed.get("scene_num")
            if parsed_chapter is None or parsed_scene is None:
                parsed_chapter, parsed_scene = parse_scene_identity_from_title(parsed.get("display_name"))
            if parsed_chapter != int(chapter_num) or parsed_scene != int(scene_num):
                continue
            rel_path = os.path.relpath(os.path.join(root, filename), stories_path).replace(os.sep, "/")
            matches.append((story_sort_key(rel_path), os.path.join(root, filename), parsed))

    if not matches:
        return []
    matches.sort(key=lambda item: item[0])
    return [(path, parsed) for _, path, parsed in matches]


def resolve_chapter_directory(
    stories_path: str,
    chapter_dir_name: str,
    *,
    chapter_num: Optional[int] = None,
) -> str:
    """优先复用同编号章节目录，避免标题变化后生成重复文件夹。"""
    safe_name = str(chapter_dir_name or "").strip().replace("\\", "_").replace("/", "_")
    exact_path = os.path.join(stories_path, safe_name) if safe_name else stories_path
    if os.path.isdir(exact_path):
        return exact_path

    identity = chapter_num if chapter_num is not None else parse_chapter_identity_from_title(safe_name)
    if identity is not None and os.path.isdir(stories_path):
        matches = [
            item for item in os.listdir(stories_path)
            if os.path.isdir(os.path.join(stories_path, item))
            and parse_chapter_identity_from_title(item) == int(identity)
        ]
        if matches:
            matches.sort(key=str.casefold)
            return os.path.join(stories_path, matches[0])
    return exact_path


def resolve_planned_scene_file_path(
    stories_path: str,
    chapter_num: int,
    scene_num: int,
    scene_title: str,
    *,
    chapter_dir_name: str = "",
    file_format: str = "arc",
) -> Tuple[str, bool, Dict[str, Any] | None]:
    """解析规划场景文件路径：已有则覆盖，未有则按身份新建。"""
    matches = find_scene_files_by_identity(
        stories_path,
        chapter_num,
        scene_num,
        file_format=file_format,
    )
    if len(matches) > 1:
        relative_paths = [
            os.path.relpath(path, stories_path).replace(os.sep, "/")
            for path, _ in matches
        ]
        raise DuplicateSceneIdentityError(chapter_num, scene_num, relative_paths)
    if matches:
        existing_path, parsed = matches[0]
        return existing_path, True, parsed

    target_dir = resolve_chapter_directory(
        stories_path,
        chapter_dir_name,
        chapter_num=int(chapter_num),
    )
    filename = build_scene_story_filename(
        chapter_num,
        scene_num,
        scene_title,
        file_format=file_format,
    )
    return os.path.join(target_dir, filename), False, None


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


def rebuild_story_filename(
    filename: str,
    *,
    display_name: Optional[str] = None,
    order: Optional[int] = None,
    chapter_num: Optional[int] = None,
) -> str:
    parsed = parse_story_filename(filename)
    if not parsed:
        base = sanitize_story_display_name(display_name or os.path.splitext(filename)[0])
        return f"{base}{os.path.splitext(filename)[1] or '.arc'}"
    effective_order = parsed["order"] if order is None else int(order)
    effective_chap = parsed["chapter_num"] if chapter_num is None else chapter_num
    return build_story_filename(
        display_name or parsed["display_name"],
        file_format=parsed["format"],
        chapter_num=effective_chap,
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


def list_story_files(
    stories_path: str,
    *,
    file_format: str | None = None,
) -> list[tuple[str, str, Optional[Dict[str, Any]]]]:
    """递归列出作品正文文件，返回相对路径、绝对路径和文件名元数据。"""
    if not os.path.isdir(stories_path):
        return []

    target_ext = story_extension(file_format) if file_format else None
    entries: list[tuple[tuple, str, str, Optional[Dict[str, Any]]]] = []
    for root, dirs, files in os.walk(stories_path):
        dirs.sort()
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in {".arc", ".md"}:
                continue
            if target_ext and ext != target_ext:
                continue
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, stories_path).replace(os.sep, "/")
            parsed = parse_story_filename(filename)
            entries.append((story_sort_key(rel_path), rel_path, abs_path, parsed))

    entries.sort(key=lambda item: (item[0], item[1].lower()))
    return [(rel_path, abs_path, parsed) for _, rel_path, abs_path, parsed in entries]


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
