#!/usr/bin/env python3
"""
Steeles Memorial Chapel Scraper
Extracts obituary data from steelesmemorialchapel.com
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime
from database_setup import NeshamaDatabase

class SteelesScraper:
    def __init__(self):
        self.source_name = "Steeles Memorial Chapel"
        self.base_url = "https://steelesmemorialchapel.com"
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
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def extract_obituary_links(self, html):
        """Extract all obituary links from homepage"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # Find all condolence links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/condolence/' in href:
                full_url = href if href.startswith('http') else self.base_url + href
                if full_url not in links:
                    links.append(full_url)

        return links

    def clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else None

    def parse_obituary_page(self, url):
        """Extract all data from individual obituary page"""
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            data = {
                'source': self.source_name,
                'source_url': url,
                'condolence_url': url,
                'city': 'Toronto'
            }

            # Extract deceased name
            name_elem = soup.find('h1', class_='entry-title') or soup.find('h1')
            if name_elem:
                data['deceased_name'] = self.clean_text(name_elem.get_text())
            else:
                # Try to extract from URL as fallback
                name_from_url = url.split('/condolence/')[-1].replace('-', ' ').title()
                data['deceased_name'] = name_from_url

            if not data.get('deceased_name'):
                return None  # Skip if no name found

            # Extract full obituary text
            obit_content = soup.find('div', class_='entry-content') or soup.find('div', class_='obituary')
            if obit_content:
                # Get all paragraphs
                paragraphs = [p.get_text() for p in obit_content.find_all('p')]
                data['obituary_text'] = self.clean_text('\n\n'.join(paragraphs))

                # Try to extract structured data from text
                full_text = data['obituary_text']

                # Hebrew name pattern
                hebrew_match = re.search(r'[\u0590-\u05FF\s]+', full_text)
                if hebrew_match:
                    data['hebrew_name'] = hebrew_match.group(0).strip()

                # Date of death
                death_date_patterns = [
                    r'passed away.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
                    r'died.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
                    r'peacefully.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})'
                ]
                for pattern in death_date_patterns:
                    match = re.search(pattern, full_text, re.IGNORECASE)
                    if match:
                        data['date_of_death'] = match.group(1)
                        break

                # Yahrzeit
                yahrzeit_match = re.search(r'Yahrzeit:?\s*([^\n.]+)', full_text, re.IGNORECASE)
                if yahrzeit_match:
                    data['yahrzeit_date'] = self.clean_text(yahrzeit_match.group(1))

            # Extract funeral information
            funeral_info = soup.find(text=re.compile(r'Funeral|Chapel Service', re.IGNORECASE))
            if funeral_info:
                parent = funeral_info.find_parent()
                if parent:
                    funeral_text = self.clean_text(parent.get_text())

                    # Extract datetime
                    datetime_match = re.search(
                        r'([A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
                        funeral_text
                    )
                    if datetime_match:
                        data['funeral_datetime'] = f"{datetime_match.group(1)} at {datetime_match.group(2)}"

                    # Extract location
                    location_match = re.search(r'Chapel(?:\s+Service)?,?\s+([^\n]+)', funeral_text)
                    if location_match:
                        data['funeral_location'] = self.clean_text(location_match.group(1))

            # Extract burial information
            burial_info = soup.find(text=re.compile(r'Burial|Cemetery', re.IGNORECASE))
            if burial_info:
                parent = burial_info.find_parent()
                if parent:
                    data['burial_location'] = self.clean_text(parent.get_text())

            # Extract shiva information
            shiva_info = soup.find(text=re.compile(r'Shiva', re.IGNORECASE))
            if shiva_info:
                parent = shiva_info.find_parent()
                if parent:
                    data['shiva_info'] = self.clean_text(parent.get_text())

            # Check for livestream
            livestream_link = soup.find('a', href=re.compile(r'smclive|livestream', re.IGNORECASE))
            if livestream_link:
                data['livestream_url'] = livestream_link['href']

            # Extract photo
            photo = soup.find('img', class_=re.compile(r'obituary|deceased|memorial', re.IGNORECASE))
            if photo and photo.get('src'):
                photo_url = photo['src']
                data['photo_url'] = photo_url if photo_url.startswith('http') else self.base_url + photo_url

            return data

        except Exception as e:
            print(f"Error parsing {url}: {str(e)}")
            return None

    def extract_comments(self, url):
        """Extract condolence comments from page"""
        try:
            html = self.fetch_page(url)
            if not html:
                return []

            soup = BeautifulSoup(html, 'html.parser')
            comments = []

            # Find comment containers
            comment_section = soup.find('div', id=re.compile(r'comment|condolence', re.IGNORECASE))
            if not comment_section:
                comment_section = soup.find('div', class_=re.compile(r'comment|condolence', re.IGNORECASE))

            if comment_section:
                for comment_div in comment_section.find_all('div', class_='comment'):
                    comment_data = {}

                    # Extract commenter name
                    name_elem = comment_div.find('cite') or comment_div.find(class_='comment-author')
                    if name_elem:
                        comment_data['commenter_name'] = self.clean_text(name_elem.get_text())

                    # Extract comment text
                    text_elem = comment_div.find('p') or comment_div.find(class_='comment-text')
                    if text_elem:
                        comment_data['comment_text'] = self.clean_text(text_elem.get_text())

                    # Extract timestamp
                    time_elem = comment_div.find('time') or comment_div.find(class_='comment-date')
                    if time_elem:
                        comment_data['posted_at'] = self.clean_text(time_elem.get_text())

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
            print(f"Starting Steeles Memorial Chapel scraper")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")

            # Fetch homepage
            print("Fetching homepage...")
            homepage_html = self.fetch_page(self.base_url)
            if not homepage_html:
                raise Exception("Failed to fetch homepage")

            # Extract obituary links
            obituary_links = self.extract_obituary_links(homepage_html)
            stats['found'] = len(obituary_links)
            print(f"Found {stats['found']} obituary links\n")

            # Process each obituary
            for i, link in enumerate(obituary_links, 1):
                try:
                    print(f"[{i}/{stats['found']}] Processing: {link.split('/')[-2]}...")

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

                    # Be polite - small delay between requests
                    time.sleep(1)

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
    scraper = SteelesScraper()
    scraper.run()
