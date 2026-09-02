#!/usr/bin/env python3
"""
Tests for the empty-subscriber-table guard on the daily digest.

The evidence this exists for, from Erin's inbox:

  Aug 17, Aug 24 and Aug 31 2026 (all Mondays) each delivered TWO
  [Neshama Health] reports, five seconds apart:

    11:00:00Z   Obituaries 6, Sent 0, Active 0, Pending 0, Unsubscribed 0
    11:00:05Z   Obituaries 5, Sent 54, Active 69, Unsubscribed 11

  Monday-only because _send_health_summary gates on weekday() == 0. The digest
  runs every Sun-Fri; only its health report is weekly.

  Production /api/digest-status records exactly ONE run per day, so the 11:00:00
  process was writing digest_runs somewhere else. Both reports show near
  identical scraper freshness (Benjamin's 642.3h in both), but the small
  differences move in BOTH directions (Misaskim 28.7 vs 28.6, Paperman 13.6 vs
  13.7), which two reads of one table five seconds apart cannot produce and two
  independently-scraping deployments can.

  A brand new empty database is ruled out: EmailSubscriptionManager creates an
  empty subscribers table on construction, but get_new_obituaries would then
  raise "no such table: obituaries" before any health email could be sent. The
  phantom reports 5 to 6 obituaries, so it has a populated, current obituaries
  table and an empty subscriber table.

  Conclusion: a second deployment running the same code against its own
  database. Which one requires the Render dashboard to confirm.

Whatever the deployment turns out to be, the guard is the same: a run that sees
obituaries but zero confirmed subscribers must not send, and must say so.

Run:  python3 -m pytest tests/test_digest_subscriber_guard.py -v
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(REPO_ROOT))
sys.path.insert(0, os.path.abspath(os.path.join(REPO_ROOT, 'frontend')))

from database_setup import NeshamaDatabase
from daily_digest import DailyDigestSender, instance_fingerprint


STEELES = 'Steeles Memorial Chapel'


class DigestGuardTestBase(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        NeshamaDatabase(self.db_path).create_tables()
        self.sender = DailyDigestSender(db_path=self.db_path,
                                        sendgrid_api_key='test-key')
        self.health_emails = []
        self.sent_digests = []

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            try:
                os.unlink(self.db_path + suffix)
            except OSError:
                pass

    def _add_obituary(self, name='Test Person', slug='test-person'):
        url = f'https://steelesmemorialchapel.com/condolence/{slug}/'
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO obituaries (id, source, source_url, condolence_url, "
            "deceased_name, city, scraped_at, first_seen, last_updated, "
            "content_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (slug, STEELES, url, url, name, 'Toronto', now, now, now, 'h-' + slug))
        conn.commit()
        conn.close()

    def _add_subscriber(self, email='reader@example.com', confirmed=1):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO subscribers (email, unsubscribe_token, confirmed, "
            "frequency, locations, subscribed_at) VALUES (?,?,?,?,?,?)",
            (email, 'tok-' + email, confirmed, 'daily', 'toronto,montreal',
             datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def _run(self):
        def fake_digest_send(email, token, html, locations=None, obit_count=None):
            self.sent_digests.append(email)
            return {'success': True, 'status_code': 202}

        real_health = self.sender._send_health_summary

        def capture_health(result):
            # Run the real body but intercept the SendGrid client.
            with patch('daily_digest.SendGridAPIClient') as client:
                sent = []
                client.return_value.send.side_effect = lambda m: sent.append(m)
                real_health(result)
                self.health_emails.extend(sent)

        with patch.object(self.sender, 'send_digest_to_subscriber', fake_digest_send), \
             patch.object(self.sender, '_send_health_summary', capture_health):
            return self.sender.send_daily_digest()


class EmptySubscriberTableTests(DigestGuardTestBase):

    def test_digest_is_not_sent_when_there_are_no_subscribers(self):
        self._add_obituary('David Wayne De Leon', 'david-wayne-de-leon')
        self._add_obituary('Miriam Kaplan', 'miriam-kaplan')

        result = self._run()

        self.assertEqual(result['status'], 'skipped_no_subscribers')
        self.assertEqual(result['subscribers_sent'], 0)
        self.assertEqual(result['obituaries_count'], 2,
                         'the guard must still report what it saw')
        self.assertEqual(self.sent_digests, [],
                         'nothing may be sent from an instance with no subscribers')

    def test_result_carries_the_instance_fingerprint(self):
        self._add_obituary()
        result = self._run()
        self.assertIn('instance', result)
        self.assertIn('db=', result['instance'])

    def test_guard_does_not_fire_when_subscribers_exist(self):
        self._add_obituary('David Wayne De Leon', 'david-wayne-de-leon')
        self._add_subscriber()

        result = self._run()

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['subscribers_sent'], 1)
        self.assertEqual(self.sent_digests, ['reader@example.com'])

    def test_unconfirmed_subscribers_do_not_satisfy_the_guard(self):
        """Pending double-opt-in is not consent, and not a production signal."""
        self._add_obituary()
        self._add_subscriber('pending@example.com', confirmed=0)

        result = self._run()

        self.assertEqual(result['status'], 'skipped_no_subscribers')
        self.assertEqual(self.sent_digests, [])

    def test_a_genuinely_quiet_day_with_real_subscribers_still_sends(self):
        """No obituaries but real subscribers is a quiet day, not an alarm."""
        self._add_subscriber()
        result = self._run()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(self.sent_digests, ['reader@example.com'])


class HealthReportTests(DigestGuardTestBase):
    """The report must be loud, and must name its own deployment."""

    def _health_body(self):
        self.assertTrue(self.health_emails, 'no health email was produced')
        return self.health_emails[-1].get()['content'][0]['value']

    def _health_subject(self):
        return self.health_emails[-1].get()['subject']

    def _force_monday(self):
        # _send_health_summary only emails on Mondays.
        real_datetime = datetime

        class MondayDatetime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                base = real_datetime(2026, 8, 31, 7, 0, 0)   # a Monday
                return base
        return patch('daily_digest.datetime', MondayDatetime)

    def test_no_subscriber_report_is_unmistakable(self):
        self._add_obituary()
        with self._force_monday():
            self._run()

        body = self._health_body()
        self.assertIn('NO CONFIRMED SUBSCRIBERS', body)
        self.assertIn('The digest was NOT sent', body)
        self.assertIn('INSTANCE', body)
        self.assertIn('NO SUBSCRIBERS', self._health_subject())

    def test_normal_report_carries_instance_but_no_alarm(self):
        self._add_obituary()
        self._add_subscriber()
        with self._force_monday():
            self._run()

        body = self._health_body()
        self.assertIn('INSTANCE', body)
        self.assertNotIn('NO CONFIRMED SUBSCRIBERS', body)
        self.assertNotIn('NO SUBSCRIBERS', self._health_subject())


class FingerprintTests(unittest.TestCase):

    def test_fingerprint_names_the_database(self):
        with patch.dict(os.environ, {'DATABASE_PATH': '/data/neshama.db'}):
            self.assertIn('db=/data/neshama.db', instance_fingerprint())

    def test_fingerprint_includes_render_service_when_present(self):
        with patch.dict(os.environ, {'RENDER_SERVICE_NAME': 'neshama-staging',
                                     'RENDER_GIT_BRANCH': 'staging'}):
            fp = instance_fingerprint()
            self.assertIn('service=neshama-sta', fp)
            self.assertIn('branch=staging', fp)

    def test_fingerprint_survives_a_bare_local_environment(self):
        for var in ('RENDER_SERVICE_NAME', 'RENDER_GIT_BRANCH',
                    'RENDER_GIT_COMMIT', 'RENDER_INSTANCE_ID', 'DATABASE_PATH'):
            os.environ.pop(var, None)
        self.assertIn('host=', instance_fingerprint())


if __name__ == '__main__':
    unittest.main(verbosity=2)
