#!/usr/bin/env python3
"""Generate missing launch week Instagram graphics for Neshama."""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")

# === Colors ===
CREAM_BG = (245, 241, 235)
DARK_BROWN = (62, 39, 35)
TERRACOTTA = (210, 105, 30)
MUTED_BROWN = (92, 83, 74)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (200, 180, 140)
DARK_STRIP = (50, 35, 30)

W, H = 1080, 1080

os.makedirs(OUTPUT_DIR, exist_ok=True)


def make_font(path, size, weight=None):
    font = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except:
            pass
    return font


def draw_divider(draw, y, width, color=DIVIDER_GOLD, length=60):
    x1 = (width - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=color, width=2)


def draw_candle(draw, cx, top_y):
    flame_color = (210, 130, 30)
    flame_center_y = top_y + 8
    for dy in range(-8, 9):
        radius = max(0, int(6 * (1 - abs(dy) / 9)))
        if dy < 0:
            radius = max(0, int(4 * (1 - abs(dy) / 8)))
        draw.ellipse(
            [cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
            fill=flame_color,
        )
    draw.rectangle([cx - 2, top_y + 18, cx + 2, top_y + 70], fill=(180, 165, 140))


def center_text(draw, text, font, y, color, width=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return bbox[3] - bbox[1]


def draw_dark_strips(draw):
    draw.rectangle([0, 0, W, 8], fill=DARK_STRIP)
    draw.rectangle([0, H - 8, W, H], fill=DARK_STRIP)


# ============================================================
# Shabbat Shalom — Saturday March 29 post
# ============================================================
def generate_shabbat_shalom():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw)

    heading_font = make_font(CORMORANT, 64)
    body_font = make_font(CRIMSON, 24)
    footer_font = make_font(CRIMSON, 20)

    # Two candles (Shabbat candles — side by side)
    draw_candle(draw, W // 2 - 25, 140)
    draw_candle(draw, W // 2 + 25, 140)

    # Heading
    y = 280
    h = center_text(draw, "Shabbat Shalom", heading_font, y, DARK_BROWN)
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 45

    # Body
    body_lines = [
        "A pause from the noise.",
        "",
        "A moment to be present",
        "with the people still here,",
        "",
        "and to carry gently the memory",
        "of those who aren't.",
    ]
    line_spacing = 36
    for line in body_lines:
        if line == "":
            y += 18
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 40

    # Divider
    draw_divider(draw, y, W)
    y += 45

    # Warm closing
    closing_font = make_font(CRIMSON, 26)
    center_text(draw, "May your Shabbat bring", closing_font, y, TERRACOTTA)
    y += 36
    center_text(draw, "rest, warmth, and connection.", closing_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "shabbat-shalom.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Created: {out_path}  ({size_kb:.0f} KB)")


# ============================================================
# Week One Reflection — Sunday March 30 post
# ============================================================
def generate_week_one_reflection():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw)

    big_font = make_font(CORMORANT, 72)
    heading_font = make_font(CORMORANT, 36)
    body_font = make_font(CRIMSON, 23)
    tagline_font = make_font(CORMORANT, 30)
    footer_font = make_font(CRIMSON, 20)

    # Candle
    draw_candle(draw, W // 2, 60)

    # Big "One week."
    y = 170
    h = center_text(draw, "One week.", big_font, y, DARK_BROWN)
    y += h + 35

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body text
    body_lines = [
        "Thank you to every person",
        "who visited, shared, and sent",
        "Neshama to someone",
        "who needed it.",
        "",
        "We didn't build this to go viral.",
        "We built it so the next time",
        "someone in your community passes,",
        "you don't have to wonder",
        "how to find out or how to help.",
        "",
        "This is just the beginning.",
    ]
    line_spacing = 33
    for line in body_lines:
        if line == "":
            y += 20
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 30

    # Divider
    draw_divider(draw, y, W)
    y += 35

    # Tagline
    center_text(draw, "Every soul remembered. Every life honoured.", tagline_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "week-one-reflection.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Created: {out_path}  ({size_kb:.0f} KB)")


# === Run ===
if __name__ == "__main__":
    generate_shabbat_shalom()
    generate_week_one_reflection()
    print("\nDone. Both launch week graphics generated.")
