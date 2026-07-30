from __future__ import annotations

import os
from typing import Mapping


DEFAULT_SERVER_HOST = "0.0.0.0"
DEFAULT_SERVER_PORT = 6688


def resolve_server_binding(
    env: Mapping[str, str] | None = None,
) -> tuple[str, int]:
    """从环境变量解析服务监听地址，生产默认值保持不变。"""
    current_env = os.environ if env is None else env
    host = str(current_env.get("SPARKARC_SERVER_HOST") or DEFAULT_SERVER_HOST).strip()
    if not host:
        host = DEFAULT_SERVER_HOST

    raw_port = str(current_env.get("SPARKARC_SERVER_PORT") or DEFAULT_SERVER_PORT).strip()
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"SPARKARC_SERVER_PORT 必须是整数，当前值：{raw_port!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"SPARKARC_SERVER_PORT 必须位于 1-65535，当前值：{port}")
    return host, port


def build_local_server_urls(host: str, port: int) -> tuple[str, str]:
    """为浏览器入口和健康检查生成可访问的本机地址。"""
    normalized_host = str(host or "").strip()
    browser_host = "localhost" if normalized_host in {"", "0.0.0.0", "::"} else normalized_host
    health_host = "127.0.0.1" if normalized_host in {"", "0.0.0.0", "::"} else normalized_host
    return (
        f"http://{browser_host}:{int(port)}",
        f"http://{health_host}:{int(port)}/health",
    )
