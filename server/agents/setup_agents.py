import json
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt
from .communication import SparkBaseAgent

class MuseAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_muse", user_id=user_id)
        self.llm = LLM_Manager.get_user_llm(str(user_id), agent_name="agent_muse")[0]

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

        # 使用 stream() 收集所有 chunks，避免流式 LLM 的 invoke() 兼容性问题
        chunks = []
        for chunk in self.llm.stream(messages):
            chunks.append(getattr(chunk, 'content', ''))
        return ''.join(chunks)

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
                           genres: list = None, tones: list = None, worldviews: list = None, length_hint: str = None):
        """
        Expands a vague idea into a rich creative seed.
        
        Args:
            raw_input: The raw inspiration input
            style: Optional preferred style (e.g., 治愈, 悬疑, 恐怖)
            genres: Optional list of genre tags (e.g., ['校园', '日常'])
            tones: Optional list of tone/school tags (e.g., ['现实主义', '魔幻现实主义'])
            worldviews: Optional list of worldview/setting tags (e.g., ['架空', '穿越'])
            length_hint: Optional length suggestion (短篇/中篇/长篇)
        """
        # Build dynamic hint strings
        style_hint = "5.  **风格倾向**：不限。"
        if style:
            style_hint = f"5.  **风格倾向**：请以「{style}」风格为主导进行创作。"
        
        genre_hint = "6.  **题材方向**：不限。"
        if genres and len(genres) > 0:
            genre_list = "、".join(genres)
            genre_hint = f"6.  **题材方向**：请围绕「{genre_list}」题材展开构思。"

        tone_hint = "7.  **基调与流派**：不限。"
        if tones and len(tones) > 0:
            tone_list = "、".join(tones)
            tone_hint = f"7.  **基调与流派**：请融入「{tone_list}」的文学特质与氛围。"

        worldview_hint = "8.  **世界规则**：不限。"
        if worldviews and len(worldviews) > 0:
            worldview_list = "、".join(worldviews)
            worldview_hint = f"8.  **世界规则出**：请基于「{worldview_list}」的世界规则构建背景。"
        
        length_hint_str = ""
        if length_hint:
            length_map = {
                "短篇": "建议约1-3章节，聚焦单一事件或情感弧线，适合短篇小说或Demo级游戏剧情",
                "中篇": "建议约5-10章节，可以有多条主线交织，适合中篇小说或标准独立游戏流程",
                "长篇": "建议10+章节，支持宏大世界观和复杂角色关系，适合长篇连载或大型游戏剧本"
            }
            hint_text = length_map.get(length_hint, length_hint)
            length_hint_str = f"9.  **篇幅建议**：{length_hint}（{hint_text}）。"
        
        prompts = load_prompt('muse', raw_input=raw_input, 
                             style_hint=style_hint, 
                             genre_hint=genre_hint, 
                             tone_hint=tone_hint,
                             worldview_hint=worldview_hint,
                             length_hint=length_hint_str)
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]
        
        # We return a generator for streaming
        for chunk in self.llm.stream(messages):
            yield chunk.content

