#!/usr/bin/env python3
"""
Generate 7 launch week Instagram graphics for Neshama (Mar 23-28, 2026).
Version 2: LARGER fonts (~40-50% increase) + updated tagline.

Posts:
  1. Mar 23 (Sun)  - Pre-launch teaser: "Tomorrow changes everything"
  2. Mar 24 (Mon AM) - Launch announcement: "We're live"
  3. Mar 24 (Mon PM) - Founder story: "Why I built Neshama"
  4. Mar 25 (Tue)  - One feed: "Comforting our community"
  5. Mar 26 (Wed)  - Nichum aveilim: showing up for mourners
  6. Mar 27 (Fri)  - Shabbat Shalom
  7. Mar 28 (Sat)  - Week one reflection
"""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")

# === Colors ===
CREAM_BG = (250, 249, 246)       # #FAF9F6
DARK_BROWN = (62, 39, 35)
TERRACOTTA = (210, 105, 30)      # #D2691E
MUTED_BROWN = (92, 83, 74)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (200, 180, 140)
DARK_STRIP = (50, 35, 30)

W, H = 1080, 1080
STRIP_H = 8

os.makedirs(OUTPUT_DIR, exist_ok=True)


# === Helper functions ===
def make_font(path, size, weight=None):
    font = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass
    return font


def draw_divider(draw, y, width=W, color=DIVIDER_GOLD, length=80):
    x1 = (width - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=color, width=2)


def draw_candle(draw, cx, top_y, scale=1.0):
    """Draw a memorial candle. scale > 1 makes it bigger."""
    flame_color = (210, 130, 30)
    flame_inner = (245, 200, 80)
    s = scale
    flame_center_y = top_y + int(10 * s)
    # Outer flame
    for dy in range(int(-10 * s), int(12 * s)):
        radius = max(0, int(8 * s * (1 - abs(dy) / (11 * s))))
        if dy < 0:
            radius = max(0, int(5 * s * (1 - abs(dy) / (10 * s))))
        draw.ellipse(
            [cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
            fill=flame_color,
        )
    # Inner glow
    for dy in range(int(-5 * s), int(6 * s)):
        radius = max(0, int(3 * s * (1 - abs(dy) / (6 * s))))
        draw.ellipse(
            [cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
            fill=flame_inner,
        )
    # Candle body
    body_w = int(3 * s)
    draw.rectangle(
        [cx - body_w, top_y + int(22 * s), cx + body_w, top_y + int(80 * s)],
        fill=(180, 165, 140),
    )


def center_text(draw, text, font, y, color, width=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return bbox[3] - bbox[1]


def draw_dark_strips(draw):
    draw.rectangle([0, 0, W, STRIP_H], fill=DARK_STRIP)
    draw.rectangle([0, H - STRIP_H, W, H], fill=DARK_STRIP)


def new_square():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw)
    return img, draw


def save_image(img, path):
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


# ============================================================
# POST 1: Mar 23 (Sun) — Pre-launch teaser
# ============================================================
def generate_post_1():
    img, draw = new_square()

    # Fonts — ~40-50% larger than originals
    heading_font = make_font(CORMORANT, 84)
    body_font = make_font(CRIMSON, 36)
    date_font = make_font(CRIMSON, 32)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 60, scale=1.4)

    # Heading
    y = 200
    h = center_text(draw, "Tomorrow", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "changes", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "everything.", heading_font, y, TERRACOTTA)
    y += h + 45

    # Divider
    draw_divider(draw, y)
    y += 50

    # Body
    lines = [
        "Something the community",
        "has been missing.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 14

    y += 30

    # Date
    center_text(draw, "March 24, 2026", date_font, y, SAGE)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-1.png"))


# ============================================================
# POST 2: Mar 24 AM — Launch announcement
# ============================================================
def generate_post_2():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 90)
    sub_font = make_font(CORMORANT, 48)
    body_font = make_font(CRIMSON, 34)
    cta_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 55, scale=1.4)

    # Big heading
    y = 190
    h = center_text(draw, "We're live.", heading_font, y, DARK_BROWN)
    y += h + 20

    # Subtitle
    h = center_text(draw, "Comforting Our Community", sub_font, y, TERRACOTTA)
    y += h + 40

    draw_divider(draw, y)
    y += 45

    # Body
    lines = [
        "Toronto & Montreal obituaries.",
        "One respectful feed.",
        "Shiva meal coordination.",
        "Memorial tributes.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 16

    y += 35

    draw_divider(draw, y)
    y += 45

    # CTA
    center_text(draw, "Visit neshama.ca", cta_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-2.png"))


# ============================================================
# POST 3: Mar 24 PM — Founder story
# ============================================================
def generate_post_3():
    img, draw = new_square()

    label_font = make_font(CRIMSON, 30)
    heading_font = make_font(CORMORANT, 78)
    body_font = make_font(CRIMSON, 32)
    tagline_font = make_font(CORMORANT, 42)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 50, scale=1.3)

    # Label
    y = 175
    h = center_text(draw, "Why I built", label_font, y, SAGE)
    y += h + 10

    # Big name
    h = center_text(draw, "Neshama", heading_font, y, TERRACOTTA)
    y += h + 30

    draw_divider(draw, y)
    y += 40

    # Body
    lines = [
        "When someone in our community passes,",
        "you shouldn't have to search",
        "five different websites to find out.",
        "",
        "You shouldn't have to wonder",
        "how to help the family.",
        "",
        "I built Neshama so that",
        "no one grieves without",
        "their community knowing.",
    ]
    line_spacing = 40
    for line in lines:
        if line == "":
            y += 22
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 25

    draw_divider(draw, y)
    y += 40

    # Tagline
    center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-3.png"))


# ============================================================
# POST 4: Mar 25 (Tue) — One feed / Comforting our community
# ============================================================
def generate_post_4():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 82)
    sub_font = make_font(CRIMSON, 34)
    source_font = make_font(CRIMSON, 30)
    body_font = make_font(CRIMSON, 36)
    tagline_font = make_font(CORMORANT, 50)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 55, scale=1.4)

    # Big heading
    y = 195
    h = center_text(draw, "One feed", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "instead of five.", heading_font, y, DARK_BROWN)
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
    center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-4.png"))


