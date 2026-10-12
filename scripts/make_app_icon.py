"""Makes frontend/app-icon.png, the icon of the desktop icon (macOS app, Linux menu entry).

The shape of the application icons on macOS: a rounded square (about 80% of the canvas, the rest transparent, as the
system's own icons) in the dark colour of the logo's badge, with the kanji in the logo's blue and no ring. The kanji
is cut out of frontend/logo-mask.png (the ring lies outside RING_RADIUS); the colours are read from
frontend/logo.png, so a new logo only needs this script to be run again.

Development helper, not part of the program: it needs Pillow, which is NOT a dependency of Seisa
(python3 -m venv /tmp/v && /tmp/v/bin/pip install pillow && /tmp/v/bin/python scripts/make_app_icon.py).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
CANVAS = 1024
TILE = 824  # the body of a macOS icon on a 1024 px canvas; the margin around it stays transparent
RADIUS = 185  # corner radius of that body (the system's squircle is close to 22.4% of the body)
RING_RADIUS = 215  # in the 512 px logo, everything closer to the centre than this is the kanji (the ring starts at 232)
KANJI_SHARE = 0.62  # width of the kanji as a share of the body
SUPERSAMPLE = 4


def main() -> None:
    logo = Image.open(FRONTEND / "logo.png").convert("RGBA")
    ring_colour = logo.getpixel((256, 12))[:3]  # the blue of the ring and the kanji
    badge_colour = logo.getpixel((100, 100))[:3]  # the dark fill

    alpha = Image.open(FRONTEND / "logo-mask.png").convert("LA").getchannel("A")
    centre = alpha.width / 2
    pixels = alpha.load()
    for y in range(alpha.height):
        for x in range(alpha.width):
            if math.hypot(x - centre, y - centre) >= RING_RADIUS:
                pixels[x, y] = 0
    left, top, right, bottom = alpha.getbbox()
    kanji = alpha.crop((left, top, right, bottom))
    width = round(TILE * KANJI_SHARE)
    kanji = kanji.resize((width, round(kanji.height * width / kanji.width)), Image.LANCZOS)

    margin = (CANVAS - TILE) // 2
    big = CANVAS * SUPERSAMPLE
    body = Image.new("L", (big, big), 0)
    ImageDraw.Draw(body).rounded_rectangle(
        (margin * SUPERSAMPLE, margin * SUPERSAMPLE, (margin + TILE) * SUPERSAMPLE - 1, (margin + TILE) * SUPERSAMPLE - 1),
        radius=RADIUS * SUPERSAMPLE, fill=255,
    )
    body = body.resize((CANVAS, CANVAS), Image.LANCZOS)

    icon = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    icon.paste(Image.new("RGBA", (CANVAS, CANVAS), (*badge_colour, 255)), (0, 0), body)
    icon.paste(Image.new("RGBA", kanji.size, (*ring_colour, 255)), ((CANVAS - kanji.width) // 2, (CANVAS - kanji.height) // 2), kanji)
    icon.save(FRONTEND / "app-icon.png", optimize=True)
    print(f"app-icon.png: {CANVAS}x{CANVAS}, body {TILE}, kanji {kanji.size}, badge #{bytes(badge_colour).hex()}, blue #{bytes(ring_colour).hex()}")


if __name__ == "__main__":
    main()
