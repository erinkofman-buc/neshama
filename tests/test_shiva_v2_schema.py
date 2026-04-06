"""
Tests for V7 schema migration — Meal Planner Redesign columns.
Verifies that ShivaManager.setup_database() adds all new columns
to shiva_support and meal_signups tables.
"""

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


if __name__ == '__main__':
    unittest.main()
