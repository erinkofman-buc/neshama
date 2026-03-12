#!/usr/bin/env python3
"""
Update vendor emails in neshama.db based on website scraping results.
Run without --confirm to preview. Run with --confirm to write changes.
Always backs up the DB first.
"""

import sqlite3
import shutil
import sys
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/Desktop/Neshama/neshama.db")

# New emails found from vendor websites (id, vendor_name, email, source)
NEW_EMAILS = [
    (255, "Schmaltz Appetizing", "info@schmaltzappetizing.com", "Homepage"),
    (356, "Bubby's New York Bagels", "info@bubbysbagels.com", "Homepage"),
    (263, "Ely's Fine Foods", "catering@elysfinefoods.com", "Homepage"),
    (300, "Ely's Fine Foods Gift Baskets", "catering@elysfinefoods.com", "Homepage (same site)"),
    (225, "Milk 'N Honey", "order@milknhoney.ca", "Homepage"),
    (330, "Slice N Bites", "manager@slicenbites.com", "Homepage"),
    (224, "The Chicken Nest", "chickennestorders@gmail.com", "Homepage"),
    (327, "Umami Sushi", "info@umamisushi.ca", "Contact page"),
    (238, "Wok & Bowl", "info@wokandbowl.ca", "Homepage"),
    (269, "Blossom by La Plaza", "info@blossombylaplaza.com", "Homepage"),
    (294, "La Marguerite Catering", "info@lamarguerite.ca", "Homepage"),
    (280, "Nosherz", "robert@nosherz.com", "Homepage"),
    (279, "Montreal Kosher Bakery", "info@montrealkosher.ca", "Homepage"),
    (270, "Paradise Kosher Catering", "info@paradisekosher.com", "Homepage"),
    (287, "Europea", "jferrer@europea.ca", "Homepage"),
    (281, "Mandy's", "wholesale@mandys.ca", "Contact page"),
    (283, "Moishes", "moishesmontreal@moishes.ca", "Homepage"),
    (240, "Aish Tanoor", "info@aishtanoor.com", "Homepage"),
    (312, "Laura Secord", "customerservice@laurasecord.ca", "Homepage"),
    (311, "Purdys Chocolatier", "sales@purdys.com", "Homepage"),
    (261, "Longo's", "guestcare@longos.com", "Homepage"),
    (257, "Paramount Fine Foods", "catering@paramountfinefoods.com", "Contact page"),
    (275, "Lester's Deli", "info@lestersdeli.com", "Homepage"),
    (273, "Deli 365", "montrealdeli365@gmail.com", "Homepage"),
    (292, "District Bagel", "info@districtbagel.com", "Homepage"),
    (266, "PRC Caterers", "info@prccaterers.com", "Homepage"),
    (227, "Yummy Market", "info@yummymarket.com", "Homepage"),
    (282, "Gibby's", "info@gibbys.com", "Homepage"),
    (291, "Olive et Gourmando", "info@oliveetgourmando.com", "Homepage"),
    (274, "Schwartz's Deli", "info@schwartzsdeli.com", "Homepage"),
    (236, "Terroni", "info@terroni.com", "Homepage"),
    (267, "Beyond Delish", "info@beyonddelish.ca", "Homepage"),
    (258, "Scaramouche Restaurant", "scaramouche@rogers.com", "Contact page"),
    (333, "Shalom India", "shalomindiacatering@gmail.com", "Homepage"),
    (325, "Chagall", "info@chagallto.com", "Homepage"),
    (226, "Kosher Gourmet", "orders@koshergourmet.ca", "Homepage"),
    (303, "Romi's Bakery", "info@romisbakery.com", "Homepage"),
    (301, "Nutcracker Sweet / Baskits", "orders@baskits.com", "Contact page"),
    (297, "Gifting Kosher Canada", "cs@giftingkosher.com", "Homepage"),
]


def main():
    confirm = "--confirm" in sys.argv

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    # Always back up first
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.replace(".db", f"_backup_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check which vendors already have emails (skip those)
    skipped = 0
    to_update = []

    print("\n" + "=" * 80)
    print("VENDOR EMAIL UPDATE PREVIEW")
    print("=" * 80)

    for vendor_id, name, email, source in NEW_EMAILS:
        cursor.execute("SELECT id, name, email FROM vendors WHERE id = ?", (vendor_id,))
        row = cursor.fetchone()
        if not row:
            print(f"  SKIP (not found): ID {vendor_id} - {name}")
            skipped += 1
            continue

        existing_email = row[2]
        if existing_email and existing_email.strip():
            print(f"  SKIP (has email): ID {vendor_id} - {name} -> {existing_email}")
            skipped += 1
            continue

        to_update.append((vendor_id, name, email, source))
        print(f"  UPDATE: ID {vendor_id} - {name} -> {email} ({source})")

    print(f"\n{'=' * 80}")
    print(f"Summary: {len(to_update)} to update, {skipped} skipped")
    print(f"{'=' * 80}\n")

    if not to_update:
        print("Nothing to update.")
        conn.close()
        return

    if not confirm:
        print("DRY RUN - no changes written.")
        print("Run with --confirm to apply updates.")
        conn.close()
        return

    # Apply updates
    updated = 0
    for vendor_id, name, email, source in to_update:
        cursor.execute("UPDATE vendors SET email = ? WHERE id = ?", (email, vendor_id))
        updated += 1

    conn.commit()
    conn.close()

    print(f"DONE: {updated} vendor emails updated.")
    print(f"Backup at: {backup_path}")


if __name__ == "__main__":
    main()
