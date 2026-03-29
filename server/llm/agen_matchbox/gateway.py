"""轻量 LLM 客户端网关，不依赖 manager/数据库。"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .env_utils import get_env_var
from .reasoning_compat import extract_reasoning_text_from_chat_delta


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
