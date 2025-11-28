"""
Critic Agent - 剧本评审

严格评估编剧提供的剧本初稿，检查视角一致性、逻辑连贯性等
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import get_agent_usage_key, load_prompt


class CriticAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Critic needs high reasoning to catch subtle errors
        usage_key = get_agent_usage_key(user_id, "agent_critic")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.3)

    def evaluate(self, script_nodes: list, context: str, beat_sheet: dict) -> tuple[int, str, str]:
        """
        Evaluates the generated script.
        Returns: (score, feedback_summary, detailed_critique)
        """
        
        # Convert nodes back to text for evaluation
        script_text = json.dumps(script_nodes, ensure_ascii=False, indent=2)
        beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        # 从 YAML 加载提示词
        prompts = load_prompt(
            'critic',
            context=context,
            beat_sheet=beat_sheet_str,
            script=script_text
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
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
