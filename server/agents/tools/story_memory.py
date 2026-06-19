from __future__ import annotations

from typing import Literal

from langchain.tools import tool
from pydantic import BaseModel, Field

from .common import ToolExecutionContext


class StoryMemoryToolInput(BaseModel):
    """StoryMemory 只读工具入参。"""

    action: Literal["status", "query", "scene_task_pack"] = Field(
        description="操作类型：status=查看已吸收的故事状态；query=按问题查询角色/关系/场景状态；scene_task_pack=生成当前场景写作状态包。"
    )
    question: str | None = Field(default=None, description="query 时填写要核对的问题；scene_task_pack 时可填写当前场景目标。")
    scene_title: str | None = Field(default=None, description="scene_task_pack 时填写当前场景名。")
    characters: list[str] | None = Field(default=None, description="scene_task_pack 时填写当前场景登场角色名列表。")


@tool(args_schema=StoryMemoryToolInput)
def story_memory_tool(
    action: Literal["status", "query", "scene_task_pack"],
    question: str | None = None,
    scene_title: str | None = None,
    characters: list[str] | None = None,
) -> str:
    """读取项目的实时故事记忆。

    本工具只读，不触发生成、不修改文件。它读取每次场景保存后自动吸收的轻量状态，
    适合在写作前核对人物关系、最近出场、伏笔线索和相关场景摘要。
    """
    from agents.story_memory import StoryMemoryFacade

    user_id, project_name = ToolExecutionContext.get_context()
    facade = StoryMemoryFacade(user_id=user_id, project_name=project_name)

    try:
        if action == "status":
            return facade.format_status()
        if action == "scene_task_pack":
            payload = facade.compose_scene_task_pack(
                scene_title=scene_title or "",
                scene_characters=characters or [],
                guidance=question or "",
            )
            return payload.get("text") or "StoryMemory 尚未整理出可用任务包。"
        return facade.query_text(question or "")
    except Exception as e:
        return f"StoryMemory 查询失败：{e}"

