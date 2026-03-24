#!/usr/bin/env python3
"""
Regenerate Mar 29 Passover grief Instagram graphic.
Simplified, spacious design — grief post should feel gentle, not dense.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")

# === Colors (v3 warm palette) ===
CREAM_BG = (252, 249, 243)
DARK_BROWN = (72, 52, 43)
TERRACOTTA = (195, 110, 60)
MUTED_BROWN = (110, 95, 82)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)
SOFT_BORDER = (235, 225, 210)

W, H = 1080, 1080


def make_font(path, size):
    return ImageFont.truetype(path, size)


def draw_divider(draw, y, length=90):
    x1 = (W - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=DIVIDER_GOLD, width=2)


def draw_soft_borders(draw):
    border_h = 6
    draw.rectangle([0, 0, W, border_h], fill=SOFT_BORDER)
    draw.rectangle([0, H - border_h, W, H], fill=SOFT_BORDER)
    draw.line([(60, border_h + 12), (W - 60, border_h + 12)], fill=DIVIDER_GOLD, width=1)
    draw.line([(60, H - border_h - 12), (W - 60, H - border_h - 12)], fill=DIVIDER_GOLD, width=1)


def draw_candle(draw, cx, top_y, scale=1.0):
    flame_color = (215, 145, 50)
    flame_inner = (250, 210, 100)
    glow_color = (250, 235, 200)
    s = scale
    flame_center_y = top_y + int(10 * s)

    glow_r = int(20 * s)
    for r in range(glow_r, 0, -1):
        alpha_factor = r / glow_r
        glow = tuple(int(g * (1 - alpha_factor * 0.3) + CREAM_BG[i] * alpha_factor * 0.3) for i, g in enumerate(glow_color))
        draw.ellipse([cx - r, flame_center_y - r, cx + r, flame_center_y + r], fill=glow)

    for dy in range(int(-10 * s), int(12 * s)):
        radius = max(0, int(8 * s * (1 - abs(dy) / (11 * s))))
        if dy < 0:
            radius = max(0, int(5 * s * (1 - abs(dy) / (10 * s))))
        draw.ellipse([cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1], fill=flame_color)

    for dy in range(int(-5 * s), int(6 * s)):
        radius = max(0, int(3 * s * (1 - abs(dy) / (6 * s))))
        draw.ellipse([cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1], fill=flame_inner)

    body_w = int(3 * s)
    draw.rectangle([cx - body_w, top_y + int(22 * s), cx + body_w, top_y + int(70 * s)], fill=(195, 180, 155))


def center_text(draw, text, font, y, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return th


def generate():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_soft_borders(draw)

    # Fonts
    heading_font = make_font(CORMORANT, 72)
    body_font = make_font(CRIMSON, 34)
    tagline_font = make_font(CORMORANT, 48)
    save_font = make_font(CRIMSON, 28)
    footer_font = make_font(CRIMSON, 28)

    # Start content at ~30% from top for breathing room
    y = int(H * 0.30)

    # Candle — pushed down, starting well below top
    candle_top = y - 100  # candle sits above the heading area
    draw_candle(draw, W // 2, candle_top, scale=1.3)

    # Heading: "The empty chair / at the seder table."
    h = center_text(draw, "The empty chair", heading_font, y, DARK_BROWN)
    y += h + 12
    h = center_text(draw, "at the seder table.", heading_font, y, DARK_BROWN)
    y += h + 50  # generous spacing

    # Divider
    draw_divider(draw, y)
    y += 50  # generous spacing after divider

    # Body — only two lines
    h = center_text(draw, "An empty chair. A missing voice.", body_font, y, MUTED_BROWN)
    y += h + 18
    h = center_text(draw, "A recipe no one else makes quite the same way.", body_font, y, MUTED_BROWN)
    y += h + 55  # generous spacing

    # Divider
    draw_divider(draw, y)
    y += 55  # generous spacing

    # Terracotta tagline
    h = center_text(draw, "You are not alone.", tagline_font, y, TERRACOTTA)
    y += h + 40

    # Save line
    h = center_text(draw, "Save this for when you need it.", save_font, y, SAGE)
    y += h + 35

    # Footer
    center_text(draw, "neshama.ca", footer_font, y, SAGE)

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "mar29-passover.png")
    img.save(output_path, "PNG")
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Saved {output_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    generate()
