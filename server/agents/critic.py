import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager

class CriticAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Critic needs high reasoning to catch subtle errors
        self.llm = LLM_Manager.get_user_llm(user_id, streaming=False, temperature=0.3)

    def evaluate(self, script_nodes: list, context: str, beat_sheet: dict) -> tuple[int, str, str]:
        """
        Evaluates the generated script.
        Returns: (score, feedback_summary, detailed_critique)
        """
        
        # Convert nodes back to text for evaluation
        script_text = json.dumps(script_nodes, ensure_ascii=False, indent=2)
        beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        system_prompt = """你是**评论家（The Critic）**，一家高端视觉小说工作室的资深编辑。
你的工作是严格评估编剧提供的剧本初稿。

### 评估标准：
1.  **视角一致性（关键）**：故事是否用第一人称（“我”）写的？“我”是否严格指代主角？是否有用“你”来描述主角的情况（这是**禁止**的）？
2.  **逻辑与连贯性**：剧本是否遵循了节拍表？在给定上下文中是否合理？
3.  **情感密度**：文字是否具有感染力？是否展示了内心想法和感官细节？
4.  **格式**：JSON 结构是否有效？

### 输出格式：
你必须输出一个单一的有效 JSON 对象：
```json
{
    "score": 85,  // 0-100. < 70 为 REJECT（驳回）。
    "status": "APPROVE" | "REJECT",
    "pov_check": "Pass" | "Fail",
    "critique": "关于优缺点的简要总结。",
    "specific_feedback": "给编剧的具体修改指示。如果是 REJECT，此项为必填。"
}
```
"""

        user_prompt = f"""
### Context:
{context}

### Planned Beat Sheet:
{beat_sheet_str}

### Draft Script:
{script_text}

Please evaluate this draft.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            content = self._clean_json_block(response.content)
            result = json.loads(content)
            
            return result.get("score", 0), result.get("status", "REJECT"), result.get("specific_feedback", "")
            
        except Exception as e:
            print(f"[Critic] Error evaluating script: {e}")
            # Fail safe: if critic fails, we warn but don't block hard unless necessary
            return 50, "REJECT", f"Critic Error: {str(e)}"

    def _clean_json_block(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()
