#!/usr/bin/env python3
"""
Tests for V3 features: alternative contributions, organizer updates feed,
one-click thank-you notes.
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from shiva_manager import ShivaManager


class V3TestBase(unittest.TestCase):
    """Base class with temp DB and helper methods."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.mgr = ShivaManager(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _create_shiva(self, **overrides):
        """Create a shiva page via the manager and return the result."""
        now = datetime.now()
        data = {
            'organizer_name': 'Sarah Cohen',
            'organizer_email': 'sarah@example.com',
            'organizer_relationship': 'daughter',
            'family_name': 'Goldstein',
            'shiva_address': '123 Main St',
            'shiva_city': 'Toronto',
            'shiva_start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'shiva_end_date': (now + timedelta(days=5)).strftime('%Y-%m-%d'),
            'pause_shabbat': False,
            'privacy_consent': True,
        }
        data.update(overrides)
        result = self.mgr.create_support(data)
        self.assertEqual(result['status'], 'success')
        return result

    def _create_signup(self, shiva_id, **overrides):
        """Create a meal signup and return the result."""
        now = datetime.now()
        data = {
            'shiva_support_id': shiva_id,
            'volunteer_name': 'David Levi',
            'volunteer_email': 'david@example.com',
            'meal_date': now.strftime('%Y-%m-%d'),
            'meal_type': 'Dinner',
            'privacy_consent': True,
        }
        data.update(overrides)
        result = self.mgr.signup_meal(data)
        return result


# ══════════════════════════════════════════════════════════════
# V3 Migration Tests
# ══════════════════════════════════════════════════════════════

class TestV3Migrations(V3TestBase):

    def test_shiva_updates_table_created(self):
        """shiva_updates table exists after migration."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shiva_updates'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    def test_alternative_columns_on_meal_signups(self):
        """meal_signups has alternative_type and alternative_note columns."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(meal_signups)')
        cols = [row[1] for row in cursor.fetchall()]
        conn.close()
        self.assertIn('alternative_type', cols)
        self.assertIn('alternative_note', cols)

    def test_thank_you_sent_column_on_shiva_support(self):
        """shiva_support has thank_you_sent column."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(shiva_support)')
        cols = [row[1] for row in cursor.fetchall()]
        conn.close()
        self.assertIn('thank_you_sent', cols)

    def test_shiva_updates_index_created(self):
        """Index on shiva_updates.shiva_support_id exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_updates_shiva'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    def test_migrations_are_idempotent(self):
        """Running migrations twice does not error."""
        # Just re-init the manager; should not raise
        mgr2 = ShivaManager(self.db_path)
        self.assertIsNotNone(mgr2)


# ══════════════════════════════════════════════════════════════
# Alternative Contribution Tests
# ══════════════════════════════════════════════════════════════

class TestAlternativeContribution(V3TestBase):

    def test_alternative_signup_succeeds(self):
        """Can sign up with an alternative contribution type."""
        shiva = self._create_shiva()
        result = self._create_signup(
            shiva['id'],
            alternative_type='gift_card',
            alternative_note='Uber Eats $50',
            meal_description='Gift card - Uber Eats $50',
        )
        self.assertEqual(result['status'], 'success')

    def test_alternative_signup_stored_correctly(self):
        """Alternative type and note are stored in the database."""
        shiva = self._create_shiva()
        result = self._create_signup(
            shiva['id'],
            alternative_type='gift_basket',
            alternative_note='Baskits deluxe',
        )
        self.assertEqual(result['status'], 'success')

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT alternative_type, alternative_note, status FROM meal_signups WHERE id=?',
                        (result['signup_id'],))
        row = dict(cursor.fetchone())
        conn.close()

        self.assertEqual(row['alternative_type'], 'gift_basket')
        self.assertEqual(row['alternative_note'], 'Baskits deluxe')
        self.assertEqual(row['status'], 'alternative')

    def test_alternative_does_not_block_regular_signup(self):
        """An alternative contribution does not prevent a regular signup on the same slot."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        # Alternative signup
        r1 = self._create_signup(
            shiva['id'],
            meal_date=date,
            meal_type='Lunch',
            volunteer_name='Alt Person',
            volunteer_email='alt@example.com',
            alternative_type='vendor_meal',
        )
        self.assertEqual(r1['status'], 'success')

        # Regular signup on same slot should succeed
        r2 = self._create_signup(
            shiva['id'],
            meal_date=date,
            meal_type='Lunch',
            volunteer_name='Regular Person',
            volunteer_email='reg@example.com',
        )
        self.assertEqual(r2['status'], 'success')

    def test_regular_signup_blocks_duplicate(self):
        """A regular signup still blocks a second regular signup on the same slot."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        r1 = self._create_signup(
            shiva['id'],
            meal_date=date,
            meal_type='Dinner',
            volunteer_name='First',
            volunteer_email='first@example.com',
        )
        self.assertEqual(r1['status'], 'success')

        r2 = self._create_signup(
            shiva['id'],
            meal_date=date,
            meal_type='Dinner',
            volunteer_name='Second',
            volunteer_email='second@example.com',
        )
        self.assertEqual(r2['status'], 'error')
        self.assertIn('already signed up', r2['message'])

    def test_multiple_alternatives_same_slot(self):
        """Multiple alternative contributions on the same slot are allowed."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        for i in range(3):
            r = self._create_signup(
                shiva['id'],
                meal_date=date,
                meal_type='Lunch',
                volunteer_name=f'Alt {i}',
                volunteer_email=f'alt{i}@example.com',
                alternative_type='gift_card',
            )
            self.assertEqual(r['status'], 'success')

    def test_get_signups_includes_alternative_fields(self):
        """get_signups() returns alternative_type and alternative_note."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        self._create_signup(
            shiva['id'],
            meal_date=date,
            meal_type='Lunch',
            alternative_type='gift_card',
            alternative_note='Skip the Dishes',
        )

        signups = self.mgr.get_signups(shiva['id'])
        self.assertEqual(signups['status'], 'success')
        self.assertEqual(len(signups['data']), 1)
        self.assertEqual(signups['data'][0]['alternative_type'], 'gift_card')
        self.assertEqual(signups['data'][0]['alternative_note'], 'Skip the Dishes')
        self.assertEqual(signups['data'][0]['status'], 'alternative')


