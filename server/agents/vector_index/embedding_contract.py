"""项目语义检索的嵌入契约。

本文件只保存云端与本地后端必须共同遵守的稳定参数，避免切换后端时
悄悄改变向量空间并污染已有索引。
"""

from __future__ import annotations

from typing import Any


QWEN3_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
QWEN3_EMBEDDING_DIMENSIONS = 1024
QWEN3_EMBEDDING_MAX_CONTEXT_TOKENS = 32768
QWEN3_EMBEDDING_BATCH_SIZE = 32
QWEN3_EMBEDDING_METRIC = "cosine"
QWEN3_EMBEDDING_NORMALIZE = True
QWEN3_EMBEDDING_VERSION = "qwen3-embedding-0.6b-1024-cosine-v1"

# Qwen3 Embedding 支持 instruction-aware 检索。文档入库不加前缀，查询侧固定
# 使用中文检索任务描述，确保云端和本地后端得到同一条输入文本。
QWEN3_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def build_query_text(text: str) -> str:
    """构造稳定的查询侧输入文本。"""
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned
    return f"{QWEN3_QUERY_INSTRUCTION}{cleaned}"


def embedding_extra_body() -> dict[str, Any]:
    """返回 OpenAI 兼容嵌入请求应携带的固定参数。"""
    return {
        "dimensions": QWEN3_EMBEDDING_DIMENSIONS,
        "encoding_format": "float",
    }


def embedding_contract_metadata() -> dict[str, Any]:
    """返回写入向量索引元数据的嵌入契约。"""
    return {
        "version": QWEN3_EMBEDDING_VERSION,
        "model": QWEN3_EMBEDDING_MODEL,
        "dimensions": QWEN3_EMBEDDING_DIMENSIONS,
        "metric": QWEN3_EMBEDDING_METRIC,
        "normalize": QWEN3_EMBEDDING_NORMALIZE,
        "query_instruction": QWEN3_QUERY_INSTRUCTION,
        "max_context_tokens": QWEN3_EMBEDDING_MAX_CONTEXT_TOKENS,
    }

