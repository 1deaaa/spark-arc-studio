from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "client" / "src" / "assets" / "sparkarc-light.png"
RES_ROOT = ROOT / "client" / "src-tauri" / "gen" / "android" / "app" / "src" / "main" / "res"
FIT_RATIO = 72 / 108


def build_foreground(size: tuple[int, int]) -> Image.Image:
    source = Image.open(SOURCE).convert("RGBA")
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError(f"Source image has no usable foreground pixels: {SOURCE}")

    content = source.crop(bbox)
    max_width = max(1, round(size[0] * FIT_RATIO))
    max_height = max(1, round(size[1] * FIT_RATIO))
    scale = min(max_width / content.width, max_height / content.height)
    resized = content.resize(
        (
            max(1, round(content.width * scale)),
            max(1, round(content.height * scale)),
        ),
        Image.LANCZOS,
    )

    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    offset = ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2)
    canvas.alpha_composite(resized, offset)
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Android foreground source image is missing: {SOURCE}")

    targets = sorted(RES_ROOT.glob("mipmap-*/ic_launcher_foreground.png"))
    if not targets:
        raise FileNotFoundError(f"Android foreground output directory was not found: {RES_ROOT}")

    for target in targets:
        with Image.open(target) as existing:
            output = build_foreground(existing.size)
        output.save(target, "PNG")
        print(f"✅ Android adaptive foreground updated: {target.relative_to(ROOT)} ({output.width}x{output.height})")


if __name__ == "__main__":
    main()
