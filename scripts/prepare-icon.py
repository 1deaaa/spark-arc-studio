#!/usr/bin/env python3
"""
SparkArc 品牌图标预处理脚本

从正方形源图自动生成各平台所需的圆角 PNG 图标：
1. assets/sparkarc.jpg → client/src-tauri/icons/app-icon-source.png（30% 圆角，Tauri 图标源）
2. assets/sparkarc-light.png → client/src/assets/sparkarc-logo-rounded.png（亮色 UI Logo）
3. assets/sparkarc-dark.png → client/src/assets/sparkarc-logo-dark-rounded.png（暗色 UI Logo）

圆角半径 30% 符合 Google Play 2026.3.31 强制标准。
依赖：Pillow>=10.0.0
"""

from pathlib import Path
from PIL import Image, ImageDraw

# 项目根目录（脚本位于 scripts/ 下）
ROOT = Path(__file__).resolve().parent.parent

# 圆角比例：30%，符合 Google Play 2026.3.31 强制标准
CORNER_RATIO = 0.30
ICON_SIZE = 1024


def apply_rounded_corners(img: Image.Image, ratio: float = CORNER_RATIO) -> Image.Image:
    """为 PNG 图像添加圆角透明遮罩。"""
    size = img.width
    radius = int(size * ratio)
    # 确保图像为 RGBA
    img = img.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def process_launcher_icon():
    """从 sparkarc.jpg 生成圆角 app-icon-source.png。"""
    src = ROOT / "assets" / "sparkarc.jpg"
    out = ROOT / "client" / "src-tauri" / "icons" / "app-icon-source.png"

    if not src.exists():
        print(f"❌ 源图不存在: {src}")
        return False

    img = Image.open(src).convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    img = apply_rounded_corners(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    radius_px = int(ICON_SIZE * CORNER_RATIO)
    print(f"✅ 启动器图标: {src.name} → {out.relative_to(ROOT)} ({ICON_SIZE}x{ICON_SIZE}, 圆角 {radius_px}px = {CORNER_RATIO*100:.0f}%)")
    return True


def process_ui_logo(src_name: str, out_name: str, label: str):
    """从 assets/ 下的 PNG 复制为 UI Logo（无需圆角，背景透明即可）。"""
    src = ROOT / "assets" / src_name
    out = ROOT / "client" / "src" / "assets" / out_name

    if not src.exists():
        print(f"⚠️ 跳过 {label} Logo: 源图不存在 {src}")
        return False

    img = Image.open(src).convert("RGBA")
    # 统一缩放到 1024x1024
    if img.size != (ICON_SIZE, ICON_SIZE):
        img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print(f"✅ {label} Logo: {src.name} → {out.relative_to(ROOT)}")
    return True


def main():
    print("🎨 SparkArc 图标预处理")
    print(f"   圆角比例: {CORNER_RATIO*100:.0f}% (Google Play 2026 标准)")
    print()

    ok = True
    ok &= process_launcher_icon()
    ok &= process_ui_logo("sparkarc-light.png", "sparkarc-logo-light.png", "亮色")
    ok &= process_ui_logo("sparkarc-dark.png", "sparkarc-logo-dark.png", "暗色")

    if ok:
        print()
        print("🎉 全部完成！下一步运行:")
        print("   npm run tauri icon src-tauri/icons/app-icon-source.png")
        print("   python scripts/patch-android-adaptive-foreground.py")
    else:
        print()
        print("⚠️ 部分图标生成失败，请检查源文件")


if __name__ == "__main__":
    main()
