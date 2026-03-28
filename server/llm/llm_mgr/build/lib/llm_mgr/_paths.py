"""
llm_mgr 运行时路径工具。

目标：
- 源码模式下，保持现有行为（默认仍使用包目录）。
- 已安装到 site-packages 且目录不可写时，自动切换到用户可写目录。
- 支持通过环境变量 LLM_MGR_HOME 显式指定运行目录。
"""

from __future__ import annotations

import os
import shutil
from typing import Optional


PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))


def _get_default_user_home() -> str:
    # Windows 优先使用 APPDATA；其他平台回退到 ~/.llm_mgr
    appdata = os.getenv("APPDATA")
    if isinstance(appdata, str) and appdata.strip():
        return os.path.join(appdata, "llm_mgr")
    return os.path.join(os.path.expanduser("~"), ".llm_mgr")


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".llm_mgr_write_probe")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def get_runtime_home() -> str:
    """返回 llm_mgr 运行时目录。"""
    env_home = os.getenv("LLM_MGR_HOME")
    if isinstance(env_home, str) and env_home.strip():
        runtime_home = os.path.abspath(env_home.strip())
        os.makedirs(runtime_home, exist_ok=True)
        return runtime_home

    # 源码模式优先沿用包目录（保持兼容）。
    if _is_writable_dir(PACKAGE_DIR):
        return PACKAGE_DIR

    runtime_home = _get_default_user_home()
    os.makedirs(runtime_home, exist_ok=True)
    return runtime_home


def get_runtime_file_path(file_name: str, seed_from_package: bool = False) -> str:
    """
    返回运行时文件路径。

    参数:
    - file_name: 文件名
    - seed_from_package: 若运行时文件不存在，且包内存在同名文件，则自动拷贝一份种子文件。
    """
    runtime_home = get_runtime_home()
    runtime_path = os.path.join(runtime_home, file_name)

    if seed_from_package and not os.path.exists(runtime_path):
        package_path = os.path.join(PACKAGE_DIR, file_name)
        if os.path.exists(package_path):
            shutil.copy2(package_path, runtime_path)

    return runtime_path


def get_package_file_path(file_name: str) -> str:
    """返回包内静态文件路径。"""
    return os.path.join(PACKAGE_DIR, file_name)
