#!/usr/bin/env python3
"""Generate Neshama 'How It Works' one-pager — single tall image for email/WhatsApp/IG Story.
1080x1920 (9:16 story format). Also exports letter-size PDF."""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1080, 1920
BG = "#FFF8F0"
DARK_BROWN = "#3E2723"
TERRACOTTA = "#D2691E"
MUTED_BROWN = "#5C534A"
SAGE = "#B2BEB5"
GOLD = "#C9A96E"
WHITE = "#FFFFFF"

OUT = os.path.dirname(os.path.abspath(__file__))

def find_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

HEADING_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/Library/Fonts/Georgia Bold.ttf",
]
BODY_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/Library/Fonts/Georgia.ttf",
]
ITALIC_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
    "/Library/Fonts/Georgia Italic.ttf",
]

def heading_font(size): return find_font(HEADING_FONTS, size)
def body_font(size): return find_font(BODY_FONTS, size)
def italic_font(size): return find_font(ITALIC_FONTS, size)

def text_bbox_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_centered_text(draw, text, y, font, fill):
    tw, th = text_bbox_size(draw, text, font)
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return th

def draw_wrapped_centered(draw, text, y, font, fill, max_width=920):
    words = text.split()
    lines, current = [], ""
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
    for line in lines:
        y += draw_centered_text(draw, line, y, font, fill) + 8
    return y

def draw_left_text(draw, text, x, y, font, fill):
    draw.text((x, y), text, font=font, fill=fill)
    bbox = draw.textbbox((0, 0), text, font)
    return bbox[3] - bbox[1]

def draw_divider(draw, y, width=80):
    x1 = (W - width) // 2
    draw.rectangle([x1, y, x1 + width, y + 3], fill=GOLD)

def draw_step_circle(draw, num, x, y, size=48):
    draw.ellipse([x, y, x + size, y + size], fill=TERRACOTTA)
    font = heading_font(int(size * 0.5))
    tw, th = text_bbox_size(draw, str(num), font)
    draw.text((x + (size - tw) // 2, y + (size - th) // 2 - 2), str(num), font=font, fill=WHITE)

# Steps data
steps = [
    {
        "title": "Their memorial appears",
        "desc": "Obituaries are gathered automatically from local funeral homes. No one has to post it.",
    },
    {
        "title": "Someone wants to help",
        "desc": "A friend sees three clear options: bring food, send something thoughtful, or prepare the home.",
    },
    {
        "title": "Meals get organized",
        "desc": "In minutes, a friend sets up a meal schedule \u2014 dates, dietary needs, drop-off details. No account needed.",
    },
    {
        "title": "The link goes out",
        "desc": "Share the page on WhatsApp, email, or text. Friends sign up for a day \u2014 no login required.",
    },
    {
        "title": "The community responds",
        "desc": "The calendar fills in. Everyone sees what's covered and what's still needed. No duplicates, no gaps.",
    },
    {
        "title": "Beyond the meals",
        "desc": "Tributes on the memorial page. A yahrzeit reminder a year later. The connection doesn't end when shiva does.",
    },
]

# Build image
img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# Header
y = 80
draw_divider(draw, y)
y += 25
y += draw_centered_text(draw, "How Neshama Works", y, heading_font(58), DARK_BROWN) + 12
y += draw_centered_text(draw, "Community support when it matters most", y, italic_font(28), MUTED_BROWN) + 20
draw_divider(draw, y)
y += 50

# Steps
left_margin = 120
text_left = 190
max_text_width = W - text_left - 80

for i, step in enumerate(steps):
    # Circle with number
    draw_step_circle(draw, i + 1, left_margin - 50, y - 4, size=52)

    # Title
    th = draw_left_text(draw, step["title"], text_left, y, heading_font(32), DARK_BROWN)
    y += th + 10

    # Description — wrap manually
    words = step["desc"].split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        tw, _ = text_bbox_size(draw, test, body_font(26))
        if tw > max_text_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    for line in lines:
        draw_left_text(draw, line, text_left, y, body_font(26), MUTED_BROWN)
        y += 34

    y += 35

    # Connector line between steps (not after last)
    if i < len(steps) - 1:
        cx = left_margin - 24
        draw.line([(cx, y - 30), (cx, y + 5)], fill=SAGE, width=2)
        y += 10

# Bottom section
y += 20
draw_divider(draw, y)
y += 35

# Tagline
y += draw_centered_text(draw, "No accounts. No fees. Just community.", y, italic_font(30), MUTED_BROWN) + 30

# CTA
y += draw_centered_text(draw, "See the full walkthrough", y, body_font(28), DARK_BROWN) + 10
y += draw_centered_text(draw, "neshama.ca/demo", y, heading_font(36), TERRACOTTA) + 40

# Branding footer
draw_divider(draw, y)
y += 20
draw_centered_text(draw, "neshama.ca", y, body_font(26), SAGE)
draw_centered_text(draw, "Toronto & Montreal", y + 34, body_font(22), SAGE)

# Save PNG
png_path = os.path.join(OUT, "how-neshama-works.png")
img.save(png_path, quality=95)
print(f"  Saved {png_path}")

# Save PDF (letter size — 8.5x11 at 150 DPI = 1275x1650)
pdf_w, pdf_h = 1275, 1650
pdf_img = Image.new("RGB", (pdf_w, pdf_h), BG)
# Scale the 1080x1920 image to fit within letter, maintaining aspect
scale = min(pdf_w / W, pdf_h / H)
new_w = int(W * scale)
new_h = int(H * scale)
resized = img.resize((new_w, new_h), Image.LANCZOS)
paste_x = (pdf_w - new_w) // 2
paste_y = (pdf_h - new_h) // 2
pdf_img.paste(resized, (paste_x, paste_y))

pdf_path = os.path.join(OUT, "how-neshama-works.pdf")
pdf_img.save(pdf_path, "PDF", resolution=150)
print(f"  Saved {pdf_path}")

print("\nDone! One-pager ready for email, WhatsApp, and IG Story.")
