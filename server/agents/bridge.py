import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager

class BridgeAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        self.llm = LLM_Manager.get_user_llm(user_id, streaming=False, temperature=0.5)

    def bridge_scenes(self, prev_text: str, next_text: str, context: str) -> list:
        """
        Generates a transition sequence between two disconnected scenes.
        """
        system_prompt = """你是**桥梁（The Bridge）**。
你的任务是在两个不连贯的故事片段之间编写平滑的过渡。
你必须保持现有故事的基调和风格。

### 输入：
- **上一片段**：上一场景的结尾。
- **下一片段**：新场景的开头。

### 输出：
生成一个对话/旁白节点的 JSON 数组，自然地连接它们。
格式：
```json
[
  { "chr": "...", "txt": "..." }
]
```
"""
        user_prompt = f"""
### Context:
{context}

### Previous Segment (End):
{prev_text[-500:] if prev_text else "Start of story"}

### Next Segment (Start):
{next_text[:500] if next_text else "End of story"}

Please write the transition.
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            return self._extract_json(response.content)
        except Exception as e:
            print(f"[Bridge] Error: {e}")
            return []

    def _extract_json(self, text):
        # Simple extraction logic (simplified for brevity)
        import re
        match = re.search(r'```json\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match: return json.loads(match.group(1))
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
        return []
