# 风格分析 Agent 包
# 重构后只保留 UnifiedStyleAnalyzer。
# 旧的多 Agent 并行 JSON 框架(StyleAnalysisAgent / ValidatorAgent / CoordinatorAgent)
# 文风能力统一由 agent_style 服务与提示词管线提供，不再维护独立 Agent 工作流。

from ..unified_analyzer import UnifiedStyleAnalyzer

__all__ = [
    "UnifiedStyleAnalyzer",
]
