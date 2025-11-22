import json
import os
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from core.utils import get_project_path

class MirrorAgent:
    def __init__(self, user_id, project_name):
        self.user_id = user_id
        self.project_name = project_name
        self.llm = LLM_Manager.get_user_llm(user_id, streaming=False, temperature=0.5)
        self.prefs_file = os.path.join(get_project_path(user_id, project_name), 'UserPrefs.json')

    def analyze_feedback(self, original_content: str, user_feedback: str) -> dict:
        """
        Analyzes user feedback to generate rewrite instructions and update preferences.
        """
        system_prompt = """你是**魔镜（The Mirror）**。
你的目标是将用户反馈提炼为给编剧的可执行指令。

### 任务：
1.  **分析**：用户到底不喜欢什么？（基调、剧情、角色、逻辑？）
2.  **提炼**：创建一个“负面约束”（不做什么）或“偏好”（做什么）。
3.  **指示**：编写清晰、技术性的指令，让编剧修复当前片段。

### 输出格式：
```json
{
    "rewrite_instruction": "给编剧的具体指令...",
    "new_preference": "保存以备将来使用的通用规则（例如：'用户讨厌超过3行的内心独白'）。",
    "preference_type": "negative_constraint" | "style_preference"
}
```
"""
        user_prompt = f"""
### Original Content (Snippet):
{original_content[:1000]}...

### User Feedback:
{user_feedback}

Analyze and generate instructions.
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            result = self._extract_json(response.content)
            
            # Persist preference if found
            if result.get("new_preference"):
                self._save_preference(result["new_preference"], result.get("preference_type", "style_preference"))
                
            return result
        except Exception as e:
            print(f"[Mirror] Error: {e}")
            return {"rewrite_instruction": user_feedback}

    def _save_preference(self, pref, ptype):
        try:
            data = {}
            if os.path.exists(self.prefs_file):
                with open(self.prefs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            if ptype not in data: data[ptype] = []
            if pref not in data[ptype]:
                data[ptype].append(pref)
                
            with open(self.prefs_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _extract_json(self, text):
        import re
        match = re.search(r'```json\s*(\[.*?\]|\{.*?\})\s*```', text, re.DOTALL)
        if match: return json.loads(match.group(1))
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
        return {}
