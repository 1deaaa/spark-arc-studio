"""
LLM Manager Package
通用 LLM 管理器组件

主要导出：
- LLM_Manager: 单例实例，直接使用
- AIManager: 管理器类，可自定义实例化
- SecurityManager: 安全管理器（加密/解密）
- get_decrypted_api_key: 获取解密的 API Key
- probe_platform_models: 探测平台可用模型
- init_default_llm: 初始化函数

常量：
- SYSTEM_USER_ID: 系统用户 ID
- DEFAULT_USAGE_KEY: 默认用途键
- BUILTIN_USAGE_SLOTS: 内置用途槽位
"""

from .security import SecurityManager
from .config import (
    SYSTEM_USER_ID,
    DEFAULT_USAGE_KEY,
    BUILTIN_USAGE_SLOTS,
    DEFAULT_PLATFORM_CONFIGS,
    LLM_AUTO_KEY,
    USE_SYS_LLM_CONFIG,
    get_decrypted_api_key,
)
from .utils import probe_platform_models
from .models import (
    Base,
    LLMPlatform,
    LLModels,
    LLMSysPlatformKey,
    UserModelUsage,
    AgentModelBinding,
    ModelUsageStats,
)
from .manager import AIManager


# 单例实例
LLM_Manager = AIManager()


def init_default_llm():
    """初始化 AI 管理器"""
    print("正在执行 AI 管理器的启动初始化...")
    LLM_Manager.initialize_defaults()
    print("AI 管理器初始化完成。")


__all__ = [
    # 主要导出
    'LLM_Manager',
    'AIManager',
    'SecurityManager',
    'get_decrypted_api_key',
    'init_default_llm',
    'probe_platform_models',
    # 常量
    'SYSTEM_USER_ID',
    'DEFAULT_USAGE_KEY',
    'BUILTIN_USAGE_SLOTS',
    'DEFAULT_PLATFORM_CONFIGS',
    'LLM_AUTO_KEY',
    'USE_SYS_LLM_CONFIG',
    # 数据库模型（供高级用户使用）
    'Base',
    'LLMPlatform',
    'LLModels',
    'LLMSysPlatformKey',
    'UserModelUsage',
    'AgentModelBinding',
    'ModelUsageStats',
]
