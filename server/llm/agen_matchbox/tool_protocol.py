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


def _schema_ref(schema: Any, definitions: Dict[str, Any]) -> Any:
    """解析 Pydantic JSON Schema 中的本地引用。"""
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not (
        ref.startswith("#/$defs/") or ref.startswith("#/definitions/")
    ):
        return schema
    return definitions.get(ref.rsplit("/", 1)[-1], schema)


def _schema_variants(schema: Any, definitions: Dict[str, Any]) -> list[Dict[str, Any]]:
    """展开联合类型，保留所有可能的结构分支。"""
    resolved = _schema_ref(schema, definitions)
    if not isinstance(resolved, dict):
        return []
    variants: list[Dict[str, Any]] = []
    for key in ("anyOf", "oneOf"):
        values = resolved.get(key)
        if isinstance(values, list):
            for value in values:
                variants.extend(_schema_variants(value, definitions) or ([value] if isinstance(value, dict) else []))
            return variants
    return [resolved]


def _schema_has_type(schema: Any, expected: str, definitions: Dict[str, Any]) -> bool:
    """判断 Schema 是否允许指定结构类型。"""
    for variant in _schema_variants(schema, definitions):
        schema_type = variant.get("type")
        if schema_type == expected or (isinstance(schema_type, list) and expected in schema_type):
            return True
        if expected == "object" and isinstance(variant.get("properties"), dict):
            return True
        if expected == "object" and isinstance(variant.get("additionalProperties"), (dict, bool)):
            return True
        if expected == "array" and isinstance(variant.get("items"), dict):
            return True
    return False


def _select_schema_for_value(schema: Any, value: Any, definitions: Dict[str, Any]) -> Dict[str, Any]:
    """从联合类型中选择与当前值形状最匹配的分支。"""
    variants = _schema_variants(schema, definitions)
    if not variants:
        return {}
    wanted = "array" if isinstance(value, list) else "object" if isinstance(value, dict) else None
    if wanted:
        for variant in variants:
            if variant.get("type") == wanted or (
                wanted == "object" and isinstance(variant.get("properties"), dict)
            ) or (
                wanted == "array" and isinstance(variant.get("items"), dict)
            ):
                return variant
    for variant in variants:
        if variant.get("type") != "null":
            return variant
    return variants[0]


def _try_parse_structured_value(value: Any) -> Any:
    """仅尝试把字符串解码为 JSON 值，失败时返回原值。"""
    if not isinstance(value, str) or not value.strip():
        return value
    text = value.strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def _normalize_value_by_schema(value: Any, schema: Any, definitions: Dict[str, Any]) -> Any:
    """按照 Schema 递归解包模型错误地二次序列化的对象和数组。"""
    variants = _schema_variants(schema, definitions)
    if not variants:
        return value

    if isinstance(value, str) and _schema_has_type(schema, "object", definitions):
        value = _try_parse_structured_value(value)
    elif isinstance(value, str) and _schema_has_type(schema, "array", definitions):
        value = _try_parse_structured_value(value)

    selected = _select_schema_for_value(schema, value, definitions)
    selected = _schema_ref(selected, definitions)
    if not isinstance(selected, dict):
        return value
    selected_type = selected.get("type")
    is_object = selected_type == "object" or (isinstance(selected_type, list) and "object" in selected_type)
    is_array = selected_type == "array" or (isinstance(selected_type, list) and "array" in selected_type)

    if isinstance(value, dict) and (
        is_object
        or isinstance(selected.get("properties"), dict)
        or "additionalProperties" in selected
    ):
        properties = selected.get("properties") if isinstance(selected.get("properties"), dict) else {}
        additional = selected.get("additionalProperties")
        normalized = dict(value)
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                normalized[key] = _normalize_value_by_schema(item, child_schema, definitions)
        return normalized

    if isinstance(value, list) and (
        is_array or isinstance(selected.get("items"), dict)
    ):
        item_schema = selected.get("items")
        if isinstance(item_schema, dict):
            return [_normalize_value_by_schema(item, item_schema, definitions) for item in value]
    return value


def _args_schema_json(schema: Any) -> Dict[str, Any]:
    """读取 LangChain/Pydantic 参数模型的 JSON Schema。"""
    if schema is None:
        return {}
    if isinstance(schema, dict):
        return schema
    model_json_schema = getattr(schema, "model_json_schema", None)
    if callable(model_json_schema):
        try:
            payload = model_json_schema()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
    schema_method = getattr(schema, "schema", None)
    if callable(schema_method):
        try:
            payload = schema_method()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            pass
    return {}


def normalize_tool_args(
    tool_args: Any,
    *,
    tool: Any = None,
    args_schema: Any = None,
) -> Dict[str, Any]:
    """按工具参数 Schema 解包结构字段，普通字符串字段保持原样。"""
    if isinstance(tool_args, dict):
        normalized = dict(tool_args)
    else:
        normalized = _parse_args(tool_args)
    if not isinstance(normalized, dict):
        return {}

    schema_model = args_schema
    if schema_model is None and tool is not None:
        schema_model = getattr(tool, "args_schema", None)
    schema = _args_schema_json(schema_model)
    if not schema:
        return normalized

    definitions = schema.get("$defs") or schema.get("definitions") or {}
    return _normalize_value_by_schema(normalized, schema, definitions)


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
    tool_lookup: Callable[[str], Any] | Dict[str, Any] | None = None,
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
        tool = None
        if callable(tool_lookup):
            try:
                tool = tool_lookup(tool_name)
            except Exception:
                tool = None
        elif isinstance(tool_lookup, dict):
            tool = tool_lookup.get(tool_name)
        tool_args = normalize_tool_args(tool_args, tool=tool)

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
