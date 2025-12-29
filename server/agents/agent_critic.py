"""
逻辑审核 - 剧本评审

严格评估编剧提供的剧本初稿，检查视角一致性、逻辑连贯性等
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt
from .communication import SparkBaseAgent


class CriticAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_critic", user_id=user_id)
        # Critic needs high reasoning to catch subtle errors
        # Enable streaming for chat interactions; evaluate() will still work with invoke()
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_critic", streaming=True, temperature=0.3)

    def evaluate(
        self,
        script_nodes: list,
        context: str,
        guidance: str = "",
        worldview: str = "",
        roles: str = "",
        style_profile: object = None,
    ) -> tuple[int, str, str]:
        """
        Evaluates the generated script.
        Returns: (score, feedback_summary, detailed_critique)
        """
        
        # Convert nodes back to text for evaluation
        script_text = json.dumps(script_nodes, ensure_ascii=False, indent=2)

        style_profile_text = ""
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        # 从 YAML 加载提示词
        prompts = load_prompt(
            'critic',
            context=context,
            guidance=guidance or "",
            worldview=worldview or "",
            roles=roles or "",
            style_profile=style_profile_text or "",
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
            raise RuntimeError(f"[Critic] 评审失败: {e}")

    def _clean_json_block(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()
