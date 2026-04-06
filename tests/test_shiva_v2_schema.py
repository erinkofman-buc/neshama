"""
Tests for V7 schema migration — Meal Planner Redesign columns.
Verifies that ShivaManager.setup_database() adds all new columns
to shiva_support and meal_signups tables.
"""

import json
import os
import sys
import sqlite3
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))
from shiva_manager import ShivaManager


class TestV7SchemaColumns(unittest.TestCase):
    """Verify V7 migration adds all expected columns."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.manager = ShivaManager(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _get_columns(self, table):
        conn = sqlite3.connect(self.tmp.name)
        cursor = conn.execute(f'PRAGMA table_info({table})')
        cols = {row[1] for row in cursor.fetchall()}
        conn.close()
        return cols

    # ── shiva_support columns ────────────────────────────────

    def test_burial_date_column(self):
        self.assertIn('burial_date', self._get_columns('shiva_support'))

    def test_kosher_column(self):
        self.assertIn('kosher', self._get_columns('shiva_support'))

    def test_num_adults_column(self):
        self.assertIn('num_adults', self._get_columns('shiva_support'))

    def test_num_kids_column(self):
        self.assertIn('num_kids', self._get_columns('shiva_support'))

    def test_lunch_dropoff_start_column(self):
        self.assertIn('lunch_dropoff_start', self._get_columns('shiva_support'))

    def test_lunch_dropoff_end_column(self):
        self.assertIn('lunch_dropoff_end', self._get_columns('shiva_support'))

    def test_dinner_dropoff_start_column(self):
        self.assertIn('dinner_dropoff_start', self._get_columns('shiva_support'))

    def test_dinner_dropoff_end_column(self):
        self.assertIn('dinner_dropoff_end', self._get_columns('shiva_support'))

    def test_suggested_caterers_column(self):
        self.assertIn('suggested_caterers', self._get_columns('shiva_support'))

    def test_custom_suggestions_column(self):
        self.assertIn('custom_suggestions', self._get_columns('shiva_support'))

    def test_organizer_contact_visible_column(self):
        self.assertIn('organizer_contact_visible', self._get_columns('shiva_support'))

    def test_enabled_meals_column(self):
        self.assertIn('enabled_meals', self._get_columns('shiva_support'))

    # ── meal_signups columns ─────────────────────────────────

    def test_group_name_column(self):
        self.assertIn('group_name', self._get_columns('meal_signups'))

    def test_contact_phone_column(self):
        self.assertIn('contact_phone', self._get_columns('meal_signups'))

    def test_is_walkin_column(self):
        self.assertIn('is_walkin', self._get_columns('meal_signups'))

    # ── Idempotency ──────────────────────────────────────────

    def test_idempotent_migration(self):
        """Running setup_database() twice should not raise."""
        self.manager.setup_database()
        cols_support = self._get_columns('shiva_support')
        cols_signups = self._get_columns('meal_signups')
        self.assertIn('burial_date', cols_support)
        self.assertIn('is_walkin', cols_signups)


class TestSearchActiveShivas(unittest.TestCase):
    """Verify search_active_shivas returns correct results."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.manager = ShivaManager(db_path=self.tmp.name)
        # Create a test shiva
        self.test_data = {
            'privacy_consent': 1,
            'organizer_name': 'Test User',
            'organizer_email': 'test@example.com',
            'family_name': 'Goldberg',
            'shiva_start_date': '2026-04-06',
            'shiva_end_date': '2026-04-12',
            'organizer_relationship': 'Friend',
            'shiva_city': 'Toronto',
            '_skip_similar': True,
        }
        result = self.manager.create_support(self.test_data)
        self.assertEqual(result['status'], 'success')
        self.shiva_id = result['id']

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_search_exact_name(self):
        results = self.manager.search_active_shivas('Goldberg')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['family_name'], 'Goldberg')
        self.assertEqual(results[0]['id'], self.shiva_id)

    def test_search_prefix(self):
        results = self.manager.search_active_shivas('Gold')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['family_name'], 'Goldberg')

    def test_search_no_match(self):
        results = self.manager.search_active_shivas('Ramirez')
        self.assertEqual(len(results), 0)

    def test_search_returns_expected_fields(self):
        results = self.manager.search_active_shivas('Goldberg')
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIn('id', row)
        self.assertIn('family_name', row)
        self.assertIn('shiva_start_date', row)
        self.assertIn('shiva_end_date', row)
        self.assertIn('shiva_city', row)

    def test_search_short_query_returns_empty(self):
        results = self.manager.search_active_shivas('G')
        self.assertEqual(len(results), 0)


