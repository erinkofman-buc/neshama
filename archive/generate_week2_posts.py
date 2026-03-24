#!/usr/bin/env python3
"""
Generate Week 2 Instagram graphics for Neshama (Mar 31 - Apr 6, 2026).
4 posts: Mon carousel (5 slides), Wed single, Fri single, Sun single.
Uses v3 style: warm greeting-card feel, cream bg, centered content.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
HEBREW = os.path.join(FONT_DIR, "NotoSerifHebrew-Regular.ttf")

# === Colors (v3 palette) ===
CREAM_BG = (252, 249, 243)
DARK_BROWN = (72, 52, 43)
TERRACOTTA = (195, 110, 60)
MUTED_BROWN = (110, 95, 82)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)
SOFT_BORDER = (235, 225, 210)

W, H = 1080, 1080


# === Helper functions (from v3) ===
def make_font(path, size):
    return ImageFont.truetype(path, size)


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


def draw_bullet_item(draw, text, font, y, color, bullet_x=140, text_x=170):
    """Draw a bullet point with text, left-aligned with indent."""
    # Draw bullet dot
    dot_r = 5
    dot_y = y + measure_text_height(draw, text, font) // 2
    draw.ellipse([bullet_x - dot_r, dot_y - dot_r, bullet_x + dot_r, dot_y + dot_r], fill=color)
    # Draw text
    draw.text((text_x, y), text, fill=color, font=font)
    return measure_text_height(draw, text, font)


def draw_number_item(draw, number, text, num_font, text_font, y, num_color, text_color, num_x=120, text_x=160):
    """Draw a numbered item."""
    draw.text((num_x, y), str(number), fill=num_color, font=num_font)
    draw.text((text_x, y), text, fill=text_color, font=text_font)
    return measure_text_height(draw, text, text_font)


# ============================================================
# POST 1: Mar 31 (Mon) — Shiva Essentials Carousel (5 slides)
# ============================================================
def generate_shiva_carousel():
    carousel_dir = os.path.join(OUTPUT_DIR, "mar31-shiva-essentials-carousel")
    os.makedirs(carousel_dir, exist_ok=True)

    # --- SLIDE 1: Hook ---
    img, draw = new_square()
    heading_font = make_font(CORMORANT, 78)
    sub_font = make_font(CORMORANT, 48)
    body_font = make_font(CRIMSON, 36)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 95
    total = candle_h + 30 + 200 + 40 + 45 + 80 + 30
    y = calc_content_start(total)

    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    h = center_text(draw, "What to bring", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "to a shiva house.", heading_font, y, DARK_BROWN)
    y += h + 25

    h = center_text(draw, "A Practical Guide", sub_font, y, TERRACOTTA)
    y += h + 40

    draw_divider(draw, y)
    y += 45

    h = center_text(draw, "Swipe for 4 things that", body_font, y, MUTED_BROWN)
    y += h + 14
    h = center_text(draw, "actually help a grieving family.", body_font, y, MUTED_BROWN)
    y += h + 40

    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)
    center_text(draw, "1 / 5", make_font(CRIMSON, 24), H - 85, SAGE)

    save_image(img, os.path.join(carousel_dir, "slide-1.png"))

    # --- SLIDE 2: Food ---
    img, draw = new_square()
    heading_font = make_font(CORMORANT, 66)
    body_font = make_font(CRIMSON, 32)
    tip_font = make_font(CRIMSON, 30)
    footer_font = make_font(CRIMSON, 28)

    y = int(H * 0.15)

    draw_candle(draw, W // 2, y, scale=1.0)
    y += 80 + 20

    h = center_text(draw, "1. Ready-to-eat food", heading_font, y, DARK_BROWN)
    y += h + 30

    draw_divider(draw, y)
    y += 35

    lines = [
        "Mourners often can\u2019t cook.",
        "Bring food that\u2019s ready to serve \u2014",
        "no reheating, no prep needed.",
        "",
        "Think: cut fruit, baked goods,",
        "deli platters, individually",
        "wrapped sandwiches.",
    ]
    for line in lines:
        if line == "":
            y += 18
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += 42

    y += 25
    draw_divider(draw, y)
    y += 35

    h = center_text(draw, "Tip: Ask the family about", tip_font, y, TERRACOTTA)
    y += h + 10
    h = center_text(draw, "dietary needs first.", tip_font, y, TERRACOTTA)

    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)
    center_text(draw, "2 / 5", make_font(CRIMSON, 24), H - 85, SAGE)

    save_image(img, os.path.join(carousel_dir, "slide-2.png"))

    # --- SLIDE 3: Paper goods & practical items ---
    img, draw = new_square()
    heading_font = make_font(CORMORANT, 66)
    body_font = make_font(CRIMSON, 32)
    footer_font = make_font(CRIMSON, 28)

    y = int(H * 0.15)

    draw_candle(draw, W // 2, y, scale=1.0)
    y += 80 + 20

    h = center_text(draw, "2. Paper goods &", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "practical supplies", heading_font, y, DARK_BROWN)
    y += h + 30

    draw_divider(draw, y)
    y += 35

    lines = [
        "Nobody thinks to bring these,",
        "but they always run out:",
        "",
        "Paper plates, cups, napkins,",
        "plastic cutlery, garbage bags,",
        "tissues, hand soap.",
        "",
        "These small things make",
        "the biggest difference.",
    ]
    for line in lines:
        if line == "":
            y += 18
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += 42

    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)
    center_text(draw, "3 / 5", make_font(CRIMSON, 24), H - 85, SAGE)

    save_image(img, os.path.join(carousel_dir, "slide-3.png"))

    # --- SLIDE 4: Your presence ---
    img, draw = new_square()
    heading_font = make_font(CORMORANT, 66)
    body_font = make_font(CRIMSON, 32)
    footer_font = make_font(CRIMSON, 28)

    y = int(H * 0.15)

    draw_candle(draw, W // 2, y, scale=1.0)
    y += 80 + 20

    h = center_text(draw, "3. Your presence", heading_font, y, DARK_BROWN)
    y += h + 30

    draw_divider(draw, y)
    y += 35

    lines = [
        "You don\u2019t need to bring anything",
        "at all. Just show up.",
        "",
        "Sit with the mourner.",
        "Let them lead the conversation.",
        "If they\u2019re silent, be silent too.",
        "",
        "In Jewish tradition, the visitor",
        "doesn\u2019t speak first. Follow",
        "the mourner\u2019s lead.",
    ]
    for line in lines:
        if line == "":
            y += 18
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += 42

    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)
    center_text(draw, "4 / 5", make_font(CRIMSON, 24), H - 85, SAGE)

    save_image(img, os.path.join(carousel_dir, "slide-4.png"))

    # --- SLIDE 5: CTA ---
    img, draw = new_square()
    heading_font = make_font(CORMORANT, 72)
    body_font = make_font(CRIMSON, 34)
    cta_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 95
    total = candle_h + 30 + 200 + 40 + 45 + 150
    y = calc_content_start(total)

    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    h = center_text(draw, "The best thing", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "you can bring?", heading_font, y, DARK_BROWN)
    y += h + 20

    h = center_text(draw, "Yourself.", heading_font, y, TERRACOTTA)
    y += h + 40

    draw_divider(draw, y)
    y += 45

    lines = [
        "Save this for when you need it.",
        "Share it with someone who might.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 16

    y += 30

    h = center_text(draw, "More at neshama.ca/shiva-guide", cta_font, y, TERRACOTTA)

    center_text(draw, "neshama.ca", footer_font, H - 55, SAGE)
    center_text(draw, "5 / 5", make_font(CRIMSON, 24), H - 85, SAGE)

    save_image(img, os.path.join(carousel_dir, "slide-5.png"))


# ============================================================
# POST 2: Apr 2 (Wed) — Holidays & Grief (Passover overlap)
# ============================================================
def generate_holidays_grief():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 68)
    sub_font = make_font(CORMORANT, 44)
    body_font = make_font(CRIMSON, 32)
    tagline_font = make_font(CORMORANT, 40)
    save_font = make_font(CRIMSON, 28)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 85
    total = candle_h + 22 + 180 + 14 + 50 + 28 + 35 + 380 + 20 + 35 + 50 + 20 + 30
    y = max(int(H * 0.10), (H - 60 - total) // 2)

    draw_candle(draw, W // 2, y, scale=1.15)
    y += candle_h + 22

    h = center_text(draw, "When holidays", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "and grief collide.", heading_font, y, DARK_BROWN)
    y += h + 14

    h = center_text(draw, "Pesach & Mourning", sub_font, y, TERRACOTTA)
    y += h + 28

    draw_divider(draw, y)
    y += 35

    lines = [
        "The seder table is set.",
        "But someone\u2019s chair is empty.",
        "",
        "Holidays can be the hardest days",
        "for those carrying grief. The joy",
        "around you can make the absence",
        "feel even louder.",
        "",
        "If this is you \u2014 you\u2019re not alone.",
        "Your community sees you.",
        "Your feelings are valid.",
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

    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 20

    h = center_text(draw, "Save this for someone who needs it.", save_font, y, SAGE)
    y += h + 18

    footer_y = min(y + 10, H - 45)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "apr02-holidays-grief.png"))


# ============================================================
# POST 3: Apr 4 (Fri) — Meal Coordination Feature Explainer
# ============================================================
def generate_meal_coordination():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 64)
    sub_font = make_font(CORMORANT, 42)
    num_font = make_font(CORMORANT, 52)
    body_font = make_font(CRIMSON, 30)
    cta_font = make_font(CRIMSON, 34)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 80
    total = candle_h + 20 + 90 + 12 + 40 + 25 + 35 + 400 + 25 + 35 + 45
    y = max(int(H * 0.08), (H - 60 - total) // 2)

    draw_candle(draw, W // 2, y, scale=1.1)
    y += candle_h + 20

    h = center_text(draw, "Shiva meals,", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "without the chaos.", heading_font, y, DARK_BROWN)
    y += h + 12

    h = center_text(draw, "How Neshama\u2019s Meal Coordination Works", sub_font, y, TERRACOTTA)
    y += h + 25

    draw_divider(draw, y)
    y += 35

    # Step-by-step with numbers
    steps = [
        ("1.", "An organizer creates a meal", "schedule for the mourning family."),
        ("2.", "They share the link with", "friends, neighbours, and community."),
        ("3.", "Volunteers sign up for specific", "meals \u2014 no duplicates, no gaps."),
        ("4.", "The family gets nourished.", "No group texts. No guessing."),
    ]

    step_spacing = 18
    for num, line1, line2 in steps:
        # Number
        draw.text((110, y), num, fill=TERRACOTTA, font=num_font)
        # Lines
        draw.text((165, y + 4), line1, fill=MUTED_BROWN, font=body_font)
        y += 36
        draw.text((165, y + 4), line2, fill=MUTED_BROWN, font=body_font)
        y += 36 + step_spacing

    y += 15

    draw_divider(draw, y)
    y += 35

    h = center_text(draw, "Because feeding a family in", body_font, y, MUTED_BROWN)
    y += h + 10
    h = center_text(draw, "mourning is chesed \u2014 it just", body_font, y, MUTED_BROWN)
    y += h + 10
    h = center_text(draw, "works better when it\u2019s organized.", body_font, y, MUTED_BROWN)
    y += h + 30

    h = center_text(draw, "Try it at neshama.ca", cta_font, y, TERRACOTTA)
    y += h + 20

    footer_y = min(y + 10, H - 45)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "apr04-meal-coordination.png"))


# ============================================================
# POST 4: Apr 6 (Sun) — Week One Lessons (Founder/BTS)
# ============================================================
def generate_week_one_lessons():
    img, draw = new_square()

    label_font = make_font(CRIMSON, 30)
    heading_font = make_font(CORMORANT, 74)
    body_font = make_font(CRIMSON, 32)
    tagline_font = make_font(CORMORANT, 42)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 85
    total = candle_h + 22 + 100 + 12 + 35 + 30 + 35 + 380 + 25 + 35 + 50
    y = max(int(H * 0.10), (H - 60 - total) // 2)

    draw_candle(draw, W // 2, y, scale=1.15)
    y += candle_h + 22

    h = center_text(draw, "Behind the Scenes", label_font, y, SAGE)
    y += h + 12

    h = center_text(draw, "What we learned", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "in week one.", heading_font, y, DARK_BROWN)
    y += h + 30

    draw_divider(draw, y)
    y += 35

    lines = [
        "We launched Neshama on March 24.",
        "Here\u2019s what the first week taught us:",
        "",
        "People check. Every morning,",
        "community members visit to see",
        "who they might need to show up for.",
        "",
        "Meal coordination matters.",
        "It\u2019s the feature people share most.",
        "",
        "This work is personal.",
        "Every message reminds us why",
        "we built this.",
    ]
    line_spacing = 38
    for line in lines:
        if line == "":
            y += 16
            continue
        center_text(draw, line, body_font, y, MUTED_BROWN)
        y += line_spacing

    y += 20

    draw_divider(draw, y)
    y += 35

    h = center_text(draw, "Comforting our community.", tagline_font, y, TERRACOTTA)
    y += h + 20

    footer_y = min(y + 10, H - 45)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    save_image(img, os.path.join(OUTPUT_DIR, "apr06-week-one-lessons.png"))


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=== Neshama Week 2 Graphics (Mar 31 - Apr 6) ===\n")

    print("Post 1: Mar 31 — Shiva Essentials Carousel (5 slides)")
    generate_shiva_carousel()

    print("\nPost 2: Apr 2 — Holidays & Grief (Passover)")
    generate_holidays_grief()

    print("\nPost 3: Apr 4 — Meal Coordination Feature")
    generate_meal_coordination()

    print("\nPost 4: Apr 6 — Week One Lessons")
    generate_week_one_lessons()

    print("\n=== Done — 4 posts (8 images) generated for Week 2 ===")
