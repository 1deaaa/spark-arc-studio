"""
Tkinter GUI 主题与控件配色辅助。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk


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
    root.configure(bg=COLORS["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    body_size = _font_size(10, ui_scale)
    small_size = _font_size(9, ui_scale)
    title_size = _font_size(18, ui_scale, minimum=16, maximum=24)
    stat_size = _font_size(16, ui_scale, minimum=14, maximum=22)

    for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(font_name).configure(family=FONT_FAMILY, size=body_size)
        except tk.TclError:
            pass
    try:
        tkfont.nametofont("TkFixedFont").configure(family=MONO_FAMILY, size=max(body_size - 1, 9))
    except tk.TclError:
        pass

    style.configure(".", font=(FONT_FAMILY, body_size), foreground=COLORS["text"], background=COLORS["bg"])
    style.configure("Shell.TFrame", background=COLORS["bg"])
    style.configure("Hero.TFrame", background=COLORS["surface"])
    style.configure("Card.TFrame", background=COLORS["surface"])
    style.configure("MutedCard.TFrame", background=COLORS["surface_muted"])

    style.configure(
        "Card.TLabelframe",
        background=COLORS["surface"],
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=(FONT_FAMILY, body_size, "bold"),
    )

    style.configure("HeroTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT_FAMILY, title_size, "bold"))
    style.configure("HeroSubtitle.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=(FONT_FAMILY, body_size))
    style.configure("Surface.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT_FAMILY, body_size))
    style.configure("SurfaceMuted.TLabel", background=COLORS["surface"], foreground=COLORS["text_muted"], font=(FONT_FAMILY, small_size))
    style.configure("MutedValue.TLabel", background=COLORS["surface_muted"], foreground=COLORS["text"], font=(FONT_FAMILY, stat_size, "bold"))
    style.configure("MutedCaption.TLabel", background=COLORS["surface_muted"], foreground=COLORS["text_muted"], font=(FONT_FAMILY, small_size))
    style.configure("Accent.TLabel", background=COLORS["surface"], foreground=COLORS["accent"], font=(FONT_FAMILY, body_size, "bold"))
    style.configure("CardTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=(FONT_FAMILY, body_size + 1, "bold"))

    style.configure("TSeparator", background=COLORS["border"])
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure(
        "Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=max(body_size + 12, 28),
        bordercolor=COLORS["border"],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["surface_muted"],
        foreground=COLORS["text"],
        font=(FONT_FAMILY, body_size, "bold"),
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#FFFFFF")],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", "#E4ECF9")],
    )
    style.configure(
        "TNotebook.Tab",
        padding=(16, 10),
        background=COLORS["surface_muted"],
        foreground=COLORS["text_muted"],
        font=(FONT_FAMILY, body_size, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["surface"]), ("active", "#E4ECF9")],
        foreground=[("selected", COLORS["text"]), ("active", COLORS["text"])],
    )

    style.configure(
        "TButton",
        padding=(12, 8),
        background=COLORS["surface_muted"],
        foreground=COLORS["text"],
        borderwidth=0,
    )
    style.map("TButton", background=[("active", "#E1EAF8")])
    style.configure("Primary.TButton", background=COLORS["accent"], foreground="#FFFFFF")
    style.map("Primary.TButton", background=[("active", COLORS["accent_hover"]), ("disabled", COLORS["border"])], foreground=[("disabled", "#FFFFFF")])
    style.configure("Danger.TButton", background=COLORS["danger"], foreground="#FFFFFF")
    style.map("Danger.TButton", background=[("active", "#B83636"), ("disabled", COLORS["border"])], foreground=[("disabled", "#FFFFFF")])

    style.configure(
        "TEntry",
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        insertcolor=COLORS["text"],
        padding=6,
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=6,
    )
    style.configure(
        "Readonly.TEntry",
        fieldbackground=COLORS["surface_muted"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=6,
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
    widget.configure(
        bg=COLORS["surface"],
        fg=COLORS["text"],
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        selectbackground=COLORS["accent"],
        selectforeground="#FFFFFF",
        activestyle="none",
        font=(FONT_FAMILY, _font_size(10, ui_scale)),
    )


def style_text_widget(widget, *, ui_scale: float = 1.0) -> None:
    """统一 Text 视觉。"""
    widget.configure(
        bg=COLORS["surface"],
        fg=COLORS["text"],
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        insertbackground=COLORS["text"],
        selectbackground="#CCD9F6",
        font=(FONT_FAMILY, _font_size(10, ui_scale)),
        padx=10,
        pady=10,
    )


__all__ = ["COLORS", "apply_theme", "style_listbox", "style_text_widget"]
