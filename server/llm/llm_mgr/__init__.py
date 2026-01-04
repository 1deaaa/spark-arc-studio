"""
LLM Manager Package
通用 LLM 管理器组件

主要导出：
- LLM_Manager: 单例实例，直接使用（自动完成初始化）
- AIManager: 管理器类，可自定义实例化
- TrackedChatModel: 带用量追踪的 LLM 包装器
- SecurityManager: 安全管理器（加密/解密）
- get_decrypted_api_key: 获取解密的 API Key
- probe_platform_models: 探测平台可用模型

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
from .manager import AIManager
from .tracked_model import TrackedChatModel


# 单例实例（构造时自动完成数据库初始化和配置同步）
LLM_Manager = AIManager()


__all__ = [
    # 主要导出
    'LLM_Manager',
    'AIManager',
    'TrackedChatModel',
    'SecurityManager',
    'get_decrypted_api_key',
    'probe_platform_models',
    # 常量
    'SYSTEM_USER_ID',
    'DEFAULT_USAGE_KEY',
    'BUILTIN_USAGE_SLOTS',
    'DEFAULT_PLATFORM_CONFIGS',
    'LLM_AUTO_KEY',
    'USE_SYS_LLM_CONFIG',
]

