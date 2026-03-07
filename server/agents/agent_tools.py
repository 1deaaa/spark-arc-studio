"""
Agent Tools - 统一的工具定义模块

使用 LangChain @tool 装饰器定义所有 Agent 可调用的工具。
工具通过 model.bind_tools() 绑定到 LLM，让模型自主决策何时调用。
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import current_user_id, current_project_name
from core.utils import ensure_project_characters_directory, get_project_path
from story.outline_parser import parse_beat_sheet_markup, parse_outline_markup


# ==================== Tool Input Schemas ====================

class RewriteWorldviewInput(BaseModel):
    """重写世界观的输入参数"""
    overwrite_content: str = Field(description="完整的世界观覆盖文本。调用后将直接写入并覆盖世界观文件")


class RewriteAllCharactersInput(BaseModel):
    """重写所有角色的输入参数"""
    overwrite_content: str = Field(description="完整的角色覆盖文本。推荐 JSON: {\"characters\":[{\"name\":\"角色名\",\"content\":\"角色设定\"}]}；或纯文本格式：角色名+空行+角色内容，多个角色用 --- 分隔")


class UpdateCharacterInput(BaseModel):
    """修改单个角色的输入参数"""
    character_name: str = Field(description="要修改的角色名称")
    overwrite_content: str = Field(description="该角色的完整覆盖文本。调用后将直接覆盖该角色内容")


class RewriteSynopsisInput(BaseModel):
    """重写梗概的输入参数"""
    overwrite_content: str = Field(description="完整梗概覆盖文本。支持 JSON 或纯文本")


class RewriteBeatSheetInput(BaseModel):
    """重写节拍表的输入参数"""
    overwrite_content: str = Field(description="完整节拍表覆盖文本。支持 JSON 或纯文本")


class RewriteOutlineInput(BaseModel):
    """重写大纲的输入参数"""
    overwrite_content: str = Field(description="完整大纲覆盖文本。优先使用 Outline Markup（@title/@summary/##/###）。必须只包含最终可保存的大纲正文，不得混入解释、确认话术、提示词、代码围栏或系统指令")


class RewriteScriptInput(BaseModel):
    """重写剧本的输入参数"""
    overwrite_content: str = Field(description="完整剧本覆盖文本（.arc）")


class CaptureInspirationInput(BaseModel):
    """捕获并扩写灵感的输入参数"""
    raw_input: str = Field(description="需要扩写并保存的灵感种子")
    style: str | None = Field(default=None, description="可选风格，如治愈、悬疑")
    genres: list[str] | None = Field(default=None, description="可选题材标签列表")
    tones: list[str] | None = Field(default=None, description="可选基调标签列表")
    worldviews: list[str] | None = Field(default=None, description="可选世界观标签列表")
    length_hint: str | None = Field(default=None, description="可选篇幅建议，如短篇、中篇、长篇")

class PatchWorldviewInput(BaseModel):
    """局部修改世界观的输入参数"""
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文中的连续文字，建议提取完整的1~3句话，不要太短以免误替换）")
    replace_text: str = Field(description="修改后的新文本片段")

class PatchSynopsisInput(BaseModel):
    """局部修改梗概的输入参数"""
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")

class PatchBeatSheetInput(BaseModel):
    """局部修改节拍表的输入参数"""
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")

class PatchScriptInput(BaseModel):
    """局部修改剧本的输入参数"""
    search_text: str = Field(description="需要被替换的剧本片段（必须精确匹配原文）")
    replace_text: str = Field(description="修改后的新文本片段")

# ==================== Tool Execution Context ====================

class ToolExecutionContext:
    """
    工具执行上下文，封装 user_id 和 project_name。
    工具函数通过 current_user_id / current_project_name 获取上下文。
    """

    @staticmethod
    def get_context() -> tuple[str, str]:
        """获取当前用户ID和项目名"""
        user_id = current_user_id.get()
        project_name = current_project_name.get()
        if not user_id or not project_name:
            raise RuntimeError("缺少用户或项目上下文，无法执行工具")
        return str(user_id), project_name


def _parse_json_or_text(content: str) -> Any:
    text = (content or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return {"content": text}


def _strip_markdown_fence(content: str) -> str:
    text = (content or "").strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _coerce_synopsis_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None
    if isinstance(parsed, dict) and any(key in parsed for key in ("synopsis_text", "title", "themes", "pacing_guide", "logline")):
        return parsed
    return {
        "title": "未命名故事",
        "logline": "",
        "synopsis_text": clean_content,
        "themes": [],
        "pacing_guide": "",
    }


def _coerce_beat_sheet_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None
    if isinstance(parsed, dict) and ("beats" in parsed or "global_emotional_arc" in parsed):
        return parsed
    return parse_beat_sheet_markup(clean_content)


def _coerce_outline_payload(content: str) -> dict | None:
    clean_content = _strip_markdown_fence(content)
    parsed = _parse_json_or_text(clean_content)
    if parsed is None:
        return None

    if isinstance(parsed, dict) and ("nodes" in parsed or "summary" in parsed or "mainTheme" in parsed):
        outline = parsed
    else:
        source_text = parsed.get("content", clean_content) if isinstance(parsed, dict) else clean_content
        outline = parse_outline_markup(source_text)

    outline.setdefault("title", "未命名大纲")
    outline.setdefault("summary", "")
    outline.setdefault("mainTheme", "")
    outline.setdefault("nodes", [])
    outline["totalChapters"] = len(outline.get("nodes", []))
    outline["estimatedScenes"] = sum(len(ch.get("children", [])) for ch in outline.get("nodes", []))
    return outline


def _build_muse_tags(style: str | None, genres: list[str] | None, tones: list[str] | None, worldviews: list[str] | None, length_hint: str | None = None) -> dict:
    tags = {
        "styles": [style] if style else [],
        "genres": genres or [],
        "tones": tones or [],
        "worldviews": worldviews or [],
        "lengthHint": [length_hint] if length_hint else [],
    }
    return tags


# ==================== Lorebook Tools ====================

@tool(args_schema=CaptureInspirationInput)
def capture_inspiration(raw_input: str, style: str | None = None, genres: list[str] | None = None, tones: list[str] | None = None, worldviews: list[str] | None = None, length_hint: str | None = None) -> str:
    """
    扩写灵感并保存到灵感工坊。
    """
    from agents.setup_agents import MuseAgent
    from agents.agent_utils import collect_text_output

    user_id = current_user_id.get()
    if not user_id:
        return "捕获灵感失败：缺少用户上下文。"
    agent = MuseAgent(user_id)
    context = agent.build_context(
        operation="expand_inspiration",
        raw_input=raw_input,
        style=style,
        genres=genres,
        tones=tones,
        worldviews=worldviews,
        length_hint=length_hint,
    )
    result = collect_text_output(agent.execute(context))
    if not result:
        return "捕获灵感失败：生成结果为空。"

    save_result = agent.write_result(
        result,
        user_id=user_id,
        source=raw_input,
        tags=_build_muse_tags(style, genres, tones, worldviews, length_hint),
        origin="ui",
    )
    if isinstance(save_result, dict) and not save_result.get("success", False):
        return f"捕获灵感失败：{save_result.get('error') or save_result}"
    return f"已成功捕获并扩写灵感。\n\n{result}"

@tool(args_schema=RewriteWorldviewInput)
def rewrite_worldview(overwrite_content: str) -> str:
    """
    使用 overwrite_content 中的完整文本覆盖世界观设定。
    """
    import logging

    logger = logging.getLogger("agent_tools")
    logger.info(f"[TOOL CALL] rewrite_worldview 被调用, overwrite_content={overwrite_content[:100]}...")

    from agents.agent_lorebook import WorldviewAgent

    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    agent.write_result(
        overwrite_content,
        operation="overwrite_worldview",
        user_id=user_id,
        project_name=project_name,
    )
    return "已使用工具参数中的完整文本覆盖世界观。"


@tool(args_schema=RewriteAllCharactersInput)
def rewrite_all_characters(overwrite_content: str) -> str:
    """
    使用 overwrite_content 中的完整文本覆盖所有角色设定。
    """
    from agents.agent_lorebook import WorldviewAgent

    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    return agent.write_result(
        overwrite_content,
        operation="overwrite_characters",
        user_id=user_id,
        project_name=project_name,
        overwrite_content=overwrite_content,
    )


@tool(args_schema=UpdateCharacterInput)
def update_character(character_name: str, overwrite_content: str) -> str:
    """
    使用 overwrite_content 直接覆盖特定角色设定，不影响其他角色。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    characters_path = ensure_project_characters_directory(user_id, project_name)
    bind_path = os.path.join(characters_path, 'chr.bind')

    if not os.path.exists(bind_path):
        return f"未找到角色绑定文件，无法修改角色 '{character_name}'。"

    with open(bind_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f) or {}

    char_id = None
    for cid, name in mapping.items():
        if name == character_name:
            char_id = cid
            break

    if char_id is None:
        return f"未找到名为 '{character_name}' 的角色。"

    content = (overwrite_content or "").strip()
    if not content:
        return f"修改角色 '{character_name}' 失败：overwrite_content 为空。"

    char_file = os.path.join(characters_path, f"{char_id}.txt")
    with open(char_file, 'w', encoding='utf-8') as f:
        f.write(f"{character_name}\n\n{content}")

    return f"已成功修改角色 '{character_name}' 的设定。"


