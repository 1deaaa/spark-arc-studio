from __future__ import annotations

import json
import os

from langchain.tools import tool
from pydantic import BaseModel, Field

from core.utils import ensure_project_characters_directory, get_project_path

from .common import ToolExecutionContext, _apply_patch


class RewriteWorldviewInput(BaseModel):
    overwrite_content: str = Field(description="完整的世界观覆盖文本。调用后将直接写入并覆盖世界观文件")


class RewriteAllCharactersInput(BaseModel):
    overwrite_content: str = Field(description='完整的角色覆盖文本。推荐 XML: <character><name>角色名</name><content>角色设定</content></character>；也支持 JSON: {"characters":[{"name":"角色名","content":"角色设定"}]}；或兼容旧的纯文本格式：角色名+空行+角色内容，多个角色用 --- 分隔')


class UpdateCharacterInput(BaseModel):
    character_name: str = Field(description="要修改的角色名称")
    overwrite_content: str = Field(description="该角色的完整覆盖文本。调用后将直接覆盖该角色内容")


class PatchWorldviewInput(BaseModel):
    search_text: str = Field(description="需要被替换的原文片段（必须精确匹配原文中的连续文字，建议提取完整的1~3句话，不要太短以免误替换）。传入空字符串可将 replace_text 追加到文件末尾")
    replace_text: str = Field(description="修改后的新文本片段")


@tool(args_schema=RewriteWorldviewInput)
def rewrite_worldview(overwrite_content: str) -> str:
    """覆盖世界观全文。"""
    import logging

    from agents.agent_lorebook import WorldviewAgent

    logger = logging.getLogger("agent_tools")
    logger.info(
        f"[TOOL CALL] rewrite_worldview 被调用, overwrite_content={overwrite_content[:100]}..."
    )

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
    """覆盖全部角色设定。"""
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
    """覆盖单个角色设定。"""
    from story.project_files import lookup_character_id_by_name

    user_id, project_name = ToolExecutionContext.get_context()
    characters_path = ensure_project_characters_directory(user_id, project_name)

    # 复用统一工具，避免重复实现 chr.bind 解析与按名字反查
    char_id = lookup_character_id_by_name(user_id, project_name, character_name)
    if not char_id:
        return f"未找到名为 '{character_name}' 的角色。"

    content = (overwrite_content or "").strip()
    if not content:
        return f"修改角色 '{character_name}' 失败：overwrite_content 为空。"

    char_file = os.path.join(characters_path, f"{char_id}.txt")
    with open(char_file, "w", encoding="utf-8") as f:
        f.write(f"{character_name}\n\n{content}")

    # 同步更新 chr.bind 中的角色名（使用 dict 格式）
    bind_path = os.path.join(characters_path, "chr.bind")
    if os.path.exists(bind_path):
        try:
            with open(bind_path, "r", encoding="utf-8") as f:
                bind_data = json.load(f) or {}
            bind_data[str(char_id)] = character_name
            with open(bind_path, "w", encoding="utf-8") as f:
                json.dump(bind_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return f"已成功修改角色 '{character_name}' 的设定。"


@tool(args_schema=PatchWorldviewInput)
def patch_worldview(search_text: str, replace_text: str) -> str:
    """局部修改世界观文本。search_text 传空字符串可将 replace_text 追加到文件末尾。"""
    user_id, project_name = ToolExecutionContext.get_context()
    worldview_path = os.path.join(get_project_path(user_id, project_name), "世界观.txt")
    return _apply_patch(worldview_path, search_text, replace_text, file_label="世界观.txt")
