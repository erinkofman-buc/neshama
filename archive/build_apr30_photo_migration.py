"""Build apply-photo-bundle-apr30.sql from vendor-photo-picks-2026-04-30.csv.

Maps CSV picks to seed slugs, remaps 3 names that exported under their
pre-fix truncated forms (Apr 30 AM apostrophe/circumflex restoration).
Outputs a single transactional SQL file matching the Apr 21 pattern.
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, '/Users/erinkofman/Desktop/Neshama')
from seed_vendors import VENDORS, MONTREAL_VENDORS, GIFT_VENDORS, slugify

CSV_PATH = '/Users/erinkofman/Desktop/Tax 2025/vendor-photo-picks-2026-04-30.csv'
OUT_PATH = '/Users/erinkofman/Desktop/Neshama/archive/apply-photo-bundle-apr30.sql'

# CSV exported with localStorage keys captured before the Apr 30 AM JSON fix
# restored truncated names. Map old → new before slugifying.
NAME_REMAP = {
    'Baskets n': "Baskets n' Stuf",
    'Ely': "Ely's Fine Foods Gift Baskets",
    'Romi': "Romi's Bakery",
    'Rotisserie Laurier': "Rôtisserie Laurier",
}

seed = {v['name']: v for v in VENDORS + MONTREAL_VENDORS + GIFT_VENDORS}
seed_slug_to_name = {slugify(n): n for n in seed}

picks_url, picks_none, unreviewed, errors = [], [], [], []

with open(CSV_PATH) as f:
    for row in csv.DictReader(f):
        raw_name = row['Vendor Name']
        choice = row['Choice'].strip()
        url = row['Picked URL'].strip()
        canonical = NAME_REMAP.get(raw_name, raw_name)
        slug = slugify(canonical)
        if not choice:
            unreviewed.append(canonical)
            continue
        if slug not in seed_slug_to_name:
            errors.append((raw_name, canonical, slug, choice))
            continue
        if choice == 'NEEDS NEW SOURCE':
            picks_none.append((canonical, slug))
        else:
            picks_url.append((canonical, slug, url))


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


lines = [
    "-- Neshama photo audit Cycle 3 migration — Apr 30, 2026",
    "-- Run on Render shell AFTER merging the Apr 30 evening deploy.",
    "-- Source: vendor-photo-picks-2026-04-30.csv (Erin's picks via review.html)",
    "--",
    f"-- Scope: {len(picks_url)} image_url UPDATEs, {len(picks_none)} clears (→ cream placeholder)",
    "",
    "BEGIN TRANSACTION;",
    "",
    "SELECT 'vendors before' AS label, COUNT(*) AS n FROM vendors;",
    "SELECT 'with image before' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';",
    "",
    "-- === Picks: set image_url ===",
]
for canonical, slug, url in picks_url:
    lines.append(
        f"UPDATE vendors SET image_url = '{sql_escape(url)}' "
        f"WHERE slug = '{sql_escape(slug)}';  -- {sql_escape(canonical)}"
    )

lines += ["", "-- === Picks: clear image_url (cream placeholder) ==="]
for canonical, slug in picks_none:
    lines.append(
        f"UPDATE vendors SET image_url = NULL "
        f"WHERE slug = '{sql_escape(slug)}';  -- {sql_escape(canonical)} (NEEDS NEW SOURCE)"
    )

lines += [
    "",
    "SELECT 'vendors after' AS label, COUNT(*) AS n FROM vendors;",
    "SELECT 'with image after' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url != '';",
    "",
    "COMMIT;",
    "",
]

Path(OUT_PATH).write_text('\n'.join(lines) + '\n')

print(f'Wrote: {OUT_PATH}')
print(f'  UPDATE image_url:   {len(picks_url)}')
print(f'  Clear image_url:    {len(picks_none)}')
print(f'  Unreviewed (skip):  {len(unreviewed)}  → {unreviewed}')
print(f'  Slug mismatches:    {len(errors)}')
for raw, canonical, slug, choice in errors:
    print(f'    csv={raw!r}  →  canonical={canonical!r}  slug={slug!r}  ({choice})')
