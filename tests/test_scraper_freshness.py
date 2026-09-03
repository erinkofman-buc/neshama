#!/usr/bin/env python3
"""
Tests for the corrected scraper freshness semantics and bot-challenge detection.

The 2026-08-31 health email said this:

    Benjamin's Park Memorial Chapel: 642.3h ago (STALE)
    Misaskim: 28.7h ago (STALE)
    Paperman & Sons: 13.6h ago (STALE)
    Steeles Memorial Chapel: 20.4h ago (STALE)

Three of those four scrapers were working perfectly. The number was
MAX(obituaries.scraped_at), which is written on INSERT and never on UPDATE, so
it means "when did we last store a NEW obituary" - not "did the scraper run".
The cron runs every 20 minutes, so a 6-hour threshold on that number flags an
ordinary overnight as a failure, and a genuine 27-day outage hid among three
false alarms.

Run:  python3 -m pytest tests/test_scraper_freshness.py -v
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(REPO_ROOT))

from database_setup import NeshamaDatabase
from scraper_health import (
    collect_source_health, format_health_lines, broken_sources,
    stale_window_seconds, is_bot_challenge, BotProtectionBlocked,
)

BENJAMINS = "Benjamin's Park Memorial Chapel"
STEELES = 'Steeles Memorial Chapel'
MISASKIM = 'Misaskim'
PAPERMAN = 'Paperman & Sons'


class FakeResponse:
    def __init__(self, status_code=200, headers=None, text=''):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


class FreshnessTests(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        NeshamaDatabase(self.db_path).create_tables()
        self.conn = sqlite3.connect(self.db_path)
        self.now = datetime(2026, 8, 31, 7, 0, 0)

    def tearDown(self):
        self.conn.close()
        for suffix in ('', '-wal', '-shm'):
            try:
                os.unlink(self.db_path + suffix)
            except OSError:
                pass

    def _log_run(self, source, hours_ago, status='success', error=None):
        when = (self.now - timedelta(hours=hours_ago)).isoformat()
        self.conn.execute(
            'INSERT INTO scraper_log (source, run_time, status, error_message) '
            'VALUES (?,?,?,?)', (source, when, status, error))
        self.conn.commit()

    def _add_obituary(self, source, hours_ago, slug):
        when = (self.now - timedelta(hours=hours_ago)).isoformat()
        self.conn.execute(
            'INSERT INTO obituaries (id, source, source_url, condolence_url, '
            'deceased_name, city, scraped_at, first_seen, last_updated, '
            'content_hash) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (slug, source, 'https://example.test/' + slug,
             'https://example.test/' + slug, 'Person ' + slug, 'Toronto',
             when, when, when, 'h-' + slug))
        self.conn.commit()

    def _report(self):
        return collect_source_health(self.conn, now=self.now)

    def test_the_aug_31_scenario_flags_exactly_one_source(self):
        """The regression, reproduced. Only Benjamin's is actually broken."""
        # All four scrapers ran 10 minutes ago; Benjamin's failed.
        for source in (STEELES, MISASKIM, PAPERMAN):
            self._log_run(source, hours_ago=0.16, status='success')
        self._log_run(BENJAMINS, hours_ago=0.16, status='failed',
                      error='403 Client Error: Forbidden')
        self._log_run(BENJAMINS, hours_ago=642.3, status='success')

        # New obituaries at exactly the ages the Aug 31 email reported.
        self._add_obituary(BENJAMINS, 642.3, 'b1')
        self._add_obituary(MISASKIM, 28.7, 'm1')
        self._add_obituary(PAPERMAN, 13.6, 'p1')
        self._add_obituary(STEELES, 20.4, 's1')

        report = self._report()
        self.assertEqual(broken_sources(report), [BENJAMINS],
                         'only the genuinely broken scraper may be flagged')
        for source in (STEELES, MISASKIM, PAPERMAN):
            with self.subTest(source=source):
                self.assertFalse(report[source]['stale'])

    def test_both_numbers_are_reported(self):
        self._log_run(STEELES, hours_ago=0.2, status='success')
        self._add_obituary(STEELES, 20.4, 's1')
        entry = self._report()[STEELES]
        self.assertAlmostEqual(entry['hours_since_success'], 0.2, places=1)
        self.assertAlmostEqual(entry['hours_since_new'], 20.4, places=1)
        self.assertFalse(entry['stale'], 'the scraper succeeded 12 minutes ago')
        self.assertFalse(entry['quiet'],
                         '20h is an ordinary overnight, not worth remarking on')

    def test_quiet_is_only_reported_past_a_full_day(self):
        """"Quiet" is cosmetic and must not creep back toward crying wolf."""
        self._log_run(MISASKIM, hours_ago=0.2, status='success')
        self._add_obituary(MISASKIM, 30, 'm1')
        entry = self._report()[MISASKIM]
        self.assertFalse(entry['stale'])
        self.assertTrue(entry['quiet'])
        self.assertIn('no new obituaries for 30.0h',
                      format_health_lines({MISASKIM: entry}))

    def test_a_failing_scraper_is_stale_even_though_it_runs_constantly(self):
        """The /api/health half of the bug: 121 failed runs a day is not freshness."""
        for hours in range(0, 24):
            self._log_run(BENJAMINS, hours_ago=hours, status='failed',
                          error='Cloudflare challenge')
        report = self._report()
        self.assertTrue(report[BENJAMINS]['stale'])
        self.assertIn('Cloudflare', report[BENJAMINS]['last_error'])

    def test_a_source_that_never_succeeded_is_stale(self):
        report = self._report()
        self.assertEqual(sorted(broken_sources(report)),
                         sorted([BENJAMINS, STEELES, MISASKIM, PAPERMAN]))

    def test_shabbat_pause_is_not_a_failure(self):
        """Scrapers are paused Friday sunset to Saturday sunset by design."""
        for source in (STEELES, MISASKIM, PAPERMAN, BENJAMINS):
            self._log_run(source, hours_ago=20, status='success')
        report = collect_source_health(self.conn, now=self.now, shabbat=True)
        self.assertEqual(broken_sources(report), [])

    def test_stale_window_is_three_cron_intervals_with_a_floor(self):
        self.assertEqual(stale_window_seconds(1200), 3600)     # 20 min -> 1h
        self.assertEqual(stale_window_seconds(3600), 10800)    # 60 min -> 3h
        self.assertEqual(stale_window_seconds(60), 3600)       # floor holds

    def test_report_text_names_the_reason(self):
        self._log_run(BENJAMINS, hours_ago=642.3, status='success')
        self._log_run(BENJAMINS, hours_ago=0.1, status='failed',
                      error='Cloudflare challenge on Home.aspx')
        for source in (STEELES, MISASKIM, PAPERMAN):
            self._log_run(source, hours_ago=0.1, status='success')
            self._add_obituary(source, 2, 'x' + source[:3])

        text = format_health_lines(self._report())
        self.assertIn('BROKEN', text)
        self.assertIn('Cloudflare challenge', text)
        self.assertNotIn('STALE', text)
        # The three healthy sources must not be shouted about.
        self.assertEqual(text.count('BROKEN'), 1)


