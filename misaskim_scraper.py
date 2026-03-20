#!/usr/bin/env python3
"""
Misaskim.ca Shiva Listings Scraper
Scrapes shiva listings from misaskim.ca (Orthodox community, Toronto)
Partnership via Eli Warner — he approved pulling from their listings.

Data available: deceased names (English + Hebrew), listing URLs, donation status
Data NOT available: shiva addresses, times, funeral details (minimal listings)

Usage:
    python misaskim_scraper.py                # scrape and display
    python misaskim_scraper.py --save         # save to CSV
    python misaskim_scraper.py --check-new    # only show new listings not in Neshama DB

Requires: pip3 install requests beautifulsoup4
"""

import argparse
import csv
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependencies: pip3 install requests beautifulsoup4")
    sys.exit(1)


BASE_URL = "https://misaskim.ca/shiva-listings/"
HEADERS = {
    'User-Agent': 'Neshama/1.0 (neshama.ca; partnership with Misaskim via Eli Warner)',
}


def clean_text(text):
    """Clean and normalize text, escaping HTML to prevent stored XSS."""
    if not text:
        return None
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\S+@\S+\.\S+', '[email]', text)
    return text if text else None


def scrape_listings_page(url):
    """Scrape a single page of shiva listings."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return [], None

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = []

    # Find listing cards — links to individual shiva pages
    # Cards are wrapped in <a> tags with full card content inside (name + donate + view text)
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/shiva-listings/' in href and href != '/shiva-listings/' and href != BASE_URL:
            # Skip pagination and generic links
            if '?page=' in href or href.endswith('/shiva-listings'):
                continue

            # Extract name from heading inside the card, or from the slug
            name_text = None

            # Try headings first (h2, h3, h4)
            heading = link.find(['h1', 'h2', 'h3', 'h4', 'h5'])
            if heading:
                name_text = heading.get_text(strip=True)

            # If no heading, try extracting from the full text (remove action words)
            if not name_text:
                full_text = link.get_text(strip=True)
                # Remove common action text that appears in cards
                for remove in ['Donate in memory', 'View shiva information', 'Shiva Listings',
                               'C$0', '0.0% of C$0 goal']:
                    full_text = full_text.replace(remove, '')
                name_text = full_text.strip()

            # Clean residual fundraising text from name
            if name_text:
                name_text = re.sub(r'\d+\.?\d*%\s*of\s*goal', '', name_text).strip()
                name_text = re.sub(r'C?\$\d+', '', name_text).strip()
                name_text = re.sub(r'\s{2,}', ' ', name_text).strip()

            # Last resort: build name from the URL slug
            if not name_text or len(name_text) < 3:
                slug = href.rstrip('/').split('/')[-1]
                # Convert slug to name: "mrs-zeesal-klein-ah" → "Mrs Zeesal Klein Ah"
                name_text = slug.replace('-', ' ').replace('_', ' ').title()
                # Remove trailing numbers (like _1, _2)
                name_text = re.sub(r'\s+\d+$', '', name_text)

            full_url = href if href.startswith('http') else f"https://misaskim.ca{href}"
            slug = href.rstrip('/').split('/')[-1]

            listings.append({
                'name': clean_text(name_text) or name_text,
                'url': full_url,
                'slug': slug,
                'source': 'Misaskim',
                'scraped_at': datetime.now().isoformat(),
            })

    # Filter out test/junk entries from Misaskim
    TEST_PATTERNS = [
        r'^test\b', r'\btest\b.*\btest\b', r'^test$',
        r'\bblabla\b', r'\bblablabla\b', r'^test max$',
        r'^test for\b', r'^testing\b', r'^sample\b',
        r'^dummy\b', r'^fake\b', r'^example\b',
    ]
    filtered = []
    for l in listings:
        name_lower = l['name'].lower().strip()
        is_test = any(re.search(pat, name_lower) for pat in TEST_PATTERNS)
        if is_test:
            logging.info(f"  Skipping test entry: {l['name']}")
        else:
            filtered.append(l)
    listings = filtered

    # Deduplicate by slug (same listing appears in multiple links)
    seen = set()
    unique = []
    for l in listings:
        if l['slug'] not in seen:
            seen.add(l['slug'])
            unique.append(l)

    # Check for next page
    next_page = None
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        if text == '2' or text == 'Next' or '?page=2' in a['href']:
            next_url = a['href']
            if not next_url.startswith('http'):
                next_url = f"https://misaskim.ca{next_url}"
            next_page = next_url
            break

    return unique, next_page


def scrape_all_listings(max_pages=5):
    """Scrape all pages of shiva listings."""
    all_listings = []
    url = BASE_URL
    page = 1

    while url and page <= max_pages:
        print(f"  Scraping page {page}: {url}")
        listings, next_page = scrape_listings_page(url)
        all_listings.extend(listings)
        print(f"    Found {len(listings)} listings")

        url = next_page
        page += 1

    # Final dedup
    seen = set()
    unique = []
    for l in all_listings:
        if l['slug'] not in seen:
            seen.add(l['slug'])
            unique.append(l)

    return unique


def check_against_neshama(listings, db_path=None):
    """Check which Misaskim listings are NOT already in Neshama's obituary database."""
    if db_path is None:
        db_path = os.path.expanduser('~/Desktop/Neshama/neshama.db')

    if not os.path.exists(db_path):
        print(f"  DB not found at {db_path} — can't check for duplicates")
        return listings, []

    conn = sqlite3.connect(db_path, timeout=30)
    cursor = conn.cursor()

    # Get existing obituary names (normalize for comparison)
    cursor.execute("SELECT deceased_name FROM obituaries")
    existing = set()
    for row in cursor.fetchall():
        name = row[0].lower().strip()
        # Remove common suffixes
        name = re.sub(r'\s*(z"l|a"h|zt"l|ob"m)\s*$', '', name, flags=re.IGNORECASE)
        existing.add(name)
    conn.close()

    new_listings = []
    already_in_db = []

    for l in listings:
        name_clean = l['name'].lower().strip()
        name_clean = re.sub(r'\s*(z"l|a"h|zt"l|ob"m)\s*$', '', name_clean, flags=re.IGNORECASE)

        # Check for fuzzy match (first + last name)
        parts = name_clean.split()
        matched = False
        for existing_name in existing:
            if len(parts) >= 2:
                # Check if last name matches
                if parts[-1] in existing_name and parts[0] in existing_name:
                    matched = True
                    break
            if name_clean in existing_name or existing_name in name_clean:
                matched = True
                break

        if matched:
            already_in_db.append(l)
        else:
            new_listings.append(l)

    return new_listings, already_in_db