@tool(args_schema=PatchWorldviewInput)
def patch_worldview(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段进行局部修改（不会重写全文），适用于对世界观的小规模调整或纠错。"""
    user_id, project_name = ToolExecutionContext.get_context()
    worldview_path = os.path.join(get_project_path(user_id, project_name), '世界观.txt')
    if not os.path.exists(worldview_path):
        return "局部修改失败：世界观文件不存在。"
    
    with open(worldview_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if search_text not in content:
        return f"局部修改失败：在原文中未找到与 search_text 完全一致的连续片段，请检查是否包含多余空格或换行。"
        
    new_content = content.replace(search_text, replace_text, 1)
    with open(worldview_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    return "已成功局部更新世界观设定。"


# ==================== Showrunner Tools ====================

@tool(args_schema=RewriteSynopsisInput)
def rewrite_synopsis(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事梗概。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写梗概失败：overwrite_content 为空。"

    data = _coerce_synopsis_payload(content)
    if data is None:
        return "重写梗概失败：overwrite_content 为空。"

    agent = ShowrunnerAgent(user_id)
    agent.write_result(data, operation="synopsis", user_id=user_id, project_name=project_name)

    return "已成功重写并保存故事梗概。"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖节拍表。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写节拍表失败：overwrite_content 为空。"

    data = _coerce_beat_sheet_payload(content)
    if data is None:
        return "重写节拍表失败：overwrite_content 为空。"

    agent = ShowrunnerAgent(user_id)
    agent.write_result(data, operation="beat_sheet", user_id=user_id, project_name=project_name)

    return "已成功重写并保存节拍表。"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事大纲，内容必须是最终可保存的大纲正文。
    """
    from agents.agent_showrunner import ShowrunnerAgent

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写大纲失败：overwrite_content 为空。"

    outline = _coerce_outline_payload(content)
    if outline is None:
        return "重写大纲失败：overwrite_content 为空。"

    agent = ShowrunnerAgent(user_id)
    agent.write_result(outline, operation="outline", user_id=user_id, project_name=project_name, save_to_project=True, save_to_history=False)
    return "已成功重写并保存故事大纲。"


@tool(args_schema=PatchSynopsisInput)
def patch_synopsis(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对梗概进行局部修改，适用于对大纲设定文件的部分语句进行增删改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    if not os.path.exists(synopsis_path):
        return "局部修改失败：故事梗概文件不存在。"
        
    with open(synopsis_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if search_text not in content:
        return "局部修改失败：在原文中未找到完全匹配的 search_text。"
        
    new_content = content.replace(search_text, replace_text, 1)
    # 尝试验证 JSON 是否还是合法的
    try:
        json.loads(new_content)
    except Exception as e:
        return f"局部修改失败：替换后破坏了原有的 JSON 格式 ({e})，请检查 replace_text 的引号和括号是否闭合。"
        
    with open(synopsis_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    return "已成功局部更新故事梗概。"


@tool(args_schema=PatchBeatSheetInput)
def patch_beat_sheet(search_text: str, replace_text: str) -> str:
    """通过提供原文片段和新文本片段对节拍表进行局部修改。"""
    user_id, project_name = ToolExecutionContext.get_context()
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    if not os.path.exists(beats_path):
        return "局部修改失败：节拍表文件不存在。"
        
    with open(beats_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if search_text not in content:
        return "局部修改失败：在原文中未找到完全匹配的 search_text。"
        
    new_content = content.replace(search_text, replace_text, 1)
    try:
        json.loads(new_content)
    except Exception as e:
        return f"局部修改失败：替换后破坏了原有的 JSON 格式 ({e})。"
        
    with open(beats_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    return "已成功局部更新节拍表。"


# ==================== Scriptwriter Tools ====================

@tool(args_schema=RewriteScriptInput)
def rewrite_script(overwrite_content: str) -> str:
    """
    直接返回 overwrite_content 作为剧本覆盖内容。
    """
    content = (overwrite_content or "").strip()
    if not content:
        return "重写剧本失败：overwrite_content 为空。"
@tool(args_schema=PatchScriptInput)
def patch_script(search_text: str, replace_text: str) -> str:
    """找出剧本中的 search_text 并且替换为 replace_text。由于剧本分散在多个文件中，该工具将遍历所有文件以寻找精确匹配。"""
    user_id, project_name = ToolExecutionContext.get_context()
    from core.utils import get_project_stories_path
    
    stories_path = get_project_stories_path(user_id, project_name)
    if not os.path.exists(stories_path):
        return "局部修改剧本失败：stories 目录不存在。"
        
    for filename in os.listdir(stories_path):
        if not filename.endswith('.arc'):
            continue
            
        file_path = os.path.join(stories_path, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if search_text in content:
            new_content = content.replace(search_text, replace_text, 1)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return f"已成功局部更新剧本文本（修改发生于文件: {filename}）。"
            
    return "局部修改剧本失败：在当前项目下的所有剧本文件中，均未找到完全匹配的 search_text片段，请检查是否包含多余空格或换行。"

# ==================== Tool Registry ====================

MUSE_TOOLS = [capture_inspiration]
LOREBOOK_TOOLS = [rewrite_worldview, rewrite_all_characters, update_character, patch_worldview]
SHOWRUNNER_TOOLS = [rewrite_synopsis, rewrite_beat_sheet, rewrite_outline, patch_synopsis, patch_beat_sheet]
SCRIPTWRITER_TOOLS = [rewrite_script, patch_script]

ALL_TOOLS = MUSE_TOOLS + LOREBOOK_TOOLS + SHOWRUNNER_TOOLS + SCRIPTWRITER_TOOLS
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_tools_for_agent(agent_id: str) -> list:
    """根据 Agent ID 返回对应的工具列表"""
    tool_map = {
        "agent_muse": MUSE_TOOLS,
        "agent_lorebook": LOREBOOK_TOOLS,
        "agent_showrunner": SHOWRUNNER_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_TOOLS,
    }
    return tool_map.get(agent_id, [])
