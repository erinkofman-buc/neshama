#!/usr/bin/env python3
"""Generate 9 Instagram carousel slides for BehindTheCounterRx collagen post."""

from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

# === BRAND SPECS ===
W, H = 1080, 1080
BG = "#FAFAF7"
CHARCOAL = "#2D2D2D"
GREEN = "#2D7D46"
LIGHT_GREY = "#C8C8C8"
DOT_GREY = "#D0D0D0"
BODY_COLOR = "#3A3A3A"
DISCLAIMER_COLOR = "#888888"

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# === FONT LOADING ===
def load_font(bold=False, size=54):
    """Try Georgia, fall back to Times, then default."""
    candidates_bold = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
        "/System/Library/Fonts/Times New Roman Bold.ttf",
    ]
    candidates_regular = [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Georgia.ttf",
        "/System/Library/Fonts/Times New Roman.ttf",
    ]
    candidates = candidates_bold if bold else candidates_regular
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # Last resort
    try:
        return ImageFont.truetype("Georgia", size)
    except:
        return ImageFont.load_default()


FONT_HEADING_LG = load_font(bold=True, size=68)
FONT_HEADING = load_font(bold=True, size=58)
FONT_BODY = load_font(bold=False, size=32)
FONT_BODY_SM = load_font(bold=False, size=28)
FONT_WATERMARK = load_font(bold=False, size=22)
FONT_DISCLAIMER = load_font(bold=False, size=22)
FONT_SUBTEXT = load_font(bold=False, size=38)
FONT_ARROW = load_font(bold=True, size=36)

TOTAL_SLIDES = 9


def draw_dots(draw, current_slide):
    """Draw slide indicator dots at the bottom."""
    dot_r = 6
    dot_spacing = 22
    total_w = TOTAL_SLIDES * (dot_r * 2) + (TOTAL_SLIDES - 1) * (dot_spacing - dot_r * 2)
    start_x = (W - total_w) // 2
    y = H - 90
    for i in range(TOTAL_SLIDES):
        cx = start_x + i * dot_spacing
        color = GREEN if i == current_slide else DOT_GREY
        draw.ellipse([cx - dot_r, y - dot_r, cx + dot_r, y + dot_r], fill=color)


def draw_watermark(draw):
    """Draw BehindTheCounterRx watermark."""
    text = "BehindTheCounterRx"
    bbox = draw.textbbox((0, 0), text, font=FONT_WATERMARK)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 55), text, fill=LIGHT_GREY, font=FONT_WATERMARK)


def draw_green_line(draw, y, width=120):
    """Draw a short green accent line."""
    x = (W - width) // 2
    draw.rectangle([x, y, x + width, y + 4], fill=GREEN)


def wrap_and_draw(draw, text, font, x, y, max_width, color=BODY_COLOR, line_spacing=10, center=False):
    """Word-wrap text and draw it. Returns the y after the last line."""
    # Estimate chars per line
    avg_char_w = font.getlength("M")
    chars_per_line = int(max_width / avg_char_w * 1.6)

    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
        else:
            wrapped = textwrap.wrap(paragraph, width=chars_per_line)
            lines.extend(wrapped if wrapped else [""])

    cur_y = y
    for line in lines:
        if line == "":
            cur_y += font.size * 0.6
            continue
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        if center:
            lx = (W - lw) // 2
        else:
            lx = x
        draw.text((lx, cur_y), line, fill=color, font=font)
        cur_y += lh + line_spacing
    return cur_y


def new_slide():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    return img, draw


def center_text(draw, text, font, y, color=CHARCOAL):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=color, font=font)
    return y + (bbox[3] - bbox[1])


def save_slide(img, draw, num):
    draw_dots(draw, num)
    draw_watermark(draw)
    path = os.path.join(OUT_DIR, f"slide_{num + 1:02d}.png")
    img.save(path, "PNG")
    print(f"  Saved {path}")


# ============================
# SLIDE 1 — HOOK
# ============================
def slide_1():
    img, draw = new_slide()
    # Green accent line
    draw_green_line(draw, 340, 80)
    # Heading
    y = 380
    y = center_text(draw, "Your collagen", FONT_HEADING_LG, y) + 10
    y = center_text(draw, "supplement", FONT_HEADING_LG, y) + 30
    # Subtext
    lines = ["is probably not doing", "what you think it is"]
    for line in lines:
        y = center_text(draw, line, FONT_SUBTEXT, y, color=BODY_COLOR) + 8
    save_slide(img, draw, 0)


# ============================
# SLIDE 2
# ============================
def slide_2():
    img, draw = new_slide()
    y = 160
    y = center_text(draw, "What happens when", FONT_HEADING, y) + 5
    y = center_text(draw, "you swallow collagen", FONT_HEADING, y) + 20
    draw_green_line(draw, y, 80)
    y += 40
    body = (
        "Your stomach acid breaks it down\n"
        "into amino acids. Only ~10% of\n"
        "peptides survive digestion intact.\n"
        "\n"
        "Your body doesn't stamp them\n"
        "'deliver to face.'"
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=12)
    save_slide(img, draw, 1)


