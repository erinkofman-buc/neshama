#!/usr/bin/env python3
"""
Generate 7 launch week Instagram graphics for Neshama (Mar 23-28, 2026).
Version 3: Vertically centered, warm greeting-card feel, better spacing.

+ Bonus: Passover grief post (launch-week-bonus-passover.png)

Design changes from v2:
- Content vertically centered (starts ~25% down, not 8%)
- No harsh dark brown strips — replaced with soft warm gradient edges
- Candle integrated into composition (not floating at very top)
- Reduced gap between body text and neshama.ca footer
- Warmer terracotta, softer palette
- Slightly increased line spacing for 50-80 year old readability
- Overall: warm greeting card, not tech slide
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
HEBREW = os.path.join(FONT_DIR, "NotoSerifHebrew-Regular.ttf")

# === Colors (warmer, softer) ===
CREAM_BG = (252, 249, 243)          # Warmer cream
DARK_BROWN = (72, 52, 43)           # Softer dark brown (not black-brown)
TERRACOTTA = (195, 110, 60)         # Warmer, less jarring terracotta
MUTED_BROWN = (110, 95, 82)         # Readable warm brown for body
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)      # Warm gold divider
SOFT_BORDER = (235, 225, 210)       # Soft warm border instead of dark strips

W, H = 1080, 1080

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


def draw_divider(draw, y, width=W, color=DIVIDER_GOLD, length=90):
    """Warm gold divider line, centered."""
    x1 = (width - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=color, width=2)


def draw_soft_borders(draw):
    """Soft warm gradient borders instead of harsh dark strips."""
    border_h = 6
    # Top border — soft warm line
    draw.rectangle([0, 0, W, border_h], fill=SOFT_BORDER)
    # Bottom border
    draw.rectangle([0, H - border_h, W, H], fill=SOFT_BORDER)
    # Add a subtle inner line for warmth
    draw.line([(60, border_h + 12), (W - 60, border_h + 12)], fill=DIVIDER_GOLD, width=1)
    draw.line([(60, H - border_h - 12), (W - 60, H - border_h - 12)], fill=DIVIDER_GOLD, width=1)


def draw_candle(draw, cx, top_y, scale=1.0):
    """Draw a memorial candle with warm glow."""
    flame_color = (215, 145, 50)
    flame_inner = (250, 210, 100)
    glow_color = (250, 235, 200)
    s = scale
    flame_center_y = top_y + int(10 * s)

    # Soft glow behind flame
    glow_r = int(20 * s)
    for r in range(glow_r, 0, -1):
        alpha_factor = r / glow_r
        glow = tuple(int(g * (1 - alpha_factor * 0.3) + CREAM_BG[i] * alpha_factor * 0.3) for i, g in enumerate(glow_color))
        draw.ellipse(
            [cx - r, flame_center_y - r, cx + r, flame_center_y + r],
            fill=glow,
        )

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
    # Candle body — slightly warmer color
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
    """Center content vertically, accounting for footer.
    Returns the Y coordinate to start drawing content."""
    usable = H - footer_space
    start_y = (usable - total_content_height) // 2
    # Ensure minimum 15% from top
    start_y = max(int(H * 0.15), start_y)
    return start_y


# ============================================================
# POST 1: Mar 23 (Sun) — Pre-launch teaser
# ============================================================
def generate_post_1():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 84)
    body_font = make_font(CRIMSON, 38)
    date_font = make_font(CRIMSON, 34)
    footer_font = make_font(CRIMSON, 30)

    # Measure content height to center
    candle_h = 95
    heading_h = measure_text_height(draw, "Tomorrow", heading_font) * 3 + 16  # 3 lines
    gap1 = 40
    divider_gap = 45
    body_h = measure_text_height(draw, "Something", body_font) * 2 + 14
    gap2 = 30
    date_h = measure_text_height(draw, "March 24", date_font)

    total = candle_h + 30 + heading_h + gap1 + divider_gap + body_h + gap2 + date_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    # Heading
    h = center_text(draw, "Tomorrow", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "changes", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "everything.", heading_font, y, TERRACOTTA)
    y += h + gap1

    draw_divider(draw, y)
    y += divider_gap

    # Body
    lines = [
        "Something the community",
        "has been missing.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 14

    y += gap2

    # Date
    center_text(draw, "March 24, 2026", date_font, y, SAGE)
    y += date_h + 30

    # Footer — close to content, not at very bottom
    footer_y = min(y + 20, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-1.png"))


# ============================================================
# POST 2: Mar 24 AM — Launch announcement
# ============================================================
def generate_post_2():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 90)
    sub_font = make_font(CORMORANT, 48)
    body_font = make_font(CRIMSON, 36)
    cta_font = make_font(CRIMSON, 40)
    footer_font = make_font(CRIMSON, 30)

    # Measure for centering
    candle_h = 95
    heading_h = measure_text_height(draw, "We're live.", heading_font)
    sub_h = measure_text_height(draw, "Comforting", sub_font)
    body_lines_h = measure_text_height(draw, "Toronto", body_font) * 4 + 16 * 3
    cta_h = measure_text_height(draw, "Visit", cta_font)

    total = candle_h + 30 + heading_h + 20 + sub_h + 40 + 45 + body_lines_h + 35 + 45 + cta_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    # Big heading
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
        y += h + 18

    y += 30

    draw_divider(draw, y)
    y += 45

    # CTA
    h = center_text(draw, "Visit neshama.ca", cta_font, y, TERRACOTTA)
    y += h + 30

    # Footer
    footer_y = min(y + 15, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-2.png"))


# ============================================================
# POST 3: Mar 24 PM — Founder story
# ============================================================
def generate_post_3():
    img, draw = new_square()

    label_font = make_font(CRIMSON, 32)
    heading_font = make_font(CORMORANT, 78)
    body_font = make_font(CRIMSON, 34)
    tagline_font = make_font(CORMORANT, 44)
    footer_font = make_font(CRIMSON, 30)

    # Measure for centering
    candle_h = 90
    label_h = measure_text_height(draw, "Why I built", label_font)
    name_h = measure_text_height(draw, "Neshama", heading_font)
    body_line_h = measure_text_height(draw, "When", body_font)
    # 7 text lines + 2 blank gaps
    body_total = body_line_h * 7 + 44 * 6 + 22 * 2
    tagline_h = measure_text_height(draw, "Comforting", tagline_font)

    total = candle_h + 25 + label_h + 10 + name_h + 30 + 40 + body_total + 25 + 40 + tagline_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.2)
    y += candle_h + 25

    # Label
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
    line_spacing = 44
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
    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 25

    # Footer
    footer_y = min(y + 15, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-3.png"))


# ============================================================
# POST 4: Mar 25 (Tue) — One feed / Comforting our community
# ============================================================
def generate_post_4():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 82)
    source_font = make_font(CRIMSON, 32)
    body_font = make_font(CRIMSON, 38)
    tagline_font = make_font(CORMORANT, 50)
    footer_font = make_font(CRIMSON, 30)

    candle_h = 95
    heading_h = measure_text_height(draw, "One feed", heading_font) * 2 + 8
    source_h = measure_text_height(draw, "Steeles", source_font)
    body_h = measure_text_height(draw, "Two cities.", body_font)
    tagline_h = measure_text_height(draw, "Comforting", tagline_font)

    total = candle_h + 30 + heading_h + 40 + 40 + source_h + 45 + 45 + body_h + 50 + tagline_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    # Big heading
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
    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 25

    # Footer
    footer_y = min(y + 15, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-4.png"))


# ============================================================
# POST 5: Mar 26 (Wed) — Nichum aveilim
# ============================================================
def generate_post_5():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 66)
    hebrew_font = make_font(CRIMSON, 30)
    body_font = make_font(CRIMSON, 32)
    cta_font = make_font(CRIMSON, 34)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 85
    heading_h = measure_text_height(draw, "Showing up", heading_font) * 2 + 8
    hebrew_h = measure_text_height(draw, "Nichum", hebrew_font)
    body_line_h = measure_text_height(draw, "In Jewish", body_font)
    body_total = body_line_h * 6 + 40 * 5 + 18 * 2
    cta_h = measure_text_height(draw, "neshama.ca", cta_font)

    total = candle_h + 22 + heading_h + 15 + hebrew_h + 30 + 35 + body_total + 20 + 35 + cta_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.15)
    y += candle_h + 22

    # Heading
    h = center_text(draw, "Showing up", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "for mourners.", heading_font, y, DARK_BROWN)
    y += h + 15

    # Hebrew concept
    h = center_text(draw, "Nichum Aveilim \u2014 \u05E0\u05D9\u05D7\u05D5\u05DD \u05D0\u05D1\u05DC\u05D9\u05DD", hebrew_font, y, SAGE)
    y += h + 30

    draw_divider(draw, y)
    y += 35

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

    # CTA
    h = center_text(draw, "neshama.ca/shiva-organize", cta_font, y, TERRACOTTA)
    y += h + 20

    # Footer
    footer_y = min(y + 12, H - 50)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-5.png"))


# ============================================================
# POST 6: Mar 27 (Fri) — Shabbat Shalom
# ============================================================
def generate_post_6():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 90)
    body_font = make_font(CRIMSON, 38)
    closing_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 30)

    candle_h = 110
    heading_h = measure_text_height(draw, "Shabbat Shalom", heading_font)
    body_line_h = measure_text_height(draw, "A pause", body_font)
    body_total = body_line_h * 5 + 48 * 4 + 20 * 2
    closing_h = measure_text_height(draw, "May your", closing_font) * 2 + 50

    total = candle_h + 30 + heading_h + 40 + 45 + body_total + 35 + 45 + closing_h
    y = calc_content_start(total)

    # Two Shabbat candles side by side
    draw_candle(draw, W // 2 - 30, y, scale=1.4)
    draw_candle(draw, W // 2 + 30, y, scale=1.4)
    y += candle_h + 30

    # Heading
    h = center_text(draw, "Shabbat Shalom", heading_font, y, DARK_BROWN)
    y += h + 40

    draw_divider(draw, y)
    y += 45

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
    line_spacing = 48
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
    h = center_text(draw, "May your Shabbat bring", closing_font, y, TERRACOTTA)
    y += h + 12
    h = center_text(draw, "rest, warmth, and connection.", closing_font, y, TERRACOTTA)
    y += h + 25

    # Footer
    footer_y = min(y + 15, H - 55)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-6.png"))


# ============================================================
# POST 7: Mar 28 (Sat) — Week one reflection
# ============================================================
def generate_post_7():
    img, draw = new_square()

    big_font = make_font(CORMORANT, 90)
    body_font = make_font(CRIMSON, 34)
    tagline_font = make_font(CORMORANT, 44)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 90
    heading_h = measure_text_height(draw, "One week.", big_font)
    body_line_h = measure_text_height(draw, "Thank you", body_font)
    body_total = body_line_h * 8 + 40 * 7 + 20 * 2
    tagline_h = measure_text_height(draw, "Comforting", tagline_font)

    total = candle_h + 25 + heading_h + 35 + 40 + body_total + 25 + 35 + tagline_h
    y = calc_content_start(total)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.2)
    y += candle_h + 25

    # Big heading
    h = center_text(draw, "One week.", big_font, y, DARK_BROWN)
    y += h + 35

    draw_divider(draw, y)
    y += 40

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
    line_spacing = 40
    for line in lines:
        if line == "":
            y += 20
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 25

    draw_divider(draw, y)
    y += 35

    # Tagline
    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 20

    # Footer
    footer_y = min(y + 12, H - 50)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-7.png"))


# ============================================================
# BONUS: Passover grief post
# ============================================================
def generate_passover_bonus():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 64)
    sub_font = make_font(CORMORANT, 42)
    body_font = make_font(CRIMSON, 32)
    tagline_font = make_font(CORMORANT, 40)
    save_font = make_font(CRIMSON, 28)
    footer_font = make_font(CRIMSON, 28)

    # Tighter measurements for this dense post
    candle_h = 80
    heading_h = measure_text_height(draw, "The empty chair", heading_font) * 2 + 8
    sub_h = measure_text_height(draw, "Passover", sub_font)
    body_line_h = measure_text_height(draw, "The seder", body_font)
    body_total = body_line_h * 8 + 38 * 7 + 18 * 2
    tagline_h = measure_text_height(draw, "Comforting", tagline_font)
    save_h = measure_text_height(draw, "Save this", save_font)

    total = candle_h + 20 + heading_h + 12 + sub_h + 28 + 35 + body_total + 20 + 35 + tagline_h + 20 + save_h
    # Use a lower minimum start for this dense post
    usable = H - 60
    y = max(int(H * 0.08), (usable - total) // 2)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.1)
    y += candle_h + 20

    # Heading
    h = center_text(draw, "The empty chair", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "at the seder table.", heading_font, y, DARK_BROWN)
    y += h + 12

    # Subtitle
    h = center_text(draw, "Passover & Grief", sub_font, y, TERRACOTTA)
    y += h + 28

    draw_divider(draw, y)
    y += 35

    # Body
    lines = [
        "The seder asks us to remember.",
        "But some memories carry weight",
        "this time of year.",
        "",
        "An empty chair. A missing voice.",
        "A recipe no one else makes",
        "quite the same way.",
        "",
        "You are not alone in feeling this.",
        "Your community is here.",
    ]
    line_spacing = 38
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
    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 20

    # Save prompt
    h = center_text(draw, "Save this for when you need it.", save_font, y, SAGE)
    y += h + 18

    # Footer
    footer_y = min(y + 10, H - 45)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "launch-week-bonus-passover.png"))


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=== Neshama Launch Week Graphics (v3 — centered, warm greeting card) ===\n")

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

    print("\nBonus: Passover grief post")
    generate_passover_bonus()

    print("\n=== Done — 7 launch week + 1 bonus Passover graphic generated ===")
