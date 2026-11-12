#!/usr/bin/env python3
"""Значки приложения из packaging/icons/source.png: цветная плитка на прозрачном, белом или чёрном фоне.

Если у картинки уже есть прозрачный фон, берётся он. Иначе фон находится заливкой от углов картинки
и удаляется: чёрный – по яркости, белый с серой тенью – по малой насыщенности цвета. Результат:
  packaging/icons/icon.png   1024×1024, плитка с прозрачным фоном (Linux, документация)
  packaging/icons/icon.icns  macOS: рисунок на весь квадрат, углы скругляет сама система.
                             macOS 26 значок с прозрачными полями сажает в серую рамку
  packaging/icons/icon.ico   Windows, плитка с прозрачным фоном
Нужен Pillow.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(ROOT, "packaging", "icons")
SOURCE = os.path.join(ICONS, "source.png")
GRAY = 40    # насыщенность (0–255), ниже которой пиксель светлого фона считается фоном или тенью
DARK = 45    # яркость (0–255), ниже которой пиксель тёмного фона считается фоном
SHRINK = 3   # px: срез по краю плитки, убирает светлую кайму от фона
MAC_RADIUS = 0.2237   # радиус скругления, которым macOS обрезает значок, как доля стороны


def tile_mask(img):
    """Маска плитки: готовая прозрачность картинки или всё, кроме серо-белого фона у краёв."""
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] < 255:
        return alpha
    hsv = img.convert("RGB").convert("HSV")
    if hsv.getchannel("V").getpixel((0, 0)) < DARK:          # тёмный фон
        grayish = hsv.getchannel("V").point(lambda v: 255 if v < DARK else 0)
    else:                                                     # белый фон с серой тенью
        grayish = hsv.getchannel("S").point(lambda v: 255 if v < GRAY else 0)
    w, h = grayish.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if grayish.getpixel(corner) == 255:
            ImageDraw.floodfill(grayish, corner, 128)          # фон, достижимый от края
    background = grayish.point(lambda v: 255 if v == 128 else 0)
    mask = ImageChops.invert(background)
    mask = mask.filter(ImageFilter.MinFilter(2 * SHRINK + 1))   # срезать кайму
    return mask.filter(ImageFilter.GaussianBlur(1.2))           # мягкий край без «лесенки»


def cut():
    src = Image.open(SOURCE).convert("RGBA")
    mask = tile_mask(src)
    src.putalpha(mask)
    art = src.crop(mask.point(lambda v: 255 if v > 8 else 0).getbbox())
    side = max(art.size)   # в квадрат по центру, пропорции плитки не меняются
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def rim_color(art):
    """Средний цвет внешнего края плитки: им заполняются углы квадрата для macOS."""
    alpha = art.getchannel("A").point(lambda v: 255 if v > 250 else 0)
    ring = ImageChops.subtract(alpha, alpha.filter(ImageFilter.MinFilter(9)))
    pixels = [p for p, m in zip(art.convert("RGB").get_flattened_data(), ring.get_flattened_data()) if m]
    return tuple(sum(c) // len(pixels) for c in zip(*pixels)) + (255,)


def corner_zoom(art):
    """Во сколько раз увеличить плитку, чтобы её скруглённый угол целиком вышел за маску macOS."""
    alpha, n = art.getchannel("A"), art.width
    d = next(i for i in range(n // 2) if alpha.getpixel((i, i)) > 250) / n   # где начинается плитка по диагонали
    mac = MAC_RADIUS * (1 - 2 ** -0.5)                                      # то же у маски macOS
    return max(1.0, (0.5 - mac) / (0.5 - d))


def full_bleed(art, size=1024):
    """Непрозрачный квадрат для macOS: плитка увеличена так, чтобы её углы вышли за маску системы;
    остатки уголков – цвета края плитки."""
    big = round(size * corner_zoom(art))
    canvas = Image.new("RGBA", (size, size), rim_color(art))
    canvas.alpha_composite(art.resize((big, big), Image.LANCZOS), dest=(0, 0), source=((big - size) // 2,) * 2)
    return canvas


def main():
    art = cut()
    flat = art.resize((1024, 1024), Image.LANCZOS)
    flat.save(os.path.join(ICONS, "icon.png"))
    canvas = full_bleed(art)
    # Windows: значок без полей
    art.resize((256, 256), Image.LANCZOS).save(
        os.path.join(ICONS, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if sys.platform == "darwin" and shutil.which("iconutil"):
        tmp = tempfile.mkdtemp(suffix=".iconset")
        for n in (16, 32, 128, 256, 512):
            canvas.resize((n, n), Image.LANCZOS).save(os.path.join(tmp, f"icon_{n}x{n}.png"))
            canvas.resize((2 * n, 2 * n), Image.LANCZOS).save(os.path.join(tmp, f"icon_{n}x{n}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", tmp, "-o", os.path.join(ICONS, "icon.icns")], check=True)
        shutil.rmtree(tmp)
    print("Значки обновлены")


if __name__ == "__main__":
    main()
