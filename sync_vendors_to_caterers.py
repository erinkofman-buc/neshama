#!/usr/bin/env python3
"""One-time sync: copy food vendors into caterer_partners so they appear in
the shiva organizer caterer browser. Runs safely multiple times (skips existing)."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get('DATABASE_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neshama.db'))

KOSHER_MAP = {
    'COR': 'certified_kosher',
    'OK': 'certified_kosher',
    'MK': 'certified_kosher',
    'certified_kosher': 'certified_kosher',
    'kosher_style': 'kosher_style',
    'not_certified': 'not_kosher',
}

def sync():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all food vendors not already in caterer_partners
    cursor.execute('''
        SELECT v.* FROM vendors v
        WHERE v.vendor_type = 'food'
        AND NOT EXISTS (
            SELECT 1 FROM caterer_partners cp
            WHERE LOWER(cp.business_name) = LOWER(v.name)
        )
    ''')
    vendors = [dict(r) for r in cursor.fetchall()]
    print(f"Found {len(vendors)} food vendors not yet in caterer_partners")

    now = datetime.now().isoformat()
    added = 0

    for v in vendors:
        slug = v.get('slug', '')
        kosher_raw = v.get('kosher_status', 'not_certified')
        kosher_level = KOSHER_MAP.get(kosher_raw, 'not_kosher')

        try:
            cursor.execute('''
                INSERT INTO caterer_partners (
                    id, business_name, contact_name, email, phone, website,
                    instagram, delivery_area, kosher_level, has_delivery,
                    has_online_ordering, price_range, shiva_menu_description,
                    logo_url, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                slug or f"vendor-{v['id']}",
                v['name'],
                v['name'],  # contact_name = business name (can be enriched later)
                v.get('email') or f"{slug}@pending.neshama.ca",
                v.get('phone') or '',
                v.get('website') or '',
                v.get('instagram') or '',
                v.get('delivery_area') or v.get('city') or 'GTA',
                kosher_level,
                1 if v.get('delivery') else 0,
                0,
                '$$',
                v.get('description') or f"Contact {v['name']} for shiva meal options.",
                v.get('image_url') or '',
                'approved',  # Show in browse list immediately
                now,
                now,
            ))
            added += 1
            print(f"  + {v['name']} ({kosher_level})")
        except sqlite3.IntegrityError:
            print(f"  ~ {v['name']} (already exists)")

    conn.commit()
    conn.close()
    print(f"\nDone: {added} vendors added to caterer_partners")

if __name__ == '__main__':
    sync()
