#!/usr/bin/env python3
"""
Vendor Enrichment via Firecrawl — Neshama
==========================================
Uses Firecrawl API to scrape vendor websites and extract:
  - image_url (og:image, logo, storefront)
  - instagram handle
  - email address
  - phone number (if missing)
  - delivery info
  - hours of operation

Reads from local neshama.db, outputs JSON + SQL migration.
Only enriches fields that are currently missing.

Usage:
  python3 outscraper_pipeline/enrich_vendors_firecrawl.py
  python3 outscraper_pipeline/enrich_vendors_firecrawl.py --dry-run
  python3 outscraper_pipeline/enrich_vendors_firecrawl.py --limit 10
  python3 outscraper_pipeline/enrich_vendors_firecrawl.py --apply
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
    print("ERROR: firecrawl-py not installed. Run: pip3 install firecrawl-py")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "neshama.db")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "vendor_enrichment_firecrawl.json")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "vendor_enrichment_firecrawl.sql")

API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

# Delay between requests to stay under rate limits (free tier: 500 credits)
DELAY_SECONDS = 2

# Fields we want to extract via Firecrawl's LLM extraction
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "business_email": {
            "type": "string",
            "description": "Primary business contact email address (not noreply or support@shopify)"
        },
        "phone_number": {
            "type": "string",
            "description": "Primary business phone number"
        },
        "instagram_handle": {
            "type": "string",
            "description": "Instagram handle/username (without @)"
        },
        "logo_or_hero_image_url": {
            "type": "string",
            "description": "URL of the business logo or main hero/storefront image"
        },
        "offers_delivery": {
            "type": "boolean",
            "description": "Whether the business offers delivery service"
        },
        "delivery_area": {
            "type": "string",
            "description": "Areas/neighborhoods where they deliver"
        },
        "kosher_certification": {
            "type": "string",
            "description": "Kosher certification body if any (e.g. COR, MK, OK, OU)"
        },
        "hours_of_operation": {
            "type": "string",
            "description": "Business hours, brief format"
        }
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_vendors(db_path):
    """Load all vendors from local DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, name, slug, website, phone, email, instagram,
               image_url, delivery, delivery_area, kosher_status, description
        FROM vendors
        WHERE website IS NOT NULL AND website != ''
        ORDER BY name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clean_email(email):
    """Filter out junk emails."""
    if not email:
        return None
    email = email.strip().lower()
    junk = [
        'noreply@', 'no-reply@', 'support@shopify', 'support@squarespace',
        'example.com', 'test@', 'wixpress.com', 'sentry', 'gist-apps.com',
        'user@domain',
    ]
    if any(j in email for j in junk):
        return None
    if '@' not in email or '.' not in email.split('@')[-1]:
        return None
    return email


def clean_phone(phone):
    """Format as (XXX) XXX-XXXX for 10-digit NA numbers."""
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) >= 7:
        return phone.strip()
    return None


def clean_instagram(handle):
    """Normalize instagram handle."""
    if not handle:
        return None
    handle = handle.strip().lower().lstrip('@')
    # Filter out non-handles
    if handle in ('p', 'reel', 'reels', 'explore', 'stories', 'accounts', ''):
        return None
    if '/' in handle or ' ' in handle:
        # Try to extract from URL
        match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', handle)
        if match:
            handle = match.group(1).lower()
        else:
            return None
    return f"@{handle}"


def map_kosher_status(cert_text, current_status):
    """Map extracted kosher certification to our labels: COR, MK, not_certified."""
    if not cert_text:
        return None
    cert = cert_text.upper().strip()
    if 'COR' in cert:
        return 'COR'
    if 'MK' in cert or 'MONTREAL KOSHER' in cert:
        return 'MK'
    if 'OU' in cert or 'OK' in cert or 'STAR-K' in cert:
        return cert_text.strip()  # Keep specific cert name
    # If they say "kosher" but no cert body, and current is already set, don't change
    if current_status and current_status != 'not_certified':
        return None
    return None


