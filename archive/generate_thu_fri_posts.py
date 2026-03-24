#!/usr/bin/env python3
"""
Generate 2 Instagram graphics for Neshama launch week:
- Thu Mar 27: What Neshama means (soul)
- Fri Mar 28: 3 ways to help a family sitting shiva
"""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
HEBREW = os.path.join(FONT_DIR, "NotoSerifHebrew-Regular.ttf")

# === Colors (same v3 palette) ===
CREAM_BG = (252, 249, 243)
DARK_BROWN = (72, 52, 43)
TERRACOTTA = (195, 110, 60)
MUTED_BROWN = (110, 95, 82)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)
SOFT_BORDER = (235, 225, 210)

W, H = 1080, 1080

os.makedirs(OUTPUT_DIR, exist_ok=True)


# === Helper functions (from v3) ===
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
        glow = tuple(int(g * (1 - alpha_factor * 0.3) + CREAM_BG[i] * alpha_factor * 0.3) for i, g in enumerate(glow_color))
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


def save_image(img, path):
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


def calc_content_start(total_content_height, footer_space=80):
    usable = H - footer_space
    start_y = (usable - total_content_height) // 2
    start_y = max(int(H * 0.15), start_y)
    return start_y


def wrap_text(draw, text, font, max_width):
    """Word-wrap text to fit within max_width. Returns list of lines."""
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
    return lines


# ============================================================
# POST: Thu Mar 27 — What Neshama means
# ============================================================
def generate_thu_neshama_meaning():
    img, draw = new_square()

    label_font = make_font(CRIMSON, 30)
    heading_font = make_font(CORMORANT, 82)
    hebrew_font = make_font(HEBREW, 44)
    sub_font = make_font(CORMORANT, 48)
    body_font = make_font(CRIMSON, 32)
    tagline_font = make_font(CORMORANT, 42)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 90

    # Measure content
    label_h = measure_text_height(draw, "What does", label_font)
    heading_h = measure_text_height(draw, "Neshama", heading_font)
    hebrew_h = measure_text_height(draw, "\u05E0\u05E9\u05DE\u05D4", hebrew_font)
    sub_h = measure_text_height(draw, "mean?", sub_font)
    body_line_h = measure_text_height(draw, "We chose", body_font)
    # Body: ~8 lines + 2 blank spacers
    body_total = body_line_h * 8 + 40 * 7 + 18 * 2
    tagline_h = measure_text_height(draw, "Behind every", tagline_font)

    total = candle_h + 22 + label_h + 10 + heading_h + 6 + hebrew_h + 6 + sub_h + 30 + 35 + body_total + 20 + 35 + tagline_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.2)
    y += candle_h + 22

    # Label
    h = center_text(draw, "What does", label_font, y, SAGE)
    y += h + 10

    # Big name
    h = center_text(draw, "Neshama", heading_font, y, TERRACOTTA)
    y += h + 6

    # Hebrew
    h = center_text(draw, "\u05E0\u05E9\u05DE\u05D4", hebrew_font, y, DARK_BROWN)
    y += h + 6

    # "mean?"
    h = center_text(draw, "mean?", sub_font, y, DARK_BROWN)
    y += h + 30

    draw_divider(draw, y)
    y += 35

    # Body
    lines = [
        "It means soul.",
        "",
        "This isn\u2019t about death.",
        "It\u2019s about comfort.",
        "",
        "We chose the name because",
        "behind every listing",
        "is a soul who mattered,",
        "and a family that",
        "needs comfort.",
    ]
    line_spacing = 40
    for line in lines:
        if line == "":
            y += 18
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 20

    draw_divider(draw, y)
    y += 35

    # Tagline
    h = center_text(draw, "Behind every listing is a soul.", tagline_font, y, TERRACOTTA)
    y += h + 20

    # Footer
    footer_y = min(y + 12, H - 50)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    path = os.path.join(OUTPUT_DIR, "launch-week-thu-neshama-meaning.png")
    save_image(img, path)


# ============================================================
# POST: Fri Mar 28 — 3 ways to help a family sitting shiva
# ============================================================
def generate_fri_3ways():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 62)
    num_font = make_font(CORMORANT, 46)
    body_font = make_font(CRIMSON, 30)
    bold_font = make_font(CRIMSON, 32)
    cta_font = make_font(CRIMSON, 30)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 85

    # This is a denser post — use lower start
    # Measure roughly
    heading_h = measure_text_height(draw, "3 ways to help", heading_font) * 2 + 8
    body_line_h = measure_text_height(draw, "Bring a meal", body_font)
    # 3 sections, each ~3 lines + number
    section_h = (body_line_h + 8) * 3 + 10  # per section
    total_sections = section_h * 3 + 25 * 2  # 3 sections + gaps
    cta_h = measure_text_height(draw, "neshama.ca", cta_font)

    total = candle_h + 18 + heading_h + 28 + 30 + total_sections + 20 + 30 + cta_h
    usable = H - 60
    y = max(int(H * 0.08), (usable - total) // 2)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.1)
    y += candle_h + 18

    # Heading
    h = center_text(draw, "3 ways to help a family", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "sitting shiva today", heading_font, y, DARK_BROWN)
    y += h + 28

    draw_divider(draw, y)
    y += 30

    # === Section 1: Bring a meal ===
    tip1_lines = [
        "1. Bring a meal.",
        "Not just any meal \u2014 something warm,",
        "ready to serve, enough",
        "for the whole family.",
    ]
    h = center_text(draw, tip1_lines[0], bold_font, y, TERRACOTTA)
    y += h + 10
    for line in tip1_lines[1:]:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 8

    y += 22

    # === Section 2: Send a message ===
    tip2_lines = [
        "2. Send a message.",
        "You don\u2019t need to call. A text saying",
        "\u2018thinking of you\u2019 means more",
        "than you know.",
    ]
    h = center_text(draw, tip2_lines[0], bold_font, y, TERRACOTTA)
    y += h + 10
    for line in tip2_lines[1:]:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 8

    y += 22

    # === Section 3: Just show up ===
    tip3_lines = [
        "3. Just show up.",
        "You don\u2019t need an invitation.",
        "That\u2019s what community means.",
    ]
    h = center_text(draw, tip3_lines[0], bold_font, y, TERRACOTTA)
    y += h + 10
    for line in tip3_lines[1:]:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 8

    y += 20

    draw_divider(draw, y)
    y += 30

    # CTA
    h = center_text(draw, "neshama.ca/shiva/organize", cta_font, y, TERRACOTTA)
    y += h + 18

    # Footer
    footer_y = min(y + 10, H - 45)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    path = os.path.join(OUTPUT_DIR, "launch-week-fri-3ways.png")
    save_image(img, path)


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=== Generating Thu + Fri Instagram graphics ===\n")

    print("Thu Mar 27 — What Neshama means")
    generate_thu_neshama_meaning()

    print("\nFri Mar 28 — 3 ways to help a family sitting shiva")
    generate_fri_3ways()

    print("\n=== Done — 2 graphics generated ===")
