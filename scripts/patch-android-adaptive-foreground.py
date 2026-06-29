from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "sparkarc.jpg"
RES_ROOT = ROOT / "client" / "src-tauri" / "gen" / "android" / "app" / "src" / "main" / "res"
FIT_RATIO = 60 / 108
TRANSPARENT_THRESHOLD = 26
OPAQUE_THRESHOLD = 72


def estimate_background_color(img: Image.Image) -> tuple[int, int, int]:
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


def remove_flat_background(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    bg = estimate_background_color(rgba)
    pixels = []
    pixel_data = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    for red, green, blue, alpha in pixel_data:
        distance = abs(red - bg[0]) + abs(green - bg[1]) + abs(blue - bg[2])
        if distance <= TRANSPARENT_THRESHOLD:
            next_alpha = 0
        elif distance >= OPAQUE_THRESHOLD:
            next_alpha = alpha
        else:
            next_alpha = round(alpha * (distance - TRANSPARENT_THRESHOLD) / (OPAQUE_THRESHOLD - TRANSPARENT_THRESHOLD))
        pixels.append((red, green, blue, next_alpha))
    rgba.putdata(pixels)
    return rgba


def build_foreground(size: tuple[int, int]) -> Image.Image:
    source = remove_flat_background(Image.open(SOURCE))
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError(f"源图没有可用前景像素：{SOURCE}")

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
        raise FileNotFoundError(f"Android 前景源图不存在：{SOURCE}")

    targets = sorted(RES_ROOT.glob("mipmap-*/ic_launcher_foreground.png"))
    if not targets:
        raise FileNotFoundError(f"未找到 Android 前景图输出目录：{RES_ROOT}")

    for target in targets:
        with Image.open(target) as existing:
            output = build_foreground(existing.size)
        output.save(target, "PNG")
        print(f"✅ Android adaptive foreground updated: {target.relative_to(ROOT)} ({output.width}x{output.height})")


if __name__ == "__main__":
    main()
