#!/usr/bin/env python3
"""Generate Neshama post-Passover Instagram graphics."""

from PIL import Image, ImageDraw, ImageFont
import os
import textwrap

# === CONFIGURATION ===
W, H = 1080, 1080
BG = "#FFF8F0"
DARK_BROWN = "#3E2723"
TERRACOTTA = "#D2691E"
MUTED_BROWN = "#5C534A"
LIGHT_SAGE = "#C8D5B9"

OUT = "/Users/erinkofman/Desktop/Neshama/instagram-posts"

# === FONT LOADING ===
def find_font(candidates, size):
    """Try multiple font paths, fall back to default."""
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Last resort: try common names via Pillow's font search
    for name in ["Georgia.ttf", "Times New Roman.ttf", "DejaVuSerif.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    print(f"WARNING: No serif font found, using default at size {size}")
    return ImageFont.load_default()

# Serif bold candidates (for headings - stand-in for Cormorant Garamond)
HEADING_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/Library/Fonts/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    "/Library/Fonts/Times New Roman Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]

# Serif regular candidates (for body - stand-in for Crimson Pro)
BODY_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/Library/Fonts/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]

def heading_font(size):
    return find_font(HEADING_FONTS, size)

def body_font(size):
    return find_font(BODY_FONTS, size)


# === HELPER FUNCTIONS ===

def new_canvas():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    return img, draw

def text_bbox_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_centered_text(draw, text, y, font, fill):
    tw, th = text_bbox_size(draw, text, font)
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return th

