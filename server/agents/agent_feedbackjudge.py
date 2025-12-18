"""
意图识别 - 意图分类

快速判断用户意图：继续剧情还是修改内容
"""
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt


class FeedbackJudgeAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Use a fast/lightweight model if possible
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key="fast", streaming=False, temperature=0.1)

    def route_request(self, user_input: str) -> str:
        """
        Decides whether the user wants to proceed (NEXT) or modify (MODIFY).
        """
        # 从 YAML 加载提示词
        prompts = load_prompt(
            'feedbackjudge',
            user_input=user_input
        )
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            response = self.llm.invoke(messages)
            decision = response.content.strip().upper()
            if "MODIFY" in decision: return "MODIFY"
            return "NEXT"
        except Exception as e:
            raise RuntimeError(f"[FeedbackJudge] 意图分类失败: {e}")
