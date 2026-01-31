# 风格分析 Agents 包
# 重构后使用 UnifiedStyleAnalyzer 取代原有的7个并行Agent

from .base import StyleAnalysisAgent
from .validator import ValidatorAgent
from .coordinator import CoordinatorAgent

# 新的统一分析器
from ..unified_analyzer import UnifiedStyleAnalyzer

__all__ = [
    "StyleAnalysisAgent",
    "ValidatorAgent",
    "CoordinatorAgent",
    "UnifiedStyleAnalyzer",
]

# 废弃的Agent已移至 _old 目录：
# - DialogueAgent, MonologueAgent, NarrativeAgent
# - LanguageAgent, StructureAgent, EmotionThemeAgent, CharacterPlotAgent