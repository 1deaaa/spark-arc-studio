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

from typing import Any, Dict, List, Optional

from core.request_context import get_current_project_name, resolve_project_name
from llm.agen_matchbox.reasoning_compat import (
    extract_reasoning_text_from_message,
    extract_text_content_from_message,
    extract_visible_text_from_plain_text,
    MessageEventStreamReasoningAdapter,
)

from .agent_style import (
    find_style_profile_by_name,
    list_style_profiles,
    load_project_style_profile,
    resolve_project_style_binding,
)
from .communication import SparkBaseAgent, is_stop_event_set
from .context_budget import prepare_chat_messages_with_budget, stream_context_budget_events
from .language_policy import prepend_prompt_language_policy
from .prompt_layout import build_current_user_message


class StyleChatAgent(SparkBaseAgent):
    """负责风格档案问答的聊天 Agent。"""

    def __init__(self, user_id: str, project_name: Optional[str] = None):
        super().__init__(agent_id="agent_style", user_id=user_id)
        self.project_name = project_name

    def _resolve_project_name(self) -> Optional[str]:
        """优先使用显式项目名，其次回退到请求上下文中的当前项目。"""
        return resolve_project_name(self.project_name, get_current_project_name())

    def _match_explicit_style_name(self, user_message: str, available_styles: List[str]) -> Optional[str]:
        text = (user_message or "").strip()
        if not text or not available_styles:
            return None

        quoted_candidates = []
        for left, right in [("《", "》"), ("【", "】"), ("[", "]"), ("\"", "\""), ("'", "'")]:
            if left in text and right in text:
                start = text.find(left)
                end = text.find(right, start + 1)
                if start >= 0 and end > start:
                    quoted = text[start + 1:end].strip()
                    if quoted:
                        quoted_candidates.append(quoted)

        styles_set = {s: s for s in available_styles}
        for candidate in quoted_candidates:
            if candidate in styles_set:
                return candidate

        matched = [name for name in available_styles if name and name in text]
        if matched:
            matched.sort(key=len, reverse=True)
            return matched[0]

        return None

    def _resolve_style_payload(self, preferred_style_name: Optional[str] = None) -> Dict[str, Any]:
        """解析当前聊天应绑定的风格档案与辅助提示信息。"""
        project_name = self._resolve_project_name()
        available_styles = [
            item["style_name"] for item in list_style_profiles(user_id=self.user_id)
        ]

        if preferred_style_name:
            explicit_record = find_style_profile_by_name(preferred_style_name, user_id=self.user_id)
            if explicit_record is not None:
                return {
                    "project_name": project_name,
                    "style_id": explicit_record["style_id"],
                    "style_name": explicit_record["style_name"],
                    "style_profile": explicit_record["style_profile"],
                    "available_styles": available_styles,
                    "source": "explicit",
                }

        if not project_name:
            return {
                "project_name": None,
                "style_id": None,
                "style_name": None,
                "style_profile": None,
                "available_styles": available_styles,
                "source": "none",
            }

        binding = resolve_project_style_binding(self.user_id, project_name)
        style_profile = load_project_style_profile(self.user_id, project_name)
        return {
            "project_name": project_name,
            "style_id": (binding or {}).get("style_id"),
            "style_name": (binding or {}).get("style_name"),
            "style_profile": style_profile,
            "available_styles": available_styles,
            "source": "project",
        }

    def _build_style_system_prompt(self, active_context: Optional[str] = None, user_message: str = "") -> str:
        """构建专用于风格问答的系统提示词。"""
        available_styles = [
            item["style_name"] for item in list_style_profiles(user_id=self.user_id)
        ]
        explicit_style_name = self._match_explicit_style_name(user_message, available_styles)
        payload = self._resolve_style_payload(preferred_style_name=explicit_style_name)
        project_name = payload.get("project_name")
        style_id = payload.get("style_id")
        style_name = payload.get("style_name")
        style_profile = payload.get("style_profile")
        available_styles = payload.get("available_styles") or []
        source = payload.get("source")

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
            profile_text = str(style_profile)
            if source == "explicit":
                lines.append("本轮对话检测到用户显式指定了风格名称，优先按该风格档案回答。")
            lines.extend([
                f"当前绑定风格档案：{style_name}（style_id: {style_id}）",
                "以下是本次对话必须参考的完整 Markdown 风格档案：",
                "---STYLE_PROFILE_BEGIN---",
                profile_text,
                "---STYLE_PROFILE_END---",
                "请默认基于这份完整风格档案回答用户。若档案信息不足，再明确指出不足之处。",
            ])
        else:
            available_text = "、".join(available_styles) if available_styles else "暂无可用风格档案"
            lines.extend([
                "当前项目尚未绑定风格档案，因此你不能伪造一个风格配置。",
                f"当前用户可用风格档案：{available_text}",
                "如果用户要分析具体风格，请先提醒其在风格管理页将某个风格应用到当前项目，或先完成风格分析。",
            ])

        return prepend_prompt_language_policy("\n\n".join(lines))

    def _build_budget_result(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        active_context: Optional[str] = None,
        emit_event=None,
    ):
        return prepare_chat_messages_with_budget(
            user_id=self.user_id,
            project_name=self.project_name or "",
            agent_id=self.agent_id,
            system_instruction=self._build_style_system_prompt(active_context=None, user_message=user_message),
            history=history,
            user_message=build_current_user_message(
                user_message=user_message,
                active_context=active_context,
            ),
            llm_client=self.llm,
            emit_event=emit_event,
        )

    def _build_messages(
        self,
        user_message: str,
        history: Optional[List[Dict[str, Any]]] = None,
        active_context: Optional[str] = None,
        emit_event=None,
    ):
        result = self._build_budget_result(
            user_message,
            history=history,
            active_context=active_context,
            emit_event=emit_event,
        )
        self._set_context_checkpoint_candidate(result.checkpoint)
        return result.messages

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None) -> str:
        self._set_context_checkpoint_candidate(None)
        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            response = self.llm.invoke(self._build_messages(user_message, history=history, active_context=active_context))
            response_text = extract_text_content_from_message(response)
            if response_text:
                return response_text
            return extract_visible_text_from_plain_text(
                response.content if isinstance(response.content, str) else str(response.content)
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            from agents.context_budget import NonRetryableChatError
            if isinstance(e, NonRetryableChatError):
                raise
            return f"[Agent Error] 风格对话失败: {e}"

    def chat_stream(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None, **kwargs):
        self._set_context_checkpoint_candidate(None)
        stop_event = kwargs.get("stop_event")
        if is_stop_event_set(stop_event):
            return

        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            stream_reasoning_adapter = MessageEventStreamReasoningAdapter()
            budget_result = yield from stream_context_budget_events(
                self._build_budget_result,
                user_message=user_message,
                history=history,
                active_context=active_context,
            )
            self._set_context_checkpoint_candidate(budget_result.checkpoint)
            messages = budget_result.messages
            for chunk in self.llm.stream(messages):
                if is_stop_event_set(stop_event):
                    return

                reasoning, content = stream_reasoning_adapter.push_message(chunk)
                if reasoning:
                    yield {"event": "reasoning_delta", "text": reasoning, "source_agent": self.agent_id}
                if content:
                    yield {"event": "assistant_delta", "text": content, "source_agent": self.agent_id}
            trailing_reasoning, trailing_content = stream_reasoning_adapter.flush()
            if is_stop_event_set(stop_event):
                return
            if trailing_reasoning:
                yield {"event": "reasoning_delta", "text": trailing_reasoning, "source_agent": self.agent_id}
            if trailing_content:
                yield {"event": "assistant_delta", "text": trailing_content, "source_agent": self.agent_id}
        except Exception as e:
            import traceback
            traceback.print_exc()
            from agents.context_budget import NonRetryableChatError
            from agents.routes.schemas import format_ai_error
            if isinstance(e, NonRetryableChatError):
                yield e.to_event()
                return
            yield {"event": "error", "data": format_ai_error(e)}

