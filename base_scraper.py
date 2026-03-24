#!/usr/bin/env python3
"""
Neshama Base Scraper Framework
Abstract base class for all new scrapers in the multi-city expansion.

Existing scrapers (steeles, benjamins, paperman, misaskim) do NOT need
to be refactored to use this — it's for NEW scrapers only.
"""

import logging
import time
import re
import requests
from abc import ABC, abstractmethod
from datetime import datetime
from database_setup import NeshamaDatabase
from city_config import get_city_by_slug

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class that all new Neshama scrapers should inherit from.

    Subclasses must implement:
        - fetch_obituary_listings() -> list of raw listing data
        - parse_obituary(raw_data) -> dict matching the obituary schema

    The base class provides:
        - HTTP session with retry logic and rate limiting
        - Database integration (upsert_obituary, log_scraper_run)
        - City metadata from city_config
        - Standardized run() loop with error handling and stats
    """

    def __init__(self, source_name, city_slug, base_url, request_delay=2.0):
        """
        Args:
            source_name: Human-readable name (e.g. 'Star of David Memorial Gardens')
            city_slug:   Key from city_config.CITIES (e.g. 'south-florida')
            base_url:    Root URL of the funeral home website
            request_delay: Seconds to wait between HTTP requests (default 2.0)
        """
        self.source_name = source_name
        self.city_slug = city_slug
        self.base_url = base_url.rstrip('/')
        self.request_delay = request_delay

        # Load city metadata
        self.city_config = get_city_by_slug(city_slug) or {}
        self.city_display = self.city_config.get('display_name', city_slug.replace('-', ' ').title())
        self.country = self.city_config.get('country', '')
        self.region = self.city_config.get('region', '')

        # HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

        # Database
        self.db = NeshamaDatabase()

        # Track when we last made a request for rate limiting
        self._last_request_time = 0

    # ──────────────────────────────────────────────
    # HTTP helpers
    # ──────────────────────────────────────────────

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def fetch_page(self, url, retries=3, timeout=15):
        """
        Fetch a page with retry logic and rate limiting.
        Returns the response text, or None on failure.
        """
        self._rate_limit()

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"[{self.source_name}] Request failed (attempt {attempt + 1}/{retries}): "
                    f"{url} — {e}"
                )
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                else:
                    logger.error(f"[{self.source_name}] All retries exhausted for {url}")
        return None

    def fetch_json(self, url, retries=3, timeout=15):
        """
        Fetch a JSON endpoint with retry logic and rate limiting.
        Returns parsed JSON (dict/list), or None on failure.
        """
        self._rate_limit()

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                logger.warning(
                    f"[{self.source_name}] JSON fetch failed (attempt {attempt + 1}/{retries}): "
                    f"{url} — {e}"
                )
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[{self.source_name}] All retries exhausted for {url}")
        return None

    # ──────────────────────────────────────────────
    # Text helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def clean_text(text):
        """Clean and normalize text. Redact email addresses."""
        if not text:
            return None
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', text)
        return text if text else None

    @staticmethod
    def strip_html(html_text):
        """Strip HTML tags and return clean text."""
        if not html_text:
            return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else None

    # ──────────────────────────────────────────────
    # Abstract methods — subclasses MUST implement
    # ──────────────────────────────────────────────

    @abstractmethod
    def fetch_obituary_listings(self):
        """
        Fetch and return a list of raw obituary data items.
        Each item will be passed to parse_obituary().

        Returns:
            list: Raw obituary data (dicts, HTML snippets, URLs, etc.)
        """
        pass

    @abstractmethod
    def parse_obituary(self, raw_data):
        """
        Parse a single raw obituary item into the Neshama schema.

        Must return a dict with at least:
            - 'source': str
            - 'source_url': str
            - 'condolence_url': str
            - 'deceased_name': str
            - 'city': str

        Optional fields:
            - 'hebrew_name', 'date_of_death', 'yahrzeit_date'
            - 'funeral_datetime', 'funeral_location', 'burial_location'
            - 'shiva_info', 'obituary_text', 'livestream_url', 'photo_url'
            - 'shiva_address', 'shiva_hours', 'shiva_concludes',
              'shiva_raw', 'shiva_private'

        Returns:
            dict or None (None = skip this record)
        """
        pass

    # ──────────────────────────────────────────────
    # Optional hooks — subclasses MAY override
    # ──────────────────────────────────────────────

    def extract_comments(self, obituary_url_or_id):
        """
        Override to extract condolence comments for a given obituary.
        Returns a list of dicts with keys: commenter_name, comment_text, posted_at
        Default: returns empty list.
        """
        return []

    def post_process(self, obit_data):
        """
        Hook called after parse_obituary() but before database upsert.
        Use for shiva parsing, geocoding, etc.
        Default: returns data unchanged.
        """
        return obit_data

    # ──────────────────────────────────────────────
    # Storage
    # ──────────────────────────────────────────────

    def store_results(self, obituaries):
        """
        Upsert a list of parsed obituary dicts into the database.
        Returns stats dict with 'new', 'updated', 'unchanged', 'errors' counts.
        """
        stats = {'new': 0, 'updated': 0, 'unchanged': 0, 'errors': 0}

        for obit_data in obituaries:
            try:
                obit_id, action = self.db.upsert_obituary(obit_data)

                if action == 'inserted':
                    stats['new'] += 1
                    logger.info(f"  + New: {obit_data['deceased_name']}")
                elif action == 'updated':
                    stats['updated'] += 1
                    logger.info(f"  ~ Updated: {obit_data['deceased_name']}")
                else:
                    stats['unchanged'] += 1
                    logger.info(f"  = Unchanged: {obit_data['deceased_name']}")

                # Extract and save comments
                comments = self.extract_comments(obit_data.get('source_url'))
                new_comments = 0
                for comment in comments:
                    comment_id = self.db.upsert_comment(obit_id, comment)
                    if comment_id:
                        new_comments += 1
                if new_comments > 0:
                    logger.info(f"    >> Added {new_comments} new comments")

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"  !! Error storing {obit_data.get('deceased_name', '?')}: {e}")

        return stats

    # ──────────────────────────────────────────────
    # Logging
    # ──────────────────────────────────────────────

    def log_run(self, status, stats, error=None, duration=None):
        """Log scraper execution to the scraper_log table."""
        self.db.log_scraper_run(
            source=self.source_name,
            status=status,
            stats=stats,
            error=error,
            duration=duration,
        )

    # ──────────────────────────────────────────────
    # Main run loop
    # ──────────────────────────────────────────────

    def run(self):
        """
        Execute the full scraping process:
        1. Fetch listings
        2. Parse each one
        3. Store results
        4. Log the run
        """
        start_time = time.time()
        stats = {'found': 0, 'new': 0, 'updated': 0, 'errors': 0}

        try:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Starting {self.source_name} scraper ({self.city_display})")
            logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'=' * 60}\n")

            # Step 1: Fetch raw listings
            raw_listings = self.fetch_obituary_listings()
            stats['found'] = len(raw_listings)
            logger.info(f"Found {stats['found']} obituary listings\n")

            if not raw_listings:
                logger.info("No listings found — nothing to process.")
                duration = time.time() - start_time
                self.log_run('success', stats, duration=duration)
                return stats

            # Step 2: Parse each listing
            parsed = []
            for i, raw in enumerate(raw_listings, 1):
                try:
                    logger.info(f"[{i}/{stats['found']}] Parsing...")
                    obit_data = self.parse_obituary(raw)

                    if not obit_data:
                        logger.info("  -- Skipped (no data)")
                        stats['errors'] += 1
                        continue

                    # Run post-processing hook
                    obit_data = self.post_process(obit_data)
                    if obit_data:
                        parsed.append(obit_data)

                except Exception as e:
                    logger.error(f"  !! Parse error: {e}")
                    stats['errors'] += 1

            # Step 3: Store results
            store_stats = self.store_results(parsed)
            stats['new'] = store_stats['new']
            stats['updated'] = store_stats['updated']
            stats['errors'] += store_stats['errors']

            # Step 4: Log success
            duration = time.time() - start_time
            self.log_run('success', stats, duration=duration)

            logger.info(f"\n{'=' * 60}")
            logger.info(f"Scraping completed successfully")
            logger.info(
                f"Found: {stats['found']} | New: {stats['new']} | "
                f"Updated: {stats['updated']} | Errors: {stats['errors']}"
            )
            logger.info(f"Duration: {duration:.1f} seconds")
            logger.info(f"{'=' * 60}\n")

            return stats

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            self.log_run('failed', stats, error=error_msg, duration=duration)
            logger.error(f"\n!! {self.source_name} scraping failed: {error_msg}\n")
            raise
