#!/usr/bin/env python3
"""
Audit Image Extractor — MVP (Phase 1)
======================================
Reads Jordana's vendor photo audit CSV. For every row where
Image Status == "Replace" AND "New Image URL" is present, scrapes that
source URL via Firecrawl and extracts candidate image URLs.

No Vision pass. No DB writes. Pure local JSON output for Erin to review.

Usage:
  export FIRECRAWL_API_KEY=fc-...
  python3 outscraper_pipeline/extract_audit_images.py --dry-run
  python3 outscraper_pipeline/extract_audit_images.py --limit 10
  python3 outscraper_pipeline/extract_audit_images.py --start 10 --limit 10
  python3 outscraper_pipeline/extract_audit_images.py            # all 87
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

try:
    from firecrawl import FirecrawlApp
except ImportError:
    print("ERROR: pip3 install firecrawl-py")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = "/Users/erinkofman/Desktop/Neshama_Vendor_Photo_Audit/Vendor Audit-Table 1.csv"
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "audit_image_candidates.json")

DELAY_SECONDS = 1.5
SCRAPE_TIMEOUT_MS = 30000
TOP_N = 3

JUNK_IMAGE_PATTERNS = [
    # Existing patterns carried from enrich_vendors_images.py
    'placeholder', 'default', 'blank', 'spacer', '1x1', 'pixel',
    'facebook.com', 'twitter.com', 'google.com/images',
    'shopify.com/s/files', 'cdn.shopify.com/shopifycloud',
    'gravatar.com', 'wp-content/plugins',
    # Extensions for MVP
    'favicon', 'sprite', '/emoji/', 'emoji.', 'apple-touch-icon',
    'logo', 'brandmark', 'watermark',  # broad — catches bistrograndelogo-black etc.
    'icon.', '-icon', '_icon', '/icon/', '/icons/',
    # Kashrut certification marks (COR, MK, OU, etc.) — not food
    '/cor.', '/cor1', '/cor2', '/cor3', '/cor4', '/cor5', '/cor6',
    '-cor.', '_cor.', 'cor-certified', 'cor_certified',
    '/mk.', '-mk.', '_mk.', '/mk-', 'kashrut', 'kosher-cert', 'certified.',
    # Tiny dimension hints
    '-16x16', '-32x32', '-48x48', '-64x64', '-96x96', '-128x128',
    '-150x150', '-75x75', '_thumb', '_s.jpg', '_s.png',
    # Instagram UI / system assets
    'static.cdninstagram.com/rsrc',
    'instagram.com/static',
    # Google Maps static tiles
    'maps.googleapis.com/maps/api/staticmap',
    'maps.gstatic.com',
    # Tracking pixels / analytics
    'doubleclick.net', 'googletagmanager', 'google-analytics',
    'segment.io', 'mixpanel',
]


def classify_url(url: str) -> str:
    u = url.lower()
    if 'instagram.com' in u:
        return 'instagram'
    if 'google.com/maps' in u or 'maps.app.goo.gl' in u or 'g.page' in u:
        return 'gmb'
    if 'facebook.com' in u:
        return 'facebook'
    return 'website'


def is_valid_image(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    if not url.startswith(('http://', 'https://')):
        return False
    low = url.lower()
    for pat in JUNK_IMAGE_PATTERNS:
        if pat in low:
            return False
    return True


def absolutize(base: str, src: str) -> str:
    try:
        return urljoin(base, src)
    except Exception:
        return src


def extract_img_urls_from_html(html: str, base: str) -> list[str]:
    """Pull every <img src=...> and data-src=... from raw HTML. Ordered, deduped."""
    if not html:
        return []
    out: list[str] = []
    seen: set[str] = set()
    # src + data-src + srcset (take first URL from srcset)
    patterns = [
        r'<img[^>]+?src=["\']([^"\']+)["\']',
        r'<img[^>]+?data-src=["\']([^"\']+)["\']',
        r'<img[^>]+?data-lazy-src=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html, flags=re.IGNORECASE):
            raw = m.group(1).strip()
            if not raw:
                continue
            url = absolutize(base, raw)
            if url not in seen:
                seen.add(url)
                out.append(url)
    # og:image as backup if metadata parser missed it
    for m in re.finditer(
        r'<meta[^>]+?property=["\']og:image["\'][^>]+?content=["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE,
    ):
        url = absolutize(base, m.group(1).strip())
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def rank_candidates(og_image: str | None, html_imgs: list[str]) -> list[dict]:
    """Return up to TOP_N candidates in rank order. og:image first, then HTML order."""
    ranked: list[dict] = []
    seen: set[str] = set()

    if og_image and is_valid_image(og_image):
        ranked.append({"url": og_image, "source": "og_image", "rank": 1})
        seen.add(og_image)

    for url in html_imgs:
        if len(ranked) >= TOP_N:
            break
        if url in seen:
            continue
        if not is_valid_image(url):
            continue
        ranked.append({
            "url": url,
            "source": "img_tag",
            "rank": len(ranked) + 1,
        })
        seen.add(url)

    return ranked


def load_audit_rows(csv_path: str) -> list[dict]:
    """Header row is line 3 of the CSV (two metadata rows precede it)."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 4:
        raise ValueError(f"CSV looks empty or malformed: {csv_path}")

    header = rows[2]
    data_rows = rows[3:]

    out: list[dict] = []
    for r in data_rows:
        if not any(cell.strip() for cell in r):
            continue
        record = {header[i].strip(): (r[i].strip() if i < len(r) else "")
                  for i in range(len(header))}
        out.append(record)
    return out


