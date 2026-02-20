#!/usr/bin/env python3
"""
One-time script to backfill delivery_area for existing food vendors.
Run: python3 update_delivery_zones.py
"""

import sqlite3
import os

DB_PATH = os.environ.get('DATABASE_PATH', 'neshama.db')

# slug -> delivery_area mapping (matches seed_vendors.py)
ZONE_MAP = {
    # Bagel Shops & Bakeries
    'what-a-bagel': 'Thornhill/Vaughan,North York',
    'gryfes-bagel-bakery': '',
    'kivas-bagels': '',
    'bagel-world': 'Toronto,North York',
    'hermes-bakery': 'Toronto,North York',
    'united-bakers-dairy-restaurant': 'Toronto',
    # Kosher Restaurants & Caterers
    'jem-salads': 'Thornhill/Vaughan,North York,Toronto',
    'bistro-grande': 'Thornhill/Vaughan,North York',
    'miami-grill': 'Toronto,North York',
    'tov-li-pizza-falafel': 'Toronto,North York',
    'mattis-kitchen': 'Toronto,North York',
    'yummy-market': 'Toronto,North York',
    'daiters-meat-deli': '',
    'orlys-kitchen': 'Toronto,North York',
    'cafe-sheli': '',
    # Caterers
    'creative-kosher-catering': 'GTA-wide',
    'main-event-catering': 'GTA-wide',
    'taam-hayam-catering': 'GTA-wide',
    'joshs-catering': 'GTA-wide',
    # Italian
    'village-pizza-kosher': 'Toronto,North York',
    'pizza-pita': 'Toronto,North York',
    'il-paesano': 'Toronto',
    'terroni': 'Toronto',
    # Middle Eastern & Israeli
    'dr-laffa': 'Toronto,North York',
    'aish-tanoor': '',
    'parallel': 'Toronto',
    'shwarma-express': 'Toronto,North York',
    'me-va-me': 'Thornhill/Vaughan,North York',
    'pita-box': 'Thornhill/Vaughan,North York',
    # More diverse options
    'sushi-inn': 'Toronto,North York',
    'noahs-natural-foods': 'Toronto',
    'summerhill-market': 'Toronto',
    'pickle-barrel': 'Toronto,North York',
    'harbord-bakery': '',
    'centre-street-deli': 'Thornhill/Vaughan,North York,Toronto',
    'nortown-foods': 'Toronto,North York',
    'cheese-boutique': 'Toronto',
}


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    updated = 0

    for slug, zone in ZONE_MAP.items():
        cursor.execute(
            'UPDATE vendors SET delivery_area = ? WHERE slug = ? AND vendor_type = ?',
            (zone, slug, 'food')
        )
        if cursor.rowcount:
            updated += 1

    conn.commit()
    conn.close()
    print(f"Updated delivery_area for {updated} food vendors")


if __name__ == '__main__':
    main()
