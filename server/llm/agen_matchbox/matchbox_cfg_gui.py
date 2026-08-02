"""
LLM 配置管理器 GUI 入口。

支持直接运行本文件，同时避免依赖外层目录名必须叫 llm。
"""
import sys
from pathlib import Path


if __package__ in (None, ""):
    _PACKAGE_DIR = Path(__file__).resolve().parent
    for _import_root in (_PACKAGE_DIR.parent.parent, _PACKAGE_DIR.parent):
        _import_root_text = str(_import_root)
        if _import_root_text not in sys.path:
            sys.path.insert(0, _import_root_text)
    __package__ = _PACKAGE_DIR.name


_host_schema_initializer = None
try:
    from llm.matchbox_adapter import (
        configure_sparkarc_matchbox_environment,
        prepare_sparkarc_matchbox_gui,
    )
except ImportError:
    pass
else:
    configure_sparkarc_matchbox_environment()
    _host_schema_initializer = prepare_sparkarc_matchbox_gui


from .gui.main_window import LLMConfigGUI, main

__all__ = ["LLMConfigGUI", "main"]

if __name__ == "__main__":
    main(schema_initializer=_host_schema_initializer)
