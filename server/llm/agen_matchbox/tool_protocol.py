"""OpenAI Compatible 工具消息协议的统一规范化与校验底座。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Dict

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


class ToolMessageProtocolError(ValueError):
    """工具调用消息历史不满足 OpenAI Compatible 闭合协议。"""


def tool_call_as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            dumped = method()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    try:
        return dict(value)
    except Exception:
        return {}


def extract_tool_call_id(tool_call: Any) -> str:
    call = tool_call_as_dict(tool_call)
    function = tool_call_as_dict(call.get("function") or getattr(tool_call, "function", None))
    return str(
        call.get("id")
        or getattr(tool_call, "id", None)
        or function.get("id")
        or ""
    )


def extract_tool_name(tool_call: Any) -> str:
    call = tool_call_as_dict(tool_call)
    function_obj = call.get("function") or getattr(tool_call, "function", None)
    function = tool_call_as_dict(function_obj)
    return str(
        call.get("name")
        or getattr(tool_call, "name", None)
        or function.get("name")
        or getattr(function_obj, "name", None)
        or ""
    )


def _parse_args(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    text = value.strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        candidates.append(text[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def extract_tool_args(tool_call: Any) -> Dict[str, Any]:
    call = tool_call_as_dict(tool_call)
    function_obj = call.get("function") or getattr(tool_call, "function", None)
    function = tool_call_as_dict(function_obj)
    for value in (
        call.get("args"),
        getattr(tool_call, "args", None),
        call.get("arguments"),
        getattr(tool_call, "arguments", None),
        function.get("arguments"),
        getattr(function_obj, "arguments", None),
    ):
        parsed = _parse_args(value)
        if parsed:
            return parsed
        if isinstance(value, dict):
            return value
    return {}


def _tool_spec_has_args(spec: Dict[str, Any]) -> bool:
    args = spec.get("args")
    return isinstance(args, dict) and any(value is not None for value in args.values())


def dedupe_tool_specs(items: Sequence[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """合并 SDK 在多个字段中重复暴露的同一工具调用。"""
    deduped: Dict[str, Dict[str, Any]] = {}
    ordered_keys: list[str] = []
    for fallback_index, item in enumerate(items):
        raw = item.get("raw")
        item_index = item.get("index")
        key = (
            extract_tool_call_id(raw)
            or f"{item.get('name') or 'unknown_tool'}::{item_index if item_index is not None else fallback_index}"
        )
        if key not in deduped:
            deduped[key] = dict(item)
            ordered_keys.append(key)
        elif _tool_spec_has_args(item) and not _tool_spec_has_args(deduped[key]):
            deduped[key] = dict(item)
    return [deduped[key] for key in ordered_keys]


def extract_tool_specs_from_message(message: Any) -> list[Dict[str, Any]]:
    """从 LangChain/OpenAI 兼容消息的所有常见字段提取工具调用。"""
    items: list[Dict[str, Any]] = []

    def _append(values: Any) -> None:
        if not isinstance(values, list):
            return
        for index, raw in enumerate(values):
            items.append({
                "raw": raw,
                "name": extract_tool_name(raw),
                "args": extract_tool_args(raw),
                "index": index,
            })

    _append(getattr(message, "tool_calls", None) or [])
    _append(getattr(message, "invalid_tool_calls", None) or [])
    additional = getattr(message, "additional_kwargs", None) or {}
    if isinstance(additional, dict):
        _append(additional.get("tool_calls") or [])
        function_call = additional.get("function_call")
        if function_call:
            raw = {"function": function_call, "type": "tool_call"}
            items.append({
                "raw": raw,
                "name": extract_tool_name(raw),
                "args": extract_tool_args(raw),
                "index": 0,
            })
    return dedupe_tool_specs(items)


def prepare_tool_specs_for_execution(
    tool_specs: Sequence[Dict[str, Any]],
    *,
    normalize_name: Callable[[str], str] | None = None,
) -> list[Dict[str, Any]]:
    """为工具执行与消息历史生成同一组稳定、唯一的调用 ID。"""
    normalize = normalize_name or (lambda value: value)
    prepared: list[Dict[str, Any]] = []
    used_call_ids: set[str] = set()
    for index, spec in enumerate(tool_specs):
        item = dict(spec)
        tool_name = normalize(str(
            item.get("name") or extract_tool_name(item.get("raw")) or "unknown_tool"
        ))
        tool_args = item.get("args")
        if not isinstance(tool_args, dict):
            tool_args = extract_tool_args(item.get("raw"))
        if not isinstance(tool_args, dict):
            tool_args = {}

        call_id = extract_tool_call_id(item.get("raw")).strip()
        if not call_id or call_id in used_call_ids:
            call_id = f"call_{uuid.uuid4().hex}"
        used_call_ids.add(call_id)
        item.update({
            "raw": {
                "id": call_id,
                "name": tool_name,
                "args": tool_args,
                "type": "tool_call",
            },
            "name": tool_name,
            "args": tool_args,
            "call_id": call_id,
            "index": item.get("index", index),
        })
        prepared.append(item)
    return prepared


def build_tool_history_message(message: Any, tool_specs: Sequence[Dict[str, Any]]) -> AIMessage:
    """重建 assistant 工具消息，只声明实际进入执行链的调用。"""
    additional_kwargs = dict(getattr(message, "additional_kwargs", None) or {})
    additional_kwargs.pop("tool_calls", None)
    additional_kwargs.pop("function_call", None)
    message_kwargs: Dict[str, Any] = {
        "content": getattr(message, "content", "") or "",
        "additional_kwargs": additional_kwargs,
        "tool_calls": [dict(spec["raw"]) for spec in tool_specs],
    }
    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        message_kwargs["response_metadata"] = dict(response_metadata)
    for field_name in ("name", "id", "usage_metadata"):
        field_value = getattr(message, field_name, None)
        if field_value is not None:
            message_kwargs[field_name] = field_value
    return AIMessage(**message_kwargs)


def build_tool_result_messages(
    results: Iterable[tuple[str, str, Any]],
) -> list[ToolMessage]:
    """把执行结果转换为与规范调用 ID 一一对应的 ToolMessage。"""
    return [
        ToolMessage(content=str(result or ""), tool_call_id=call_id, name=tool_name)
        for call_id, tool_name, result in results
    ]


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or "").strip().lower()
    msg_type = str(getattr(message, "type", "") or "").strip().lower()
    return {
        "ai": "assistant",
        "human": "user",
    }.get(msg_type, msg_type)


def _assistant_tool_call_ids(message: Any) -> list[str]:
    if isinstance(message, dict):
        calls = message.get("tool_calls") or []
    else:
        calls = getattr(message, "tool_calls", None) or []
        if not calls:
            additional = getattr(message, "additional_kwargs", None) or {}
            calls = additional.get("tool_calls") or [] if isinstance(additional, dict) else []
    return [extract_tool_call_id(call).strip() for call in calls]


def _tool_message_call_id(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("tool_call_id") or "").strip()
    return str(getattr(message, "tool_call_id", "") or "").strip()


def validate_tool_message_history(messages: Sequence[Any]) -> None:
    """确保每组 assistant tool_calls 在下一条普通消息前完整闭合。"""
    pending: set[str] = set()
    declared_at = -1
    for index, message in enumerate(messages):
        role = _message_role(message)
        if pending:
            if role != "tool":
                missing = ", ".join(sorted(pending))
                raise ToolMessageProtocolError(
                    f"第 {declared_at + 1} 条 assistant 工具调用缺少响应：{missing}；"
                    f"第 {index + 1} 条消息已进入 {role or 'unknown'}。"
                )
            call_id = _tool_message_call_id(message)
            if not call_id:
                raise ToolMessageProtocolError(f"第 {index + 1} 条 tool 消息缺少 tool_call_id。")
            if call_id not in pending:
                raise ToolMessageProtocolError(
                    f"第 {index + 1} 条 tool 消息响应了未声明或已完成的调用：{call_id}。"
                )
            pending.remove(call_id)
            continue

        if role == "tool":
            call_id = _tool_message_call_id(message) or "<empty>"
            raise ToolMessageProtocolError(
                f"第 {index + 1} 条 tool 消息没有对应的 assistant 工具调用：{call_id}。"
            )
        if role != "assistant":
            continue
        call_ids = _assistant_tool_call_ids(message)
        if not call_ids:
            continue
        if any(not call_id for call_id in call_ids):
            raise ToolMessageProtocolError(f"第 {index + 1} 条 assistant 消息包含空 tool_call id。")
        if len(call_ids) != len(set(call_ids)):
            raise ToolMessageProtocolError(f"第 {index + 1} 条 assistant 消息包含重复 tool_call id。")
        pending = set(call_ids)
        declared_at = index

    if pending:
        missing = ", ".join(sorted(pending))
        raise ToolMessageProtocolError(
            f"第 {declared_at + 1} 条 assistant 工具调用在消息结尾仍缺少响应：{missing}。"
        )

