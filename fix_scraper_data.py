#!/usr/bin/env python3
"""
One-time cleanup: fix Steeles photos + obituary text, NULL Benjamin's candle
placeholders, and recalculate content_hash for ALL records (prevents mass-update
storm from hash formula change).

SAFE: Does NOT change obituary IDs. Does NOT bump last_updated.

Usage:
    python fix_scraper_data.py --db /data/neshama.db          # dry run
    python fix_scraper_data.py --db /data/neshama.db --apply  # apply changes
"""

import argparse
import hashlib
import logging
import os
import re
import sqlite3
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

PHOTO_EXCLUSION_RE = re.compile(
    r'logo|icon|badge|star|bao|bereavement|\.svg|data:image|placeholder|banner',
    re.IGNORECASE
)

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
})


def clean_text(text):
    """Clean and normalize text."""
    if not text:
        return None
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\S+@\S+\.\S+', '[email]', text)
    return text if text else None


def generate_content_hash(row):
    """Generate content hash matching the NEW formula in database_setup.py (with photo_url)."""
    content = f"{row.get('deceased_name', '') or ''}_" \
              f"{row.get('funeral_datetime', '') or ''}_" \
              f"{row.get('shiva_info', '') or ''}_" \
              f"{row.get('livestream_url', '') or ''}_" \
              f"{row.get('photo_url', '') or ''}"
    return hashlib.md5(content.encode()).hexdigest()


def extract_steeles_photo(soup):
    """Extract photo URL from Steeles background-image CSS."""
    photo_div = soup.find('div', class_='description-photo')
    if not photo_div:
        return None
    fig = photo_div.find(style=re.compile(r'background-image'))
    if not fig:
        return None
    style = fig.get('style', '')
    bg_match = re.search(
        r'background-image:\s*url\(\s*["\']?([^"\')\s]+)["\']?\s*\)', style
    )
    if not bg_match:
        return None
    url = bg_match.group(1)
    if PHOTO_EXCLUSION_RE.search(url):
        return None
    if not url.startswith('http'):
        url = 'https://steelesmemorialchapel.com' + url
    return url


def extract_steeles_text(soup):
    """Extract full obituary text from Steeles post-content div."""
    post_content = soup.find('div', class_='post-content')
    if not post_content:
        return None
    paragraphs = [clean_text(p.get_text()) for p in post_content.find_all('p')]
    text = '\n\n'.join(p for p in paragraphs if p)
    return text if text else None


def fix_steeles(cursor, apply=False):
    """Fix Steeles photo URLs and obituary text by fetching source pages."""
    cursor.execute('''
        SELECT id, deceased_name, source_url, photo_url, obituary_text
        FROM obituaries
        WHERE source = 'Steeles Memorial Chapel'
    ''')
    rows = cursor.fetchall()
    logging.info(f"Found {len(rows)} Steeles records")

    fixed_photo = 0
    fixed_text = 0

    for obit_id, name, source_url, old_photo, old_text in rows:
        if not source_url:
            logging.info(f"  SKIP: {name} — no source URL")
            continue

        try:
            resp = SESSION.get(source_url, timeout=15)
            if resp.status_code == 404:
                if old_photo:
                    logging.info(f"  404:  {name} — page gone, NULLing photo_url (was: {old_photo[:80]})")
                    if apply:
                        cursor.execute('UPDATE obituaries SET photo_url = NULL WHERE id = ?', (obit_id,))
                    fixed_photo += 1
                else:
                    logging.info(f"  404:  {name} — page gone, no photo to fix")
                continue
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.info(f"  ERROR: {name} — {e}")
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Fix photo
        new_photo = extract_steeles_photo(soup)
        if new_photo != old_photo:
            old_display = (old_photo or 'NULL')[:80]
            new_display = (new_photo or 'NULL')[:80]
            logging.info(f"  PHOTO: {name} — {old_display} → {new_display}")
            if apply:
                cursor.execute('UPDATE obituaries SET photo_url = ? WHERE id = ?', (new_photo, obit_id))
            fixed_photo += 1

        # Fix obituary text
        new_text = extract_steeles_text(soup)
        if new_text and new_text != old_text:
            old_len = len(old_text) if old_text else 0
            new_len = len(new_text)
            logging.info(f"  TEXT:  {name} — {old_len} chars → {new_len} chars")
            if apply:
                cursor.execute('UPDATE obituaries SET obituary_text = ? WHERE id = ?', (new_text, obit_id))
            fixed_text += 1

        time.sleep(1)  # Be polite to Steeles server

    logging.info(f"Steeles: {fixed_photo} photos fixed, {fixed_text} texts fixed")
    return fixed_photo, fixed_text


