#!/usr/bin/env python3
"""
One-time backfill: extract date_of_death from existing obituary_text
for Steeles Memorial Chapel records where date_of_death is NULL.

SAFE: Only updates date_of_death. Does NOT touch content_hash or last_updated.
Logs every change for auditability.

Usage:
    python backfill_steeles_dates.py              # dry run (default)
    python backfill_steeles_dates.py --apply       # actually update DB
"""

import argparse
import logging
import os
import re
import sqlite3
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Same regex patterns used by steeles_scraper.py
DEATH_DATE_PATTERNS = [
    re.compile(r'passed away.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
    re.compile(r'died.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
    re.compile(r'peacefully.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
]


def extract_death_date(obituary_text):
    """Extract date of death from obituary text using contextual regex patterns."""
    if not obituary_text:
        return None
    for pattern in DEATH_DATE_PATTERNS:
        match = pattern.search(obituary_text)
        if match:
            return match.group(1)
    return None


def run_backfill(db_path, apply=False):
    """Find Steeles records with NULL date_of_death and extract from obituary_text."""
    if not os.path.exists(db_path):
        logging.error(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    # Find Steeles records where date_of_death is NULL but obituary_text exists
    cursor.execute('''
        SELECT id, deceased_name, obituary_text
        FROM obituaries
        WHERE source = 'Steeles Memorial Chapel'
          AND (date_of_death IS NULL OR date_of_death = '')
          AND obituary_text IS NOT NULL
          AND obituary_text != ''
    ''')

    rows = cursor.fetchall()
    logging.info(f"Found {len(rows)} Steeles records with NULL date_of_death and non-NULL obituary_text")

    updated = 0
    skipped = 0

    for obit_id, name, obit_text in rows:
        extracted_date = extract_death_date(obit_text)
        if extracted_date:
            logging.info(f"  MATCH: {name} -> date_of_death = '{extracted_date}'")
            if apply:
                # Update ONLY date_of_death -- do NOT touch content_hash or last_updated
                cursor.execute(
                    'UPDATE obituaries SET date_of_death = ? WHERE id = ?',
                    (extracted_date, obit_id)
                )
            updated += 1
        else:
            logging.info(f"  SKIP:  {name} -> no date pattern found in obituary text")
            skipped += 1

    if apply:
        conn.commit()
        logging.info(f"\nAPPLIED: {updated} records updated, {skipped} skipped (no date found)")
    else:
        logging.info(f"\nDRY RUN: {updated} would be updated, {skipped} skipped (no date found)")
        logging.info("Run with --apply to actually update the database")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Backfill date_of_death for Steeles obituaries from existing obituary_text'
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='Actually update the database (default is dry run)'
    )
    parser.add_argument(
        '--db', type=str,
        default=os.environ.get('DATABASE_PATH', 'neshama.db'),
        help='Path to neshama.db (default: DATABASE_PATH env var or neshama.db)'
    )
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    logging.info(f"{'=' * 60}")
    logging.info(f"STEELES DATE BACKFILL — {mode}")
    logging.info(f"Database: {args.db}")
    logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"{'=' * 60}")

    run_backfill(args.db, apply=args.apply)

    logging.info(f"{'=' * 60}")


if __name__ == '__main__':
    main()
