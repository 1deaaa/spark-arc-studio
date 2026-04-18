"""
语义分块器包

公共接口：SemanticChunk, SemanticChunker, register_strategy, get_strategy
"""

from .base import SemanticChunk, ChunkStrategy, register_strategy, get_strategy, list_strategies
from .chunker import SemanticChunker

# 导入策略模块触发自动注册
from .strategies import register_all_strategies
register_all_strategies()

__all__ = [
    "SemanticChunk",
    "ChunkStrategy",
    "SemanticChunker",
    "register_strategy",
    "get_strategy",
    "list_strategies",
]