def draw_wrapped_centered(draw, text, y, font, fill, max_width=900):
    """Draw multi-line text, each line centered."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        tw, _ = text_bbox_size(draw, test, font)
        if tw > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    total_h = 0
    for line in lines:
        tw, th = text_bbox_size(draw, line, font)
        x = (W - tw) // 2
        draw.text((x, y + total_h), line, font=font, fill=fill)
        total_h += th + 12  # line spacing
    return total_h

def draw_terracotta_line(draw, y, width=600):
    x0 = (W - width) // 2
    draw.line([(x0, y), (x0 + width, y)], fill=TERRACOTTA, width=2)

def draw_neshama_footer(draw, y=None):
    if y is None:
        y = H - 80
    fnt = body_font(22)
    draw_centered_text(draw, "neshama.ca", y, fnt, MUTED_BROWN)

def draw_dots(draw, current, total=5, y=None):
    """Draw slide indicator dots."""
    if y is None:
        y = H - 60
    dot_r = 8
    spacing = 30
    total_width = (total - 1) * spacing
    start_x = (W - total_width) // 2

    for i in range(total):
        cx = start_x + i * spacing
        color = TERRACOTTA if i == current else LIGHT_SAGE
        draw.ellipse([cx - dot_r, y - dot_r, cx + dot_r, y + dot_r], fill=color)


# === GRAPHIC 1: Post-Passover ===
def graphic1():
    img, draw = new_canvas()

    fnt_main = heading_font(60)
    fnt_second = heading_font(48)

    # Center the two lines as a block
    h1 = text_bbox_size(draw, "The holiday is over.", fnt_main)[1]
    h2 = text_bbox_size(draw, "The mourning wasn't.", fnt_second)[1]
    block_h = h1 + 40 + h2  # 40px gap between lines
    start_y = (H - block_h) // 2 - 40  # shift up slightly for balance

    draw_centered_text(draw, "The holiday is over.", start_y, fnt_main, DARK_BROWN)
    draw_centered_text(draw, "The mourning wasn't.", start_y + h1 + 40, fnt_second, DARK_BROWN)

    # Terracotta line
    line_y = H - 130
    draw_terracotta_line(draw, line_y)

    # Footer
    draw_neshama_footer(draw, H - 90)

    path = os.path.join(OUT, "apr09-post-passover.png")
    img.save(path)
    print(f"Saved: {path}")


# === GRAPHIC 2: The In-Between ===
def graphic2():
    img, draw = new_canvas()

    fnt_main = heading_font(58)
    fnt_sub = body_font(30)

    h1 = text_bbox_size(draw, "The in-between.", fnt_main)[1]
    subtitle = "After the holiday ends, the quiet returns."
    h2 = text_bbox_size(draw, subtitle, fnt_sub)[1]
    block_h = h1 + 30 + h2
    start_y = (H - block_h) // 2 - 40

    draw_centered_text(draw, "The in-between.", start_y, fnt_main, DARK_BROWN)
    draw_centered_text(draw, subtitle, start_y + h1 + 30, fnt_sub, MUTED_BROWN)

    line_y = H - 130
    draw_terracotta_line(draw, line_y)

    draw_neshama_footer(draw, H - 90)

    path = os.path.join(OUT, "apr12-the-in-between.png")
    img.save(path)
    print(f"Saved: {path}")


# === GRAPHIC 3: Yizkor Carousel ===
def graphic3():
    carousel_dir = os.path.join(OUT, "apr13-yizkor-carousel")
    os.makedirs(carousel_dir, exist_ok=True)

    slides = [
        {
            "heading": "What is Yizkor?",
            "body": "A memorial prayer said four times a year. It means 'remember.'"
        },
        {
            "heading": "When do we say it?",
            "body": "Yom Kippur. Shemini Atzeret. The last day of Passover. Shavuot. Four times the calendar stops and says: remember who you've lost."
        },
        {
            "heading": "What happens during Yizkor?",
            "body": "Those who have lost a parent, spouse, sibling, or child rise and pray. Those who haven't traditionally step outside \u2014 a quiet acknowledgement that this moment belongs to the mourners."
        },
        {
            "heading": "Why it matters",
            "body": "Most traditions grieve once and move on. Judaism says: come back to it. Four times a year, your community stands with you while you remember."
        },
        {
            "heading": "Neshama exists for the same reason.",
            "body": "So no one remembers alone.",
            "footer": True
        },
    ]

    for i, slide in enumerate(slides):
        img, draw = new_canvas()

        fnt_heading = heading_font(50)
        fnt_body = body_font(28)

        # Heading
        heading_h = draw_wrapped_centered(draw, slide["heading"], 200, fnt_heading, DARK_BROWN, max_width=850)

        # Terracotta accent line under heading
        line_y = 200 + heading_h + 20
        draw_terracotta_line(draw, line_y, width=400)

        # Body text
        body_y = line_y + 40
        draw_wrapped_centered(draw, slide["body"], body_y, fnt_body, DARK_BROWN, max_width=820)

        # Dots
        draw_dots(draw, i, total=5, y=H - 50)

        # Footer on last slide
        if slide.get("footer"):
            draw_neshama_footer(draw, H - 100)

        path = os.path.join(carousel_dir, f"slide-{i+1}.png")
        img.save(path)
        print(f"Saved: {path}")


# === GRAPHIC 4: Yom HaShoah ===
def graphic4():
    img, draw = new_canvas()

    fnt_main = heading_font(62)
    fnt_sub = heading_font(44)

    # Very faint terracotta line above text
    line_y = (H // 2) - 100
    draw_terracotta_line(draw, line_y, width=300)

    h1 = text_bbox_size(draw, "Six million souls.", fnt_main)[1]
    h2 = text_bbox_size(draw, "We remember.", fnt_sub)[1]
    block_h = h1 + 35 + h2
    start_y = line_y + 30

    draw_centered_text(draw, "Six million souls.", start_y, fnt_main, DARK_BROWN)
    draw_centered_text(draw, "We remember.", start_y + h1 + 35, fnt_sub, DARK_BROWN)

    # No logo, no neshama.ca. Just the words.

    path = os.path.join(OUT, "apr14-yom-hashoah.png")
    img.save(path)
    print(f"Saved: {path}")


# === MAIN ===
if __name__ == "__main__":
    print("Generating Neshama post-Passover Instagram graphics...")
    print(f"Output directory: {OUT}\n")

    graphic1()
    graphic2()
    graphic3()
    graphic4()

    print("\nDone! All graphics generated.")
