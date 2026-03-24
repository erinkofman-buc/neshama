#!/usr/bin/env python3
"""
Neshama Vendor Pipeline — Import to Database
Takes pipeline-processed vendor CSV and imports into Neshama's SQLite database.
Deduplicates against existing vendors. Generates migration SQL for production.

Usage:
    python import_vendors.py --input data/step7_directory_ready.csv --dry-run
    python import_vendors.py --input data/step7_directory_ready.csv
    python import_vendors.py --input data/step4_publish_ready.csv --skip-filters
"""

import argparse
import csv
import os
import re
import sqlite3
import sys
from datetime import datetime


def slugify(name):
    """Convert vendor name to URL slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def load_existing_vendors(db_path):
    """Load existing vendor names and slugs."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, slug FROM vendors")
    vendors = {row[0].lower().strip(): row[1] for row in cursor.fetchall()}
    conn.close()
    return vendors


def map_category(row):
    """Map pipeline category to Neshama database category."""
    primary = row.get('primary_category', row.get('category', '')).upper()
    mapping = {
        'SHIVA_SPECIALIST': 'Caterers',
        'FULL_SERVICE_CATERER': 'Caterers',
        'MEAL_DELIVERY': 'Kosher Restaurants & Caterers',
        'BAKERY_GIFTS': 'Bagel Shops & Bakeries',
        'DELI_COUNTER': 'Restaurants & Delis',
        'RESTAURANT_CATERER': 'Kosher Restaurants & Caterers',
        'GIFT_BASKET_SPECIALIST': 'Gift Baskets & Fruit',
        'JUDAICA_SHOP': 'Judaica & Books',
    }
    return mapping.get(primary, row.get('category', 'Kosher Restaurants & Caterers'))


def map_kosher_status(row):
    """Map pipeline kosher data to Neshama database format."""
    cert = row.get('kosher_cert', '').upper()
    if 'COR' in cert:
        return 'COR'
    elif 'MK' in cert:
        return 'MK'
    elif 'STAR-K' in cert or 'OU' in cert:
        return cert
    elif 'KOSHER STYLE' in cert or 'STYLE' in cert:
        return 'not_certified'
    return 'not_certified'


def import_vendors(input_file, db_path, dry_run=False):
    """Import vendors from pipeline CSV into database."""
    existing = load_existing_vendors(db_path)
    print(f"Existing vendors in DB: {len(existing)}")

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Vendors in input file: {len(rows)}")

    to_import = []
    skipped_dedup = []
    skipped_quality = []

    for row in rows:
        name = row.get('name', row.get('business_name', '')).strip()
        if not name:
            continue

        # Dedup check
        if name.lower().strip() in existing:
            skipped_dedup.append(name)
            continue

        # Quality gate — skip Tier 4/5 if tier column exists
        tier = row.get('tier', '').upper()
        if tier in ('TIER 5', 'TIER_5', '5'):
            skipped_quality.append(name)
            continue

        slug = slugify(name)
        category = map_category(row)
        kosher_status = map_kosher_status(row)
        description = row.get('directory_description', row.get('description', ''))
        address = row.get('full_address', row.get('address', ''))
        neighborhood = row.get('neighborhood', row.get('city', ''))
        phone = row.get('phone', '')
        website = row.get('site', row.get('website', ''))
        delivery = 1 if row.get('delivery_available', '').lower() in ('true', '1', 'yes') else 0
        delivery_area = row.get('delivery_areas', row.get('service_areas', ''))

        to_import.append({
            'name': name,
            'slug': slug,
            'category': category,
            'description': description,
            'address': address,
            'neighborhood': neighborhood,
            'phone': phone,
            'website': website,
            'kosher_status': kosher_status,
            'delivery': delivery,
            'delivery_area': delivery_area,
            'vendor_type': 'food',
        })

    print(f"\nTo import: {len(to_import)}")
    print(f"Skipped (already in DB): {len(skipped_dedup)}")
    print(f"Skipped (low quality): {len(skipped_quality)}")

    if dry_run:
        print(f"\n[DRY RUN] Would import {len(to_import)} vendors:")
        for v in to_import:
            print(f"  {v['name']} | {v['category']} | {v['kosher_status']} | {v['website']}")
        return to_import

    # Import to local database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    imported = 0

    for v in to_import:
        try:
            cursor.execute("""
                INSERT INTO vendors (name, slug, category, description, address,
                    neighborhood, phone, website, kosher_status, delivery,
                    delivery_area, vendor_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (v['name'], v['slug'], v['category'], v['description'],
                  v['address'], v['neighborhood'], v['phone'], v['website'],
                  v['kosher_status'], v['delivery'], v['delivery_area'],
                  v['vendor_type']))
            imported += 1
        except Exception as e:
            print(f"  ERROR importing {v['name']}: {e}")

    conn.commit()
    conn.close()
    print(f"\nImported {imported} vendors to local DB")

    # Generate migration SQL for production
    migration_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data',
        f'migration_{datetime.now().strftime("%Y%m%d")}.sql'
    )
    with open(migration_path, 'w') as f:
        f.write(f"-- Neshama vendor import migration\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Source: {input_file}\n")
        f.write(f"-- Vendors: {len(to_import)}\n\n")
        for v in to_import:
            name_escaped = v['name'].replace("'", "''")
            desc_escaped = v['description'].replace("'", "''")
            f.write(f"INSERT OR IGNORE INTO vendors (name, slug, category, description, "
                    f"address, neighborhood, phone, website, kosher_status, delivery, "
                    f"delivery_area, vendor_type) VALUES ("
                    f"'{name_escaped}', '{v['slug']}', '{v['category']}', "
                    f"'{desc_escaped}', '{v['address']}', '{v['neighborhood']}', "
                    f"'{v['phone']}', '{v['website']}', '{v['kosher_status']}', "
                    f"{v['delivery']}, '{v['delivery_area']}', '{v['vendor_type']}');\n")

    print(f"Migration SQL saved to {migration_path}")
    print(f"Copy these SQL statements into api_server.py migrations for production deploy.")

    return to_import


def main():
    parser = argparse.ArgumentParser(description='Neshama Pipeline — Import Vendors')
    parser.add_argument('--input', type=str, required=True, help='Pipeline CSV to import')
    parser.add_argument('--db', type=str,
                        default=os.path.expanduser('~/Desktop/Neshama/neshama.db'),
                        help='Path to local neshama.db')
    parser.add_argument('--dry-run', action='store_true', help='Preview without importing')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"NESHAMA VENDOR IMPORT")
    print(f"Input: {args.input}")
    print(f"Database: {args.db}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE IMPORT'}")
    print(f"{'='*60}")

    import_vendors(args.input, args.db, args.dry_run)


if __name__ == '__main__':
    main()