# ============================================================
# POST 5: Mar 26 (Wed) — Nichum aveilim
# ============================================================
def generate_post_5():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 72)
    hebrew_font = make_font(CRIMSON, 30)
    body_font = make_font(CRIMSON, 34)
    cta_font = make_font(CRIMSON, 36)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 50, scale=1.3)

    # Heading
    y = 185
    h = center_text(draw, "Showing up", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "for mourners.", heading_font, y, DARK_BROWN)
    y += h + 18

    # Hebrew concept
    h = center_text(draw, "Nichum Aveilim \u2014 \u05E0\u05D9\u05D7\u05D5\u05DD \u05D0\u05D1\u05DC\u05D9\u05DD", hebrew_font, y, SAGE)
    y += h + 35

    draw_divider(draw, y)
    y += 40

    # Body
    lines = [
        "In Jewish tradition,",
        "comforting the bereaved",
        "isn\u2019t optional \u2014 it\u2019s a mitzvah.",
        "",
        "Bringing food. Sitting in silence.",
        "Just being there.",
        "",
        "Neshama helps you show up",
        "when it matters most.",
    ]
    line_spacing = 42
    for line in lines:
        if line == "":
            y += 22
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 25

    draw_divider(draw, y)
    y += 40

    # CTA
    center_text(draw, "neshama.ca/shiva-organize", cta_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-5.png"))


# ============================================================
# POST 6: Mar 27 (Fri) — Shabbat Shalom
# ============================================================
def generate_post_6():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 90)
    body_font = make_font(CRIMSON, 36)
    closing_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 28)

    # Two Shabbat candles
    draw_candle(draw, W // 2 - 35, 120, scale=1.5)
    draw_candle(draw, W // 2 + 35, 120, scale=1.5)

    # Heading
    y = 280
    h = center_text(draw, "Shabbat Shalom", heading_font, y, DARK_BROWN)
    y += h + 45

    draw_divider(draw, y)
    y += 50

    # Body
    lines = [
        "A pause from the noise.",
        "",
        "A moment to be present",
        "with the people still here,",
        "",
        "and to carry gently the memory",
        "of those who aren\u2019t.",
    ]
    line_spacing = 46
    for line in lines:
        if line == "":
            y += 20
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 35

    draw_divider(draw, y)
    y += 45

    # Warm closing
    center_text(draw, "May your Shabbat bring", closing_font, y, TERRACOTTA)
    y += 48
    center_text(draw, "rest, warmth, and connection.", closing_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-6.png"))


# ============================================================
# POST 7: Mar 28 (Sat) — Week one reflection
# ============================================================
def generate_post_7():
    img, draw = new_square()

    big_font = make_font(CORMORANT, 100)
    body_font = make_font(CRIMSON, 34)
    tagline_font = make_font(CORMORANT, 44)
    footer_font = make_font(CRIMSON, 28)

    # Candle
    draw_candle(draw, W // 2, 50, scale=1.4)

    # Big heading
    y = 185
    h = center_text(draw, "One week.", big_font, y, DARK_BROWN)
    y += h + 40

    draw_divider(draw, y)
    y += 45

    # Body
    lines = [
        "Thank you to every person",
        "who visited, shared, and sent",
        "Neshama to someone",
        "who needed it.",
        "",
        "We didn\u2019t build this to go viral.",
        "We built it so the next time",
        "someone in your community passes,",
        "you know where to go.",
        "",
        "This is just the beginning.",
    ]
    line_spacing = 42
    for line in lines:
        if line == "":
            y += 22
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 30

    draw_divider(draw, y)
    y += 40

    # Tagline — updated
    center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 65, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-7.png"))


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=== Neshama Launch Week Graphics (v2 — larger fonts) ===\n")

    print("Post 1: Mar 23 — Pre-launch teaser")
    generate_post_1()

    print("\nPost 2: Mar 24 AM — Launch announcement")
    generate_post_2()

    print("\nPost 3: Mar 24 PM — Founder story")
    generate_post_3()

    print("\nPost 4: Mar 25 — One feed / Comforting our community")
    generate_post_4()

    print("\nPost 5: Mar 26 — Nichum aveilim")
    generate_post_5()

    print("\nPost 6: Mar 27 — Shabbat Shalom")
    generate_post_6()

    print("\nPost 7: Mar 28 — Week one reflection")
    generate_post_7()

    print("\n=== Done — 7 launch week graphics generated ===")
