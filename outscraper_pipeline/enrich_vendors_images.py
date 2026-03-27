#!/usr/bin/env python3
"""
Vendor Image + Deep Enrichment Pass — Firecrawl
================================================
Focused on filling remaining gaps:
  - og_image from metadata (126/126 missing)
  - emails, instagram, phones from markdown content
  - Only scrapes vendors still missing data

Usage:
  python3 outscraper_pipeline/enrich_vendors_images.py
  python3 outscraper_pipeline/enrich_vendors_images.py --limit 10
  python3 outscraper_pipeline/enrich_vendors_images.py --apply
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time

try:
    from firecrawl import FirecrawlApp
except ImportError:
    print("ERROR: pip3 install firecrawl-py")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "neshama.db")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "vendor_enrichment_images.json")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "vendor_enrichment_images.sql")

API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
DELAY_SECONDS = 1.5

# Junk image patterns to skip
JUNK_IMAGE_PATTERNS = [
    'placeholder', 'default', 'blank', 'spacer', '1x1', 'pixel',
    'facebook.com', 'twitter.com', 'google.com/images',
    'shopify.com/s/files', 'cdn.shopify.com/shopifycloud',
    'gravatar.com', 'wp-content/plugins',
]

JUNK_EMAIL_PATTERNS = [
    'noreply@', 'no-reply@', 'support@shopify', 'support@squarespace',
    'example.com', 'test@', 'wixpress.com', 'sentry', 'gist-apps.com',
    'user@domain', '.jpg', '.png', '.gif', '.webp', '.co.uk',
]


def load_vendors_needing_data(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, name, slug, website, phone, email, instagram, image_url,
               delivery, delivery_area, kosher_status
        FROM vendors
        WHERE website IS NOT NULL AND website != ''
          AND (image_url IS NULL OR image_url = ''
               OR email IS NULL OR email = ''
               OR instagram IS NULL OR instagram = ''
               OR phone IS NULL OR phone = '')
        ORDER BY name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_valid_image(url):
    if not url or not url.startswith('http'):
        return False
    url_lower = url.lower()
    for pattern in JUNK_IMAGE_PATTERNS:
        if pattern in url_lower:
            return False
    # Must look like an image or be an og:image URL
    return True


def clean_email(email):
    if not email:
        return None
    email = email.strip().lower()
    for pattern in JUNK_EMAIL_PATTERNS:
        if pattern in email:
            return None
    if '@' not in email or '.' not in email.split('@')[-1]:
        return None
    return email


def clean_phone(phone):
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]
    # Validate NA area code (first digit must be 2-9)
    if len(digits) == 10 and digits[0] in '23456789':
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return None


def clean_instagram(handle):
    if not handle:
        return None
    handle = handle.strip().lower().lstrip('@')
    if handle in ('', 'v', 'p', 'reel', 'reels', 'explore', 'stories', 'accounts'):
        return None
    if '/' in handle:
        match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', handle)
        if match:
            handle = match.group(1).lower()
        else:
            return None
    if ' ' in handle or len(handle) < 2:
        return None
    return f"@{handle}"


def sql_escape(val):
    return val.replace("'", "''")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  Vendor Image + Deep Enrichment — Firecrawl")
    print("=" * 60)

    app = FirecrawlApp(api_key=API_KEY)

    vendors = load_vendors_needing_data(DB_PATH)
    print(f"\nVendors needing data: {len(vendors)}")

    if args.limit:
        vendors = vendors[:args.limit]
        print(f"  (limited to {args.limit})")

    results = []
    stats = {
        "total": len(vendors), "scraped": 0, "errors": 0, "enriched": 0,
        "images": 0, "emails": 0, "instagrams": 0, "phones": 0,
        "credits_used": 0, "cache_hits": 0,
    }

    for i, v in enumerate(vendors):
        name = v["name"]
        slug = v["slug"]
        website = v["website"].strip()

        missing = []
        if not v["image_url"]: missing.append("img")
        if not v["email"]: missing.append("email")
        if not v["instagram"]: missing.append("ig")
        if not v["phone"]: missing.append("phone")

        if stats["scraped"] > 0:
            time.sleep(DELAY_SECONDS)

        print(f"\n  [{i+1}/{len(vendors)}] {name} — need: {', '.join(missing)}")

        try:
            result = app.scrape(website, formats=["markdown"], timeout=30000)
            stats["scraped"] += 1
            stats["credits_used"] += 1

            # Check cache
            if hasattr(result, 'metadata') and hasattr(result.metadata, 'cache_state'):
                if result.metadata.cache_state == 'hit':
                    stats["cache_hits"] += 1

        except Exception as e:
            err = str(e)[:100]
            print(f"    ERROR: {err}")
            stats["errors"] += 1
            continue

        enriched = {"slug": slug, "name": name, "image_url": None,
                    "email": None, "instagram": None, "phone": None}
        found = False

        # === IMAGE from metadata ===
        if not v["image_url"] and hasattr(result, 'metadata'):
            meta = result.metadata
            img = None
            if hasattr(meta, 'og_image') and meta.og_image:
                img = meta.og_image
            if not img and hasattr(meta, 'favicon') and meta.favicon:
                # Skip favicons — too small
                pass

            if img and is_valid_image(img):
                enriched["image_url"] = img
                stats["images"] += 1
                found = True

        # === EMAIL from markdown ===
        markdown = result.markdown or "" if hasattr(result, 'markdown') else ""

        if not v["email"]:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', markdown)
            for em in emails:
                cleaned = clean_email(em)
                if cleaned:
                    enriched["email"] = cleaned
                    stats["emails"] += 1
                    found = True
                    break

        # === INSTAGRAM from markdown ===
        if not v["instagram"]:
            ig_matches = re.findall(r'instagram\.com/([A-Za-z0-9_.]+)', markdown, re.IGNORECASE)
            for handle in ig_matches:
                cleaned = clean_instagram(handle)
                if cleaned:
                    enriched["instagram"] = cleaned
                    stats["instagrams"] += 1
                    found = True
                    break

        # === PHONE from markdown ===
        if not v["phone"]:
            phone_matches = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', markdown)
            for pm in phone_matches:
                cleaned = clean_phone(pm)
                if cleaned:
                    enriched["phone"] = cleaned
                    stats["phones"] += 1
                    found = True
                    break

        if found:
            results.append(enriched)
            stats["enriched"] += 1
            parts = []
            if enriched["image_url"]: parts.append("IMG")
            if enriched["email"]: parts.append("EMAIL")
            if enriched["instagram"]: parts.append("IG")
            if enriched["phone"]: parts.append("TEL")
            print(f"    FOUND: {', '.join(parts)}")
        else:
            print(f"    nothing new")

    # Save JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: {OUTPUT_JSON}")

    # Save SQL
    sql_lines = [
        "-- Vendor Image + Deep Enrichment via Firecrawl",
        f"-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"-- Vendors enriched: {stats['enriched']}",
        "",
    ]
    for r in results:
        slug = sql_escape(r["slug"])
        sets = []
        if r["image_url"]:
            sets.append(f"image_url = '{sql_escape(r['image_url'])}'")
        if r["email"]:
            sets.append(f"email = '{sql_escape(r['email'])}'")
        if r["instagram"]:
            sets.append(f"instagram = '{sql_escape(r['instagram'])}'")
        if r["phone"]:
            sets.append(f"phone = '{sql_escape(r['phone'])}'")
        if sets:
            sql_lines.append(f"UPDATE vendors SET {', '.join(sets)} WHERE slug = '{slug}';")

    with open(OUTPUT_SQL, "w") as f:
        f.write("\n".join(sql_lines))
    print(f"Saved: {OUTPUT_SQL}")

    # Apply
    if args.apply and results:
        print("\nApplying to local database...")
        conn = sqlite3.connect(DB_PATH)
        applied = 0
        for r in results:
            updates = {}
            if r["image_url"]: updates["image_url"] = r["image_url"]
            if r["email"]: updates["email"] = r["email"]
            if r["instagram"]: updates["instagram"] = r["instagram"]
            if r["phone"]: updates["phone"] = r["phone"]
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE vendors SET {set_clause} WHERE slug = ?",
                    list(updates.values()) + [r["slug"]]
                )
                applied += 1
        conn.commit()
        conn.close()
        print(f"  Applied to {applied} vendors")

    # Summary
    print("\n" + "=" * 60)
    print("  ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Vendors processed:      {stats['scraped']}")
    print(f"  Cache hits:             {stats['cache_hits']}")
    print(f"  Errors:                 {stats['errors']}")
    print(f"  Vendors enriched:       {stats['enriched']}")
    print(f"  ─────────────────────────────────")
    print(f"  Images found:           {stats['images']}")
    print(f"  Emails found:           {stats['emails']}")
    print(f"  Instagram handles:      {stats['instagrams']}")
    print(f"  Phone numbers:          {stats['phones']}")
    print(f"  ─────────────────────────────────")
    print(f"  Firecrawl credits used: {stats['credits_used']}")
    print(f"  Credits remaining:      ~{500 - 117 - stats['credits_used']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