def sql_escape(val):
    return val.replace("'", "''")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Enrich Neshama vendors via Firecrawl")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just show what would happen")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N vendors (0 = all)")
    parser.add_argument("--apply", action="store_true", help="Apply enrichment directly to local DB")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip vendors that already have all enrichable fields filled")
    args = parser.parse_args()

    print("=" * 60)
    print("  Neshama Vendor Enrichment — Firecrawl")
    print("=" * 60)

    # Init Firecrawl
    app = FirecrawlApp(api_key=API_KEY)
    print(f"\nFirecrawl API initialized")

    # Load vendors
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    vendors = load_vendors(DB_PATH)
    print(f"Loaded {len(vendors)} vendors with websites")

    if args.limit:
        vendors = vendors[:args.limit]
        print(f"  (limited to first {args.limit})")

    # Track results
    results = []
    stats = {
        "total": len(vendors), "scraped": 0, "errors": 0, "enriched": 0,
        "skipped_complete": 0, "images": 0, "emails": 0, "instagrams": 0,
        "phones": 0, "delivery_areas": 0, "credits_used": 0,
    }

    for i, v in enumerate(vendors):
        name = v["name"]
        slug = v["slug"]
        website = v["website"].strip()

        # Check what's missing
        missing = []
        if not v["image_url"]:
            missing.append("image")
        if not v["email"]:
            missing.append("email")
        if not v["instagram"]:
            missing.append("instagram")
        if not v["phone"]:
            missing.append("phone")
        if not v["delivery_area"]:
            missing.append("delivery_area")

        if not missing and args.skip_existing:
            stats["skipped_complete"] += 1
            continue

        # Rate limit
        if stats["scraped"] > 0:
            time.sleep(DELAY_SECONDS)

        print(f"\n  [{i+1}/{len(vendors)}] {name}")
        print(f"    URL: {website}")
        print(f"    Missing: {', '.join(missing) if missing else 'checking for updates'}")

        try:
            # Step 1: Scrape for metadata (og:image, etc) — 1 credit
            scrape_result = app.scrape(website, formats=["markdown"], timeout=30000)
            stats["scraped"] += 1
            stats["credits_used"] += 1

            # Get metadata from scrape
            metadata = {}
            if hasattr(scrape_result, 'metadata_dict') and callable(scrape_result.metadata_dict):
                metadata = scrape_result.metadata_dict()
            elif hasattr(scrape_result, 'metadata'):
                metadata = scrape_result.metadata if isinstance(scrape_result.metadata, dict) else {}

            # Get markdown content for regex extraction
            markdown = ""
            if hasattr(scrape_result, 'markdown') and scrape_result.markdown:
                markdown = scrape_result.markdown
        except Exception as e:
            err = str(e)[:120]
            print(f"    ERROR: {err}")
            stats["errors"] += 1
            continue

        # Extract data from metadata + markdown content
        extracted = {}

        # Image from og:image metadata
        for key in ['ogImage', 'og:image', 'twitter:image']:
            val = metadata.get(key)
            if val:
                extracted['logo_or_hero_image_url'] = val
                break

        # Extract email from markdown
        email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', markdown)
        if email_matches:
            extracted['business_email'] = email_matches[0]

        # Extract Instagram from markdown
        ig_matches = re.findall(r'instagram\.com/([A-Za-z0-9_.]+)', markdown, re.IGNORECASE)
        if ig_matches:
            extracted['instagram_handle'] = ig_matches[0]

        # Extract phone from markdown
        phone_matches = re.findall(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', markdown)
        if phone_matches:
            extracted['phone_number'] = phone_matches[0]

        # Extract delivery info from markdown
        delivery_patterns = [
            r'(?:deliver(?:y|ing|s)?(?:\s+(?:to|in|across|throughout))?\s+)([\w\s,/&]+?)(?:\.|$|\n)',
        ]
        for pat in delivery_patterns:
            m = re.search(pat, markdown, re.IGNORECASE)
            if m:
                area = m.group(1).strip()
                if len(area) > 5 and len(area) < 100:
                    extracted['delivery_area'] = area
                break

        enriched = {
            "slug": slug,
            "name": name,
            "image_url": None,
            "instagram": None,
            "phone": None,
            "email": None,
            "delivery_area": None,
            "source": "firecrawl",
        }
        found_something = False

        # Image
        if not v["image_url"]:
            img = extracted.get("logo_or_hero_image_url")
            if img and img.startswith("http"):
                enriched["image_url"] = img
                stats["images"] += 1
                found_something = True

        # Email
        if not v["email"]:
            email = clean_email(extracted.get("business_email"))
            if email:
                enriched["email"] = email
                stats["emails"] += 1
                found_something = True

        # Instagram
        if not v["instagram"]:
            ig = clean_instagram(extracted.get("instagram_handle"))
            if ig:
                enriched["instagram"] = ig
                stats["instagrams"] += 1
                found_something = True

        # Phone
        if not v["phone"]:
            phone = clean_phone(extracted.get("phone_number"))
            if phone:
                enriched["phone"] = phone
                stats["phones"] += 1
                found_something = True

        # Delivery area
        if not v["delivery_area"]:
            area = extracted.get("delivery_area")
            if area and area.lower() not in ('n/a', 'none', 'unknown', ''):
                enriched["delivery_area"] = area
                stats["delivery_areas"] += 1
                found_something = True

        # Log what we found
        if found_something:
            results.append(enriched)
            stats["enriched"] += 1
            parts = []
            if enriched["image_url"]: parts.append("IMG")
            if enriched["email"]: parts.append("EMAIL")
            if enriched["instagram"]: parts.append("IG")
            if enriched["phone"]: parts.append("TEL")
            if enriched["delivery_area"]: parts.append("AREA")
            print(f"    FOUND: {', '.join(parts)}")
        else:
            print(f"    nothing new")

    # Save results
    if not args.dry_run:
        # JSON
        with open(OUTPUT_JSON, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved: {OUTPUT_JSON}")

        # SQL migration
        sql_lines = [
            "-- Neshama Vendor Enrichment via Firecrawl",
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
            if r["delivery_area"]:
                sets.append(f"delivery_area = '{sql_escape(r['delivery_area'])}'")
            if sets:
                sql_lines.append(
                    f"UPDATE vendors SET {', '.join(sets)} WHERE slug = '{slug}';"
                )
        sql_lines.append("")

        with open(OUTPUT_SQL, "w") as f:
            f.write("\n".join(sql_lines))
        print(f"Saved: {OUTPUT_SQL}")

    # Apply to DB
    if args.apply and results:
        print("\nApplying to local database...")
        conn = sqlite3.connect(DB_PATH)
        applied = 0
        for r in results:
            updates = {}
            if r["image_url"]:
                updates["image_url"] = r["image_url"]
            if r["email"]:
                updates["email"] = r["email"]
            if r["instagram"]:
                updates["instagram"] = r["instagram"]
            if r["phone"]:
                updates["phone"] = r["phone"]
            if r["delivery_area"]:
                updates["delivery_area"] = r["delivery_area"]
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                conn.execute(
                    f"UPDATE vendors SET {set_clause} WHERE slug = ?",
                    list(updates.values()) + [r["slug"]]
                )
                applied += 1
        conn.commit()
        conn.close()
        print(f"  Applied enrichment to {applied} vendors in {DB_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("  ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Total vendors:          {stats['total']}")
    print(f"  Skipped (complete):     {stats['skipped_complete']}")
    print(f"  Scraped via Firecrawl:  {stats['scraped']}")
    print(f"  Errors:                 {stats['errors']}")
    print(f"  Vendors enriched:       {stats['enriched']}")
    print(f"  ─────────────────────────────────")
    print(f"  Images found:           {stats['images']}")
    print(f"  Emails found:           {stats['emails']}")
    print(f"  Instagram handles:      {stats['instagrams']}")
    print(f"  Phone numbers:          {stats['phones']}")
    print(f"  Delivery areas:         {stats['delivery_areas']}")
    print(f"  ─────────────────────────────────")
    print(f"  Firecrawl credits used: {stats['credits_used']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
