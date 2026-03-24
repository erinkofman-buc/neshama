#!/usr/bin/env python3
"""
Dignity Memorial Scraper — Multi-Funeral-Home Parameterized Scraper

Dignity Memorial (dignitymemorial.com) is the largest funeral home network
in North America. Many Jewish funeral homes are part of this network:
  - Star of David Memorial Gardens (South Florida)
  - Riverside Gordon Memorial Chapels (South Florida)
  - Menorah Gardens Funeral Chapels (South Florida)
  - IJ Morris (NYC)
  - Riverside Memorial Chapel (NYC)
  - And more.

This scraper is parameterized: one class handles all Dignity Memorial
funeral homes, configured via city_config.py entries.

URL Patterns on dignitymemorial.com:
  Funeral home page:  /funeral-homes/{slug}
  Obituaries listing: /obituaries/{city}-{state}/search
  Individual obit:    /obituaries/{first}-{last}/{id}
  Obituary API:       /api/obituaries?funeralHomeId={id}&page={n}

NOTE: Dignity Memorial uses Cloudflare protection. This scraper uses
cloudscraper (if available) or falls back to requests with browser-like
headers. Heavy anti-bot sites may require Playwright or a headless
browser in production — this is a working prototype to demonstrate
the pattern.
"""

import logging
import re
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup

from base_scraper import BaseScraper
from city_config import CITIES

logger = logging.getLogger(__name__)

# Attempt to import cloudscraper for Cloudflare bypass;
# fall back to plain requests if not installed.
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False


