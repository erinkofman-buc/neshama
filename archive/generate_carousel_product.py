#!/usr/bin/env python3
"""
Generate a 5-slide Instagram carousel for Neshama's product.
Output: 1080x1350px portrait PNG slides.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# ── Paths ──────────────────────────────────────────────────────────────
FONT_HEADING = "/Users/erinkofman/Desktop/Neshama/fonts/CormorantGaramond.ttf"
FONT_BODY = "/Users/erinkofman/Desktop/Neshama/fonts/CrimsonPro.ttf"
FONT_HEBREW = "/Library/Fonts/Arial Unicode.ttf"
OUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts/carousel-product"

# ── Dimensions ─────────────────────────────────────────────────────────
W, H = 1080, 1350
PAD = 80
CONTENT_TOP = 120

# ── Colors ─────────────────────────────────────────────────────────────
CREAM_BG = (245, 241, 235)
DARK_BROWN = (62, 39, 35)
TERRACOTTA = (210, 105, 30)
MUTED_BROWN = (92, 83, 74)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (200, 180, 140)
DARK_STRIP = (50, 35, 30)

# ── Helper Functions ───────────────────────────────────────────────────

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


def draw_centered_text(draw, text, y, font, fill, width):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, y), text, fill=fill, font=font)
    return bbox[3] - bbox[1]


def new_slide():
    """Create a blank slide with cream background and dark strips."""
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    # Top strip
    draw.rectangle([0, 0, W, 8], fill=DARK_STRIP)
    # Bottom strip
    draw.rectangle([0, H - 8, W, H], fill=DARK_STRIP)
    return img, draw


def draw_footer(draw, text="neshama.ca", color=SAGE):
    """Draw footer text near the bottom."""
    font = make_font(FONT_BODY, 22, weight=400)
    draw_centered_text(draw, text, H - 60, font, color, W)


def save_slide(img, num):
    path = os.path.join(OUT_DIR, f"slide_{num}.png")
    img.save(path, "PNG")
    size_kb = os.path.getsize(path) / 1024
    print(f"  Saved {path}  ({size_kb:.0f} KB)")
    return path


# ── Fonts ──────────────────────────────────────────────────────────────
heading_lg = make_font(FONT_HEADING, 56, weight=700)
heading_md = make_font(FONT_HEADING, 48, weight=700)
heading_sm = make_font(FONT_HEADING, 36, weight=700)
body_font = make_font(FONT_BODY, 26, weight=400)
body_sm = make_font(FONT_BODY, 24, weight=400)

# ======================================================================
# SLIDE 1 — Hook
# ======================================================================
print("Generating Slide 1 (Hook)...")
img, draw = new_slide()

# Candle at top center
draw_candle(draw, W // 2, CONTENT_TOP)

y = CONTENT_TOP + 100

# "How many websites"
h = draw_centered_text(draw, "How many websites", y, heading_lg, DARK_BROWN, W)
y += h + 10
h = draw_centered_text(draw, "do you check", y, heading_lg, DARK_BROWN, W)
y += h + 50

# Second part
h = draw_centered_text(draw, "when someone in the", y, heading_md, DARK_BROWN, W)
y += h + 10
h = draw_centered_text(draw, "community passes?", y, heading_md, DARK_BROWN, W)

draw_footer(draw)
save_slide(img, 1)

# ======================================================================
# SLIDE 2 — Problem
# ======================================================================
print("Generating Slide 2 (Problem)...")
img, draw = new_slide()

y = CONTENT_TOP + 60

sources = [
    "Benjamin\u2019s Park.",
    "Steeles Memorial.",
    "Paperman\u2019s.",
    "Community WhatsApp groups.",
    "Word of mouth at shul.",
]

source_font = make_font(FONT_HEADING, 36, weight=700)

for line in sources:
    h = draw_centered_text(draw, line, y, source_font, DARK_BROWN, W)
    y += h + 30

y += 20
draw_divider(draw, y, W)
y += 40

# Muted smaller text
h = draw_centered_text(
    draw, "It\u2019s a lot of tabs for a heavy moment.", y, body_font, MUTED_BROWN, W
)

draw_footer(draw)
save_slide(img, 2)

# ======================================================================
# SLIDE 3 — Solution
# ======================================================================
print("Generating Slide 3 (Solution)...")
img, draw = new_slide()

# Candle
draw_candle(draw, W // 2, CONTENT_TOP)

y = CONTENT_TOP + 100

# Terracotta heading
h = draw_centered_text(draw, "Neshama brings", y, heading_lg, TERRACOTTA, W)
y += h + 10
h = draw_centered_text(draw, "it together.", y, heading_lg, TERRACOTTA, W)
y += h + 40

draw_divider(draw, y, W)
y += 50

# Body text
body_lines = [
    "One feed. Every listing from",
    "Toronto and Montreal\u2019s Jewish",
    "funeral homes. Updated daily.",
]
for line in body_lines:
    h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
    y += h + 12

draw_footer(draw)
save_slide(img, 3)

# ======================================================================
# SLIDE 4 — Trust
# ======================================================================
print("Generating Slide 4 (Trust)...")
img, draw = new_slide()

y = CONTENT_TOP + 120

# Large heading
h = draw_centered_text(draw, "No account needed.", y, heading_lg, DARK_BROWN, W)
y += h + 20
h = draw_centered_text(draw, "No ads. No noise.", y, heading_lg, DARK_BROWN, W)
y += h + 50

draw_divider(draw, y, W)
y += 50

# Body
body_lines = [
    "Just a warm, respectful space",
    "to stay informed and connected.",
]
for line in body_lines:
    h = draw_centered_text(draw, line, y, body_font, MUTED_BROWN, W)
    y += h + 12

draw_footer(draw)
save_slide(img, 4)

# ======================================================================
# SLIDE 5 — CTA
# ======================================================================
print("Generating Slide 5 (CTA)...")
img, draw = new_slide()

# Candle
draw_candle(draw, W // 2, CONTENT_TOP)

y = CONTENT_TOP + 100

# Large heading
h = draw_centered_text(draw, "Visit neshama.ca", y, heading_lg, DARK_BROWN, W)
y += h + 40

draw_divider(draw, y, W)
y += 50

# Terracotta text
h = draw_centered_text(
    draw, "Share with someone who\u2019d", y, body_font, TERRACOTTA, W
)
y += h + 12
h = draw_centered_text(
    draw, "find this meaningful.", y, body_font, TERRACOTTA, W
)

draw_footer(draw)
save_slide(img, 5)

# ── Summary ────────────────────────────────────────────────────────────
print("\nAll 5 slides generated successfully!")
print(f"Output directory: {OUT_DIR}")
