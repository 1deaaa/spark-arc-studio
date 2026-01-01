"""
AIManager 完整实现
通过 Mixin 组合模式将功能模块化
"""

from .base import AIManagerBase
from .platform import PlatformMixin
from .model import ModelMixin
from .user_config import UserConfigMixin
from .agent_binding import AgentBindingMixin
from .llm_builder import LLMBuilderMixin
from .usage_stats import UsageStatsMixin


class AIManager(
    AIManagerBase,
    PlatformMixin,
    ModelMixin,
    UserConfigMixin,
    AgentBindingMixin,
    LLMBuilderMixin,
    UsageStatsMixin,
):
    """
    AI 模型管理器
    
    功能模块：
    - AIManagerBase: 基础初始化和核心工具方法
    - PlatformMixin: 平台增删改查
    - ModelMixin: 模型增删改
    - UserConfigMixin: 用户配置和用途槽位管理
    - AgentBindingMixin: Agent 与模型的绑定
    - LLMBuilderMixin: 构建 LLM 客户端实例
    - UsageStatsMixin: 使用统计记录和查询
    """
    
    def __init__(self, db_name: str = "llm_config.db"):
        super().__init__(db_name)
        self.initialize_defaults()


__all__ = ['AIManager']
