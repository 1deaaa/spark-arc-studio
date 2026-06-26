"""
Tkinter GUI 主题与控件配色辅助。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import customtkinter as ctk


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

FONT_FAMILY = "Microsoft YaHei UI"
MONO_FAMILY = "Consolas"


def _font_size(base_size: int, ui_scale: float, *, minimum: int = 9, maximum: int | None = None) -> int:
    scaled = int(round(base_size * min(max(ui_scale, 1.0), 1.25)))
    result = max(minimum, scaled)
    if maximum is not None:
        result = min(result, maximum)
    return result


def apply_theme(root, *, ui_scale: float = 1.0) -> dict:
    """应用统一主题样式。"""
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    # 探测当前主题，配置 ttk.Treeview
    mode = ctk.get_appearance_mode().lower()
    if mode == "dark":
        bg = "#2b2b2b"
        fg = "#dce4ee"
        border = "#3f3f3f"
        head_bg = "#242424"
        head_fg = "#dce4ee"
        select_bg = "#1f538d"
        select_fg = "#ffffff"
        active_bg = "#1a1a1a"
    else:
        bg = "#ffffff"
        fg = "#1e293b"
        border = "#d7e1f0"
        head_bg = "#eef3fb"
        head_fg = "#1e293b"
        select_bg = "#3b8ed0"
        select_fg = "#ffffff"
        active_bg = "#e4ecf9"

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    body_size = _font_size(12, ui_scale)
    small_size = _font_size(10, ui_scale)
    title_size = _font_size(18, ui_scale, minimum=16, maximum=24)
    stat_size = _font_size(16, ui_scale, minimum=14, maximum=22)

    style.configure(
        "Treeview",
        background=bg,
        fieldbackground=bg,
        foreground=fg,
        rowheight=max(body_size + 12, 30),
        bordercolor=border,
        borderwidth=0,
        highlightthickness=0,
        font=(FONT_FAMILY, body_size),
    )
    style.configure(
        "Treeview.Heading",
        background=head_bg,
        foreground=head_fg,
        font=(FONT_FAMILY, body_size, "bold"),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", select_bg)],
        foreground=[("selected", select_fg)],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", active_bg)],
    )

    return {
        "body_size": body_size,
        "small_size": small_size,
        "title_size": title_size,
        "stat_size": stat_size,
        "colors": COLORS,
    }


def style_listbox(widget, *, ui_scale: float = 1.0) -> None:
    """统一 Listbox 视觉。"""
    mode = ctk.get_appearance_mode().lower()
    if mode == "dark":
        bg = "#2b2b2b"
        fg = "#dce4ee"
        border = "#3f3f3f"
        select_bg = "#1f538d"
    else:
        bg = "#ffffff"
        fg = "#1e293b"
        border = "#d7e1f0"
        select_bg = "#3b8ed0"

    widget.configure(
        bg=bg,
        fg=fg,
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        selectbackground=select_bg,
        selectforeground="#FFFFFF",
        activestyle="none",
        font=(FONT_FAMILY, _font_size(11, ui_scale)),
    )


def style_text_widget(widget, *, ui_scale: float = 1.0) -> None:
    """统一 Text 视觉。"""
    mode = ctk.get_appearance_mode().lower()
    if mode == "dark":
        bg = "#2b2b2b"
        fg = "#dce4ee"
        border = "#3f3f3f"
    else:
        bg = "#ffffff"
        fg = "#1e293b"
        border = "#d7e1f0"

    widget.configure(
        bg=bg,
        fg=fg,
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=border,
        highlightcolor=bg,
        insertbackground=fg,
        selectbackground="#CCD9F6" if mode != "dark" else "#1f538d",
        font=(FONT_FAMILY, _font_size(10, ui_scale)),
    )


__all__ = ["COLORS", "apply_theme", "style_listbox", "style_text_widget"]

