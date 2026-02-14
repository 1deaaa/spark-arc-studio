"""
环境变量工具模块
统一管理 .env 文件的读取和写入
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key

# .env 文件唯一读取路径（llm_mgr 目录）
_ENV_PATH: Path = Path(__file__).parent / ".env"


def _ensure_env_file() -> Path:
    """确保 llm_mgr/.env 文件存在并返回其路径。"""
    _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _ENV_PATH.exists() and _ENV_PATH.is_dir():
        raise IsADirectoryError(f".env 路径异常（是目录而非文件）: {_ENV_PATH}")
    _ENV_PATH.touch(exist_ok=True)
    return _ENV_PATH


def get_env_path() -> Path:
    """返回 .env 文件路径"""
    return _ENV_PATH


def load_env() -> None:
    """加载 .env 文件到环境变量"""
    env_path = _ensure_env_file()
    load_dotenv(env_path, override=True)


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取环境变量（优先从 .env 加载）"""
    load_env()
    return os.environ.get(key, default)


def set_env_var(key: str, value: str) -> bool:
    """
    设置环境变量并持久化到 .env 文件
    返回 True 表示成功
    """
    try:
        env_path = _ensure_env_file()

        # 写入 .env 文件
        set_key(str(env_path), key, value)
        
        # 同时更新当前进程环境变量
        os.environ[key] = value
        return True
    except Exception as e:
        print(f"❌ 写入 .env 失败: {e}")
        return False
