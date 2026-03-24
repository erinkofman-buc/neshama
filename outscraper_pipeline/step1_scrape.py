#!/usr/bin/env python3
"""
Neshama Vendor Pipeline — Step 1: Outscraper Raw Scrape
Pulls Google Maps business data for Jewish community vendors.

Usage:
    python step1_scrape.py --category shiva --city toronto
    python step1_scrape.py --category bakeries --city montreal
    python step1_scrape.py --category all --city toronto
    python step1_scrape.py --category shiva --city south-florida
    python step1_scrape.py --category restaurants --city nyc
    python step1_scrape.py --keywords "kosher caterer Thornhill" --city toronto

Requires: pip install outscraper
API key: set OUTSCRAPER_API_KEY env var or pass --api-key
"""

import argparse
import csv
import os
import sys
from datetime import datetime

# Add parent directory to path for city_config import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from city_config import CITIES

try:
    from outscraper import ApiClient
except ImportError:
    print("Install outscraper: pip install outscraper")
    sys.exit(1)


# ── All valid city slugs (active + expansion) ──
# Expansion cities are defined here so keywords are ready when cities activate in city_config
ALL_CITY_SLUGS = list(CITIES.keys()) + ['south-florida', 'chicago', 'nyc', 'la']

# ── Region codes by city (for Outscraper API) ──
REGION_CODES = {slug: cfg['country'] for slug, cfg in CITIES.items()}
REGION_CODES.update({
    'south-florida': 'US',
    'chicago': 'US',
    'nyc': 'US',
    'la': 'US',
})


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
        'south-florida': [
            "shiva catering Boca Raton",
            "shiva catering Fort Lauderdale",
            "shiva meal delivery South Florida",
            "shiva platters Aventura",
            "bereavement catering Boca Raton",
            "kosher caterer Boca Raton",
            "kosher catering Hollywood FL",
            "kosher catering Sunny Isles",
            "kosher caterer Aventura",
            "kosher meal delivery Boca Raton",
        ],
        'chicago': [
            "shiva catering Skokie",
            "shiva catering Highland Park IL",
            "shiva catering Chicago",
            "shiva meal delivery Chicago",
            "kosher caterer Skokie",
            "kosher catering Chicago",
            "kosher catering Northbrook IL",
            "bereavement catering Chicago",
        ],
        'nyc': [
            "shiva catering Manhattan",
            "shiva catering Brooklyn",
            "shiva meal delivery New York",
            "shiva platters Great Neck",
            "shiva catering Five Towns",
            "kosher caterer Brooklyn",
            "kosher catering Manhattan",
            "kosher catering Teaneck",
            "bereavement catering New York",
        ],
        'la': [
            "shiva catering Beverly Hills",
            "shiva catering Pico Robertson",
            "shiva catering Los Angeles",
            "shiva meal delivery Encino",
            "kosher caterer Beverly Hills",
            "kosher catering Los Angeles",
            "kosher catering Tarzana",
            "bereavement catering Los Angeles",
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
        'south-florida': [
            "kosher bakery Boca Raton",
            "Jewish bakery Aventura",
            "kosher bakery Hollywood FL",
            "challah delivery Boca Raton",
            "best kosher bakery South Florida",
        ],
        'chicago': [
            "kosher bakery Skokie",
            "kosher bakery Chicago",
            "Jewish bakery Highland Park IL",
            "challah delivery Chicago",
        ],
        'nyc': [
            "kosher bakery Brooklyn",
            "kosher bakery Manhattan",
            "Jewish bakery Great Neck",
            "challah delivery New York",
            "best kosher bakery Brooklyn",
        ],
        'la': [
            "kosher bakery Beverly Hills",
            "kosher bakery Pico Robertson",
            "Jewish bakery Los Angeles",
            "challah delivery Encino",
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
        'south-florida': [
            "gift basket Boca Raton",
            "shiva gift basket Fort Lauderdale",
            "kosher gift basket Aventura",
            "bereavement gift basket Boca Raton",
            "condolence gift South Florida",
            "fruit basket delivery Hollywood FL",
        ],
        'chicago': [
            "gift basket Chicago",
            "shiva gift basket Skokie",
            "kosher gift basket Chicago",
            "condolence gift basket Highland Park IL",
        ],
        'nyc': [
            "gift basket Five Towns",
            "shiva gift basket Manhattan",
            "kosher gift basket Brooklyn",
            "condolence gift New York",
            "bereavement gift basket Great Neck",
        ],
        'la': [
            "gift basket Beverly Hills",
            "shiva gift basket Los Angeles",
            "kosher gift basket Pico Robertson",
            "condolence gift Encino",
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
        'south-florida': [
            "Judaica store Boca Raton",
            "Judaica shop Aventura",
            "Jewish bookstore Fort Lauderdale",
            "shiva candles Boca Raton",
        ],
        'chicago': [
            "Judaica store Skokie",
            "Jewish bookstore Chicago",
            "Judaica shop Highland Park IL",
        ],
        'nyc': [
            "Judaica store Brooklyn",
            "Judaica shop Manhattan",
            "Jewish bookstore Great Neck",
            "Judaica store Five Towns",
        ],
        'la': [
            "Judaica store Beverly Hills",
            "Judaica shop Pico Robertson",
            "Jewish bookstore Los Angeles",
        ],
    },
    # Services that help with shiva logistics
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
        'south-florida': [
            "shiva home setup Boca Raton",
            "chair rental Fort Lauderdale Jewish",
            "event rental Aventura kosher",
        ],
        'chicago': [
            "shiva home setup Chicago",
            "chair rental Skokie Jewish",
        ],
        'nyc': [
            "shiva home setup Manhattan",
            "chair rental Brooklyn Jewish",
            "event rental Five Towns kosher",
        ],
        'la': [
            "shiva home setup Beverly Hills",
            "chair rental Los Angeles Jewish",
        ],
    },
    # Restaurants & delis (expansion cities get dedicated keywords)
    'restaurants': {
        'south-florida': [
            "kosher restaurant Aventura",
            "kosher restaurant Boca Raton",
            "Jewish deli Hollywood FL",
            "kosher deli Boca Raton",
            "kosher restaurant Sunny Isles",
        ],
        'chicago': [
            "kosher restaurant Chicago",
            "kosher restaurant Skokie",
            "kosher deli Chicago",
            "Jewish deli Skokie",
        ],
        'nyc': [
            "kosher deli Great Neck",
            "kosher restaurant Brooklyn",
            "kosher restaurant Manhattan",
            "Jewish deli Five Towns",
            "kosher restaurant Forest Hills",
        ],
        'la': [
            "kosher restaurant Encino",
            "kosher restaurant Beverly Hills",
            "kosher restaurant Pico Robertson",
            "kosher deli Los Angeles",
        ],
    },
}


def scrape_google_maps(api_key, queries, limit_per_query=50, region='CA'):
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
                region=region,
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
    all_categories = list(KEYWORDS.keys())
    parser = argparse.ArgumentParser(description='Neshama Outscraper Pipeline — Step 1')
    parser.add_argument('--category', choices=all_categories + ['all'],
                        default='shiva', help='Vendor category to scrape')
    parser.add_argument('--city', choices=ALL_CITY_SLUGS + ['all'],
                        default='toronto', help='City to scrape (any city from city_config)')
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
        categories = all_categories if args.category == 'all' else [args.category]
        cities = ALL_CITY_SLUGS if args.city == 'all' else [args.city]
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

    # Determine region code for Outscraper API
    region = REGION_CODES.get(args.city, 'US') if args.city != 'all' else 'US'

    # Scrape
    raw_results = scrape_google_maps(api_key, queries, limit_per_query=args.limit, region=region)
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
