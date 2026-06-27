#!/usr/bin/env python3
"""
PART A quick-win indexing fixes (branch fix/ssr-indexing):
  1. Vendor pages emit a per-vendor self-canonical (not the hardcoded
     /directory/vendor placeholder).
  2. Unknown vendor slugs return 404, not a 200 shell (soft-404 fix).
  3. date_of_death guard: internal newlines/whitespace are collapsed at the
     upsert chokepoint so a stray newline can't produce a malformed URL.

Network-free: local NeshamaAPIHandler on a loopback port + direct DB calls.
"""

import os
import sys
import sqlite3
import tempfile
import threading
import unittest
import http.client
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class VendorCanonicalAnd404Test(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_PATH'] = cls.db_path
        conn = sqlite3.connect(cls.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS vendors "
                     "(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, name TEXT, website TEXT, instagram TEXT)")
        conn.execute("INSERT INTO vendors (slug, name) VALUES ('cumbraes', 'Cumbrae''s')")
        conn.commit()
        conn.close()

        import api_server
        from api_server import NeshamaAPIHandler
        api_server.DB_PATH = cls.db_path  # pin away from the real DB
        cls.port = _free_port()
        cls.server = ThreadingHTTPServer(('127.0.0.1', cls.port), NeshamaAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def _get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            conn.request('GET', path)
            r = conn.getresponse()
            body = r.read().decode('utf-8', 'ignore')
            return r.status, body
        finally:
            conn.close()

    def test_known_vendor_emits_self_canonical(self):
        status, body = self._get('/directory/cumbraes')
        self.assertEqual(status, 200)
        self.assertIn('<link rel="canonical" href="https://neshama.ca/directory/cumbraes">', body)
        self.assertNotIn('href="https://neshama.ca/directory/vendor"', body,
                         'hardcoded /directory/vendor canonical must be gone')
        # og:url should match too
        self.assertIn('content="https://neshama.ca/directory/cumbraes"', body)

    def test_known_vendor_canonical_ignores_query_params(self):
        status, body = self._get('/directory/cumbraes?from=shiva-caterers-toronto&utm_source=x')
        self.assertEqual(status, 200)
        self.assertIn('<link rel="canonical" href="https://neshama.ca/directory/cumbraes">', body,
                      'param variants must self-canonical to the clean vendor URL')

    def test_unknown_slug_returns_404(self):
        status, _ = self._get('/directory/pizza-pita')   # not in vendors table
        self.assertEqual(status, 404, 'removed/unknown vendor slug must 404, not serve a 200 shell')


class DateOfDeathGuardTest(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_PATH'] = self.db_path
        from database_setup import NeshamaDatabase
        self.db = NeshamaDatabase(self.db_path)
        self.db.create_tables()  # create schema

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _row_dod(self, obit_id):
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute('SELECT date_of_death FROM obituaries WHERE id = ?', (obit_id,))
            r = cur.fetchone()
            return r[0] if r else None
        finally:
            conn.close()

    def test_newline_in_date_is_stripped_on_store(self):
        obit = {
            'source': 'Test Home',
            'source_url': 'https://example.test/1',
            'condolence_url': 'https://example.test/1',
            'deceased_name': 'Laura Schertzer',
            'date_of_death': 'May 1, \n2026',   # the malformed value
            'city': 'Toronto',
        }
        obit_id, action = self.db.upsert_obituary(obit)
        stored = self._row_dod(obit_id)
        self.assertEqual(stored, 'May 1, 2026', f'newline must be collapsed; got {stored!r}')
        self.assertNotIn('\n', stored)
        self.assertNotIn('\r', stored)
        # A yahrzeit URL built from this value is now well-formed (no raw newline)
        self.assertNotIn('\n', f"/yahrzeit?date_of_death={stored}")

    def test_normal_date_unchanged(self):
        obit = {
            'source': 'Test Home', 'source_url': 'https://example.test/2',
            'condolence_url': 'https://example.test/2', 'deceased_name': 'Normal Person',
            'date_of_death': 'Monday, June 17, 2026', 'city': 'Toronto',
        }
        obit_id, _ = self.db.upsert_obituary(obit)
        self.assertEqual(self._row_dod(obit_id), 'Monday, June 17, 2026')


if __name__ == '__main__':
    unittest.main(verbosity=2)
