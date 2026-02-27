import logging
#!/usr/bin/env python3
"""
Regenerate Neshama marketing graphics with "local food vendors" (no number).
Matches exact existing design: Cormorant Garamond, Crimson Pro, terracotta/cream/sage.
"""

from PIL import Image, ImageDraw, ImageFont
import os

FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
CG_FONT = os.path.join(FONTS_DIR, 'CormorantGaramond.ttf')
CP_FONT = os.path.join(FONTS_DIR, 'CrimsonPro.ttf')
HEBREW_FONT = '/Library/Fonts/Arial Unicode.ttf'  # System font with Hebrew support

# Brand colors
CREAM_BG = (245, 241, 235)       # #F5F1EB
DARK_BROWN = (62, 39, 35)        # #3E2723
TERRACOTTA = (210, 105, 30)      # #D2691E
MUTED_BROWN = (92, 83, 74)       # #5C534A
SAGE = (158, 148, 136)           # #9E9488
DIVIDER_GOLD = (200, 180, 140)   # muted gold for dividers
DARK_STRIP = (50, 35, 30)        # top/bottom dark strips


def make_font(path, size, weight=None):
    """Create a font with optional variable weight."""
    font = ImageFont.truetype(path, size)
    if weight is not None:
        font.set_variation_by_axes([weight])
    return font


def draw_divider(draw, y, width, color=DIVIDER_GOLD, length=60):
    """Draw a horizontal divider line centered."""
    x1 = (width - length) // 2
    draw.line([(x1, y), (x1 + length, y)], fill=color, width=2)


def draw_candle(draw, cx, top_y):
    """Draw the memorial candle icon (match existing)."""
    # Flame (orange teardrop)
    flame_color = (210, 130, 30)
    flame_center_y = top_y + 8
    for dy in range(-8, 9):
        radius = max(0, int(6 * (1 - abs(dy) / 9)))
        if dy < 0:
            radius = max(0, int(4 * (1 - abs(dy) / 8)))
        draw.ellipse([cx - radius, flame_center_y + dy, cx + radius, flame_center_y + dy + 1],
                     fill=flame_color)

    # Wick/stick (tan)
    stick_color = (180, 165, 140)
    draw.rectangle([cx - 2, top_y + 18, cx + 2, top_y + 70], fill=stick_color)


def generate_post2_three_features():
    """
    Post 2: Three things Neshama does — 1080x1080
    Changes "18 local food vendors" → "Local food vendors"
    """
    W, H = 1080, 1080
    img = Image.new('RGB', (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)

    # Title: "Three things Neshama does"
    title_font = make_font(CG_FONT, 48, weight=700)
    title = "Three things Neshama does"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 55), title, fill=DARK_BROWN, font=title_font)

    # Subtitle: "— all free —"
    sub_font = make_font(CP_FONT, 22, weight=400)
    sub = "— all free —"
    bbox = draw.textbbox((0, 0), sub, font=sub_font)
    sw = bbox[2] - bbox[0]
    draw.text(((W - sw) // 2, 115), sub, fill=SAGE, font=sub_font)

    # Section layout
    sections = [
        {
            'num': '1',
            'title': 'Obituary Feed',
            'lines': [
                "Listings from Steeles, Benjamin's,",
                "and Paperman's — all in one place.",
                "No more checking three websites."
            ]
        },
        {
            'num': '2',
            'title': 'Meal Coordination',
            'lines': [
                "Families set up a page.",
                "Volunteers sign up to bring food.",
                "Everyone sees what's covered."
            ]
        },
        {
            'num': '3',
            'title': 'Caterer Directory',
            'lines': [
                "Local food vendors who",
                "do shiva meals — browse,",
                "compare, and order."
            ]
        },
    ]

    num_font = make_font(CG_FONT, 60, weight=700)
    section_title_font = make_font(CG_FONT, 32, weight=700)
    body_font = make_font(CP_FONT, 22, weight=400)

    y_start = 170
    section_height = 230

    for i, sec in enumerate(sections):
        y = y_start + i * section_height

        # Number (terracotta, left side)
        draw.text((70, y + 20), sec['num'], fill=TERRACOTTA, font=num_font)

        # Section title (bold, dark brown)
        draw.text((155, y + 20), sec['title'], fill=DARK_BROWN, font=section_title_font)

        # Body lines
        line_y = y + 65
        for line in sec['lines']:
            draw.text((155, line_y), line, fill=MUTED_BROWN, font=body_font)
            line_y += 30

        # Divider between sections (not after last)
        if i < 2:
            div_y = y + section_height - 20
            draw.line([(70, div_y), (W - 70, div_y)], fill=DIVIDER_GOLD, width=1)

    # Footer: neshama.ca
    footer_font = make_font(CP_FONT, 22, weight=400)
    footer = "neshama.ca"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, H - 70), footer, fill=SAGE, font=footer_font)

    path = os.path.join(os.path.dirname(__file__), 'instagram-posts', 'post-2-three-features.png')
    img.save(path, 'PNG')
    logging.info(f\'  ✅ Saved {path}')
    return path


