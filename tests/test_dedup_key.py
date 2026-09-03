#!/usr/bin/env python3
"""
Tests for the stable obituary identity (obituary_identity.source_key) and the
digest sent-log.

The case these exist for, taken from real production data:

  David Wayne De Leon (Steeles) was announced as a NEW obituary in both the
  2026-08-27 and 2026-08-28 daily digests. The Aug 27 email carried no shiva
  line; the Aug 28 email carried one. Only one row survives in production
  (first_seen 2026-08-28T02:58:24), so the Aug 27 row was a different row with
  a different id - the identity hash changed when late-arriving fields landed.

Run:  python3 -m pytest tests/test_dedup_key.py -v
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(REPO_ROOT))
sys.path.insert(0, os.path.abspath(os.path.join(REPO_ROOT, 'frontend')))

from database_setup import NeshamaDatabase
from obituary_identity import source_key, announce_key, names_look_unrelated


STEELES = 'Steeles Memorial Chapel'
DE_LEON_URL = 'https://steelesmemorialchapel.com/condolence/david-wayne-de-leon/'


def preliminary_listing():
    """First scrape: the funeral home has published a name and a URL, nothing else."""
    return {
        'source': STEELES,
        'source_url': DE_LEON_URL,
        'condolence_url': DE_LEON_URL,
        'deceased_name': 'David Wayne De Leon',
        'city': 'Toronto',
    }


def filled_in_listing():
    """Re-scrape hours later: date_of_death and shiva detail have landed."""
    data = preliminary_listing()
    data['date_of_death'] = 'August 26, 2026'
    data['shiva_info'] = 'Shiva at the family home, Thursday 2-5pm'
    data['burial_location'] = 'Dawes Road Cemetery'
    return data


class IdentityKeyTests(unittest.TestCase):
    """source_key must be derivable and stable across every live source."""

    def test_key_derived_for_each_funeral_home(self):
        cases = [
            (STEELES, DE_LEON_URL, 'steeles:david-wayne-de-leon'),
            ("Benjamin's Park Memorial Chapel",
             'https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=142228&fg=0',
             'benjamins:142228'),
            ('Misaskim',
             'https://misaskim.ca/shiva-listings/mr-nathan-grunbaum-zl/',
             'misaskim:mr-nathan-grunbaum-zl'),
            ('Paperman & Sons',
             'https://www.paperman.com/funerals/Sandra-Dubrofsky-née-Cherry-998C37A6',
             'paperman:998c37a6'),
        ]
        for source, url, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(source_key(source, url), expected)

    def test_key_survives_a_name_change(self):
        """The dominant real-world mutation: the home edits the displayed name.

        Paperman embeds the name in its slug, so the whole URL changes - only
        the trailing hex is stable. This is why we key on the hex, not the URL.
        """
        a = source_key('Paperman & Sons',
                       'https://www.paperman.com/funerals/Julie-Nataf-676277EA')
        b = source_key('Paperman & Sons',
                       'https://www.paperman.com/funerals/Jacqueline-Salama-Nataf-676277ea')
        self.assertEqual(a, b)

    def test_key_ignores_cosmetic_url_differences(self):
        base = source_key("Benjamin's Park Memorial Chapel",
                          'https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=142228&fg=0')
        self.assertEqual(base, source_key(
            "Benjamin's Park Memorial Chapel",
            'https://BenjaminsParkMemorialChapel.ca/servicedetails.aspx?snum=142228'))

    def test_no_url_yields_no_key(self):
        self.assertIsNone(source_key(STEELES, None))
        self.assertIsNone(source_key(STEELES, '   '))

    def test_renames_are_not_flagged_as_unrelated(self):
        """All ten of these are one person renamed, taken from production."""
        for a, b in [
            ('Yosi Derman', 'Jonathan Derman'),
            ('Zippe Blitstein', 'Sandra Blitstein'),
            ('Tony Belchetz', 'Anthony BELCHETZ'),
            ('Gerald "Jerry" Gold', 'Jerry Gold'),
            ('Simon Chouchan', 'Simon Chauchan'),
            ('Avi Benshabat', 'Avi Avrum Benshabat'),
            ('Hy Goldstein', 'Hyman Goldstein'),
        ]:
            with self.subTest(pair=(a, b)):
                self.assertFalse(names_look_unrelated(a, b))

    def test_genuinely_unrelated_names_are_flagged(self):
        self.assertTrue(names_look_unrelated('David De Leon', 'Miriam Kaplan'))


class UpsertTests(unittest.TestCase):
    """scrape -> re-scrape must UPDATE, never INSERT a second row."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db = NeshamaDatabase(self.db_path)
        self.db.create_tables()

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            try:
                os.unlink(self.db_path + suffix)
            except OSError:
                pass

    def _rows(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute('SELECT * FROM obituaries').fetchall()]
        conn.close()
        return rows

    def test_rescrape_with_late_date_of_death_updates_one_row(self):
        """The exact De Leon sequence. This is the regression."""
        first_id, first_action = self.db.upsert_obituary(preliminary_listing())
        self.assertEqual(first_action, 'inserted')

        second_id, second_action = self.db.upsert_obituary(filled_in_listing())
        self.assertEqual(second_action, 'updated')

        rows = self._rows()
        self.assertEqual(len(rows), 1, f"expected 1 row, got {len(rows)}: "
                                       f"{[r['deceased_name'] for r in rows]}")
        self.assertEqual(first_id, second_id, "row id must not change - URLs would break")
        self.assertEqual(rows[0]['date_of_death'], 'August 26, 2026')
        self.assertEqual(rows[0]['source_key'], 'steeles:david-wayne-de-leon')

    def test_rescrape_with_changed_name_updates_one_row(self):
        """65/65 production duplicate groups had a changed name. Avi Benshabat, Aug 30."""
        url = 'https://steelesmemorialchapel.com/condolence/avi-benshabat/'
        base = {'source': STEELES, 'source_url': url, 'condolence_url': url,
                'deceased_name': 'Avi Benshabat', 'city': 'Toronto'}
        first_id, _ = self.db.upsert_obituary(dict(base))

        renamed = dict(base, deceased_name='Avi Avrum Benshabat')
        second_id, action = self.db.upsert_obituary(renamed)

        self.assertEqual(action, 'updated')
        self.assertEqual(first_id, second_id)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['deceased_name'], 'Avi Avrum Benshabat')

    def test_two_different_people_same_name_same_home_stay_separate(self):
        """The edge case the old name-based key could not handle at all.

        The funeral home assigns each of them a different URL, so they get
        different keys and remain two rows - by construction, no time window.
        """
        a_url = 'https://steelesmemorialchapel.com/condolence/david-cohen/'
        b_url = 'https://steelesmemorialchapel.com/condolence/david-cohen-2/'
        self.db.upsert_obituary({
            'source': STEELES, 'source_url': a_url, 'condolence_url': a_url,
            'deceased_name': 'David Cohen', 'date_of_death': 'March 3, 2026',
            'city': 'Toronto'})
        self.db.upsert_obituary({
            'source': STEELES, 'source_url': b_url, 'condolence_url': b_url,
            'deceased_name': 'David Cohen', 'date_of_death': 'August 14, 2026',
            'city': 'Toronto'})

        rows = self._rows()
        self.assertEqual(len(rows), 2, "two different people must not be merged")
        self.assertEqual(len({r['source_key'] for r in rows}), 2)

    def test_legacy_row_without_source_key_is_matched_and_backfilled(self):
        """Rows written before this change must not fork on the next scrape."""
        legacy = preliminary_listing()
        legacy_id, _ = self.db.upsert_obituary(legacy)

        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE obituaries SET source_key = NULL')
        conn.commit()
        conn.close()

        same_id, action = self.db.upsert_obituary(filled_in_listing())
        self.assertEqual(action, 'updated')
        self.assertEqual(same_id, legacy_id)
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source_key'], 'steeles:david-wayne-de-leon')

    def test_unchanged_rescrape_reports_unchanged(self):
        self.db.upsert_obituary(filled_in_listing())
        _, action = self.db.upsert_obituary(filled_in_listing())
        self.assertEqual(action, 'unchanged')

    def test_oldest_id_survives_when_duplicates_already_exist(self):
        """Production shape: two rows for one person already exist, unkeyed.

        The next scrape must update the OLDER row and leave its id intact.
        Memorial URLs are shared in WhatsApp groups and indexed by Google.
        """
        conn = sqlite3.connect(self.db_path)
        older = (datetime.now() - timedelta(days=2)).isoformat()
        newer = (datetime.now() - timedelta(days=1)).isoformat()
        for row_id, name, seen in [('old-id', 'Avi Benshabat', older),
                                   ('new-id', 'Avi Avrum Benshabat', newer)]:
            conn.execute(
                "INSERT INTO obituaries (id, source, source_url, condolence_url, "
                "deceased_name, city, scraped_at, first_seen, last_updated, "
                "content_hash, source_key) VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                (row_id, STEELES,
                 'https://steelesmemorialchapel.com/condolence/avi-benshabat/',
                 'https://steelesmemorialchapel.com/condolence/avi-benshabat/',
                 name, 'Toronto', seen, seen, seen, 'seed-' + row_id))
        conn.commit()
        conn.close()

        self.db.create_tables()          # backfills source_key, as at startup

        url = 'https://steelesmemorialchapel.com/condolence/avi-benshabat/'
        returned_id, action = self.db.upsert_obituary({
            'source': STEELES, 'source_url': url, 'condolence_url': url,
            'deceased_name': 'Avi Avrum Benshabat',
            'date_of_death': 'August 29, 2026', 'city': 'Toronto'})

        self.assertEqual(action, 'updated')
        self.assertEqual(returned_id, 'old-id', 'the oldest id must survive')

        ids = {r['id'] for r in self._rows()}
        self.assertEqual(len(ids), 2, 'the scrape must not add a third row')
        self.assertIn('old-id', ids)
        self.assertIn('new-id', ids, 'pre-existing rows are merged by the migration, not here')


