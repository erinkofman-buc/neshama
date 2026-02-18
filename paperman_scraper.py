#!/usr/bin/env python3
"""
Paperman & Sons Funeral Home Scraper
Extracts obituary data from paperman.com (Montreal)
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import json
from datetime import datetime
from database_setup import NeshamaDatabase
from shiva_parser import extract_shiva_info


class PapermanScraper:
    def __init__(self):
        self.source_name = "Paperman & Sons"
        self.base_url = "https://www.paperman.com"
        self.image_base_url = "https://ymhbzpyciewmkvghgtpg.supabase.co/storage/v1/object/public/client-images"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.db = NeshamaDatabase()

    def fetch_page(self, url, retries=3):
        """Fetch page with retry logic"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None

    def fetch_json(self, url, retries=3):
        """Fetch JSON endpoint with retry logic"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None

    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', text)
        return text if text else None

    def strip_html(self, html_text):
        """Strip HTML tags and return clean text"""
        if not html_text:
            return None
        soup = BeautifulSoup(html_text, 'html.parser')
        return self.clean_text(soup.get_text())

    def extract_obituary_listings(self, html):
        """Extract all funeral listings from the funerals page __NEXT_DATA__"""
        # The Paperman site is a Next.js app; funeral data is embedded as
        # JSON inside a <script id="__NEXT_DATA__"> tag on the /funerals page.
        match = re.search(r'__NEXT_DATA__[^>]+>(.*?)</script>', html, re.DOTALL)
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
            funerals = data.get('props', {}).get('pageProps', {}).get('activeFunerals', [])
            return funerals
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing __NEXT_DATA__: {e}")
            return []

    def build_photo_url(self, image_path):
        """Construct full photo URL from the Supabase storage path"""
        if not image_path:
            return None
        return f"{self.image_base_url}/{image_path}"

    def parse_funeral_date(self, funeral_data):
        """Extract and format the funeral date and time"""
        # Prefer the human-readable email_funeral_date (e.g. "Thursday, February 5 at 1:00PM")
        email_date = funeral_data.get('email_funeral_date')
        if email_date:
            return email_date

        # Fall back to web_funeral_date (e.g. "2026-02-05 13:00")
        web_date = funeral_data.get('web_funeral_date')
        if web_date:
            try:
                dt = datetime.strptime(web_date, '%Y-%m-%d %H:%M')
                return dt.strftime('%A, %B %d at %I:%M%p')
            except ValueError:
                return web_date

        return None

    def extract_death_date(self, obituary_text):
        """Try to extract date of death from the obituary text"""
        if not obituary_text:
            return None

        # Common patterns in Paperman obituaries:
        # "on Monday, February 2, 2026"
        # "on January 11, 2026"
        # "le 13 janvier 2026"
        patterns = [
            r'on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+\d{1,2},?\s+\d{4})',
            r'on\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+\d{1,2},?\s+\d{4})',
            r'le\s+(\d{1,2}\s+(?:janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|'
            r'septembre|octobre|novembre|d[eé]cembre)\s+\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, obituary_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def build_shiva_info(self, funeral_data):
        """Combine shiva-related fields into a single info string"""
        parts = []

        shiva_notes = self.strip_html(funeral_data.get('shiva_notes'))
        if shiva_notes:
            parts.append(shiva_notes)

        shiva_address = funeral_data.get('web_shiva_address')
        if shiva_address:
            parts.append(f"Address: {shiva_address}")

        shiva_start = funeral_data.get('shiva_start_date')
        shiva_end = funeral_data.get('shiva_end_date')
        if shiva_start and shiva_end:
            parts.append(f"Dates: {shiva_start} to {shiva_end}")
        elif shiva_start:
            parts.append(f"Starting: {shiva_start}")

        shiva_note = funeral_data.get('web_shiva_note')
        if shiva_note:
            parts.append(shiva_note)

        shiva_private = funeral_data.get('shiva_private')
        if shiva_private and shiva_private == 'strict':
            parts.append("(Private)")

        return '; '.join(parts) if parts else None

    def parse_obituary_data(self, funeral_data):
        """Extract all data from a single funeral listing object"""
        try:
            name = funeral_data.get('name')
            if not name:
                return None

            slug = funeral_data.get('slug', '')
            source_url = f"{self.base_url}/funerals/{slug}" if slug else self.base_url
            obituary_html = funeral_data.get('obituary_en') or funeral_data.get('obituary_fr')
            obituary_text = self.strip_html(obituary_html)

            data = {
                'source': self.source_name,
                'source_url': source_url,
                'condolence_url': source_url,
                'deceased_name': name,
                'city': 'Montreal',
            }

            # Yahrzeit date (Hebrew date of death)
            yahrzeit = funeral_data.get('yahrzeit_date')
            if yahrzeit:
                data['yahrzeit_date'] = yahrzeit

            # Date of death - extracted from the obituary text
            death_date = self.extract_death_date(obituary_text)
            if death_date:
                data['date_of_death'] = death_date

            # Funeral date and time
            funeral_datetime = self.parse_funeral_date(funeral_data)
            if funeral_datetime:
                data['funeral_datetime'] = funeral_datetime

            # Funeral location
            location = funeral_data.get('web_location')
            other_location = funeral_data.get('other_location')
            if location:
                data['funeral_location'] = location
            elif other_location:
                data['funeral_location'] = other_location

            # Burial / cemetery
            cemetery_name = funeral_data.get('cemetery_name')
            if cemetery_name:
                data['burial_location'] = cemetery_name

            # Shiva info
            shiva_info = self.build_shiva_info(funeral_data)
            if shiva_info:
                data['shiva_info'] = shiva_info

            # Obituary text (cleaned from HTML)
            if obituary_text:
                data['obituary_text'] = obituary_text

            # Extract structured shiva info from obituary text
            parse_text = obituary_text or shiva_info
            if parse_text:
                shiva_parsed = extract_shiva_info(parse_text)
                if shiva_parsed:
                    data['shiva_address'] = shiva_parsed['shiva_address']
                    data['shiva_hours'] = shiva_parsed['shiva_hours']
                    data['shiva_concludes'] = shiva_parsed['shiva_concludes']
                    data['shiva_raw'] = shiva_parsed['shiva_raw']
                    data['shiva_private'] = shiva_parsed['shiva_private']

            # Livestream
            if funeral_data.get('streaming'):
                data['livestream_url'] = source_url

            # Photo URL
            photo_url = self.build_photo_url(funeral_data.get('image_path'))
            if photo_url:
                data['photo_url'] = photo_url

            return data

        except Exception as e:
            print(f"Error parsing funeral data for {funeral_data.get('name', 'unknown')}: {str(e)}")
            return None

    def extract_comments(self, funeral_id):
        """Extract condolence messages from the Paperman comments API"""
        try:
            url = f"{self.base_url}/api/comment?funeralId={funeral_id}"
            comments_data = self.fetch_json(url)

            if not comments_data or not isinstance(comments_data, list):
                return []

            comments = []
            for entry in comments_data:
                # Skip private comments
                if entry.get('private', False):
                    continue

                comment_text = self.clean_text(entry.get('text'))
                if not comment_text:
                    continue

                comment_data = {
                    'comment_text': comment_text,
                }

                commenter_name = self.clean_text(entry.get('name'))
                if commenter_name:
                    comment_data['commenter_name'] = commenter_name

                posted_at = entry.get('created_at')
                if posted_at:
                    comment_data['posted_at'] = posted_at

                comments.append(comment_data)

            return comments

        except Exception as e:
            print(f"Error extracting comments for funeral {funeral_id}: {str(e)}")
            return []

    def run(self):
        """Execute full scraping process"""
        start_time = time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            print(f"\n{'='*60}")
            print(f"Starting Paperman & Sons scraper")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            # Fetch the funerals listing page which contains all active funerals
            # as embedded JSON via Next.js __NEXT_DATA__
            funerals_url = f"{self.base_url}/funerals"
            print(f"Fetching listings page: {funerals_url}")
            html = self.fetch_page(funerals_url)

            if not html:
                raise Exception("Failed to fetch listings page")

            # Extract funeral listings from the embedded JSON
            funeral_listings = self.extract_obituary_listings(html)
            stats['found'] = len(funeral_listings)
            print(f"Found {stats['found']} obituary listings\n")

            # Process each funeral listing
            for i, funeral_data in enumerate(funeral_listings, 1):
                try:
                    display_name = funeral_data.get('name', 'Unknown')
                    funeral_id = funeral_data.get('id')
                    print(f"[{i}/{stats['found']}] Processing: {display_name}...")

                    # Parse obituary data from the listing JSON
                    obit_data = self.parse_obituary_data(funeral_data)
                    if not obit_data:
                        print("  -- Skipped (no data)")
                        stats['errors'] += 1
                        continue

                    # Save to database
                    obit_id, action = self.db.upsert_obituary(obit_data)

                    if action == 'inserted':
                        stats['new'] += 1
                        print(f"  + New: {obit_data['deceased_name']}")
                    elif action == 'updated':
                        stats['updated'] += 1
                        print(f"  ~ Updated: {obit_data['deceased_name']}")
                    else:
                        print(f"  = Unchanged: {obit_data['deceased_name']}")

                    # Extract and save comments via the API
                    if funeral_id and funeral_data.get('enable_web_comments', False):
                        comments = self.extract_comments(funeral_id)
                        new_comments = 0
                        for comment in comments:
                            comment_id = self.db.upsert_comment(obit_id, comment)
                            if comment_id:
                                new_comments += 1

                        if new_comments > 0:
                            print(f"  >> Added {new_comments} new comments")

                    # Be polite - delay between requests
                    time.sleep(1.5)

                except Exception as e:
                    print(f"  !! Error: {str(e)}")
                    stats['errors'] += 1

            # Log completion
            duration = time.time() - start_time
            self.db.log_scraper_run(
                source=self.source_name,
                status='success',
                stats=stats,
                duration=duration
            )

            print(f"\n{'='*60}")
            print(f"Scraping completed successfully")
            print(f"Found: {stats['found']} | New: {stats['new']} | Updated: {stats['updated']} | Errors: {stats['errors']}")
            print(f"Duration: {duration:.1f} seconds")
            print(f"{'='*60}\n")

            return stats

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            self.db.log_scraper_run(
                source=self.source_name,
                status='failed',
                stats=stats,
                error=error_msg,
                duration=duration
            )

            print(f"\n!! Scraping failed: {error_msg}\n")
            raise


if __name__ == '__main__':
    scraper = PapermanScraper()
    scraper.run()
