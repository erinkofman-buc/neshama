#!/usr/bin/env python3
"""
v3 — editorial design using the real Neshama logo as the hero.

Design DNA from Cake/Lantern (per HQ/01-Projects/Neshama/Research/bereavement-site-design.md):
  - One hero element + one headline + one subhead + one CTA
  - Restraint over density
  - Generous whitespace (40-50% less dense than typical web app)
  - Photography/wordmark doing the lifting, not text blocks
  - Trust signals: free, no ads — subtle line at bottom

Replaces v1 (4-step flyer) and v2 (3-step + UI peek + button — still too dense).

Output: meal-coordination-v3.png in instagram-posts/
"""
from PIL import Image, ImageDraw, ImageFont
import os

FONT_DIR = "/Users/erinkofman/Desktop/Neshama/fonts"
OUTPUT_DIR = "/Users/erinkofman/Desktop/Neshama/instagram-posts"
LOGO_PATH = "/Users/erinkofman/Desktop/Neshama/marketing-kit/general/NESHAMA LOGO 1.png"
CORMORANT = os.path.join(FONT_DIR, "CormorantGaramond.ttf")
CRIMSON = os.path.join(FONT_DIR, "CrimsonPro.ttf")

# Brand palette (per neshama_marketing_skill.md + bereavement-site-design.md)
CREAM_BG = (252, 249, 243)
DARK_BROWN = (72, 52, 43)
TERRACOTTA = (195, 110, 60)
MUTED_BROWN = (110, 95, 82)
SAGE = (158, 148, 136)
DIVIDER_GOLD = (205, 185, 150)
SOFT_BORDER = (235, 225, 210)

W, H = 1080, 1080


def make_font(path, size):
    return ImageFont.truetype(path, size)


def center_text(draw, text, font, y, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (W - tw) // 2
    draw.text((x, y), text, fill=color, font=font)
    return th


def draw_soft_borders(draw):
    border_h = 6
    draw.rectangle([0, 0, W, border_h], fill=SOFT_BORDER)
    draw.rectangle([0, H - border_h, W, H], fill=SOFT_BORDER)
    draw.line([(60, border_h + 12), (W - 60, border_h + 12)], fill=DIVIDER_GOLD, width=1)
    draw.line([(60, H - border_h - 12), (W - 60, H - border_h - 12)], fill=DIVIDER_GOLD, width=1)


def draw_centered_divider(draw, y, length=70):
    x1 = (W - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=DIVIDER_GOLD, width=2)


def paste_logo(canvas, logo_target_w):
    """Paste the Neshama logo at target width, centered horizontally, return (top_y, height_used)."""
    logo = Image.open(LOGO_PATH).convert("RGBA")
    aspect = logo.height / logo.width
    target_h = int(logo_target_w * aspect)
    logo_resized = logo.resize((logo_target_w, target_h), Image.Resampling.LANCZOS)

    # Place the logo
    x = (W - logo_target_w) // 2
    return logo_resized, x, target_h


def generate():
    img = Image.new("RGB", (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)
    draw_soft_borders(draw)

    # Type scales (editorial — bigger, more confident)
    headline_font = make_font(CORMORANT, 78)
    subhead_font = make_font(CRIMSON, 32)
    url_font = make_font(CORMORANT, 38)
    trust_font = make_font(CRIMSON, 22)

    # === Logo (hero) ===
    logo_target_w = 420  # tighter so headline + subhead + URL all fit comfortably
    logo_img, logo_x, logo_h = paste_logo(img, logo_target_w)
    logo_top_y = 80

    # The logo PNG has a soft cream gradient background; paste with alpha mask
    img.paste(logo_img, (logo_x, logo_top_y), logo_img)

    # Re-create draw object after paste
    draw = ImageDraw.Draw(img)

    # === Below the logo ===
    y = logo_top_y + logo_h + 20

    # Divider
    draw_centered_divider(draw, y)
    y += 42

    # Headline (editorial — two lines, large)
    h = center_text(draw, "Shiva meals,", headline_font, y, DARK_BROWN)
    y += h + 4
    h = center_text(draw, "without the chaos.", headline_font, y, DARK_BROWN)
    y += h + 28

    # Subhead — single line, restrained
    h = center_text(
        draw,
        "Free coordination for Toronto and Montreal Jewish families.",
        subhead_font,
        y,
        MUTED_BROWN,
    )
    y += h + 50

    # URL (quiet anchor — editorial, not a button)
    h = center_text(draw, "neshama.ca", url_font, y, TERRACOTTA)
    # Subtle underline for the URL
    url_text_w = draw.textbbox((0, 0), "neshama.ca", font=url_font)
    url_w = url_text_w[2] - url_text_w[0]
    underline_x1 = (W - url_w) // 2
    draw.line(
        [(underline_x1, y + h + 2), (underline_x1 + url_w, y + h + 2)],
        fill=TERRACOTTA,
        width=1,
    )
    y += h + 32

    # Trust line (small, sage — sits just below URL, comfortably above bottom border)
    trust = "Free.   No ads.   No subscriptions."
    center_text(draw, trust, trust_font, y, SAGE)

    out_path = os.path.join(OUTPUT_DIR, "meal-coordination-v3.png")
    img.save(out_path, "PNG")
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Saved {out_path}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    generate()
