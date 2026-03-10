#!/usr/bin/env python3
"""
Neshama Vendor Pipeline — Step 1: Outscraper Raw Scrape
Pulls Google Maps business data for Jewish community vendors.

Usage:
    python step1_scrape.py --category shiva --city toronto
    python step1_scrape.py --category bakeries --city montreal
    python step1_scrape.py --category all --city toronto
    python step1_scrape.py --keywords "kosher caterer Thornhill" --city toronto

Requires: pip install outscraper
API key: set OUTSCRAPER_API_KEY env var or pass --api-key
"""

import argparse
import csv
import os
import sys
from datetime import datetime

try:
    from outscraper import ApiClient
except ImportError:
    print("Install outscraper: pip install outscraper")
    sys.exit(1)


# ── Keyword definitions by category and city ──

KEYWORDS = {
    'shiva': {
        'toronto': [
            # High-intent shiva keywords
            "shiva catering Toronto",
            "shiva meal delivery Toronto",
            "shiva platters Toronto",
            "shiva food package Toronto",
            "bereavement catering Toronto",
            # Kosher catering with capacity signals
            "kosher caterer Toronto",
            "kosher catering large groups Toronto",
            "kosher platters delivery Toronto",
            "kosher meal delivery same day Toronto",
            "kosher comfort food delivery Toronto",
            # Neighbourhood-specific (where Jews live)
            "kosher caterer North York",
            "kosher caterer Thornhill",
            "kosher caterer Vaughan",
            "kosher caterer Bathurst Manor",
            "kosher catering Forest Hill",
            "kosher catering Lawrence Park",
            # Quality signals
            "best kosher caterer Toronto",
            "best kosher restaurant Toronto",
            "kosher deli catering Toronto",
        ],
        'montreal': [
            "shiva catering Montreal",
            "shiva meal delivery Montreal",
            "traiteur casher Montreal",
            "traiteur shiva Montreal",
            "kosher catering Montreal",
            "kosher meal delivery Montreal",
            "best kosher restaurant Montreal",
            "kosher caterer Cote-Saint-Luc",
            "kosher caterer Outremont",
            "kosher deli Montreal",
        ],
    },
    'bakeries': {
        'toronto': [
            "kosher bakery Toronto",
            "Jewish bakery Toronto",
            "challah delivery Toronto",
            "kosher bakery North York",
            "kosher bakery Thornhill",
            "kosher cookies delivery Toronto",
            "kosher cake delivery Toronto",
            "best kosher bakery Toronto",
            "shiva dessert platter Toronto",
        ],
        'montreal': [
            "kosher bakery Montreal",
            "Jewish bakery Montreal",
            "boulangerie casher Montreal",
            "challah delivery Montreal",
            "best kosher bakery Montreal",
        ],
    },
    'gifts': {
        'toronto': [
            "shiva gift basket Toronto",
            "shiva gift delivery Toronto",
            "bereavement gift basket Toronto",
            "condolence gift Toronto",
            "kosher gift basket Toronto",
            "sympathy gift basket Toronto",
            "kosher chocolate gift Toronto",
            "fruit basket delivery Toronto",
            "comfort food gift Toronto",
            "same day gift basket delivery Toronto",
        ],
        'montreal': [
            "shiva gift basket Montreal",
            "bereavement gift Montreal",
            "kosher gift basket Montreal",
            "condolence basket Montreal",
            "sympathy gift delivery Montreal",
        ],
    },
    'judaica': {
        'toronto': [
            "Judaica store Toronto",
            "Judaica shop North York",
            "Jewish bookstore Toronto",
            "shiva candles Toronto",
            "yahrzeit candle Toronto",
            "kippot Toronto",
            "Jewish memorial gifts Toronto",
        ],
        'montreal': [
            "Judaica Montreal",
            "Jewish bookstore Montreal",
            "Judaica store Cote-Saint-Luc",
        ],
    },
    # New category: services that help with shiva logistics
    'shiva_services': {
        'toronto': [
            "shiva home setup Toronto",
            "chair rental shiva Toronto",
            "folding chair rental Toronto Jewish",
            "event rental Toronto kosher",
            "shiva house cleaning Toronto",
        ],
        'montreal': [
            "shiva home setup Montreal",
            "chair rental Montreal Jewish",
        ],
    },
}


def scrape_google_maps(api_key, queries, limit_per_query=50):
    """Run Outscraper Google Maps search for each query."""
    client = ApiClient(api_key=api_key)
    all_results = []

    for i, query in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Scraping: {query}")
        try:
            results = client.google_maps_search(
                query,
                limit=limit_per_query,
                language='en',
                region='CA',
            )
            if results and len(results) > 0:
                # Outscraper returns list of lists
                batch = results[0] if isinstance(results[0], list) else results
                print(f"  Found {len(batch)} results")
                for r in batch:
                    r['source_keyword'] = query
                all_results.extend(batch)
            else:
                print(f"  No results")
        except Exception as e:
            print(f"  ERROR: {e}")

    return all_results


def deduplicate(results):
    """Deduplicate by place_id, keeping the first occurrence."""
    seen = set()
    unique = []
    for r in results:
        pid = r.get('place_id', r.get('name', ''))
        if pid not in seen:
            seen.add(pid)
            unique.append(r)
    return unique


