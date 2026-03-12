#!/usr/bin/env python3
"""
Generate a 7-slide Instagram carousel about Jewish mourning stages.
Output: 1080x1350 portrait images using Neshama design system.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ── Paths ──────────────────────────────────────────────────────────
FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")
HEBREW_FONT = "/Library/Fonts/Arial Unicode.ttf"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts/carousel-mourning"

# ── Dimensions ─────────────────────────────────────────────────────
W, H = 1080, 1350
PAD_X = 80
STRIP_H = 8

# ── Colours ────────────────────────────────────────────────────────
CREAM_BG = (245, 241, 235)
DARK_BROWN = (62, 39, 35)
TERRACOTTA = (210, 105, 30)
MUTED_BROWN = (92, 83, 74)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (200, 180, 140)
DARK_STRIP = (50, 35, 30)

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


def draw_centered_text(draw, text, y, font, fill, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, y), text, fill=fill, font=font)
    return bbox[3] - bbox[1]


def draw_centered_lines(draw, lines, start_y, font, fill, width, line_gap=0):
    """Draw multiple centered lines, return total height used."""
    y = start_y
    for line in lines:
        h = draw_centered_text(draw, line, y, font, fill, width)
        y += h + line_gap
    return y - start_y


def new_slide():
    """Return a fresh slide Image + Draw with background and dark strips."""
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    # Top strip
    draw.rectangle([0, 0, W, STRIP_H], fill=DARK_STRIP)
    # Bottom strip
    draw.rectangle([0, H - STRIP_H, W, H], fill=DARK_STRIP)
    return img, draw


def draw_footer(draw, text="neshama.ca"):
    """Draw small footer near bottom."""
    font = make_font(CRIMSON, 20, weight=400)
    draw_centered_text(draw, text, H - 55, font, SAGE, W)


def save_slide(img, num):
    path = os.path.join(OUTPUT_DIR, f"slide_{num}.png")
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")


# ── Fonts (pre-load) ──────────────────────────────────────────────
heading_lg = make_font(CORMORANT, 56, weight=700)
heading_md = make_font(CORMORANT, 48, weight=700)
heading_sm = make_font(CORMORANT, 40, weight=700)
body_font = make_font(CRIMSON, 26, weight=400)
body_sm = make_font(CRIMSON, 22, weight=400)
footer_font = make_font(CRIMSON, 20, weight=400)
stage_font = make_font(CORMORANT, 56, weight=700)
subtitle_font = make_font(CRIMSON, 24, weight=400)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 1 — Hook
# ══════════════════════════════════════════════════════════════════
def slide_1():
    img, draw = new_slide()
    y = 120

    # Candle
    draw_candle(draw, W // 2, y)
    y += 110

    # Large heading
    for line in ["Most people show up", "during shiva."]:
        h = draw_centered_text(draw, line, y, heading_lg, DARK_BROWN, W)
        y += h + 8
    y += 40

    # Terracotta question
    h = draw_centered_text(draw, "What happens after?", y, heading_md, TERRACOTTA, W)
    y += h

    # Footer
    draw_footer(draw)
    save_slide(img, 1)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 2 — Structure overview
# ══════════════════════════════════════════════════════════════════
def slide_2():
    img, draw = new_slide()
    y = 200

    # Heading
    h = draw_centered_text(draw, "Shiva lasts 7 days.", y, heading_lg, DARK_BROWN, W)
    y += h + 40

    # Sub-heading
    for line in ["But Jewish mourning", "doesn't end there."]:
        h = draw_centered_text(draw, line, y, heading_md, DARK_BROWN, W)
        y += h + 8
    y += 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    body_lines = [
        "Judaism provides a structure for grief \u2014",
        "stages that give mourners permission",
        "to heal at their own pace.",
    ]
    for line in body_lines:
        h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
        y += h + 10

    draw_footer(draw)
    save_slide(img, 2)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 3 — Shloshim
# ══════════════════════════════════════════════════════════════════
def slide_3():
    img, draw = new_slide()
    y = 220

    # Stage name
    h = draw_centered_text(draw, "Shloshim", y, stage_font, TERRACOTTA, W)
    y += h + 16

    # Subtitle
    h = draw_centered_text(draw, "the first 30 days", y, subtitle_font, SAGE, W)
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    body_lines = [
        "Mourners begin re-entering daily life,",
        "but still avoid celebrations, live music,",
        "and joyful gatherings.",
    ]
    for line in body_lines:
        h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
        y += h + 10

    draw_footer(draw)
    save_slide(img, 3)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 4 — The First Year
# ══════════════════════════════════════════════════════════════════
def slide_4():
    img, draw = new_slide()
    y = 220

    # Stage name
    h = draw_centered_text(draw, "The First Year", y, stage_font, TERRACOTTA, W)
    y += h + 16

    # Subtitle
    h = draw_centered_text(draw, "for parents", y, subtitle_font, SAGE, W)
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    body_lines = [
        "Children mourning a parent observe",
        "restrictions for 12 months.",
        "Kaddish is recited daily.",
    ]
    for line in body_lines:
        h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
        y += h + 10

    draw_footer(draw)
    save_slide(img, 4)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 5 — Yahrzeit
# ══════════════════════════════════════════════════════════════════
def slide_5():
    img, draw = new_slide()
    y = 220

    # Stage name
    h = draw_centered_text(draw, "Yahrzeit", y, stage_font, TERRACOTTA, W)
    y += h + 16

    # Subtitle
    h = draw_centered_text(draw, "the anniversary", y, subtitle_font, SAGE, W)
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    body_lines = [
        "Each year, a candle is lit for 24 hours.",
        "The soul is remembered by name in shul.",
    ]
    for line in body_lines:
        h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
        y += h + 10
    y += 30

    # CTA in terracotta
    h = draw_centered_text(
        draw, "Set a reminder at neshama.ca/yahrzeit", y, body_sm, TERRACOTTA, W
    )

    draw_footer(draw)
    save_slide(img, 5)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 6 — Unveiling
# ══════════════════════════════════════════════════════════════════
def slide_6():
    img, draw = new_slide()
    y = 220

    # Stage name
    h = draw_centered_text(draw, "Unveiling", y, stage_font, TERRACOTTA, W)
    y += h + 16

    # Subtitle
    h = draw_centered_text(draw, "the headstone ceremony", y, subtitle_font, SAGE, W)
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    body_lines = [
        "Typically held within the first year.",
        "A private gathering at the grave to",
        "formally mark the monument.",
    ]
    for line in body_lines:
        h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
        y += h + 10

    draw_footer(draw)
    save_slide(img, 6)


# ══════════════════════════════════════════════════════════════════
#  SLIDE 7 — CTA
# ══════════════════════════════════════════════════════════════════
def slide_7():
    img, draw = new_slide()
    y = 120

    # Candle
    draw_candle(draw, W // 2, y)
    y += 110

    # Heading
    for line in ["Grief doesn\u2019t follow", "a schedule."]:
        h = draw_centered_text(draw, line, y, heading_lg, DARK_BROWN, W)
        y += h + 8
    y += 40

    # Terracotta line
    h = draw_centered_text(
        draw, "But tradition gives it a shape.", y, heading_md, TERRACOTTA, W
    )
    y += h + 40

    # Divider
    draw_divider(draw, y, W)
    y += 40

    # Body
    h = draw_centered_text(
        draw, "Save this for someone navigating loss.", y, body_font, MUTED_BROWN, W
    )

    # Footer
    draw_footer(draw)
    save_slide(img, 7)


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating carousel in {OUTPUT_DIR}\n")

    slide_1()
    slide_2()
    slide_3()
    slide_4()
    slide_5()
    slide_6()
    slide_7()

    print(f"\nDone — 7 slides saved to {OUTPUT_DIR}")
