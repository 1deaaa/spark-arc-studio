# 风格分析 Agent 包
# 重构后只保留 UnifiedStyleAnalyzer。
# 旧的多 Agent 并行 JSON 框架(StyleAnalysisAgent / ValidatorAgent / CoordinatorAgent)
# 在 Markdown 化之后已废弃,如需历史参考请查阅 _old/ 目录。

from ..unified_analyzer import UnifiedStyleAnalyzer

__all__ = [
    "UnifiedStyleAnalyzer",
]
