"""
LLM Manager Package
通用 LLM 管理器组件

主要导出：
- initialize_matchbox: 显式初始化全局管理器（推荐）
- matchbox: 统一获取全局管理器（推荐入口，required=True 时未初始化报错）
- create_matchbox: 创建独立 AIManager 实例（不污染全局）
- reset_matchbo: 重置全局管理器
- create_quick_llm: 轻量模式创建 Chat 客户端（不依赖管理层/数据库）
- create_quick_embedding: 轻量模式创建 Embedding 客户端（不依赖管理层/数据库）
- AIManager: 管理器类（按需加载）
- LLMClient: get_user_llm() 的具名返回对象（含 llm / usage / 模型上限）
- LLMUsage: LLM 用量查询句柄（由 get_user_llm() 返回）
- SecurityManager: 安全管理器（加密/解密）
- get_decrypted_api_key: 获取解密的 API Key
- probe_platform_models: 探测平台可用模型

常量：
- SYSTEM_USER_ID: 系统用户 ID
- DEFAULT_USAGE_KEY: 默认用途键
- BUILTIN_USAGE_SLOTS: 内置用途槽位
"""

from __future__ import annotations

from importlib import import_module
import os
import sys
import threading
from typing import Any, Optional, Tuple


_manager_instance = None
_manager_lock = threading.Lock()

_LAZY_EXPORTS: dict[str, Tuple[str, str]] = {
    "AIManager": (".manager", "AIManager"),
    "ChatUniversal": (".gateway", "ChatUniversal"),
    "create_quick_llm": (".gateway", "create_quick_llm"),
    "create_quick_embedding": (".gateway", "create_quick_embedding"),
    "LLMClient": (".tracked_model", "LLMClient"),
    "LLMUsage": (".tracked_model", "LLMUsage"),
    "SecurityManager": (".security", "SecurityManager"),
    "CreditBalanceExceededError": (".credit_services", "CreditBalanceExceededError"),
    "QuotaExceededError": (".quota_services", "QuotaExceededError"),
    "probe_platform_models": (".utils", "probe_platform_models"),
    "get_decrypted_api_key": (".config", "get_decrypted_api_key"),
    "SYSTEM_USER_ID": (".config", "SYSTEM_USER_ID"),
    "DEFAULT_USAGE_KEY": (".config", "DEFAULT_USAGE_KEY"),
    "BUILTIN_USAGE_SLOTS": (".config", "BUILTIN_USAGE_SLOTS"),
    "DEFAULT_PLATFORM_CONFIGS": (".config", "DEFAULT_PLATFORM_CONFIGS"),
    "LLM_AUTO_KEY": (".config", "LLM_AUTO_KEY"),
    "USE_SYS_LLM_CONFIG": (".config", "USE_SYS_LLM_CONFIG"),
}


def _load_symbol(module_name: str, symbol: str) -> Any:
    module = import_module(module_name, __name__)
    return getattr(module, symbol)


def _should_enable_manager() -> bool:
    if os.environ.get("SPARKARC_SKIP_LLM_MANAGER") == "1":
        return False
    for arg in sys.argv:
        if "alembic" in arg or "gen_migration.py" in arg:
            return False
    return True


def create_matchbox(db_name: str = "llm_config.db"):
    """创建独立 AIManager 实例。"""
    ai_manager_cls = _load_symbol(".manager", "AIManager")
    return ai_manager_cls(db_name=db_name)


def initialize_matchbox(
    db_name: str = "llm_config.db",
    ensure_defaults: bool = True,
    force: bool = False,
) -> Optional[Any]:
    """显式初始化全局 AIManager。

    默认行为：首次初始化时创建实例，并同步默认配置。
    force=True 时会重建实例（用于切换 db_name 或测试场景）。
    """
    global _manager_instance
    if not _should_enable_manager():
        return None

    with _manager_lock:
        if _manager_instance is not None and not force:
            return _manager_instance

        manager = create_matchbox(db_name=db_name)
        if ensure_defaults:
            manager.initialize_defaults()
        _manager_instance = manager
        return _manager_instance


def matchbox(*, required: bool = True) -> Optional[Any]:
    """获取全局 AIManager。

    - required=True（默认）: 业务调用场景，未初始化或被禁用时抛出 RuntimeError。
    - required=False: 仅用于探测场景（较少使用），未初始化或被禁用时返回 None。
    """
    if not _should_enable_manager():
        if required:
            raise RuntimeError(
                "LLM Manager 当前被禁用（迁移/脚本模式或 SPARKARC_SKIP_LLM_MANAGER=1）。"
            )
        return None

    manager = _manager_instance
    if manager is None and required:
        raise RuntimeError(
            "LLM Manager 尚未初始化。请在应用启动阶段先调用 initialize_matchbox()。"
        )
    return manager


def reset_matchbo() -> None:
    """重置全局 AIManager 单例。"""
    global _manager_instance
    with _manager_lock:
        _manager_instance = None


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = _load_symbol(*target)
    globals()[name] = value
    return value


__all__ = [
    # 主要导出
    'initialize_matchbox',
    'matchbox',
    'create_matchbox',
    'reset_matchbo',
    'AIManager',
    'ChatUniversal',
    'create_quick_llm',
    'create_quick_embedding',
    'LLMClient',
    'LLMUsage',
    'CreditBalanceExceededError',
    'QuotaExceededError',
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

