"""
高分屏与窗口几何尺寸配置辅助工具（适配 Flet 0.28.3）。
"""
from __future__ import annotations

import flet as ft


def enable_high_dpi_awareness() -> None:
    """保持兼容性的高分屏感知入口（Flutter/Flet 底层自动适配高分屏缩放）。"""
    pass


def configure_page_window(
    page: ft.Page,
    *,
    title: str = "火柴Agent网关 · LLM 配置台",
    width: int = 1420,
    height: int = 880,
    min_width: int = 1180,
    min_height: int = 720,
) -> None:
    """统一配置 Flet 0.28.3 主窗口的标题、尺寸、最小尺寸与居中。"""
    page.title = title
    if hasattr(page, "window") and page.window is not None:
        page.window.width = width
        page.window.height = height
        page.window.min_width = min_width
        page.window.min_height = min_height
        try:
            page.window.center()
        except Exception:
            pass


def prepare_root_window(page: ft.Page, **kwargs) -> tuple[int, int]:
    """老接口兼容实现。"""
    width = kwargs.get("width", 1420)
    height = kwargs.get("height", 880)
    configure_page_window(
        page,
        title=kwargs.get("title", "火柴Agent网关 · LLM 配置台"),
        width=width,
        height=height,
        min_width=kwargs.get("min_size", (1180, 720))[0] if "min_size" in kwargs else 1180,
        min_height=kwargs.get("min_size", (1180, 720))[1] if "min_size" in kwargs else 720,
    )
    return width, height


def prepare_toplevel_window(dialog: ft.AlertDialog, **kwargs) -> None:
    """老接口兼容实现（Flet 中模态对话框由 AlertDialog 承载）。"""
    pass


__all__ = [
    "enable_high_dpi_awareness",
    "configure_page_window",
    "prepare_root_window",
    "prepare_toplevel_window",
]