class DigestNoRepeatTests(unittest.TestCase):
    """One appearance across two consecutive digests."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        self.db = NeshamaDatabase(self.db_path)
        self.db.create_tables()

        from daily_digest import DailyDigestSender
        with patch.object(
            __import__('subscription_manager').EmailSubscriptionManager,
            'create_subscribers_table', lambda self: None
        ):
            pass
        self.sender = DailyDigestSender(db_path=self.db_path,
                                        sendgrid_api_key='test-key')
        self._seed_subscriber()

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            try:
                os.unlink(self.db_path + suffix)
            except OSError:
                pass

    def _seed_subscriber(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO subscribers (email, unsubscribe_token, confirmed, "
            "frequency, locations, subscribed_at) VALUES (?,?,?,?,?,?)",
            ('reader@example.com', 'tok-1', 1, 'daily', 'toronto,montreal',
             datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def _run_digest(self):
        """Run a digest with SendGrid stubbed out; return the obit names sent."""
        captured = []

        def fake_send(email, token, html, locations=None, obit_count=None):
            captured.append(html or '')
            return {'success': True, 'status_code': 202}

        with patch.object(self.sender, 'send_digest_to_subscriber', fake_send), \
             patch.object(self.sender, '_send_health_summary', lambda r: None):
            self.sender.send_daily_digest()
        return captured

    def test_person_appears_in_exactly_one_of_two_consecutive_digests(self):
        # Day 1: preliminary listing, no date_of_death.
        self.db.upsert_obituary(preliminary_listing())
        day_one = self._run_digest()
        self.assertTrue(any('David Wayne De Leon' in h for h in day_one),
                        "should be announced on the first digest")

        # Between digests the funeral home fills in the detail.
        self.db.upsert_obituary(filled_in_listing())

        # Day 2: the same person, now with more detail, must NOT reappear.
        day_two = self._run_digest()
        self.assertFalse(any('David Wayne De Leon' in h for h in day_two),
                         "De Leon was announced twice - the Aug 27/28 regression")

    def test_sent_log_survives_a_duplicate_row(self):
        """Even if a duplicate row is somehow created, no second announcement."""
        self.db.upsert_obituary(preliminary_listing())
        self._run_digest()

        # Force the exact failure the old key produced: a second row, new id,
        # same person, same funeral-home URL.
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO obituaries (id, source, source_url, deceased_name, "
            "condolence_url, city, scraped_at, first_seen, last_updated, "
            "content_hash, source_key) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ('forced-duplicate-id', STEELES, DE_LEON_URL, 'David Wayne De Leon',
             DE_LEON_URL, 'Toronto', datetime.now().isoformat(),
             datetime.now().isoformat(), datetime.now().isoformat(),
             'different-hash', 'steeles:david-wayne-de-leon')
        )
        conn.commit()
        conn.close()

        day_two = self._run_digest()
        self.assertFalse(any('David Wayne De Leon' in h for h in day_two),
                         "sent-log must suppress a duplicate row too")

    def test_a_genuinely_new_person_is_still_announced(self):
        """The guard must not swallow real news."""
        self.db.upsert_obituary(preliminary_listing())
        self._run_digest()

        other_url = 'https://steelesmemorialchapel.com/condolence/miriam-kaplan/'
        self.db.upsert_obituary({
            'source': STEELES, 'source_url': other_url,
            'condolence_url': other_url, 'deceased_name': 'Miriam Kaplan',
            'city': 'Toronto'})

        day_two = self._run_digest()
        self.assertTrue(any('Miriam Kaplan' in h for h in day_two))
        self.assertFalse(any('David Wayne De Leon' in h for h in day_two))


if __name__ == '__main__':
    unittest.main(verbosity=2)
