#!/usr/bin/env python3
"""
Tests for V4 launch hardening: error handling, health check,
rate limiting, friendly errors, and production safety.
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import threading
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from shiva_manager import ShivaManager


# ══════════════════════════════════════════════════════════════
# Helper: spin up a real test server
# ══════════════════════════════════════════════════════════════

def _find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class _ServerTestBase(unittest.TestCase):
    """Spins up a real NeshamaAPIHandler on a random port."""

    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        # Set environment so the server uses our temp DB
        os.environ['DATABASE_PATH'] = cls.db_path
        # Create tables
        cls.mgr = ShivaManager(cls.db_path)
        # Seed an obituaries table for health check
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS obituaries (
                id TEXT PRIMARY KEY,
                deceased_name TEXT,
                city TEXT DEFAULT 'Toronto',
                source TEXT DEFAULT 'test',
                last_updated TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                vendor_type TEXT DEFAULT 'food',
                featured INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                confirmed INTEGER DEFAULT 0,
                subscribed_at TEXT,
                confirmed_at TEXT,
                frequency TEXT DEFAULT 'daily',
                locations TEXT DEFAULT 'toronto'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obituary_id TEXT,
                author_name TEXT,
                message TEXT,
                relationship TEXT,
                created_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obituary_id TEXT,
                text TEXT,
                created_at TEXT
            )
        ''')
        # Insert test data
        cursor.execute("INSERT INTO obituaries (id, deceased_name, city, source, last_updated) VALUES ('obit1', 'Test Person', 'Toronto', 'test', ?)", (datetime.now().isoformat(),))
        cursor.execute("INSERT INTO obituaries (id, deceased_name, city, source, last_updated) VALUES ('obit2', 'Test Person 2', 'Montreal', 'test', ?)", (datetime.now().isoformat(),))
        cursor.execute("INSERT INTO vendors (name, vendor_type, featured) VALUES ('Test Vendor', 'food', 1)")
        conn.commit()
        conn.close()

        # Import and start server
        from api_server import NeshamaAPIHandler, run_server
        cls.port = _find_free_port()
        cls.server = HTTPServer(('127.0.0.1', cls.port), NeshamaAPIHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def _get(self, path):
        """GET request, returns (status_code, parsed_json)."""
        try:
            req = Request(f'{self.base_url}{path}')
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read().decode('utf-8'))
            return resp.status, data
        except HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))
            return e.code, data

    def _post(self, path, body=None):
        """POST request, returns (status_code, parsed_json)."""
        payload = json.dumps(body or {}).encode('utf-8')
        try:
            req = Request(f'{self.base_url}{path}', data=payload,
                          headers={'Content-Type': 'application/json'})
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read().decode('utf-8'))
            return resp.status, data
        except HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))
            return e.code, data


# ══════════════════════════════════════════════════════════════
# Health Check Tests
# ══════════════════════════════════════════════════════════════

class TestHealthCheck(_ServerTestBase):

    def test_health_check_returns_ok(self):
        """GET /api/health returns status ok."""
        status, data = self._get('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'ok')

    def test_health_check_includes_counts(self):
        """Health check includes obituary and vendor counts."""
        status, data = self._get('/api/health')
        self.assertEqual(status, 200)
        self.assertIn('obituaries', data)
        self.assertIn('vendors', data)
        self.assertGreaterEqual(data['obituaries'], 2)
        self.assertGreaterEqual(data['vendors'], 1)


# ══════════════════════════════════════════════════════════════
# Error Handling Tests
# ══════════════════════════════════════════════════════════════

class TestErrorHandling(_ServerTestBase):

    def test_404_for_unknown_endpoint(self):
        """Unknown path returns 404 with JSON error."""
        status, data = self._get('/api/nonexistent')
        self.assertEqual(status, 404)
        self.assertEqual(data['status'], 'error')

    def test_bad_shiva_id_returns_not_found(self):
        """Requesting a non-existent shiva ID returns not_found, not a crash."""
        status, data = self._get('/api/shiva/nonexistent-uuid-12345')
        self.assertIn(status, [200, 404])
        # Should return gracefully (not_found status from manager)
        self.assertIn(data.get('status'), ['not_found', 'error'])

    def test_bad_obituary_id_returns_not_found(self):
        """Requesting a non-existent obituary returns 404."""
        status, data = self._get('/api/obituary/bad-id-999')
        self.assertEqual(status, 404)
        self.assertEqual(data['status'], 'error')

    def test_malformed_json_post(self):
        """POST with malformed JSON returns 400."""
        try:
            req = Request(f'{self.base_url}/api/shiva',
                          data=b'not valid json{{{',
                          headers={'Content-Type': 'application/json'})
            resp = urlopen(req, timeout=5)
            status = resp.status
            data = json.loads(resp.read().decode('utf-8'))
        except HTTPError as e:
            status = e.code
            data = json.loads(e.read().decode('utf-8'))
        self.assertEqual(status, 400)
        self.assertIn('Invalid JSON', data.get('message', data.get('error', {}).get('message', '')))

    def test_create_shiva_missing_fields(self):
        """Create shiva with missing required fields returns 400."""
        status, data = self._post('/api/shiva', {'organizer_name': 'Test'})
        self.assertEqual(status, 400)
        self.assertEqual(data['status'], 'error')

    def test_meal_signup_missing_fields(self):
        """Meal signup with empty body returns error."""
        # First create a shiva page via manager
        now = datetime.now()
        result = self.mgr.create_support({
            'organizer_name': 'Test Org',
            'organizer_email': 'test@example.com',
            'organizer_relationship': 'friend',
            'family_name': 'TestFamily',
            'shiva_address': '456 Test St',
            'shiva_start_date': now.strftime('%Y-%m-%d'),
            'shiva_end_date': (now + timedelta(days=3)).strftime('%Y-%m-%d'),
            'privacy_consent': True,
        })
        shiva_id = result['id']
        status, data = self._post(f'/api/shiva/{shiva_id}/signup', {})
        self.assertEqual(status, 400)

    def test_post_update_no_token(self):
        """Post update without auth token returns 401."""
        status, data = self._post('/api/shiva/some-id/updates', {'message': 'test'})
        self.assertEqual(status, 401)

    def test_send_thank_you_no_token(self):
        """Send thank-you without auth token returns 401."""
        status, data = self._post('/api/shiva/some-id/send-thank-you', {})
        self.assertEqual(status, 401)


# ══════════════════════════════════════════════════════════════
# Rate Limiter Unit Tests
# ══════════════════════════════════════════════════════════════

class TestRateLimiter(unittest.TestCase):

    def test_rate_limiter_allows_within_limit(self):
        """Requests within the limit are allowed."""
        from api_server import _check_rate_limit, _rate_limit_store
        # Use unique key to avoid test interference
        test_ip = f'test-{time.time()}'
        self.assertTrue(_check_rate_limit(test_ip, 'test_endpoint', max_calls=3, window=60))
        self.assertTrue(_check_rate_limit(test_ip, 'test_endpoint', max_calls=3, window=60))
        self.assertTrue(_check_rate_limit(test_ip, 'test_endpoint', max_calls=3, window=60))

    def test_rate_limiter_blocks_over_limit(self):
        """Requests over the limit are blocked."""
        from api_server import _check_rate_limit, _rate_limit_store
        test_ip = f'test-block-{time.time()}'
        for _ in range(3):
            _check_rate_limit(test_ip, 'test_block', max_calls=3, window=60)
        self.assertFalse(_check_rate_limit(test_ip, 'test_block', max_calls=3, window=60))

    def test_rate_limiter_different_endpoints_independent(self):
        """Different endpoints have independent limits."""
        from api_server import _check_rate_limit
        test_ip = f'test-indep-{time.time()}'
        for _ in range(3):
            _check_rate_limit(test_ip, 'endpoint_a', max_calls=3, window=60)
        # endpoint_a is maxed out
        self.assertFalse(_check_rate_limit(test_ip, 'endpoint_a', max_calls=3, window=60))
        # endpoint_b still works
        self.assertTrue(_check_rate_limit(test_ip, 'endpoint_b', max_calls=3, window=60))


# ══════════════════════════════════════════════════════════════
# Friendly Error Message Tests
# ══════════════════════════════════════════════════════════════

class TestFriendlyErrors(unittest.TestCase):

    def test_sqlite_error_is_friendly(self):
        """SQLite errors produce user-friendly messages."""
        from api_server import NeshamaAPIHandler
        handler = MagicMock(spec=NeshamaAPIHandler)
        handler._friendly_error = NeshamaAPIHandler._friendly_error.__get__(handler)
        msg = handler._friendly_error('sqlite3.OperationalError: no such table: foo')
        self.assertNotIn('sqlite3', msg)
        self.assertIn('database error', msg.lower())

    def test_database_locked_is_friendly(self):
        """Database locked errors are user-friendly."""
        from api_server import NeshamaAPIHandler
        handler = MagicMock(spec=NeshamaAPIHandler)
        handler._friendly_error = NeshamaAPIHandler._friendly_error.__get__(handler)
        msg = handler._friendly_error('database is locked')
        self.assertIn('busy', msg.lower())

    def test_long_error_is_truncated(self):
        """Very long error messages are replaced with generic message."""
        from api_server import NeshamaAPIHandler
        handler = MagicMock(spec=NeshamaAPIHandler)
        handler._friendly_error = NeshamaAPIHandler._friendly_error.__get__(handler)
        long_msg = 'x' * 300
        msg = handler._friendly_error(long_msg)
        self.assertLess(len(msg), 100)

    def test_normal_error_passes_through(self):
        """Short non-technical errors pass through unchanged."""
        from api_server import NeshamaAPIHandler
        handler = MagicMock(spec=NeshamaAPIHandler)
        handler._friendly_error = NeshamaAPIHandler._friendly_error.__get__(handler)
        msg = handler._friendly_error('Email not found')
        self.assertEqual(msg, 'Email not found')


# ══════════════════════════════════════════════════════════════
# Production Safety Tests
# ══════════════════════════════════════════════════════════════

class TestProductionSafety(_ServerTestBase):

    def test_admin_endpoints_require_auth(self):
        """Admin endpoints without token return 403."""
        # Admin scrape requires ADMIN_SECRET when set
        with patch.dict(os.environ, {'ADMIN_SECRET': 'test-secret-123'}):
            status, data = self._get('/admin/scrape')
            self.assertEqual(status, 403)

    def test_admin_backup_requires_auth(self):
        """Admin backup without token returns 403."""
        with patch.dict(os.environ, {'ADMIN_SECRET': 'test-secret-123'}):
            status, data = self._get('/admin/backup')
            self.assertEqual(status, 403)

    def test_sitemap_is_served(self):
        """sitemap.xml is accessible."""
        try:
            req = Request(f'{self.base_url}/sitemap.xml')
            resp = urlopen(req, timeout=5)
            content = resp.read().decode('utf-8')
            self.assertEqual(resp.status, 200)
            self.assertIn('neshama.ca', content)
        except HTTPError:
            self.fail('sitemap.xml should be accessible')

    def test_robots_txt_is_served(self):
        """robots.txt is accessible."""
        try:
            req = Request(f'{self.base_url}/robots.txt')
            resp = urlopen(req, timeout=5)
            content = resp.read().decode('utf-8')
            self.assertEqual(resp.status, 200)
            self.assertIn('Sitemap', content)
        except HTTPError:
            self.fail('robots.txt should be accessible')


if __name__ == '__main__':
    unittest.main()
