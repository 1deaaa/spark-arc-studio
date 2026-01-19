"""
环境变量工具模块
统一管理 .env 文件的读取和写入
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key

# .env 文件路径（server 根目录）
_ENV_PATH: Path = Path(__file__).parent.parent.parent / ".env"


def get_env_path() -> Path:
    """返回 .env 文件路径"""
    return _ENV_PATH


def load_env() -> None:
    """加载 .env 文件到环境变量"""
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=True)


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
        # 确保 .env 文件存在
        if not _ENV_PATH.exists():
            _ENV_PATH.touch()
        
        # 写入 .env 文件
        set_key(str(_ENV_PATH), key, value)
        
        # 同时更新当前进程环境变量
        os.environ[key] = value
        return True
    except Exception as e:
        print(f"❌ 写入 .env 失败: {e}")
        return False
