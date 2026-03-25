#!/usr/bin/env python3
"""
Vendor Data Enrichment Script for Neshama
==========================================
Scrapes vendor websites to extract:
  - og:image / twitter:image  -> image_url
  - Instagram links           -> instagram handle
  - Phone numbers (if missing) -> phone

Outputs:
  - vendor_enrichment.json  (structured results)
  - vendor_enrichment.sql   (migration statements)

Usage: python3 outscraper_pipeline/enrich_vendors.py
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "vendor_enrichment.json")
OUTPUT_SQL = os.path.join(SCRIPT_DIR, "vendor_enrichment.sql")

FOOD_API = "https://neshama.ca/api/vendors"
GIFT_API = "https://neshama.ca/api/gift-vendors"

TIMEOUT = 10
DELAY = 1

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Relaxed SSL context for sites with certificate issues
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------------------
# HTML parser to extract meta tags, instagram links, and tel: links
# ---------------------------------------------------------------------------
class VendorPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image = None
        self.twitter_image = None
        self.instagram_handles = []
        self.phone_numbers = []
        self.email_addresses = []
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k.lower(): v for k, v in attrs if k}

        # Meta tags (og:image, twitter:image)
        if tag == "meta":
            prop = attrs_dict.get("property", "") or attrs_dict.get("name", "")
            content = attrs_dict.get("content", "")
            if prop.lower() == "og:image" and content:
                self.og_image = content
            elif prop.lower() == "twitter:image" and content:
                self.twitter_image = content

        # Links
        if tag == "a":
            href = attrs_dict.get("href", "") or ""

            # Instagram
            if "instagram.com/" in href.lower():
                match = re.search(
                    r"instagram\.com/([A-Za-z0-9_.]+)", href, re.IGNORECASE
                )
                if match:
                    handle = match.group(1).lower()
                    if handle not in (
                        "p", "reel", "reels", "explore", "stories",
                        "accounts", "about", "developer", "legal",
                    ):
                        self.instagram_handles.append(handle)

            # Email (mailto: links)
            if href.lower().startswith("mailto:"):
                email = href[7:].split("?")[0].strip().lower()
                if "@" in email and "." in email.split("@")[1]:
                    if email not in self.email_addresses:
                        self.email_addresses.append(email)

            # Phone (tel: links)
            if href.lower().startswith("tel:"):
                raw = href[4:].strip()
                cleaned = re.sub(r"[^\d+]", "", raw)
                if len(cleaned) >= 7:
                    self.phone_numbers.append(raw)

    def handle_data(self, data):
        # Also find emails in page text (not just mailto links)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', data)
        for e in emails:
            e = e.lower()
            if e not in self.email_addresses and not e.endswith('.png') and not e.endswith('.jpg'):
                self.email_addresses.append(e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as resp:
        raw = resp.read()
        # Try utf-8, fall back to latin-1
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="replace")


def format_phone(raw: str) -> str:
    """Try to format as (XXX) XXX-XXXX for 10-digit North American numbers."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw  # Return as-is if not standard NA format


PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)


def extract_phone_from_text(html: str) -> str | None:
    """Fallback: find phone numbers in page text via regex."""
    matches = PHONE_PATTERN.findall(html)
    for m in matches:
        digits = re.sub(r"\D", "", m)
        if digits.startswith("1") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10:
            return format_phone(m)
    return None


