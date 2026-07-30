"""验证服务监听配置与本机访问地址的统一解析。"""

from __future__ import annotations

import pytest

from core.server_runtime import build_local_server_urls, resolve_server_binding


def test_server_binding_uses_production_defaults() -> None:
    assert resolve_server_binding({}) == ("0.0.0.0", 6688)


def test_server_binding_accepts_environment_overrides() -> None:
    assert resolve_server_binding(
        {
            "SPARKARC_SERVER_HOST": "127.0.0.1",
            "SPARKARC_SERVER_PORT": "7788",
        }
    ) == ("127.0.0.1", 7788)


def test_server_binding_rejects_non_integer_port() -> None:
    with pytest.raises(ValueError, match="必须是整数"):
        resolve_server_binding({"SPARKARC_SERVER_PORT": "not-a-port"})


@pytest.mark.parametrize("port", ["0", "65536", "-1"])
def test_server_binding_rejects_out_of_range_port(port: str) -> None:
    with pytest.raises(ValueError, match="必须位于 1-65535"):
        resolve_server_binding({"SPARKARC_SERVER_PORT": port})


@pytest.mark.parametrize("host", ["", "0.0.0.0", "::"])
def test_wildcard_binding_builds_reachable_local_urls(host: str) -> None:
    assert build_local_server_urls(host, 7788) == (
        "http://localhost:7788",
        "http://127.0.0.1:7788/health",
    )


def test_explicit_binding_is_preserved_in_local_urls() -> None:
    assert build_local_server_urls("127.0.0.1", 7788) == (
        "http://127.0.0.1:7788",
        "http://127.0.0.1:7788/health",
    )
