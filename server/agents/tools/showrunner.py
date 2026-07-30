from __future__ import annotations

import os

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import get_project_path

from .common import ToolExecutionContext, _apply_patch, _strip_markdown_fence


class RewriteSynopsisInput(BaseModel):
    overwrite_content: str = Field(description="完整梗概覆盖文本。支持 JSON 或纯文本")


class RewriteBeatSheetInput(BaseModel):
    overwrite_content: str = Field(description="完整节拍表覆盖文本。支持 JSON 或纯文本")


class RewriteOutlineInput(BaseModel):
    overwrite_content: str = Field(description="首批或完整大纲覆盖文本。优先使用 Outline Markup（@title/@summary/##/###）。大纲较长时建议每批约 10 个场景，以保证每个场景的规划质量并降低超长工具调用截断风险；首批调用本工具，剩余场景调用 patch_outline(search_text=\"\", replace_text=后续正文) 追加。10 个只是软建议，应按单场信息密度灵活调整，绝不能为满足数量而压缩场景内容或降低质量。必须只包含最终可保存的大纲正文，不得混入解释、确认话术、提示词、代码围栏或系统指令")


class PatchSynopsisInput(BaseModel):
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）。传入空字符串可将 replace_text 追加到文件末尾")
    replace_text: str = Field(description="修改后的新文本片段")


class PatchBeatSheetInput(BaseModel):
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）。传入空字符串可将 replace_text 追加到文件末尾")
    replace_text: str = Field(description="修改后的新文本片段")


class PatchOutlineInput(BaseModel):
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文中的连续文字，建议提取完整的1~3句话）。传入空字符串会将 replace_text 追加到大纲末尾；长大纲首批 rewrite_outline 后，后续批次应使用此追加能力")
    replace_text: str = Field(description="修改或追加的新大纲正文。分批追加时保持每个场景信息完整，不能为缩短调用而牺牲质量")


@tool(args_schema=RewriteSynopsisInput)
def rewrite_synopsis(overwrite_content: str) -> str:
    """覆盖故事梗概。"""
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写梗概失败：overwrite_content 为空。"

    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    with open(synopsis_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存故事梗概。"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(overwrite_content: str) -> str:
    """覆盖节拍表。"""
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写节拍表失败：overwrite_content 为空。"

    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    with open(beats_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存节拍表。"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(overwrite_content: str) -> str:
    """覆盖故事大纲。"""
    user_id, project_name = ToolExecutionContext.get_context()

    content = _strip_markdown_fence((overwrite_content or "").strip())
    if not content:
        return "重写大纲失败：overwrite_content 为空。"

    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    with open(outline_path, "w", encoding="utf-8") as f:
        f.write(content)

    return "已成功重写并保存故事大纲。"


@tool(args_schema=PatchSynopsisInput)
def patch_synopsis(search_text: str, replace_text: str) -> str:
    """局部修改梗概。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), "梗概.txt")
    return _apply_patch(synopsis_path, search_text, replace_text, file_label="梗概.txt")


@tool(args_schema=PatchBeatSheetInput)
def patch_beat_sheet(search_text: str, replace_text: str) -> str:
    """局部修改节拍表。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    return _apply_patch(beats_path, search_text, replace_text, file_label="节拍表.txt")


@tool(args_schema=PatchOutlineInput)
def patch_outline(search_text: str, replace_text: str) -> str:
    """局部修改大纲。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    user_id, project_name = ToolExecutionContext.get_context()
    outline_path = os.path.join(get_project_path(user_id, project_name), "大纲.txt")
    return _apply_patch(outline_path, search_text, replace_text, file_label="大纲.txt")
