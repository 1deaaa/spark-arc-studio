# agents/registry.py
# 本文件用于注册所有可被前端管理的 Agent 及其用途key、显示名、描述等元数据

AGENT_REGISTRY = [
    {
        "key": "agent_showrunner",
        "name": "Showrunner (策划)",
        "description": "负责故事大纲与分集规划。",
        "group": "main"
    },
    {
        "key": "agent_scriptwriter",
        "name": "Scriptwriter (编剧)",
        "description": "负责具体场景剧本撰写。",
        "group": "main"
    },
    {
        "key": "agent_critic",
        "name": "Critic (评论家)",
        "description": "负责剧本审核与反馈。",
        "group": "main"
    },
    {
        "key": "agent_muse",
        "name": "Muse (灵感缪斯)",
        "description": "负责灵感扩展与创意生成。",
        "group": "main"
    },
    {
        "key": "agent_state_keeper",
        "name": "State Keeper (状态管理)",
        "description": "负责剧情状态与一致性维护。",
        "group": "main"
    },
    # 风格相关 agent 统一注册为同一个用途
    {
        "key": "agent_style",
        "name": "Style Agent (风格分析)",
        "description": "负责风格分析、风格迁移等所有风格相关任务。",
        "group": "style"
    }
]

def get_agent_registry():
    return AGENT_REGISTRY
