"""Floppy-disk artwork drawn with Pillow (no Tk dependency; also used by the build)."""

from PIL import Image, ImageDraw


def make_floppy(size=256, badge=False):
    s = 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((16, 16, 240, 240), radius=18, fill=(38, 70, 140, 255))
    d.polygon([(240, 16), (240, 62), (194, 16)], fill=(0, 0, 0, 0))        # cut corner
    d.rectangle((64, 16, 192, 92), fill=(200, 205, 215, 255))              # shutter
    d.rectangle((150, 28, 178, 80), fill=(60, 60, 70, 255))
    d.rectangle((48, 130, 208, 240), fill=(245, 245, 245, 255))            # label
    for y in (158, 184, 210):
        d.line((64, y, 192, y), fill=(150, 160, 180, 255), width=5)
    if badge:
        d.ellipse((140, 140, 250, 250), fill=(40, 190, 80, 255), outline=(255, 255, 255, 255), width=10)
    return img.resize((size, size), Image.LANCZOS) if size != s else img
