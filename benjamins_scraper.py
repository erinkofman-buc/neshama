import logging
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
from shiva_parser import extract_shiva_info

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
        seen_snums = set()

        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'ServiceDetails.aspx' in href:
                full_url = href if href.startswith('http') else self.base_url + '/' + href.lstrip('../').lstrip('/')
                # Deduplicate by service number, not full URL
                snum_match = re.search(r'[?&]snum=(\d+)', full_url)
                if snum_match:
                    snum = snum_match.group(1)
                    if snum not in seen_snums:
                        seen_snums.add(snum)
                        links.append(full_url)
                elif full_url not in links:
                    links.append(full_url)

        return links

    def _find_additional_listing_pages(self, html):
        """
        Look for non-postback links to additional listing pages.

        ASP.NET WebForms postback pagination (__doPostBack) is NOT feasible
        without maintaining ViewState across requests. Instead, look for
        standard <a href> links to archive or past-services pages.

        Returns a list of URLs (max 10 pages as safety valve).
        """
        soup = BeautifulSoup(html, 'html.parser')
        additional = []
        max_pages = 10

        # Patterns for archive/past listing pages
        archive_patterns = re.compile(
            r'(?:archive|past|previous|history|older|all)',
            re.IGNORECASE
        )

        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True).lower()

            # Skip postback links (these need ViewState)
            if 'javascript:' in href or '__doPostBack' in href:
                continue

            # Skip the homepage itself and service detail pages
            if 'Home.aspx' in href and '?' not in href:
                continue
            if 'ServiceDetails.aspx' in href:
                continue

            # Look for archive-type pages by link text or href
            if archive_patterns.search(text) or archive_patterns.search(href):
                full_url = href if href.startswith('http') else self.base_url + '/' + href.lstrip('/')
                if full_url not in additional:
                    additional.append(full_url)

            if len(additional) >= max_pages:
                break

        if additional:
            logging.info(f"Found {len(additional)} additional listing page(s)")
        else:
            logging.info("No additional listing pages found (ASP.NET postback pagination not supported)")

        return additional

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
                'condolence_url': url,
                'city': 'Toronto'
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

            # Extract structured shiva info from obituary text
            obit_text = data.get('obituary_text') or data.get('shiva_info')
            if obit_text:
                shiva_parsed = extract_shiva_info(obit_text)
                if shiva_parsed:
                    data['shiva_address'] = shiva_parsed['shiva_address']
                    data['shiva_hours'] = shiva_parsed['shiva_hours']
                    data['shiva_concludes'] = shiva_parsed['shiva_concludes']
                    data['shiva_raw'] = shiva_parsed['shiva_raw']
                    data['shiva_private'] = shiva_parsed['shiva_private']

            # Photo
            photo_elem = soup.find('img', id=re.compile(r'ContentPlaceHolder1.*img', re.IGNORECASE))
            if not photo_elem:
                photo_elem = soup.find('img', src=re.compile(r'DataUpload|photos', re.IGNORECASE))
            if photo_elem and photo_elem.get('src'):
                photo_url = photo_elem['src']
                data['photo_url'] = photo_url if photo_url.startswith('http') else self.base_url + '/' + photo_url.lstrip('/')

            return data

        except Exception as e:
            logging.info(f"Error parsing {url}: {str(e)}")
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
            logging.info(f"Error extracting comments from {url}: {str(e)}")
            return []

    def run(self):
        """Execute full scraping process"""
        start_time = time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            logging.info(f"\n{'='*60}")
            logging.info(f"Starting Benjamin's Park Memorial Chapel scraper")
            logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"{'='*60}\n")

            # Fetch homepage (which contains current service listings)
            homepage_url = f"{self.base_url}/Home.aspx"
            logging.info(f"Fetching listings page: {homepage_url}")
            html = self.fetch_page(homepage_url)

            if not html:
                raise Exception("Failed to fetch listings page")

            # Extract service detail links from homepage
            obituary_links = self.extract_obituary_links(html)

            # Pagination: Benjamin's uses ASP.NET WebForms with __doPostBack
            # for pagination, which requires maintaining ViewState and
            # EventValidation tokens across requests. Standard GET-based
            # pagination is not available.
            #
            # Best-effort: check for any additional listing pages linked from
            # the homepage (e.g. Archive.aspx, PastServices.aspx) that don't
            # require postback. These would be standard <a href> links.
            additional_pages = self._find_additional_listing_pages(html)
            for page_url in additional_pages:
                logging.info(f"Fetching additional listing page: {page_url}")
                page_html = self.fetch_page(page_url)
                if page_html:
                    extra_links = self.extract_obituary_links(page_html)
                    # Merge, deduplicating by snum
                    existing_snums = set()
                    for link in obituary_links:
                        snum_match = re.search(r'[?&]snum=(\d+)', link)
                        if snum_match:
                            existing_snums.add(snum_match.group(1))
                    for link in extra_links:
                        snum_match = re.search(r'[?&]snum=(\d+)', link)
                        if snum_match and snum_match.group(1) not in existing_snums:
                            obituary_links.append(link)
                            existing_snums.add(snum_match.group(1))
                        elif not snum_match and link not in obituary_links:
                            obituary_links.append(link)
                    time.sleep(2)  # Rate limit between page fetches

            stats['found'] = len(obituary_links)
            logging.info(f"Found {stats['found']} obituary links\n")

            # Process each obituary
            for i, link in enumerate(obituary_links, 1):
                try:
                    # Extract snum from URL for display
                    snum_match = re.search(r'snum=(\d+)', link)
                    display_id = snum_match.group(1) if snum_match else link.split('/')[-1]
                    logging.info(f"[{i}/{stats['found']}] Processing: service #{display_id}...")

                    # Parse obituary data
                    obit_data = self.parse_obituary_page(link)
                    if not obit_data:
                        logging.info("  ⚠️  Skipped (no data)")
                        stats['errors'] += 1
                        continue

                    # Save to database
                    obit_id, action = self.db.upsert_obituary(obit_data)

                    if action == 'inserted':
                        stats['new'] += 1
                        logging.info(f"  ✅ New: {obit_data['deceased_name']}")
                    elif action == 'updated':
                        stats['updated'] += 1
                        logging.info(f"  🔄 Updated: {obit_data['deceased_name']}")
                    else:
                        logging.info(f"  ⏭️  Unchanged: {obit_data['deceased_name']}")

                    # Extract and save comments
                    comments = self.extract_comments(link)
                    new_comments = 0
                    for comment in comments:
                        comment_id = self.db.upsert_comment(obit_id, comment)
                        if comment_id:
                            new_comments += 1

                    if new_comments > 0:
                        logging.info(f"  💬 Added {new_comments} new comments")

                    # Be polite - delay between requests
                    time.sleep(1.5)

                except Exception as e:
                    logging.info(f"  ❌ Error: {str(e)}")
                    stats['errors'] += 1

            # Log completion
            duration = time.time() - start_time
            self.db.log_scraper_run(
                source=self.source_name,
                status='success',
                stats=stats,
                duration=duration
            )

            logging.info(f"\n{'='*60}")
            logging.info(f"Scraping completed successfully")
            logging.info(f"Found: {stats['found']} | New: {stats['new']} | Updated: {stats['updated']} | Errors: {stats['errors']}")
            logging.info(f"Duration: {duration:.1f} seconds")
            logging.info(f"{'='*60}\n")

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

            logging.info(f"\n❌ Scraping failed: {error_msg}\n")
            raise

if __name__ == '__main__':
    scraper = BenjaminsScraper()
    scraper.run()
