#!/usr/bin/env python3
"""Regenerate two Instagram graphics: carousel slide 5 and mar25 one-feed."""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
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


def make_font(path, size, weight=None):
    font = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass
    return font


def draw_divider(draw, y, width=W, color=DIVIDER_GOLD, length=90):
    x1 = (width - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=color, width=2)


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
        glow = tuple(
            int(g * (1 - alpha_factor * 0.3) + CREAM_BG[i] * alpha_factor * 0.3)
            for i, g in enumerate(glow_color)
        )
        draw.ellipse(
            [cx - r, flame_center_y - r, cx + r, flame_center_y + r],
            fill=glow,
        )
    for dy in range(int(-10 * s), int(12 * s)):
        radius = max(0, int(8 * s * (1 - abs(dy) / (11 * s))))
        if dy < 0:
            radius = max(0, int(5 * s * (1 - abs(dy) / (10 * s))))
        draw.ellipse(
            [cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
            fill=flame_color,
        )
    for dy in range(int(-5 * s), int(6 * s)):
        radius = max(0, int(3 * s * (1 - abs(dy) / (6 * s))))
        draw.ellipse(
            [cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
            fill=flame_inner,
        )
    body_w = int(3 * s)
    draw.rectangle(
        [cx - body_w, top_y + int(22 * s), cx + body_w, top_y + int(70 * s)],
        fill=(195, 180, 155),
    )


def center_text(draw, text, font, y, color, width=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (width - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return th


def measure_text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def new_square():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_soft_borders(draw)
    return img, draw


def calc_content_start(total_content_height, footer_space=80):
    usable = H - footer_space
    start_y = (usable - total_content_height) // 2
    start_y = max(int(H * 0.12), start_y)
    return start_y


def draw_wrapped_text(draw, text, font, y, color, max_width, line_spacing=0):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    total_h = 0
    for line in lines:
        h = center_text(draw, line, font, y, color)
        y += h + line_spacing
        total_h += h + line_spacing
    return total_h


# ============================================================
#  CAROUSEL SLIDE 5 — matches generate_tip_slide from carousel script
# ============================================================
def generate_slide_5():
    img, draw = new_square()

    number_font = make_font(CORMORANT, 110)
    title_font = make_font(CORMORANT, 54)
    body_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 28)

    tip = {
        "number": "4",
        "title": "You don\u2019t need\nthe right words.",
        "body": "Most people avoid visiting because they don\u2019t know what to say. The truth? Your presence is the message.",
    }

    title_lines = tip["title"].split("\n")

    # Estimate total height (same as generate_tip_slide)
    num_h = 90
    title_h = len(title_lines) * 55
    body_h = 120
    total = num_h + 30 + title_h + 35 + 10 + 40 + body_h
    y = calc_content_start(total)

    # Number in large terracotta
    h = center_text(draw, tip["number"], number_font, y, TERRACOTTA)
    y += h + 25

    # Divider under number
    draw_divider(draw, y, length=60)
    y += 35

    # Title lines
    for line in title_lines:
        h = center_text(draw, line, title_font, y, DARK_BROWN)
        y += h + 10
    y += 25

    # Divider
    draw_divider(draw, y)
    y += 40

    # Body text — wrapped
    draw_wrapped_text(draw, tip["body"], body_font, y, MUTED_BROWN, max_width=W - 160, line_spacing=14)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 50, SAGE)

    path = "/Users/erinkofman/Desktop/Neshama/instagram-posts/carousel-shiva-guest/slide-5.png"
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


# ============================================================
#  MAR25 ONE FEED — matches generate_post_4 style from launch week v3
# ============================================================
def generate_one_feed():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 82)
    source_font = make_font(CRIMSON, 32)
    body_font = make_font(CRIMSON, 38)
    tagline_font = make_font(CORMORANT, 50)
    new_line_font = make_font(CRIMSON, 30)
    footer_font = make_font(CRIMSON, 30)

    candle_h = 95
    heading_h = measure_text_height(draw, "One feed.", heading_font)
    source_h = measure_text_height(draw, "Steeles", source_font)
    body_h = measure_text_height(draw, "Two cities.", body_font)
    tagline_h = measure_text_height(draw, "Comforting", tagline_font)
    new_line_h = measure_text_height(draw, "Soon", new_line_font)

    total = candle_h + 30 + heading_h + 40 + 40 + source_h + 45 + 45 + body_h + 50 + tagline_h + 20 + new_line_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    # Big heading — just "One feed." (no second line)
    h = center_text(draw, "One feed.", heading_font, y, DARK_BROWN)
    y += h + 40

    draw_divider(draw, y)
    y += 40

    # Sources
    h = center_text(
        draw,
        "Steeles \u00b7 Benjamin\u2019s \u00b7 Paperman\u2019s \u00b7 Misaskim",
        source_font,
        y,
        SAGE,
    )
    y += h + 45

    draw_divider(draw, y)
    y += 45

    # Body
    h = center_text(draw, "Two cities. One place.", body_font, y, MUTED_BROWN)
    y += h + 50

    # Tagline
    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 20

    # New line under tagline
    h = center_text(draw, "Soon, wherever our community calls home.", new_line_font, y, MUTED_BROWN)
    y += h + 25

    # Footer
    footer_y = min(y + 15, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    path = "/Users/erinkofman/Desktop/Neshama/instagram-posts/mar25-one-feed.png"
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    print("=== Regenerating two graphics ===\n")

    print("1. Carousel slide 5:")
    generate_slide_5()

    print("\n2. Mar 25 one-feed:")
    generate_one_feed()

    print("\n=== Done ===")
