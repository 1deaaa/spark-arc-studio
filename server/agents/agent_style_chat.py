"""
Style 聊天 Agent

职责：
- 将当前项目绑定的完整风格档案注入到聊天上下文
- 允许用户直接询问风格内容、写作倾向、适用建议
- 在未绑定项目风格时，明确告知当前状态，并提示可用风格列表

说明：
- 它属于聊天层 Agent，因此继承 `SparkBaseAgent`
- 它不参与 `SparkAgentExecutor` 的生成/落盘协议
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from core.request_context import current_project_name
from llm.llm_mgr.reasoning_compat import extract_reasoning_text_from_message, extract_text_content_from_message

from .agent_style import load_style_profile_from_file, list_all_authors
from .communication import SparkBaseAgent


class StyleChatAgent(SparkBaseAgent):
    """负责风格档案问答的聊天 Agent。"""

    def __init__(self, user_id: str, project_name: Optional[str] = None):
        super().__init__(agent_id="agent_style", user_id=user_id)
        self.project_name = project_name

    def _resolve_project_name(self) -> Optional[str]:
        """优先使用显式项目名，其次回退到请求上下文中的当前项目。"""
        return self.project_name or current_project_name.get()

    def _resolve_style_payload(self) -> Dict[str, Any]:
        """解析当前聊天应绑定的风格档案与辅助提示信息。"""
        project_name = self._resolve_project_name()
        available_styles = list_all_authors(user_id=self.user_id)

        if not project_name:
            return {
                "project_name": None,
                "author_id": None,
                "style_profile": None,
                "available_styles": available_styles,
            }

        author_id = f"{self.user_id}_{project_name}"
        style_profile = load_style_profile_from_file(author_id, user_id=self.user_id)
        return {
            "project_name": project_name,
            "author_id": author_id,
            "style_profile": style_profile,
            "available_styles": available_styles,
        }

    def _build_style_system_prompt(self, active_context: Optional[str] = None) -> str:
        """构建专用于风格问答的系统提示词。"""
        payload = self._resolve_style_payload()
        project_name = payload.get("project_name")
        author_id = payload.get("author_id")
        style_profile = payload.get("style_profile")
        available_styles = payload.get("available_styles") or []

        lines = [
            "你是 SparkArc 的 Style Agent。",
            "你的职责是基于完整风格档案回答用户关于文风、叙事、措辞、结构倾向、模仿建议、使用边界的问题。",
            "回答时必须以风格档案中的实际内容为依据，不要编造档案里不存在的结论。",
            "如果用户要求总结、解释、举例、提炼规则、给出改写建议，都可以结合风格档案进行回答。",
        ]

        if project_name:
            lines.append(f"当前项目：{project_name}")
        else:
            lines.append("当前项目：未提供")

        if style_profile is not None:
            profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)
            lines.extend([
                f"当前绑定风格档案：{author_id}",
                "以下是本次对话必须参考的完整风格档案 JSON：",
                "---STYLE_PROFILE_JSON_BEGIN---",
                profile_text,
                "---STYLE_PROFILE_JSON_END---",
                "请默认基于这份完整风格档案回答用户。若档案信息不足，再明确指出不足之处。",
            ])
        else:
            available_text = "、".join(available_styles) if available_styles else "暂无可用风格档案"
            lines.extend([
                "当前项目尚未绑定风格档案，因此你不能伪造一个风格配置。",
                f"当前用户可用风格档案：{available_text}",
                "如果用户要分析具体风格，请先提醒其在风格管理页将某个风格应用到当前项目，或先完成风格分析。",
            ])

        if active_context:
            lines.extend([
                "以下是用户当前编辑中的实时内容，可作为风格建议时的参考输入：",
                "---ACTIVE_CONTEXT_BEGIN---",
                active_context,
                "---ACTIVE_CONTEXT_END---",
            ])

        return "\n\n".join(lines)

    def _build_messages(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        active_context: Optional[str] = None,
    ):
        messages = [SystemMessage(content=self._build_style_system_prompt(active_context=active_context))]

        if history:
            for msg in history[-10:]:
                role = msg.get("role")
                content = msg.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    messages.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    messages.append(AIMessage(content=str(content)))

        messages.append(HumanMessage(content=user_message))
        return messages

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None) -> str:
        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            response = self.llm.invoke(self._build_messages(user_message, history=history, active_context=active_context))
            response_text = extract_text_content_from_message(response)
            if response_text:
                return response_text
            return response.content if isinstance(response.content, str) else str(response.content)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[Agent Error] 风格对话失败: {e}"

    def chat_stream(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None):
        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            for chunk in self.llm.stream(self._build_messages(user_message, history=history, active_context=active_context)):
                reasoning = extract_reasoning_text_from_message(chunk)
                if reasoning:
                    yield {"event": "reasoning_delta", "text": reasoning}

                content = extract_text_content_from_message(chunk)
                if content:
                    yield {"event": "assistant_delta", "text": content}
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": str(e)}
