from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt, build_length_hint_str, SparkAgentExecutor
from .communication import SparkBaseAgent

class MuseAgent(SparkBaseAgent, SparkAgentExecutor):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_muse", user_id=user_id)
        self.llm = LLM_Manager.get_user_llm(str(user_id), agent_name="agent_muse")

    def build_context(self, operation: str = "expand_inspiration", **kwargs) -> dict:
        """把灵感扩展请求整理成统一上下文，供不同入口复用。"""
        return {"operation": operation, **kwargs}

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """按统一上下文执行灵感扩展或 Muse 对话。"""
        operation = context.get("operation") or "expand_inspiration"
        if operation == "chat":
            if kwargs.get("stream", False):
                return self.chat_stream(
                    user_message=context.get("user_message", ""),
                    history=context.get("history"),
                    active_context=context.get("active_context"),
                )
            return self.chat(
                user_message=context.get("user_message", ""),
                history=context.get("history"),
                active_context=context.get("active_context"),
            )
        return self.expand_inspiration(
            raw_input=context.get("raw_input", ""),
            style=context.get("style"),
            genres=context.get("genres"),
            tones=context.get("tones"),
            worldviews=context.get("worldviews"),
            length_hint=context.get("length_hint"),
        )

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """
        根据入口差异把灵感结果写回现有条目或全局灵感库。

        `origin` 字段用于标记灵感条目的来源，方便后续做通知、筛选与兼容迁移：
        - `ui`：来自页面手动创建/手动扩写，不进入未读提醒
        - `mcp`：来自 MCP 捕获，会进入未读提醒与 MCP 列表逻辑
        - `legacy`：历史老数据补标记，表示该条目创建时系统还没有来源字段
        """
        from mcp_server.spark_inspiration.logic import save_inspiration, update_inspiration, current_user_id

        inspiration_id = kwargs.get("inspiration_id")
        source = kwargs.get("source", "")
        tags = kwargs.get("tags")
        origin = kwargs.get("origin", "ui")
        user_id = str(kwargs.get("user_id") or self.user_id)

        content = result if isinstance(result, str) else ""
        if not content:
            return None

        if inspiration_id:
            return update_inspiration(user_id, inspiration_id, {"content": content})

        token = current_user_id.set(user_id)
        try:
            return save_inspiration(
                source=source,
                content=content,
                tags=tags,
                origin=origin,
            )
        finally:
            current_user_id.reset(token)

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
        
        length_hint_str = build_length_hint_str(length_hint)
        
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

