"""
Showrunner Agent - 剧情大纲生成

生成可视化的树状剧情大纲，包含：
- 节点（可嵌套）
- 每个节点有标题、描述、类型、子节点等
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import get_agent_usage_key


class ShowrunnerAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        usage_key = get_agent_usage_key(user_id, "agent_showrunner")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.7)

    def generate_outline(self, context: str, worldview: str, roles: str, guidance: str) -> dict:
        """
        生成可视化剧情大纲（树状结构）
        
        返回格式：
        {
            "title": "故事标题",
            "summary": "整体概述",
            "nodes": [
                {
                    "id": "node_1",
                    "title": "第一幕：开端",
                    "type": "act",
                    "description": "...",
                    "mood": "...",
                    "tension": "low/medium/high",
                    "children": [
                        {
                            "id": "node_1_1",
                            "title": "场景1：相遇",
                            "type": "scene",
                            "description": "...",
                            "characters": ["角色A", "角色B"],
                            "keyBeats": ["节拍1", "节拍2"],
                            "children": []
                        }
                    ]
                }
            ]
        }
        """
        system_prompt = """你是高质量互动视觉小说（Galgame）的**总编剧**。
你的任务是创建一个**结构化的剧情大纲**，这个大纲将以可视化的树状图形式展示给用户编辑。

### 大纲结构要求：
1. **层级清晰**：使用 幕(Act) → 场景(Scene) → 节拍(Beat) 的三级结构
2. **每个节点必须包含**：
   - `id`: 唯一标识符（如 "act_1", "scene_1_1", "beat_1_1_1"）
   - `title`: 简短标题（5-15字）
   - `type`: 节点类型 ("act" | "scene" | "beat")
   - `description`: 详细描述（1-3句话）
   
3. **可选字段**：
   - `mood`: 情感氛围
   - `tension`: 紧张程度 ("low" | "medium" | "high")
   - `characters`: 涉及的角色列表
   - `keyBeats`: 关键事件点（仅用于scene级别）
   - `notes`: 导演备注

4. **children**: 子节点数组（可嵌套）

### 输出格式：
输出一个单一的有效JSON对象：
```json
{
    "title": "故事标题",
    "summary": "整体故事概述（2-3句话）",
    "totalActs": 3,
    "estimatedScenes": 10,
    "mainTheme": "核心主题",
    "nodes": [
        {
            "id": "act_1",
            "title": "第一幕：开端",
            "type": "act",
            "description": "建立世界观，引入主角...",
            "mood": "平静/神秘",
            "tension": "low",
            "children": [
                {
                    "id": "scene_1_1",
                    "title": "日常的早晨",
                    "type": "scene",
                    "description": "展示主角的日常生活...",
                    "characters": ["主角"],
                    "mood": "温馨",
                    "tension": "low",
                    "keyBeats": [
                        "主角醒来，环顾熟悉的房间",
                        "收到神秘信息"
                    ],
                    "children": []
                }
            ]
        }
    ]
}
```

### 约束：
- 所有文本内容必须是**中文**
- JSON键名保持英文以便程序处理
- 根据提供的上下文和世界观创建合适的故事结构
- 确保结构完整，每个幕至少包含2-3个场景
- 默认生成3幕结构（可根据guidance调整）
"""

        user_prompt = f"""
### 世界观设定：
{worldview if worldview else "（未提供，请创建一个原创世界观）"}

### 角色设定：
{roles if roles else "（未提供，请创建合适的角色）"}

### 当前上下文/背景：
{context if context else "这是一个全新的故事"}

### 用户指导/意图：
{guidance if guidance else "请生成一个标准的三幕剧结构大纲"}

请生成结构化的剧情大纲。
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content
            content = self._clean_json_block(content)
            outline = json.loads(content)
            
            # 确保必要字段存在
            if 'nodes' not in outline:
                outline['nodes'] = []
            if 'title' not in outline:
                outline['title'] = '新故事大纲'
                
            return outline
        except Exception as e:
            print(f"[Showrunner] Error generating outline: {e}")
            # 返回基础模板
            return self._get_fallback_outline()

    def plan_scene(self, context: str, worldview: str, roles: str, guidance: str) -> dict:
        """
        生成场景级别的 Beat Sheet（保留兼容性）
        """
        system_prompt = """你是高质量互动视觉小说（Galgame）的**总编剧**和**首席作家**。
你的目标不是写最终剧本，而是为接下来的剧情创建一个**节拍表（Beat Sheet）**（结构计划）。

### 你的目标：
1.  **分析上下文**：理解当前的剧情状态、角色动机和紧张程度。
2.  **规划节奏**：决定接下来的剧情应该是快节奏（动作/冲突）还是慢节奏（内省/浪漫）。
3.  **定义关键节拍**：列出3-5个必须发生的具体情节点或情感时刻。

### 输出格式：
你必须输出一个单一的有效JSON对象，结构如下：
```json
{
    "summary": "本段剧情的简要总结（1-2句话）。",
    "pacing": "Slow" | "Normal" | "Fast",
    "tension_level": "Low" | "Medium" | "High",
    "mood": "情感氛围（例如：忧郁、紧张、快乐）。",
    "key_beats": [
        "节拍 1: 第一个事件/对话焦点的描述。",
        "节拍 2: ...",
        "节拍 3: ..."
    ],
    "director_notes": "给编剧的具体指示，关于镜头角度、感官细节或潜台词。"
}
```

### 约束：
- **语言**：JSON键和结构值（如 "Slow"）应保持英文以便程序处理，但 `summary`、`key_beats` 和 `director_notes` 的内容必须是**中文**，以确保文化韵味。
- **一致性**：确保计划符合提供的世界观和角色设定。
"""

        user_prompt = f"""
### Worldview:
{worldview}

### Character Settings:
{roles}

### Current Story Context:
{context}

### User Guidance/Intent:
{guidance}

Please generate the Beat Sheet for the next sequence.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            content = response.content
            content = self._clean_json_block(content)
            beat_sheet = json.loads(content)
            return beat_sheet
        except Exception as e:
            print(f"[Showrunner] Error generating beat sheet: {e}")
            return {
                "summary": "剧情继续发展",
                "pacing": "Normal",
                "tension_level": "Medium",
                "mood": "Neutral",
                "key_beats": ["角色继续当前的对话或行动"],
                "director_notes": "保持当前氛围"
            }

    def _clean_json_block(self, text: str) -> str:
        """Extract JSON from potential markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    def _get_fallback_outline(self) -> dict:
        """返回一个基础的大纲模板"""
        return {
            "title": "新故事大纲",
            "summary": "请在左侧输入上下文和指导，生成详细大纲",
            "totalActs": 3,
            "estimatedScenes": 0,
            "mainTheme": "",
            "nodes": [
                {
                    "id": "act_1",
                    "title": "第一幕：开端",
                    "type": "act",
                    "description": "故事的开始，建立背景和角色",
                    "mood": "平静",
                    "tension": "low",
                    "children": []
                },
                {
                    "id": "act_2",
                    "title": "第二幕：发展",
                    "type": "act",
                    "description": "冲突升级，角色面临挑战",
                    "mood": "紧张",
                    "tension": "medium",
                    "children": []
                },
                {
                    "id": "act_3",
                    "title": "第三幕：高潮与结局",
                    "type": "act",
                    "description": "矛盾解决，故事收尾",
                    "mood": "激烈",
                    "tension": "high",
                    "children": []
                }
            ]
        }
