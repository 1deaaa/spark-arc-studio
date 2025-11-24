import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import get_agent_usage_key

class ShowrunnerAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Showrunner needs reasoning capabilities, so we use the user's configured smart model
        usage_key = get_agent_usage_key(user_id, "agent_showrunner")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.7)

    def plan_scene(self, context: str, worldview: str, roles: str, guidance: str) -> dict:
        """
        Generates a Beat Sheet (plan) for the next scene.
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
            
            # Basic cleanup to ensure we get JSON
            content = self._clean_json_block(content)
            
            beat_sheet = json.loads(content)
            return beat_sheet
        except Exception as e:
            print(f"[Showrunner] Error generating beat sheet: {e}")
            # Fallback plan if AI fails
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
            # Find the first newline
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            # Remove the last ```
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()
