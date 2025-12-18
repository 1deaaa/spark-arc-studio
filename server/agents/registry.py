# agents/registry.py
# 本文件用于注册所有可被前端管理的 Agent 及其用途key、显示名、描述等元数据

AGENT_REGISTRY = [
    {
        "key": "agent_showrunner",
        "name": "导演助理",
        "description": "负责故事大纲与分集规划。",
        "group": "main"
    },
    {
        "key": "agent_scriptwriter",
        "name": "执笔编剧",
        "description": "负责具体场景剧本撰写。",
        "group": "main"
    },
    {
        "key": "agent_critic",
        "name": "逻辑审核",
        "description": "负责剧本审核与反馈。",
        "group": "main"
    },
    {
        "key": "agent_muse",
        "name": "灵感种子",
        "description": "负责灵感扩展与创意生成。",
        "group": "main"
    },
    {
        "key": "agent_lorebook",
        "name": "设定生成",
        "description": "负责世界观与角色生成。",
        "group": "main"
    },
    {
        "key": "agent_feedbackjudge",
        "name": "意图识别",
        "description": "负责简单的意图识别。",
        "group": "main"
    },
    {
        "key": "agent_mirror",
        "name": "反馈记录",
        "description": "负责反馈分析与偏好学习。",
        "group": "main"
    },
    # 风格相关 agent 统一注册为同一个用途
    {
        "key": "agent_style",
        "name": "文风克隆",
        "description": "负责风格分析、风格迁移等所有风格相关任务。",
        "group": "style"
    }
]

def get_agent_registry():
    return AGENT_REGISTRY
