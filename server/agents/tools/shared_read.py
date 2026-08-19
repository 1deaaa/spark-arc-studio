from __future__ import annotations

import os
import re

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import get_project_path
from core.project_settings import get_project_story_tags
from agents.story_terminology import build_story_structure_note, get_story_terminology
from story.outline_parser import parse_outline_markup

from .common import ToolExecutionContext


def _project_story_terms(user_id: str, project_name: str) -> dict[str, str]:
    """读取项目模式并返回用户术语；读取失败时按剧本模式处理。"""
    try:
        tags = get_project_story_tags(user_id, project_name)
        mode = (tags or {}).get("workspace_mode")
    except Exception:
        mode = "script"
    return get_story_terminology(mode)


def _story_structure_note(user_id: str, project_name: str) -> str:
    """按项目模式生成共享读取工具的结构说明。"""

    terms = _project_story_terms(user_id, project_name)
    return (
        f"{build_story_structure_note(terms['workspace_mode'])} "
        "chapter_index/scene_index 只是逻辑大纲索引，不是 Unicode 文件名排序，也不是物理目录名。"
        f"当前落盘映射为：story_group 文件夹= {terms['group']}，story_unit 正文文件= {terms['unit']}。"
    )


class ReadChapterSceneInput(BaseModel):
    chapter_index: int = Field(description="逻辑大纲故事分组索引（从 0 开始），不是物理文件夹名、chapter 字段或文件名排序")
    scene_index: int | None = Field(default=None, description="逻辑大纲故事单元索引（从 0 开始）。不提供则读取整个逻辑分组对应的正文文件；剧本模式对应场景文件，小说模式对应章节文件")


class ReadChapterOutlineRawInput(BaseModel):
    chapter_index: int = Field(description="逻辑大纲故事分组索引（从 0 开始），对应大纲.txt 中 ## Chapter 的顺序；不是物理文件夹名或文件名排序")


@tool
def list_chapters() -> str:
    """列出逻辑大纲结构及其对应的物理故事分组文件夹/正文文件结构。"""
    user_id, project_name = ToolExecutionContext.get_context()
    structure_note = _story_structure_note(user_id, project_name)

    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return "当前项目尚无大纲数据（大纲.txt 不存在）。"

    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            data = parse_outline_markup(f.read())
    except Exception as e:
        return f"读取大纲失败: {e}"

    nodes = data.get("nodes", [])
    if not nodes:
        return "大纲中没有章节数据。"

    lines = [f"## 项目大纲：{data.get('title', '未命名')}", structure_note]
    summary = data.get("summary", "")
    if summary:
        lines.append(f"概述: {summary}")
    lines.append(f"共 {len(nodes)} 个逻辑大纲章节\n")

    for i, node in enumerate(nodes):
        title = node.get("title") or node.get("name") or f"章节{i + 1}"
        children = node.get("children", [])
        desc = node.get("description") or ""
        lines.append(f"### 逻辑章节 [{i}] {title}  ({len(children)} 个逻辑场景)")
        if desc:
            lines.append(f"  摘要: {desc}")
        for j, scene in enumerate(children):
            scene_title = scene.get("title") or scene.get("name") or f"场景{j + 1}"
            lines.append(f"  - 逻辑场景 [{i}-{j}] {scene_title}")

    return "\n".join(lines)


