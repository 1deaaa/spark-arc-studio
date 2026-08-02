"""Matchbox 自带的数据库连接基础设施。

该模块只负责创建 SQLAlchemy Engine，不读取宿主项目的配置或数据库模块。
宿主若已有统一的 Engine 工厂，可以通过 ``AIManager`` 的构造参数注入。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import StaticPool


def _coerce_sqlite_url(path: str | os.PathLike[str]) -> str:
    """把 SQLite 文件路径转换为绝对 URL。"""
    return f"sqlite:///{Path(path).expanduser().resolve().as_posix()}"


def normalize_database_url(
    *,
    env_key: str,
    default_sqlite_path: str | os.PathLike[str],
) -> str:
    """从指定环境变量读取数据库 URL，缺省时使用 SQLite 文件。"""
    raw = (os.environ.get(env_key) or "").strip()
    return raw or _coerce_sqlite_url(default_sqlite_path)


def _is_sqlite_url(url: str) -> bool:
    """判断数据库 URL 是否使用 SQLite。"""
    try:
        return make_url(url).get_backend_name() == "sqlite"
    except Exception:
        return str(url).startswith("sqlite:")


def _is_sqlite_memory_url(url: str) -> bool:
    """判断 URL 是否指向进程内 SQLite 数据库。"""
    try:
        parsed = make_url(url)
        return parsed.get_backend_name() == "sqlite" and parsed.database in {None, "", ":memory:"}
    except Exception:
        return str(url).rstrip("/").endswith(":memory:")


def _install_sqlite_pragmas(engine: Engine) -> None:
    """为 SQLite 连接安装适合并发服务的默认参数。"""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # pragma: no cover - 由驱动触发
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_configured_engine(
    database_url: str,
    *,
    echo: bool = False,
    future: bool = True,
    sqlite_pool_size: int | None = 20,
    sqlite_max_overflow: int | None = 30,
    postgres_pool_size: int | None = 20,
    postgres_max_overflow: int | None = 40,
    pool_timeout: int = 60,
    **kwargs: Any,
) -> Engine:
    """按数据库方言创建 Engine。"""
    engine_kwargs: dict[str, Any] = {
        "echo": echo,
        "future": future,
        **kwargs,
    }

    if _is_sqlite_url(database_url):
        if _is_sqlite_memory_url(database_url):
            engine_kwargs.setdefault("poolclass", StaticPool)
            connect_args = dict(engine_kwargs.get("connect_args") or {})
            connect_args.setdefault("check_same_thread", False)
            engine_kwargs["connect_args"] = connect_args
        else:
            if sqlite_pool_size is not None:
                engine_kwargs.setdefault("pool_size", sqlite_pool_size)
            if sqlite_max_overflow is not None:
                engine_kwargs.setdefault("max_overflow", sqlite_max_overflow)
            engine_kwargs.setdefault("pool_timeout", pool_timeout)
        engine = create_engine(database_url, **engine_kwargs)
        _install_sqlite_pragmas(engine)
        return engine

    engine_kwargs.setdefault("pool_size", postgres_pool_size)
    engine_kwargs.setdefault("max_overflow", postgres_max_overflow)
    engine_kwargs.setdefault("pool_timeout", pool_timeout)
    engine_kwargs.setdefault("pool_pre_ping", True)
    engine_kwargs.setdefault("pool_recycle", 1800)
    return create_engine(database_url, **engine_kwargs)


def create_engine_from_env(
    *,
    env_key: str,
    default_sqlite_path: str | os.PathLike[str],
    **kwargs: Any,
) -> Engine:
    """从环境变量或默认 SQLite 路径创建 Engine。"""
    return create_configured_engine(
        normalize_database_url(env_key=env_key, default_sqlite_path=default_sqlite_path),
        **kwargs,
    )
