#!/usr/bin/env python3
"""
Tests for V2 features: co-organizer system, multi-date signup, email verification.
"""

import os
import sys
import sqlite3
import tempfile
import uuid
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from shiva_manager import ShivaManager


class V2TestBase(unittest.TestCase):
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
            'family_name': 'Cohen',
            'shiva_address': '123 Main St',
            'shiva_city': 'Toronto',
            'shiva_start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'shiva_end_date': (now + timedelta(days=5)).strftime('%Y-%m-%d'),
            'privacy_consent': True,
        }
        data.update(overrides)
        result = self.mgr.create_support(data)
        self.assertEqual(result['status'], 'success')
        return result


# ══════════════════════════════════════════════════════════════
# Co-Organizer Tests
# ══════════════════════════════════════════════════════════════

class TestCoOrganizerInvite(V2TestBase):

    def test_invite_co_organizer(self):
        """Primary organizer can invite a co-organizer."""
        shiva = self._create_shiva()
        result = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.assertEqual(result['status'], 'success')
        self.assertIn('co_token', result)
        self.assertEqual(result['invitee_email'], 'david@example.com')

    def test_cannot_invite_self(self):
        """Organizer cannot invite their own email."""
        shiva = self._create_shiva()
        result = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'Sarah Cohen', 'email': 'sarah@example.com'}
        )
        self.assertEqual(result['status'], 'error')
        self.assertIn('yourself', result['message'])

    def test_duplicate_invite_rejected(self):
        """Cannot send duplicate invite to same email."""
        shiva = self._create_shiva()
        self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        result = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.assertEqual(result['status'], 'error')
        self.assertIn('pending', result['message'])

    def test_only_primary_can_invite(self):
        """Co-organizer cannot invite others (only primary can)."""
        shiva = self._create_shiva()
        # Invite and accept co-organizer
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        # Co-organizer tries to invite — should fail
        result = self.mgr.invite_co_organizer(
            shiva['id'], invite['co_token'],
            {'name': 'Eve Green', 'email': 'eve@example.com'}
        )
        self.assertEqual(result['status'], 'error')
        self.assertIn('primary organizer', result['message'])


class TestCoOrganizerAccept(V2TestBase):

    def test_accept_invite(self):
        """Co-organizer can accept invitation."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        result = self.mgr.accept_co_organizer_invite(invite['co_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['shiva_id'], shiva['id'])

    def test_double_accept_handled(self):
        """Accepting twice returns already_accepted."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])
        result = self.mgr.accept_co_organizer_invite(invite['co_token'])
        self.assertEqual(result['status'], 'already_accepted')

    def test_invalid_token(self):
        """Invalid token returns error."""
        result = self.mgr.accept_co_organizer_invite('bogus-token')
        self.assertEqual(result['status'], 'error')


class TestCoOrganizerAuth(V2TestBase):

    def test_co_organizer_can_view_dashboard(self):
        """Accepted co-organizer can access organizer dashboard."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        # Co-organizer can view dashboard
        result = self.mgr.get_support_for_organizer(shiva['id'], invite['co_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['data']['family_name'], 'Cohen')

    def test_co_organizer_can_view_signups(self):
        """Accepted co-organizer can view meal signup details."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        result = self.mgr.get_signups_for_organizer(shiva['id'], invite['co_token'])
        self.assertEqual(result['status'], 'success')

    def test_co_organizer_can_update_page(self):
        """Accepted co-organizer can update page details."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        result = self.mgr.update_support(
            shiva['id'], invite['co_token'],
            {'family_notes': 'Please bring kosher food only'}
        )
        self.assertEqual(result['status'], 'success')

    def test_pending_co_organizer_cannot_access(self):
        """Pending (not yet accepted) co-organizer cannot access dashboard."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        # Do NOT accept — try to access with pending token
        result = self.mgr.get_support_for_organizer(shiva['id'], invite['co_token'])
        self.assertEqual(result['status'], 'error')


class TestCoOrganizerRevoke(V2TestBase):

    def test_revoke_co_organizer(self):
        """Primary organizer can revoke a co-organizer."""
        shiva = self._create_shiva()
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        # Get co-organizer list to find ID
        co_list = self.mgr.list_co_organizers(shiva['id'], shiva['magic_token'])
        co_id = co_list['data'][0]['id']

        result = self.mgr.revoke_co_organizer(shiva['id'], shiva['magic_token'], co_id)
        self.assertEqual(result['status'], 'success')

        # Revoked co-organizer cannot access anymore
        result = self.mgr.get_support_for_organizer(shiva['id'], invite['co_token'])
        self.assertEqual(result['status'], 'error')

    def test_re_invite_after_revoke(self):
        """Can re-invite a previously revoked co-organizer."""
        shiva = self._create_shiva()
        invite1 = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite1['co_token'])
        co_list = self.mgr.list_co_organizers(shiva['id'], shiva['magic_token'])
        co_id = co_list['data'][0]['id']
        self.mgr.revoke_co_organizer(shiva['id'], shiva['magic_token'], co_id)

        # Re-invite
        invite2 = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'David Levi', 'email': 'david@example.com'}
        )
        self.assertEqual(invite2['status'], 'success')


