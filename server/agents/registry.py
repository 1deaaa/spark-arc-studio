# agents/registry.py
# 本文件用于注册所有可被前端管理的 Agent 及其用途key、显示名、描述等元数据
#
# name / display / description 采用多语言字典结构：
#   { 'zh-CN': '中文', 'en-US': 'English', 'ja-JP': '日本語' }
# 新增语言时，只需在每个 Agent 条目的 name/display/description 中加一组翻译即可。
# 前端通过 i18n 的 components.agentNames / agentDescriptions 做本地映射，
# 后端通过 resolve_agent_i18n_field() 按请求 locale 提取对应字段。
#
# icon: Lucide 图标名（PascalCase），前端 AgentAvatar 通过映射表转为组件。
# color: 该 Agent 的专属主题色（hex），用于头像描边/光晕/轮盘扇片渐变。
# 这两个字段是前端所有 Agent 视觉呈现的唯一真相源，禁止在前端各处再硬编码。

AGENT_REGISTRY = [
    {
        "key": "agent_director",
        "name": {
            "zh-CN": "导演",
            "en-US": "Director",
            "ja-JP": "監督",
        },
        "display": {
            "zh-CN": "负责统筹全局，多轮协调并调度专家 Agent。",
            "en-US": "Coordinates the whole workflow and delegates tasks to specialist agents.",
            "ja-JP": "全体進行を統括し、各 Agent を協調させます。",
        },
        "description": {
            "zh-CN": "系统的总入口与协调中枢。通过多轮工具调用自主决策：查阅项目章节结构、读取剧本内容、委派任务给专家 Agent。可直接回答用户问题，也可协调多个专家完成复杂任务。",
            "en-US": "The central entry point and coordination hub. Autonomously decides via multi-turn tool calls: inspect chapter structure, read script content, delegate tasks to specialist agents. Can directly answer user questions or coordinate multiple specialists for complex tasks.",
            "ja-JP": "システムの総合入口と調整ハブ。マルチターンのツール呼び出しで自律的に判断：章構造の確認、脚本内容の読み取り、専門 Agent へのタスク委派。ユーザーの質問に直接回答することも、複数の専門家を調整して複雑なタスクを完了することも可能です。",
        },
        "group": "main",
        "participatesInBeaconBus": True,
        "icon": "Compass",
        "color": "#5b8cff"
    },
    {
        "key": "agent_showrunner",
        "name": {
            "zh-CN": "文案策划",
            "en-US": "Showrunner",
            "ja-JP": "ショーランナー",
        },
        "display": {
            "zh-CN": "负责故事大纲与分集规划。",
            "en-US": "Plans story architecture and pacing.",
            "ja-JP": "物語構成とテンポ設計を担当します。",
        },
        "description": {
            "zh-CN": "负责创作故事大纲、梗概、剧情结构、分集/分章规划、节拍表（Beat Sheet）。当用户想要讨论整体剧情走向或大纲结构时使用。",
            "en-US": "Creates story outlines, synopses, plot structures, episode/chapter planning, and beat sheets. Used when discussing overall plot direction or outline structure.",
            "ja-JP": "ストーリーのアウトライン、あらすじ、プロット構造、エピソード/章構成、ビートシートを作成します。全体的なプロットの方向性や構成について議論する際に使用します。",
        },
        "group": "main",
        "icon": "Waypoints",
        "color": "#2dd4bf"
    },
    {
        "key": "agent_scriptwriter",
        "name": {
            "zh-CN": "执笔编剧",
            "en-US": "Scriptwriter",
            "ja-JP": "脚本作家",
        },
        "display": {
            "zh-CN": "负责具体场景剧本撰写。",
            "en-US": "Writes scenes and script content.",
            "ja-JP": "本文とシーン脚本の執筆を担当します。",
        },
        "description": {
            "zh-CN": "负责具体的正文撰写、场景描写、对话生成、续写、改写一整段。当用户讨论某个具体场景或者剧本的内容时使用。",
            "en-US": "Handles actual text writing, scene descriptions, dialogue generation, continuation, and paragraph rewriting. Used when discussing a specific scene or script content.",
            "ja-JP": "本文の執筆、シーン描写、対話生成、続きの執筆、段落の書き直しを担当します。特定のシーンや脚本の内容について議論する際に使用します。",
        },
        "group": "main",
        "icon": "Feather",
        "color": "#38bdf8"
    },
    {
        "key": "agent_critic",
        "name": {
            "zh-CN": "评审专家",
            "en-US": "Critic",
            "ja-JP": "批評エキスパート",
        },
        "display": {
            "zh-CN": "负责剧本/小说审查、AI味诊断与修改建议。",
            "en-US": "Reviews quality and provides rewrite suggestions.",
            "ja-JP": "品質レビューと改稿提案を担当します。",
        },
        "description": {
            "zh-CN": "负责对已有剧本、小说段落、具体场景进行严格评审：检查 AI 味残留、对白自然度、文学承载、逻辑与人设问题。既可由用户直接聊天咨询，也可被导演委派读取具体场景后给出审稿意见。",
            "en-US": "Conducts rigorous reviews of existing scripts, novel passages, and specific scenes: checks for AI flavor residue, dialogue naturalness, literary quality, logic and character consistency. Can be consulted directly by users or delegated by the Director to review specific scenes.",
            "ja-JP": "既存の脚本や小説の段落、特定のシーンを厳格にレビュー：AI味の残存、対話の自然さ、文学的品質、論理とキャラクター一貫性をチェックします。ユーザーから直接相談されることも、監督から特定シーンのレビューを委派されることもあります。",
        },
        "group": "main",
        "icon": "ScanEye",
        "color": "#ff6b6b"
    },
    {
        "key": "agent_muse",
        "name": {
            "zh-CN": "灵感种子",
            "en-US": "Muse Seed",
            "ja-JP": "着想シード",
        },
        "display": {
            "zh-CN": "负责灵感扩展与创意生成。",
            "en-US": "Expands inspirations and explores ideas.",
            "ja-JP": "着想の拡張と発散支援を担当します。",
        },
        "description": {
            "zh-CN": '负责所有与"灵感"相关的任务：创意点子、脑洞扩展、灵感启发、查看/回顾灵感内容。当用户消息中包含"灵感"二字，或用户卡文需要创意建议时使用。',
            "en-US": 'Handles all "inspiration" related tasks: creative ideas, brainstorming, inspiration prompts, viewing/reviewing inspiration content. Used when the user mentions "inspiration" or needs creative suggestions for writer\'s block.',
            "ja-JP": '「着想」に関連するすべてのタスクを担当：クリエイティブなアイデア、ブレインストーミング、着想の促進、着想内容の確認/振り返り。ユーザーが「着想」に言及した場合や、行き詰まった時にクリエイティブな提案が必要な場合に使用します。',
        },
        "group": "main",
        "icon": "Wand2",
        "color": "#b07cff"
    },
    {
        "key": "agent_lorebook",
        "name": {
            "zh-CN": "设定专家",
            "en-US": "Lore Specialist",
            "ja-JP": "設定エキスパート",
        },
        "display": {
            "zh-CN": "负责世界观与角色生成。",
            "en-US": "Maintains worldbuilding consistency and settings.",
            "ja-JP": "世界観と設定の整合性を担当します。",
        },
        "description": {
            "zh-CN": "负责世界观设定、角色档案、人物关系、背景故事、百科。当用户想要增加、修改或查看设定时使用。",
            "en-US": "Handles worldbuilding settings, character profiles, relationships, backstories, and lore encyclopedia. Used when the user wants to add, modify, or view settings.",
            "ja-JP": "世界観の設定、キャラクタープロフィール、人物関係、バックストーリー、百科事典を担当します。ユーザーが設定を追加、変更、確認したい場合に使用します。",
        },
        "group": "main",
        "icon": "ScrollText",
        "color": "#f5b942"
    },
    {
        "key": "agent_style",
        "name": {
            "zh-CN": "文风克隆",
            "en-US": "Style Clone",
            "ja-JP": "文体クローン",
        },
        "display": {
            "zh-CN": "负责风格分析、风格迁移等所有风格相关任务。",
            "en-US": "Unifies writing style and tone.",
            "ja-JP": "文体と表現の統一を担当します。",
        },
        "description": {
            "zh-CN": "负责文风分析、风格仿写、语气调优。当用户想要模仿某人写东西或调整语言风格时使用。",
            "en-US": "Handles style analysis, style imitation, and tone tuning. Used when the user wants to imitate someone's writing or adjust language style.",
            "ja-JP": "文体分析、スタイル模写、トーン調整を担当します。誰かの書き方を模倣したい場合や、言語スタイルを調整したい場合に使用します。",
        },
        "group": "style",
        "icon": "Palette",
        "color": "#ec4899"
    },
    {
        "key": "agent_utility",
        "name": {
            "zh-CN": "系统工具",
            "en-US": "System Utility",
            "ja-JP": "システムツール",
        },
        "display": {
            "zh-CN": "负责上下文压缩与聊天附件预处理等系统内部任务。",
            "en-US": "Handles internal system tasks such as context compaction and chat attachment preprocessing.",
            "ja-JP": "コンテキスト圧縮やチャット添付の前処理など、内部システムタスクを担当します。",
        },
        "description": {
            "zh-CN": "系统内部工具 Agent，不进入聊天入口、不参与信标总线或导演委派，但可单独绑定模型，用于长上下文压缩和聊天附件切分等基础能力。",
            "en-US": "An internal utility agent. It is hidden from chat entry points and delegation, but can be bound to its own model for context compaction and attachment preprocessing.",
            "ja-JP": "内部ユーティリティ Agent。チャット入口や委任には表示されませんが、コンテキスト圧縮や添付前処理用に個別モデルを割り当てられます。",
        },
        "group": "system",
        "participatesInBeaconBus": False,
        "visibleInChat": False,
        "visibleInModelBinding": True,
        "icon": "Settings2",
        "color": "#64748b"
    }
]


def _resolve_i18n_field(field_value, locale: str = 'zh-CN') -> str:
    """从多语言字典中提取指定 locale 的文本；若非字典则原样返回。"""
    if isinstance(field_value, dict):
        return field_value.get(locale, field_value.get('zh-CN', ''))
    return field_value


def get_agent_registry(locale: str | None = None):
    """返回 Agent 注册表。若指定 locale，则将 name/display/description 展开为纯字符串。"""
    if locale is None:
        return AGENT_REGISTRY

    resolved = []
    for entry in AGENT_REGISTRY:
        item = {k: v for k, v in entry.items() if k not in ('name', 'display', 'description')}
        item['name'] = _resolve_i18n_field(entry['name'], locale)
        item['display'] = _resolve_i18n_field(entry['display'], locale)
        item['description'] = _resolve_i18n_field(entry['description'], locale)
        resolved.append(item)
    return resolved
