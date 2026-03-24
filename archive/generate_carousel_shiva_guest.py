#!/usr/bin/env python3
"""
Generate a 7-slide Instagram carousel: "5 Things Every Shiva Guest Should Know"
Output: 1080x1080 square images using Neshama design system (v3 warm style).
Scheduled for Wed Mar 26.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

# === Paths ===
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts/carousel-shiva-guest"
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


def save_slide(img, num):
    path = os.path.join(OUTPUT_DIR, f"slide-{num}.png")
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


def draw_wrapped_text(draw, text, font, y, color, max_width, line_spacing=0):
    """Draw text that wraps within max_width, centered on each line. Returns total height."""
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


# === Font sizes (larger for 50-80 year old readability) ===
# Headings: big and bold
# Body: 36-38px (larger than v3's 32-34)
# Numbers: large terracotta


# ============================================================
#  SLIDE 1 — Hook
# ============================================================
def slide_1():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 72)
    sub_font = make_font(CORMORANT, 56)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 95
    y = calc_content_start(candle_h + 30 + 180 + 40 + 70)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 35

    # Main heading
    h = center_text(draw, "5 Things", heading_font, y, DARK_BROWN)
    y += h + 10
    h = center_text(draw, "Every Shiva Guest", heading_font, y, DARK_BROWN)
    y += h + 10
    h = center_text(draw, "Should Know", heading_font, y, TERRACOTTA)
    y += h + 45

    draw_divider(draw, y)
    y += 40

    # Subtitle
    h = center_text(draw, "Swipe to learn how", sub_font, y, MUTED_BROWN)
    y += h + 8
    h = center_text(draw, "to show up well.", sub_font, y, MUTED_BROWN)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 50, SAGE)

    save_slide(img, 1)


# ============================================================
#  SLIDES 2-6 — Tips
# ============================================================

TIPS = [
    {
        "number": "1",
        "title": "You don\u2019t need to say\nthe perfect thing.",
        "body": "Just being there matters more than any words. Sit with them. Listen.",
    },
    {
        "number": "2",
        "title": "Bring food they\ncan actually eat.",
        "body": "Think simple, ready-to-serve meals. Ask about dietary needs first.",
    },
    {
        "number": "3",
        "title": "Keep your visit short.",
        "body": "15\u201320 minutes is enough. Follow the mourner\u2019s lead. If they want to talk, stay. If not, that\u2019s okay too.",
    },
    {
        "number": "4",
        "title": "Don\u2019t say \u2018let me know\nif you need anything.\u2019",
        "body": "Instead, just do something specific: bring dinner Tuesday, offer to drive the kids, drop off paper goods.",
    },
    {
        "number": "5",
        "title": "It\u2019s okay to mention their\nloved one by name.",
        "body": "Mourners want to hear their person\u2019s name. Share a memory. It matters.",
    },
]


def generate_tip_slide(slide_num, tip):
    img, draw = new_square()

    number_font = make_font(CORMORANT, 110)
    title_font = make_font(CORMORANT, 54)
    body_font = make_font(CRIMSON, 38)
    footer_font = make_font(CRIMSON, 28)

    # Calculate layout
    title_lines = tip["title"].split("\n")

    # Start positioning — vertically centered
    # Estimate total height
    num_h = 90
    title_h = len(title_lines) * 55
    body_h = 120  # approximate for wrapped body
    total = num_h + 30 + title_h + 35 + 10 + 40 + body_h
    y = calc_content_start(total)

    # Number in large terracotta
    h = center_text(draw, tip["number"], number_font, y, TERRACOTTA)
    y += h + 25

    # Divider under number
    draw_divider(draw, y, length=60)
    y += 35

    # Title lines — bold heading font
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

    save_slide(img, slide_num)


# ============================================================
#  SLIDE 7 — CTA
# ============================================================
def slide_7():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 64)
    body_font = make_font(CRIMSON, 36)
    cta_font = make_font(CRIMSON, 40)
    footer_font = make_font(CRIMSON, 28)

    candle_h = 95
    y = calc_content_start(candle_h + 30 + 80 + 40 + 200 + 40 + 50)

    # Candle
    draw_candle(draw, W // 2, y, scale=1.3)
    y += candle_h + 30

    # Heading
    h = center_text(draw, "Neshama helps", heading_font, y, DARK_BROWN)
    y += h + 10
    h = center_text(draw, "you show up.", heading_font, y, TERRACOTTA)
    y += h + 40

    draw_divider(draw, y)
    y += 40

    # Body lines
    lines = [
        "Find who needs support.",
        "Coordinate meals.",
        "Send something thoughtful.",
    ]
    for line in lines:
        h = center_text(draw, line, body_font, y, MUTED_BROWN)
        y += h + 18

    y += 30

    draw_divider(draw, y)
    y += 40

    # CTA
    h = center_text(draw, "neshama.ca", cta_font, y, TERRACOTTA)

    # Footer
    center_text(draw, "neshama.ca", footer_font, H - 50, SAGE)

    save_slide(img, 7)


# ============================================================
#  Main
# ============================================================
if __name__ == "__main__":
    print("=== Generating: 5 Things Every Shiva Guest Should Know ===\n")

    print("Slide 1: Hook")
    slide_1()

    for i, tip in enumerate(TIPS):
        slide_num = i + 2
        print(f"\nSlide {slide_num}: Tip {tip['number']}")
        generate_tip_slide(slide_num, tip)

    print("\nSlide 7: CTA")
    slide_7()

    print(f"\n=== Done — 7 slides saved to {OUTPUT_DIR} ===")
