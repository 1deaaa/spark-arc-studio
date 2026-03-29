"""
环境变量工具模块
统一管理 .env 文件的读取和写入
"""
import os
from pathlib import Path
from typing import Dict, Optional
from dotenv import dotenv_values, set_key

from .paths import get_env_file_path

# .env 文件唯一读取路径（llm_mgr 目录）
_ENV_PATH: Path = get_env_file_path()
_ENV_INIT_BANNER = (
    "#绝对禁止将此文件上传至仓库 必须确保ignore里有\n"
    "#禁止直接修改 要通过/api/admin/config/llm-key接口修改LLM_KEY\n\n"
)
_ENV_CACHE: Optional[Dict[str, Optional[str]]] = None
_ENV_CACHE_MTIME_NS: Optional[int] = None
_ENV_CACHE_SIZE: Optional[int] = None


def _refresh_env_cache(force: bool = False) -> Dict[str, Optional[str]]:
    """读取并缓存 llm_mgr/.env，只有文件变化时才重新解析。"""
    global _ENV_CACHE, _ENV_CACHE_MTIME_NS, _ENV_CACHE_SIZE

    env_path = _ensure_env_file()
    stat = env_path.stat()
    mtime_ns = stat.st_mtime_ns
    size = stat.st_size

    if (
        not force
        and _ENV_CACHE is not None
        and _ENV_CACHE_MTIME_NS == mtime_ns
        and _ENV_CACHE_SIZE == size
    ):
        return _ENV_CACHE

    data = dict(dotenv_values(env_path))
    _ENV_CACHE = data
    _ENV_CACHE_MTIME_NS = mtime_ns
    _ENV_CACHE_SIZE = size
    return data


def _ensure_env_file() -> Path:
    """确保 llm_mgr/.env 文件存在并返回其路径。"""
    _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _ENV_PATH.exists() and _ENV_PATH.is_dir():
        raise IsADirectoryError(f".env 路径异常（是目录而非文件）: {_ENV_PATH}")
    if not _ENV_PATH.exists():
        _ENV_PATH.write_text(_ENV_INIT_BANNER, encoding="utf-8")
    elif _ENV_PATH.stat().st_size == 0:
        _ENV_PATH.write_text(_ENV_INIT_BANNER, encoding="utf-8")
    return _ENV_PATH


def get_env_path() -> Path:
    """返回 .env 文件路径"""
    return _ENV_PATH


def load_env() -> None:
    """预热 .env 缓存。保留旧接口名，但不再回写进程环境变量。"""
    _refresh_env_cache()


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取环境变量：优先 llm_mgr/.env，缺失时回退进程环境变量。"""
    data = _refresh_env_cache()
    value = data.get(key)
    # 兼容历史部署：允许通过系统/终端环境变量注入配置。
    if value is None or (isinstance(value, str) and not value.strip()):
        value = os.environ.get(key, default)

    if isinstance(value, str):
        value = value.strip()
    return value


def get_env_file_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """仅从 llm_mgr/.env 读取变量（不回退进程环境）。"""
    data = _refresh_env_cache()
    value = data.get(key, default)
    if isinstance(value, str):
        value = value.strip()
    return value


def has_env_file_var(key: str) -> bool:
    """判断 llm_mgr/.env 文件中是否显式配置了非空变量。"""
    value = get_env_file_var(key)
    return isinstance(value, str) and bool(value.strip())


def set_env_var(key: str, value: str) -> bool:
    """
    设置环境变量并持久化到 .env 文件
    返回 True 表示成功
    """
    try:
        env_path = _ensure_env_file()

        # 写入 .env 文件
        set_key(str(env_path), key, value)

        # 兼容当前进程内依赖，但不再作为读取真源
        os.environ[key] = value
        _refresh_env_cache(force=True)
        return True
    except Exception as e:
        print(f"❌ 写入 .env 失败: {e}")
        return False
