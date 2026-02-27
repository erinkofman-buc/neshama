#!/usr/bin/env python3
"""
Neshama Guestbook Keepsake PDF Generator

Generates a beautifully formatted PDF keepsake from memorial guestbook entries.
Matches the site's elegant serif typography and warm color palette.
"""

import io
import os
import logging
import textwrap
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, HRFlowable, KeepTogether, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
from reportlab.graphics import renderPDF

# ── Color Palette (matches site CSS variables) ────────────────────
CREAM = HexColor('#FAF9F6')
WARM_BEIGE = HexColor('#F5F5DC')
SAGE = HexColor('#B2BEB5')
SAGE_DARK = HexColor('#8a9a8d')
TERRACOTTA = HexColor('#D2691E')
DARK_BROWN = HexColor('#3E2723')
LIGHT_TAUPE = HexColor('#D4C5B9')
GOLD = HexColor('#C9A96E')
AMBER = HexColor('#E8A040')
SOFT_GOLD = HexColor('#F0E6D3')

# Entry type colors
ENTRY_COLORS = {
    'memory': GOLD,
    'condolence': SAGE,
    'prayer': TERRACOTTA,
    'candle': AMBER,
}

ENTRY_ICONS = {
    'memory': '\u2727',       # sparkle
    'condolence': '\u2661',   # heart outline
    'prayer': '\u2721',       # star of david
    'candle': '\u2736',       # six-pointed star
}

ENTRY_LABELS = {
    'memory': 'Shared Memory',
    'condolence': 'Condolence',
    'prayer': 'Prayer',
    'candle': 'Candle Lit',
}


