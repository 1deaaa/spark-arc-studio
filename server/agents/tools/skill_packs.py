from __future__ import annotations

import json

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


class SearchSkillsInput(BaseModel):
    query: str = Field(default="", description="要检索的写作 Skill 关键词，可为空以列出推荐项。")
    limit: int = Field(default=8, ge=1, le=20, description="最多返回多少个 Skill。")


class ReadSkillInput(BaseModel):
    skill_id: str = Field(description="要读取的 Skill ID 或 normalized name。")


class ReadSkillReferenceInput(BaseModel):
    skill_id: str = Field(description="Skill ID 或 normalized name。")
    path: str = Field(description="Skill 内 references/templates/resources 下的文本参考文件路径。")


@tool(args_schema=SearchSkillsInput)
def search_skills(query: str = "", limit: int = 8) -> str:
    """搜索已安装的文本型 Agent Skill。先搜索再读取，不要猜测 Skill 内容。"""
    user_id, _project_name = ToolExecutionContext.get_context()
    from agents.skill_packs import search_skills as _search_skills

    results = _search_skills(user_id, query=query, limit=limit)
    if not results:
        return "没有找到匹配的 Skill。"
    payload = [
        {
            "skill_id": item.get("skill_id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "domain": item.get("domain"),
            "compatibility_status": item.get("compatibility_status"),
        }
        for item in results
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool(args_schema=ReadSkillInput)
def read_skill(skill_id: str) -> str:
    """按需读取一个 Skill 的质量适配视图。Skill 不改变系统格式协议，只提供质量方法参考。"""
    user_id, _project_name = ToolExecutionContext.get_context()
    from agents.skill_packs import read_skill as _read_skill

    return _read_skill(user_id, skill_id)


@tool(args_schema=ReadSkillReferenceInput)
def read_skill_reference(skill_id: str, path: str) -> str:
    """读取 Skill 的文本参考文件。只允许读取 references/templates/resources 等安全文本资源。"""
    user_id, _project_name = ToolExecutionContext.get_context()
    from agents.skill_packs import read_skill_reference as _read_skill_reference

    return _read_skill_reference(user_id, skill_id, path)
