#!/usr/bin/env python3
"""
Benjamin's Park Memorial Chapel Scraper
Extracts obituary data from benjaminsparkmemorialchapel.ca
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime
from database_setup import NeshamaDatabase

class BenjaminsScraper:
    def __init__(self):
        self.source_name = "Benjamin's Park Memorial Chapel"
        self.base_url = "https://benjaminsparkmemorialchapel.ca"
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

    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', text)
        return text if text else None

    def extract_obituary_links(self, html):
        """Extract all ServiceDetails links from homepage"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'ServiceDetails.aspx' in href:
                full_url = href if href.startswith('http') else self.base_url + '/' + href.lstrip('../').lstrip('/')
                if full_url not in links:
                    links.append(full_url)

        return links

    def get_span_text(self, soup, span_id):
        """Extract text from ASP.NET span by ID"""
        elem = soup.find('span', id=span_id)
        if elem:
            return self.clean_text(elem.get_text())
        return None

    def parse_obituary_page(self, url):
        """Extract all data from individual service details page"""
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            data = {
                'source': self.source_name,
                'source_url': url,
                'condolence_url': url
            }

            # Extract deceased name from ASP.NET span
            name = self.get_span_text(soup, 'ContentPlaceHolder1_lblName')
            if not name:
                name = self.get_span_text(soup, 'ContentPlaceHolder1_Label1')
            if not name:
                return None
            data['deceased_name'] = name

            # Hebrew name
            hebrew_name = self.get_span_text(soup, 'ContentPlaceHolder1_lblHebrewName')
            if not hebrew_name:
                hebrew_name = self.get_span_text(soup, 'ContentPlaceHolder1_Label2')
            if hebrew_name:
                data['hebrew_name'] = hebrew_name

            # Date of death
            death_date = self.get_span_text(soup, 'ContentPlaceHolder1_lblDeathDate')
            if death_date:
                data['date_of_death'] = death_date

            # Yahrzeit date
            yahrzeit = self.get_span_text(soup, 'ContentPlaceHolder1_lblYahrzeitDate')
            if yahrzeit:
                data['yahrzeit_date'] = yahrzeit

            # Funeral date and time
            funeral_date = self.get_span_text(soup, 'ContentPlaceHolder1_lblFuneralDate')
            funeral_time = self.get_span_text(soup, 'ContentPlaceHolder1_lblFuneralTime')
            if funeral_date:
                if funeral_time:
                    data['funeral_datetime'] = f"{funeral_date} at {funeral_time}"
                else:
                    data['funeral_datetime'] = funeral_date

            # Funeral location
            funeral_place = self.get_span_text(soup, 'ContentPlaceHolder1_lblFuneralPlacename')
            funeral_address = self.get_span_text(soup, 'ContentPlaceHolder1_lblFuneralPlaceaddress')
            if funeral_place:
                if funeral_address:
                    data['funeral_location'] = f"{funeral_place}, {funeral_address}"
                else:
                    data['funeral_location'] = funeral_place

            # Cemetery / burial
            cemetery = self.get_span_text(soup, 'ContentPlaceHolder1_cemetryname')
            cemetery_addr = self.get_span_text(soup, 'ContentPlaceHolder1_cemetryaddress')
            if cemetery:
                if cemetery_addr:
                    data['burial_location'] = f"{cemetery}, {cemetery_addr}"
                else:
                    data['burial_location'] = cemetery

            # Shiva info
            shiva_div = soup.find('div', id='ContentPlaceHolder1_shivaContent')
            if shiva_div:
                data['shiva_info'] = self.clean_text(shiva_div.get_text())

            # Obituary / notice text
            notice = self.get_span_text(soup, 'ContentPlaceHolder1_lblNotice')
            if notice:
                data['obituary_text'] = notice

            # Livestream / video
            video_div = soup.find('div', id='ContentPlaceHolder1_videolink')
            if video_div:
                video_link = video_div.find('a', href=True)
                if video_link:
                    data['livestream_url'] = video_link['href']
                else:
                    data['livestream_url'] = url

            # Photo
            photo_elem = soup.find('img', id=re.compile(r'ContentPlaceHolder1.*img', re.IGNORECASE))
            if not photo_elem:
                photo_elem = soup.find('img', src=re.compile(r'DataUpload|photos', re.IGNORECASE))
            if photo_elem and photo_elem.get('src'):
                photo_url = photo_elem['src']
                data['photo_url'] = photo_url if photo_url.startswith('http') else self.base_url + '/' + photo_url.lstrip('/')

            return data

        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")
            return None

    def extract_comments(self, url):
        """Extract condolence messages from memorial book section"""
        try:
            html = self.fetch_page(url)
            if not html:
                return []

            soup = BeautifulSoup(html, 'html.parser')
            comments = []

            memorial_book = soup.find('div', id='ContentPlaceHolder1_memorialBook')
            if not memorial_book:
                return []

            for entry in memorial_book.find_all('div', class_=re.compile(r'message|entry|condolence', re.IGNORECASE)):
                comment_data = {}

                name_elem = entry.find(class_=re.compile(r'author|name|sender', re.IGNORECASE))
                if not name_elem:
                    name_elem = entry.find('strong') or entry.find('b')
                if name_elem:
                    comment_data['commenter_name'] = self.clean_text(name_elem.get_text())

                text_elem = entry.find(class_=re.compile(r'text|message|content', re.IGNORECASE))
                if not text_elem:
                    text_elem = entry.find('p')
                if text_elem:
                    comment_data['comment_text'] = self.clean_text(text_elem.get_text())

                date_elem = entry.find(class_=re.compile(r'date|time|posted', re.IGNORECASE))
                if date_elem:
                    comment_data['posted_at'] = self.clean_text(date_elem.get_text())

                if comment_data.get('comment_text'):
                    comments.append(comment_data)

            return comments

        except Exception as e:
            print(f"Error extracting comments from {url}: {str(e)}")
            return []

    def run(self):
        """Execute full scraping process"""
        start_time = time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            print(f"\n{'='*60}")
            print(f"Starting Benjamin's Park Memorial Chapel scraper")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            # Fetch homepage (which contains current service listings)
            homepage_url = f"{self.base_url}/Home.aspx"
            print(f"Fetching listings page: {homepage_url}")
            html = self.fetch_page(homepage_url)

            if not html:
                raise Exception("Failed to fetch listings page")

            # Extract service detail links
            obituary_links = self.extract_obituary_links(html)
            stats['found'] = len(obituary_links)
            print(f"Found {stats['found']} obituary links\n")

            # Process each obituary
            for i, link in enumerate(obituary_links, 1):
                try:
                    # Extract snum from URL for display
                    snum_match = re.search(r'snum=(\d+)', link)
                    display_id = snum_match.group(1) if snum_match else link.split('/')[-1]
                    print(f"[{i}/{stats['found']}] Processing: service #{display_id}...")

                    # Parse obituary data
                    obit_data = self.parse_obituary_page(link)
                    if not obit_data:
                        print("  ⚠️  Skipped (no data)")
                        stats['errors'] += 1
                        continue

                    # Save to database
                    obit_id, action = self.db.upsert_obituary(obit_data)

                    if action == 'inserted':
                        stats['new'] += 1
                        print(f"  ✅ New: {obit_data['deceased_name']}")
                    elif action == 'updated':
                        stats['updated'] += 1
                        print(f"  🔄 Updated: {obit_data['deceased_name']}")
                    else:
                        print(f"  ⏭️  Unchanged: {obit_data['deceased_name']}")

                    # Extract and save comments
                    comments = self.extract_comments(link)
                    new_comments = 0
                    for comment in comments:
                        comment_id = self.db.upsert_comment(obit_id, comment)
                        if comment_id:
                            new_comments += 1

                    if new_comments > 0:
                        print(f"  💬 Added {new_comments} new comments")

                    # Be polite - delay between requests
                    time.sleep(1.5)

                except Exception as e:
                    print(f"  ❌ Error: {str(e)}")
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

            print(f"\n❌ Scraping failed: {error_msg}\n")
            raise

if __name__ == '__main__':
    scraper = BenjaminsScraper()
    scraper.run()