def fix_benjamins_candle(cursor, apply=False):
    """NULL out Benjamin's Candle-big.jpg placeholder photos."""
    cursor.execute('''
        SELECT id, deceased_name, photo_url
        FROM obituaries
        WHERE source = "Benjamin's Park Memorial Chapel"
          AND photo_url IS NOT NULL
          AND LOWER(photo_url) LIKE '%candle-big.jpg%'
    ''')
    rows = cursor.fetchall()
    logging.info(f"Found {len(rows)} Benjamin's records with candle placeholder")

    for obit_id, name, old_photo in rows:
        logging.info(f"  NULL:  {name} — was: {old_photo[:80]}")
        if apply:
            cursor.execute('UPDATE obituaries SET photo_url = NULL WHERE id = ?', (obit_id,))

    return len(rows)


def verify_shiva_links(cursor, apply=False):
    """Check and fix shiva-to-obituary links. Reconnect Lipman, verify Ferne Kappy."""

    # Find all shiva pages and their linked obituaries
    cursor.execute('''
        SELECT s.id, s.family_name, s.obituary_id, s.status,
               o.deceased_name AS obit_name
        FROM shiva_support s
        LEFT JOIN obituaries o ON o.id = s.obituary_id
    ''')
    shivas = cursor.fetchall()
    logging.info(f"Found {len(shivas)} shiva pages")

    for shiva_id, family, obit_id, status, obit_name in shivas:
        linked = "LINKED" if obit_name else "DISCONNECTED"
        logging.info(f"  {family or 'unnamed'} ({status}): {linked}"
                     f"{' → ' + obit_name if obit_name else ''}"
                     f"  [shiva={shiva_id[:12]}, obit={obit_id[:12] if obit_id else 'NONE'}]")

    # Find Lipman shiva — search by family name
    cursor.execute('''
        SELECT s.id, s.obituary_id FROM shiva_support s
        WHERE LOWER(s.family_name) LIKE '%lipman%'
    ''')
    lipman_shiva = cursor.fetchall()

    if lipman_shiva:
        for shiva_id, current_obit in lipman_shiva:
            # Find the Lipman obituary
            cursor.execute('''
                SELECT id, deceased_name, source FROM obituaries
                WHERE LOWER(deceased_name) LIKE '%lipman%'
            ''')
            lipman_obits = cursor.fetchall()

            if lipman_obits:
                # Show what we found
                for obit_id, obit_name, source in lipman_obits:
                    logging.info(f"  LIPMAN MATCH: obit '{obit_name}' ({source}) id={obit_id[:16]}")

                if len(lipman_obits) == 1:
                    correct_obit_id = lipman_obits[0][0]
                    if current_obit != correct_obit_id:
                        logging.info(f"  RECONNECT: Lipman shiva {shiva_id[:12]} → obit {correct_obit_id[:16]}")
                        if apply:
                            cursor.execute(
                                'UPDATE shiva_support SET obituary_id = ? WHERE id = ?',
                                (correct_obit_id, shiva_id)
                            )
                    else:
                        logging.info(f"  Lipman shiva already correctly linked")
                else:
                    logging.info(f"  MANUAL: Multiple Lipman obituaries found — needs manual selection")
            else:
                logging.info(f"  WARNING: Lipman shiva exists but no Lipman obituary found")

    # Verify Ferne Kappy link
    cursor.execute('''
        SELECT s.id, s.family_name, s.obituary_id, o.deceased_name
        FROM shiva_support s
        LEFT JOIN obituaries o ON o.id = s.obituary_id
        WHERE LOWER(s.family_name) LIKE '%kappy%'
    ''')
    kappy_shivas = cursor.fetchall()
    if kappy_shivas:
        for shiva_id, family, obit_id, obit_name in kappy_shivas:
            if obit_name:
                logging.info(f"  KAPPY OK: shiva '{family}' linked to '{obit_name}'")
            else:
                logging.info(f"  KAPPY BROKEN: shiva '{family}' has no linked obituary!")
    else:
        logging.info(f"  No Kappy shiva found")


