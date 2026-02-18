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
    overwrite_content: str = Field(description="完整大纲覆盖文本。支持 JSON 或纯文本")


class RewriteScriptInput(BaseModel):
    """重写剧本的输入参数"""
    overwrite_content: str = Field(description="完整剧本覆盖文本（.arc）")


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


# ==================== Lorebook Tools ====================

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
    return agent._overwrite_worldview_tool(user_id, project_name, overwrite_content)


@tool(args_schema=RewriteAllCharactersInput)
def rewrite_all_characters(overwrite_content: str) -> str:
    """
    使用 overwrite_content 中的完整文本覆盖所有角色设定。
    """
    from agents.agent_lorebook import WorldviewAgent

    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    return agent._overwrite_characters_tool(user_id, project_name, overwrite_content)


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


# ==================== Showrunner Tools ====================

@tool(args_schema=RewriteSynopsisInput)
def rewrite_synopsis(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事梗概。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写梗概失败：overwrite_content 为空。"

    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    data = _parse_json_or_text(content)
    if data is None:
        return "重写梗概失败：overwrite_content 为空。"

    with open(synopsis_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return "已成功重写并保存故事梗概。"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖节拍表。
    """
    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写节拍表失败：overwrite_content 为空。"

    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    data = _parse_json_or_text(content)
    if data is None:
        return "重写节拍表失败：overwrite_content 为空。"

    with open(beats_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return "已成功重写并保存节拍表。"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(overwrite_content: str) -> str:
    """
    直接使用 overwrite_content 覆盖故事大纲。
    """
    from agents.routes.schemas import _save_project_outline

    user_id, project_name = ToolExecutionContext.get_context()

    content = (overwrite_content or "").strip()
    if not content:
        return "重写大纲失败：overwrite_content 为空。"

    parsed = _parse_json_or_text(content)
    if parsed is None:
        return "重写大纲失败：overwrite_content 为空。"

    if isinstance(parsed, dict):
        outline = parsed
    else:
        outline = {
            "title": "未命名大纲",
            "nodes": [],
            "content": content,
        }

    _save_project_outline(user_id, project_name, outline)
    return "已成功重写并保存故事大纲。"


# ==================== Scriptwriter Tools ====================

@tool(args_schema=RewriteScriptInput)
def rewrite_script(overwrite_content: str) -> str:
    """
    直接返回 overwrite_content 作为剧本覆盖内容。
    """
    content = (overwrite_content or "").strip()
    if not content:
        return "重写剧本失败：overwrite_content 为空。"
    return content


# ==================== Tool Registry ====================

LOREBOOK_TOOLS = [rewrite_worldview, rewrite_all_characters, update_character]
SHOWRUNNER_TOOLS = [rewrite_synopsis, rewrite_beat_sheet, rewrite_outline]
SCRIPTWRITER_TOOLS = [rewrite_script]

ALL_TOOLS = LOREBOOK_TOOLS + SHOWRUNNER_TOOLS + SCRIPTWRITER_TOOLS
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_tools_for_agent(agent_id: str) -> list:
    """根据 Agent ID 返回对应的工具列表"""
    tool_map = {
        "agent_lorebook": LOREBOOK_TOOLS,
        "agent_showrunner": SHOWRUNNER_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_TOOLS,
    }
    return tool_map.get(agent_id, [])
