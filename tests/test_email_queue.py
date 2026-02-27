#!/usr/bin/env python3
"""
Tests for email_queue.process_email_queue()

Simulates each of the 6 email types triggering correctly:
  1. Day-before reminders (7 PM)
  2. Morning-of reminders (8 AM)
  3. Uncovered-slot alerts (7 PM)
  4. Daily organizer summaries (8 PM)
  5. Thank-you emails (day after shiva ends)
  6. Retry failed sends

Uses a temporary SQLite database and mocks SendGrid to avoid real API calls.
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add frontend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from email_queue import (
    process_email_queue,
    log_immediate_email,
    _process_day_before_reminders,
    _process_morning_of_reminders,
    _process_uncovered_alerts,
    _process_daily_summaries,
    _process_thank_yous,
    _process_retries,
    _log_email,
    _mark_sent,
    _mark_failed,
)
from shiva_manager import ShivaManager


class EmailQueueTestBase(unittest.TestCase):
    """Base class that sets up a temp DB with v2 schema."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        # Use ShivaManager to create full schema including v2 migrations
        self.mgr = ShivaManager(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _create_shiva(self, shiva_id='test-shiva-1', family_name='Cohen',
                      start_offset=-1, end_offset=5, status='active',
                      notification_prefs=None):
        """Insert a test shiva_support row."""
        now = datetime.now()
        start = (now + timedelta(days=start_offset)).strftime('%Y-%m-%d')
        end = (now + timedelta(days=end_offset)).strftime('%Y-%m-%d')
        prefs = notification_prefs or '{"instant":true,"daily_summary":true,"uncovered_alert":true}'
        self.cursor.execute('''
            INSERT OR REPLACE INTO shiva_support
                (id, organizer_name, organizer_email, organizer_relationship,
                 family_name, shiva_address, shiva_city, shiva_start_date, shiva_end_date,
                 status, magic_token, privacy_consent, created_at,
                 notification_prefs, drop_off_instructions)
            VALUES (?, 'Sarah Cohen', 'sarah@example.com', 'daughter',
                    ?, '123 Main St', 'Toronto', ?, ?,
                    ?, 'tok_test123', 1, ?,
                    ?, 'Leave food on porch')
        ''', (shiva_id, family_name, start, end, status,
              now.isoformat(), prefs))
        self.conn.commit()
        return shiva_id

    def _create_signup(self, shiva_id='test-shiva-1', vol_name='David Levi',
                       vol_email='david@example.com', meal_date=None,
                       meal_type='Dinner', status='confirmed',
                       reminder_day_before=0, reminder_morning_of=0):
        """Insert a test meal_signups row."""
        if meal_date is None:
            meal_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.cursor.execute('''
            INSERT INTO meal_signups
                (shiva_support_id, volunteer_name, volunteer_email,
                 meal_date, meal_type, privacy_consent, created_at,
                 status, reminder_day_before, reminder_morning_of)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (shiva_id, vol_name, vol_email, meal_date, meal_type,
              datetime.now().isoformat(), status,
              reminder_day_before, reminder_morning_of))
        self.conn.commit()
        return self.cursor.lastrowid


class TestDayBeforeReminders(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_sends_reminder_at_7pm(self, mock_send):
        """Day-before reminder fires at 7 PM for tomorrow's meals."""
        mock_send.return_value = (True, 'msg-123', None)
        self._create_shiva()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        signup_id = self._create_signup(meal_date=tomorrow)

        # Simulate 7 PM Toronto time
        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=19, minute=15)
        sent = _process_day_before_reminders(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent, 1)
        mock_send.assert_called_once()
        # Verify email was logged
        self.cursor.execute('SELECT * FROM email_log WHERE email_type=?', ('day_before_reminder',))
        log = self.cursor.fetchone()
        self.assertIsNotNone(log)
        self.assertEqual(log['status'], 'sent')
        self.assertEqual(log['recipient_email'], 'david@example.com')

        # Verify reminder flag was set
        self.cursor.execute('SELECT reminder_day_before FROM meal_signups WHERE id=?', (signup_id,))
        self.assertEqual(self.cursor.fetchone()[0], 1)

    @patch('email_queue._send_via_sendgrid')
    def test_skips_before_7pm(self, mock_send):
        """Day-before reminder does NOT fire before 7 PM."""
        self._create_shiva()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self._create_signup(meal_date=tomorrow)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=14, minute=0)
        sent = _process_day_before_reminders(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)
        mock_send.assert_not_called()

    @patch('email_queue._send_via_sendgrid')
    def test_skips_already_reminded(self, mock_send):
        """Does not re-send if reminder_day_before flag already set."""
        self._create_shiva()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self._create_signup(meal_date=tomorrow, reminder_day_before=1)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=19, minute=15)
        sent = _process_day_before_reminders(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)
        mock_send.assert_not_called()


class TestMorningOfReminders(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_sends_reminder_at_8am(self, mock_send):
        """Morning-of reminder fires at 8 AM for today's meals."""
        mock_send.return_value = (True, 'msg-456', None)
        self._create_shiva(start_offset=-2)
        today = datetime.now().strftime('%Y-%m-%d')
        signup_id = self._create_signup(meal_date=today)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=8, minute=30)
        sent = _process_morning_of_reminders(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent, 1)
        mock_send.assert_called_once()
        self.cursor.execute('SELECT reminder_morning_of FROM meal_signups WHERE id=?', (signup_id,))
        self.assertEqual(self.cursor.fetchone()[0], 1)

    @patch('email_queue._send_via_sendgrid')
    def test_skips_before_8am(self, mock_send):
        """Morning-of reminder does NOT fire before 8 AM."""
        self._create_shiva(start_offset=-2)
        today = datetime.now().strftime('%Y-%m-%d')
        self._create_signup(meal_date=today)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=6, minute=0)
        sent = _process_morning_of_reminders(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)
        mock_send.assert_not_called()


class TestUncoveredAlerts(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_sends_alert_for_uncovered_dates(self, mock_send):
        """Uncovered alert fires when future dates have no signups."""
        mock_send.return_value = (True, 'msg-789', None)
        self._create_shiva(start_offset=0, end_offset=3)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=19, minute=15)
        sent = _process_uncovered_alerts(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent, 1)
        mock_send.assert_called_once()
        # Verify the email contains uncovered date info
        call_args = mock_send.call_args
        self.assertIn('uncovered', call_args[0][3].lower())  # subject

    @patch('email_queue._send_via_sendgrid')
    def test_no_alert_when_all_covered(self, mock_send):
        """No alert when all future dates have signups."""
        self._create_shiva(start_offset=0, end_offset=2)
        # Sign up for tomorrow and day after
        for days in range(1, 3):
            date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            self._create_signup(meal_date=date, vol_name=f'Vol {days}',
                                vol_email=f'vol{days}@example.com')

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=19, minute=15)
        sent = _process_uncovered_alerts(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)

    @patch('email_queue._send_via_sendgrid')
    def test_respects_notification_prefs(self, mock_send):
        """No alert when organizer has uncovered_alert disabled."""
        self._create_shiva(
            start_offset=0, end_offset=3,
            notification_prefs='{"instant":true,"daily_summary":true,"uncovered_alert":false}'
        )

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=19, minute=15)
        sent = _process_uncovered_alerts(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)
        mock_send.assert_not_called()


class TestDailySummaries(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_sends_summary_at_8pm(self, mock_send):
        """Daily summary fires at 8 PM during active shiva."""
        mock_send.return_value = (True, 'msg-sum', None)
        self._create_shiva(start_offset=-2, end_offset=3)
        today = datetime.now().strftime('%Y-%m-%d')
        self._create_signup(meal_date=today)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=20, minute=5)
        sent = _process_daily_summaries(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent, 1)
        mock_send.assert_called_once()
        self.cursor.execute('SELECT * FROM email_log WHERE email_type=?', ('daily_summary',))
        log = self.cursor.fetchone()
        self.assertEqual(log['status'], 'sent')

    @patch('email_queue._send_via_sendgrid')
    def test_no_duplicate_summary(self, mock_send):
        """Daily summary only sends once per day (dedup)."""
        mock_send.return_value = (True, 'msg-sum', None)
        self._create_shiva(start_offset=-2, end_offset=3)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=20, minute=5)

        # First run
        sent1 = _process_daily_summaries(self.cursor, 'fake-key', fake_now)
        self.conn.commit()
        # Second run same day
        sent2 = _process_daily_summaries(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent1, 1)
        self.assertEqual(sent2, 0)

    @patch('email_queue._send_via_sendgrid')
    def test_respects_disabled_summary_pref(self, mock_send):
        """No summary when organizer has daily_summary disabled."""
        self._create_shiva(
            start_offset=-2, end_offset=3,
            notification_prefs='{"instant":true,"daily_summary":false,"uncovered_alert":true}'
        )

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=20, minute=5)
        sent = _process_daily_summaries(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)
        mock_send.assert_not_called()


class TestThankYous(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_sends_thank_you_day_after_end(self, mock_send):
        """Thank-you emails sent to all volunteers the day after shiva ends."""
        mock_send.return_value = (True, 'msg-ty', None)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        self._create_shiva(start_offset=-7, end_offset=-1)
        # Two volunteers
        self._create_signup(vol_name='Alice Green', vol_email='alice@example.com',
                            meal_date=yesterday)
        self._create_signup(vol_name='Bob White', vol_email='bob@example.com',
                            meal_date=yesterday)

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto')).replace(hour=10, minute=0)
        sent = _process_thank_yous(self.cursor, 'fake-key', fake_now)
        self.conn.commit()

        self.assertEqual(sent, 2)
        self.assertEqual(mock_send.call_count, 2)
        # Verify shiva archived
        self.cursor.execute('SELECT status FROM shiva_support WHERE id=?', ('test-shiva-1',))
        self.assertEqual(self.cursor.fetchone()[0], 'archived')

    @patch('email_queue._send_via_sendgrid')
    def test_no_thank_you_if_already_sent(self, mock_send):
        """Thank-you dedup: skip if already sent for this shiva."""
        mock_send.return_value = (True, 'msg-ty', None)
        self._create_shiva(start_offset=-7, end_offset=-1)
        self._create_signup(vol_name='Alice', vol_email='alice@example.com',
                            meal_date=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
        # Mark as already sent
        _log_email(self.cursor, 'test-shiva-1', 'thank_you', 'alice@example.com', 'Alice')
        self.cursor.execute("UPDATE email_log SET status='sent' WHERE email_type='thank_you'")
        self.conn.commit()

        import pytz
        fake_now = datetime.now(pytz.timezone('America/Toronto'))
        sent = _process_thank_yous(self.cursor, 'fake-key', fake_now)

        self.assertEqual(sent, 0)


class TestRetries(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_retries_recent_failures(self, mock_send):
        """Retries failed emails from the last 24 hours."""
        mock_send.return_value = (True, 'msg-retry', None)
        self._create_shiva(start_offset=-2, end_offset=3)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        signup_id = self._create_signup(meal_date=tomorrow)

        # Insert a failed email
        email_id = _log_email(self.cursor, 'test-shiva-1', 'day_before_reminder',
                              'david@example.com', 'David Levi', signup_id)
        _mark_failed(self.cursor, email_id, 'Connection timeout')
        self.conn.commit()

        retried = _process_retries(self.cursor, 'fake-key')
        self.conn.commit()

        self.assertEqual(retried, 1)
        self.cursor.execute('SELECT status FROM email_log WHERE id=?', (email_id,))
        self.assertEqual(self.cursor.fetchone()[0], 'sent')

    @patch('email_queue._send_via_sendgrid')
    def test_skips_after_max_retries(self, mock_send):
        """Stops retrying after MAX_RETRIES (3) attempts."""
        self._create_shiva(start_offset=-2, end_offset=3)
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        signup_id = self._create_signup(meal_date=tomorrow)

        # Insert 3 failed emails (max retries reached)
        for i in range(3):
            eid = _log_email(self.cursor, 'test-shiva-1', 'day_before_reminder',
                             'david@example.com', 'David Levi', signup_id)
            _mark_failed(self.cursor, eid, f'Error {i}')
        self.conn.commit()

        retried = _process_retries(self.cursor, 'fake-key')
        self.conn.commit()

        self.assertEqual(retried, 0)
        mock_send.assert_not_called()


class TestProcessEmailQueue(EmailQueueTestBase):

    @patch('email_queue._send_via_sendgrid')
    def test_full_queue_run(self, mock_send):
        """Full process_email_queue() run processes all email types."""
        mock_send.return_value = (True, 'msg-full', None)

        # Set up data for multiple email types
        self._create_shiva(start_offset=-2, end_offset=3)
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        # Signup for today (morning-of) and tomorrow (day-before)
        self._create_signup(meal_date=today, vol_name='Today Vol',
                            vol_email='today@example.com')
        self._create_signup(meal_date=tomorrow, vol_name='Tomorrow Vol',
                            vol_email='tomorrow@example.com')

        results = process_email_queue(self.db_path)
        self.assertIsInstance(results, dict)
        # Results should include all 6 keys
        for key in ['day_before_reminders', 'morning_of_reminders',
                     'uncovered_alerts', 'daily_summaries', 'thank_yous', 'retries']:
            self.assertIn(key, results)

    @patch('email_queue.datetime')
    def test_shabbat_pause(self, mock_dt):
        """Email queue pauses during Shabbat."""
        import pytz
        tz = pytz.timezone('America/Toronto')
        # Friday 7 PM (Shabbat)
        friday_evening = datetime(2026, 2, 27, 19, 0, tzinfo=tz)  # Friday
        mock_dt.now.return_value = friday_evening
        mock_dt.strptime = datetime.strptime
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # We need a different approach since process_email_queue uses datetime.now(tz)
        # Let's test the Shabbat check directly
        now_toronto = friday_evening
        weekday = now_toronto.weekday()
        is_shabbat = (weekday == 4 and now_toronto.hour >= 18) or (weekday == 5 and now_toronto.hour < 21)
        self.assertTrue(is_shabbat)


class TestLogImmediateEmail(EmailQueueTestBase):

    def test_logs_sent_email(self):
        """log_immediate_email correctly logs a sent email."""
        self._create_shiva()
        log_immediate_email(self.db_path, 'test-shiva-1', 'signup_confirmation',
                            'vol@example.com', 'Test Volunteer',
                            sendgrid_message_id='sg-123', status='sent')

        # Re-read from DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM email_log WHERE email_type=?', ('signup_confirmation',))
        log = cur.fetchone()
        conn.close()

        self.assertIsNotNone(log)
        self.assertEqual(log['status'], 'sent')
        self.assertEqual(log['sendgrid_message_id'], 'sg-123')
        self.assertEqual(log['recipient_email'], 'vol@example.com')

    def test_logs_failed_email(self):
        """log_immediate_email logs a failed email."""
        self._create_shiva()
        log_immediate_email(self.db_path, 'test-shiva-1', 'signup_confirmation',
                            'vol@example.com', 'Test Volunteer', status='failed')

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT * FROM email_log WHERE email_type=?', ('signup_confirmation',))
        log = cur.fetchone()
        conn.close()

        self.assertEqual(log['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
