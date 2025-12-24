# agents/registry.py
# 本文件用于注册所有可被前端管理的 Agent 及其用途key、显示名、描述等元数据

AGENT_REGISTRY = [
    {
        "key": "agent_director",
        "name": "导演",
        "display": "负责统筹全局，路由并分发需求到其他 Agent。",
        "description": "系统的总入口，负责将任务路由给其他专家 Agent。如果无法确定路由到谁，默认路由到 agent_scriptwriter。",
        "group": "main"
    },
    {
        "key": "agent_showrunner",
        "name": "文案策划",
        "display": "负责故事大纲与分集规划。",
        "description": "负责创作故事大纲、梗概、剧情结构、分集/分章规划、节拍表（Beat Sheet）。当用户想要讨论整体剧情走向或大纲结构时使用。",
        "group": "main"
    },
    {
        "key": "agent_scriptwriter",
        "name": "执笔编剧",
        "display": "负责具体场景剧本撰写。",
        "description": "负责具体的正文撰写、场景描写、对话生成、续写、改写一整段。当用户讨论某个具体场景或者剧本的内容时使用。",
        "group": "main"
    },
    {
        "key": "agent_critic",
        "name": "逻辑审核",
        "display": "负责剧本审核与反馈。",
        "description": "负责逻辑审查、漏洞分析、质量评估。当用户想要评审已有剧本的合理性或寻找漏洞时使用。",
        "group": "main"
    },
    {
        "key": "agent_muse",
        "name": "灵感种子",
        "display": "负责灵感扩展与创意生成。",
        "description": "负责提供创意点子、脑洞、灵感启发。当用户卡文或需要创意建议时使用。",
        "group": "main"
    },
    {
        "key": "agent_lorebook",
        "name": "设定专家",
        "display": "负责世界观与角色生成。",
        "description": "负责世界观设定、角色档案、人物关系、背景故事、百科。当用户想要增加、修改或查看设定时使用。",
        "group": "main"
    },
    # 风格相关 agent 统一注册为同一个用途
    {
        "key": "agent_style",
        "name": "文风克隆",
        "display": "负责风格分析、风格迁移等所有风格相关任务。",
        "description": "负责文风分析、风格仿写、语气调优。当用户想要模仿某人写东西或调整语言风格时使用。",
        "group": "style"
    }
]

def get_agent_registry():
    return AGENT_REGISTRY
