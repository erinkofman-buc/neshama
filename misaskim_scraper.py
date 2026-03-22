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
# Use browser-like User-Agent — Misaskim runs WordPress/Elementor with LevCharity plugin
# which serves stripped-down HTML to bot User-Agents, omitting the campaign card blocks.
# A bot UA was returning only ~2 listings instead of all ~28.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


# Regex to strip honorific suffixes from names (A"H, Z"L, etc.)
# Handles: straight quotes, curly quotes, Hebrew geresh (״), double prime (″),
# no quotes at all (AH, ZL), spaces between letters and quote, and Hebrew ע"ה
_QUOTE = r'[\u0022\u0027\u2018\u2019\u201c\u201d\u201e\u05f4\u2033\u02bc]'
_HONORIFIC_SUFFIX_RE = re.compile(
    r'\s*(?:'
    r'z\s*' + _QUOTE + r'?\s*l'        # z"l  — zichrono livracha
    r'|a\s*' + _QUOTE + r'?\s*h'       # a"h  — alav/aleha hashalom
    r'|zt\s*' + _QUOTE + r'?\s*l'      # zt"l — zecher tzaddik livracha
    r'|ob\s*' + _QUOTE + r'?\s*m'      # ob"m — olav/oleha hashalom
    r'|\u05e2[\u0022\u05f4\u2033]?\u05d4'  # ע"ה — Hebrew
    r')\s*$',
    re.IGNORECASE
)


def strip_honorific_suffix(name):
    """Remove honorific suffixes like A\"H, Z\"L, OB\"M, ZT\"L, ע\"ה from a name."""
    return _HONORIFIC_SUFFIX_RE.sub('', name).strip()


def clean_text(text):
    """Clean and normalize text, escaping HTML to prevent stored XSS."""
    if not text:
        return None
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\S+@\S+\.\S+', '[email]', text)
    return text if text else None


def _extract_slug(href):
    """Extract the listing slug from a URL or path containing /shiva-listings/."""
    # Strip query params and fragments
    href_clean = href.split('?')[0].split('#')[0]
    # Remove trailing slash and get last path component
    return href_clean.rstrip('/').split('/')[-1]


def _is_listing_link(href):
    """Check if a URL/path points to an individual shiva listing (not the index page)."""
    if '/shiva-listings/' not in href:
        return False
    # Reject the index page itself (relative or absolute)
    if href.rstrip('/').endswith('/shiva-listings') or href.rstrip('/') == 'shiva-listings':
        return False
    if href == '/shiva-listings/' or href == BASE_URL:
        return False
    # Reject pagination links
    if '?page=' in href or '?campaign_page=' in href:
        return False
    # Must have a slug after /shiva-listings/
    slug = _extract_slug(href)
    if not slug or slug == 'shiva-listings':
        return False
    return True


def _name_from_slug(slug):
    """Convert a URL slug to a human-readable name."""
    # Remove trailing _1, _2 suffixes (duplicate slugs on Misaskim)
    slug_clean = re.sub(r'_\d+$', '', slug)
    name = slug_clean.replace('-', ' ').replace('_', ' ').title()
    return name


