#!/usr/bin/env python3
"""
Tests for the condolence guestbook feature.

Covers all entry types (condolence, memory, prayer, candle),
type filtering, rate limiting, validation, and backward compatibility.
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from http.server import HTTPServer
import threading
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError

# Create the temp DB BEFORE importing the server, because api_server reads
# DATABASE_PATH at import time to set the module-level DB_PATH constant.
_DB_FD, _DB_PATH = tempfile.mkstemp(suffix='.db')
os.environ['DATABASE_PATH'] = _DB_PATH

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from shiva_manager import ShivaManager


# ======================================================================
# Module-level server setup (shared by all test classes)
# ======================================================================

def _find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def _setup_module_db():
    """Create all tables with guestbook columns and seed test data."""
    mgr = ShivaManager(_DB_PATH)

    conn = sqlite3.connect(_DB_PATH)
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
            created_at TEXT,
            entry_type TEXT DEFAULT 'condolence',
            prayer_text TEXT,
            is_candle INTEGER DEFAULT 0
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

    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT OR IGNORE INTO obituaries (id, deceased_name, city, source, last_updated) "
        "VALUES ('obit-gb-1', 'Ruth Cohen', 'Toronto', 'test', ?)", (now,)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO obituaries (id, deceased_name, city, source, last_updated) "
        "VALUES ('obit-gb-2', 'David Levy', 'Montreal', 'test', ?)", (now,)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO vendors (name, vendor_type, featured) VALUES ('Test Vendor', 'food', 1)"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO subscribers (email, confirmed) VALUES ('test@example.com', 1)"
    )
    conn.commit()
    conn.close()
    return mgr


# Initialize DB, import server, start server -- all at module level
_mgr = _setup_module_db()

from api_server import NeshamaAPIHandler, _rate_limit_store

_PORT = _find_free_port()
_SERVER = HTTPServer(('127.0.0.1', _PORT), NeshamaAPIHandler)
_SERVER_THREAD = threading.Thread(target=_SERVER.serve_forever, daemon=True)
_SERVER_THREAD.start()
_BASE_URL = f'http://127.0.0.1:{_PORT}'


def tearDownModule():
    _SERVER.shutdown()
    os.close(_DB_FD)
    os.unlink(_DB_PATH)


# ======================================================================
# Shared base class
# ======================================================================

class _GuestbookTestBase(unittest.TestCase):
    """Provides HTTP helpers and DB access. All classes share one server."""

    def setUp(self):
        """Clear rate limit store between tests to avoid interference."""
        _rate_limit_store.clear()

    def _get(self, path):
        """GET request, returns (status_code, parsed_json)."""
        try:
            req = Request(f'{_BASE_URL}{path}')
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
            req = Request(f'{_BASE_URL}{path}', data=payload,
                          headers={'Content-Type': 'application/json'})
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read().decode('utf-8'))
            return resp.status, data
        except HTTPError as e:
            data = json.loads(e.read().decode('utf-8'))
            return e.code, data

    def _submit_tribute(self, **overrides):
        """Helper to submit a tribute with sensible defaults."""
        payload = {
            'obituary_id': 'obit-gb-1',
            'author_name': 'Sarah Miller',
            'message': 'She was a wonderful person.',
            'relationship': 'friend',
        }
        payload.update(overrides)
        return self._post('/api/tributes', payload)

    def _read_db_tribute(self, tribute_id):
        """Read a single tribute row directly from the DB for verification."""
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tributes WHERE id = ?', (tribute_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


# ======================================================================
# 1-7: Submission Tests
# ======================================================================

class TestGuestbookSubmission(_GuestbookTestBase):
    """Tests for POST /api/tributes with various entry types."""

    def test_01_submit_condolence_default_type(self):
        """Submit condolence (default type) -- entry_type='condolence' in response."""
        status, data = self._submit_tribute(
            entry_type='condolence',
            message='Baruch Dayan HaEmet. My deepest condolences.',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')
        self.assertIn('id', data)

        # Verify via GET that entry_type is persisted
        get_status, get_data = self._get('/api/tributes/obit-gb-1')
        self.assertEqual(get_status, 200)
        found = [t for t in get_data['data'] if t['id'] == data['id']]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['entry_type'], 'condolence')

    def test_02_submit_memory(self):
        """Submit memory -- verify type stored correctly."""
        status, data = self._submit_tribute(
            entry_type='memory',
            message='I remember her beautiful challah every Shabbat.',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'memory')
        self.assertIn('challah', row['message'])

    def test_03_submit_prayer_with_preset(self):
        """Submit prayer with preset -- verify prayer_text stored."""
        status, data = self._submit_tribute(
            entry_type='prayer',
            prayer_text='El Malei Rachamim',
            message='',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'prayer')
        self.assertEqual(row['prayer_text'], 'El Malei Rachamim')

    def test_04_submit_prayer_with_custom_text(self):
        """Submit prayer with custom text -- verify message stored."""
        status, data = self._submit_tribute(
            entry_type='prayer',
            prayer_text='',
            message='May her neshama have an aliyah.',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'prayer')
        self.assertIn('neshama', row['message'])

    def test_05_submit_candle_with_message(self):
        """Submit candle with message -- verify is_candle=1."""
        status, data = self._submit_tribute(
            entry_type='candle',
            message='Lighting a candle in her memory.',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'candle')
        self.assertEqual(row['is_candle'], 1)
        self.assertIn('candle', row['message'])

    def test_06_submit_candle_without_message(self):
        """Submit candle without message -- empty message is OK."""
        status, data = self._submit_tribute(
            entry_type='candle',
            message='',
        )
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'candle')
        self.assertEqual(row['is_candle'], 1)
        self.assertEqual(row['message'], '')

    def test_07_backward_compat_no_entry_type(self):
        """Old-style POST (no entry_type field) defaults to condolence."""
        payload = {
            'obituary_id': 'obit-gb-1',
            'author_name': 'Old Client',
            'message': 'So sorry for your loss.',
            'relationship': 'neighbor',
        }
        status, data = self._post('/api/tributes', payload)
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')

        row = self._read_db_tribute(data['id'])
        self.assertIsNotNone(row)
        self.assertEqual(row['entry_type'], 'condolence')
        self.assertEqual(row['is_candle'], 0)


# ======================================================================
# 8-9: Retrieval and Filtering Tests
# ======================================================================

class TestGuestbookRetrieval(_GuestbookTestBase):
    """Tests for GET /api/tributes/{obit_id} including type filter."""

    def test_08_get_entries_returns_new_fields(self):
        """GET entries returns entry_type, prayer_text, and is_candle fields."""
        # Insert a prayer entry
        self._submit_tribute(
            entry_type='prayer',
            prayer_text='Kaddish',
            message='',
        )

        status, data = self._get('/api/tributes/obit-gb-1')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')
        self.assertGreater(data['count'], 0)

        entry = data['data'][0]
        self.assertIn('entry_type', entry)
        self.assertIn('prayer_text', entry)
        self.assertIn('is_candle', entry)

    def test_09_filter_by_type_candle(self):
        """Filter by ?type=candle returns only candle entries."""
        # Submit one candle and one condolence to obit-gb-2
        self._submit_tribute(
            obituary_id='obit-gb-2',
            entry_type='candle',
            message='',
        )
        self._submit_tribute(
            obituary_id='obit-gb-2',
            entry_type='condolence',
            message='Thinking of the family.',
        )

        # Filter for candles only
        status, data = self._get('/api/tributes/obit-gb-2?type=candle')
        self.assertEqual(status, 200)
        self.assertGreater(data['count'], 0)
        for entry in data['data']:
            self.assertEqual(entry['entry_type'], 'candle')
            self.assertEqual(entry['is_candle'], 1)


# ======================================================================
# 10: Rate Limiting
# ======================================================================

class TestGuestbookRateLimit(_GuestbookTestBase):
    """Tests for tribute rate limiting (5 per 5 min per IP)."""

    def test_10_rate_limit_blocks_sixth_submission(self):
        """6th submission within 5 minutes gets 429."""
        # First 5 should succeed
        for i in range(5):
            status, data = self._submit_tribute(
                message=f'Rate limit test message #{i+1}',
            )
            self.assertEqual(status, 200, f'Submission {i+1} should succeed, got {status}')

        # 6th should be rate-limited
        status, data = self._submit_tribute(
            message='This should be blocked',
        )
        self.assertEqual(status, 429)
        self.assertEqual(data['status'], 'error')
        self.assertIn('wait', data['message'].lower())


# ======================================================================
# 11-13: Validation Tests
# ======================================================================

class TestGuestbookValidation(_GuestbookTestBase):
    """Tests for input validation on POST /api/tributes."""

    def test_11_missing_required_fields(self):
        """Missing author_name or obituary_id returns 400."""
        # Missing author_name
        status, data = self._post('/api/tributes', {
            'obituary_id': 'obit-gb-1',
            'message': 'Hello',
        })
        self.assertEqual(status, 400)
        self.assertEqual(data['status'], 'error')

        # Missing obituary_id
        status, data = self._post('/api/tributes', {
            'author_name': 'Test',
            'message': 'Hello',
        })
        self.assertEqual(status, 400)
        self.assertEqual(data['status'], 'error')

    def test_12_invalid_entry_type(self):
        """Invalid entry_type returns 400."""
        status, data = self._submit_tribute(
            entry_type='invalid_type',
        )
        self.assertEqual(status, 400)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Invalid entry type', data['message'])

    def test_13_prayer_with_neither_text_nor_message(self):
        """Prayer with neither prayer_text nor message returns 400."""
        status, data = self._post('/api/tributes', {
            'obituary_id': 'obit-gb-1',
            'author_name': 'Test Person',
            'entry_type': 'prayer',
            'prayer_text': '',
            'message': '',
            'relationship': 'friend',
        })
        self.assertEqual(status, 400)
        self.assertEqual(data['status'], 'error')
        self.assertIn('prayer', data['message'].lower())


# ======================================================================
# 14: Backward Compatibility -- Community Stats
# ======================================================================

class TestGuestbookCommunityStats(_GuestbookTestBase):
    """Tests that community stats still works with the new schema."""

    def test_14_community_stats_backward_compat(self):
        """GET /api/community-stats returns valid data including tributes."""
        # Add a tribute so count is at least 1
        self._submit_tribute(message='Stats compat test')

        status, data = self._get('/api/community-stats')
        self.assertEqual(status, 200)
        self.assertEqual(data['status'], 'success')
        self.assertIn('data', data)
        stats = data['data']
        self.assertIn('souls_remembered', stats)
        self.assertIn('tributes_left', stats)
        self.assertIn('community_members', stats)
        self.assertGreaterEqual(stats['souls_remembered'], 1)
        self.assertGreaterEqual(stats['tributes_left'], 1)
        self.assertIsInstance(stats['community_members'], int)


# ======================================================================
# 15-22: PDF Keepsake Tests
# ======================================================================

class TestKeepsakePDF(_GuestbookTestBase):
    """Tests for the PDF keepsake export feature."""

    def _get_pdf(self, path):
        """GET request expecting PDF bytes, returns (status_code, bytes)."""
        try:
            req = Request(f'{_BASE_URL}{path}')
            resp = urlopen(req, timeout=10)
            return resp.status, resp.read()
        except HTTPError as e:
            return e.code, e.read()

    def test_15_keepsake_returns_pdf(self):
        """GET /api/tributes/{id}/keepsake.pdf returns valid PDF."""
        # Ensure at least one entry exists
        self._submit_tribute(
            obituary_id='obit-gb-1',
            message='Keepsake test entry',
            entry_type='memory',
        )
        status, body = self._get_pdf('/api/tributes/obit-gb-1/keepsake.pdf')
        self.assertEqual(status, 200)
        self.assertTrue(body[:5] == b'%PDF-', 'Response should be a valid PDF')
        self.assertGreater(len(body), 1000, 'PDF should have substantial content')

    def test_16_keepsake_empty_guestbook(self):
        """Keepsake PDF works with zero guestbook entries."""
        status, body = self._get_pdf('/api/tributes/obit-gb-2/keepsake.pdf')
        self.assertEqual(status, 200)
        self.assertTrue(body[:5] == b'%PDF-', 'Should return a valid PDF even with no entries')

    def test_17_keepsake_nonexistent_obituary(self):
        """Keepsake for non-existent obituary returns 404."""
        status, body = self._get_pdf('/api/tributes/nonexistent-obit/keepsake.pdf')
        self.assertEqual(status, 404)

    def test_18_keepsake_all_entry_types(self):
        """PDF generates correctly with all 4 entry types present."""
        obit = 'obit-gb-1'
        self._submit_tribute(obituary_id=obit, message='A fond memory', entry_type='memory')
        self._submit_tribute(obituary_id=obit, message='Deepest condolences', entry_type='condolence')
        self._submit_tribute(obituary_id=obit, entry_type='prayer', prayer_text='May their memory be a blessing')
        self._submit_tribute(obituary_id=obit, entry_type='candle')

        status, body = self._get_pdf(f'/api/tributes/{obit}/keepsake.pdf')
        self.assertEqual(status, 200)
        self.assertTrue(body[:5] == b'%PDF-')
        # PDF with 4+ entries should be larger
        self.assertGreater(len(body), 2000)

    def test_19_keepsake_content_disposition(self):
        """Response includes Content-Disposition header for download."""
        req = Request(f'{_BASE_URL}/api/tributes/obit-gb-1/keepsake.pdf')
        resp = urlopen(req, timeout=10)
        cd = resp.headers.get('Content-Disposition', '')
        self.assertIn('attachment', cd)
        self.assertIn('.pdf', cd)
        resp.read()  # consume body

    def test_20_keepsake_content_type(self):
        """Response has correct Content-Type header."""
        req = Request(f'{_BASE_URL}/api/tributes/obit-gb-1/keepsake.pdf')
        resp = urlopen(req, timeout=10)
        ct = resp.headers.get('Content-Type', '')
        self.assertIn('application/pdf', ct)
        resp.read()


class TestKeepsakePDFUnit(unittest.TestCase):
    """Unit tests for the PDF generator module directly (no server needed)."""

    def test_21_generate_empty_entries(self):
        """generate_keepsake_pdf works with empty entries list."""
        from pdf_keepsake import generate_keepsake_pdf
        obit = {'deceased_name': 'Test Person', 'date_of_death': '2026-01-15'}
        pdf = generate_keepsake_pdf(obit, [])
        self.assertTrue(pdf[:5] == b'%PDF-')
        self.assertGreater(len(pdf), 500)

    def test_22_generate_special_characters(self):
        """PDF handles special characters in names and messages."""
        from pdf_keepsake import generate_keepsake_pdf
        obit = {'deceased_name': 'Sarah O\'Brien-Levy', 'hebrew_name': 'Test'}
        entries = [{
            'author_name': 'Jean-Pierre & Marie',
            'message': 'Fond memories <3 of "the best" neighbor & friend.',
            'entry_type': 'memory',
            'created_at': '2026-02-20T10:00:00',
            'relationship': 'Neighbor',
        }]
        pdf = generate_keepsake_pdf(obit, entries)
        self.assertTrue(pdf[:5] == b'%PDF-')


if __name__ == '__main__':
    unittest.main()
