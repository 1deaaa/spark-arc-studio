"""
core.long_text
==============

通用"分块串行 + 末尾聚合"管线。从 agents.agent_style 的
UnifiedStyleAnalyzer 抽取的纯机械调度层，业务语义（prompt/schema）由回调注入。

典型调用方：
- agents.agent_style.UnifiedStyleAnalyzer  -> 风格指纹分析
- agents.attachment.AttachmentAnalyzer     -> 聊天附件按焦点分析（plot/characters/...）

设计原则：
- Pipeline 不懂业务，只管遍历 chunks、滚动 context_hint、末尾聚合
- 业务方通过回调（build_chunk_prompt / parse_chunk_output / build_final_prompt）
  注入各自的 prompt 与输出解析逻辑
"""

from .chunked_pipeline import (
    ChunkedLongTextPipeline,
    ChunkRunResult,
    PipelineResult,
)

__all__ = [
    "ChunkedLongTextPipeline",
    "ChunkRunResult",
    "PipelineResult",
]