class TestListCoOrganizers(V2TestBase):

    def test_list_co_organizers(self):
        """List shows pending and accepted co-organizers."""
        shiva = self._create_shiva()
        self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'Alice', 'email': 'alice@example.com'}
        )
        invite = self.mgr.invite_co_organizer(
            shiva['id'], shiva['magic_token'],
            {'name': 'Bob', 'email': 'bob@example.com'}
        )
        self.mgr.accept_co_organizer_invite(invite['co_token'])

        result = self.mgr.list_co_organizers(shiva['id'], shiva['magic_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 2)
        statuses = {r['status'] for r in result['data']}
        self.assertEqual(statuses, {'pending', 'accepted'})


# ══════════════════════════════════════════════════════════════
# Multi-Date Signup Tests
# ══════════════════════════════════════════════════════════════

class TestMultiDateSignup(V2TestBase):

    def test_multi_date_signup(self):
        """Sign up for multiple dates at once."""
        # Use pause_shabbat=False to avoid Shabbat conflicts in tests
        shiva = self._create_shiva(pause_shabbat=False,
                                    shiva_end_date=(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'))
        now = datetime.now()
        # Use days 7-9 to avoid any date edge cases
        dates = [
            (now + timedelta(days=7)).strftime('%Y-%m-%d'),
            (now + timedelta(days=8)).strftime('%Y-%m-%d'),
            (now + timedelta(days=9)).strftime('%Y-%m-%d'),
        ]
        result = self.mgr.signup_meals_multi({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Alice Green',
            'volunteer_email': 'alice@example.com',
            'meal_type': 'Dinner',
            'privacy_consent': True,
            'meal_dates': dates,
        })
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['signups']), 3)
        self.assertIn('signup_group_id', result)
        self.assertEqual(result['family_name'], 'Cohen')

    def test_multi_signup_with_conflicts(self):
        """Partial success when some dates are already taken."""
        shiva = self._create_shiva(pause_shabbat=False,
                                    shiva_end_date=(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'))
        now = datetime.now()
        date1 = (now + timedelta(days=7)).strftime('%Y-%m-%d')
        date2 = (now + timedelta(days=8)).strftime('%Y-%m-%d')

        # Take date1
        self.mgr.signup_meal({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Bob White',
            'volunteer_email': 'bob@example.com',
            'meal_type': 'Dinner',
            'meal_date': date1,
            'privacy_consent': True,
        })

        # Multi-signup includes date1 (conflict) and date2 (available)
        result = self.mgr.signup_meals_multi({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Alice Green',
            'volunteer_email': 'alice@example.com',
            'meal_type': 'Dinner',
            'privacy_consent': True,
            'meal_dates': [date1, date2],
        })
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['signups']), 1)  # Only date2 succeeded
        self.assertEqual(len(result['errors']), 1)  # date1 failed

    def test_multi_signup_all_fail(self):
        """Error when no dates can be signed up."""
        shiva = self._create_shiva()
        result = self.mgr.signup_meals_multi({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Alice Green',
            'volunteer_email': 'alice@example.com',
            'meal_type': 'Dinner',
            'privacy_consent': True,
            'meal_dates': ['2020-01-01'],  # Way outside shiva range
        })
        self.assertEqual(result['status'], 'error')

    def test_multi_signup_group_id_shared(self):
        """All signups from same submission share a signup_group_id."""
        shiva = self._create_shiva(pause_shabbat=False,
                                    shiva_end_date=(datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'))
        now = datetime.now()
        dates = [
            (now + timedelta(days=7)).strftime('%Y-%m-%d'),
            (now + timedelta(days=8)).strftime('%Y-%m-%d'),
        ]
        result = self.mgr.signup_meals_multi({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Alice Green',
            'volunteer_email': 'alice@example.com',
            'meal_type': 'Dinner',
            'privacy_consent': True,
            'meal_dates': dates,
        })
        group_id = result['signup_group_id']

        # Verify in DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT signup_group_id FROM meal_signups WHERE shiva_support_id=?',
                    (shiva['id'],))
        rows = cur.fetchall()
        conn.close()

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['signup_group_id'] == group_id for r in rows))

    def test_max_dates_limit(self):
        """Reject more than 14 dates."""
        shiva = self._create_shiva()
        dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(15)]
        result = self.mgr.signup_meals_multi({
            'shiva_support_id': shiva['id'],
            'volunteer_name': 'Alice',
            'volunteer_email': 'alice@example.com',
            'meal_type': 'Dinner',
            'privacy_consent': True,
            'meal_dates': dates,
        })
        self.assertEqual(result['status'], 'error')
        self.assertIn('14', result['message'])


