#!/usr/bin/env python3
"""SparkArc icon preprocessing script.

Generates the rounded PNG source image used by platform packaging:
assets/sparkarc.jpg → client/src-tauri/icons/app-icon-source.png

UI logo assets (sparkarc-light.png / sparkarc-dark.png) are maintained
manually under client/src/assets/ and are not modified by this script.
The 30% corner radius follows the Google Play 2026-03-31 requirement.
Dependency: Pillow>=10.0.0
"""

from pathlib import Path
from PIL import Image, ImageDraw

# Project root (this script lives under scripts/).
ROOT = Path(__file__).resolve().parent.parent

# Rounded-corner ratio: 30%, matching the Google Play 2026-03-31 requirement.
CORNER_RATIO = 0.30
ICON_SIZE = 1024


def apply_rounded_corners(img: Image.Image, ratio: float = CORNER_RATIO) -> Image.Image:
    """Apply a rounded alpha mask to a PNG image."""
    size = img.width
    radius = int(size * ratio)
    # Ensure the image is in RGBA mode.
    img = img.convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def process_launcher_icon():
    """Generate the rounded app-icon-source.png from sparkarc.jpg."""
    src = ROOT / "assets" / "sparkarc.jpg"
    out = ROOT / "client" / "src-tauri" / "icons" / "app-icon-source.png"

    if not src.exists():
        print(f"❌ Source image not found: {src}")
        return False

    img = Image.open(src).convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    img = apply_rounded_corners(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    radius_px = int(ICON_SIZE * CORNER_RATIO)
    print(f"✅ Launcher icon: {src.name} → {out.relative_to(ROOT)} ({ICON_SIZE}x{ICON_SIZE}, corner radius {radius_px}px = {CORNER_RATIO*100:.0f}%)")
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
