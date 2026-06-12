"""轻量 LLM 客户端网关，不依赖 manager/数据库。"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .env_utils import get_env_var
from .reasoning_compat import (
    extract_metadata_reasoning_text_from_message,
    extract_reasoning_text_from_chat_delta,
    extract_reasoning_text_from_message,
)


def _env_flag_enabled(name: str, default: bool) -> bool:
    """读取布尔环境变量，支持 1/0、true/false、yes/no、on/off。"""
    raw = get_env_var(name)
    if raw is None:
        return default

    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def build_sdk_compat_headers(
    existing_headers: Optional[Mapping[str, str]] = None,
) -> Optional[Dict[str, str]]:
    """为 OpenAI 兼容网关构建请求头。"""
    headers = dict(existing_headers or {})

    if not _env_flag_enabled("SPARKARC_OPENAI_COMPAT_OVERRIDE_UA", default=True):
        return headers or None

    for key in headers.keys():
        if str(key).lower() == "user-agent":
            return headers or None

    compat_ua = get_env_var("SPARKARC_OPENAI_COMPAT_USER_AGENT", "SparkArc/1.0")
    compat_ua = (compat_ua or "SparkArc/1.0").strip() or "SparkArc/1.0"
    headers["User-Agent"] = compat_ua
    return headers


def apply_sdk_request_compat(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """统一注入 SDK 兼容参数。"""
    compat_headers = build_sdk_compat_headers(kwargs.get("default_headers"))
    if compat_headers is not None:
        kwargs["default_headers"] = compat_headers
    stream_usage_mode = str(get_env_var("SPARKARC_OPENAI_COMPAT_STREAM_USAGE", "auto") or "auto").strip().lower()
    if stream_usage_mode in {"1", "true", "yes", "on", "auto"}:
        kwargs.setdefault("stream_usage", True)
    return kwargs


class ChatUniversal(ChatOpenAI):
    """
    ChatOpenAI 子类：尽量保留各类 OpenAI 兼容网关返回的 reasoning 文本。
    
    背景：
        LangChain 1.x 的 ChatOpenAI 对 OpenAI 官方 content blocks 支持较好，
        但对很多“OpenAI 兼容”网关附加在 delta 里的非标准 reasoning 字段
        （如 `reasoning_content`、`reasoning`、`analysis`、`thinking`）会直接丢弃。
    
    方案：
        覆盖 _convert_chunk_to_generation_chunk 方法，在父类处理完毕后检查原始 delta
        中是否包含上述非标准 reasoning 字段。如有则统一注入到
        `AIMessageChunk.additional_kwargs["reasoning_content"]`。

        这样上层业务与用量统计都只依赖一个统一入口，无需关心不同中转站的命名差异。
    
    稳定性：
        相比 monkey-patch（运行时替换模块级函数），子类继承更稳健：
        - 不修改 LangChain 的任何源码
        - 如果 LangChain 升级重命名了方法，Python 会正常报错而非静默失效
        - _convert_chunk_to_generation_chunk 是实例方法，LangChain 不太可能在 1.x 内改名
    """

    def _get_request_payload(
        self,
        input_,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        payload_messages = payload.get("messages")
        if not isinstance(payload_messages, list):
            return payload

        source_messages = self._convert_input(input_).to_messages()
        for source_message, payload_message in zip(source_messages, payload_messages):
            if not isinstance(payload_message, dict):
                continue
            if payload_message.get("role") != "assistant":
                continue

            reasoning = extract_metadata_reasoning_text_from_message(source_message)
            if reasoning:
                payload_message["reasoning_content"] = reasoning

        return payload

    def _create_chat_result(self, response, generation_info: dict | None = None):
        result = super()._create_chat_result(response, generation_info=generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()
        raw_usage = response_dict.get("usage")
        if raw_usage:
            llm_output = dict(result.llm_output or {})
            llm_output["usage"] = raw_usage
            result.llm_output = llm_output
        choices = response_dict.get("choices") or []

        for generation, raw_choice in zip(result.generations, choices):
            raw_message = raw_choice.get("message") if isinstance(raw_choice, dict) else None
            reasoning = extract_reasoning_text_from_message(raw_message)
            if reasoning and hasattr(generation.message, "additional_kwargs"):
                generation.message.additional_kwargs["reasoning_content"] = reasoning

        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        result = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if result is None:
            return None

        raw_usage = chunk.get("usage")
        if raw_usage and hasattr(result.message, "response_metadata"):
            result.message.response_metadata["usage"] = raw_usage

        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            reasoning = extract_reasoning_text_from_chat_delta(delta)
            if reasoning and isinstance(reasoning, str):
                msg = result.message
                if hasattr(msg, "additional_kwargs"):
                    msg.additional_kwargs["reasoning_content"] = reasoning

        return result


def create_quick_llm(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    **kwargs: Any,
) -> ChatUniversal:
    """创建轻量 Chat 客户端，不触发 AIManager/数据库逻辑。"""
    payload = dict(kwargs)
    payload.pop("streaming", None)
    payload = apply_sdk_request_compat(payload)
    return ChatUniversal(
        base_url=base_url,
        api_key=api_key,
        model_name=model_name,
        **payload,
    )


def create_quick_embedding(
    *,
    base_url: str,
    api_key: str,
    model_name: str,
    **kwargs: Any,
) -> OpenAIEmbeddings:
    """创建轻量 Embedding 客户端，不触发 AIManager/数据库逻辑。"""
    payload = dict(kwargs)
    payload = apply_sdk_request_compat(payload)
    return OpenAIEmbeddings(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,
        **payload,
    )