@tool(args_schema=ReadChapterSceneInput)
def read_chapter_scene(chapter_index: int, scene_index: int | None = None) -> str:
    """按逻辑大纲索引读取对应故事分组/故事单元，并返回匹配的物理正文文件。"""
    user_id, project_name = ToolExecutionContext.get_context()
    structure_note = _story_structure_note(user_id, project_name)
    project_path = get_project_path(user_id, project_name)

    outline_path = os.path.join(project_path, "大纲.txt")
    outline_info = ""
    chapter_node = None
    try:
        if os.path.exists(outline_path):
            with open(outline_path, "r", encoding="utf-8") as f:
                data = parse_outline_markup(f.read())
            nodes = data.get("nodes", [])
            if 0 <= chapter_index < len(nodes):
                chapter_node = nodes[chapter_index]
            else:
                return f"章节索引 {chapter_index} 超出范围（共 {len(nodes)} 章）。"
    except Exception as e:
        return f"读取大纲失败: {e}"

    if chapter_node:
        title = chapter_node.get("title") or chapter_node.get("name") or f"章节{chapter_index + 1}"
        desc = chapter_node.get("description") or ""
        children = chapter_node.get("children", [])

        parts = [structure_note, f"## 大纲 - 逻辑故事分组 {chapter_index}: {title}"]
        if desc:
            parts.append(f"逻辑章节描述:\n{desc}")

        if scene_index is not None:
            if 0 <= scene_index < len(children):
                scene = children[scene_index]
                scene_title = scene.get("title") or scene.get("name") or f"场景{scene_index + 1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 逻辑场景 {chapter_index}-{scene_index}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)
            else:
                parts.append(f"\n逻辑场景索引 {scene_index} 超出范围（本逻辑章节共 {len(children)} 个场景）。")
        else:
            for j, scene in enumerate(children):
                scene_title = scene.get("title") or scene.get("name") or f"场景{j + 1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 逻辑场景 {chapter_index}-{j}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)

        outline_info = "\n".join(parts)

    from core.utils import get_project_stories_path

    stories_path = get_project_stories_path(user_id, project_name)
    script_info = ""
    if os.path.exists(stories_path):
        from story.file_naming import list_story_files

        all_story_files = list_story_files(stories_path)
        target_chapter_num = chapter_index + 1
        chapter_files = [
            entry for entry in all_story_files
            if entry[2] and entry[2].get("chapter_num") == target_chapter_num
        ]

        if not chapter_files and chapter_node:
            chapter_title = str(chapter_node.get("title") or chapter_node.get("name") or "").strip()
            chapter_files = [
                entry for entry in all_story_files
                if chapter_title and entry[0].split("/", 1)[0] == chapter_title
            ]

        if not chapter_files:
            chapter_groups: list[list[tuple]] = []
            group_map: dict[str, list[tuple]] = {}
            for entry in all_story_files:
                group_key = entry[0].split("/", 1)[0] if "/" in entry[0] else ""
                if group_key not in group_map:
                    group_map[group_key] = []
                    chapter_groups.append(group_map[group_key])
                group_map[group_key].append(entry)
            if 0 <= chapter_index < len(chapter_groups):
                chapter_files = chapter_groups[chapter_index]

        selected_files = chapter_files
        if scene_index is not None and chapter_files:
            target_scene_num = scene_index + 1
            identity_match = next(
                (
                    entry for entry in chapter_files
                    if entry[2] and entry[2].get("scene_num") == target_scene_num
                ),
                None,
            )
            selected_files = [identity_match] if identity_match else (
                [chapter_files[scene_index]] if 0 <= scene_index < len(chapter_files) else []
            )

        if selected_files:
            persisted_parts = []
            for rel_path, story_path, parsed in selected_files:
                file_format = str((parsed or {}).get("format") or ("novel" if story_path.endswith(".md") else "arc"))
                fence = "markdown" if file_format == "novel" else "arc"
                format_label = "小说" if file_format == "novel" else "剧本"
                try:
                    with open(story_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    persisted_parts.append(
                        f"## 已落盘{format_label}正文文件: {rel_path}\n```{fence}\n{content}\n```"
                    )
                except Exception as e:
                    persisted_parts.append(f"读取正文文件 {rel_path} 失败: {e}")
            script_info = "\n\n" + "\n\n".join(persisted_parts)
        elif all_story_files:
            script_info = "\n\n（未找到与该章节/场景身份匹配的已落盘正文文件）"
        else:
            script_info = "\n\n（当前项目尚无已落盘正文文件）"

    result = outline_info + script_info
    return result if result.strip() else f"逻辑故事分组 {chapter_index} 没有找到任何内容。"


@tool(args_schema=ReadChapterOutlineRawInput)
def read_chapter_outline_raw(chapter_index: int) -> str:
    """读取指定逻辑大纲故事分组的原文，不代表物理故事分组文件夹或正文文件。"""
    user_id, project_name = ToolExecutionContext.get_context()
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    if not os.path.exists(outline_path):
        return "当前项目尚无大纲数据（大纲.txt 不存在）。"

    with open(outline_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    chapter_pattern = re.compile(r'^(##\s+)', re.MULTILINE)
    splits = list(chapter_pattern.finditer(full_text))

    if not splits:
        if chapter_index == 0:
            return full_text
        return f"章节索引 {chapter_index} 超出范围（大纲中没有 ## Chapter 标记）。"

    if chapter_index < 0 or chapter_index >= len(splits):
        return f"章节索引 {chapter_index} 超出范围（共 {len(splits)} 个章节）。"

    start = splits[chapter_index].start()
    if chapter_index + 1 < len(splits):
        end = splits[chapter_index + 1].start()
    else:
        end = len(full_text)

    chapter_raw = full_text[start:end].rstrip()
    return chapter_raw
