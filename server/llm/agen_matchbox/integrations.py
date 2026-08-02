"""Matchbox 与宿主应用之间的可选集成回调。

Matchbox 的默认运行路径不需要这些回调。服务型宿主可以按需注入业务默认用途、
请求身份、用量上下文和外部密钥轮换处理器，而无需让 Matchbox 导入宿主模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


DefaultUsageKeyResolver = Callable[[Optional[str]], str]
CallerContextProvider = Callable[[], tuple[Optional[str], bool]]
UsageContextProvider = Callable[[], Optional[str]]
SecretRotationHandler = Callable[..., None]


@dataclass(frozen=True)
class MatchboxIntegrations:
    """一组可选的宿主回调。

    ``secret_rotation_handler`` 在 Matchbox 已经扫描通用密钥、但尚未提交事务时
    被调用。处理器可以通过回调登记自己的密钥迁移任务，从而与通用密钥迁移保持
    同一事务边界。
    """

    default_usage_key_resolver: Optional[DefaultUsageKeyResolver] = None
    caller_context_provider: Optional[CallerContextProvider] = None
    usage_context_provider: Optional[UsageContextProvider] = None
    secret_rotation_handler: Optional[SecretRotationHandler] = None
