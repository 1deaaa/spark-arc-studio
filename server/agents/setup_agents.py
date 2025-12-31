import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt
from .communication import SparkBaseAgent

class MuseAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_muse", user_id=user_id)
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_muse", streaming=True, temperature=0.9) # High creativity

    def chat(self, user_message: str, history=None, active_context: str = None) -> str:
        """用于“与专家交流”的对话模式：允许解释与讨论，不强制输出固定模板。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from agents.agent_utils import load_prompt

        # Load chat_system from YAML
        try:
            prompts = load_prompt('muse')
            system_prompt = prompts.get('chat_system') or prompts.get('system')
        except Exception:
            system_prompt = "你是‘灵感种子’：擅长创意发散与点子推进。"

        messages = [SystemMessage(content=system_prompt)]
        if history:
            for msg in history[-10:]:
                role = msg.get('role')
                content = msg.get('content')
                if not content:
                    continue
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                if role == 'user':
                    messages.append(HumanMessage(content=str(content)))
                elif role == 'assistant':
                    messages.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            messages.append(HumanMessage(content=f"【当前上下文】\n{active_context}"))

        messages.append(HumanMessage(content=user_message))

        resp = self.llm.invoke(messages)
        return resp.content

    def chat_stream(self, user_message: str, history=None, active_context: str = None):
        """对话模式的流式输出。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from agents.agent_utils import load_prompt

        # Load chat_system from YAML
        try:
            prompts = load_prompt('muse')
            system_prompt = prompts.get('chat_system') or prompts.get('system')
        except Exception:
            system_prompt = "你是‘灵感种子’：擅长创意发散与点子推进。"

        messages = [SystemMessage(content=system_prompt)]
        if history:
            for msg in history[-10:]:
                role = msg.get('role')
                content = msg.get('content')
                if not content:
                    continue
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                if role == 'user':
                    messages.append(HumanMessage(content=str(content)))
                elif role == 'assistant':
                    messages.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            messages.append(HumanMessage(content=f"【当前上下文】\n{active_context}"))

        messages.append(HumanMessage(content=user_message))

        for chunk in self.llm.stream(messages):
            yield getattr(chunk, 'content', '')

    def expand_inspiration(self, raw_input: str, style: str = None, 
                           genres: list = None, length_hint: str = None):
        """
        Expands a vague idea into a rich creative seed.
        
        Args:
            raw_input: The raw inspiration input
            style: Optional preferred style (e.g., 治愈, 悬疑, 恐怖)
            genres: Optional list of genre tags (e.g., ['校园', '日常'])
            length_hint: Optional length suggestion (短篇/中篇/长篇)
        """
        # Build dynamic hint strings
        style_hint = ""
        if style:
            style_hint = f"5.  **风格倾向**：请以「{style}」风格为主导进行创作。"
        
        genre_hint = ""
        if genres and len(genres) > 0:
            genre_list = "、".join(genres)
            genre_hint = f"6.  **题材方向**：请围绕「{genre_list}」题材展开构思。"
        
        length_hint_str = ""
        if length_hint:
            length_map = {
                "短篇": "约1-3章节，聚焦单一事件或情感弧线",
                "中篇": "约5-10章节，可以有多条主线交织",
                "长篇": "10+章节，支持宏大世界观和复杂角色关系"
            }
            hint_text = length_map.get(length_hint, length_hint)
            length_hint_str = f"7.  **篇幅建议**：{length_hint}（{hint_text}）。"
        
        prompts = load_prompt('muse', raw_input=raw_input, 
                             style_hint=style_hint, 
                             genre_hint=genre_hint, 
                             length_hint=length_hint_str)
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]
        
        # We return a generator for streaming
        for chunk in self.llm.stream(messages):
            yield chunk.content

