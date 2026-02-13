"""
Agent Tools - 统一的工具定义模块

使用 LangChain @tool 装饰器定义所有 Agent 可调用的工具。
工具通过 model.bind_tools() 绑定到 LLM，让模型自主决策何时调用。

设计原则：
1. 工具只负责执行，不负责判断是否应该调用
2. 调用前的确认逻辑由 Agent 的 chat 方法处理
3. 复用现有的生成方法，避免代码冗余
"""

from __future__ import annotations

import json
import os
from typing import Optional, Iterator, List, Dict, Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.request_context import current_user_id, current_project_name
from core.utils import (
    ensure_project_characters_directory,
    get_project_worldview_path,
    ensure_project_worldview_and_character_settings,
    get_project_path
)


# ==================== Tool Input Schemas ====================

class RewriteWorldviewInput(BaseModel):
    """重写世界观的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改世界观")


class RewriteAllCharactersInput(BaseModel):
    """重写所有角色的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改角色设定")


class UpdateCharacterInput(BaseModel):
    """修改单个角色的输入参数"""
    character_name: str = Field(description="要修改的角色名称")
    guidance: str = Field(description="用户的修改指导，描述希望如何修改该角色")


class RewriteSynopsisInput(BaseModel):
    """重写梗概的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改梗概")


class RewriteBeatSheetInput(BaseModel):
    """重写节拍表的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改节拍表")


class RewriteOutlineInput(BaseModel):
    """重写大纲的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改大纲")


class RewriteScriptInput(BaseModel):
    """重写剧本的输入参数"""
    guidance: str = Field(description="用户的修改指导，描述希望如何修改剧本")


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


# ==================== Lorebook Tools ====================

@tool(args_schema=RewriteWorldviewInput)
def rewrite_worldview(guidance: str) -> str:
    """
    根据用户指导重写世界观设定。
    
    调用此工具前，必须先向用户确认修改方向。
    此工具会直接覆盖保存世界观文件。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    import logging
    logger = logging.getLogger("agent_tools")
    logger.info(f"[TOOL CALL] rewrite_worldview 被调用, guidance={guidance[:100]}...")
    print(f"[DEBUG] rewrite_worldview 工具被调用: guidance={guidance[:100]}...")
    
    from agents.agent_lorebook import WorldviewAgent
    
    user_id, project_name = ToolExecutionContext.get_context()
    logger.info(f"[TOOL CALL] 上下文: user_id={user_id}, project_name={project_name}")
    print(f"[DEBUG] 上下文: user_id={user_id}, project_name={project_name}")
    
    agent = WorldviewAgent(int(user_id))
    result = agent._overwrite_worldview_tool(user_id, project_name, guidance)
    
    logger.info(f"[TOOL CALL] rewrite_worldview 执行完成, result={result[:200]}...")
    print(f"[DEBUG] rewrite_worldview 执行完成: {result[:200]}...")
    
    return result