class BotChallengeDetectionTests(unittest.TestCase):
    """Reproduced live on 2026-09-02: HTTP 403, cf-mitigated: challenge."""

    def test_cf_mitigated_header_is_detected(self):
        self.assertTrue(is_bot_challenge(FakeResponse(
            403, {'cf-mitigated': 'challenge', 'server': 'cloudflare'},
            '<title>Just a moment...</title>')))

    def test_challenge_body_without_the_header_is_detected(self):
        self.assertTrue(is_bot_challenge(FakeResponse(
            403, {'server': 'cloudflare'},
            '<html><head><title>Just a moment...</title></head></html>')))

    def test_an_ordinary_403_is_not_a_challenge(self):
        self.assertFalse(is_bot_challenge(FakeResponse(
            403, {}, '<h1>Forbidden</h1>')))

    def test_a_normal_page_is_not_a_challenge(self):
        self.assertFalse(is_bot_challenge(FakeResponse(
            200, {}, '<html><body>Service Details</body></html>')))

    def test_none_is_handled(self):
        self.assertFalse(is_bot_challenge(None))

    def test_benjamins_scraper_raises_the_named_exception(self):
        from benjamins_scraper import BenjaminsScraper
        scraper = BenjaminsScraper.__new__(BenjaminsScraper)

        class Session:
            def get(self, url, timeout=None):
                return FakeResponse(403, {'cf-mitigated': 'challenge'},
                                    '<title>Just a moment...</title>')
        scraper.session = Session()

        with self.assertRaises(BotProtectionBlocked) as ctx:
            scraper.fetch_page('https://benjaminsparkmemorialchapel.ca/Home.aspx')
        message = str(ctx.exception)
        self.assertIn('Cloudflare challenge', message)
        self.assertIn('site policy change', message)


if __name__ == '__main__':
    unittest.main(verbosity=2)
