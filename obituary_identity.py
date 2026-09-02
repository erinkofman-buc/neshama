#!/usr/bin/env python3
"""
Stable obituary identity.

Why this module exists
----------------------
The original identity was md5(source + deceased_name + date_of_death). Both of
those inputs are *late-arriving*: funeral homes publish a preliminary listing and
then fill in detail hours later. When a field changed, the hash changed, and the
re-scrape INSERTed a second row instead of UPDATEing the first. The daily digest
then announced the same person twice.

Confirmed against production data on 2026-09-02 (1,270 public rows):

  * 65 source_urls carry more than one row.
  * In 65/65 of those groups the deceased_name differs
    (e.g. "Jerry Gold" -> 'Gerald "Jerry" Gold', "Ray Mendell" -> "Raymond Mendell").
  * In only 5/65 does date_of_death differ.
  * 0 groups share a (source, normalized_name) pair.

So the dominant driver is the *name*, not the date - but both are mutable, and
the fix is the same: stop hashing mutable content into the identity.

The funeral home already assigns every obituary a permanent identifier in its
URL. That is the identity we key on:

    Steeles     https://steelesmemorialchapel.com/condolence/<slug>/
    Benjamin's  https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=<n>&fg=0
    Misaskim    https://misaskim.ca/shiva-listings/<slug>/
    Paperman    https://www.paperman.com/funerals/<Name-Slug>-<8-hex>

Two different people at the same funeral home are distinguished because the home
gives them different URLs - which is strictly better than any name-plus-time-window
rule, and it is the case the old key handled worst.

This module never touches the database. `database_setup.upsert_obituary` owns the
lookup order; see `docs/` and the sprint note in decisions-log.md.
"""

import re
from urllib.parse import urlsplit, parse_qs


# Funeral homes whose URL shape we understand well enough to extract a permanent
# id from. Anything not listed falls through to _normalize_url().
_STEELES_RE = re.compile(r'/condolence/([^/?#]+)', re.IGNORECASE)
_MISASKIM_RE = re.compile(r'/shiva-listings/([^/?#]+)', re.IGNORECASE)
_PAPERMAN_RE = re.compile(r'/funerals/.*?-([0-9a-f]{8})/?$', re.IGNORECASE)


def _normalize_url(url):
    """Scheme/host/case/trailing-slash-insensitive form of a URL.

    Used as the generic fallback key. Keeps the query string but drops the
    cosmetic 'fg' parameter Benjamin's appends, so ?snum=1&fg=0 and ?snum=1
    are the same obituary.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None

    host = (parts.netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]

    path = (parts.path or '').rstrip('/').lower()

    query = ''
    if parts.query:
        params = parse_qs(parts.query, keep_blank_values=False)
        params.pop('fg', None)
        if params:
            query = '?' + '&'.join(
                f'{k.lower()}={sorted(v)[0].lower()}'
                for k, v in sorted(params.items())
            )

    if not host and not path:
        return None
    return f'{host}{path}{query}'


def source_key(source, source_url):
    """Return a stable, funeral-home-assigned key for one obituary.

    Returns None when there is no usable URL - the caller must then fall back to
    the legacy name+date hash rather than guessing.
    """
    if not source_url or not str(source_url).strip():
        return None

    url = str(source_url).strip()
    src = (source or '').strip().lower()

    # Benjamin's: the snum query parameter is the permanent service number.
    if 'benjamin' in src or 'benjaminsparkmemorialchapel' in url.lower():
        m = re.search(r'[?&]snum=(\d+)', url, re.IGNORECASE)
        if m:
            return f'benjamins:{m.group(1)}'

    # Paperman: trailing 8-hex id. The slug before it embeds the name and does
    # change when the name is corrected, so we deliberately keep only the hex.
    if 'paperman' in src or 'paperman.com' in url.lower():
        m = _PAPERMAN_RE.search(url)
        if m:
            return f'paperman:{m.group(1).lower()}'

    if 'steeles' in src or 'steelesmemorialchapel' in url.lower():
        m = _STEELES_RE.search(url)
        if m:
            return f'steeles:{m.group(1).lower()}'

    if 'misaskim' in src or 'misaskim.ca' in url.lower():
        m = _MISASKIM_RE.search(url)
        if m:
            return f'misaskim:{m.group(1).lower()}'

    normalized = _normalize_url(url)
    return f'url:{normalized}' if normalized else None


def announce_key(source, source_url, obituary_id):
    """Key the digest sent-log on.

    Deliberately the *person*, not the row: if a key bug ever does mint a second
    row for someone, the sent-log still refuses to announce them twice. Falls
    back to the row id only when there is no usable URL.
    """
    key = source_key(source, source_url)
    if key:
        return key
    return f'id:{obituary_id}'


# ── name comparison, used only as a safety guard ──────────────────────────────

_TITLE_RE = re.compile(r'^(dr|rabbi|rev|cantor|mr|mrs|ms|hon)\.?\s+', re.IGNORECASE)


def normalize_name(name):
    """Normalize a name for *comparison only*. Never used to build an identity."""
    if not name:
        return ''
    import unicodedata
    n = ''.join(c for c in str(name) if unicodedata.category(c) != 'Cf')
    n = re.sub(r'\s*\([^)]*\)', '', n)          # "(Jerry)", "(née Smith)"
    n = re.sub(r'\s*"[^"]*"', '', n)            # 'Gerald "Jerry" Gold'
    n = re.sub(r'\s*ז[״״"]ל\s*', '', n)   # ז״ל
    n = _TITLE_RE.sub('', n)
    n = re.sub(r'[^\w\s]', ' ', n)
    return re.sub(r'\s+', ' ', n).strip().lower()


def names_look_unrelated(a, b):
    """True when two names for the same source_key look nothing alike.

    ADVISORY ONLY - this never changes the upsert decision. It exists so a
    funeral home reusing a URL for a different person would show up in the logs
    instead of silently overwriting a record.

    It is deliberately not a gate. That was the first design, and production data
    killed it: of the 74 source_keys carrying more than one row on 2026-09-02, a
    name-divergence gate rejected 10 - and inspection showed all 10 are the same
    person renamed by the funeral home:

        Yosi Derman        -> Jonathan Derman          (Hebrew / English)
        Zippe Blitstein    -> Sandra Blitstein         (Hebrew / English)
        Tony Belchetz      -> Anthony BELCHETZ         (diminutive / legal)
        Gerald "Jerry" Gold-> Jerry Gold               (nickname)
        Simon Chouchan     -> Simon Chauchan           (typo correction)
        ... and 5 more of the same shapes

    Gating on the name would therefore *preserve* 10 duplicates in order to guard
    against a case that does not occur in 1,270 rows. The URL is what the funeral
    home treats as the record identity, so we trust it and log the divergence.
    """
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb or na == nb:
        return False

    ta, tb = set(na.split()), set(nb.split())
    if ta & tb:
        return False         # any shared token (usually the surname) - related
    return True
