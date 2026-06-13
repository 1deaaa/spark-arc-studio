"""Agent 提示词质量偏好 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.auth import get_current_user
from agents.prompt_preferences import (
    get_agent_prompt_preferences,
    reset_agent_prompt_preference,
    save_agent_prompt_preference,
)


prompt_preferences_router = APIRouter()


class PromptPreferenceSaveRequest(BaseModel):
    agent_id: str = Field(..., description="Agent 标识，例如 agent_muse")
    content: str = Field(default="", description="质量偏好覆盖内容")
    enabled: bool = Field(default=True, description="是否启用该覆盖")


@prompt_preferences_router.get("/api/agents/prompt-preferences/{agent_id}")
async def get_prompt_preferences(agent_id: str, user: dict = Depends(get_current_user)):
    """读取某个 Agent 的提示词偏好配置。"""
    user_id = str(user["user_id"])
    return get_agent_prompt_preferences(user_id, agent_id)


@prompt_preferences_router.post("/api/agents/prompt-preferences")
async def save_prompt_preferences(
    data: PromptPreferenceSaveRequest,
    user: dict = Depends(get_current_user),
):
    """保存某个 Agent 的提示词偏好覆盖。"""
    user_id = str(user["user_id"])
    return save_agent_prompt_preference(
        user_id=user_id,
        agent_id=data.agent_id,
        content=data.content,
        enabled=data.enabled,
    )


@prompt_preferences_router.delete("/api/agents/prompt-preferences/{agent_id}")
async def reset_prompt_preferences(agent_id: str, user: dict = Depends(get_current_user)):
    """删除某个 Agent 的提示词偏好覆盖。"""
    user_id = str(user["user_id"])
    return reset_agent_prompt_preference(user_id, agent_id)
