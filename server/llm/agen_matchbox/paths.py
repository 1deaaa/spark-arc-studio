"""matchbox 运行期文件路径辅助工具。"""

from __future__ import annotations

import os
from pathlib import Path


_HOME_ENV_NAME = "AGENT_MATCHBOX_HOME"
_PACKAGE_DIR = Path(__file__).resolve().parent


def get_package_dir() -> Path:
    """返回 matchbox 包的物理目录。"""
    return _PACKAGE_DIR


def get_mgr_home() -> Path:
    """返回 matchbox 运行期目录。

    解析顺序：
    1. 环境变量 AGENT_MATCHBOX_HOME
        - 绝对路径：直接使用
        - 相对路径：相对于当前工作目录解析
    2. 回退到 matchbox 包目录
    """
    raw = (os.environ.get(_HOME_ENV_NAME) or "").strip()
    if not raw:
        return _PACKAGE_DIR

    home = Path(raw).expanduser()
    if not home.is_absolute():
        home = Path.cwd() / home
    return home.resolve()


def ensure_mgr_home_exists() -> Path:
    """确保运行期目录存在，并返回该目录。"""
    home = get_mgr_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_db_file_path(db_name: str = "llm_config.db") -> Path:
    """解析数据库文件路径。

    - db_name 为绝对路径：直接使用
    - db_name 为相对路径：放到 matchbox 运行期目录下
    """
    db_path = Path(db_name).expanduser()
    if db_path.is_absolute():
        return db_path
    return get_mgr_home() / db_path


def get_state_file_path() -> Path:
    """返回状态文件路径。"""
    return get_mgr_home() / "matchbox_state.json"


def get_env_file_path() -> Path:
    """返回 .env 文件路径。"""
    return get_mgr_home() / ".env"


def get_config_file_path() -> Path:
    """返回当前生效 YAML 配置路径。"""
    return get_mgr_home() / "matchbox_cfg.yaml"


def get_packaged_config_template_path() -> Path:
    """返回包内自带 YAML 模板路径。"""
    return _PACKAGE_DIR / "matchbox_cfg.yaml"
