#!/usr/bin/env python3
"""
Generate 4 Instagram posts for the week of March 16–22, 2026.
  1. Passover Grief Carousel (7 slides, 1080x1350)
  2. Meal Coordination (single, 1080x1080)
  3. One Feed (single, 1080x1080)
  4. March 24 Teaser (single, 1080x1080)
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ── Paths ──────────────────────────────────────────────────────────
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
BASE_OUTPUT = "/Users/erinkofman/Desktop/Neshama/instagram-posts"

# ── Colors ─────────────────────────────────────────────────────────
CREAM_BG = (245, 241, 235)
DARK_BROWN = (62, 39, 35)
TERRACOTTA = (210, 105, 30)
MUTED_BROWN = (92, 83, 74)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (200, 180, 140)
DARK_STRIP = (50, 35, 30)

# ── Dimensions ─────────────────────────────────────────────────────
SQUARE_W, SQUARE_H = 1080, 1080
PORT_W, PORT_H = 1080, 1350
STRIP_H = 8


# ── Helper functions ───────────────────────────────────────────────
def make_font(path, size, weight=None):
    font = ImageFont.truetype(path, size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
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


def center_text(draw, text, font, y, color, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (width - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return bbox[3] - bbox[1]


def draw_dark_strips(draw, w, h):
    draw.rectangle([0, 0, w, STRIP_H], fill=DARK_STRIP)
    draw.rectangle([0, h - STRIP_H, w, h], fill=DARK_STRIP)


def new_portrait_slide():
    img = Image.new("RGB", (PORT_W, PORT_H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw, PORT_W, PORT_H)
    return img, draw


def new_square():
    img = Image.new("RGB", (SQUARE_W, SQUARE_H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_dark_strips(draw, SQUARE_W, SQUARE_H)
    return img, draw


def save_image(img, path):
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


# ── Pre-load fonts ─────────────────────────────────────────────────
heading_lg = make_font(CORMORANT, 56, weight=700)
heading_md = make_font(CORMORANT, 48, weight=700)
heading_sm = make_font(CORMORANT, 40, weight=700)
body_font = make_font(CRIMSON, 26, weight=400)
body_sm = make_font(CRIMSON, 22, weight=400)
body_xs = make_font(CRIMSON, 20, weight=400)
cta_font = make_font(CRIMSON, 26, weight=400)
footer_font = make_font(CRIMSON, 20, weight=400)
bullet_font = make_font(CRIMSON, 24, weight=400)
subtitle_font = make_font(CRIMSON, 24, weight=400)
sage_small = make_font(CRIMSON, 22, weight=400)


# ══════════════════════════════════════════════════════════════════
#  POST 1: Passover Grief Carousel — 7 slides (1080x1350)
# ══════════════════════════════════════════════════════════════════
CAROUSEL_DIR = os.path.join(BASE_OUTPUT, "carousel-passover-grief")


def carousel_slide_1():
    img, draw = new_portrait_slide()
    y = 180

    draw_candle(draw, PORT_W // 2, y)
    y += 110

    h = center_text(draw, "The First Pesach", heading_lg, y, DARK_BROWN, PORT_W)
    y += h + 8
    h = center_text(draw, "After a Loss", heading_lg, y, DARK_BROWN, PORT_W)
    y += h + 50

    draw_divider(draw, y, PORT_W)
    y += 45

    center_text(draw, "Save this for someone who needs it.", sage_small, y, SAGE, PORT_W)

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_1.png"))


def carousel_slide_2():
    img, draw = new_portrait_slide()
    y = 280

    h = center_text(draw, "The seder table", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 8
    h = center_text(draw, "feels different now.", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 50

    draw_divider(draw, y, PORT_W)
    y += 45

    lines = [
        "The chair where they always sat.",
        "The melody only they knew.",
        "The questions they always asked.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN, PORT_W)
        y += h + 14

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_2.png"))


def carousel_slide_3():
    img, draw = new_portrait_slide()
    y = 280

    h = center_text(draw, "Grief doesn\u2019t pause", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 8
    h = center_text(draw, "for holidays.", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 50

    draw_divider(draw, y, PORT_W)
    y += 45

    lines = [
        "Jewish holidays can be the hardest days \u2014",
        "because they were built",
        "around togetherness.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN, PORT_W)
        y += h + 14

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_3.png"))


def carousel_slide_4():
    img, draw = new_portrait_slide()
    y = 240

    lines_heading = [
        "You might not want to",
        "host this year.",
    ]
    for line in lines_heading:
        h = center_text(draw, line, heading_md, y, DARK_BROWN, PORT_W)
        y += h + 8
    y += 30

    h = center_text(draw, "You might not want to go.", body_font, y, MUTED_BROWN, PORT_W)
    y += h + 40

    draw_divider(draw, y, PORT_W)
    y += 45

    h = center_text(draw, "Both are okay.", heading_sm, y, TERRACOTTA, PORT_W)
    y += h + 30

    h = center_text(draw, "There is no wrong way to do this.", body_font, y, MUTED_BROWN, PORT_W)

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_4.png"))


def carousel_slide_5():
    img, draw = new_portrait_slide()
    y = 240

    h = center_text(draw, "What helps:", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 40

    draw_divider(draw, y, PORT_W)
    y += 45

    bullets = [
        "Let someone else host",
        "Keep one tradition alive",
        "Say their name at the table",
        "Set a place, or don\u2019t",
    ]
    for bullet in bullets:
        text = f"\u2022  {bullet}"
        h = center_text(draw, text, bullet_font, y, MUTED_BROWN, PORT_W)
        y += h + 22

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_5.png"))


def carousel_slide_6():
    img, draw = new_portrait_slide()
    y = 220

    h = center_text(draw, "What the community", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 8
    h = center_text(draw, "can do:", heading_md, y, DARK_BROWN, PORT_W)
    y += h + 40

    draw_divider(draw, y, PORT_W)
    y += 45

    bullets = [
        "Invite, don\u2019t pressure",
        "Bring a dish",
        "Mention who\u2019s missing",
        "Check in after the seder",
    ]
    for bullet in bullets:
        text = f"\u2022  {bullet}"
        h = center_text(draw, text, bullet_font, y, MUTED_BROWN, PORT_W)
        y += h + 22

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_6.png"))


def carousel_slide_7():
    img, draw = new_portrait_slide()
    y = 250

    draw_candle(draw, PORT_W // 2, y)
    y += 110

    lines = [
        "Neshama is here \u2014",
        "before, during,",
        "and after loss.",
    ]
    for line in lines:
        h = center_text(draw, line, heading_md, y, DARK_BROWN, PORT_W)
        y += h + 8
    y += 40

    draw_divider(draw, y, PORT_W)
    y += 45

    center_text(draw, "neshama.ca", heading_sm, y, TERRACOTTA, PORT_W)

    center_text(draw, "neshama.ca", footer_font, PORT_H - 55, SAGE, PORT_W)
    save_image(img, os.path.join(CAROUSEL_DIR, "slide_7.png"))


# ══════════════════════════════════════════════════════════════════
#  POST 2: Meal Coordination — single 1080x1080
# ══════════════════════════════════════════════════════════════════
def generate_post_8():
    img, draw = new_square()

    # Candle
    draw_candle(draw, SQUARE_W // 2, 60)

    # Heading
    y = 155
    h = center_text(draw, "Who\u2019s coordinating", heading_md, y, DARK_BROWN, SQUARE_W)
    y += h + 8
    h = center_text(draw, "the food?", heading_md, y, DARK_BROWN, SQUARE_W)
    y += h + 30

    draw_divider(draw, y, SQUARE_W)
    y += 35

    body_lines = [
        "Five people texting \u201Cwhat should I bring?\u201D",
        "Three casseroles showing up on Monday.",
        "Nothing on Thursday.",
        "",
        "Shiva meals shouldn\u2019t be this hard",
        "to coordinate.",
    ]
    line_spacing = 34
    for line in body_lines:
        if line == "":
            y += line_spacing
            continue
        center_text(draw, line, body_sm, y, MUTED_BROWN, SQUARE_W)
        y += line_spacing

    y += 25

    draw_divider(draw, y, SQUARE_W)
    y += 35

    # CTA
    center_text(draw, "neshama.ca/shiva-organize", cta_font, y, TERRACOTTA, SQUARE_W)

    # Footer
    center_text(draw, "neshama.ca", footer_font, SQUARE_H - 55, SAGE, SQUARE_W)

    path = os.path.join(BASE_OUTPUT, "post-8-meal-coordination.png")
    save_image(img, path)


# ══════════════════════════════════════════════════════════════════
#  POST 3: One Feed — single 1080x1080
# ══════════════════════════════════════════════════════════════════
def generate_post_9():
    img, draw = new_square()

    # Candle
    draw_candle(draw, SQUARE_W // 2, 60)

    # Big heading
    y = 165
    h = center_text(draw, "One feed", heading_lg, y, DARK_BROWN, SQUARE_W)
    y += h + 8
    h = center_text(draw, "instead of five.", heading_lg, y, DARK_BROWN, SQUARE_W)
    y += h + 35

    draw_divider(draw, y, SQUARE_W)
    y += 35

    # Sources in sage
    h = center_text(
        draw,
        "Steeles \u00b7 Benjamin\u2019s \u00b7 Paperman\u2019s \u00b7 Misaskim",
        subtitle_font,
        y,
        SAGE,
        SQUARE_W,
    )
    y += h + 40

    draw_divider(draw, y, SQUARE_W)
    y += 40

    # Body
    h = center_text(draw, "242 obituaries. Two cities.", body_font, y, MUTED_BROWN, SQUARE_W)
    y += h + 12
    h = center_text(draw, "One place.", heading_sm, y, TERRACOTTA, SQUARE_W)

    # Footer
    center_text(draw, "neshama.ca", footer_font, SQUARE_H - 55, SAGE, SQUARE_W)

    path = os.path.join(BASE_OUTPUT, "post-9-one-feed.png")
    save_image(img, path)


# ══════════════════════════════════════════════════════════════════
#  POST 4: March 24 Teaser — single 1080x1080
# ══════════════════════════════════════════════════════════════════
def generate_post_10():
    img, draw = new_square()

    # Candle
    draw_candle(draw, SQUARE_W // 2, 100)

    # Large date
    y = 220
    h = center_text(draw, "March 24.", heading_lg, y, DARK_BROWN, SQUARE_W)
    y += h + 40

    draw_divider(draw, y, SQUARE_W)
    y += 45

    # Body
    lines = [
        "Something the community",
        "has been missing.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN, SQUARE_W)
        y += h + 12

    # Footer
    center_text(draw, "neshama.ca", footer_font, SQUARE_H - 55, SAGE, SQUARE_W)

    path = os.path.join(BASE_OUTPUT, "post-10-march-24-teaser.png")
    save_image(img, path)


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Create output directories
    os.makedirs(CAROUSEL_DIR, exist_ok=True)
    os.makedirs(BASE_OUTPUT, exist_ok=True)

    print("=== Passover Grief Carousel (7 slides) ===")
    carousel_slide_1()
    carousel_slide_2()
    carousel_slide_3()
    carousel_slide_4()
    carousel_slide_5()
    carousel_slide_6()
    carousel_slide_7()

    print("\n=== Post 8: Meal Coordination ===")
    generate_post_8()

    print("\n=== Post 9: One Feed ===")
    generate_post_9()

    print("\n=== Post 10: March 24 Teaser ===")
    generate_post_10()

    print("\nDone — all 10 images generated.")
