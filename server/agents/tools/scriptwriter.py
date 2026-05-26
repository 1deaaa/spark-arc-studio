from __future__ import annotations

import os

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import get_project_path
from agents.project_content import load_worldview

from .common import ToolExecutionContext, _apply_patch


class CreateOrRewriteScriptInput(BaseModel):
    overwrite_content: str = Field(description="完整的剧本/小说正文。若目标场景文件尚不存在，系统将自动创建；若已存在则覆盖。必须只包含最终可保存的正文，不得混入解释、确认话术或元话语。")
    chapter_name: str | None = Field(default=None, description="目标章节名称（即文件夹名称）。【CRITICAL】剧本将保存到该章节目录下。写剧本/小说前，必须先调用 create_chapter 确保该章节目录存在，并在此传入一致的章节名。严禁在不指定章节的情况下调用此工具往根目录写入孤儿场景文件。")
    work_name: str | None = Field(default=None, description="场景文件的显示名称（不含扩展名）。若不提供，系统将自动根据内容或上下文命名。")
    export_format: str | None = Field(default=None, description="输出格式：'arc' 为互动剧本（默认），'novel' 为纯文学小说。决定文件扩展名与格式规范。")


class CreateChapterInput(BaseModel):
    chapter_name: str = Field(description="章节名称，将作为 stories 目录下的子文件夹名称。建议格式如「第一章_开端」或「第01章_相遇」。")


class PatchScriptInput(BaseModel):
    search_text: str = Field(description="需要被替换的剧本片段（必须精确匹配原文）。传入空字符串可将 replace_text 追加到文件末尾")
    replace_text: str = Field(description="修改后的新文本片段")


class ReadCharacterInput(BaseModel):
    character_name: str = Field(description="要查阅的角色名字，例如'张三'")


def _ensure_chapter_dir(stories_path: str, chapter_name: str) -> str:
    safe = (chapter_name or "").strip().replace("\\", "_").replace("/", "_")
    if not safe:
        return stories_path
    chapter_dir = os.path.join(stories_path, safe)
    os.makedirs(chapter_dir, exist_ok=True)
    return chapter_dir


@tool
def read_worldview() -> str:
    """读取世界观全文。"""
    user_id, project_name = ToolExecutionContext.get_context()
    content = load_worldview(user_id, project_name)
    return content if content else "未找到世界观设定。"


@tool(args_schema=ReadCharacterInput)
def read_character(character_name: str) -> str:
    """读取角色设定。

    历史 Bug：旧版本是用"文件名包含字符串"做匹配，但角色文件是用 ID 命名
    （如 ``0.txt``），传入真实角色名（如"沈逐流"）永远命中不到。现已改为
    通过统一工具 ``lookup_character_id_by_name`` 走 chr.bind 反查。
    """
    from story.project_files import (
        get_character_file_path,
        lookup_character_id_by_name,
    )

    user_id, project_name = ToolExecutionContext.get_context()
    char_id = lookup_character_id_by_name(user_id, project_name, character_name)
    if not char_id:
        return f"未找到名为 '{character_name}' 的角色档案。"

    char_file = get_character_file_path(user_id, project_name, char_id)
    if not char_file:
        return f"找到角色 '{character_name}' 但其设定文件丢失。"

    with open(char_file, "r", encoding="utf-8") as f:
        return f.read()


@tool
def read_synopsis() -> str:
    """读取故事梗概。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    if not os.path.exists(synopsis_path):
        return "未找到故事梗概。"
    with open(synopsis_path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def read_beat_sheet() -> str:
    """读取节拍表。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if not os.path.exists(beats_path):
        return "未找到节拍表。"
    with open(beats_path, "r", encoding="utf-8") as f:
        return f.read()


@tool(args_schema=CreateOrRewriteScriptInput)
def create_or_rewrite_script(
    overwrite_content: str,
    chapter_name: str | None = None,
    work_name: str | None = None,
    export_format: str | None = None,
) -> str:
    """创建或覆盖剧本文件。"""
    from core.utils import get_project_stories_path
    from story.file_naming import build_story_filename, next_story_order, sanitize_story_display_name

    effective_format = export_format or "arc"

    content = (overwrite_content or "").strip()
    if not content:
        return "创建/重写剧本失败：overwrite_content 为空。"

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)
    os.makedirs(stories_path, exist_ok=True)

    if chapter_name and chapter_name.strip():
        target_dir = _ensure_chapter_dir(stories_path, chapter_name.strip())
        relative_dir = chapter_name.strip().replace("\\", "_").replace("/", "_")
    else:
        target_dir = stories_path
        relative_dir = ""

    display = sanitize_story_display_name(work_name.strip() if work_name and work_name.strip() else "新场景")
    order = next_story_order(stories_path, relative_dir)
    filename = build_story_filename(display, file_format=effective_format, order=order)
    file_path = os.path.join(target_dir, filename)

    import re as _re

    if effective_format != "novel" and not _re.search(r'^#\s+\S', content, _re.MULTILINE):
        content = f"# {display}\n{content}"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    rel = os.path.join(relative_dir, filename).replace("\\", "/") if relative_dir else filename
    format_label = "小说" if effective_format == "novel" else "剧本"
    return f"{format_label}已保存：{rel}"


@tool(args_schema=CreateChapterInput)
def create_chapter(chapter_name: str) -> str:
    """创建章节目录。"""
    from core.utils import get_project_stories_path

    name = (chapter_name or "").strip()
    if not name:
        return "创建章节失败：chapter_name 不能为空。"

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)
    chapter_dir = _ensure_chapter_dir(stories_path, name)
    return f"章节已创建：{name}（路径：{chapter_dir}）"


@tool(args_schema=PatchScriptInput)
def patch_script(search_text: str, replace_text: str) -> str:
    """局部修改剧本内容。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    from core.utils import get_project_stories_path

    user_id, project_name = ToolExecutionContext.get_context()
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        return "局部修改剧本失败：stories 目录不存在。"

    arc_files = sorted(f for f in os.listdir(stories_path) if f.endswith(".arc"))

    for filename in arc_files:
        file_path = os.path.join(stories_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            arc_content = f.read()
        if search_text in arc_content:
            return _apply_patch(file_path, search_text, replace_text, file_label=filename)

    for filename in arc_files:
        file_path = os.path.join(stories_path, filename)
        result = _apply_patch(file_path, search_text, replace_text, file_label=filename)
        if not result.startswith("局部修改失败"):
            return result

    return (
        "局部修改剧本失败：在当前项目所有剧本文件中均未找到与 search_text 匹配的片段。\n"
        "提示：请确保 search_text 取自原文的完整连续片段（建议 1‑3 句），不要包含额外解释性文字。"
    )
