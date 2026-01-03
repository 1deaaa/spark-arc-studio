"""
Token 用量提取器

从 LangChain 的 ChatResult 和 Chunk 中提取 token 使用量。
支持多种 API 响应格式：
- OpenAI / Azure OpenAI
- Google Gemini  
- Anthropic Claude
- OpenAI 兼容 API（DeepSeek、Qwen/通义千问、GLM 等）

LangChain 已将各厂商的 token 统计标准化到 message.usage_metadata：
- input_tokens：输入 token 数
- output_tokens：输出 token 数
- total_tokens：总 token 数

注意：OpenAI/Azure OpenAI 流式模式默认不返回 token 统计，
需要设置 stream_usage=True（已在 builder.py 中处理）。
"""

from typing import Any, Dict, Optional


def extract_usage_from_result(result: Any) -> Dict[str, int]:
    """
    从 ChatResult 中提取 token 使用量。
    
    Args:
        result: LangChain ChatResult 对象
        
    Returns:
        {"prompt_tokens": int, "completion_tokens": int}
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    
    # 方法1: 从 llm_output 获取（OpenAI 兼容 API 的传统格式）
    if hasattr(result, "llm_output") and result.llm_output:
        extracted = _extract_from_dict(result.llm_output)
        if extracted["prompt_tokens"] or extracted["completion_tokens"]:
            return extracted
    
    # 方法2: 从 generation.message 获取（LangChain 标准格式）
    if hasattr(result, "generations") and result.generations:
        gen = result.generations[0]
        if hasattr(gen, "message"):
            msg = gen.message
            extracted = _extract_from_message(msg)
            if extracted["prompt_tokens"] or extracted["completion_tokens"]:
                return extracted
    
    return usage


def extract_usage_from_chunk(chunk: Any) -> Dict[str, int]:
    """
    从流式 Chunk 中提取 token 使用量。
    
    大多数 API 在最后一个 chunk 返回完整的 token 统计。
    
    Args:
        chunk: LangChain ChatGenerationChunk 对象
        
    Returns:
        {"prompt_tokens": int, "completion_tokens": int}
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    
    if not hasattr(chunk, "message"):
        return usage
    
    msg = chunk.message
    return _extract_from_message(msg)


def _extract_from_message(msg: Any) -> Dict[str, int]:
    """
    从 Message 对象中提取 token 使用量。
    
    尝试以下位置：
    1. message.usage_metadata（LangChain 标准，所有主流模型都支持）
    2. message.response_metadata.usage（某些 API 的备选位置）
    3. message.response_metadata 顶层字段
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    
    # 位置1: usage_metadata（LangChain 标准格式）
    # 支持：OpenAI、Azure、Gemini、Claude、DeepSeek、Qwen、GLM 等
    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
        meta = msg.usage_metadata
        # LangChain 标准字段名
        usage["prompt_tokens"] = _safe_get_attr(meta, "input_tokens", 0)
        usage["completion_tokens"] = _safe_get_attr(meta, "output_tokens", 0)
        if usage["prompt_tokens"] or usage["completion_tokens"]:
            return usage
    
    # 位置2: response_metadata（备选位置）
    if hasattr(msg, "response_metadata") and msg.response_metadata:
        resp_meta = msg.response_metadata
        if isinstance(resp_meta, dict):
            extracted = _extract_from_dict(resp_meta)
            if extracted["prompt_tokens"] or extracted["completion_tokens"]:
                return extracted
    
    return usage


def _extract_from_dict(data: Dict[str, Any]) -> Dict[str, int]:
    """
    从字典中提取 token 使用量。
    
    支持多种格式：
    - token_usage.prompt_tokens / completion_tokens（OpenAI 传统格式）
    - usage.prompt_tokens / completion_tokens（某些 API）
    - usage.input_tokens / output_tokens（LangChain 标准）
    - 顶层的 prompt_tokens / input_tokens 等
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    
    # 检查 token_usage 子对象（OpenAI 传统格式）
    token_usage = data.get("token_usage", {})
    if token_usage:
        usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0) or 0
        usage["completion_tokens"] = token_usage.get("completion_tokens", 0) or 0
        if usage["prompt_tokens"] or usage["completion_tokens"]:
            return usage
    
    # 检查 usage 子对象
    usage_obj = data.get("usage", {})
    if usage_obj:
        # 尝试 OpenAI 格式字段名
        pt = usage_obj.get("prompt_tokens") or usage_obj.get("input_tokens") or 0
        ct = usage_obj.get("completion_tokens") or usage_obj.get("output_tokens") or 0
        if pt or ct:
            return {"prompt_tokens": int(pt), "completion_tokens": int(ct)}
    
    # 检查顶层字段
    prompt_keys = ["prompt_tokens", "input_tokens", "promptTokens", "inputTokens"]
    completion_keys = ["completion_tokens", "output_tokens", "completionTokens", "outputTokens"]
    
    for key in prompt_keys:
        if key in data and data[key]:
            usage["prompt_tokens"] = int(data[key])
            break
    
    for key in completion_keys:
        if key in data and data[key]:
            usage["completion_tokens"] = int(data[key])
            break
    
    return usage


def _safe_get_attr(obj: Any, attr: str, default: int = 0) -> int:
    """安全获取对象属性，返回整数值"""
    val = getattr(obj, attr, None)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default