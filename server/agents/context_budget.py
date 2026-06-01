"""聊天上下文 token 预算与自动压缩。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from llm.agen_matchbox.estimate_tokens import estimate_tokens


CHAT_HISTORY_FETCH_LIMIT = 200


@dataclass(slots=True)
class ContextBudgetResult:
    messages: List[BaseMessage]
    compacted: bool = False
    original_tokens: int = 0
    compacted_tokens: int = 0
    retained_messages: int = 0


def _coerce_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


def _history_to_messages(history: List[Dict[str, Any]] | None) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for msg in history or []:
        role = str(msg.get("role") or "").strip()
        content = _coerce_content(msg.get("content")).strip()
        if not content:
            continue
        metadata = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
        if role == "system" and metadata.get("kind") == "context_summary":
            messages = [SystemMessage(content=(
                "【已手动压缩的早期上下文】\n"
                "以下内容是用户手动触发上下文压缩后生成的内部交接摘要，"
                "请把它视为此前对话事实与工作进度，不要向用户解释压缩过程。\n"
                f"{content}"
            ))]
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _message_text(message: BaseMessage) -> str:
    role = getattr(message, "type", "") or message.__class__.__name__
    return f"{role}: {_coerce_content(getattr(message, 'content', ''))}"


def _message_type(message: BaseMessage) -> str:
    return str(getattr(message, "type", "") or "").strip().lower()


def _has_tool_calls(message: BaseMessage) -> bool:
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        return True
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict) and additional_kwargs.get("tool_calls"):
        return True
    return False


def _repair_tool_boundary(body_messages: List[BaseMessage], retained_messages: List[BaseMessage]) -> List[BaseMessage]:
    """避免预算裁剪把 AI 工具调用与 ToolMessage 响应切开。"""
    if not retained_messages:
        return retained_messages

    start = max(0, len(body_messages) - len(retained_messages))
    while start > 0 and _message_type(body_messages[start]) == "tool":
        start -= 1
    if start > 0 and _message_type(body_messages[start - 1]) in {"ai", "assistant"} and _has_tool_calls(body_messages[start - 1]):
        start -= 1
    return list(body_messages[start:])


def _drop_oldest_message_unit(messages: List[BaseMessage]) -> None:
    """按工具调用单元丢弃最老消息，避免留下孤立 ToolMessage。"""
    if not messages:
        return
    first_type = _message_type(messages[0])
    if first_type == "tool":
        while messages and _message_type(messages[0]) == "tool":
            messages.pop(0)
        return
    if first_type in {"ai", "assistant"} and _has_tool_calls(messages[0]):
        messages.pop(0)
        while messages and _message_type(messages[0]) == "tool":
            messages.pop(0)
        return
    messages.pop(0)


def _messages_tokens(messages: List[BaseMessage], model_name: str | None) -> int:
    if not messages:
        return 0
    return estimate_tokens("\n\n".join(_message_text(m) for m in messages), model=model_name)


def _messages_to_history_items(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for message in messages:
        msg_type = getattr(message, "type", "") or ""
        role = "assistant" if msg_type in {"ai", "assistant"} else "user"
        items.append({"role": role, "content": _coerce_content(getattr(message, "content", ""))})
    return items


def _get_model_name(llm_client: Any) -> str:
    usage = getattr(llm_client, "usage", None)
    return str(getattr(usage, "model_name", "") or getattr(llm_client, "model_name", "") or "").strip()


def _get_limits(llm_client: Any) -> tuple[int, int]:
    max_context = int(getattr(llm_client, "max_context_tokens", 0) or 100000)
    max_output = int(getattr(llm_client, "max_output_tokens", 0) or 4096)
    return max(max_context, 8192), max(max_output, 1024)


def _budget_limits(max_context: int, max_output: int) -> tuple[int, int]:
    reserved_output = min(max_output, max(4096, int(max_context * 0.25)))
    safety_margin = max(4096, int(max_context * 0.05))
    hard_budget = max(4096, max_context - reserved_output - safety_margin)
    trigger_budget = max(4096, int(max_context * 0.85))
    return hard_budget, trigger_budget


def _append_event(emit_event: Callable[[Dict[str, Any]], None] | None, payload: Dict[str, Any]) -> None:
    if emit_event is None:
        return
    try:
        emit_event(payload)
    except Exception:
        pass


def _emit_started(
    emit_event: Callable[[Dict[str, Any]], None] | None,
    *,
    original_tokens: int,
    model_name: str,
    retained_messages: int,
    reason: str,
) -> None:
    _append_event(emit_event, {
        "event": "context_compaction_started",
        "original_tokens": original_tokens,
        "model": model_name,
        "retained_messages": retained_messages,
        "reason": reason,
    })


def _emit_finished(
    emit_event: Callable[[Dict[str, Any]], None] | None,
    *,
    original_tokens: int,
    compacted_tokens: int,
    retained_messages: int,
    model_name: str,
) -> None:
    _append_event(emit_event, {
        "event": "context_compaction_finished",
        "original_tokens": original_tokens,
        "compacted_tokens": compacted_tokens,
        "retained_messages": retained_messages,
        "model": model_name,
    })


def _emit_failed(
    emit_event: Callable[[Dict[str, Any]], None] | None,
    *,
    original_tokens: int,
    compacted_tokens: int,
    retained_messages: int,
    model_name: str,
    error: Exception,
) -> None:
    _append_event(emit_event, {
        "event": "context_compaction_failed",
        "original_tokens": original_tokens,
        "compacted_tokens": compacted_tokens,
        "retained_messages": retained_messages,
        "model": model_name,
        "message": str(error),
    })


def _emit_context_window_stats(
    emit_event: Callable[[Dict[str, Any]], None] | None,
    *,
    agent_id: str,
    original_tokens: int,
    input_tokens: int,
    retained_messages: int,
    model_name: str,
    max_context_tokens: int,
    max_output_tokens: int,
    hard_budget: int,
    trigger_budget: int,
    compacted: bool,
    reason: str,
) -> None:
    _append_event(emit_event, {
        "event": "context_window_stats",
        "agent_id": agent_id,
        "source_agent": agent_id,
        "input_tokens": max(int(input_tokens or 0), 0),
        "original_tokens": max(int(original_tokens or 0), 0),
        "retained_messages": max(int(retained_messages or 0), 0),
        "model": model_name,
        "max_context_tokens": max_context_tokens,
        "max_output_tokens": max_output_tokens,
        "hard_budget": hard_budget,
        "trigger_budget": trigger_budget,
        "compacted": bool(compacted),
        "reason": reason,
    })


def _compress_history_items(
    *,
    user_id: str,
    project_name: str,
    agent_id: str,
    model_name: str,
    target_tokens: int,
    current_user_message: str,
    overflow_messages: List[BaseMessage],
) -> SystemMessage:
    from agents.utility_agent import UtilityAgent

    utility = UtilityAgent(user_id=user_id, project_name=project_name)
    summary = utility.compress_chat_history(
        history_items=_messages_to_history_items(overflow_messages),
        agent_id=agent_id,
        model_name=model_name,
        target_tokens=target_tokens,
        current_user_message=current_user_message,
    )
    return SystemMessage(content=(
        "【已压缩的早期上下文】\n"
        "以下内容是系统为避免上下文窗口溢出而生成的内部交接摘要，"
        "请把它视为此前对话事实与工作进度，不要向用户解释压缩过程。\n"
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
    ))


def prepare_chat_messages_with_budget(
    *,
    user_id: str,
    project_name: str,
    agent_id: str,
    system_instruction: str,
    history: List[Dict[str, Any]] | None,
    user_message: str,
    llm_client: Any,
    emit_event: Callable[[Dict[str, Any]], None] | None = None,
) -> ContextBudgetResult:
    """构造聊天 messages，并在超过模型预算时自动压缩早期历史。"""
    model_name = _get_model_name(llm_client)
    max_context, max_output = _get_limits(llm_client)
    hard_budget, trigger_budget = _budget_limits(max_context, max_output)

    system_msg = SystemMessage(content=system_instruction)
    current_msg = HumanMessage(content=user_message)
    history_messages = _history_to_messages(history)
    full_messages = [system_msg, *history_messages, current_msg]
    original_tokens = _messages_tokens(full_messages, model_name)
    if original_tokens <= hard_budget and original_tokens <= trigger_budget:
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=original_tokens,
            retained_messages=len(history_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="within_budget",
        )
        return ContextBudgetResult(full_messages, False, original_tokens, original_tokens, len(history_messages))

    base_tokens = _messages_tokens([system_msg, current_msg], model_name)
    summary_reserved = min(12000, max(2048, int(hard_budget * 0.2)))
    recent_budget = max(1024, hard_budget - base_tokens - summary_reserved)

    retained_reversed: List[BaseMessage] = []
    retained_tokens = 0
    for message in reversed(history_messages):
        cost = _messages_tokens([message], model_name)
        if retained_reversed and retained_tokens + cost > recent_budget:
            break
        retained_reversed.append(message)
        retained_tokens += cost

    retained_messages = list(reversed(retained_reversed))
    overflow_count = max(0, len(history_messages) - len(retained_messages))
    overflow_messages = history_messages[:overflow_count]

    if not overflow_messages:
        compacted_messages = [system_msg, *retained_messages, current_msg]
        while len(retained_messages) > 1 and _messages_tokens(compacted_messages, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted_messages = [system_msg, *retained_messages, current_msg]
        compacted_tokens = _messages_tokens(compacted_messages, model_name)
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="recent_context_trimmed",
        )
        return ContextBudgetResult(compacted_messages, False, original_tokens, compacted_tokens, len(retained_messages))

    _emit_started(
        emit_event,
        original_tokens=original_tokens,
        model_name=model_name,
        retained_messages=len(retained_messages),
        reason="context_budget_exceeded",
    )

    try:
        summary_msg = _compress_history_items(
            user_id=user_id,
            project_name=project_name,
            agent_id=agent_id,
            model_name=model_name,
            target_tokens=summary_reserved,
            current_user_message=user_message,
            overflow_messages=overflow_messages,
        )
        compacted_messages = [system_msg, summary_msg, *retained_messages, current_msg]
        while len(retained_messages) > 1 and _messages_tokens(compacted_messages, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted_messages = [system_msg, summary_msg, *retained_messages, current_msg]
        compacted_tokens = _messages_tokens(compacted_messages, model_name)
        _emit_finished(
            emit_event,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
        )
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=True,
            reason="context_compacted",
        )
        return ContextBudgetResult(compacted_messages, True, original_tokens, compacted_tokens, len(retained_messages))
    except Exception as exc:
        compacted_messages = [system_msg, *retained_messages, current_msg]
        while len(retained_messages) > 1 and _messages_tokens(compacted_messages, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted_messages = [system_msg, *retained_messages, current_msg]
        compacted_tokens = _messages_tokens(compacted_messages, model_name)
        _emit_failed(
            emit_event,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            error=exc,
        )
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="context_compaction_failed",
        )
        return ContextBudgetResult(compacted_messages, False, original_tokens, compacted_tokens, len(retained_messages))


def rebudget_existing_messages(
    *,
    user_id: str,
    project_name: str,
    agent_id: str,
    messages: List[BaseMessage],
    llm_client: Any,
    emit_event: Callable[[Dict[str, Any]], None] | None = None,
    current_user_message: str = "",
) -> ContextBudgetResult:
    """对已经进入多轮工具循环的 LangChain messages 再做一次预算压缩。"""
    if len(messages) <= 2:
        model_name = _get_model_name(llm_client)
        max_context, max_output = _get_limits(llm_client)
        hard_budget, trigger_budget = _budget_limits(max_context, max_output)
        tokens = _messages_tokens(messages, model_name)
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=tokens,
            input_tokens=tokens,
            retained_messages=max(0, len(messages) - 1),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="within_budget",
        )
        return ContextBudgetResult(messages, False, tokens, tokens, max(0, len(messages) - 1))

    model_name = _get_model_name(llm_client)
    max_context, max_output = _get_limits(llm_client)
    hard_budget, trigger_budget = _budget_limits(max_context, max_output)
    original_tokens = _messages_tokens(messages, model_name)
    if original_tokens <= hard_budget and original_tokens <= trigger_budget:
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=original_tokens,
            retained_messages=max(0, len(messages) - 1),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="within_budget",
        )
        return ContextBudgetResult(messages, False, original_tokens, original_tokens, max(0, len(messages) - 1))

    system_msg = messages[0]
    body_messages = messages[1:]
    base_tokens = _messages_tokens([system_msg], model_name)
    summary_reserved = min(12000, max(2048, int(hard_budget * 0.2)))
    recent_budget = max(1024, hard_budget - base_tokens - summary_reserved)

    retained_reversed: List[BaseMessage] = []
    retained_tokens = 0
    for message in reversed(body_messages):
        cost = _messages_tokens([message], model_name)
        if retained_reversed and retained_tokens + cost > recent_budget:
            break
        retained_reversed.append(message)
        retained_tokens += cost

    retained_messages = _repair_tool_boundary(body_messages, list(reversed(retained_reversed)))

    overflow_count = max(0, len(body_messages) - len(retained_messages))
    overflow_messages = body_messages[:overflow_count]
    if not overflow_messages:
        compacted = [system_msg, *retained_messages]
        while len(retained_messages) > 2 and _messages_tokens(compacted, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted = [system_msg, *retained_messages]
        compacted_tokens = _messages_tokens(compacted, model_name)
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="recent_context_trimmed",
        )
        return ContextBudgetResult(compacted, False, original_tokens, compacted_tokens, len(retained_messages))

    _emit_started(
        emit_event,
        original_tokens=original_tokens,
        model_name=model_name,
        retained_messages=len(retained_messages),
        reason="tool_loop_context_budget_exceeded",
    )

    try:
        summary_msg = _compress_history_items(
            user_id=user_id,
            project_name=project_name,
            agent_id=agent_id,
            model_name=model_name,
            target_tokens=summary_reserved,
            current_user_message=current_user_message,
            overflow_messages=overflow_messages,
        )
        compacted = [system_msg, summary_msg, *retained_messages]
        while len(retained_messages) > 2 and _messages_tokens(compacted, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted = [system_msg, summary_msg, *retained_messages]
        compacted_tokens = _messages_tokens(compacted, model_name)
        _emit_finished(
            emit_event,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
        )
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=True,
            reason="tool_loop_context_compacted",
        )
        return ContextBudgetResult(compacted, True, original_tokens, compacted_tokens, len(retained_messages))
    except Exception as exc:
        compacted = [system_msg, *retained_messages]
        while len(retained_messages) > 2 and _messages_tokens(compacted, model_name) > hard_budget:
            _drop_oldest_message_unit(retained_messages)
            compacted = [system_msg, *retained_messages]
        compacted_tokens = _messages_tokens(compacted, model_name)
        _emit_failed(
            emit_event,
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            error=exc,
        )
        _emit_context_window_stats(
            emit_event,
            agent_id=agent_id,
            original_tokens=original_tokens,
            input_tokens=compacted_tokens,
            retained_messages=len(retained_messages),
            model_name=model_name,
            max_context_tokens=max_context,
            max_output_tokens=max_output,
            hard_budget=hard_budget,
            trigger_budget=trigger_budget,
            compacted=False,
            reason="tool_loop_context_compaction_failed",
        )
        return ContextBudgetResult(compacted, False, original_tokens, compacted_tokens, len(retained_messages))