def scrape_listings_page(url):
    """Scrape a single page of shiva listings.

    Uses two strategies:
    1. Parse <a> tags with /shiva-listings/ hrefs (primary)
    2. Regex scan the full HTML for listing URLs (fallback for JS-rendered content
       that may appear in inline scripts, data attributes, or pre-rendered HTML blocks)
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return [], None

    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    listings = []
    found_slugs = set()  # track slugs across both strategies

    # --- Strategy 1: Parse <a> tags (works when server renders the campaign cards) ---
    for link in soup.find_all('a', href=True):
        href = link['href']
        if not _is_listing_link(href):
            continue

        slug = _extract_slug(href)
        if slug in found_slugs:
            continue
        found_slugs.add(slug)

        # Extract name from heading inside the card
        name_text = None
        heading = link.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if heading:
            name_text = heading.get_text(strip=True)

        # Try the full text of the <a>, stripping common action/fundraising text
        if not name_text:
            full_text = link.get_text(strip=True)
            for remove in ['Donate in memory', 'Donate in Memory',
                           'View shiva information', 'View Shiva Information',
                           'Shiva Listings', 'shiva listings',
                           'Become a Shiva Listing',
                           'C$0', '0.0% of C$0 goal',
                           'Donate to this campaign']:
                full_text = full_text.replace(remove, '')
            name_text = full_text.strip()

        # Clean residual fundraising text
        if name_text:
            name_text = re.sub(r'\d+\.?\d*%\s*of\s*C?\$?\d*\s*goal', '', name_text).strip()
            name_text = re.sub(r'C?\$\d[\d,.]*', '', name_text).strip()
            name_text = re.sub(r'\s{2,}', ' ', name_text).strip()

        # Fall back to slug-derived name
        if not name_text or len(name_text) < 3:
            name_text = _name_from_slug(slug)

        full_url = href if href.startswith('http') else f"https://misaskim.ca{href}"

        listings.append({
            'name': clean_text(name_text) or name_text,
            'url': full_url,
            'slug': slug,
            'source': 'Misaskim',
            'scraped_at': datetime.now().isoformat(),
        })

    strategy1_count = len(listings)

    # --- Strategy 2: Regex fallback — scan full HTML for listing URLs ---
    # Catches URLs in inline JS, data-* attributes, JSON-LD, or any context
    # where BeautifulSoup's <a> parsing misses them.
    url_pattern = re.compile(
        r'https?://misaskim\.ca/shiva-listings/([a-z0-9][a-z0-9_-]+)/?',
        re.IGNORECASE
    )
    for match in url_pattern.finditer(html):
        slug = match.group(1).rstrip('/')
        if slug in found_slugs:
            continue
        # Skip if slug is just "shiva-listings" (the index page itself matched weirdly)
        if slug == 'shiva-listings':
            continue
        found_slugs.add(slug)

        full_url = f"https://misaskim.ca/shiva-listings/{slug}/"
        name_text = _name_from_slug(slug)

        listings.append({
            'name': clean_text(name_text) or name_text,
            'url': full_url,
            'slug': slug,
            'source': 'Misaskim',
            'scraped_at': datetime.now().isoformat(),
        })

    strategy2_count = len(listings) - strategy1_count
    if strategy2_count > 0:
        logging.info(f"  Strategy 2 (regex) found {strategy2_count} additional listings")

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

    # Check for next page — try multiple pagination patterns
    next_page = None
    current_page_num = 1
    # Detect current page number from URL
    page_match = re.search(r'[?&]campaign_page=(\d+)', url)
    if page_match:
        current_page_num = int(page_match.group(1))
    next_page_num = current_page_num + 1

    for a in soup.find_all('a', href=True):
        a_href = a['href']
        text = a.get_text(strip=True)
        # Match "2", "3", "Next", ">" or pagination query params
        is_next = (
            text == str(next_page_num) or
            text.lower() in ('next', '>', 'next page', '\u00bb') or
            f'campaign_page={next_page_num}' in a_href or
            f'page={next_page_num}' in a_href or
            f'paged={next_page_num}' in a_href
        )
        if is_next:
            next_url = a_href
            if not next_url.startswith('http'):
                next_url = f"https://misaskim.ca{next_url}"
            # Only follow if the URL is for the same listings section
            if 'shiva-listing' in next_url or 'page' in next_url:
                next_page = next_url
                break

    return filtered, next_page


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
        name = strip_honorific_suffix(row[0].lower().strip())
        existing.add(name)
    conn.close()

    new_listings = []
    already_in_db = []

    for l in listings:
        name_clean = strip_honorific_suffix(l['name'].lower().strip())

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
