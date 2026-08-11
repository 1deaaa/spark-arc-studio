import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple
from core.utils import get_project_stories_path, get_project_path
from story.file_naming import (
    build_scene_story_filename,
    list_story_files,
    sanitize_story_display_name,
    strip_story_filename_meta,
    story_extension,
)


def _coerce_positive_int(value: Any, fallback: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _find_scene_file(
    stories_path: str,
    chapter_num: Any,
    scene_num: Any,
    scene_title: str,
    file_format: str = "md",
    story_files: Optional[list[tuple[str, str, Optional[Dict[str, Any]]]]] = None,
) -> Tuple[Optional[str], bool]:
    """
    递归查找匹配指定章节/场景编号的文件。

    优先按元数据（chap=xxx, scene=xxx）匹配，支持文件在任意子目录。
    返回 (文件绝对路径, 是否存在)。
    """
    target_ext = story_extension(file_format)
    normalized_chapter_num = _coerce_positive_int(chapter_num, 1)
    normalized_scene_num = _coerce_positive_int(scene_num, 1)
    available_story_files = story_files if story_files is not None else list_story_files(
        stories_path,
        file_format=file_format,
    )

    # 优先使用规划元数据，避免同名小节被错误归并。
    for _, absolute_path, parsed in available_story_files:
        if not parsed or parsed.get("extension") != target_ext or parsed.get("free"):
            continue
        if (
            parsed.get("chapter_num") == normalized_chapter_num
            and parsed.get("scene_num") == normalized_scene_num
        ):
            return absolute_path, True

    # 兼容手动创建或整理进章节但尚未补齐 scene 元数据的文件。
    desired_display_name = sanitize_story_display_name(str(scene_title or "").strip(), "")
    if desired_display_name:
        for _, absolute_path, parsed in available_story_files:
            if not parsed or parsed.get("extension") != target_ext:
                continue
            if parsed.get("display_name") == desired_display_name:
                return absolute_path, True

    # 未找到，返回预期路径（用于显示）
    expected_filename = build_scene_story_filename(
        normalized_chapter_num,
        normalized_scene_num,
        scene_title,
        file_format=file_format,
    )
    return os.path.join(stories_path, expected_filename), False


def _load_project_outline(user_id: str, project_name: str) -> Dict[str, Any]:
    """读取项目 大纲.txt，解析失败返回空大纲。"""
    from story.outline_parser import parse_outline_markup
    path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(path):
        return {"nodes": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return parse_outline_markup(f.read())
    except Exception:
        return {"nodes": []}


_CONCEPTION_FIELD_RE = re.compile(
    r"^(?P<indent>\s*)(?:[-*]\s*)?[\"']?(?:conception|scene[_ -]?conception|sceneConception)[\"']?\s*[:：=]\s*(?P<value>.*)$",
    re.IGNORECASE,
)

_CONCEPTION_BLOCK_RE = re.compile(
    r"<conception(?:\s[^>]*)?>([\s\S]*?)(?:</conception\s*>|$)",
    re.IGNORECASE,
)


def parse_novel_document(text: Any) -> Dict[str, str]:
    """拆分小说原文中的模型构思和用户可见正文。"""
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    stripped = raw.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            body_candidates = [
                payload.get(key)
                for key in ("content", "body", "text", "正文", "novel")
                if isinstance(payload.get(key), str)
            ]
            body = next((item for item in body_candidates if item.strip()), body_candidates[0] if body_candidates else None)
            conception = next((payload.get(key) for key in ("conception", "scene_conception", "sceneConception") if isinstance(payload.get(key), str)), "")
            if isinstance(body, str):
                return {"body": clean_novel_visible_text(body), "conception": str(conception or "").strip()}

    conceptions = [match.group(1).strip() for match in _CONCEPTION_BLOCK_RE.finditer(raw) if match.group(1).strip()]
    raw = _CONCEPTION_BLOCK_RE.sub("", raw)
    raw = re.sub(r"<conception\s*/>\s*", "", raw, flags=re.IGNORECASE)
    lines: list[str] = []
    source_lines = raw.split("\n")
    index = 0
    while index < len(source_lines):
        line = source_lines[index]
        match = _CONCEPTION_FIELD_RE.match(line)
        if not match:
            lines.append(line)
            index += 1
            continue

        value = match.group("value").strip()
        if value:
            conceptions.append(value)
            index += 1
            continue

        conception_indent = len(match.group("indent").replace("\t", "    "))
        nested: list[str] = []
        index += 1
        while index < len(source_lines):
            candidate = source_lines[index]
            if not candidate.strip():
                index += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip(" \t"))
            if candidate_indent <= conception_indent:
                break
            nested.append(candidate.strip())
            index += 1
        if nested:
            conceptions.append("\n".join(nested))
    return {
        "body": clean_novel_visible_text("\n".join(lines)),
        "conception": next((item for item in reversed(conceptions) if item), "").strip(),
    }


def serialize_novel_document(body: Any, conception: Any = "") -> str:
    """将小说正文与模型构思序列化为稳定的单一文档格式。"""
    normalized_body = str(body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized_conception = str(conception or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_conception:
        return normalized_body
    return f"<conception>\n{normalized_conception}\n</conception>" + (f"\n\n{normalized_body}" if normalized_body else "")


def clean_novel_visible_text(text: Any) -> str:
    """清洗小说对用户可见的正文，隐藏仅供模型使用的构思字段。"""
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    stripped = raw.strip()

    # 模型偶尔会返回 JSON/Markup 对象；只取正文候选字段，丢弃 conception。
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            for key in ("content", "body", "text", "正文", "novel"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    raw = value
                    break

    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    raw = re.sub(
        r"<conception(?:\s[^>]*)?>.*?(?:</conception\s*>|$)",
        "",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    raw = re.sub(r"<conception\s*/>\s*", "", raw, flags=re.IGNORECASE)

    # 只删除行首的明确字段，正文中正常出现“构思”一词不会被误删。
    lines: list[str] = []
    skip_indented = False
    conception_indent = 0
    for line in raw.split("\n"):
        match = _CONCEPTION_FIELD_RE.match(line)
        if match:
            skip_indented = not match.group("value").strip()
            conception_indent = len(match.group("indent").replace("\t", "    "))
            continue
        if skip_indented:
            if not line.strip():
                continue
            line_indent = len(line) - len(line.lstrip(" \t"))
            if line_indent > conception_indent:
                continue
            skip_indented = False
        lines.append(line)
    raw = "\n".join(lines)
    raw = re.sub(r"^\s*[@#]?conception\s*$", "", raw, flags=re.IGNORECASE | re.MULTILINE)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def parse_scene_md(text: str) -> str:
    """
    清洗单个场景 .md 文件：移除 thought 块与 HTML 注释头。
    """
    text = clean_novel_visible_text(text)
    # 移除可能存在的 @intro 开头的多行信息直到遇到空行或 #
    text = re.sub(r'@intro\s*.*?(?=\n\n|\n#|$)', '', text, flags=re.DOTALL)
    
    return text.strip()

def get_novel_chapter_list(user_id: str, project_name: str, export_format: str = "md") -> List[Dict[str, Any]]:
    """
    返回章节+场景的目录树及具体内容，供前端阅读器或导出时聚合使用。
    """
    outline = _load_project_outline(user_id, project_name)
    stories_path = get_project_stories_path(user_id, project_name)
    story_files = list_story_files(stories_path, file_format=export_format)
    matched_paths: set[str] = set()
    
    chapter_nodes = [node for node in (outline.get("nodes", [])) if node.get("type") == "chapter"]
    
    toc = []
    
    for ch_idx, chapter in enumerate(chapter_nodes):
        chapter_num = _coerce_positive_int(chapter.get("chapter"), ch_idx + 1)
        chapter_title = chapter.get("title") or chapter.get("name") or f"Chapter {chapter_num}"
        scenes = chapter.get("children", [])
        if not isinstance(scenes, list):
            scenes = []
        
        chapter_info = {
            "chapter_num": chapter_num,
            "title": chapter_title,
            "scenes": []
        }
        
        for s_idx, scene in enumerate(scenes):
            scene = scene if isinstance(scene, dict) else {}
            scene_title = scene.get("title") or scene.get("name") or f"Scene {s_idx + 1}"
            scene_num = _coerce_positive_int(scene.get("scene_num") or scene.get("scene"), s_idx + 1)
            # 递归查找场景文件（支持子目录）
            filepath, exists = _find_scene_file(
                stories_path,
                chapter_num,
                scene_num,
                scene_title,
                file_format=export_format,
                story_files=story_files,
            )
            
            content = ""
            if exists:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                content = parse_scene_md(raw_content)
            
            # 从实际路径提取文件名用于显示
            actual_filename = os.path.basename(filepath) if exists else build_scene_story_filename(
                chapter_num, scene_num, scene_title, file_format=export_format
            )

            if exists:
                matched_paths.add(_normalize_path(filepath))
                
            chapter_info["scenes"].append({
                "scene_idx": s_idx,
                "title": scene_title,
                "content": content,
                "exists": exists,
                "filename": strip_story_filename_meta(actual_filename)
            })
        
        toc.append(chapter_info)

    chapters_by_num: dict[int, Dict[str, Any]] = {
        _coerce_positive_int(chapter.get("chapter_num"), index + 1): chapter
        for index, chapter in enumerate(toc)
    }
    next_chapter_num = max(chapters_by_num, default=0) + 1

    # 手动创建的 free 文件，以及整理进章节后仍保留 free 标记的文件，
    # 可能没有完整的规划元数据；只要有正文就必须纳入导出目录。
    # 只要文件确实有正文，就补入目录，避免投稿或整本导出静默丢失内容。
    for relative_path, absolute_path, parsed in story_files:
        if _normalize_path(absolute_path) in matched_paths:
            continue

        with open(absolute_path, "r", encoding="utf-8") as f:
            content = parse_scene_md(f.read())
        if not content:
            continue

        parsed_chapter_num = parsed.get("chapter_num") if parsed else None
        if parsed_chapter_num is not None:
            chapter_num = _coerce_positive_int(parsed_chapter_num, next_chapter_num)
            chapter_info = chapters_by_num.get(chapter_num)
            if chapter_info is None:
                display_name = parsed.get("display_name") if parsed else ""
                chapter_info = {
                    "chapter_num": chapter_num,
                    "title": display_name or os.path.splitext(os.path.basename(relative_path))[0],
                    "scenes": [],
                }
                toc.append(chapter_info)
                chapters_by_num[chapter_num] = chapter_info
                next_chapter_num = max(next_chapter_num, chapter_num + 1)
        else:
            display_name = parsed.get("display_name") if parsed else ""
            chapter_info = {
                "chapter_num": next_chapter_num,
                "title": display_name or os.path.splitext(os.path.basename(relative_path))[0],
                "scenes": [],
            }
            toc.append(chapter_info)
            chapters_by_num[next_chapter_num] = chapter_info
            next_chapter_num += 1

        display_name = parsed.get("display_name") if parsed else os.path.splitext(os.path.basename(relative_path))[0]
        chapter_info["scenes"].append({
            "scene_idx": len(chapter_info["scenes"]),
            "title": display_name,
            "content": content,
            "exists": True,
            "filename": strip_story_filename_meta(os.path.basename(relative_path)),
        })
        matched_paths.add(_normalize_path(absolute_path))

    return toc

def aggregate_novel(user_id: str, project_name: str, export_format: str = "md") -> str:
    """
    按 大纲.txt 顺序聚合所有场景 .md 文件，返回完整 Markdown 文本。
    """
    toc = get_novel_chapter_list(user_id, project_name, export_format)
    
    full_text_blocks = []
    full_text_blocks.append(f"# {project_name}\n")
    
    for chapter in toc:
        content_scenes = [
            scene["content"].strip()
            for scene in chapter["scenes"]
            if scene.get("exists") and scene.get("content", "").strip()
        ]
        has_content = bool(content_scenes)
        if not has_content:
            continue
            
        # 章节大标题
        full_text_blocks.append(f"## 第{chapter['chapter_num']}章 {chapter['title']}")
        
        for content in content_scenes:
            # 场景正文（自带 # 场景名，如果是 AI 生成的话。为避免重复，可以直接使用清洗后的 content）
            full_text_blocks.append(content)
            
        full_text_blocks.append("")  # 章节末尾加空行

    return "\n\n".join(full_text_blocks).strip()
