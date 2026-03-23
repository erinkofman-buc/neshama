#!/usr/bin/env python3
"""Generate 8 Instagram carousel slides for BehindTheCounterRx creatine post."""

from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

# === BRAND SPECS ===
BG_COLOR = "#FAFAF7"
ACCENT_GREEN = "#2D7D46"
TEXT_DARK = "#2D2D2D"
TEXT_SECONDARY = "#666666"
WATERMARK_COLOR = "#CCCCCC"
DOT_INACTIVE = "#D0D0D0"
SIZE = (1080, 1080)
TOTAL_SLIDES = 8

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# === FONT LOADING ===
def load_font(bold=False, size=48):
    """Try Georgia, then Times, then default."""
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/Library/Fonts/Georgia Bold.ttf",
            "/System/Library/Fonts/Supplemental/Georgia-Bold.ttf",
            "/System/Library/Fonts/Times New Roman Bold.ttf",
            "/Library/Fonts/Times New Roman Bold.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Georgia.ttf",
            "/System/Library/Fonts/Times New Roman.ttf",
            "/Library/Fonts/Times New Roman.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # Fallback: try any available serif
    fallbacks = [
        "/System/Library/Fonts/NewYork.ttf",
        "/System/Library/Fonts/Palatino.ttc",
    ]
    for path in fallbacks:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def get_fonts():
    return {
        "heading": load_font(bold=True, size=54),
        "heading_large": load_font(bold=True, size=60),
        "body": load_font(bold=False, size=30),
        "body_large": load_font(bold=False, size=34),
        "subtext": load_font(bold=False, size=36),
        "watermark": load_font(bold=False, size=18),
        "footer": load_font(bold=False, size=24),
        "small": load_font(bold=False, size=20),
        "slide1_heading": load_font(bold=True, size=52),
        "slide1_sub": load_font(bold=False, size=38),
        "slide2_heading": load_font(bold=True, size=72),
        "slide2_body": load_font(bold=False, size=30),
    }


FONTS = get_fonts()


# === DRAWING HELPERS ===

def draw_text_wrapped(draw, text, x, y, font, fill, max_width, line_spacing=1.4):
    """Draw text with word wrapping. Returns the y position after the last line."""
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        # Wrap each paragraph
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

    current_y = y
    for line in lines:
        if line == "":
            bbox = draw.textbbox((0, 0), "A", font=font)
            h = bbox[3] - bbox[1]
            current_y += int(h * 0.7)
            continue
        draw.text((x, current_y), line, fill=fill, font=font)
        bbox = draw.textbbox((0, 0), line, font=font)
        h = bbox[3] - bbox[1]
        current_y += int(h * line_spacing)
    return current_y


def draw_slide_dots(draw, current_slide):
    """Draw slide indicator dots at the bottom."""
    dot_radius = 6
    dot_spacing = 24
    total_width = (TOTAL_SLIDES - 1) * dot_spacing
    start_x = (SIZE[0] - total_width) // 2
    y = SIZE[1] - 80

    for i in range(TOTAL_SLIDES):
        cx = start_x + i * dot_spacing
        color = ACCENT_GREEN if i == current_slide else DOT_INACTIVE
        r = dot_radius if i == current_slide else 5
        draw.ellipse([cx - r, y - r, cx + r, y + r], fill=color)


def draw_watermark(draw):
    """Draw BehindTheCounterRx watermark at bottom."""
    font = FONTS["watermark"]
    text = "BehindTheCounterRx"
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (SIZE[0] - w) // 2
    y = SIZE[1] - 50
    draw.text((x, y), text, fill=WATERMARK_COLOR, font=font)


def new_slide():
    img = Image.new("RGB", SIZE, BG_COLOR)
    draw = ImageDraw.Draw(img)
    return img, draw


def draw_accent_line(draw, y, width=200):
    """Draw a pharmacy green accent line."""
    x_start = (SIZE[0] - width) // 2
    draw.rectangle([x_start, y, x_start + width, y + 4], fill=ACCENT_GREEN)


def draw_heading_centered(draw, text, y, font=None):
    """Draw centered heading text. Returns bottom y."""
    if font is None:
        font = FONTS["heading"]
    # Wrap if needed
    lines = []
    words = text.split()
    current_line = words[0]
    max_w = SIZE[0] - 160
    for word in words[1:]:
        test = current_line + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current_line = test
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)

    current_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (SIZE[0] - w) // 2
        draw.text((x, current_y), line, fill=TEXT_DARK, font=font)
        current_y += int(h * 1.35)
    return current_y


# === SLIDE GENERATORS ===

def slide_1():
    img, draw = new_slide()
    # Center the heading vertically
    heading = "The supplement every\nwoman over 40\nshould know about"
    subtext = "(and it's not collagen)"

    # Draw heading
    y = 260
    font = FONTS["slide1_heading"]
    for line in heading.split("\n"):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (SIZE[0] - w) // 2
        draw.text((x, y), line, fill=TEXT_DARK, font=font)
        y += int(h * 1.4)

    # Accent line
    draw_accent_line(draw, y + 15, width=260)

    # Subtext
    y += 50
    font_sub = FONTS["slide1_sub"]
    bbox = draw.textbbox((0, 0), subtext, font=font_sub)
    w = bbox[2] - bbox[0]
    x = (SIZE[0] - w) // 2
    draw.text((x, y), subtext, fill=TEXT_SECONDARY, font=font_sub)

    draw_slide_dots(draw, 0)
    draw_watermark(draw)
    return img


