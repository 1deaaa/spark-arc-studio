# agents/registry.py
# 本文件用于注册所有可被前端管理的 Agent 及其用途key、显示名、描述等元数据

AGENT_REGISTRY = [
    {
        "key": "agent_director",
        "name": "导演",
        "display": "负责统筹全局，多轮协调并调度专家 Agent。",
        "description": "系统的总入口与协调中枢。通过多轮工具调用自主决策：查阅项目章节结构、读取剧本内容、委派任务给专家 Agent。可直接回答用户问题，也可协调多个专家完成复杂任务。",
        "group": "main",
        "participatesInBeaconBus": True
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
        "name": "评审专家",
        "display": "负责剧本/小说审查、AI味诊断与修改建议。",
        "description": "负责对已有剧本、小说段落、具体场景进行严格评审：检查 AI 味残留、对白自然度、文学承载、逻辑与人设问题。既可由用户直接聊天咨询，也可被导演委派读取具体场景后给出审稿意见。",
        "group": "main"
    },
    {
        "key": "agent_muse",
        "name": "灵感种子",
        "display": "负责灵感扩展与创意生成。",
        "description": '负责所有与"灵感"相关的任务：创意点子、脑洞扩展、灵感启发、查看/回顾灵感内容。当用户消息中包含"灵感"二字，或用户卡文需要创意建议时使用。',
        "group": "main"
    },
    {
        "key": "agent_lorebook",
        "name": "设定专家",
        "display": "负责世界观与角色生成。",
        "description": "负责世界观设定、角色档案、人物关系、背景故事、百科。当用户想要增加、修改或查看设定时使用。",
        "group": "main"
    },
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
