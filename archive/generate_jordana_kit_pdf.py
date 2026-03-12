#!/usr/bin/env python3
"""Generate a clean PDF of Jordana's Outreach Kit from the markdown source."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import re

OUTPUT = "/Users/erinkofman/Desktop/Neshama/marketing-kit/JORDANA-OUTREACH-KIT.pdf"

# Brand colors
TERRACOTTA = HexColor("#D2691E")
DARK_BROWN = HexColor("#3E2723")
CREAM = HexColor("#FFF8F0")
SAGE = HexColor("#9E9488")

styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    'KitTitle', parent=styles['Title'],
    fontSize=24, textColor=DARK_BROWN,
    spaceAfter=6, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'KitSubtitle', parent=styles['Normal'],
    fontSize=12, textColor=SAGE,
    spaceAfter=20, fontName='Helvetica'
))
styles.add(ParagraphStyle(
    'SectionHead', parent=styles['Heading1'],
    fontSize=16, textColor=TERRACOTTA,
    spaceBefore=18, spaceAfter=8, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'SubHead', parent=styles['Heading2'],
    fontSize=13, textColor=DARK_BROWN,
    spaceBefore=12, spaceAfter=6, fontName='Helvetica-Bold'
))
styles.add(ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontSize=10.5, textColor=DARK_BROWN,
    spaceAfter=6, fontName='Helvetica', leading=14
))
styles.add(ParagraphStyle(
    'BodyBold', parent=styles['Normal'],
    fontSize=10.5, textColor=DARK_BROWN,
    spaceAfter=6, fontName='Helvetica-Bold', leading=14
))
styles.add(ParagraphStyle(
    'Quote', parent=styles['Normal'],
    fontSize=10, textColor=HexColor("#555555"),
    leftIndent=20, spaceAfter=6, fontName='Helvetica-Oblique', leading=13,
    borderColor=SAGE, borderWidth=0, borderPadding=0
))
styles.add(ParagraphStyle(
    'KitBullet', parent=styles['Normal'],
    fontSize=10.5, textColor=DARK_BROWN,
    spaceAfter=4, fontName='Helvetica', leading=14,
    leftIndent=15, bulletIndent=5
))
styles.add(ParagraphStyle(
    'SmallNote', parent=styles['Normal'],
    fontSize=9, textColor=SAGE,
    spaceAfter=4, fontName='Helvetica-Oblique'
))

def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch
    )
    story = []

    # Title page
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("Neshama", styles['KitTitle']))
    story.append(Paragraph("Cofounder Outreach Kit for Jordana", styles['KitTitle']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Updated March 12, 2026", styles['KitSubtitle']))
    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "Everything you need: story, messaging templates, FAQ answers, "
        "tracking links, and contact lists. Nothing goes out without a conversation first — "
        "use these as starting points and make them yours.",
        styles['Body']
    ))
    story.append(PageBreak())

    # --- WHY YOUR OUTREACH MATTERS ---
    story.append(Paragraph("Why Your Outreach Matters", styles['SectionHead']))
    story.append(Paragraph(
        "The product is built. 24 pages, 200+ obituaries, 129 vendors, 18 caterers, "
        "meal coordination, yahrzeit reminders, guestbooks — all live, all working. The tech is done.",
        styles['Body']
    ))
    story.append(Paragraph(
        "But none of it matters without people. Right now, Neshama is a fully stocked store "
        "with no customers walking in. <b>Your outreach is the ignition.</b> Every message you send, "
        "every chesed committee you tell, every caterer friend you loop in — that's what turns "
        "a built product into a living community.",
        styles['Body']
    ))
    story.append(Paragraph(
        "We can't buy this kind of trust. It has to come from you, person to person.",
        styles['BodyBold']
    ))
    for bullet in [
        "<b>Vendor revenue depends on traffic data.</b> We can't sell featured listings until we show vendors they're getting clicks. Your outreach drives the traffic.",
        "<b>Community trust compounds.</b> The earlier real people start using it, the more organic word-of-mouth builds.",
        "<b>We're spending $8.25/month.</b> We don't need millions. We need the right 500 people — and you know them."
    ]:
        story.append(Paragraph(bullet, styles['KitBullet'], bulletText='•'))

    # --- OUR STORY ---
    story.append(Paragraph("Our Story — When People Ask 'Why?'", styles['SectionHead']))
    story.append(Paragraph(
        "Your mom was a therapist who read obituaries to identify former patients and pay her respects. "
        "She was also the person who made the big salads, who cooked, who brought everyone together. "
        "When you lost her to MSA nearly eight years ago, you started doing both — reading every obituary, "
        "and feeding people. Jem Salads grew out of that.",
        styles['Body']
    ))
    story.append(Paragraph(
        "Through catering shivas every week, you saw how broken the process was. Three different "
        "funeral home websites. Meals overlapping on Monday, nothing on Wednesday. Families drowning "
        "in logistics. You came to me and said: there should be one place for all of this.",
        styles['Body']
    ))
    story.append(Paragraph(
        "When someone asks you about it, you don't need a pitch. You just tell the truth.",
        styles['BodyBold']
    ))

    # --- WHAT NESHAMA IS ---
    story.append(Paragraph("What Neshama Is", styles['SectionHead']))
    story.append(Paragraph(
        "Neshama (neshama.ca) is a free community platform for Jewish families in Toronto and Montreal.",
        styles['Body']
    ))
    for feature in [
        "<b>Obituary feed</b> — Aggregated from 4 funeral homes (Steeles, Benjamin's, Paperman's, Misaskim). 200+ listings. Updated daily.",
        "<b>Shiva meal coordination</b> — Create a shiva page. Community signs up for meal slots. No overlaps.",
        "<b>Vendor directory</b> — 129 verified vendors: food + gifts. Browsable by category.",
        "<b>Digital condolence guestbook</b> — Tributes, memorial candle, exportable PDF keepsake.",
        "<b>Yahrzeit reminders</b> — Annual Hebrew calendar reminders. Fully automated. No other site does this properly.",
        "<b>Plant a Memorial Tree</b> — JNF partnership ($18/tree).",
        "<b>Educational guides</b> — What to bring, how to sit shiva, kosher food guide, Passover grief guide.",
    ]:
        story.append(Paragraph(feature, styles['KitBullet'], bulletText='•'))

    # --- OUTREACH TEMPLATES ---
    story.append(PageBreak())
    story.append(Paragraph("Outreach Templates — Copy, Personalize, Send", styles['SectionHead']))
    story.append(Paragraph(
        "All templates below are starting points. Make them yours — your voice is what makes them work.",
        styles['SmallNote']
    ))

    # WhatsApp short
    story.append(Paragraph("Text Groups — Quick Drop (4 lines max)", styles['SubHead']))
    story.append(Paragraph(
        "Hey — some of you know my mom used to read obituaries. After losing her, I started doing "
        "the same. Erin Kofman and I built neshama.ca — one place for Toronto/Montreal Jewish "
        "obituaries, shiva meal coordination, and 129+ caterers and vendors. Free, no sign-up. "
        "Worth bookmarking: www.neshama.ca",
        styles['Quote']
    ))

    # WhatsApp long
    story.append(Paragraph("Personal Messages — Longer Version", styles['SubHead']))
    story.append(Paragraph(
        "Hey — I wanted to share something close to my heart. You know my mom read obituaries "
        "to find former patients. After losing her, I started doing both — reading obituaries and "
        "feeding people. Through Jem Salads I saw the same problem every week: meals overlapping, "
        "days uncovered, families checking three different funeral home websites.<br/><br/>"
        "So Erin and I built Neshama (www.neshama.ca). Obituaries from Toronto and Montreal in one "
        "feed, a meal coordination tool so nothing overlaps, and 129+ caterers and vendors. Free, "
        "respectful, no ads. Worth a look.",
        styles['Quote']
    ))

    # Orthodox
    story.append(Paragraph("Orthodox Community Circles", styles['SubHead']))
    story.append(Paragraph(
        "Hi [Name] — quick one. Erin Kofman and I built a community resource called Neshama "
        "(www.neshama.ca). You know how it is — three people bring chicken Monday, nobody brings "
        "anything Wednesday.<br/><br/>"
        "Neshama has obituaries from local funeral homes in one place, a meal coordination tool for "
        "shiva, and a full \"How Can I Help?\" hub with local food partners and gifts. Free, already "
        "live with 200+ listings. If you know anyone on a chesed committee, I'd love for them to see it.",
        styles['Quote']
    ))

    # Synagogue
    story.append(Paragraph("Synagogue / Chesed Committee Email", styles['SubHead']))
    story.append(Paragraph(
        "Hi [Name],<br/><br/>"
        "I wanted to share a community resource that I think would be valuable for [Synagogue Name]'s "
        "congregation.<br/><br/>"
        "I've been working with Erin Kofman on a site called Neshama (www.neshama.ca) that brings "
        "together obituaries from Toronto and Montreal's Jewish funeral homes in one place, along with "
        "a meal coordination tool for shiva and a directory of 129+ local caterers and vendors.<br/><br/>"
        "As someone who runs a catering business that serves shiva families, I see how fragmented and "
        "stressful the logistics can be. Neshama gives the community a simple way to find information, "
        "coordinate meals, and connect with vendors, all in one place. Free for families.<br/><br/>"
        "Would you be open to mentioning it in your next newsletter or sharing it with your chesed "
        "committee? Here's a blurb you can use:<br/><br/>"
        "<i>Community Resource: Neshama — A new resource for Jewish families in Toronto and Montreal. "
        "Search obituaries from local funeral homes, coordinate shiva meals with friends and neighbours, "
        "and browse a directory of verified caterers and vendors. Free to use, no sign-up required. "
        "Visit www.neshama.ca</i><br/><br/>"
        "Warmly,<br/>Jordana Mednick",
        styles['Quote']
    ))

    # Vendor peer
    story.append(Paragraph("Vendor Peers (Caterer-to-Caterer)", styles['SubHead']))
    story.append(Paragraph(
        "Hey [Name] — hope business is good! I wanted to let you know about something Erin and I "
        "have been building. It's called Neshama (www.neshama.ca) — a community hub for Jewish "
        "families dealing with a loss. Obituary feed, meal coordination for shiva, and a \"How Can I "
        "Help?\" hub with local food partners and gifts.<br/><br/>"
        "You're actually already listed on it — Erin compiled a directory of caterers and vendors across "
        "Toronto and Montreal who serve shiva families. If any details need updating, just let me know. "
        "There's also an option for a featured listing if you want more visibility, but your current "
        "listing stays free either way.<br/><br/>"
        "Worth checking out: www.neshama.ca/help",
        styles['Quote']
    ))

    # Funeral home
    story.append(Paragraph("Funeral Home Contacts", styles['SubHead']))
    story.append(Paragraph(
        "Hi [Name] — I'm reaching out because I wanted to make you aware of a community resource "
        "called Neshama (www.neshama.ca). It aggregates obituaries from Jewish funeral homes across "
        "Toronto and Montreal — including [Funeral Home Name] — along with shiva meal coordination "
        "tools and a \"How Can I Help?\" hub.<br/><br/>"
        "I've been working on this with Erin Kofman, and I wanted to make sure you knew about it. "
        "We'd genuinely appreciate any feedback. Is this useful from your perspective? Is there "
        "anything about how your listings appear that you'd want adjusted?<br/><br/>"
        "Happy to chat anytime.<br/><br/>"
        "Best,<br/>Jordana Mednick",
        styles['Quote']
    ))

    # Dana
    story.append(Paragraph("Dana Cohen Ezer / Hartsman Institute", styles['SubHead']))
    story.append(Paragraph(
        "Hey Dana — I've been meaning to tell you about this. You know what losing my mom did to me. "
        "One of the things that came out of it — you'll understand this — is that I started reading "
        "obituaries the way she used to.<br/><br/>"
        "So Erin Kofman and I built something. It's called Neshama (www.neshama.ca). It brings together "
        "obituaries from Toronto and Montreal funeral homes, has a meal coordination tool for shiva, "
        "and a full directory of caterers and vendors. Free for families, no sign-up.<br/><br/>"
        "I know through your work with the Hartsman Institute you see the community side of grief and "
        "support every day. I think Neshama could be a natural fit to share with chesed committees, "
        "community organizations, anyone working with families during difficult times.<br/><br/>"
        "Would love for you to take a look. And if you see the right people to share it with, "
        "that would mean a lot.",
        styles['Quote']
    ))

    # --- FAQ ---
    story.append(PageBreak())
    story.append(Paragraph("FAQ — When People Ask Questions", styles['SectionHead']))

    faqs = [
        ("What is this exactly?",
         "A free website for Jewish families when someone passes away. Pulls together obituaries "
         "from funeral homes, has a meal coordination tool so friends don't overlap, and a directory "
         "of 129+ local caterers and vendors. Everything the community needs during shiva, in one place."),
        ("Why not just call a caterer?",
         "You absolutely should — the site even has a directory to help you find one. But the "
         "coordination piece is different. When 12 people want to bring food, you end up with three "
         "kugels Monday and nothing Wednesday. The meal tool lets everyone sign up for specific days."),
        ("Does it cost anything?",
         "No. Free for families. No accounts, no fees. We sustain the site through optional vendor "
         "listings — the family side will always be free."),
        ("How do you make money?",
         "Vendors can pay for featured listings to get more visibility. We also have Amazon affiliate "
         "links and a voluntary sustainer program ($18/year). But the family-facing side is free. Always."),
        ("Is this only for Jewish families?",
         "It was built for the Jewish community — shiva, yahrzeit, kosher considerations. But anyone "
         "is welcome to use it."),
    ]
    for q, a in faqs:
        story.append(Paragraph("\u201c" + q + "\u201d", styles['BodyBold']))
        story.append(Paragraph(a, styles['Body']))
        story.append(Spacer(1, 4))

    # --- KEY PAGES ---
    story.append(Paragraph("Key Pages", styles['SectionHead']))
    pages = [
        ["Homepage", "www.neshama.ca"],
        ["Obituary Feed", "www.neshama.ca/feed"],
        ["Meal Coordination", "www.neshama.ca/shiva/organize"],
        ["How Can I Help? (Food)", "www.neshama.ca/help/food"],
        ["What to Bring to a Shiva", "www.neshama.ca/what-to-bring-to-a-shiva"],
        ["Passover Grief Guide", "www.neshama.ca/first-passover-after-loss"],
        ["How to Sit Shiva", "www.neshama.ca/how-to-sit-shiva"],
        ["Kosher Shiva Food", "www.neshama.ca/kosher-shiva-food"],
        ["Yahrzeit Reminders", "www.neshama.ca/yahrzeit"],
        ["Send a Gift", "www.neshama.ca/help/gifts"],
        ["About", "www.neshama.ca/about"],
        ["Cofounder Dashboard", "www.neshama.ca/dashboard"],
    ]
    table = Table(pages, colWidths=[2.5*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), DARK_BROWN),
        ('TEXTCOLOR', (1, 0), (1, -1), TERRACOTTA),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, HexColor("#E0D8D0")),
    ]))
    story.append(table)

    # --- REFERRAL TRACKING ---
    story.append(Spacer(1, 12))
    story.append(Paragraph("Referral Tracking Links", styles['SectionHead']))
    story.append(Paragraph(
        "Use these links when sharing so we can see which channels drive traffic. "
        "Results appear on your dashboard in real time.",
        styles['Body']
    ))
    refs = [
        ["Channel", "Tracking Link"],
        ["Your texts (personal)", "neshama.ca/?ref=jordana-whatsapp"],
        ["Community groups", "neshama.ca/?ref=jordana-whatsapp-groups"],
        ["Dana's network", "neshama.ca/?ref=dana"],
        ["Synagogue emails", "neshama.ca/?ref=synagogue-email"],
        ["Facebook Jewish groups", "neshama.ca/?ref=facebook-jewish"],
        ["Instagram bio", "neshama.ca/?ref=instagram"],
        ["Funeral home partnerships", "neshama.ca/?ref=funeral-home"],
        ["Canadian Jewish News", "neshama.ca/?ref=cjn-press"],
        ["Word of mouth", "neshama.ca/?ref=word-of-mouth"],
        ["Vendor outreach", "neshama.ca/?ref=vendor-email"],
    ]
    ref_table = Table(refs, colWidths=[2.5*inch, 4*inch])
    ref_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('TEXTCOLOR', (0, 0), (-1, -1), DARK_BROWN),
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#F5F1EB")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, HexColor("#E0D8D0")),
    ]))
    story.append(ref_table)

    # Closing
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", color=SAGE, thickness=1))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<i>This is your thing, Jordana. You had the idea. Let's make it matter.</i>",
        ParagraphStyle('Closing', parent=styles['Body'],
                       fontSize=12, textColor=TERRACOTTA, fontName='Helvetica-Oblique',
                       alignment=TA_CENTER)
    ))

    doc.build(story)
    print(f"PDF generated: {OUTPUT}")

if __name__ == "__main__":
    build_pdf()