def recalculate_all_hashes(cursor, apply=False):
    """Recalculate content_hash for ALL records using new formula (with photo_url).
    Does NOT touch last_updated — prevents mass-update storm on next scraper run."""
    cursor.execute('''
        SELECT id, deceased_name, funeral_datetime, shiva_info,
               livestream_url, photo_url, content_hash, source
        FROM obituaries
    ''')
    rows = cursor.fetchall()
    logging.info(f"Recalculating content_hash for {len(rows)} records")

    changed = 0
    for obit_id, name, funeral_dt, shiva_info, livestream, photo, old_hash, source in rows:
        row_data = {
            'deceased_name': name or '',
            'funeral_datetime': funeral_dt or '',
            'shiva_info': shiva_info or '',
            'livestream_url': livestream or '',
            'photo_url': photo or '',
        }
        new_hash = generate_content_hash(row_data)
        if new_hash != old_hash:
            if changed < 20:  # Only log first 20 to avoid flooding
                logging.info(f"  HASH:  {name} ({source}) — {old_hash[:12]} → {new_hash[:12]}")
            elif changed == 20:
                logging.info(f"  ... (suppressing further hash change logs)")
            if apply:
                cursor.execute(
                    'UPDATE obituaries SET content_hash = ? WHERE id = ?',
                    (new_hash, obit_id)
                )
            changed += 1

    logging.info(f"Content hash: {changed} records updated out of {len(rows)} total")
    return changed


def run(db_path, apply=False):
    """Run all fixes."""
    if not os.path.exists(db_path):
        logging.error(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    mode = "APPLY" if apply else "DRY RUN"
    logging.info(f"{'=' * 60}")
    logging.info(f"SCRAPER DATA FIX — {mode}")
    logging.info(f"Database: {db_path}")
    logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"{'=' * 60}")

    # Step 1: Fix Steeles photos + text
    logging.info(f"\n--- Step 1: Fix Steeles photos + text ---")
    steeles_photos, steeles_texts = fix_steeles(cursor, apply)

    # Step 2: Fix Benjamin's candle placeholders
    logging.info(f"\n--- Step 2: Fix Benjamin's candle placeholders ---")
    benjamins_fixed = fix_benjamins_candle(cursor, apply)

    # Step 3: Verify and fix shiva links (Lipman reconnect, Kappy verify)
    logging.info(f"\n--- Step 3: Verify shiva links ---")
    verify_shiva_links(cursor, apply)

    # Step 4: Recalculate ALL content hashes (prevents mass-update storm)
    logging.info(f"\n--- Step 4: Recalculate content hashes ---")
    hashes_fixed = recalculate_all_hashes(cursor, apply)

    if apply:
        conn.commit()
        logging.info(f"\nCOMMITTED all changes")
    else:
        logging.info(f"\nDRY RUN — no changes written. Run with --apply to execute.")

    logging.info(f"\n{'=' * 60}")
    logging.info(f"SUMMARY")
    logging.info(f"  Steeles photos fixed:      {steeles_photos}")
    logging.info(f"  Steeles texts fixed:        {steeles_texts}")
    logging.info(f"  Benjamin's candles NULLed:  {benjamins_fixed}")
    logging.info(f"  Content hashes recalculated: {hashes_fixed}")
    logging.info(f"{'=' * 60}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='One-time scraper data fix: Steeles photos + text, Benjamin\'s candle, content hashes'
    )
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry run)')
    parser.add_argument(
        '--db', type=str,
        default=os.environ.get('DATABASE_PATH', 'neshama.db'),
        help='Path to neshama.db'
    )
    args = parser.parse_args()
    run(args.db, apply=args.apply)


if __name__ == '__main__':
    main()
