#!/usr/bin/env python3
"""Generate Neshama 'How It Works' Instagram carousel (7 slides).

Alt text for each slide (paste into Buffer/IG when uploading):
1. Cover: "How Neshama works — swipe to see how community comes together when it matters most. neshama.ca"
2. Step 1: "When someone passes away, their obituary is gathered from the funeral home and appears on Neshama automatically."
3. Step 2: "A friend sees the memorial and wants to help. Three options: bring food, send something thoughtful, or prepare the home."
4. Step 3: "In a few minutes, a friend sets up a meal schedule with dates, dietary needs, and drop-off instructions. No account needed."
5. Step 4: "The support page is shared on WhatsApp, email, or text. Friends sign up for a day — no login required."
6. Step 5: "The meal calendar fills in. Green means covered, yellow means almost there. Everyone sees what's still needed."
7. Step 6: "Friends leave tributes on the memorial page. A year later, a yahrzeit reminder brings the community together again. neshama.ca/demo"

Caption for Instagram post:
How does Neshama work? Swipe through to see.

When someone in our community passes away, Neshama brings people together — from the first notification to organized shiva meals to yahrzeit remembrance, a year later and beyond.

No accounts. No fees. Just community taking care of community.

See the full walkthrough: neshama.ca/demo

#shiva #shivameal #jewishcommunity #jewishlife #torontojewish #montrealjewish #nichum #neshamaca #jewishgriefresources #communitycare
"""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1080, 1080
BG = "#FFF8F0"
DARK_BROWN = "#3E2723"
TERRACOTTA = "#D2691E"
MUTED_BROWN = "#5C534A"
SAGE = "#B2BEB5"
GOLD = "#C9A96E"

OUT = os.path.dirname(os.path.abspath(__file__))

# Font loading
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

def heading_font(size): return find_font(HEADING_FONTS, size)
def body_font(size): return find_font(BODY_FONTS, size)

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

def draw_wrapped_centered(draw, text, y, font, fill, max_width=880):
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
        y += draw_centered_text(draw, line, y, font, fill) + 14
    return y

def draw_divider(draw, y, width=80):
    x1 = (W - width) // 2
    draw.rectangle([x1, y, x1 + width, y + 3], fill=GOLD)

def draw_step_number(draw, num, y):
    font = heading_font(120)
    tw, th = text_bbox_size(draw, str(num), font)
    x = (W - tw) // 2
    draw.text((x, y), str(num), font=font, fill=SAGE)
    return th

# Slide data — copy reviewed for grief sensitivity + brand voice
slides = [
    {
        "title": "When someone you love",
        "title2": "passes away",
        "subtitle": "Swipe to see how community\ncomes together when it matters most.",
        "is_cover": True,
    },
    {
        "num": "1",
        "title": "Their memorial appears",
        "body": "When someone passes away, their obituary is gathered from the funeral home and appears on Neshama automatically.",
        "detail": "No one has to post it. It's just there.",
    },
    {
        "num": "2",
        "title": "Someone wants to help",
        "body": "A friend sees the memorial and wants to do something meaningful. They see three clear options: bring food, send something thoughtful, or prepare the home.",
        "detail": "One tap to start helping.",
    },
    {
        "num": "3",
        "title": "Meals get organized",
        "body": "In a few minutes, a friend sets up a meal schedule \u2014 dates, dietary needs, drop-off instructions. No account needed.",
        "detail": "Just a simple form.",
    },
    {
        "num": "4",
        "title": "The link goes out",
        "body": "Share the support page on WhatsApp, by email, or by text. Friends click and sign up for a day.",
        "detail": "No login. No password. Just pick a day.",
    },
    {
        "num": "5",
        "title": "The community responds",
        "body": "The meal calendar fills in \u2014 green means covered, yellow means almost there. No duplicates. No gaps.",
        "detail": "Everyone sees what's still needed.",
    },
    {
        "num": "6",
        "title": "Beyond the meals",
        "body": "Friends leave tributes on the memorial page. A year later, a gentle yahrzeit reminder brings the community back together.",
        "detail": "The connection doesn't end when shiva does.",
        "is_last": True,
        "cta_label": "See it for yourself",
        "cta_url": "neshama.ca/demo",
    },
]

for i, slide in enumerate(slides):
    img, draw = new_canvas()

    if slide.get("is_cover"):
        # Cover slide — human-centric framing
        draw_divider(draw, 260)
        y = 290
        y += draw_centered_text(draw, slide["title"], y, heading_font(56), DARK_BROWN) + 8
        y += draw_centered_text(draw, slide["title2"], y, heading_font(56), DARK_BROWN) + 35
        for line in slide["subtitle"].split("\n"):
            y += draw_centered_text(draw, line, y, body_font(32), MUTED_BROWN) + 10
        y += 50
        draw_divider(draw, y)
        # Swipe indicator
        draw_centered_text(draw, "swipe >>", y + 40, body_font(28), SAGE)
        # Neshama branding at bottom
        draw_centered_text(draw, "neshama.ca", 920, body_font(28), TERRACOTTA)
    else:
        # Step slide
        y = 100
        y += draw_step_number(draw, slide["num"], y) + 10
        draw_divider(draw, y)
        y += 28
        # Step headings at 62pt (meeting 60+ target from Jordana feedback)
        y += draw_centered_text(draw, slide["title"], y, heading_font(62), DARK_BROWN) + 28
        y = draw_wrapped_centered(draw, slide["body"], y, body_font(32), MUTED_BROWN, max_width=880)
        y += 20
        # Detail text at 32pt minimum
        y = draw_wrapped_centered(draw, slide["detail"], y, body_font(32), TERRACOTTA, max_width=880)

        if slide.get("is_last"):
            y += 35
            draw_divider(draw, y)
            y += 28
            draw_centered_text(draw, slide["cta_label"], y, body_font(34), DARK_BROWN)
            y += 50
            draw_centered_text(draw, slide["cta_url"], y, heading_font(38), TERRACOTTA)

        # Neshama branding at bottom — 26pt minimum
        draw_centered_text(draw, "neshama.ca", 1000, body_font(26), SAGE)

    fname = f"slide_{i+1}.png"
    img.save(os.path.join(OUT, fname), quality=95)
    print(f"  Saved {fname}")

print(f"\nDone! {len(slides)} slides in {OUT}")
