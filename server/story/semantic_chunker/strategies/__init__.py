"""
分块策略自动注册

导入所有策略模块并调用 register_all_strategies() 完成注册。
"""

from .outline_strategy import OutlineChunkStrategy
from .arc_strategy import ArcChunkStrategy
from .novel_strategy import NovelChunkStrategy
from .heading_strategy import HeadingChunkStrategy
from .character_strategy import CharacterChunkStrategy
from .chrbind_strategy import ChrBindChunkStrategy

from ..base import register_strategy


def register_all_strategies():
    """注册所有内置分块策略"""
    register_strategy(OutlineChunkStrategy())
    register_strategy(ArcChunkStrategy())
    register_strategy(NovelChunkStrategy())
    # heading_strategy 支持三种 format_key
    heading = HeadingChunkStrategy()
    for key in heading.format_keys:
        register_strategy(HeadingChunkStrategy(key))
    register_strategy(CharacterChunkStrategy())
    register_strategy(ChrBindChunkStrategy())
