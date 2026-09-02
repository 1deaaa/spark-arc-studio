"""
Flet GUI 主题、跨平台字体适配与控件配色辅助。
"""
from __future__ import annotations

import sys
import flet as ft


def get_recommended_font_family() -> str:
    """根据操作系统平台返回最推荐的系统字体族名称。

    1. Ubuntu Desktop: 优先使用系统自带推荐的 CJK 中文字体 'Noto Sans CJK SC'，
       备选 'WenQuanYi Micro Hei', 'Ubuntu'
    2. Windows: 优先使用微软雅黑 'Microsoft YaHei UI' 或 'Microsoft YaHei'
    3. macOS: 'PingFang SC'
    """
    if sys.platform.startswith("win"):
        return "Microsoft YaHei UI"
    elif sys.platform.startswith("linux"):
        # Ubuntu desktop 官方自带并推荐的中文字体
        return "Noto Sans CJK SC"
    elif sys.platform == "darwin":
        return "PingFang SC"
    return "sans-serif"


FONT_FAMILY = get_recommended_font_family()
MONO_FAMILY = "Consolas" if sys.platform.startswith("win") else "monospace"

COLORS = {
    "bg": "#F4F7FB",
    "surface": "#FFFFFF",
    "surface_muted": "#EEF3FB",
    "border": "#D7E1F0",
    "text": "#1E293B",
    "text_muted": "#64748B",
    "accent": "#3667D6",
    "accent_hover": "#2E57B5",
    "success": "#1D8F5A",
    "warning": "#D97706",
    "danger": "#D14343",
}


def create_theme(font_family: str | None = None, is_dark: bool = False) -> ft.Theme:
    """根据字体与深浅模式构建 Flet 0.28.3 Theme 对象。"""
    active_font = font_family or FONT_FAMILY
    return ft.Theme(
        font_family=active_font,
        color_scheme_seed=COLORS["accent"],
        use_material3=True,
    )