def slide_2():
    img, draw = new_slide()

    # Big heading
    heading = "It's creatine."
    font = FONTS["slide2_heading"]
    bbox = draw.textbbox((0, 0), heading, font=font)
    w = bbox[2] - bbox[0]
    x = (SIZE[0] - w) // 2
    draw.text((x, 220), heading, fill=ACCENT_GREEN, font=font)

    # Body
    body = ("Yes, really.\n\n"
            "Before you scroll away \u2014 I'm a pharmacist with 18 years of experience, "
            "and this is one of the few supplements I actually take myself.")
    draw_text_wrapped(draw, body, 100, 360, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.5)

    draw_slide_dots(draw, 1)
    draw_watermark(draw)
    return img


def slide_3():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "What even IS creatine?", 180)
    draw_accent_line(draw, y + 5, 180)

    body = ("Your body already makes it.\n"
            "It lives in your muscles and brain.\n"
            "It helps your cells make energy.\n\n"
            "Supplementing just tops up your stores.")
    draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.6)

    draw_slide_dots(draw, 2)
    draw_watermark(draw)
    return img


def slide_4():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "Why it matters after 40", 160)
    draw_accent_line(draw, y + 5, 180)

    body = ("During perimenopause, declining estrogen accelerates muscle loss.\n\n"
            "A 2024 review of 1,000+ participants found creatine + exercise "
            "significantly improved strength in older adults.")
    draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.55)

    draw_slide_dots(draw, 3)
    draw_watermark(draw)
    return img


def slide_5():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "The brain benefit nobody talks about", 150)
    draw_accent_line(draw, y + 5, 180)

    body = ("A 2025 study on peri/menopausal women found creatine improved "
            "reaction time and brain creatine levels.\n\n"
            "Women may respond BETTER than men to creatine's brain effects.")
    draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.55)

    draw_slide_dots(draw, 4)
    draw_watermark(draw)
    return img


def slide_6():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "What about bone density?", 160)
    draw_accent_line(draw, y + 5, 180)

    body = ("Honest answer: mixed evidence.\n\n"
            "A 2-year trial found improved bone geometry but not BMD directly.\n\n"
            "Promising but not proven. I won't oversell it.")
    draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.55)

    draw_slide_dots(draw, 5)
    draw_watermark(draw)
    return img


def slide_7():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "Is it safe?", 180)
    draw_accent_line(draw, y + 5, 140)

    body = ("29 studies. 951 women.\nNo serious adverse events.\n\n"
            "Most common side effect: 1\u20132 lbs water weight.\n\n"
            "Skip if: kidney disease, pregnant, on certain diuretics.")
    draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.55)

    draw_slide_dots(draw, 6)
    draw_watermark(draw)
    return img


def slide_8():
    img, draw = new_slide()

    y = draw_heading_centered(draw, "How to start", 150)
    draw_accent_line(draw, y + 5, 160)

    body = ("3\u20135g creatine monohydrate daily\n"
            "With a meal\n"
            "No loading phase needed\n"
            "Give it 8\u201312 weeks")
    end_y = draw_text_wrapped(draw, body, 100, y + 50, FONTS["body_large"], TEXT_DARK, SIZE[0] - 200, line_spacing=1.6)

    # Footer CTA
    footer = "Full breakdown + what I personally take --> link in bio"
    font_footer = FONTS["footer"]
    bbox = draw.textbbox((0, 0), footer, font=font_footer)
    w = bbox[2] - bbox[0]
    # Draw a subtle green background bar
    bar_y = end_y + 40
    draw.rectangle([60, bar_y, SIZE[0] - 60, bar_y + 50], fill="#E8F5E9")
    draw.text(((SIZE[0] - w) // 2, bar_y + 12), footer, fill=ACCENT_GREEN, font=font_footer)

    # Disclaimer
    disclaimer = "Not medical advice. Affiliate links may be used."
    font_small = FONTS["small"]
    bbox = draw.textbbox((0, 0), disclaimer, font=font_small)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE[0] - w) // 2, bar_y + 75), disclaimer, fill=TEXT_SECONDARY, font=font_small)

    draw_slide_dots(draw, 7)
    draw_watermark(draw)
    return img


# === MAIN ===
if __name__ == "__main__":
    generators = [slide_1, slide_2, slide_3, slide_4, slide_5, slide_6, slide_7, slide_8]
    for i, gen in enumerate(generators):
        img = gen()
        path = os.path.join(OUTPUT_DIR, f"slide_{i+1}.png")
        img.save(path, "PNG")
        print(f"Saved: {path}")
    print(f"\nAll {TOTAL_SLIDES} slides generated successfully!")