class TestV2CreateWithV7Fields(unittest.TestCase):
    """Verify create_support stores V7 meal planner fields."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.manager = ShivaManager(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_v7_fields_persisted(self):
        """Create a shiva with all V7 fields and verify they are stored."""
        import json
        data = {
            'privacy_consent': 1,
            'organizer_name': 'Sarah Cohen',
            'organizer_email': 'sarah@example.com',
            'family_name': 'Cohen',
            'shiva_start_date': '2026-04-10',
            'shiva_end_date': '2026-04-16',
            'shiva_city': 'Toronto',
            '_skip_similar': True,
            # V7 fields
            'burial_date': '2026-04-09',
            'kosher': True,
            'num_adults': 15,
            'num_kids': 5,
            'lunch_dropoff_start': '11:30',
            'lunch_dropoff_end': '12:30',
            'dinner_dropoff_start': '17:00',
            'dinner_dropoff_end': '18:00',
            'suggested_caterers': ['koshers-r-us', 'toronto-catering'],
            'custom_suggestions': ['Please bring paper plates', 'Nut-free preferred'],
            'organizer_contact_visible': True,
            'enabled_meals': ['Lunch', 'Dinner'],
            'family_notes': 'The family prefers vegetarian options.',
        }
        result = self.manager.create_support(data)
        self.assertEqual(result['status'], 'success')
        shiva_id = result['id']

        # Query DB directly to verify V7 fields
        conn = sqlite3.connect(self.tmp.name)
        cursor = conn.execute(
            'SELECT burial_date, kosher, num_adults, num_kids, '
            'lunch_dropoff_start, lunch_dropoff_end, dinner_dropoff_start, dinner_dropoff_end, '
            'suggested_caterers, custom_suggestions, organizer_contact_visible, enabled_meals, '
            'family_notes FROM shiva_support WHERE id = ?',
            (shiva_id,)
        )
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], '2026-04-09')       # burial_date
        self.assertEqual(row[1], 1)                     # kosher (integer: 1=yes, 0=no)
        self.assertEqual(row[2], 15)                   # num_adults
        self.assertEqual(row[3], 5)                    # num_kids
        self.assertEqual(row[4], '11:30')              # lunch_dropoff_start
        self.assertEqual(row[5], '12:30')              # lunch_dropoff_end
        self.assertEqual(row[6], '17:00')              # dinner_dropoff_start
        self.assertEqual(row[7], '18:00')              # dinner_dropoff_end
        self.assertEqual(json.loads(row[8]), ['koshers-r-us', 'toronto-catering'])
        self.assertEqual(json.loads(row[9]), ['Please bring paper plates', 'Nut-free preferred'])
        self.assertEqual(int(row[10]), 1)               # organizer_contact_visible
        self.assertEqual(json.loads(row[11]), ['Lunch', 'Dinner'])
        self.assertIn('vegetarian', row[12])           # family_notes

    def test_v7_fields_optional(self):
        """Create a shiva WITHOUT V7 fields — should still succeed with defaults."""
        data = {
            'privacy_consent': 1,
            'organizer_name': 'David Levi',
            'organizer_email': 'david@example.com',
            'family_name': 'Levi',
            'shiva_start_date': '2026-04-10',
            'shiva_end_date': '2026-04-16',
            '_skip_similar': True,
        }
        result = self.manager.create_support(data)
        self.assertEqual(result['status'], 'success')

        # V7 columns should be NULL
        conn = sqlite3.connect(self.tmp.name)
        cursor = conn.execute(
            'SELECT burial_date, kosher, num_adults, num_kids FROM shiva_support WHERE id = ?',
            (result['id'],)
        )
        row = cursor.fetchone()
        conn.close()
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])
        self.assertIsNone(row[3])


class TestMultipleSignups(unittest.TestCase):
    """Verify multiple groups can sign up for the same meal slot."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.manager = ShivaManager(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _create_test_shiva(self):
        result = self.manager.create_support({
            'family_name': 'TestFamily',
            'organizer_name': 'Test Org',
            'organizer_email': 'test@test.com',
            'organizer_relationship': 'Friend',
            'shiva_start_date': '2026-04-06',
            'shiva_end_date': '2026-04-12',
            'shiva_address': '1 Main St',
            'shiva_city': 'Toronto',
            'privacy_consent': 1,
            '_skip_similar': True
        })
        return result['id']

    def test_multiple_groups_same_meal(self):
        shiva_id = self._create_test_shiva()
        # First signup
        r1 = self.manager.signup_meal({
            'shiva_support_id': shiva_id,
            'volunteer_name': 'Sarah',
            'volunteer_email': 'sarah@test.com',
            'meal_date': '2026-04-07',
            'meal_type': 'Dinner',
            'meal_description': 'Chicken soup',
            'privacy_consent': 1
        })
        self.assertEqual(r1['status'], 'success')
        # Second signup for SAME slot
        r2 = self.manager.signup_meal({
            'shiva_support_id': shiva_id,
            'volunteer_name': 'Rachel',
            'volunteer_email': 'rachel@test.com',
            'meal_date': '2026-04-07',
            'meal_type': 'Dinner',
            'meal_description': 'Salad and bread',
            'privacy_consent': 1
        })
        self.assertEqual(r2['status'], 'success')

    def test_multiple_signups_different_types_still_work(self):
        shiva_id = self._create_test_shiva()
        r1 = self.manager.signup_meal({
            'shiva_support_id': shiva_id,
            'volunteer_name': 'Sarah',
            'volunteer_email': 'sarah@test.com',
            'meal_date': '2026-04-07',
            'meal_type': 'Lunch',
            'meal_description': 'Sandwiches',
            'privacy_consent': 1
        })
        self.assertEqual(r1['status'], 'success')
        r2 = self.manager.signup_meal({
            'shiva_support_id': shiva_id,
            'volunteer_name': 'Rachel',
            'volunteer_email': 'rachel@test.com',
            'meal_date': '2026-04-07',
            'meal_type': 'Dinner',
            'meal_description': 'Pasta',
            'privacy_consent': 1
        })
        self.assertEqual(r2['status'], 'success')


if __name__ == '__main__':
    unittest.main()
