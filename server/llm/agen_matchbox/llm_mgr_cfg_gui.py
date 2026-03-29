"""
LLM 配置管理器 GUI 入口。

支持直接运行本文件，同时避免依赖外层目录名必须叫 llm。
"""
import sys
from pathlib import Path


if __package__ in (None, ""):
    _PACKAGE_DIR = Path(__file__).resolve().parent
    _PARENT_DIR = str(_PACKAGE_DIR.parent)
    if _PARENT_DIR not in sys.path:
        sys.path.insert(0, _PARENT_DIR)
    __package__ = _PACKAGE_DIR.name


from .gui.main_window import LLMConfigGUI, main

__all__ = ["LLMConfigGUI", "main"]

if __name__ == "__main__":
    main()
