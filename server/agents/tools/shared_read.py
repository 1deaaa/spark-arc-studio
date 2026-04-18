from __future__ import annotations

import os
import re

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import get_project_path
from story.outline_parser import parse_outline_markup

from .common import ToolExecutionContext


class ReadChapterSceneInput(BaseModel):
    chapter_index: int = Field(description="章节索引（从 0 开始）")
    scene_index: int | None = Field(default=None, description="场景索引（从 0 开始）。不提供则读取整个章节下所有场景")


class ReadChapterOutlineRawInput(BaseModel):
    chapter_index: int = Field(description="章节索引（从 0 开始），对应大纲.txt中 ## Chapter 的顺序")


@tool
def list_chapters() -> str:
    """列出项目章节与场景结构。"""
    user_id, project_name = ToolExecutionContext.get_context()

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

    lines = [f"## 项目大纲：{data.get('title', '未命名')}"]
    summary = data.get("summary", "")
    if summary:
        lines.append(f"概述: {summary}")
    lines.append(f"共 {len(nodes)} 个章节\n")

    for i, node in enumerate(nodes):
        title = node.get("title") or node.get("name") or f"章节{i + 1}"
        children = node.get("children", [])
        desc = node.get("description") or ""
        lines.append(f"### [{i}] {title}  ({len(children)} 个场景)")
        if desc:
            lines.append(f"  摘要: {desc}")
        for j, scene in enumerate(children):
            scene_title = scene.get("title") or scene.get("name") or f"场景{j + 1}"
            lines.append(f"  - [{i}-{j}] {scene_title}")

    return "\n".join(lines)


@tool(args_schema=ReadChapterSceneInput)
def read_chapter_scene(chapter_index: int, scene_index: int | None = None) -> str:
    """读取指定章节或场景的内容。"""
    user_id, project_name = ToolExecutionContext.get_context()
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

        parts = [f"## 大纲 - 章节 {chapter_index}: {title}"]
        if desc:
            parts.append(f"章节描述:\n{desc}")

        if scene_index is not None:
            if 0 <= scene_index < len(children):
                scene = children[scene_index]
                scene_title = scene.get("title") or scene.get("name") or f"场景{scene_index + 1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 场景 {chapter_index}-{scene_index}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)
            else:
                parts.append(f"\n场景索引 {scene_index} 超出范围（本章共 {len(children)} 个场景）。")
        else:
            for j, scene in enumerate(children):
                scene_title = scene.get("title") or scene.get("name") or f"场景{j + 1}"
                scene_desc = scene.get("description") or ""
                parts.append(f"\n### 场景 {chapter_index}-{j}: {scene_title}")
                if scene_desc:
                    parts.append(scene_desc)

        outline_info = "\n".join(parts)

    from core.utils import get_project_stories_path

    stories_path = get_project_stories_path(user_id, project_name)
    script_info = ""
    if os.path.exists(stories_path):
        arc_files = sorted([f for f in os.listdir(stories_path) if f.endswith(".arc")])
        if 0 <= chapter_index < len(arc_files):
            arc_path = os.path.join(stories_path, arc_files[chapter_index])
            try:
                with open(arc_path, "r", encoding="utf-8") as f:
                    content = f.read()
                script_info = f"\n\n## 剧本文件: {arc_files[chapter_index]}\n```arc\n{content}\n```"
            except Exception as e:
                script_info = f"\n\n读取剧本文件失败: {e}"
        else:
            script_info = "\n\n（该章节尚无对应的 .arc 剧本文件）"

    result = outline_info + script_info
    return result if result.strip() else f"章节 {chapter_index} 没有找到任何内容。"


@tool(args_schema=ReadChapterOutlineRawInput)
def read_chapter_outline_raw(chapter_index: int) -> str:
    """读取指定章节的大纲原文。"""
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
