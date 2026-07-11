"""Agents Package - 智能代理模块

核心 Agent:
- CriticAgent: 剧本评审（由用户手动触发）
- ShowrunnerAgent: 剧情大纲生成
- ScriptwriterAgent: 剧本编写（包含“衔接模式”）
 - DirectorAgent: 多轮协调中枢（导演）

工具:
- agent_utils: Agent 辅助函数（提示词加载等）
"""

# 核心 Agent
from .agent_critic import CriticAgent
from .agent_showrunner import ShowrunnerAgent
from .agent_scriptwriter import ScriptwriterAgent
from .agent_director import DirectorAgent

# 工具函数
from .agent_utils import (
    load_prompt,
    get_prompts_dir,
    clear_prompt_cache
)

__all__ = [
    # Agents
    'CriticAgent',
    'ShowrunnerAgent',
    'ScriptwriterAgent',
    'DirectorAgent',
    # Utils
    'load_prompt',
    'get_prompts_dir',
    'clear_prompt_cache',
]
