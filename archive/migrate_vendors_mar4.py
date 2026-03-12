#!/usr/bin/env python3
"""
Neshama Vendor Migration — March 4, 2026

1. Update kosher_status from 'COR' to 'Kosher Style' for five vendors.
2. Delete three vendors that no longer exist.

Safe to run multiple times (idempotent).
"""

import sqlite3
import os
import sys

DB_PATH = os.environ.get('DATABASE_PATH', 'neshama.db')

# -- Step 1: vendors whose kosher_status should be 'Kosher Style' (not 'COR') --
KOSHER_STYLE_VENDORS = [
    "What A Bagel",
    "Gryfe's Bagel Bakery",
    "Kiva's Bagels",
    "Sonny Langers Dairy & Vegetarian Caterers",
    "Me-Va-Me",
]

# -- Step 2: vendors to delete (no longer exist) --
DELETE_VENDORS = [
    "Pizza Pita",
    "Shwarma Express",
    "Pita Box",
]


def run_migration(db_path=None):
    path = db_path or DB_PATH
    if not os.path.exists(path):
        print(f"ERROR: database not found at {path}")
        sys.exit(1)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # ---- Update kosher_status ----
    updated = 0
    for name in KOSHER_STYLE_VENDORS:
        cursor.execute(
            "SELECT id, kosher_status FROM vendors WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        if row is None:
            print(f"  SKIP (not found): {name}")
            continue
        vendor_id, current_status = row
        if current_status == "Kosher Style":
            print(f"  SKIP (already Kosher Style): {name}")
            continue
        cursor.execute(
            "UPDATE vendors SET kosher_status = 'Kosher Style' WHERE id = ?",
            (vendor_id,),
        )
        print(f"  UPDATED: {name}  kosher_status '{current_status}' -> 'Kosher Style'")
        updated += 1

    # ---- Delete vendors ----
    deleted = 0
    for name in DELETE_VENDORS:
        cursor.execute("SELECT id FROM vendors WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row is None:
            print(f"  SKIP (not found, already deleted?): {name}")
            continue
        vendor_id = row[0]
        cursor.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
        print(f"  DELETED: {name}  (id={vendor_id})")
        deleted += 1

    conn.commit()
    conn.close()

    print(f"\nDone. {updated} updated, {deleted} deleted.")


if __name__ == "__main__":
    print(f"Running vendor migration on: {DB_PATH}\n")
    run_migration()