# ══════════════════════════════════════════════════════════════
# Email Verification Tests
# ══════════════════════════════════════════════════════════════

class TestEmailVerification(V2TestBase):

    def test_verification_token_created(self):
        """Creating a shiva page generates a verification token."""
        result = self._create_shiva()
        self.assertIn('verification_token', result)
        self.assertTrue(len(result['verification_token']) > 10)

    def test_verify_email(self):
        """Verify email with valid token."""
        shiva = self._create_shiva()
        result = self.mgr.verify_email(shiva['verification_token'])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['shiva_id'], shiva['id'])

        # Verify status in DB
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT verification_status, verified_at, verification_token FROM shiva_support WHERE id=?',
                    (shiva['id'],))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row['verification_status'], 'verified')
        self.assertIsNotNone(row['verified_at'])
        self.assertIsNone(row['verification_token'])  # Token cleared after use

    def test_double_verify(self):
        """Second verification returns already_verified."""
        shiva = self._create_shiva()
        self.mgr.verify_email(shiva['verification_token'])
        # Token is cleared, so using same token won't find the row
        result = self.mgr.verify_email(shiva['verification_token'])
        self.assertEqual(result['status'], 'error')  # Token no longer exists

    def test_invalid_token(self):
        """Invalid token returns error."""
        result = self.mgr.verify_email('invalid-token-abc')
        self.assertEqual(result['status'], 'error')

    def test_admin_verify(self):
        """Admin can manually verify email."""
        shiva = self._create_shiva()
        result = self.mgr.admin_verify_email(shiva['id'])
        self.assertEqual(result['status'], 'success')

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT verification_status FROM shiva_support WHERE id=?', (shiva['id'],))
        self.assertEqual(cur.fetchone()['verification_status'], 'admin_approved')
        conn.close()


# ══════════════════════════════════════════════════════════════
# V2 Field Updates Tests
# ══════════════════════════════════════════════════════════════

class TestV2FieldUpdates(V2TestBase):

    def test_update_drop_off_instructions(self):
        """Organizer can update drop-off instructions."""
        shiva = self._create_shiva()
        result = self.mgr.update_support(
            shiva['id'], shiva['magic_token'],
            {'drop_off_instructions': 'Leave food on the porch, buzzer #204'}
        )
        self.assertEqual(result['status'], 'success')

        data = self.mgr.get_support_for_organizer(shiva['id'], shiva['magic_token'])
        self.assertEqual(data['data']['drop_off_instructions'], 'Leave food on the porch, buzzer #204')

    def test_update_notification_prefs(self):
        """Organizer can update notification preferences."""
        shiva = self._create_shiva()
        result = self.mgr.update_support(
            shiva['id'], shiva['magic_token'],
            {'notification_prefs': '{"instant":false,"daily_summary":true,"uncovered_alert":false}'}
        )
        self.assertEqual(result['status'], 'success')

        data = self.mgr.get_support_for_organizer(shiva['id'], shiva['magic_token'])
        import json
        prefs = json.loads(data['data']['notification_prefs'])
        self.assertFalse(prefs['instant'])
        self.assertTrue(prefs['daily_summary'])
        self.assertFalse(prefs['uncovered_alert'])

    def test_create_with_drop_off_instructions(self):
        """Create shiva page with drop-off instructions."""
        result = self._create_shiva(drop_off_instructions='Ring bell twice')
        data = self.mgr.get_support_for_organizer(result['id'], result['magic_token'])
        self.assertEqual(data['data']['drop_off_instructions'], 'Ring bell twice')

    def test_create_with_source(self):
        """Create shiva page with custom source field."""
        result = self._create_shiva(source='funeral_home')
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT source FROM shiva_support WHERE id=?', (result['id'],))
        self.assertEqual(cur.fetchone()['source'], 'funeral_home')
        conn.close()


if __name__ == '__main__':
    unittest.main()