@tool(args_schema=RewriteAllCharactersInput)
def rewrite_all_characters(guidance: str) -> str:
    """
    根据用户指导重新生成所有角色设定。
    
    调用此工具前，必须先向用户确认修改方向。
    此工具会删除现有角色（保留旁白）并重新生成。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    from agents.agent_lorebook import WorldviewAgent
    
    user_id, project_name = ToolExecutionContext.get_context()
    agent = WorldviewAgent(int(user_id))
    return agent._overwrite_characters_tool(user_id, project_name, guidance)


@tool(args_schema=UpdateCharacterInput)
def update_character(character_name: str, guidance: str) -> str:
    """
    修改特定角色的设定，不影响其他角色。
    
    调用此工具前，必须先向用户确认修改方向。
    
    Args:
        character_name: 要修改的角色名称
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from agents.agent_utils import load_prompt
    from llm.llm_mgr import LLM_Manager
    
    user_id, project_name = ToolExecutionContext.get_context()
    
    # 加载角色信息
    characters_path = ensure_project_characters_directory(user_id, project_name)
    bind_path = os.path.join(characters_path, 'chr.bind')
    
    if not os.path.exists(bind_path):
        return f"未找到角色绑定文件，无法修改角色 '{character_name}'。"
    
    with open(bind_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f) or {}
    
    # 查找角色ID
    char_id = None
    for cid, name in mapping.items():
        if name == character_name:
            char_id = cid
            break
    
    if char_id is None:
        return f"未找到名为 '{character_name}' 的角色。"
    
    # 读取现有角色设定
    char_file = os.path.join(characters_path, f"{char_id}.txt")
    existing_content = ""
    if os.path.exists(char_file):
        with open(char_file, 'r', encoding='utf-8') as f:
            existing_content = f.read()
    
    # 加载世界观作为背景
    ensure_project_worldview_and_character_settings(user_id, project_name)
    worldview_path = get_project_worldview_path(user_id, project_name)
    worldview = ""
    if os.path.exists(worldview_path):
        with open(worldview_path, 'r', encoding='utf-8') as f:
            worldview = f.read() or ""
    
    # 使用 LLM 修改角色
    llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_lorebook", streaming=False)
    
    system_prompt = f"""你是一个角色设定专家。请根据用户的修改要求，更新以下角色的设定。

世界观背景：
{worldview[:2000] if worldview else '（未提供）'}

当前角色设定：
{existing_content}

输出格式：
第一行是角色名称
空一行
然后是角色的完整设定（包含用户要求的修改）

注意：保留原有设定中合理的部分，只修改用户明确要求修改的内容。"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请修改角色 '{character_name}'：{guidance}")
    ]
    
    response = llm.invoke(messages)
    new_content = (response.content or "").strip()
    
    if not new_content:
        return f"修改角色 '{character_name}' 失败：模型未返回内容。"
    
    # 解析新名称（如果有变化）
    lines = new_content.split('\n', 2)
    new_name = lines[0].strip() if lines else character_name
    new_body = lines[2].strip() if len(lines) >= 3 else new_content
    
    # 保存修改
    with open(char_file, 'w', encoding='utf-8') as f:
        f.write(f"{new_name}\n\n{new_body}")
    
    # 更新映射（如果名称变了）
    if new_name != character_name:
        mapping[char_id] = new_name
        with open(bind_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    return f"已成功修改角色 '{character_name}' 的设定。"


# ==================== Showrunner Tools ====================

@tool(args_schema=RewriteSynopsisInput)
def rewrite_synopsis(guidance: str) -> str:
    """
    根据用户指导重写故事梗概。
    
    调用此工具前，必须先向用户确认修改方向。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    import logging
    logger = logging.getLogger("agent_tools")
    logger.info(f"[TOOL CALL] rewrite_synopsis 被调用, guidance={guidance[:100]}...")
    print(f"[DEBUG] rewrite_synopsis 工具被调用: guidance={guidance[:100]}...")
    
    from agents import ShowrunnerAgent
    from agents.routes.schemas import _load_worldview_and_roles
    
    user_id, project_name = ToolExecutionContext.get_context()
    logger.info(f"[TOOL CALL] 上下文: user_id={user_id}, project_name={project_name}")
    print(f"[DEBUG] 上下文: user_id={user_id}, project_name={project_name}")
    
    # 加载现有梗概
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    print(f"[DEBUG] synopsis_path={synopsis_path}")
    
    existing_synopsis = ""
    if os.path.exists(synopsis_path):
        with open(synopsis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            existing_synopsis = json.dumps(data, ensure_ascii=False, indent=2)
    
    info = _load_worldview_and_roles(user_id, project_name)
    showrunner = ShowrunnerAgent(user_id)
    
    # 组合 guidance 包含现有梗概信息
    full_guidance = f"现有梗概：\n{existing_synopsis}\n\n用户要求：{guidance}" if existing_synopsis else guidance
    
    try:
        result = showrunner.generate_synopsis(
            logline=full_guidance,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance
        )
        
        # 保存结果
        with open(synopsis_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"[DEBUG] rewrite_synopsis 保存成功到 {synopsis_path}")
        return "已成功重写并保存故事梗概。"
    except Exception as e:
        print(f"[DEBUG] rewrite_synopsis 失败: {e}")
        return f"重写梗概失败：{e}"


@tool(args_schema=RewriteBeatSheetInput)
def rewrite_beat_sheet(guidance: str) -> str:
    """
    根据用户指导重写节拍表。
    
    调用此工具前，必须先向用户确认修改方向。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    from agents import ShowrunnerAgent
    from agents.routes.schemas import _load_worldview_and_roles
    
    user_id, project_name = ToolExecutionContext.get_context()
    
    # 加载现有梗概和节拍表
    synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    
    synopsis = ""
    if os.path.exists(synopsis_path):
        with open(synopsis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            synopsis = json.dumps(data, ensure_ascii=False)
    
    info = _load_worldview_and_roles(user_id, project_name)
    showrunner = ShowrunnerAgent(user_id)
    
    try:
        result = showrunner.generate_beat_sheet(
            synopsis=synopsis,
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance
        )
        
        with open(beats_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return "已成功重写并保存节拍表。"
    except Exception as e:
        return f"重写节拍表失败：{e}"


@tool(args_schema=RewriteOutlineInput)
def rewrite_outline(guidance: str) -> str:
    """
    根据用户指导重写故事大纲。
    
    调用此工具前，必须先向用户确认修改方向。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        执行结果消息
    """
    from agents import ShowrunnerAgent
    from agents.routes.schemas import _load_worldview_and_roles, _save_project_outline
    
    user_id, project_name = ToolExecutionContext.get_context()
    
    # 加载现有节拍表
    beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
    beat_sheet = ""
    if os.path.exists(beats_path):
        with open(beats_path, 'r', encoding='utf-8') as f:
            beat_sheet = json.load(f)
    
    info = _load_worldview_and_roles(user_id, project_name)
    showrunner = ShowrunnerAgent(user_id)
    
    try:
        result = showrunner.generate_outline(
            context="",
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance,
            beat_sheet=beat_sheet
        )
        
        _save_project_outline(user_id, project_name, result)
        return "已成功重写并保存故事大纲。"
    except Exception as e:
        return f"重写大纲失败：{e}"


# ==================== Scriptwriter Tools ====================

@tool(args_schema=RewriteScriptInput)
def rewrite_script(guidance: str) -> str:
    """
    根据用户指导重写当前剧本场景。
    
    调用此工具前，必须先向用户确认修改方向。
    
    Args:
        guidance: 用户的修改指导
    
    Returns:
        生成的剧本内容（.arc 格式）
    """
    from agents import ScriptwriterAgent
    from agents.routes.schemas import _load_worldview_and_roles
    
    user_id, project_name = ToolExecutionContext.get_context()
    info = _load_worldview_and_roles(user_id, project_name)
    
    writer = ScriptwriterAgent(user_id)
    
    try:
        arc_script, thought = writer.write_script(
            context="",
            worldview=info['worldview'],
            roles=info['roles'],
            guidance=guidance
        )
        return arc_script
    except Exception as e:
        return f"重写剧本失败：{e}"


# ==================== Tool Registry ====================

# 按 Agent 分组的工具列表
LOREBOOK_TOOLS = [rewrite_worldview, rewrite_all_characters, update_character]
SHOWRUNNER_TOOLS = [rewrite_synopsis, rewrite_beat_sheet, rewrite_outline]
SCRIPTWRITER_TOOLS = [rewrite_script]

# 所有工具
ALL_TOOLS = LOREBOOK_TOOLS + SHOWRUNNER_TOOLS + SCRIPTWRITER_TOOLS

# 工具名称到工具对象的映射
TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def get_tools_for_agent(agent_id: str) -> list:
    """根据 Agent ID 返回对应的工具列表"""
    tool_map = {
        "agent_lorebook": LOREBOOK_TOOLS,
        "agent_showrunner": SHOWRUNNER_TOOLS,
        "agent_scriptwriter": SCRIPTWRITER_TOOLS,
    }
    return tool_map.get(agent_id, [])
