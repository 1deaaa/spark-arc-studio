import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import get_agent_usage_key

class MuseAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        usage_key = get_agent_usage_key(user_id, "agent_muse")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=True, temperature=0.9) # High creativity

    def expand_inspiration(self, raw_input: str) -> str:
        """
        Expands a vague idea into a rich creative seed.
        """
        system_prompt = """你是**缪斯（The Muse）**。
你的目标是将用户模糊的灵感（一句歌词、一种感觉、一个场景片段）扩展成一颗**创意种子**。

### 创意种子必须包含：
1.  **核心主题**：核心的哲学或情感冲突。
2.  **基调/氛围**：视觉和听觉风格（例如：赛博朋克黑色电影、田园生活片段）。
3.  **钩子（The Hook）**：一个引人注目的激励事件。
4.  **关键意象**：3个具体的视觉符号或重复出现的母题。

### 输出格式：
以 Markdown 格式返回结果。
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=raw_input)
        ]
        
        # We return a generator for streaming
        for chunk in self.llm.stream(messages):
            yield chunk.content
