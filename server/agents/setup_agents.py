import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt

class MuseAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_muse", streaming=True, temperature=0.9) # High creativity

    def expand_inspiration(self, raw_input: str) -> str:
        """
        Expands a vague idea into a rich creative seed.
        """
        prompts = load_prompt('muse', raw_input=raw_input)
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]
        
        # We return a generator for streaming
        for chunk in self.llm.stream(messages):
            yield chunk.content
