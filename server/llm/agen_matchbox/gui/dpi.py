"""
高分屏与响应式窗口布局辅助工具。
"""
from __future__ import annotations

import sys

try:
    import ctypes
except Exception:  # pragma: no cover - 极端环境兜底
    ctypes = None


_BASE_DPI = 96.0
_BASE_TK_SCALING = _BASE_DPI / 72.0


def enable_high_dpi_awareness() -> None:
    """在 Windows 上尽量启用高分屏感知。"""
    if sys.platform != "win32" or ctypes is None:
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def configure_tk_scaling(root) -> float:
    """根据当前屏幕 DPI 调整 Tk 缩放，并返回 UI 缩放倍率。"""
    root.update_idletasks()

    try:
        pixels_per_inch = float(root.winfo_fpixels("1i"))
    except Exception:
        pixels_per_inch = _BASE_DPI

    pixels_per_inch = max(pixels_per_inch, _BASE_DPI)
    try:
        root.tk.call("tk", "scaling", pixels_per_inch / 72.0)
    except Exception:
        pass
    return pixels_per_inch / _BASE_DPI


def _scaled_pair(size: tuple[int, int], ui_scale: float, *, upper: float = 1.2) -> tuple[int, int]:
    scale = min(max(ui_scale, 1.0), upper)
    return (
        int(round(size[0] * scale)),
        int(round(size[1] * scale)),
    )


def _compute_window_size(
    window,
    *,
    base_size: tuple[int, int],
    min_size: tuple[int, int],
    ui_scale: float,
    width_ratio: float,
    height_ratio: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
    screen_w = int(window.winfo_screenwidth())
    screen_h = int(window.winfo_screenheight())

    scaled_base = _scaled_pair(base_size, ui_scale, upper=1.12)
    scaled_min = _scaled_pair(min_size, ui_scale, upper=1.18)

    max_w = max(int(screen_w * width_ratio), scaled_min[0])
    max_h = max(int(screen_h * height_ratio), scaled_min[1])

    width = max(scaled_min[0], min(scaled_base[0], max_w))
    height = max(scaled_min[1], min(scaled_base[1], max_h))
    return (width, height), scaled_min


def _center_geometry(window, width: int, height: int, parent=None) -> str:
    if parent is not None:
        try:
            parent.update_idletasks()
            parent_w = parent.winfo_width() or width
            parent_h = parent.winfo_height() or height
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()

            x = parent_x + max((parent_w - width) // 2, 24)
            y = parent_y + max((parent_h - height) // 2, 24)
            return f"{width}x{height}+{x}+{y}"
        except Exception:
            pass

    screen_w = int(window.winfo_screenwidth())
    screen_h = int(window.winfo_screenheight())
    x = max((screen_w - width) // 2, 24)
    y = max((screen_h - height) // 2, 24)
    return f"{width}x{height}+{x}+{y}"


def prepare_root_window(
    root,
    *,
    title: str | None = None,
    base_size: tuple[int, int] = (1480, 930),
    min_size: tuple[int, int] = (1120, 720),
    width_ratio: float = 0.88,
    height_ratio: float = 0.86,
    ui_scale: float = 1.0,
) -> tuple[int, int]:
    """配置主窗口的默认大小、最小大小与居中布局。"""
    if title:
        root.title(title)

    (width, height), scaled_min = _compute_window_size(
        root,
        base_size=base_size,
        min_size=min_size,
        ui_scale=ui_scale,
        width_ratio=width_ratio,
        height_ratio=height_ratio,
    )

    root.minsize(*scaled_min)
    root.geometry(_center_geometry(root, width, height))
    return width, height


def prepare_toplevel_window(
    window,
    parent,
    *,
    base_size: tuple[int, int] = (860, 700),
    min_size: tuple[int, int] = (680, 520),
    width_ratio: float = 0.8,
    height_ratio: float = 0.84,
    ui_scale: float = 1.0,
) -> tuple[int, int]:
    """配置模态窗口的响应式尺寸与位置。"""
    (width, height), scaled_min = _compute_window_size(
        window,
        base_size=base_size,
        min_size=min_size,
        ui_scale=ui_scale,
        width_ratio=width_ratio,
        height_ratio=height_ratio,
    )

    window.minsize(*scaled_min)
    window.geometry(_center_geometry(window, width, height, parent=parent))
    return width, height


__all__ = [
    "configure_tk_scaling",
    "enable_high_dpi_awareness",
    "prepare_root_window",
    "prepare_toplevel_window",
]
