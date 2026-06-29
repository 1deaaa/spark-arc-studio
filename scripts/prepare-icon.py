#!/usr/bin/env python3
"""SparkArc 图标预处理脚本。

从 assets/sparkarc.jpg 生成平台打包使用的圆角 PNG：
assets/sparkarc.jpg -> client/src-tauri/icons/app-icon-source.png

client/src/assets/ 下的界面 Logo 由人工维护，本脚本不修改它们。
30% 圆角半径用于满足 Google Play 2026-03-31 的图标要求。
依赖：Pillow>=10.0.0
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parent.parent

CORNER_RATIO = 0.30
ICON_SIZE = 1024
CONTENT_SCALE = 0.88


def estimate_background_color(img: Image.Image) -> tuple[int, int, int]:
    """从四角估算源图背景色，用于扩展留白。"""
    rgb = img.convert("RGB")
    sample_size = max(8, min(rgb.size) // 16)
    boxes = [
        (0, 0, sample_size, sample_size),
        (rgb.width - sample_size, 0, rgb.width, sample_size),
        (0, rgb.height - sample_size, sample_size, rgb.height),
        (rgb.width - sample_size, rgb.height - sample_size, rgb.width, rgb.height),
    ]
    values = []
    for box in boxes:
        values.extend(ImageStat.Stat(rgb.crop(box)).mean)
    return tuple(round(sum(values[index::3]) / 4) for index in range(3))


def apply_rounded_corners(img: Image.Image, ratio: float = CORNER_RATIO) -> Image.Image:
    """给 PNG 图像应用圆角透明遮罩。"""
    size = img.width
    radius = int(size * ratio)
    img = img.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def fit_on_canvas(img: Image.Image) -> Image.Image:
    """把源图整体缩小后居中放入画布，给各平台图标保留边距。"""
    background = estimate_background_color(img)
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (*background, 255))
    fit_size = max(1, round(ICON_SIZE * CONTENT_SCALE))
    content = img.convert("RGBA")
    content.thumbnail((fit_size, fit_size), Image.LANCZOS)
    offset = ((ICON_SIZE - content.width) // 2, (ICON_SIZE - content.height) // 2)
    canvas.alpha_composite(content, offset)
    return canvas


def process_launcher_icon():
    """从 sparkarc.jpg 生成带圆角和安全留白的 app-icon-source.png。"""
    src = ROOT / "assets" / "sparkarc.jpg"
    out = ROOT / "client" / "src-tauri" / "icons" / "app-icon-source.png"

    if not src.exists():
        print(f"❌ Source image not found: {src}")
        return False

    img = fit_on_canvas(Image.open(src))
    img = apply_rounded_corners(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    radius_px = int(ICON_SIZE * CORNER_RATIO)
    print(f"✅ Launcher icon: {src.name} → {out.relative_to(ROOT)} ({ICON_SIZE}x{ICON_SIZE}, content scale {CONTENT_SCALE*100:.0f}%, corner radius {radius_px}px = {CORNER_RATIO*100:.0f}%)")
    return True


def main():
    print("🎨 SparkArc icon preprocessing")
    print(f"   Corner ratio: {CORNER_RATIO*100:.0f}% (Google Play 2026 requirement)")
    print()

    ok = process_launcher_icon()

    if ok:
        print()
        print("🎉 Done. Next run:")
        print("   npm run tauri icon src-tauri/icons/app-icon-source.png")
        print("   python scripts/patch-android-adaptive-foreground.py")
    else:
        print()
        print("⚠️ Some icon generation steps failed. Please check the source files.")


if __name__ == "__main__":
    main()
