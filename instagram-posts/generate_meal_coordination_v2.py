#!/usr/bin/env python3
"""
Generate v2 of the meal coordination graphic.

Three improvements over apr04-meal-coordination.png:
  1. 4 steps -> 3 steps (drop the "family gets nourished" line; that's a
     result, not a process step. Closing tagline conveys it.)
  2. Add a product UI peek -- small mock meal calendar with sample sign-ups.
  3. CTA reads as a button (terracotta pill) instead of plain link text.

Output: meal-coordination-v2.png in instagram-posts/
"""
from PIL import Image, ImageDraw, ImageFont
import os

FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")

CREAM_BG = (252, 249, 243)
DARK_BROWN = (72, 52, 43)
TERRACOTTA = (195, 110, 60)
MUTED_BROWN = (110, 95, 82)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)
SOFT_BORDER = (235, 225, 210)
CARD_BG = (255, 253, 248)
CARD_BORDER = (220, 205, 180)

W, H = 1080, 1080


def make_font(path, size):
    return ImageFont.truetype(path, size)


def draw_divider(draw, y, color=DIVIDER_GOLD, length=90):
    x1 = (W - length) // 2
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
        draw.ellipse([cx - r, flame_center_y - r, cx + r, flame_center_y + r], fill=glow)
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


def center_text(draw, text, font, y, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return th


def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def draw_meal_calendar_peek(draw, y, body_font, label_font, check_font):
    """Draw a small product UI peek: a meal calendar card with sample sign-ups."""
    card_w = 720
    card_h = 200
    card_x = (W - card_w) // 2
    card_y = y

    # Card background with subtle border
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=12,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=2,
    )

    # Card header label (top-left corner)
    label = "Meal calendar"
    draw.text((card_x + 24, card_y + 16), label, fill=SAGE, font=label_font)

    # Divider under header
    draw.line(
        [(card_x + 24, card_y + 48), (card_x + card_w - 24, card_y + 48)],
        fill=SOFT_BORDER,
        width=1,
    )

    # Sample meal rows: (slot, signup, taken)
    rows = [
        ("Tue dinner", "Sarah — lasagna", True),
        ("Wed lunch", "Open", False),
        ("Wed dinner", "Mark — deli platter", True),
        ("Thu dinner", "Rachel — soup", True),
    ]
    row_y = card_y + 62
    row_height = 32
    for slot, signup, taken in rows:
        # Slot label (left, dark brown)
        draw.text((card_x + 24, row_y), slot, fill=DARK_BROWN, font=body_font)
        # Signup text (right of slot, muted)
        signup_color = MUTED_BROWN if taken else TERRACOTTA
        draw.text((card_x + 220, row_y), signup, fill=signup_color, font=body_font)
        # Status: check on right if taken, plus-circle if open
        status_x = card_x + card_w - 50
        if taken:
            # Small filled terracotta circle as a "filled" marker
            r = 8
            draw.ellipse(
                [status_x - r, row_y + 6, status_x + r, row_y + 6 + 2 * r],
                fill=TERRACOTTA,
            )
            # White checkmark inside
            draw.line(
                [(status_x - 4, row_y + 14), (status_x - 1, row_y + 17)],
                fill=CREAM_BG,
                width=2,
            )
            draw.line(
                [(status_x - 1, row_y + 17), (status_x + 5, row_y + 11)],
                fill=CREAM_BG,
                width=2,
            )
        else:
            # Empty circle
            r = 8
            draw.ellipse(
                [status_x - r, row_y + 6, status_x + r, row_y + 6 + 2 * r],
                outline=TERRACOTTA,
                width=2,
            )
        row_y += row_height

    return card_h


def draw_cta_button(draw, y, font):
    """Draw a terracotta pill-shaped CTA button with arrow."""
    label = "Try it at neshama.ca"
    label_w = text_width(draw, label, font)
    btn_padding_x = 36
    btn_padding_y = 16
    btn_w = label_w + 2 * btn_padding_x
    btn_h = 56
    btn_x = (W - btn_w) // 2
    btn_y = y

    draw.rounded_rectangle(
        [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
        radius=btn_h // 2,
        fill=TERRACOTTA,
    )
    text_x = btn_x + btn_padding_x
    text_y = btn_y + (btn_h - font.size) // 2 - 4
    draw.text((text_x, text_y), label, fill=CREAM_BG, font=font)
    return btn_h


def new_square():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_soft_borders(draw)
    return img, draw


def generate():
    img, draw = new_square()

    heading_font = make_font(CORMORANT, 64)
    sub_font = make_font(CORMORANT, 38)
    num_font = make_font(CORMORANT, 50)
    body_font = make_font(CRIMSON, 28)
    closing_font = make_font(CRIMSON, 28)
    cta_font = make_font(CRIMSON, 30)
    label_font = make_font(CRIMSON, 18)
    footer_font = make_font(CRIMSON, 26)

    y = 95

    # Candle
    draw_candle(draw, W // 2, y, scale=1.0)
    y += 95

    # Title
    h = center_text(draw, "Shiva meals,", heading_font, y, DARK_BROWN)
    y += h + 8
    h = center_text(draw, "without the chaos.", heading_font, y, DARK_BROWN)
    y += h + 18

    # Subtitle (tightened)
    h = center_text(draw, "How Neshama works", sub_font, y, TERRACOTTA)
    y += h + 24

    draw_divider(draw, y)
    y += 30

    # 3 steps (dropped step 4)
    steps = [
        ("1.", "An organizer creates a meal schedule", "for the mourning family."),
        ("2.", "They share the link with friends,", "neighbours, and community."),
        ("3.", "Volunteers sign up for specific meals", "— no duplicates, no gaps."),
    ]
    for num, line1, line2 in steps:
        draw.text((150, y), num, fill=TERRACOTTA, font=num_font)
        draw.text((205, y + 4), line1, fill=MUTED_BROWN, font=body_font)
        y += 36
        draw.text((205, y + 4), line2, fill=MUTED_BROWN, font=body_font)
        y += 36 + 14

    y += 8

    # Product peek
    card_h = draw_meal_calendar_peek(draw, y, body_font, label_font, cta_font)
    y += card_h + 22

    # Closing tagline (compressed)
    h = center_text(draw, "Feeding a family in mourning is chesed.", closing_font, y, MUTED_BROWN)
    y += h + 8
    h = center_text(draw, "It just works better when it's organized.", closing_font, y, MUTED_BROWN)
    y += h + 22

    # CTA button
    btn_h = draw_cta_button(draw, y, cta_font)
    y += btn_h + 16

    # Footer
    footer_y = min(y + 4, H - 38)
    center_text(draw, "neshama.ca", footer_font, footer_y, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "meal-coordination-v2.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Saved {out_path}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    generate()
