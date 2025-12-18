"""
Agents Package - 智能代理模块

核心 Agent:
- BridgeAgent: 场景过渡生成
- CriticAgent: 剧本评审
- ShowrunnerAgent: 剧情大纲/节拍规划
- ScriptwriterAgent: 剧本编写
- feedbackjudgeAgent: 意图分类
- MirrorAgent: 反馈分析
- StateKeeper: 状态管理

工作流:
- agent_workflow: LangGraph 编排的故事生成流程

工具:
- agent_utils: Agent 辅助函数（提示词加载等）
"""

# 核心 Agent
from .agent_bridge import BridgeAgent
from .agent_critic import CriticAgent
from .agent_showrunner import ShowrunnerAgent
from .agent_scriptwriter import ScriptwriterAgent
from .agent_feedbackjudge import feedbackjudgeAgent
from .agent_mirror import MirrorAgent
from .agent_state_keeper import StateKeeper

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
    'BridgeAgent',
    'CriticAgent',
    'ShowrunnerAgent',
    'ScriptwriterAgent',
    'feedbackjudgeAgent',
    'MirrorAgent',
    'StateKeeper',
    # Workflow
    'run_story_generation_workflow',
    'create_story_generation_graph',
    'StoryGenerationState',
    # Utils
    'load_prompt',
    'get_prompts_dir',
    'clear_prompt_cache',
]
