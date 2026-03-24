#!/usr/bin/env python3
"""
Neshama Vendor Pipeline — Step 2: Clean & Consolidate
Takes raw Outscraper CSVs, removes junk, flags edge cases, deduplicates against existing vendors.

Usage:
    python step2_clean.py --input data/step1_raw_shiva_toronto_20260309.csv
    python step2_clean.py --input data/step1_raw_*.csv   (multiple files)
"""

import argparse
import csv
import glob
import os
import re
import sqlite3
import sys
from datetime import datetime

# Add parent directory to path for city_config import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from city_config import CITIES


# ── Removal criteria ──

BIG_BOX = {
    'walmart', 'loblaws', 'costco', 'no frills', 'metro', 'sobeys',
    'food basics', 'freshco', 'real canadian superstore', 't&t supermarket',
    'shoppers drug mart', 'dollarama', 'canadian tire',
}

CHAINS_NO_JEWISH = {
    'swiss chalet', 'boston pizza', 'tim hortons', 'mcdonalds', "mcdonald's",
    'subway', 'burger king', 'wendys', "wendy's", 'popeyes', "popeye's",
    'pizza hut', 'dominos', "domino's", 'kfc', 'taco bell', 'starbucks',
    'a&w', 'harvey', 'mary brown', 'new york fries', 'the keg',
    'east side mario', 'jack astor', 'montana', 'milestones', 'cactus club',
    'earls', 'joeys', "joey's", 'the rec room', 'denny',
}

NOT_VENDORS = {
    'funeral home', 'chapel', 'cemetery', 'synagogue', 'shul', 'temple',
    'community centre', 'community center', 'jcc', 'chabad',
    'hospital', 'clinic', 'pharmacy', 'school',
}

NON_KOSHER_SIGNALS = {'pork', 'shellfish', 'lobster', 'crab', 'bacon', 'ham'}


def is_big_box(name):
    name_lower = name.lower().strip()
    return any(bb in name_lower for bb in BIG_BOX)


def is_chain_no_jewish(name):
    name_lower = name.lower().strip()
    return any(ch in name_lower for ch in CHAINS_NO_JEWISH)


def is_not_vendor(name, btype=''):
    combined = f"{name} {btype}".lower()
    return any(nv in combined for nv in NOT_VENDORS)


def is_valid_address(address, city):
    """Check if address looks complete enough."""
    if not address or len(address) < 10:
        return False
    if not city:
        return False
    return True


def is_in_service_area(city, state):
    """Check if business is in any Neshama service area (uses city_config detection_keywords).

    Supports all cities defined in city_config.py, including commented-out expansion cities.
    Also includes hardcoded fallback lists for expansion cities not yet in CITIES dict.
    """
    if not city and not state:
        return False
    combined = f"{city} {state}".lower()

    # Build detection keywords from city_config (active cities)
    all_detection_keywords = []
    for slug, cfg in CITIES.items():
        all_detection_keywords.extend(cfg['detection_keywords'])

    # Expansion city keywords (ready for when they activate in city_config)
    expansion_keywords = {
        'south-florida': [
            'boca raton', 'aventura', 'fort lauderdale', 'hollywood, fl',
            'miami beach', 'sunny isles', 'surfside', 'bal harbour',
            'deerfield beach', 'delray beach', 'parkland', 'weston',
            'coral springs', 'tamarac', 'boynton beach', 'north miami beach',
            'palm beach', 'pompano beach', 'davie', ', fl',
        ],
        'chicago': [
            'skokie', 'highland park, il', 'deerfield, il', 'northbrook',
            'buffalo grove', 'glencoe', 'wilmette', 'winnetka',
            'lakeview', 'lincoln park', 'west rogers park', 'chicago', ', il',
        ],
        'nyc': [
            'new york', 'manhattan', 'brooklyn', 'queens', 'bronx',
            'long island', 'great neck', 'five towns', 'hewlett',
            'teaneck', 'forest hills', 'borough park', 'flatbush',
            'scarsdale', 'white plains', ', ny', ', nj',
        ],
        'la': [
            'los angeles', 'beverly hills', 'pico-robertson', 'encino',
            'tarzana', 'calabasas', 'culver city', 'santa monica',
            'brentwood', 'hollywood', 'westwood', ', ca',
        ],
    }
    # Only add expansion keywords if not already in CITIES (avoids duplicates)
    for slug, keywords in expansion_keywords.items():
        if slug not in CITIES:
            all_detection_keywords.extend(keywords)

    return any(area in combined for area in all_detection_keywords)


def load_existing_vendors(db_path=None):
    """Load existing vendor names for dedup."""
    if db_path is None:
        db_path = os.path.expanduser('~/Desktop/Neshama/neshama.db')
    if not os.path.exists(db_path):
        return set()
    conn = sqlite3.connect(db_path)
    names = {row[0].lower().strip() for row in conn.execute("SELECT name FROM vendors").fetchall()}
    conn.close()
    return names


