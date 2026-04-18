"""
语义分块基类与策略注册表

每种文件格式对应一个 ChunkStrategy 子类，
通过 register_strategy() 注册到全局注册表，
SemanticChunker 按注册的策略分块，超长段自动二次切分。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from story.project_files import ProjectFile


# ==================== 语义分块结果 ====================

@dataclass
class SemanticChunk:
    """语义分块结果（正则搜索和向量检索共用）"""
    text: str               # 块文本
    metadata: dict = field(default_factory=dict)  # 元数据（source, format_key, narrative_ref, chapter_idx 等）
    start_line: int = 0     # 起始行号（1-based）
    end_line: int = 0       # 结束行号
    narrative_ref: str = "" # 叙事定位文本（预计算）
    char_count: int = 0     # 字符数

    def __post_init__(self):
        if self.char_count == 0 and self.text:
            self.char_count = len(self.text)


# ==================== 策略基类 ====================

class ChunkStrategy(ABC):
    """分块策略基类"""

    @property
    @abstractmethod
    def format_key(self) -> str:
        """格式标识，如 'outline', 'arc', 'novel'"""

    @abstractmethod
    def chunk(self, project_file: ProjectFile, outline_data: dict) -> list[SemanticChunk]:
        """对单个文件执行分块"""


# ==================== 全局注册表 ====================

_STRATEGY_REGISTRY: dict[str, ChunkStrategy] = {}


def register_strategy(strategy: ChunkStrategy) -> None:
    """注册一个分块策略"""
    _STRATEGY_REGISTRY[strategy.format_key] = strategy


def get_strategy(format_key: str) -> Optional[ChunkStrategy]:
    """获取指定格式的分块策略"""
    return _STRATEGY_REGISTRY.get(format_key)


def list_strategies() -> list[str]:
    """列出所有已注册的格式 key"""
    return list(_STRATEGY_REGISTRY.keys())