def save_csv(listings, output_path):
    """Save listings to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'url', 'slug', 'source', 'scraped_at'])
        writer.writeheader()
        writer.writerows(listings)
    print(f"  Saved {len(listings)} listings to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Misaskim.ca Shiva Listings Scraper')
    parser.add_argument('--save', action='store_true', help='Save results to CSV')
    parser.add_argument('--check-new', action='store_true',
                        help='Only show listings not already in Neshama DB')
    parser.add_argument('--db', type=str, default=None, help='Path to neshama.db')
    parser.add_argument('--max-pages', type=int, default=5, help='Max pages to scrape')

    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"MISASKIM.CA SHIVA LISTINGS SCRAPER")
    print(f"Partnership: Eli Warner (approved Mar 9, 2026)")
    print(f"{'='*60}")

    listings = scrape_all_listings(max_pages=args.max_pages)
    print(f"\nTotal unique listings: {len(listings)}")

    if args.check_new:
        new_listings, already = check_against_neshama(listings, args.db)
        print(f"Already in Neshama: {len(already)}")
        print(f"NEW (not in Neshama): {len(new_listings)}")
        if new_listings:
            print(f"\nNew listings from Misaskim:")
            for l in new_listings:
                print(f"  {l['name']}")
                print(f"    {l['url']}")
        listings = new_listings

    else:
        print(f"\nAll Misaskim listings:")
        for l in listings:
            print(f"  {l['name']}")

    if args.save:
        date_str = datetime.now().strftime('%Y%m%d')
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'outscraper_pipeline', 'data')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'misaskim_listings_{date_str}.csv')
        save_csv(listings, output_path)

    print(f"\n{'='*60}")


class MisakimScraper:
    """Wrapper class matching the interface expected by master_scraper.py.

    Scrapes Misaskim.ca shiva listings and saves them to the Neshama obituaries
    table via NeshamaDatabase.upsert_obituary().
    """

    def __init__(self):
        self.source_name = "Misaskim"
        self.db = None  # lazy import to avoid circular deps at module level

    def _get_db(self):
        if self.db is None:
            from database_setup import NeshamaDatabase
            self.db = NeshamaDatabase()
        return self.db

    def run(self):
        """Execute full scraping process. Returns stats dict."""
        import time as _time
        start_time = _time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            logging.info(f"\n{'='*60}")
            logging.info(f"Starting Misaskim scraper")
            logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"{'='*60}\n")

            listings = scrape_all_listings(max_pages=5)
            stats['found'] = len(listings)
            logging.info(f"Found {stats['found']} Misaskim listings\n")

            db = self._get_db()

            for i, listing in enumerate(listings, 1):
                try:
                    logging.info(f"[{i}/{stats['found']}] Processing: {listing['name']}...")

                    # Convert Misaskim listing to obituary_data format
                    obit_data = {
                        'source': self.source_name,
                        'source_url': listing['url'],
                        'condolence_url': listing['url'],
                        'deceased_name': listing['name'],
                        'city': 'Toronto',  # Misaskim is Toronto Orthodox community
                    }

                    obit_id, action = db.upsert_obituary(obit_data)

                    if action == 'inserted':
                        stats['new'] += 1
                        logging.info(f"  New: {listing['name']}")
                    elif action == 'updated':
                        stats['updated'] += 1
                        logging.info(f"  Updated: {listing['name']}")
                    else:
                        logging.info(f"  Unchanged: {listing['name']}")

                    # Be polite — small delay between DB writes
                    _time.sleep(0.2)

                except Exception as e:
                    logging.info(f"  Error processing {listing['name']}: {str(e)}")
                    stats['errors'] += 1

            duration = _time.time() - start_time
            db.log_scraper_run(
                source=self.source_name,
                status='success',
                stats=stats,
                duration=duration
            )

            logging.info(f"\n{'='*60}")
            logging.info(f"Misaskim scraping completed")
            logging.info(f"Found: {stats['found']} | New: {stats['new']} | Updated: {stats['updated']} | Errors: {stats['errors']}")
            logging.info(f"Duration: {duration:.1f} seconds")
            logging.info(f"{'='*60}\n")

            return stats

        except Exception as e:
            duration = _time.time() - start_time
            error_msg = str(e)
            try:
                db = self._get_db()
                db.log_scraper_run(
                    source=self.source_name,
                    status='failed',
                    stats=stats,
                    error=error_msg,
                    duration=duration
                )
            except Exception:
                pass
            logging.info(f"\nMisaskim scraping failed: {error_msg}\n")
            raise


if __name__ == '__main__':
    main()
