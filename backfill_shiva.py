#!/usr/bin/env python3
"""
Backfill shiva info for existing obituaries.
Runs extract_shiva_info() against all obituaries that have obituary_text
and updates the new shiva columns.
"""

import sqlite3
import os
from shiva_parser import extract_shiva_info

def backfill():
    db_path = os.environ.get('DATABASE_PATH', 'neshama.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ensure columns exist
    for col, col_type in [
        ('shiva_address', 'TEXT'),
        ('shiva_hours', 'TEXT'),
        ('shiva_concludes', 'TEXT'),
        ('shiva_raw', 'TEXT'),
        ('shiva_private', 'INTEGER DEFAULT 0'),
    ]:
        try:
            cursor.execute(f'ALTER TABLE obituaries ADD COLUMN {col} {col_type}')
            print(f"  Added column: {col}")
        except sqlite3.OperationalError:
            pass

    # Get all obituaries with text
    cursor.execute('SELECT id, deceased_name, obituary_text, shiva_info FROM obituaries')
    rows = cursor.fetchall()
    print(f"\nProcessing {len(rows)} obituaries...\n")

    stats = {'parsed': 0, 'with_address': 0, 'with_hours': 0, 'private': 0, 'no_match': 0}

    for row in rows:
        obit_id = row['id']
        name = row['deceased_name']
        text = row['obituary_text'] or row['shiva_info'] or ''

        if not text:
            stats['no_match'] += 1
            continue

        result = extract_shiva_info(text)

        if result:
            stats['parsed'] += 1
            if result['shiva_address']:
                stats['with_address'] += 1
            if result['shiva_hours']:
                stats['with_hours'] += 1
            if result['shiva_private']:
                stats['private'] += 1

            cursor.execute('''
                UPDATE obituaries SET
                    shiva_address = ?,
                    shiva_hours = ?,
                    shiva_concludes = ?,
                    shiva_raw = ?,
                    shiva_private = ?
                WHERE id = ?
            ''', (
                result['shiva_address'],
                result['shiva_hours'],
                result['shiva_concludes'],
                result['shiva_raw'],
                1 if result['shiva_private'] else 0,
                obit_id
            ))
            print(f"  {name}: {'PRIVATE' if result['shiva_private'] else result['shiva_address'] or result['shiva_raw'][:60]}")
        else:
            stats['no_match'] += 1

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"  Backfill complete!")
    print(f"  Total obituaries: {len(rows)}")
    print(f"  Shiva info found: {stats['parsed']}")
    print(f"    With address:   {stats['with_address']}")
    print(f"    With hours:     {stats['with_hours']}")
    print(f"    Private:        {stats['private']}")
    print(f"  No shiva match:   {stats['no_match']}")
    print(f"{'='*50}\n")


if __name__ == '__main__':
    backfill()