def _first_url(raw: str) -> str:
    """Cells sometimes contain 'https://x.com/, @handle' — take the first http URL."""
    if not raw:
        return ""
    m = re.search(r'https?://[^\s,;]+', raw)
    return m.group(0).rstrip('.,;') if m else raw.strip()


def filter_to_replace_with_source(rows: list[dict]) -> list[dict]:
    picked: list[dict] = []
    for r in rows:
        status = r.get("Image Status", "").strip().lower()
        raw = r.get("New Image URL", "").strip()
        first = _first_url(raw)
        if status == "replace" and first.startswith("http"):
            r["New Image URL"] = first
            picked.append(r)
    return picked


def scrape_one(app: FirecrawlApp, url: str) -> tuple[dict | None, str | None]:
    """Return (result, error). result is raw Firecrawl result object wrapped via getattr."""
    try:
        result = app.scrape(url, formats=["markdown", "html"], timeout=SCRAPE_TIMEOUT_MS)
        return result, None
    except Exception as e:
        return None, str(e)[:200]


def extract_from_result(result, source_url: str) -> tuple[str | None, list[str]]:
    """Return (og_image, html_img_urls)."""
    og_image = None
    if hasattr(result, 'metadata') and result.metadata is not None:
        meta = result.metadata
        # Firecrawl returns og:image under several possible attrs
        for attr in ('og_image', 'ogImage', 'og:image'):
            val = getattr(meta, attr, None) if hasattr(meta, attr) else None
            if val:
                og_image = val
                break
        # dict-style fallback
        if og_image is None and isinstance(meta, dict):
            og_image = meta.get('og_image') or meta.get('ogImage') or meta.get('og:image')

    html = getattr(result, 'html', '') or ''
    html_imgs = extract_img_urls_from_html(html, source_url)
    return og_image, html_imgs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to audit CSV")
    parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = all)")
    parser.add_argument("--start", type=int, default=0, help="Skip first N eligible rows")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse CSV, classify URLs, print plan. No Firecrawl.")
    parser.add_argument("--output", default=OUTPUT_JSON, help="Output JSON path")
    args = parser.parse_args()

    print("=" * 70)
    print("  Audit Image Extractor — MVP (no Vision, no DB writes)")
    print("=" * 70)
    print(f"  CSV:    {args.csv}")
    print(f"  Output: {args.output}")
    print()

    # 1. Load + filter
    try:
        all_rows = load_audit_rows(args.csv)
    except Exception as e:
        print(f"ERROR reading CSV: {e}")
        sys.exit(1)

    eligible = filter_to_replace_with_source(all_rows)
    print(f"  Total CSV rows:            {len(all_rows)}")
    print(f"  Eligible (Replace + URL):  {len(eligible)}")

    # 2. URL-type breakdown
    type_counts: dict[str, int] = {}
    for r in eligible:
        t = classify_url(r["New Image URL"])
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"  URL types: {type_counts}")
    print()

    # 3. Apply slice
    work = eligible[args.start:]
    if args.limit:
        work = work[:args.limit]
    print(f"  Processing: {len(work)} rows"
          f" (start={args.start}, limit={args.limit or 'all'})")
    print()

    if args.dry_run:
        print("  --dry-run: skipping Firecrawl. Sample rows:")
        for r in work[:5]:
            print(f"    [{classify_url(r['New Image URL'])}] "
                  f"{r.get('Vendor Name', '?')} → {r['New Image URL'][:80]}")
        if len(work) > 5:
            print(f"    ... and {len(work) - 5} more")
        print("\nDry run complete. No network calls made.")
        return

    # 4. Firecrawl init — env var first, then .firecrawl.env file next to this script
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        key_file = os.path.join(SCRIPT_DIR, ".firecrawl.env")
        if os.path.exists(key_file):
            with open(key_file) as f:
                api_key = f.read().strip()
    if not api_key or api_key.startswith("PASTE_"):
        print("ERROR: FIRECRAWL_API_KEY not set.")
        print(f"  Paste your key into: {os.path.join(SCRIPT_DIR, '.firecrawl.env')}")
        print(f"  Or: export FIRECRAWL_API_KEY=fc-... then re-run")
        sys.exit(1)

    app = FirecrawlApp(api_key=api_key)

    # 5. Process
    results: list[dict] = []
    stats = {
        "processed": 0, "ok": 0, "no_candidates": 0, "scrape_error": 0,
        "credits_used": 0,
    }

    for i, row in enumerate(work):
        vendor = row.get("Vendor Name", "?")
        city = row.get("City", "")
        source_url = row["New Image URL"]
        url_type = classify_url(source_url)

        if i > 0:
            time.sleep(DELAY_SECONDS)

        print(f"  [{i+1}/{len(work)}] [{url_type}] {vendor} → {source_url[:70]}")

        result_obj, err = scrape_one(app, source_url)
        stats["processed"] += 1
        stats["credits_used"] += 1

        record: dict = {
            "vendor_name": vendor,
            "city": city,
            "source_url": source_url,
            "url_type": url_type,
            "candidates": [],
            "status": "ok",
            "error": None,
        }

        if err:
            record["status"] = "scrape_error"
            record["error"] = err
            stats["scrape_error"] += 1
            print(f"      ERROR: {err}")
            results.append(record)
            continue

        og_image, html_imgs = extract_from_result(result_obj, source_url)
        candidates = rank_candidates(og_image, html_imgs)
        record["candidates"] = candidates

        if not candidates:
            record["status"] = "no_candidates"
            stats["no_candidates"] += 1
            print(f"      no valid candidates")
        else:
            stats["ok"] += 1
            print(f"      found {len(candidates)} "
                  f"({'og+' if og_image else ''}{len(html_imgs)} html)")

        results.append(record)

    # 6. Write JSON
    with open(args.output, "w") as f:
        json.dump({
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "csv_source": args.csv,
            "stats": stats,
            "results": results,
        }, f, indent=2)
    print(f"\n  Saved: {args.output}")

    # 7. Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Processed:         {stats['processed']}")
    print(f"  Candidates found:  {stats['ok']}")
    print(f"  No candidates:     {stats['no_candidates']}")
    print(f"  Scrape errors:     {stats['scrape_error']}")
    print(f"  Firecrawl credits: {stats['credits_used']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
