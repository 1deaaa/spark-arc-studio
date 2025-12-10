"""
Mirror Agent - 反馈分析

分析用户反馈，提炼为可执行的修改指令
"""
import json
import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from core.utils import get_project_path
from agents.agent_utils import load_prompt, get_agent_usage_key


class MirrorAgent:
    def __init__(self, user_id, project_name):
        self.user_id = user_id
        self.project_name = project_name
        usage_key = get_agent_usage_key(user_id, "agent_mirror")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.5)
        self.prefs_file = os.path.join(get_project_path(user_id, project_name), 'UserPrefs.json')

    def analyze_feedback(self, original_content: str, user_feedback: str) -> dict:
        """
        Analyzes user feedback to generate rewrite instructions and update preferences.
        """
        # 从 YAML 加载提示词
        prompts = load_prompt(
            'mirror',
            original_content=original_content[:1000] + "..." if len(original_content) > 1000 else original_content,
            user_feedback=user_feedback
        )
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
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
        match = re.search(r'```json\s*(\[.*?\]|\{.*?\})\s*```', text, re.DOTALL)
        if match: return json.loads(match.group(1))
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1: return json.loads(text[start:end+1])
        return {}
