#!/usr/bin/env python3
"""
Migration: Clean invalid phone numbers from vendors table.
Firecrawl enrichment imported garbage numbers with invalid area codes.
Valid Canadian area codes for Toronto/Montreal: 416,647,437,905,289,365,
548,226,519,613,343,705,249,807,382,514,438,450,579,819,873

This sets invalid phone numbers to NULL rather than deleting the vendor.
Run on production via: python3 migrations/clean_phone_numbers.py
"""

import sqlite3
import re
import os

VALID_AREA_CODES = {
    '416', '647', '437', '905', '289', '365', '548', '226', '519',
    '613', '343', '705', '249', '807', '382',  # Ontario
    '514', '438', '450', '579', '819', '873',  # Quebec
}

def clean_phones(db_path):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT id, name, phone FROM vendors WHERE phone IS NOT NULL AND phone != ""')
    rows = c.fetchall()

    cleaned = 0
    for row in rows:
        digits = re.sub(r'\D', '', row['phone'])
        area = digits[:3] if len(digits) >= 10 else ''

        if len(digits) != 10 or area not in VALID_AREA_CODES:
            print(f"  INVALID: {row['name']} — {row['phone']} (area={area})")
            c.execute('UPDATE vendors SET phone = NULL WHERE id = ?', (row['id'],))
            cleaned += 1

    conn.commit()
    print(f"\nCleaned {cleaned} invalid phone numbers out of {len(rows)} total")
    conn.close()

if __name__ == '__main__':
    db_path = os.environ.get('DB_PATH', 'neshama.db')
    print(f"Cleaning phone numbers in {db_path}...")
    clean_phones(db_path)