# ══════════════════════════════════════════════════════════════
# Organizer Updates Feed Tests
# ══════════════════════════════════════════════════════════════

class TestOrganizerUpdates(V3TestBase):

    def test_post_update(self):
        """Organizer can post an update."""
        shiva = self._create_shiva()
        result = self.mgr.post_update(shiva['id'], shiva['magic_token'],
                                       'Shiva hours are 7pm-9pm daily')
        self.assertEqual(result['status'], 'success')
        self.assertIn('update_id', result)

    def test_get_updates_returns_posted(self):
        """get_updates returns posted updates in descending order."""
        shiva = self._create_shiva()
        self.mgr.post_update(shiva['id'], shiva['magic_token'], 'First update')
        self.mgr.post_update(shiva['id'], shiva['magic_token'], 'Second update')

        result = self.mgr.get_updates(shiva['id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 2)
        # Most recent first
        self.assertEqual(result['data'][0]['message'], 'Second update')
        self.assertEqual(result['data'][1]['message'], 'First update')

    def test_updates_include_organizer_name(self):
        """Updates record the organizer's name as created_by."""
        shiva = self._create_shiva()
        self.mgr.post_update(shiva['id'], shiva['magic_token'], 'Test update')

        result = self.mgr.get_updates(shiva['id'])
        self.assertEqual(result['data'][0]['created_by'], 'Sarah Cohen')

    def test_delete_update(self):
        """Organizer can delete their own update."""
        shiva = self._create_shiva()
        post_result = self.mgr.post_update(shiva['id'], shiva['magic_token'], 'To delete')
        update_id = post_result['update_id']

        result = self.mgr.delete_update(shiva['id'], shiva['magic_token'], update_id)
        self.assertEqual(result['status'], 'success')

        # Verify it's gone
        updates = self.mgr.get_updates(shiva['id'])
        self.assertEqual(len(updates['data']), 0)

    def test_delete_nonexistent_update(self):
        """Deleting a non-existent update returns error."""
        shiva = self._create_shiva()
        result = self.mgr.delete_update(shiva['id'], shiva['magic_token'], 99999)
        self.assertEqual(result['status'], 'error')
        self.assertIn('not found', result['message'])

    def test_unauthorized_post(self):
        """Posting with wrong token fails."""
        shiva = self._create_shiva()
        result = self.mgr.post_update(shiva['id'], 'wrong-token', 'Should fail')
        self.assertEqual(result['status'], 'error')
        self.assertIn('Unauthorized', result['message'])

    def test_unauthorized_delete(self):
        """Deleting with wrong token fails."""
        shiva = self._create_shiva()
        post_result = self.mgr.post_update(shiva['id'], shiva['magic_token'], 'Test')
        result = self.mgr.delete_update(shiva['id'], 'wrong-token', post_result['update_id'])
        self.assertEqual(result['status'], 'error')

    def test_empty_update_rejected(self):
        """Empty or whitespace-only updates are rejected."""
        shiva = self._create_shiva()
        result = self.mgr.post_update(shiva['id'], shiva['magic_token'], '')
        self.assertEqual(result['status'], 'error')

        result = self.mgr.post_update(shiva['id'], shiva['magic_token'], '   ')
        self.assertEqual(result['status'], 'error')

    def test_co_organizer_can_post_update(self):
        """Accepted co-organizer can post updates."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        result = self.mgr.post_update(shiva['id'], invite['co_token'],
                                       'Update from co-organizer')
        self.assertEqual(result['status'], 'success')

    def test_get_updates_public(self):
        """Anyone can view updates (no token required)."""
        shiva = self._create_shiva()
        self.mgr.post_update(shiva['id'], shiva['magic_token'], 'Public update')

        # get_updates takes no token
        result = self.mgr.get_updates(shiva['id'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 1)

    def test_updates_sanitized(self):
        """Update messages are sanitized (truncated)."""
        shiva = self._create_shiva()
        long_msg = 'A' * 3000  # Way beyond MAX_TEXT_LENGTH
        result = self.mgr.post_update(shiva['id'], shiva['magic_token'], long_msg)
        self.assertEqual(result['status'], 'success')

        updates = self.mgr.get_updates(shiva['id'])
        # Message should be truncated
        self.assertLessEqual(len(updates['data'][0]['message']), 2000)


# ══════════════════════════════════════════════════════════════
# Thank-You Notes Tests
# ══════════════════════════════════════════════════════════════

class TestThankYouNotes(V3TestBase):

    def test_send_thank_you_notes(self):
        """Thank-you notes are queued for all volunteers."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice', volunteer_email='alice@example.com')
        self._create_signup(shiva['id'], meal_date=date, meal_type='Dinner',
                            volunteer_name='Bob', volunteer_email='bob@example.com')

        result = self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 2)

    def test_thank_you_once_only(self):
        """Thank-you notes can only be sent once per shiva page."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice', volunteer_email='alice@example.com')

        r1 = self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])
        self.assertEqual(r1['status'], 'success')

        r2 = self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])
        self.assertEqual(r2['status'], 'error')
        self.assertIn('already been sent', r2['message'])

    def test_thank_you_unauthorized(self):
        """Thank-you with wrong token fails."""
        shiva = self._create_shiva()
        result = self.mgr.send_thank_you_notes(shiva['id'], 'wrong-token')
        self.assertEqual(result['status'], 'error')
        self.assertIn('Unauthorized', result['message'])

    def test_thank_you_no_volunteers(self):
        """Thank-you with no volunteers returns error."""
        shiva = self._create_shiva()
        result = self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])
        self.assertEqual(result['status'], 'error')
        self.assertIn('No volunteers', result['message'])

    def test_thank_you_deduplicates_emails(self):
        """Same volunteer with multiple signups gets only one thank-you."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        # Same volunteer signs up twice (different meals)
        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice', volunteer_email='alice@example.com')
        self._create_signup(
            shiva['id'],
            meal_date=(now + timedelta(days=1)).strftime('%Y-%m-%d'),
            meal_type='Dinner',
            volunteer_name='Alice', volunteer_email='alice@example.com')

        result = self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 1)  # Deduplicated

    def test_thank_you_queues_to_email_log(self):
        """Thank-you notes create entries in email_log."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice Green', volunteer_email='alice@example.com')

        self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_log WHERE email_type='thank_you'")
        rows = cursor.fetchall()
        conn.close()

        self.assertEqual(len(rows), 1)
        row = dict(rows[0])
        self.assertEqual(row['recipient_email'], 'alice@example.com')
        self.assertEqual(row['status'], 'pending')

    def test_thank_you_marks_flag(self):
        """After sending, thank_you_sent flag is set on shiva_support."""
        shiva = self._create_shiva()
        now = datetime.now()
        date = now.strftime('%Y-%m-%d')

        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice', volunteer_email='alice@example.com')

        self.mgr.send_thank_you_notes(shiva['id'], shiva['magic_token'])

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT thank_you_sent FROM shiva_support WHERE id=?', (shiva['id'],))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row['thank_you_sent'], 1)

    def test_co_organizer_can_send_thank_you(self):
        """Accepted co-organizer can trigger thank-you notes."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        now = datetime.now()
        date = now.strftime('%Y-%m-%d')
        self._create_signup(shiva['id'], meal_date=date, meal_type='Lunch',
                            volunteer_name='Alice', volunteer_email='alice@example.com')

        result = self.mgr.send_thank_you_notes(shiva['id'], invite['co_token'])
        self.assertEqual(result['status'], 'success')


if __name__ == '__main__':
    unittest.main()
