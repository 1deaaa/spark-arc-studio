from __future__ import annotations

import os
import re
import shutil
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, Dict, Optional, Tuple


# 兼容协议：chap/scene 是历史文件名元数据键，分别保存 story_group（外层
# 物理文件夹）和 story_unit（内层正文文件）的稳定身份。它们不是用户业务
# 术语；剧本模式的业务称谓是“剧幕/场景”，小说模式是“分卷/章节”。
# 不要按键名推断层级，也不要为了调整显示称谓而改名，否则历史文件将无法解析。
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


class StoryRenameConflictError(ValueError):
    """故事文件批量重命名发生冲突，事务尚未开始写入。"""


class StoryRenameTransactionError(RuntimeError):
    """故事文件批量重命名过程中失败，事务已尝试回滚。"""


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


def _format_chinese_number(value: int) -> str:
    """把正整数格式化为适合章节显示的中文数字。"""
    number = int(value)
    if number <= 0:
        raise ValueError("章节号必须是大于 0 的整数。")
    digits = "零一二三四五六七八九"
    if number < 10:
        return digits[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        return ("十" if tens == 1 else f"{digits[tens]}十") + (digits[ones] if ones else "")
    return str(number)


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
    """解析正文文件名。

    返回的 ``chapter_num``/``scene_num`` 字段沿用历史接口命名：它们只是
    story_group/story_unit 的稳定元数据，不等同于当前模式下用户看到的
    “剧幕/场景”或“分卷/章节”术语。
    """
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
    """构造正文文件名，并保留历史 chap/scene/order 元数据键。"""
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


def canonical_chapter_display_name(value: str | None, chapter_num: int) -> str:
    """把章节/分卷标题归一化为稳定的“中文编号 · 标题”显示名。"""
    chapter = int(chapter_num)
    prefix = _format_chinese_number(chapter)
    text = sanitize_story_display_name(str(value or "").strip(), "")
    text = re.sub(
        r"^\s*(?:Chapter\s*)?(?:第\s*)?(?:卷\s*)?"
        r"(?:\d{1,4}|[零〇一二两三四五六七八九十]+)\s*(?:章|卷)?\s*"
        r"(?:[·•:：._-]\s*|\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if not text:
        raise ValueError("章节标题必须包含可读标题，不能只有编号。")
    return f"{prefix} · {text}"


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
    """解析并复用 story_group 物理文件夹，兼容历史 chapter 命名。"""
    safe_name = str(chapter_dir_name or "").strip().replace("\\", "_").replace("/", "_")
    exact_path = os.path.join(stories_path, safe_name) if safe_name else stories_path
    if os.path.isdir(exact_path):
        return exact_path

    # story_group 文件夹本身没有稳定元数据；只有目录内正文文件的历史 chap
    # 元数据可用于复用。chapter_dir_name 只是旧接口名，不代表用户术语。
    if chapter_num is not None and os.path.isdir(stories_path):
        matches: list[str] = []
        for item in os.listdir(stories_path):
            directory = os.path.join(stories_path, item)
            if not os.path.isdir(directory):
                continue
            for filename in os.listdir(directory):
                parsed = parse_story_filename(filename)
                if parsed and parsed.get("chapter_num") == int(chapter_num) and not parsed.get("free"):
                    matches.append(directory)
                    break
        if len(matches) == 1:
            return matches[0]
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
    scene_num: Optional[int] = None,
) -> str:
    parsed = parse_story_filename(filename)
    if not parsed:
        base = sanitize_story_display_name(display_name or os.path.splitext(filename)[0])
        return f"{base}{os.path.splitext(filename)[1] or '.arc'}"
    effective_order = parsed["order"] if order is None else int(order)
    effective_chap = parsed["chapter_num"] if chapter_num is None else chapter_num
    effective_scene = parsed["scene_num"] if scene_num is None else scene_num
    return build_story_filename(
        display_name or parsed["display_name"],
        file_format=parsed["format"],
        chapter_num=effective_chap,
        scene_num=effective_scene,
        order=effective_order,
        group=parsed["group"],
        free=parsed["free"],
    )


def story_sort_key(rel_path: str) -> tuple:
    parsed = parse_story_filename(os.path.basename(rel_path))
    if not parsed:
        return (999999, 999, 999, str(rel_path or "").lower(), str(rel_path or "").lower())

    display_name = str(parsed.get("display_name") or "")
    inferred_chapter = parsed.get("chapter_num")
    inferred_scene = parsed.get("scene_num")
    if inferred_chapter is None:
        inferred_chapter = parse_chapter_identity_from_title(display_name)
    if inferred_chapter is None or inferred_scene is None:
        title_chapter, title_scene = parse_scene_identity_from_title(display_name)
        if inferred_chapter is None:
            inferred_chapter = title_chapter
        if inferred_scene is None:
            inferred_scene = title_scene
    return (
        parsed["order"] if parsed["order"] is not None else 999999,
        inferred_chapter if inferred_chapter is not None else 999,
        inferred_scene if inferred_scene is not None else 999,
        display_name.lower(),
        str(rel_path or "").lower(),
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


def load_stories_order(order_path: str) -> dict:
    """读取章节/分卷显示顺序清单；文件不存在或损坏时返回空对象。"""
    import json

    if not os.path.exists(order_path):
        return {}
    try:
        with open(order_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def rewrite_stories_order_names(value: object, rename_map: dict[str, str]) -> object:
    """递归同步目录重命名对 stories_order.json 中名称引用的影响。"""
    if isinstance(value, list):
        return [rewrite_stories_order_names(item, rename_map) for item in value]
    if isinstance(value, dict):
        return {
            rename_map.get(str(key), key): rewrite_stories_order_names(item, rename_map)
            for key, item in value.items()
        }
    if isinstance(value, str):
        return rename_map.get(value, value)
    return value


def write_stories_order_atomic(order_path: str, data: dict) -> None:
    """以临时文件原子替换章节/分卷显示顺序清单。"""
    import json

    order_directory = os.path.dirname(os.path.abspath(order_path))
    temporary_path = os.path.join(
        order_directory,
        make_temp_story_filename(os.path.basename(order_path)),
    )
    os.makedirs(order_directory, exist_ok=True)
    try:
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temporary_path, order_path)
    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass


def _absolute_story_path(stories_path: str, path: str, *, allow_missing: bool = False) -> str:
    """解析并限制 stories 内的路径，拒绝目录穿越和 stories 本身。"""
    root = os.path.abspath(os.path.normpath(os.fspath(stories_path)))
    raw_path = os.fspath(path)
    candidate = raw_path if os.path.isabs(raw_path) else os.path.join(root, raw_path)
    candidate = os.path.abspath(os.path.normpath(candidate))
    try:
        inside = os.path.commonpath((root, candidate)) == root
    except ValueError:
        inside = False
    if not inside or os.path.normcase(candidate) == os.path.normcase(root):
        raise StoryRenameConflictError(f"故事路径必须位于 stories 目录内：{path}")
    if not allow_missing and not os.path.exists(candidate):
        raise StoryRenameConflictError(f"故事文件不存在：{path}")
    return candidate


def _normalize_rename_pairs(
    rename_pairs: Iterable[tuple[str, str]],
    *,
    root_path: str | None = None,
    expect_directory: bool = False,
) -> list[tuple[str, str]]:
    """预校验批量重命名计划，允许交换目标但禁止覆盖无关文件。"""
    normalized: list[tuple[str, str]] = []
    source_keys: set[str] = set()
    target_keys: set[str] = set()
    root = os.path.abspath(os.path.normpath(os.fspath(root_path))) if root_path else None
    pairs = list(rename_pairs)

    raw_sources: list[str] = []
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise StoryRenameConflictError("批量重命名项必须是 [源路径, 目标路径]。")
        source_raw = pair[0]
        source = _absolute_story_path(root, source_raw) if root else os.path.abspath(os.path.normpath(os.fspath(source_raw)))
        raw_sources.append(source)
    source_path_keys = {os.path.normcase(path) for path in raw_sources}

    for index, pair in enumerate(pairs):
        source_raw, target_raw = pair
        source = raw_sources[index]
        target = _absolute_story_path(root, target_raw, allow_missing=True) if root else os.path.abspath(os.path.normpath(os.fspath(target_raw)))
        source_key = os.path.normcase(source)
        target_key = os.path.normcase(target)
        if source_key == target_key:
            continue
        if source_key in source_keys:
            raise StoryRenameConflictError(f"同一源文件被重复重命名：{source}")
        if target_key in target_keys:
            raise StoryRenameConflictError(f"多个文件指向同一目标：{target}")
        if not os.path.exists(source):
            raise StoryRenameConflictError(f"源路径不存在：{source}")
        if expect_directory:
            if not os.path.isdir(source):
                raise StoryRenameConflictError(f"源路径不是章节目录：{source}")
        elif not os.path.isfile(source):
            raise StoryRenameConflictError(f"源路径不是故事文件：{source}")
        if os.path.exists(target) and target_key not in source_path_keys:
            raise StoryRenameConflictError(f"目标路径已存在：{target}")
        if expect_directory and os.path.dirname(target) != os.path.dirname(source):
            raise StoryRenameConflictError("章节目录重命名只能在同一父目录内进行。")
        source_keys.add(source_key)
        target_keys.add(target_key)
        normalized.append((source, target))

    return normalized


def _story_identity_from_path(path: str) -> tuple[str, int, int] | None:
    """读取故事路径中的稳定场景身份。"""
    parsed = parse_story_filename(os.path.basename(path))
    if not parsed or parsed.get("free"):
        return None
    chapter_num = parsed.get("chapter_num")
    scene_num = parsed.get("scene_num")
    if chapter_num is None or scene_num is None:
        chapter_num, scene_num = parse_scene_identity_from_title(parsed.get("display_name"))
    if chapter_num is None or scene_num is None:
        return None
    return str(parsed.get("format") or "arc"), int(chapter_num), int(scene_num)


def validate_story_identity_plan(
    stories_path: str,
    rename_pairs: list[tuple[str, str]],
    *,
    preserve_sources: bool = False,
) -> None:
    """校验批量计划不会产生重复的章节-场景身份。

    重命名/移动时源文件会消失，因此可以把源路径排除在占用检查外；
    复制时源文件仍然存在，必须把源路径继续视为占用者。
    """
    source_keys = {os.path.normcase(os.path.abspath(source)) for source, _ in rename_pairs}
    seen_targets: dict[tuple[str, int, int], str] = {}
    for _, target in rename_pairs:
        identity = _story_identity_from_path(target)
        if identity is None:
            continue
        previous = seen_targets.get(identity)
        if previous:
            raise StoryRenameConflictError(
                f"批量操作会产生重复场景身份 {identity[1]}-{identity[2]}：{previous}、{target}"
            )
        seen_targets[identity] = target

    for _, existing_path, _ in list_story_files(stories_path):
        if not preserve_sources and os.path.normcase(os.path.abspath(existing_path)) in source_keys:
            continue
        identity = _story_identity_from_path(existing_path)
        if identity is None:
            continue
        target = seen_targets.get(identity)
        if target:
            relative_existing = os.path.relpath(existing_path, stories_path).replace(os.sep, "/")
            raise StoryRenameConflictError(
                f"场景身份 {identity[1]}-{identity[2]} 已被文件占用：{relative_existing}"
            )


def validate_story_order_plan(
    stories_path: str,
    rename_pairs: list[tuple[str, str]],
) -> None:
    """校验批量元数据更新后的非空 order 在整个 stories 中保持唯一。"""
    source_keys = {os.path.normcase(os.path.abspath(source)) for source, _ in rename_pairs}
    occupied: dict[int, str] = {}

    def _record(path: str) -> None:
        parsed = parse_story_filename(os.path.basename(path))
        order = (parsed or {}).get("order")
        if order is None:
            return
        order = int(order)
        previous = occupied.get(order)
        if previous:
            raise StoryRenameConflictError(
                f"正文排序 order={order} 重复：{previous}、{path}"
            )
        occupied[order] = path

    for _, existing_path, _ in list_story_files(stories_path):
        if os.path.normcase(os.path.abspath(existing_path)) not in source_keys:
            _record(existing_path)
    for _, target in rename_pairs:
        _record(target)


def _transactional_rename_paths(
    rename_pairs: list[tuple[str, str]],
    *,
    expect_directory: bool,
) -> list[tuple[str, str]]:
    """以临时路径完成两阶段重命名，并在异常时尽力恢复原路径。"""
    if not rename_pairs:
        return []

    staged: list[tuple[str, str, str]] = []
    finalized: list[tuple[str, str, str]] = []
    try:
        for source, target in rename_pairs:
            suffix = ".__tmp_dir__" if expect_directory else ""
            temporary = os.path.join(
                os.path.dirname(source),
                f".{os.path.basename(source)}{suffix}.{uuid.uuid4().hex}",
            )
            while os.path.exists(temporary):
                temporary = os.path.join(
                    os.path.dirname(source),
                    f".{os.path.basename(source)}{suffix}.{uuid.uuid4().hex}",
                )
            os.replace(source, temporary)
            staged.append((source, target, temporary))

        for source, target, temporary in staged:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(temporary, target)
            finalized.append((source, target, temporary))
    except Exception as exc:
        rollback_errors: list[str] = []
        for source, target, _ in reversed(finalized):
            try:
                if os.path.exists(target):
                    os.replace(target, source)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        for source, _, temporary in reversed(staged):
            try:
                if os.path.exists(temporary):
                    os.replace(temporary, source)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
        detail = f"；回滚异常：{'；'.join(rollback_errors)}" if rollback_errors else ""
        raise StoryRenameTransactionError(f"批量故事路径操作失败：{exc}{detail}") from exc

    return [(source, target) for source, target, _ in finalized]


def batch_rename_story_files(
    rename_pairs: Iterable[tuple[str, str]],
    *,
    stories_path: str | None = None,
    ensure_unique_identity: bool = False,
) -> list[tuple[str, str]]:
    """预校验并事务性重命名故事文件，支持跨章节目录移动。"""
    normalized = _normalize_rename_pairs(rename_pairs, root_path=stories_path)
    if stories_path and ensure_unique_identity:
        validate_story_identity_plan(stories_path, normalized)
    return _transactional_rename_paths(normalized, expect_directory=False)


def batch_copy_story_files(
    copy_pairs: Iterable[tuple[str, str]],
    *,
    stories_path: str | None = None,
    ensure_unique_identity: bool = False,
) -> list[tuple[str, str]]:
    """预校验并批量复制故事文件，失败时删除本次已创建的副本。"""
    normalized = _normalize_rename_pairs(copy_pairs, root_path=stories_path)
    if stories_path and ensure_unique_identity:
        validate_story_identity_plan(stories_path, normalized, preserve_sources=True)
    created: list[str] = []
    try:
        for source, target in normalized:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
            created.append(target)
    except Exception as exc:
        for target in reversed(created):
            try:
                if os.path.exists(target):
                    os.remove(target)
            except Exception:
                pass
        raise StoryRenameTransactionError(f"批量复制故事文件失败：{exc}") from exc
    return normalized


def batch_rename_story_directories(
    rename_pairs: Iterable[tuple[str, str]],
    *,
    stories_path: str,
) -> list[tuple[str, str]]:
    """在 stories 同一层级内事务性重命名章节目录。"""
    normalized = _normalize_rename_pairs(
        rename_pairs,
        root_path=stories_path,
        expect_directory=True,
    )
    return _transactional_rename_paths(normalized, expect_directory=True)


def batch_rename_story_directories_with_order(
    rename_pairs: Iterable[tuple[str, str]],
    *,
    stories_path: str,
    order_path: str,
    order_rename_map: dict[str, str],
) -> list[tuple[str, str]]:
    """事务性重命名章节/分卷目录并同步 stories_order.json。"""
    order_data = rewrite_stories_order_names(
        load_stories_order(order_path),
        order_rename_map,
    )
    renamed: list[tuple[str, str]] = []
    try:
        renamed = batch_rename_story_directories(rename_pairs, stories_path=stories_path)
        write_stories_order_atomic(order_path, order_data)
    except Exception:
        if renamed:
            try:
                batch_rename_story_directories(
                    [(target, source) for source, target in reversed(renamed)],
                    stories_path=stories_path,
                )
            except Exception as rollback_exc:
                raise StoryRenameTransactionError(
                    f"章节目录与顺序清单操作失败，且回滚失败：{rollback_exc}"
                ) from rollback_exc
        raise
    return renamed


def batch_update_story_file_metadata(
    stories_path: str,
    updates: Iterable[Mapping[str, Any]],
) -> list[tuple[str, str]]:
    """批量更新故事文件名元数据，并以事务方式完成显示名和排序字段改写。"""
    normalized_updates = list(updates)
    rename_pairs: list[tuple[str, str]] = []
    for update in normalized_updates:
        if not isinstance(update, Mapping):
            raise StoryRenameConflictError("故事元数据更新项必须是对象。")
        source_value = update.get("path") or update.get("relative_path") or update.get("filename")
        if not source_value:
            raise StoryRenameConflictError("故事元数据更新缺少 path。")
        source_candidate = _absolute_story_path(stories_path, str(source_value), allow_missing=True)
        source = source_candidate
        if not os.path.exists(source_candidate):
            resolved_source, _, _ = resolve_story_file_path(stories_path, str(source_value))
            if not resolved_source:
                raise StoryRenameConflictError(f"故事文件不存在：{source_value}")
            source = _absolute_story_path(stories_path, resolved_source)
        if not os.path.isfile(source):
            raise StoryRenameConflictError(f"故事路径不是文件：{source_value}")
        parsed = parse_story_filename(os.path.basename(source))
        if not parsed:
            raise StoryRenameConflictError(f"无法解析故事文件名元数据：{source_value}")

        values: dict[str, Any] = {
            "display_name": parsed.get("display_name"),
            "order": parsed.get("order"),
            "chapter_num": parsed.get("chapter_num"),
            "scene_num": parsed.get("scene_num"),
        }
        for key in values:
            if key in update and update[key] is not None:
                values[key] = update[key]
        for key in ("order", "chapter_num", "scene_num"):
            if values[key] is not None:
                try:
                    values[key] = int(values[key])
                except (TypeError, ValueError) as exc:
                    raise StoryRenameConflictError(f"{key} 必须是整数：{source_value}") from exc
                if values[key] <= 0:
                    raise StoryRenameConflictError(f"{key} 必须是大于 0 的整数：{source_value}")
        target_name = rebuild_story_filename(
            os.path.basename(source),
            display_name=str(values["display_name"] or ""),
            order=values["order"],
            chapter_num=values["chapter_num"],
            scene_num=values["scene_num"],
        )
        rename_pairs.append((source, os.path.join(os.path.dirname(source), target_name)))

    normalized = _normalize_rename_pairs(rename_pairs, root_path=stories_path)
    validate_story_identity_plan(stories_path, normalized)
    validate_story_order_plan(stories_path, normalized)
    return _transactional_rename_paths(normalized, expect_directory=False)
