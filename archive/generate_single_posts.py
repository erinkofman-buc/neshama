#!/usr/bin/env python3
"""Generate Instagram post graphics for Neshama."""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
HEBREW_FONT = "/Library/Fonts/Arial Unicode.ttf"

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


# === Helper functions ===
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
# POST 6: Purim — Joy and grief coexisting
# ============================================================
def generate_post_6():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw)

    # Fonts
    heading_font = make_font(CORMORANT, 52)
    body_font = make_font(CRIMSON, 24)
    cta_font = make_font(CRIMSON, 26)
    footer_font = make_font(CRIMSON, 20)

    # Candle
    draw_candle(draw, W // 2, 60)

    # Heading
    y = 155
    h = center_text(draw, "Joy and grief", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "coexist.", heading_font, y, DARK_BROWN)
    y += h + 30

    # Divider
    draw_divider(draw, y, W)
    y += 35

    # Body text block
    body_lines = [
        "Purim is a day of celebration,",
        "gifts, and feeding each other.",
        "",
        "But for families who've recently",
        "lost someone, holidays hit differently.",
        "",
        "The chair that's empty.",
        "The basket you used to send together.",
    ]
    line_spacing = 34
    for line in body_lines:
        if line == "":
            y += line_spacing
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 30

    # Divider
    draw_divider(draw, y, W)
    y += 35

    # CTA
    center_text(draw, "Check in on someone today.", cta_font, y, TERRACOTTA)
    y += 50

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "post-6-purim.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Created: {out_path}  ({size_kb:.0f} KB)")


# ============================================================
# POST 7: Founder Story — Why the name Neshama
# ============================================================
def generate_post_7():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw)

    # Fonts
    small_sage_font = make_font(CRIMSON, 22)
    heading_font = make_font(CORMORANT, 56)
    hebrew_font = make_font(HEBREW_FONT, 24)
    body_font = make_font(CRIMSON, 23)
    tagline_font = make_font(CORMORANT, 30)
    footer_font = make_font(CRIMSON, 20)

    # Candle
    draw_candle(draw, W // 2, 50)

    # Small sage text
    y = 140
    h = center_text(draw, "Why we chose the name", small_sage_font, y, SAGE)
    y += h + 12

    # Large terracotta heading
    h = center_text(draw, "Neshama", heading_font, y, TERRACOTTA)
    y += h + 14

    # Hebrew text
    h = center_text(draw, "\u05E0 \u05E9 \u05DE \u05D4", hebrew_font, y, MUTED_BROWN)
    y += h + 22

    # Divider
    draw_divider(draw, y, W)
    y += 32

    # Body text block
    body_lines = [
        ("Neshama means \u2018soul\u2019 in Hebrew.", False),
        ("BLANK_20", True),
        ("Not \u2018obituary app.\u2019", False),
        ("Not \u2018death notification service.\u2019", False),
        ("BLANK_20", True),
        ("Soul.", False),
        ("BLANK_20", True),
        ("Because that\u2019s what we\u2019re honouring \u2014", False),
        ("not the fact that someone died,", False),
        ("but the fact that someone lived.", False),
    ]
    line_spacing = 32
    for line, is_blank in body_lines:
        if is_blank:
            y += 20
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 28

    # Divider
    draw_divider(draw, y, W)
    y += 32

    # Tagline
    center_text(draw, "Every soul remembered.", tagline_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "post-7-founder-story.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Created: {out_path}  ({size_kb:.0f} KB)")


# === Run ===
if __name__ == "__main__":
    generate_post_6()
    generate_post_7()
    print("\nDone. Both posts generated.")
