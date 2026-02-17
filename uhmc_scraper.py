#!/usr/bin/env python3
"""
United Hebrew Memorial Chapel (UHMC) Scraper - Hamilton, ON
Extracts obituary data from uhmc.ca

NOTE: uhmc.ca is behind Incapsula/Imperva bot protection.
Standard requests/curl calls return an Incapsula challenge page.
This scraper uses `cloudscraper` to handle the JS challenge automatically.
If cloudscraper fails, the Incapsula challenge may have been updated and
manual testing will be needed.

Install: pip install cloudscraper

Status: SKELETON - not yet integrated into master_scraper.py
The user will verify manually once Incapsula bypass is confirmed working.
"""

import time
import re
from datetime import datetime
from database_setup import NeshamaDatabase

# Try cloudscraper first (handles Incapsula), fall back to requests
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    import requests

from bs4 import BeautifulSoup


class UHMCScraper:
    def __init__(self):
        self.source_name = "United Hebrew Memorial Chapel"
        self.base_url = "https://uhmc.ca"
        self.archives_url = "https://uhmc.ca/archives/"
        self.db = NeshamaDatabase()

        # Create session - cloudscraper handles Incapsula challenges
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',
                    'mobile': False
                }
            )
            print("  Using cloudscraper (Incapsula bypass)")
        else:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            print("  WARNING: cloudscraper not installed, using plain requests (may be blocked)")

    def fetch_page(self, url, retries=3):
        """Fetch page with retry logic and exponential backoff"""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=20)
                response.raise_for_status()

                # Check if we got an Incapsula challenge page instead of real content
                if 'Incapsula' in response.text or '_Incapsula_Resource' in response.text:
                    if attempt < retries - 1:
                        wait_time = 2 ** (attempt + 1)
                        print(f"  Incapsula challenge detected, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("  ERROR: Could not bypass Incapsula after retries")
                        return None

                return response.text
            except Exception as e:
                if attempt == retries - 1:
                    raise
                wait_time = 2 ** (attempt + 1)
                print(f"  Request failed ({e}), retrying in {wait_time}s...")
                time.sleep(wait_time)
        return None

    def extract_obituary_links(self, html):
        """Extract obituary post links from the archives page"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # WordPress structure: posts are in article or entry elements
        # UHMC uses /lastname-firstname/ URL pattern
        for article in soup.find_all('article'):
            title_el = article.find(['h2', 'h1', 'h3'])
            if title_el:
                link_el = title_el.find('a')
                if link_el and link_el.get('href'):
                    href = link_el['href']
                    name = link_el.get_text(strip=True)
                    if name and href:
                        links.append({
                            'url': href if href.startswith('http') else self.base_url + href,
                            'name': name
                        })

        # Fallback: look for entry-title class links
        if not links:
            for el in soup.find_all(class_='entry-title'):
                link_el = el.find('a')
                if link_el and link_el.get('href'):
                    links.append({
                        'url': link_el['href'],
                        'name': link_el.get_text(strip=True)
                    })

        # Fallback: look for any links matching the obituary URL pattern
        if not links:
            for a in soup.find_all('a', href=True):
                href = a['href']
                # UHMC obituaries follow /lastname-firstname/ pattern
                if re.match(r'https?://uhmc\.ca/[a-z]+-[a-z]+', href, re.IGNORECASE):
                    name = a.get_text(strip=True)
                    if name and len(name) > 3:
                        links.append({'url': href, 'name': name})

        # Deduplicate by URL
        seen = set()
        unique_links = []
        for link in links:
            if link['url'] not in seen:
                seen.add(link['url'])
                unique_links.append(link)

        return unique_links

    def get_pagination_urls(self, html):
        """Find additional archive pages (pagination)"""
        soup = BeautifulSoup(html, 'html.parser')
        pages = set()

        # WordPress pagination: /category/archives/page/N/
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/page/' in href and 'archives' in href:
                pages.add(href if href.startswith('http') else self.base_url + href)

        return sorted(pages)

    def parse_obituary_page(self, url):
        """Parse an individual obituary page for details"""
        html = self.fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Extract name from entry-title or page title
        name = None
        title_el = soup.find(class_='entry-title')
        if title_el:
            name = title_el.get_text(strip=True)
        if not name:
            title_tag = soup.find('title')
            if title_tag:
                name = title_tag.get_text(strip=True).split('|')[0].split('–')[0].strip()
        if not name:
            return None

        # Extract obituary text from entry-content
        obit_text = ''
        content_div = soup.find(class_='entry-content')
        if content_div:
            obit_text = content_div.get_text(separator='\n', strip=True)

        # Extract photo
        photo_url = None
        if content_div:
            img = content_div.find('img')
            if img and img.get('src'):
                photo_url = img['src']

        # Parse structured info from obituary text
        date_of_death = self._extract_date_of_death(obit_text)
        funeral_datetime = self._extract_funeral_info(obit_text)
        funeral_location = self._extract_funeral_location(obit_text)
        burial_location = self._extract_burial_location(obit_text)
        shiva_info = self._extract_shiva_info(obit_text)
        hebrew_name = self._extract_hebrew_name(obit_text, soup)

        return {
            'source': self.source_name,
            'source_url': url,
            'deceased_name': name,
            'hebrew_name': hebrew_name,
            'date_of_death': date_of_death,
            'funeral_datetime': funeral_datetime,
            'funeral_location': funeral_location,
            'burial_location': burial_location,
            'shiva_info': shiva_info,
            'obituary_text': obit_text[:2000] if obit_text else None,
            'condolence_url': url,
            'photo_url': photo_url,
            'city': 'Hamilton',
        }

    def _extract_date_of_death(self, text):
        """Try to extract date of death from obituary text"""
        if not text:
            return None
        # Common patterns: "passed away on January 15, 2026", "died January 15"
        patterns = [
            r'passed\s+away\s+(?:on\s+)?(\w+\s+\d{1,2},?\s*\d{4})',
            r'died\s+(?:on\s+)?(\w+\s+\d{1,2},?\s*\d{4})',
            r'passed\s+(?:on\s+)?(\w+\s+\d{1,2},?\s*\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_funeral_info(self, text):
        """Extract funeral date/time from text"""
        if not text:
            return None
        patterns = [
            r'(?:funeral|service|chapel)\s+(?:will be held\s+)?(?:on\s+)?(\w+,?\s+\w+\s+\d{1,2}[^.]*?(?:at\s+\d{1,2}[^.]*)?)',
            r'(?:funeral|service)\s*[:]\s*([^\n.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        return None

    def _extract_funeral_location(self, text):
        """Extract funeral location"""
        if not text:
            return None
        patterns = [
            r'(?:service|funeral)\s+(?:at|held at)\s+([^.]+)',
            r'(?:chapel|synagogue|temple)\s+(?:at\s+)?(\d+[^.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        return None

    def _extract_burial_location(self, text):
        """Extract burial location"""
        if not text:
            return None
        patterns = [
            r'(?:burial|interment)\s+(?:at|in)\s+([^.]+)',
            r'(?:cemetery|memorial\s+park)\s*[:-]?\s*([^.\n]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]
        return None

    def _extract_shiva_info(self, text):
        """Extract shiva information"""
        if not text:
            return None
        patterns = [
            r'shiva\s+(?:will be\s+)?(?:at|held at|observed at)\s+([^.]+(?:\.[^.]+)?)',
            r'shiva\s*[:]\s*([^\n]+(?:\n[^\n]+)?)',
            r'sitting\s+shiva\s+(?:at\s+)?([^.]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:500]
        return None

    def _extract_hebrew_name(self, text, soup):
        """Try to extract Hebrew name"""
        if not text:
            return None
        # Look for Hebrew characters in the text
        hebrew_match = re.search(r'[\u0590-\u05FF]{2,}[\s\u0590-\u05FF]*', text)
        if hebrew_match:
            return hebrew_match.group(0).strip()
        return None

    def extract_comments(self, url):
        """Extract condolence comments from obituary page"""
        html = self.fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        comments = []

        # WordPress comment structure
        comment_list = soup.find(class_='comment-list') or soup.find(id='comments')
        if not comment_list:
            return []

        for comment_el in comment_list.find_all(class_=re.compile(r'comment\b')):
            author_el = comment_el.find(class_='comment-author') or comment_el.find(class_='fn')
            content_el = comment_el.find(class_='comment-content') or comment_el.find(class_='comment-body')
            date_el = comment_el.find(class_='comment-date') or comment_el.find('time')

            if content_el:
                comment_text = content_el.get_text(strip=True)
                if comment_text:
                    comments.append({
                        'commenter_name': author_el.get_text(strip=True) if author_el else None,
                        'comment_text': comment_text[:1000],
                        'posted_at': date_el.get_text(strip=True) if date_el else None,
                    })

        return comments

    def run(self):
        """Execute full scraping process"""
        start_time = time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            print(f"\n{'='*60}")
            print(f"Starting UHMC Hamilton scraper")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if not HAS_CLOUDSCRAPER:
                print("WARNING: cloudscraper not installed - may be blocked by Incapsula")
                print("Install with: pip install cloudscraper")
            print(f"{'='*60}\n")

            # Fetch archives page
            print(f"Fetching archives: {self.archives_url}")
            html = self.fetch_page(self.archives_url)
            if not html:
                raise Exception("Failed to fetch archives page (possibly blocked by Incapsula)")

            # Extract obituary links from first page
            all_links = self.extract_obituary_links(html)

            # Check for additional pages
            pagination_urls = self.get_pagination_urls(html)
            for page_url in pagination_urls[:5]:  # Limit to 5 pages
                print(f"Fetching page: {page_url}")
                page_html = self.fetch_page(page_url)
                if page_html:
                    page_links = self.extract_obituary_links(page_html)
                    all_links.extend(page_links)
                time.sleep(2)

            stats['found'] = len(all_links)
            print(f"Found {stats['found']} obituary listings\n")

            # Process each obituary
            for i, item in enumerate(all_links, 1):
                try:
                    print(f"[{i}/{stats['found']}] Processing: {item['name']}...")

                    obit_data = self.parse_obituary_page(item['url'])
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

                    # Extract comments
                    comments = self.extract_comments(item['url'])
                    if comments:
                        new_comments = 0
                        for comment in comments:
                            cid = self.db.upsert_comment(obit_id, comment)
                            if cid:
                                new_comments += 1
                        if new_comments > 0:
                            print(f"  Added {new_comments} comments")

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
            print(f"UHMC scraping completed")
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

            print(f"\n!! UHMC scraping failed: {error_msg}\n")
            raise


if __name__ == '__main__':
    scraper = UHMCScraper()
    scraper.run()