def generate_story_features():
    """
    Story: Features overview — 1080x1920 (9:16 stories format)
    Changes "18 local vendors" → "Local vendors"
    """
    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)

    # Top dark strip
    draw.rectangle([0, 0, W, 18], fill=DARK_STRIP)

    # Candle
    draw_candle(draw, W // 2, 130)

    # NESHAMA title
    title_font = make_font(CG_FONT, 72, weight=300)
    title = "NESHAMA"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 220), title, fill=DARK_BROWN, font=title_font)

    # Hebrew: נשמה (use system font with Hebrew support)
    hebrew_font = ImageFont.truetype(HEBREW_FONT, 24)
    hebrew = "נ ש מ ה"
    bbox = draw.textbbox((0, 0), hebrew, font=hebrew_font)
    hw = bbox[2] - bbox[0]
    draw.text(((W - hw) // 2, 310), hebrew, fill=MUTED_BROWN, font=hebrew_font)

    # Divider
    draw_divider(draw, 345, W)

    # Tagline
    tagline_font = make_font(CG_FONT, 38, weight=400)
    tagline = "Every Soul Remembered"
    bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 365), tagline, fill=TERRACOTTA, font=tagline_font)

    # Three features
    features = [
        ("Obituary Feed", ["Steeles, Benjamin's & Paperman's", "all in one place"]),
        ("Meal Coordination", ["Sign up to bring food on specific days", "no more duplicate kugels"]),
        ("Caterer Directory", ["Local vendors who do", "shiva meals"]),
    ]

    feat_title_font = make_font(CG_FONT, 30, weight=700)
    feat_body_font = make_font(CP_FONT, 22, weight=400)
    y = 460

    for title, lines in features:
        # Divider
        draw_divider(draw, y, W)
        y += 20

        # Feature title
        bbox = draw.textbbox((0, 0), title, font=feat_title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), title, fill=DARK_BROWN, font=feat_title_font)
        y += 45

        # Feature body
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=feat_body_font)
            lw = bbox[2] - bbox[0]
            draw.text(((W - lw) // 2, y), line, fill=SAGE, font=feat_body_font)
            y += 30
        y += 30

    # "Completely free. No sign-up. No ads."
    draw_divider(draw, y, W)
    y += 20
    free_font = make_font(CP_FONT, 22, weight=400)
    free_text = "Completely free. No sign-up. No ads."
    bbox = draw.textbbox((0, 0), free_text, font=free_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, y), free_text, fill=MUTED_BROWN, font=free_font)

    # CTA Button: "Visit neshama.ca"
    y += 60
    btn_w, btn_h = 300, 55
    btn_x = (W - btn_w) // 2
    btn_color = TERRACOTTA
    # Rounded rectangle
    draw.rounded_rectangle([btn_x, y, btn_x + btn_w, y + btn_h], radius=28, fill=btn_color)
    btn_font = make_font(CP_FONT, 22, weight=600)
    btn_text = "Visit neshama.ca"
    bbox = draw.textbbox((0, 0), btn_text, font=btn_font)
    btw = bbox[2] - bbox[0]
    bth = bbox[3] - bbox[1]
    draw.text((btn_x + (btn_w - btw) // 2, y + (btn_h - bth) // 2 - 2), btn_text, fill='white', font=btn_font)

    # Bottom footer
    footer_font = make_font(CP_FONT, 18, weight=400)
    footer = "A free resource for Toronto & Montreal's Jewish community"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, H - 100), footer, fill=SAGE, font=footer_font)

    # Bottom dark strip
    draw.rectangle([0, H - 5, W, H], fill=DARK_STRIP)

    path = os.path.join(os.path.dirname(__file__), 'marketing-kit', 'instagram-stories', 'story-features.png')
    img.save(path, 'PNG')
    logging.info(f\'  ✅ Saved {path}')
    return path


def generate_whatsapp_vertical():
    """
    WhatsApp vertical card — 1080x1920 (same as story format)
    Changes "18 local vendors" → "Local vendors"
    """
    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), CREAM_BG)
    draw = ImageDraw.Draw(img)

    # Top dark strip
    draw.rectangle([0, 0, W, 18], fill=DARK_STRIP)

    # Candle
    draw_candle(draw, W // 2, 130)

    # NESHAMA title
    title_font = make_font(CG_FONT, 72, weight=300)
    title = "NESHAMA"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 220), title, fill=DARK_BROWN, font=title_font)

    # Hebrew: נשמה (use system font with Hebrew support)
    hebrew_font = ImageFont.truetype(HEBREW_FONT, 24)
    hebrew = "נ ש מ ה"
    bbox = draw.textbbox((0, 0), hebrew, font=hebrew_font)
    hw = bbox[2] - bbox[0]
    draw.text(((W - hw) // 2, 310), hebrew, fill=MUTED_BROWN, font=hebrew_font)

    # Divider
    draw_divider(draw, 345, W)

    # Tagline
    tagline_font = make_font(CG_FONT, 38, weight=400)
    tagline = "Every Soul Remembered"
    bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 365), tagline, fill=TERRACOTTA, font=tagline_font)

    # Three features — SAME as story-features but without "18"
    features = [
        ("Obituary Feed", ["Steeles, Benjamin's & Paperman's", "all in one place"]),
        ("Meal Coordination", ["Sign up to bring food on specific days", "no more duplicate kugels"]),
        ("Caterer Directory", ["Local vendors who do", "shiva meals"]),
    ]

    feat_title_font = make_font(CG_FONT, 30, weight=700)
    feat_body_font = make_font(CP_FONT, 22, weight=400)
    y = 460

    for title, lines in features:
        draw_divider(draw, y, W)
        y += 20
        bbox = draw.textbbox((0, 0), title, font=feat_title_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), title, fill=DARK_BROWN, font=feat_title_font)
        y += 45
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=feat_body_font)
            lw = bbox[2] - bbox[0]
            draw.text(((W - lw) // 2, y), line, fill=SAGE, font=feat_body_font)
            y += 30
        y += 30

    # "Completely free. No sign-up. No ads."
    draw_divider(draw, y, W)
    y += 20
    free_font = make_font(CP_FONT, 22, weight=400)
    free_text = "Completely free. No sign-up. No ads."
    bbox = draw.textbbox((0, 0), free_text, font=free_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, y), free_text, fill=MUTED_BROWN, font=free_font)

    # CTA Button
    y += 60
    btn_w, btn_h = 300, 55
    btn_x = (W - btn_w) // 2
    draw.rounded_rectangle([btn_x, y, btn_x + btn_w, y + btn_h], radius=28, fill=TERRACOTTA)
    btn_font = make_font(CP_FONT, 22, weight=600)
    btn_text = "Visit neshama.ca"
    bbox = draw.textbbox((0, 0), btn_text, font=btn_font)
    btw = bbox[2] - bbox[0]
    bth = bbox[3] - bbox[1]
    draw.text((btn_x + (btn_w - btw) // 2, y + (btn_h - bth) // 2 - 2), btn_text, fill='white', font=btn_font)

    # Bottom footer
    footer_font = make_font(CP_FONT, 18, weight=400)
    footer = "A free resource for Toronto & Montreal's Jewish community"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, H - 100), footer, fill=SAGE, font=footer_font)

    # Bottom dark strip
    draw.rectangle([0, H - 5, W, H], fill=DARK_STRIP)

    path = os.path.join(os.path.dirname(__file__), 'marketing-kit', 'whatsapp', 'whatsapp-vertical-card.png')
    img.save(path, 'PNG')
    logging.info(f\'  ✅ Saved {path}')
    return path


if __name__ == '__main__':
    logging.info(\'\n🎨 Regenerating Neshama marketing graphics...\n')
    logging.info(\'Removing "18" vendor count from all assets:\n')

    generate_post2_three_features()
    generate_story_features()
    generate_whatsapp_vertical()

    logging.info(\'\n✅ All 3 graphics regenerated!\n')
