"""
环境变量工具模块
统一管理 .env 文件的读取和写入
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key

# .env 文件路径（llm_mgr 目录）
_ENV_PATH: Path = Path(__file__).parent / ".env"
# 备用 .env 文件路径（写入到 data 目录，确保 Docker 场景可持久化）
_FALLBACK_ENV_PATH: Path = Path(__file__).parent.parent.parent / "data" / ".env"


def _resolve_env_path() -> Path:
    """解析可用的 .env 路径（优先 server/.env，异常时回退到 data/.env）"""
    # 情况1：llm_mgr/.env 已存在且为文件
    if _ENV_PATH.exists() and _ENV_PATH.is_file():
        return _ENV_PATH

    # 情况2：llm_mgr/.env 是目录（Docker 绑定文件缺失时常见）
    if _ENV_PATH.exists() and _ENV_PATH.is_dir():
        # 回退到 data/.env
        return _FALLBACK_ENV_PATH

    # 情况3：llm_mgr/.env 不存在，尝试创建
    try:
        _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ENV_PATH.touch(exist_ok=True)
        return _ENV_PATH
    except Exception:
        # 创建失败则回退
        return _FALLBACK_ENV_PATH


def get_env_path() -> Path:
    """返回 .env 文件路径"""
    return _resolve_env_path()


def load_env() -> None:
    """加载 .env 文件到环境变量"""
    env_path = _resolve_env_path()
    # 确保文件存在（在 fallback 路径下也创建）
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch(exist_ok=True)
    except Exception:
        pass
    if env_path.exists() and env_path.is_file():
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
        env_path = _resolve_env_path()
        # 确保 .env 文件存在
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.touch(exist_ok=True)

        # 写入 .env 文件
        set_key(str(env_path), key, value)
        
        # 同时更新当前进程环境变量
        os.environ[key] = value
        return True
    except Exception as e:
        print(f"❌ 写入 .env 失败: {e}")
        return False