def sql_escape(val: str) -> str:
    return val.replace("'", "''")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Neshama Vendor Enrichment Script")
    print("=" * 60)

    # 1. Fetch all vendors
    print("\nFetching vendors from API...")
    food = fetch_json(FOOD_API).get("data", [])
    gift = fetch_json(GIFT_API).get("data", [])
    all_vendors = food + gift
    print(f"  Food vendors: {len(food)}")
    print(f"  Gift vendors: {len(gift)}")
    print(f"  Total: {len(all_vendors)}")

    # 2. Enrich
    results = []
    stats = {"total": 0, "skipped_no_website": 0, "errors": 0,
             "images": 0, "instagrams": 0, "phones": 0, "enriched": 0}

    for i, v in enumerate(all_vendors):
        slug = v.get("slug", "")
        name = v.get("name", "")
        website = (v.get("website") or "").strip()
        existing_image = v.get("image_url") or ""
        existing_ig = v.get("instagram") or ""
        existing_phone = (v.get("phone") or "").strip()

        stats["total"] += 1

        if not website or website.lower() in ("", "n/a", "none"):
            stats["skipped_no_website"] += 1
            continue

        # Polite delay (skip before first request)
        if i > 0:
            time.sleep(DELAY)

        print(f"  [{i+1}/{len(all_vendors)}] {name} — {website} ...", end=" ", flush=True)

        try:
            html = fetch_html(website)
        except Exception as e:
            err_msg = str(e)[:80]
            print(f"ERROR: {err_msg}")
            stats["errors"] += 1
            continue

        # Parse
        parser = VendorPageParser()
        try:
            parser.feed(html)
        except Exception:
            print("PARSE ERROR")
            stats["errors"] += 1
            continue

        enriched = {
            "slug": slug,
            "name": name,
            "image_url": None,
            "instagram": None,
            "phone": None,
            "email": None,
            "source": "website_scrape",
        }
        found_something = False

        # Image (only if vendor currently has none)
        if not existing_image:
            img = parser.og_image or parser.twitter_image
            if img:
                # Make absolute if relative
                if img.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(website)
                    img = f"{parsed.scheme}://{parsed.netloc}{img}"
                enriched["image_url"] = img
                stats["images"] += 1
                found_something = True

        # Instagram (only if vendor currently has none)
        if not existing_ig and parser.instagram_handles:
            handle = parser.instagram_handles[0]
            enriched["instagram"] = f"@{handle}"
            stats["instagrams"] += 1
            found_something = True

        # Phone (only if vendor currently has none)
        if not existing_phone:
            if parser.phone_numbers:
                enriched["phone"] = format_phone(parser.phone_numbers[0])
                stats["phones"] += 1
                found_something = True
            else:
                # Fallback: regex on page text
                phone = extract_phone_from_text(html)
                if phone:
                    enriched["phone"] = phone
                    stats["phones"] += 1
                    found_something = True

        # Email (only if vendor currently has none)
        existing_email = v.get("email")
        if not existing_email and parser.email_addresses:
            # Filter junk emails
            junk_patterns = [
                'user@domain', 'sentry-next', 'wixpress.com', 'gist-apps.com',
                'example.com', 'test@', 'noreply@', 'no-reply@',
                'support@shopify', 'support@squarespace',
            ]
            clean_emails = []
            for em in parser.email_addresses:
                em = em.lstrip(':').replace('%20', '').strip()
                if '@' not in em or '.' not in em.split('@')[1]:
                    continue
                if any(junk in em.lower() for junk in junk_patterns):
                    continue
                clean_emails.append(em)
            if clean_emails:
                enriched["email"] = clean_emails[0]
                stats.setdefault("emails", 0)
                stats["emails"] += 1
                found_something = True

        if found_something:
            results.append(enriched)
            stats["enriched"] += 1
            parts = []
            if enriched["image_url"]:
                parts.append("IMG")
            if enriched["instagram"]:
                parts.append("IG")
            if enriched["phone"]:
                parts.append("TEL")
            if enriched["email"]:
                parts.append("EMAIL")
            print(f"FOUND: {', '.join(parts)}")
        else:
            print("nothing new")

    # 3. Save JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved enrichment data to: {OUTPUT_JSON}")

    # 4. Generate SQL
    sql_lines = [
        "-- Neshama Vendor Enrichment Migration",
        f"-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"-- Vendors enriched: {stats['enriched']}",
        "",
    ]
    for r in results:
        slug = sql_escape(r["slug"])
        if r["image_url"]:
            val = sql_escape(r["image_url"])
            sql_lines.append(
                f"UPDATE vendors SET image_url = '{val}' "
                f"WHERE slug = '{slug}' AND image_url IS NULL;"
            )
        if r["instagram"]:
            val = sql_escape(r["instagram"])
            sql_lines.append(
                f"UPDATE vendors SET instagram = '{val}' "
                f"WHERE slug = '{slug}' AND (instagram IS NULL OR instagram = '');"
            )
        if r["phone"]:
            val = sql_escape(r["phone"])
            sql_lines.append(
                f"UPDATE vendors SET phone = '{val}' "
                f"WHERE slug = '{slug}' AND (phone IS NULL OR phone = '');"
            )
        if r.get("email"):
            val = sql_escape(r["email"])
            sql_lines.append(
                f"UPDATE vendors SET email = '{val}' "
                f"WHERE slug = '{slug}' AND (email IS NULL OR email = '');"
            )
        sql_lines.append("")  # blank line between vendors

    with open(OUTPUT_SQL, "w") as f:
        f.write("\n".join(sql_lines))
    print(f"Saved SQL migration to: {OUTPUT_SQL}")

    # 5. Summary
    print("\n" + "=" * 60)
    print("  ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Total vendors:         {stats['total']}")
    print(f"  Skipped (no website):  {stats['skipped_no_website']}")
    print(f"  Errors (fetch/parse):  {stats['errors']}")
    print(f"  Vendors enriched:      {stats['enriched']}")
    print(f"  ─────────────────────────────────")
    print(f"  Images found:          {stats['images']}")
    print(f"  Instagram handles:     {stats['instagrams']}")
    print(f"  Phone numbers:         {stats['phones']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
