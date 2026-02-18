"""
LLM 配置管理器 GUI

支持直接右键运行：自动将 server/ 目录加入 sys.path 以解析模块路径。
"""
import sys
from pathlib import Path

# 确保 server/ 目录在 sys.path 中，以便直接运行本文件时也能正确导入 llm.llm_mgr 等模块
_SERVER_DIR = str(Path(__file__).resolve().parent.parent.parent)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from llm.llm_mgr.gui.main_window import LLMConfigGUI, main

__all__ = ["LLMConfigGUI", "main"]

if __name__ == "__main__":
    main()