def _build_styles():
    """Build all paragraph styles for the keepsake PDF."""
    styles = {}

    # Title — deceased name
    styles['title'] = ParagraphStyle(
        'KeepsakeTitle',
        fontName='Times-Bold',
        fontSize=28,
        leading=34,
        textColor=DARK_BROWN,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    # Hebrew name
    styles['hebrew'] = ParagraphStyle(
        'HebrewName',
        fontName='Times-Italic',
        fontSize=16,
        leading=20,
        textColor=SAGE_DARK,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    # Subtitle (dates, etc.)
    styles['subtitle'] = ParagraphStyle(
        'Subtitle',
        fontName='Times-Italic',
        fontSize=12,
        leading=16,
        textColor=SAGE_DARK,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    # Section heading
    styles['section_heading'] = ParagraphStyle(
        'SectionHeading',
        fontName='Times-Bold',
        fontSize=18,
        leading=24,
        textColor=DARK_BROWN,
        alignment=TA_CENTER,
        spaceBefore=16,
        spaceAfter=8,
    )

    # Entry author name
    styles['author'] = ParagraphStyle(
        'EntryAuthor',
        fontName='Times-Bold',
        fontSize=12,
        leading=16,
        textColor=DARK_BROWN,
    )

    # Entry type label
    styles['type_label'] = ParagraphStyle(
        'TypeLabel',
        fontName='Times-Italic',
        fontSize=9,
        leading=12,
        textColor=SAGE_DARK,
    )

    # Entry message body
    styles['message'] = ParagraphStyle(
        'EntryMessage',
        fontName='Times-Roman',
        fontSize=11,
        leading=16,
        textColor=DARK_BROWN,
        alignment=TA_LEFT,
        spaceBefore=4,
    )

    # Prayer text (italic, indented)
    styles['prayer'] = ParagraphStyle(
        'PrayerText',
        fontName='Times-Italic',
        fontSize=11,
        leading=16,
        textColor=TERRACOTTA,
        alignment=TA_CENTER,
        spaceBefore=4,
    )

    # Entry date/time
    styles['timestamp'] = ParagraphStyle(
        'Timestamp',
        fontName='Times-Italic',
        fontSize=9,
        leading=12,
        textColor=LIGHT_TAUPE,
        alignment=TA_RIGHT,
    )

    # Footer
    styles['footer'] = ParagraphStyle(
        'Footer',
        fontName='Times-Italic',
        fontSize=9,
        leading=12,
        textColor=SAGE_DARK,
        alignment=TA_CENTER,
    )

    # Entry count summary
    styles['summary'] = ParagraphStyle(
        'Summary',
        fontName='Times-Italic',
        fontSize=11,
        leading=15,
        textColor=SAGE_DARK,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=16,
    )

    # Obituary text
    styles['obituary_text'] = ParagraphStyle(
        'ObituaryText',
        fontName='Times-Roman',
        fontSize=10,
        leading=15,
        textColor=DARK_BROWN,
        alignment=TA_JUSTIFY,
        spaceBefore=8,
        spaceAfter=8,
    )

    return styles


def _gold_divider():
    """Create a gold horizontal rule divider matching site aesthetic."""
    return HRFlowable(
        width='40%',
        thickness=1.5,
        color=GOLD,
        spaceBefore=8,
        spaceAfter=8,
        hAlign='CENTER',
    )


def _taupe_divider():
    """Create a subtle taupe divider for between entries."""
    return HRFlowable(
        width='80%',
        thickness=0.5,
        color=LIGHT_TAUPE,
        spaceBefore=10,
        spaceAfter=10,
        hAlign='CENTER',
    )


def _format_date(iso_string):
    """Format an ISO date string to a readable format."""
    if not iso_string:
        return ''
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y')
    except (ValueError, AttributeError):
        return str(iso_string)


def _format_timestamp(iso_string):
    """Format a timestamp for entry display."""
    if not iso_string:
        return ''
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y at %I:%M %p')
    except (ValueError, AttributeError):
        return str(iso_string)


def _escape_html(text):
    """Escape text for use in reportlab Paragraph XML."""
    if not text:
        return ''
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    # Preserve line breaks
    text = text.replace('\n', '<br/>')
    return text


def _build_entry_block(entry, styles):
    """Build a KeepTogether block for a single guestbook entry."""
    elements = []
    entry_type = entry.get('entry_type', 'condolence')
    color = ENTRY_COLORS.get(entry_type, SAGE)
    label = ENTRY_LABELS.get(entry_type, 'Entry')
    icon = ENTRY_ICONS.get(entry_type, '')

    author = _escape_html(entry.get('author_name', 'Anonymous'))
    relationship = entry.get('relationship', '')
    message = _escape_html(entry.get('message', ''))
    prayer_text = _escape_html(entry.get('prayer_text', ''))
    timestamp = _format_timestamp(entry.get('created_at', ''))

    # Build a colored accent table for the entry
    # Left color bar + content
    color_hex = color.hexval() if hasattr(color, 'hexval') else str(color)

    # Type label with icon
    type_style = ParagraphStyle(
        'TypeLabelColored',
        parent=styles['type_label'],
        textColor=color,
    )
    elements.append(Paragraph(f'{icon} {label}', type_style))

    # Author + relationship
    author_text = f'<b>{author}</b>'
    if relationship:
        author_text += f'  <i>({_escape_html(relationship)})</i>'
    elements.append(Paragraph(author_text, styles['author']))

    # Message (if present)
    if message:
        elements.append(Paragraph(message, styles['message']))

    # Prayer text (if prayer entry)
    if prayer_text:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f'<i>"{prayer_text}"</i>', styles['prayer']))

    # Candle — decorative note
    if entry_type == 'candle' and not message:
        candle_style = ParagraphStyle(
            'CandleNote',
            parent=styles['message'],
            textColor=AMBER,
            alignment=TA_CENTER,
            fontName='Times-Italic',
        )
        elements.append(Paragraph('A candle was lit in their memory', candle_style))

    # Timestamp
    if timestamp:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(timestamp, styles['timestamp']))

    # Wrap in a table with a colored left border
    inner_content = []
    for el in elements:
        inner_content.append([el])

    inner_table = Table(inner_content, colWidths=[5.5 * inch])
    inner_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 4),
    ]))

    # Outer table with colored left bar
    bar_drawing = Drawing(4, 1)
    bar_drawing.add(Rect(0, 0, 4, 1, fillColor=color, strokeColor=None))

    outer_table = Table(
        [[bar_drawing, inner_table]],
        colWidths=[6, 5.6 * inch],
    )
    outer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('BACKGROUND', (0, 0), (0, -1), color),
        ('LINEAFTER', (0, 0), (0, -1), 3, color),
    ]))

    return KeepTogether([outer_table])


def _header_footer(canvas, doc, deceased_name=''):
    """Draw page header/footer on each page."""
    canvas.saveState()

    # Subtle cream page background
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)

    # Footer
    canvas.setFont('Times-Italic', 8)
    canvas.setFillColor(SAGE_DARK)
    canvas.drawCentredString(
        letter[0] / 2, 0.5 * inch,
        f'Guestbook Keepsake for {deceased_name}  \u2022  neshama.ca'
    )

    # Page number
    canvas.drawRightString(
        letter[0] - 0.75 * inch, 0.5 * inch,
        f'Page {doc.page}'
    )

    # Top decorative line
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, letter[1] - 0.6 * inch, letter[0] - 0.75 * inch, letter[1] - 0.6 * inch)

    # Bottom decorative line
    canvas.line(0.75 * inch, 0.7 * inch, letter[0] - 0.75 * inch, 0.7 * inch)

    canvas.restoreState()