def normalize_name(name):
    """Normalize business name for comparison."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name


def clean_vendors(input_files, db_path=None):
    """Clean and consolidate vendor CSVs."""
    all_rows = []
    for filepath in input_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['_source_file'] = os.path.basename(filepath)
                all_rows.append(row)

    print(f"Total raw records: {len(all_rows)}")

    existing = load_existing_vendors(db_path)
    print(f"Existing vendors in DB: {len(existing)}")

    cleaned = []
    removed = []
    flagged = []
    already_in_db = []

    for row in all_rows:
        name = row.get('name', '').strip()
        address = row.get('full_address', '').strip()
        city = row.get('city', '').strip()
        state = row.get('state', '').strip()
        try:
            rating = float(row.get('rating', 0) or 0)
        except (ValueError, TypeError):
            rating = 0
        try:
            reviews = int(float(row.get('reviews', 0) or 0))
        except (ValueError, TypeError):
            reviews = 0
        website = row.get('site', '').strip()
        btype = row.get('type', '')
        reason = None

        # Check removal criteria
        if not name:
            reason = 'missing_name'
        elif not is_valid_address(address, city):
            reason = 'missing_address'
        elif is_big_box(name):
            reason = 'big_box_retailer'
        elif is_chain_no_jewish(name):
            reason = 'chain_no_jewish_connection'
        elif is_not_vendor(name, btype):
            reason = 'not_a_vendor'
        elif not is_in_service_area(city, state):
            reason = 'outside_service_area'
        elif reviews <= 10:
            reason = 'too_few_reviews'

        if reason:
            row['removal_reason'] = reason
            removed.append(row)
            continue

        # Check if already in Neshama DB
        if normalize_name(name) in {normalize_name(n) for n in existing}:
            row['flag'] = 'ALREADY_IN_DB'
            already_in_db.append(row)
            continue

        # Flag for review (don't remove)
        flags = []
        if not website:
            flags.append('no_website')
        if rating < 3.5 and rating > 0:
            flags.append('low_rating')

        row['flag'] = '|'.join(flags) if flags else ''
        if flags:
            flagged.append(row)

        cleaned.append(row)

    return cleaned, removed, flagged, already_in_db


def save_results(cleaned, removed, flagged, already_in_db, output_dir):
    """Save cleaned results and reports."""
    date_str = datetime.now().strftime('%Y%m%d')

    columns = ['name', 'full_address', 'city', 'state', 'postal_code',
               'phone', 'site', 'rating', 'reviews', 'latitude', 'longitude',
               'working_hours', 'place_id', 'type', 'subtypes', 'source_keyword', 'flag']

    # Cleaned CSV
    cleaned_path = os.path.join(output_dir, f'step2_cleaned_{date_str}.csv')
    with open(cleaned_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(cleaned)

    # Removed CSV
    removed_path = os.path.join(output_dir, f'step2_removed_{date_str}.csv')
    rem_columns = columns + ['removal_reason']
    with open(removed_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rem_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(removed)

    # Already in DB CSV
    existing_path = os.path.join(output_dir, f'step2_already_in_db_{date_str}.csv')
    with open(existing_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(already_in_db)

    # Report
    report_path = os.path.join(output_dir, f'step2_report_{date_str}.txt')
    total = len(cleaned) + len(removed) + len(already_in_db)
    with open(report_path, 'w') as f:
        f.write(f"Neshama Outscraper Pipeline — Step 2 Cleaning Report\n")
        f.write(f"{'='*50}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"Total records processed: {total}\n")
        f.write(f"Clean records: {len(cleaned)}\n")
        f.write(f"Removed: {len(removed)}\n")
        f.write(f"Already in Neshama DB: {len(already_in_db)}\n")
        f.write(f"Flagged for review: {len(flagged)}\n\n")

        # Removal reasons breakdown
        reasons = {}
        for r in removed:
            reason = r.get('removal_reason', 'unknown')
            reasons[reason] = reasons.get(reason, 0) + 1
        f.write(f"Removal reasons:\n")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            f.write(f"  {reason}: {count}\n")

        # City breakdown
        cities = {}
        for r in cleaned:
            c = r.get('city', 'Unknown')
            cities[c] = cities.get(c, 0) + 1
        f.write(f"\nClean records by city:\n")
        for c, count in sorted(cities.items(), key=lambda x: -x[1]):
            f.write(f"  {c}: {count}\n")

        f.write(f"\nOutput files:\n")
        f.write(f"  Cleaned: {cleaned_path}\n")
        f.write(f"  Removed: {removed_path}\n")
        f.write(f"  Already in DB: {existing_path}\n")
        f.write(f"\nNEXT STEP: Review cleaned CSV, then run step3_verify.py\n")
        f.write(f"REVIEW: Check removed list — did anything get removed that shouldn't have?\n")

    print(f"\n{'='*60}")
    print(f"CLEANING REPORT")
    print(f"{'='*60}")
    print(f"Total records: {total}")
    print(f"Clean: {len(cleaned)}")
    print(f"Removed: {len(removed)}")
    print(f"Already in DB: {len(already_in_db)}")
    print(f"Flagged: {len(flagged)}")
    print(f"\nFiles saved to {output_dir}/")
    print(f"\nNEXT: Review the cleaned CSV, then run step3_verify.py")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='Neshama Pipeline — Step 2: Clean')
    parser.add_argument('--input', type=str, required=True,
                        help='Input CSV(s) from Step 1 (supports glob patterns)')
    parser.add_argument('--db', type=str, default=None,
                        help='Path to local neshama.db for dedup')

    args = parser.parse_args()

    # Expand glob patterns
    input_files = glob.glob(args.input)
    if not input_files:
        print(f"No files found matching: {args.input}")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"NESHAMA OUTSCRAPER PIPELINE — STEP 2: CLEAN")
    print(f"Input files: {len(input_files)}")
    for f in input_files:
        print(f"  {f}")
    print(f"{'='*60}")

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(output_dir, exist_ok=True)

    cleaned, removed, flagged, already_in_db = clean_vendors(input_files, args.db)
    save_results(cleaned, removed, flagged, already_in_db, output_dir)


if __name__ == '__main__':
    main()