def save_csv(results, output_path):
    """Save results to CSV with standard columns."""
    columns = [
        'name', 'full_address', 'city', 'state', 'postal_code',
        'phone', 'site', 'latitude', 'longitude',
        'rating', 'reviews', 'working_hours', 'place_id',
        'type', 'subtypes', 'category', 'description',
        'source_keyword',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for r in results:
            # Normalize field names (Outscraper uses various formats)
            row = {
                'name': r.get('name', ''),
                'full_address': r.get('full_address', r.get('address', '')),
                'city': r.get('city', ''),
                'state': r.get('state', r.get('province', '')),
                'postal_code': r.get('postal_code', ''),
                'phone': r.get('phone', ''),
                'site': r.get('site', r.get('website', '')),
                'latitude': r.get('latitude', ''),
                'longitude': r.get('longitude', ''),
                'rating': r.get('rating', ''),
                'reviews': r.get('reviews', r.get('reviews_count', '')),
                'working_hours': str(r.get('working_hours', '')),
                'place_id': r.get('place_id', ''),
                'type': r.get('type', ''),
                'subtypes': str(r.get('subtypes', '')),
                'category': r.get('category', ''),
                'description': r.get('description', ''),
                'source_keyword': r.get('source_keyword', ''),
            }
            writer.writerow(row)

    print(f"\nSaved {len(results)} rows to {output_path}")


def load_existing_vendors(db_path=None):
    """Load existing vendor names from the local database for dedup reference."""
    import sqlite3
    if db_path is None:
        db_path = os.path.expanduser('~/Desktop/Neshama/neshama.db')
    if not os.path.exists(db_path):
        print(f"  Local DB not found at {db_path} — skipping dedup check")
        return set()
    conn = sqlite3.connect(db_path)
    names = {row[0].lower().strip() for row in conn.execute("SELECT name FROM vendors").fetchall()}
    conn.close()
    return names


def main():
    parser = argparse.ArgumentParser(description='Neshama Outscraper Pipeline — Step 1')
    parser.add_argument('--category', choices=['shiva', 'bakeries', 'gifts', 'judaica', 'shiva_services', 'all'],
                        default='shiva', help='Vendor category to scrape')
    parser.add_argument('--city', choices=['toronto', 'montreal', 'both'],
                        default='toronto', help='City to scrape')
    parser.add_argument('--keywords', type=str, help='Custom keyword(s), comma-separated')
    parser.add_argument('--api-key', type=str, help='Outscraper API key (or set OUTSCRAPER_API_KEY)')
    parser.add_argument('--limit', type=int, default=50, help='Max results per keyword')
    parser.add_argument('--dry-run', action='store_true', help='Show keywords without scraping')

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('OUTSCRAPER_API_KEY', '')

    # Build keyword list
    if args.keywords:
        queries = [k.strip() for k in args.keywords.split(',')]
    else:
        categories = list(KEYWORDS.keys()) if args.category == 'all' else [args.category]
        cities = ['toronto', 'montreal'] if args.city == 'both' else [args.city]
        queries = []
        for cat in categories:
            for city in cities:
                queries.extend(KEYWORDS.get(cat, {}).get(city, []))

    if not queries:
        print("No keywords found for the given category/city combination.")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"NESHAMA OUTSCRAPER PIPELINE — STEP 1")
    print(f"Category: {args.category} | City: {args.city}")
    print(f"Keywords: {len(queries)}")
    print(f"{'='*60}")

    for i, q in enumerate(queries):
        print(f"  {i+1}. {q}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would scrape {len(queries)} keywords. Exiting.")
        sys.exit(0)

    if not api_key:
        print("\nERROR: No API key. Set OUTSCRAPER_API_KEY or pass --api-key")
        sys.exit(1)

    # Scrape
    raw_results = scrape_google_maps(api_key, queries, limit_per_query=args.limit)
    print(f"\nTotal raw results: {len(raw_results)}")

    # Deduplicate
    unique_results = deduplicate(raw_results)
    print(f"After dedup: {len(unique_results)}")

    # Check against existing vendors
    existing = load_existing_vendors()
    if existing:
        new_count = sum(1 for r in unique_results if r.get('name', '').lower().strip() not in existing)
        overlap_count = len(unique_results) - new_count
        print(f"Already in Neshama DB: {overlap_count}")
        print(f"New vendors: {new_count}")

    # Save
    date_str = datetime.now().strftime('%Y%m%d')
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'data',
        f'step1_raw_{args.category}_{args.city}_{date_str}.csv'
    )
    save_csv(unique_results, output_path)

    # Summary report
    report_path = output_path.replace('.csv', '_report.txt')
    with open(report_path, 'w') as f:
        f.write(f"Neshama Outscraper Pipeline — Step 1 Report\n")
        f.write(f"{'='*50}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Category: {args.category}\n")
        f.write(f"City: {args.city}\n")
        f.write(f"Keywords searched: {len(queries)}\n")
        f.write(f"Total raw results: {len(raw_results)}\n")
        f.write(f"After dedup: {len(unique_results)}\n")
        if existing:
            f.write(f"Already in Neshama: {overlap_count}\n")
            f.write(f"New vendors: {new_count}\n")
        f.write(f"\nOutput: {output_path}\n")
        f.write(f"\nNEXT STEP: Run step2_clean.py to clean and filter results.\n")
        f.write(f"REVIEW: Check the CSV before proceeding.\n")
    print(f"Report saved to {report_path}")
    print(f"\n{'='*60}")
    print(f"NEXT: Review the CSV, then run step2_clean.py")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
