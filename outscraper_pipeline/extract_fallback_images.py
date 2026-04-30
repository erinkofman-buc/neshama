#!/usr/bin/env python3
"""
Fallback Image Extractor — Phase 1b
====================================
Second-pass scraper for the 14 vendors where the primary audit source URL
returned no candidates or failed (Instagram, 404s, stock-photo searches).

URLs were picked via WebSearch on Apr 20, 2026. Preference order:
  1. Official website (most reliable with Firecrawl)
  2. Review blog (BlogTO, Tastet, Infatuation — scrapeable)
  3. Skip Yelp/Tripadvisor (they block scrapers)

Merges results into audit_image_candidates.json — adds `fallback_*` keys,
preserves original record.

Usage:
  python3 outscraper_pipeline/extract_fallback_images.py --dry-run
  python3 outscraper_pipeline/extract_fallback_images.py
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_audit_images import (
    DELAY_SECONDS, SCRIPT_DIR, extract_from_result, rank_candidates, scrape_one,
)

try:
    from firecrawl import FirecrawlApp
except ImportError:
    print("ERROR: pip3 install firecrawl-py")
    sys.exit(1)

JSON_PATH = os.path.join(SCRIPT_DIR, "audit_image_candidates.json")

# Vendor name → fallback URL. Picked via WebSearch Apr 20.
# Data corrections noted as `city_correction`.
FALLBACK_URLS = {
    "The Chicken Nest":         ("https://the-chicken-nest.grubbio.com/",                               None),
    "Milk 'N Honey":            ("https://milknhoney.ca/",                                              None),
    "Daiter's Kitchen":         ("https://www.daiterskitchen.ca/about-us/",                             None),
    "Parallel Brothers":        ("https://parallelbrothers.com/",                                       None),
    "Pickle Barrel":            ("https://picklebarrelcatering.com/menu/",                              None),
    "Cumbrae's":                ("https://www.cumbraes.com/",                                           None),
    "Ba-Li Laffa":              ("https://www.balilaffa.com/m/menus/main-course/",                      None),
    "Aroma Espresso Bar":       ("https://www.aromaespressobar.ca/aroma-menu/",                         None),
    "Haymishe Bakery":          ("https://www.haymishebakery.com/",                                     None),
    "Moishes":                  ("https://moishes.ca/en/",                                              None),
    "Arthurs Nosh Bar":         ("https://tastet.ca/en/reviews/arthurs-nosh-bar-a-dynamic-diner-in-saint-henri/", None),
    "Hof Kelsten":              ("https://tastet.ca/en/reviews/hof-kelsten-gourmet-bakery-on-st-laurent-boulevard/", None),
    "Linny's Luncheonette":     ("https://linnysluncheonette.com/",                                     "Toronto"),
    "Pantry Foods":             ("https://pantryfoods.ca/",                                             "Toronto"),
}


def load_key() -> str:
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        f = os.path.join(SCRIPT_DIR, ".firecrawl.env")
        if os.path.exists(f):
            with open(f) as fh:
                api_key = fh.read().strip()
    return api_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("  Fallback Image Extractor — Phase 1b")
    print("=" * 70)

    with open(JSON_PATH) as f:
        data = json.load(f)

    results_by_name = {r["vendor_name"]: r for r in data["results"]}

    missing = [name for name in FALLBACK_URLS if name not in results_by_name]
    if missing:
        print(f"  WARN: {len(missing)} names not in JSON: {missing}")

    targets = [(name, url, correction) for name, (url, correction) in FALLBACK_URLS.items()
               if name in results_by_name]
    print(f"  Fallbacks to process: {len(targets)}")

    if args.dry_run:
        for name, url, correction in targets:
            tag = f" [CITY FIX → {correction}]" if correction else ""
            print(f"    {name}{tag} → {url}")
        print("\n  Dry run. No network calls.")
        return

    api_key = load_key()
    if not api_key or api_key.startswith("PASTE_"):
        print("ERROR: FIRECRAWL_API_KEY not in env or .firecrawl.env")
        sys.exit(1)
    app = FirecrawlApp(api_key=api_key)

    stats = {"processed": 0, "ok": 0, "no_candidates": 0, "error": 0}

    for i, (name, url, correction) in enumerate(targets):
        if i > 0:
            time.sleep(DELAY_SECONDS)
        print(f"\n  [{i+1}/{len(targets)}] {name} → {url[:70]}")

        record = results_by_name[name]

        # Apply city correction if flagged
        if correction and record.get("city") != correction:
            print(f"    CITY CORRECTION: {record['city']} → {correction}")
            record["city_original"] = record["city"]
            record["city"] = correction
            record["city_corrected"] = True

        result_obj, err = scrape_one(app, url)
        stats["processed"] += 1

        record["fallback_url"] = url
        record["fallback_candidates"] = []

        if err:
            record["fallback_status"] = "scrape_error"
            record["fallback_error"] = err[:200]
            stats["error"] += 1
            print(f"      ERROR: {err[:120]}")
            continue

        og_image, html_imgs = extract_from_result(result_obj, url)
        candidates = rank_candidates(og_image, html_imgs)
        record["fallback_candidates"] = candidates
        record["fallback_error"] = None

        if not candidates:
            record["fallback_status"] = "no_candidates"
            stats["no_candidates"] += 1
            print(f"      no valid candidates")
        else:
            record["fallback_status"] = "ok"
            stats["ok"] += 1
            print(f"      found {len(candidates)}")

    # Update stats on main JSON
    data.setdefault("fallback_stats", {}).update(stats)
    data["fallback_generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Merged into: {JSON_PATH}")

    print("\n" + "=" * 70)
    print("  FALLBACK SUMMARY")
    print("=" * 70)
    print(f"  Processed:        {stats['processed']}")
    print(f"  Candidates found: {stats['ok']}")
    print(f"  No candidates:    {stats['no_candidates']}")
    print(f"  Scrape errors:    {stats['error']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