# ============================
# SLIDE 3
# ============================
def slide_3():
    img, draw = new_slide()
    y = 140
    y = center_text(draw, "The study that", FONT_HEADING, y) + 5
    y = center_text(draw, "changed everything", FONT_HEADING, y) + 20
    draw_green_line(draw, y, 80)
    y += 40
    body = (
        "2025 meta-analysis.\n"
        "23 trials. 1,474 people.\n"
        "\n"
        "Industry-funded studies =\n"
        "benefits found.\n"
        "\n"
        "Independent studies =\n"
        "no significant effect."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=12)
    save_slide(img, draw, 2)


# ============================
# SLIDE 4
# ============================
def slide_4():
    img, draw = new_slide()
    y = 200
    y = center_text(draw, "Skin hydration?", FONT_HEADING_LG, y) + 20
    draw_green_line(draw, y, 80)
    y += 45
    body = (
        "Some signal — but mostly from\n"
        "industry-funded research.\n"
        "\n"
        "Verdict: Possible but unproven."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=14)
    save_slide(img, draw, 3)


# ============================
# SLIDE 5
# ============================
def slide_5():
    img, draw = new_slide()
    y = 180
    y = center_text(draw, "Joint health?", FONT_HEADING_LG, y) + 20
    draw_green_line(draw, y, 80)
    y += 45
    body = (
        "Modest evidence for type II\n"
        "collagen in osteoarthritis.\n"
        "\n"
        "But your $45/month powder\n"
        "probably isn't type II."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=14)
    save_slide(img, draw, 4)


# ============================
# SLIDE 6
# ============================
def slide_6():
    img, draw = new_slide()
    y = 170
    y = center_text(draw, "Hair growth?", FONT_HEADING_LG, y) + 20
    draw_green_line(draw, y, 80)
    y += 45
    body = (
        "Zero evidence.\n"
        "\n"
        "NPR (2025): 'No medical evidence\n"
        "supports marketing claims for\n"
        "hair growth.'\n"
        "\n"
        "Zero. None."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=14)
    save_slide(img, draw, 5)


# ============================
# SLIDE 7
# ============================
def slide_7():
    img, draw = new_slide()
    y = 120
    y = center_text(draw, "What I'd spend that", FONT_HEADING, y) + 5
    y = center_text(draw, "money on instead", FONT_HEADING, y) + 20
    draw_green_line(draw, y, 80)
    y += 40

    items = [
        ("Vitamin C", "your body can't make collagen\nwithout it ($0.10/day)"),
        ("Glycine", "collagen building block +\nsleep support"),
        ("Hyaluronic acid", "if skin hydration is the goal"),
    ]

    for i, (title, desc) in enumerate(items):
        # Green bullet
        draw.ellipse([110, y + 6, 124, y + 20], fill=GREEN)
        # Title in bold
        font_title = load_font(bold=True, size=32)
        draw.text((140, y), title, fill=GREEN, font=font_title)
        bbox = draw.textbbox((0, 0), title, font=font_title)
        y += bbox[3] - bbox[1] + 8
        # Description
        for line in desc.split("\n"):
            draw.text((140, y), line, fill=BODY_COLOR, font=FONT_BODY)
            bbox2 = draw.textbbox((0, 0), line, font=FONT_BODY)
            y += bbox2[3] - bbox2[1] + 8
        y += 25

    save_slide(img, draw, 6)


# ============================
# SLIDE 8
# ============================
def slide_8():
    img, draw = new_slide()
    y = 130
    y = center_text(draw, "Do I take collagen", FONT_HEADING, y) + 5
    y = center_text(draw, "myself?", FONT_HEADING, y) + 20
    draw_green_line(draw, y, 80)
    y += 40
    body = (
        "Yes. I use Vital Proteins\n"
        "and Organika.\n"
        "\n"
        "Do I think it's doing as much\n"
        "as the marketing says? No.\n"
        "\n"
        "But the risk is zero and there's\n"
        "enough of a signal to try."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=12)
    save_slide(img, draw, 7)


# ============================
# SLIDE 9 — CTA
# ============================
def slide_9():
    img, draw = new_slide()
    y = 150
    y = center_text(draw, "The full breakdown", FONT_HEADING_LG, y) + 20
    draw_green_line(draw, y, 80)
    y += 40
    body = (
        "Evidence ratings for every claim.\n"
        "What to buy instead.\n"
        "What I actually take."
    )
    y = wrap_and_draw(draw, body, FONT_BODY, 100, y, W - 200, center=True, line_spacing=14)
    y += 30
    # Arrow CTA
    cta = "-> Link in bio"
    bbox = draw.textbbox((0, 0), cta, font=FONT_ARROW)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), cta, fill=GREEN, font=FONT_ARROW)
    y += 80
    # Disclaimer
    disc = "Not medical advice. Affiliate links may be used."
    bbox2 = draw.textbbox((0, 0), disc, font=FONT_DISCLAIMER)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) // 2, y), disc, fill=DISCLAIMER_COLOR, font=FONT_DISCLAIMER)
    save_slide(img, draw, 8)


# ============================
# GENERATE ALL
# ============================
if __name__ == "__main__":
    print("Generating BehindTheCounterRx collagen carousel...")
    slide_1()
    slide_2()
    slide_3()
    slide_4()
    slide_5()
    slide_6()
    slide_7()
    slide_8()
    slide_9()
    print("Done! 9 slides generated.")
