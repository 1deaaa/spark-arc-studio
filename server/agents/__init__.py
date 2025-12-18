"""Agents Package - 智能代理模块

核心 Agent:
- CriticAgent: 剧本评审（由用户手动触发）
- ShowrunnerAgent: 剧情大纲生成
- ScriptwriterAgent: 剧本编写（包含“衔接模式”）
- FeedbackJudgeAgent: 意图分类
- MirrorAgent: 反馈分析

工作流:
- agent_workflow: LangGraph 编排的故事生成流程（不含自动 Critic）

工具:
- agent_utils: Agent 辅助函数（提示词加载等）
"""

# 核心 Agent
from .agent_critic import CriticAgent
from .agent_showrunner import ShowrunnerAgent
from .agent_scriptwriter import ScriptwriterAgent
from .agent_feedbackjudge import FeedbackJudgeAgent
from .agent_mirror import MirrorAgent

# 工作流
from .agent_workflow import (
    run_story_generation_workflow,
    create_story_generation_graph,
    StoryGenerationState
)

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
    'FeedbackJudgeAgent',
    'MirrorAgent',
    # Workflow
    'run_story_generation_workflow',
    'create_story_generation_graph',
    'StoryGenerationState',
    # Utils
    'load_prompt',
    'get_prompts_dir',
    'clear_prompt_cache',
]
