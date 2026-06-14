"""
agents/routes - 路由子模块

将原 routes_agents.py 按业务领域拆分为多个模块：
- chat.py: 聊天/会话历史 API
- characters.py: 角色设定 API
- production.py: 剧本生成 API（单段/多段续写）
- critic.py: Critic 评审 API
 - style.py: 风格分析 API
- structure.py: 剧情结构 API（Synopsis, Beat Sheet, Outline AI）
- lorebook.py: Lorebook / Worldview API
- muse.py: 创意助手 API
- outline.py: 大纲管理 API
- runtime.py: Agent 运行态 API
 - prompt_preferences.py: Agent 提示词偏好 API
 - skill_packs.py: Agent Skills 管理 API
"""

from fastapi import APIRouter

# 创建聚合路由器
agents_router = APIRouter()

# 导入并包含各子路由
from .chat import chat_router
from .characters import characters_router
from .production import production_router
from .style import style_router
from .structure import structure_router
from .lorebook import lorebook_router
from .muse import muse_router
from .outline import outline_router
from .runtime import runtime_router
from .prompt_preferences import prompt_preferences_router
from .skill_packs import skill_packs_router

agents_router.include_router(chat_router)
agents_router.include_router(characters_router)
agents_router.include_router(production_router)
agents_router.include_router(style_router)
agents_router.include_router(structure_router)
agents_router.include_router(lorebook_router)
agents_router.include_router(muse_router)
agents_router.include_router(outline_router)
agents_router.include_router(runtime_router)
agents_router.include_router(prompt_preferences_router)
agents_router.include_router(skill_packs_router)
