#!/usr/bin/env python3
"""
Placeholder detection and fragment collapsing for scraped obituary fields.

Why this exists
---------------
Funeral home pages label their sections. When a scraper grabs the label instead
of the value, the label gets stored as if it were data and then rendered into a
grieving family's email. Measured on production, 2026-09-02, 1,270 public rows:

    shiva_info == "Shiva Location"        281 rows   (all Steeles)
    shiva_info == "Shiva Details"           4 rows   (all Steeles)
    burial_location == "Dawes Road Cemetery"
                                          348 rows   (ALL 348 Steeles rows)

That last one is not a coincidence and not scraped truth. Steeles' navigation
menu carries <a href="/cemetery/dawes-road-cemetery/">Dawes Road Cemetery</a>,
and the scraper's soup.find(text=/Cemetery/) matches that nav link before it ever
reaches the real "Burial Service Location" block. Every Steeles obituary
inherited the same burial location from the site chrome.

Two layers use this module, deliberately:

  1. The scrapers, so junk is never stored (steeles_scraper also got a
     structural fix so it reads the right node in the first place).
  2. The renderers, so the 633 rows that ALREADY carry junk stop printing it
     without waiting for a data migration.

Omitting a line always beats printing a placeholder. A missing "Shiva:" line
reads as "not announced yet", which is true. "Shiva: Shiva Location" reads as a
broken website.
"""

import re


# Values that are section labels, form scaffolding, or explicit non-answers.
# Matched against the whole trimmed value, case-insensitively, after stripping
# trailing punctuation. Substring matching is deliberately NOT used: a real
# shiva_info that happens to contain the words "shiva location" is still real.
_PLACEHOLDER_EXACT = {
    'shiva location',
    'shiva locations',
    'shiva details',
    'shiva detail',
    'shiva information',
    'shiva info',
    'shiva',
    'shiva address',
    'shiva hours',
    'shiva times',
    'burial',
    'burial location',
    'burial service location',
    'cemetery',
    'funeral',
    'funeral location',
    'funeral service',
    'memorial service location',
    'service location',
    'location',
    'address',
    'details',
    'detail',
    'information',
    'info',
    'tbd',
    'tba',
    'n/a',
    'na',
    'none',
    'null',
    'unknown',
    'pending',
    'not available',
    'to be announced',
    'to be determined',
    'to follow',
    'details to follow',
    'shiva details to follow',
    'shiva to follow',
    'details will follow',
    'more details to follow',
    'information to follow',
    'private',
    '-',
    '--',
    ',',
    ';',
    ':',
}

# Composed values that are nothing but a field label and an empty non-answer,
# e.g. "Address: Shiva details to follow" or "Shiva: details to follow".
_LABELLED_EMPTY_RE = re.compile(
    r'^\s*(?:shiva|burial|funeral|address|location|dates?|hours?|details?)\s*:?\s*'
    r'(?:shiva\s+)?(?:details?|information|info)?\s*'
    r'(?:will\s+|to\s+)?follow[\s.]*$',
    re.IGNORECASE,
)

_STRIP_EDGES = ' \t\r\n.,;:|-'


def is_placeholder(value):
    """True when a scraped value carries no information and must not be shown."""
    if value is None:
        return True
    text = str(value).replace('​', '').strip()
    if not text:
        return True

    bare = text.strip(_STRIP_EDGES).strip().lower()
    bare = re.sub(r'\s+', ' ', bare)
    if not bare:
        return True
    if bare in _PLACEHOLDER_EXACT:
        return True
    if _LABELLED_EMPTY_RE.match(text):
        return True
    return False


def collapse_duplicate_fragments(value, separator=';'):
    """Collapse repeated semicolon-separated fragments: "X; X" -> "X".

    Also drops fragments that are placeholders in their own right, which is what
    produced "Shiva: Address: Shiva details to follow; Shiva details to follow"
    in the 2026-08-31 digest: the shiva parser composed a summary out of parts
    that were each themselves a non-answer.

    Comparison is case- and punctuation-insensitive; the first spelling wins.
    """
    if value is None:
        return None
    text = str(value).strip()
    if separator not in text:
        return text or None

    kept, seen = [], set()
    for raw in text.split(separator):
        fragment = raw.strip()
        if not fragment:
            continue
        # "Address: Shiva details to follow" -> drop, the label carries nothing.
        without_label = re.sub(
            r'^\s*(?:shiva|burial|funeral|address|location|dates?|hours?)\s*:\s*',
            '', fragment, flags=re.IGNORECASE)
        if is_placeholder(fragment) or is_placeholder(without_label):
            continue
        signature = re.sub(r'[^\w\s]', '', without_label).strip().lower()
        signature = re.sub(r'\s+', ' ', signature)
        if signature in seen:
            continue
        seen.add(signature)
        kept.append(fragment)

    if not kept:
        return None
    return (separator + ' ').join(kept)


def clean_field(value):
    """Normalize one scraped field for storage. Returns None for junk.

    Store NULL rather than a placeholder string: a NULL is honestly absent and
    every reader already handles it, whereas a placeholder has to be recognised
    again at every render site.
    """
    if is_placeholder(value):
        return None
    collapsed = collapse_duplicate_fragments(value)
    if collapsed is None or is_placeholder(collapsed):
        return None
    return collapsed


def display_value(value):
    """What a renderer should show, or None to omit the line entirely."""
    return clean_field(value)


# Fields that carry funeral-home free text and can therefore carry a label
# instead of a value. deceased_name is deliberately absent: a name is never
# suppressed, whatever it looks like.
SCRUBBED_FIELDS = (
    'shiva_info',
    'shiva_address',
    'shiva_hours',
    'shiva_concludes',
    'shiva_raw',
    'burial_location',
    'funeral_location',
)


def scrub_obituary_row(row):
    """Null out placeholder values on one obituary dict, in place, and return it.

    Applied at the API serialization layer so the website, the memorial pages
    and any other consumer all get the same clean view without each having to
    reimplement the rules. This is a READ-time fix: it stops the 633 rows that
    already carry junk from displaying it, without waiting on a data migration.
    """
    if not isinstance(row, dict):
        return row
    for field in SCRUBBED_FIELDS:
        if field in row:
            row[field] = clean_field(row[field])
    return row