def generate_keepsake_pdf(obituary_data, tributes_data):
    """
    Generate a keepsake PDF from obituary and guestbook data.

    Args:
        obituary_data: dict with obituary fields (deceased_name, hebrew_name, date_of_death,
                       obituary_text, photo_url, etc.)
        tributes_data: list of tribute dicts (author_name, message, entry_type, prayer_text,
                       created_at, relationship, etc.)

    Returns:
        bytes — the PDF file content
    """
    buffer = io.BytesIO()
    styles = _build_styles()

    deceased_name = obituary_data.get('deceased_name', 'Unknown')

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        title=f'Guestbook Keepsake - {deceased_name}',
        author='Neshama',
        subject=f'Memorial guestbook entries for {deceased_name}',
    )

    story = []

    # ── COVER / TITLE PAGE ────────────────────────────────────

    story.append(Spacer(1, 1.5 * inch))

    # Deceased name
    story.append(Paragraph(_escape_html(deceased_name), styles['title']))

    # Hebrew name
    hebrew_name = obituary_data.get('hebrew_name', '')
    if hebrew_name:
        story.append(Paragraph(_escape_html(hebrew_name), styles['hebrew']))

    story.append(_gold_divider())

    # Date of death
    date_of_death = obituary_data.get('date_of_death', '')
    if date_of_death:
        formatted_date = _format_date(date_of_death)
        story.append(Paragraph(f'Date of Passing: {formatted_date}', styles['subtitle']))

    # Yahrzeit
    yahrzeit = obituary_data.get('yahrzeit_date', '')
    if yahrzeit:
        story.append(Paragraph(f'Yahrzeit: {_escape_html(yahrzeit)}', styles['subtitle']))

    story.append(Spacer(1, 0.5 * inch))

    # Guestbook heading
    story.append(Paragraph('Guestbook Keepsake', styles['section_heading']))

    story.append(_gold_divider())

    # Entry summary
    total = len(tributes_data)
    if total > 0:
        counts = {}
        for t in tributes_data:
            et = t.get('entry_type', 'condolence')
            counts[et] = counts.get(et, 0) + 1

        parts = []
        if counts.get('memory', 0):
            n = counts['memory']
            parts.append(f'{n} {"memory" if n == 1 else "memories"}')
        if counts.get('condolence', 0):
            n = counts['condolence']
            parts.append(f'{n} {"condolence" if n == 1 else "condolences"}')
        if counts.get('prayer', 0):
            n = counts['prayer']
            parts.append(f'{n} {"prayer" if n == 1 else "prayers"}')
        if counts.get('candle', 0):
            n = counts['candle']
            parts.append(f'{n} {"candle" if n == 1 else "candles"} lit')

        summary_text = f'{total} guestbook {"entry" if total == 1 else "entries"}: {", ".join(parts)}'
        story.append(Paragraph(summary_text, styles['summary']))
    else:
        story.append(Paragraph('No guestbook entries yet.', styles['summary']))

    # Optional: brief obituary excerpt
    obit_text = obituary_data.get('obituary_text', '')
    if obit_text:
        # Include first ~500 chars as a brief excerpt
        excerpt = obit_text[:500]
        if len(obit_text) > 500:
            excerpt = excerpt.rsplit(' ', 1)[0] + '...'
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph('In Memoriam', styles['section_heading']))
        story.append(_gold_divider())
        story.append(Paragraph(_escape_html(excerpt), styles['obituary_text']))

    # ── GUESTBOOK ENTRIES ─────────────────────────────────────

    if total > 0:
        story.append(PageBreak())
        story.append(Paragraph('Guestbook Entries', styles['section_heading']))
        story.append(_gold_divider())
        story.append(Spacer(1, 0.2 * inch))

        # Sort entries: newest first (same as web)
        sorted_entries = sorted(
            tributes_data,
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )

        for i, entry in enumerate(sorted_entries):
            entry_block = _build_entry_block(entry, styles)
            story.append(entry_block)
            if i < len(sorted_entries) - 1:
                story.append(_taupe_divider())

    # ── CLOSING PAGE ──────────────────────────────────────────

    story.append(Spacer(1, 0.5 * inch))
    story.append(_gold_divider())

    closing_style = ParagraphStyle(
        'Closing',
        fontName='Times-Italic',
        fontSize=14,
        leading=20,
        textColor=SAGE_DARK,
        alignment=TA_CENTER,
        spaceBefore=20,
        spaceAfter=12,
    )
    story.append(Paragraph('May their memory be a blessing.', closing_style))

    story.append(Spacer(1, 0.3 * inch))

    generated_date = datetime.now().strftime('%B %d, %Y')
    story.append(Paragraph(
        f'Generated on {generated_date} via <a href="https://neshama.ca" color="#D2691E">neshama.ca</a>',
        styles['footer']
    ))

    # Build the PDF
    def on_page(canvas, doc):
        _header_footer(canvas, doc, deceased_name)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
