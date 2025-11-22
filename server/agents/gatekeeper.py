from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager

class GatekeeperAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Use a fast/lightweight model if possible, but user_llm is generic here.
        # In a real scenario, we might request a specific 'flash' model.
        self.llm = LLM_Manager.get_user_llm(user_id, streaming=False, temperature=0.1)

    def route_request(self, user_input: str) -> str:
        """
        Decides whether the user wants to proceed (NEXT) or modify (MODIFY).
        """
        system_prompt = """你是**守门人（The Gatekeeper）**。
你唯一的工作是根据用户的最新消息对用户的意图进行分类。

### 类别：
- **NEXT**：用户满意，想要继续，或者给出了通用的“继续”/“往下走”指令。
- **MODIFY**：用户在批评、要求更改、指出错误或想要重写。

### 输出：
仅返回类别名称："NEXT" 或 "MODIFY"。
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]

        try:
            response = self.llm.invoke(messages)
            decision = response.content.strip().upper()
            if "MODIFY" in decision: return "MODIFY"
            return "NEXT"
        except Exception:
            return "NEXT" # Default to continue