class DignityMemorialScraper(BaseScraper):
    """
    Scraper for funeral homes on dignitymemorial.com.

    Usage:
        # Scrape a single funeral home
        scraper = DignityMemorialScraper(
            funeral_home_slug='star-of-david-memorial-gardens-and-funeral-chapel',
            funeral_home_name='Star of David Memorial Gardens',
            city_slug='south-florida',
        )
        scraper.run()

        # Or use the class method to run all Dignity Memorial homes
        # for a given city:
        DignityMemorialScraper.run_for_city('south-florida')
    """

    # Dignity Memorial base URLs
    DM_BASE = "https://www.dignitymemorial.com"
    DM_OBITS_API = "https://www.dignitymemorial.com/api/obituary/search"

    def __init__(self, funeral_home_slug, funeral_home_name, city_slug,
                 request_delay=2.5):
        """
        Args:
            funeral_home_slug: The URL slug for the funeral home on
                dignitymemorial.com (e.g. 'star-of-david-memorial-gardens-and-funeral-chapel')
            funeral_home_name: Human-readable name for source field
            city_slug: Key from city_config.CITIES
            request_delay: Seconds between requests (default 2.5 — be polite)
        """
        super().__init__(
            source_name=funeral_home_name,
            city_slug=city_slug,
            base_url=f"{self.DM_BASE}/funeral-homes/{funeral_home_slug}",
            request_delay=request_delay,
        )
        self.funeral_home_slug = funeral_home_slug
        self.funeral_home_id = None  # Populated from page data

        # Upgrade session for Cloudflare if possible
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False}
            )
            logger.info(f"[{self.source_name}] Using cloudscraper for Cloudflare bypass")
        else:
            # Add extra headers to look more like a real browser
            self.session.headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            })

    def _extract_funeral_home_id(self, html):
        """
        Extract the numeric funeral home ID from the funeral home page.
        Dignity Memorial embeds this in page data / script tags.
        """
        if not html:
            return None

        # Pattern 1: Look for funeralHomeId in script tags or inline JSON
        patterns = [
            r'"funeralHomeId"\s*:\s*(\d+)',
            r'funeralHomeId=(\d+)',
            r'"id"\s*:\s*(\d+).*?"type"\s*:\s*"FuneralHome"',
            r'data-funeral-home-id="(\d+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)

        return None

    def _extract_obits_from_html(self, html):
        """
        Parse obituary listings from an HTML page.
        Dignity Memorial renders obituaries as cards on listing pages.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        obituaries = []

        # Look for obituary cards/links
        # DM uses various selectors; try multiple patterns
        obit_links = set()

        # Pattern 1: Links matching /obituaries/{name}/{id}
        for link in soup.find_all('a', href=True):
            href = link['href']
            if re.match(r'/obituaries/[a-z]+-[a-z]+/\d+', href):
                full_url = self.DM_BASE + href if not href.startswith('http') else href
                obit_links.add(full_url)

        # Pattern 2: Look for __NEXT_DATA__ or similar embedded JSON
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if script_tag:
            try:
                data = json.loads(script_tag.string)
                props = data.get('props', {}).get('pageProps', {})
                obits = props.get('obituaries', []) or props.get('results', [])
                for obit in obits:
                    if isinstance(obit, dict):
                        obituaries.append(obit)
            except (json.JSONDecodeError, AttributeError):
                pass

        # Pattern 3: Look for JSON-LD structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                ld_data = json.loads(script.string)
                if isinstance(ld_data, list):
                    for item in ld_data:
                        if item.get('@type') == 'Person':
                            obituaries.append(item)
                elif isinstance(ld_data, dict) and ld_data.get('@type') == 'Person':
                    obituaries.append(ld_data)
            except (json.JSONDecodeError, AttributeError):
                pass

        # If we found raw links but no structured data, create stubs
        for url in obit_links:
            if not any(o.get('url') == url for o in obituaries):
                obituaries.append({'url': url, '_needs_fetch': True})

        return obituaries

    def _fetch_obit_api(self, page=1, page_size=20):
        """
        Try the Dignity Memorial obituary search API.
        Returns list of obituary dicts, or empty list.
        """
        if not self.funeral_home_id:
            return []

        params = {
            'funeralHomeId': self.funeral_home_id,
            'pageNumber': page,
            'pageSize': page_size,
            'sortBy': 'recent',
        }

        # The API may require specific headers
        headers = {
            'Accept': 'application/json',
            'Referer': self.base_url,
            'X-Requested-With': 'XMLHttpRequest',
        }

        self._rate_limit()
        try:
            response = self.session.get(
                self.DM_OBITS_API,
                params=params,
                headers=headers,
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                # API may return {results: [...], totalCount: N}
                if isinstance(data, dict):
                    return data.get('results', data.get('obituaries', []))
                elif isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"[{self.source_name}] API fetch failed: {e}")

        return []

    def fetch_obituary_listings(self):
        """
        Fetch all available obituary listings for this funeral home.
        Tries multiple strategies:
        1. JSON API (cleanest)
        2. HTML scraping of the obituaries page
        3. Funeral home page itself
        """
        all_obits = []

        # Strategy 1: Try to get the funeral home page first to extract the ID
        logger.info(f"Fetching funeral home page: {self.base_url}")
        home_html = self.fetch_page(self.base_url)

        if home_html:
            self.funeral_home_id = self._extract_funeral_home_id(home_html)
            if self.funeral_home_id:
                logger.info(f"Found funeral home ID: {self.funeral_home_id}")

            # Extract any obituaries linked from the home page
            page_obits = self._extract_obits_from_html(home_html)
            all_obits.extend(page_obits)

        # Strategy 2: Try the API if we have a funeral home ID
        if self.funeral_home_id:
            logger.info(f"Trying obituary API with ID {self.funeral_home_id}...")
            api_obits = self._fetch_obit_api(page=1, page_size=50)
            if api_obits:
                logger.info(f"API returned {len(api_obits)} obituaries")
                all_obits.extend(api_obits)

        # Strategy 3: Try the obituary listing page directly
        obits_page_url = f"{self.base_url}/obituaries"
        logger.info(f"Fetching obituaries page: {obits_page_url}")
        obits_html = self.fetch_page(obits_page_url)
        if obits_html:
            html_obits = self._extract_obits_from_html(obits_html)
            all_obits.extend(html_obits)

        # Deduplicate by URL
        seen_urls = set()
        unique_obits = []
        for obit in all_obits:
            url = obit.get('url') or obit.get('source_url') or obit.get('link', '')
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            unique_obits.append(obit)

        logger.info(f"Total unique obituary listings: {len(unique_obits)}")
        return unique_obits

    def _fetch_individual_obit_page(self, url):
        """Fetch and parse a single obituary detail page."""
        html = self.fetch_page(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'html.parser')
        data = {}

        # Name from h1 or og:title
        h1 = soup.find('h1')
        if h1:
            data['name'] = self.clean_text(h1.get_text())

        og_title = soup.find('meta', property='og:title')
        if og_title and not data.get('name'):
            data['name'] = og_title.get('content', '').split('|')[0].strip()

        # Obituary text
        obit_div = (
            soup.find('div', class_=re.compile(r'obituary-text|obit-body|obituary-content', re.I))
            or soup.find('section', class_=re.compile(r'obituary', re.I))
            or soup.find('div', {'itemprop': 'description'})
        )
        if obit_div:
            data['obituary_text'] = self.clean_text(obit_div.get_text())

        # Photo
        photo = (
            soup.find('img', class_=re.compile(r'obit|deceased|memorial|portrait', re.I))
            or soup.find('img', {'itemprop': 'image'})
        )
        if photo and photo.get('src'):
            src = photo['src']
            data['photo_url'] = src if src.startswith('http') else self.DM_BASE + src

        # Dates — look for structured data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                ld = json.loads(script.string)
                if isinstance(ld, dict) and ld.get('@type') == 'Person':
                    data['date_of_death'] = ld.get('deathDate')
                    data['date_of_birth'] = ld.get('birthDate')
            except (json.JSONDecodeError, AttributeError):
                pass

        # Service/funeral info
        service_section = soup.find(text=re.compile(r'Service|Funeral|Visitation', re.I))
        if service_section:
            parent = service_section.find_parent(['div', 'section', 'li'])
            if parent:
                data['service_text'] = self.clean_text(parent.get_text())

        return data

    def parse_obituary(self, raw_data):
        """
        Parse raw obituary data (from API, embedded JSON, or HTML card)
        into the Neshama obituary schema.
        """
        if not raw_data:
            return None

        # If this is a stub that needs fetching, go get the full page
        if raw_data.get('_needs_fetch') and raw_data.get('url'):
            page_data = self._fetch_individual_obit_page(raw_data['url'])
            raw_data.update(page_data)

        # Extract name — try multiple field names
        name = (
            raw_data.get('name')
            or raw_data.get('deceased_name')
            or raw_data.get('deceasedName')
            or raw_data.get('fullName')
        )

        if not name:
            # Try to extract from URL
            url = raw_data.get('url', '')
            match = re.search(r'/obituaries/([a-z]+-[a-z]+(?:-[a-z]+)*)/\d+', url)
            if match:
                name = match.group(1).replace('-', ' ').title()

        if not name:
            return None  # Cannot proceed without a name

        # Build source URL
        source_url = raw_data.get('url') or raw_data.get('link', '')
        if source_url and not source_url.startswith('http'):
            source_url = self.DM_BASE + source_url

        if not source_url:
            # Construct from name if we have an ID
            obit_id = raw_data.get('id') or raw_data.get('obituaryId')
            if obit_id:
                name_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                source_url = f"{self.DM_BASE}/obituaries/{name_slug}/{obit_id}"
            else:
                source_url = self.base_url

        # Build the obituary dict
        data = {
            'source': self.source_name,
            'source_url': source_url,
            'condolence_url': source_url,
            'deceased_name': self.clean_text(name),
            'city': self.city_display,
        }

        # Date of death
        dod = (
            raw_data.get('deathDate')
            or raw_data.get('date_of_death')
            or raw_data.get('dateOfDeath')
        )
        if dod:
            data['date_of_death'] = self._format_date(dod)

        # Obituary text
        obit_text = (
            raw_data.get('obituary_text')
            or raw_data.get('obituaryText')
            or raw_data.get('obituary')
            or raw_data.get('description')
        )
        if obit_text:
            data['obituary_text'] = self.clean_text(self.strip_html(obit_text))

            # Try to extract death date from text if not found
            if not data.get('date_of_death'):
                data['date_of_death'] = self._extract_death_date_from_text(
                    data['obituary_text']
                )

        # Funeral/service info
        service_text = raw_data.get('service_text') or raw_data.get('serviceText')
        if service_text:
            dt_match = re.search(
                r'(\w+day,?\s+\w+\s+\d{1,2},?\s+\d{4})\s*(?:at\s+)?(\d{1,2}:\d{2}\s*[AP]M)?',
                service_text, re.IGNORECASE
            )
            if dt_match:
                date_part = dt_match.group(1)
                time_part = dt_match.group(2)
                data['funeral_datetime'] = (
                    f"{date_part} at {time_part}" if time_part else date_part
                )

            # Location from service text
            loc_match = re.search(
                r'(?:at|held at|chapel|location)\s*:?\s*([^,\n]+)',
                service_text, re.IGNORECASE
            )
            if loc_match:
                data['funeral_location'] = self.clean_text(loc_match.group(1))

        # Funeral location fallback
        if not data.get('funeral_location'):
            loc = raw_data.get('funeralLocation') or raw_data.get('funeral_location')
            if loc:
                data['funeral_location'] = self.clean_text(loc)

        # Photo URL
        photo = (
            raw_data.get('photo_url')
            or raw_data.get('photoUrl')
            or raw_data.get('imageUrl')
            or raw_data.get('image')
        )
        if photo:
            data['photo_url'] = photo if photo.startswith('http') else self.DM_BASE + photo

        return data

    def _format_date(self, date_str):
        """Try to parse and format a date string."""
        if not date_str:
            return None

        # Already formatted nicely
        if re.match(r'[A-Z][a-z]+ \d{1,2}, \d{4}', date_str):
            return date_str

        # ISO format: 2026-03-15
        try:
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%B %d, %Y')
        except (ValueError, TypeError):
            pass

        return date_str

    def _extract_death_date_from_text(self, text):
        """Extract date of death from obituary text."""
        if not text:
            return None

        patterns = [
            r'passed away.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
            r'died.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
            r'peacefully.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
            r'entered into rest.*?on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})',
            r'([A-Za-z]+ \d{1,2}, \d{4})\s*[-–]\s*[A-Za-z]+ \d{1,2}, \d{4}',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def post_process(self, obit_data):
        """Run shiva parser on obituary text if available."""
        try:
            from shiva_parser import extract_shiva_info
            text = obit_data.get('obituary_text', '')
            if text:
                shiva_parsed = extract_shiva_info(text)
                if shiva_parsed:
                    obit_data['shiva_address'] = shiva_parsed.get('shiva_address')
                    obit_data['shiva_hours'] = shiva_parsed.get('shiva_hours')
                    obit_data['shiva_concludes'] = shiva_parsed.get('shiva_concludes')
                    obit_data['shiva_raw'] = shiva_parsed.get('shiva_raw')
                    obit_data['shiva_private'] = shiva_parsed.get('shiva_private')
        except ImportError:
            pass  # shiva_parser not available

        return obit_data

    # ──────────────────────────────────────────────
    # Class methods for multi-home orchestration
    # ──────────────────────────────────────────────

    @classmethod
    def get_dm_homes_for_city(cls, city_slug):
        """
        Get all Dignity Memorial funeral home configs for a city.
        Returns list of (slug, display_name) tuples.

        The city_config funeral_homes dict maps short keys to display names.
        For Dignity Memorial, the short key IS the DM URL slug.
        """
        city = CITIES.get(city_slug)
        if not city:
            return []

        # Only return homes for cities that list 'dignity_memorial' as a scraper
        if 'dignity_memorial' not in city.get('scrapers', []):
            return []

        return list(city.get('funeral_homes', {}).items())

    @classmethod
    def run_for_city(cls, city_slug):
        """
        Run the scraper for ALL Dignity Memorial funeral homes in a city.
        Returns combined stats.
        """
        homes = cls.get_dm_homes_for_city(city_slug)

        if not homes:
            logger.info(f"No Dignity Memorial homes configured for {city_slug}")
            return {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        total_stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        for slug, name in homes:
            try:
                logger.info(f"\n>> Running Dignity Memorial scraper for: {name}")
                scraper = cls(
                    funeral_home_slug=slug,
                    funeral_home_name=name,
                    city_slug=city_slug,
                )
                stats = scraper.run()

                total_stats['found'] += stats.get('found', 0)
                total_stats['new'] += stats.get('new', 0)
                total_stats['updated'] += stats.get('updated', 0)
                total_stats['errors'] += stats.get('errors', 0)

            except Exception as e:
                logger.error(f"!! {name} scraper failed: {e}")
                total_stats['errors'] += 1

        return total_stats


# ──────────────────────────────────────────────
# Standalone execution
# ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )

    if len(sys.argv) > 1:
        # Run for a specific city: python dignity_memorial_scraper.py south-florida
        city = sys.argv[1]
        DignityMemorialScraper.run_for_city(city)
    else:
        # Default: demo with Star of David (requires south-florida city to be active)
        print("Usage: python dignity_memorial_scraper.py <city_slug>")
        print("Example: python dignity_memorial_scraper.py south-florida")
        print("\nConfigured cities with Dignity Memorial homes:")
        for slug, cfg in CITIES.items():
            if 'dignity_memorial' in cfg.get('scrapers', []):
                homes = list(cfg.get('funeral_homes', {}).values())
                print(f"  {slug}: {', '.join(homes)}")
