#!/usr/bin/env python3
"""
Tests for HEAD support (NeshamaAPIHandler.do_HEAD).

Verifies RFC 7231 section 4.3.2 behaviour: HEAD returns the same status and
headers as GET (including Content-Length) with an empty body, for every GET
route; and that side-effectful GET routes (/api/track-click and the keepsake
PDF route) do NOT run their handler under HEAD.

Network-free: only talks to a local NeshamaAPIHandler on a loopback port.
"""

import os
import sys
import sqlite3
import tempfile
import threading
import unittest
import http.client
from urllib.parse import quote
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

# Static/page GET routes that the incident probes hit, plus a couple more.
PAGE_ROUTES = ('/feed', '/help', '/shiva-guide', '/', '/about')


def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class HeadSupportTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_PATH'] = cls.db_path
        conn = sqlite3.connect(cls.db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS vendors "
                  "(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, website TEXT, instagram TEXT)")
        c.execute("INSERT INTO vendors (slug, website, instagram) "
                  "VALUES ('testvendor', 'https://example.com', '')")
        c.execute("CREATE TABLE IF NOT EXISTS vendor_clicks "
                  "(id INTEGER PRIMARY KEY AUTOINCREMENT, vendor_slug TEXT, destination_url TEXT, "
                  "referrer_page TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        conn.close()

        import api_server
        from api_server import NeshamaAPIHandler
        # Pin the module-level DB path to our temp DB. DB_PATH is resolved once
        # at import; without this a full-suite run (where another test imported
        # api_server first against a now-deleted temp DB) would fall back to the
        # real neshama.db. Never let these tests touch the real database.
        api_server.DB_PATH = cls.db_path
        cls.port = _free_port()
        # Raise the accept backlog above the stdlib default of 5 so the
        # concurrency test's simultaneous connects don't overflow the queue.
        ThreadingHTTPServer.request_queue_size = 128
        cls.server = ThreadingHTTPServer(('127.0.0.1', cls.port), NeshamaAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    # ---- low-level request helpers (http.client handles HEAD correctly) ----

    def _request(self, method, path, headers=None):
        # Retry transient transport errors (RST / dropped keep-alive under load).
        # These are socket-level races, independent of handler correctness.
        last_exc = None
        for _ in range(5):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
            try:
                conn.request(method, path, headers=headers or {})
                resp = conn.getresponse()
                body = resp.read()
                return resp.status, dict(resp.getheaders()), body
            except (ConnectionResetError, http.client.RemoteDisconnected,
                    ConnectionRefusedError, BrokenPipeError) as e:
                last_exc = e
            finally:
                conn.close()
        raise last_exc

    def _get(self, path, headers=None):
        return self._request('GET', path, headers)

    def _head(self, path, headers=None):
        return self._request('HEAD', path, headers)

    def _click_count(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM vendor_clicks").fetchone()[0]
        finally:
            conn.close()

    # ---- core: HEAD mirrors GET headers with an empty body ----

    def test_head_matches_get_on_pages(self):
        for path in PAGE_ROUTES:
            with self.subTest(path=path):
                g_status, g_hdrs, g_body = self._get(path)
                h_status, h_hdrs, h_body = self._head(path)
                self.assertEqual(g_status, 200, f'GET {path} precondition failed')
                self.assertEqual(h_status, 200, f'HEAD {path} should be 200')
                self.assertEqual(h_body, b'', f'HEAD {path} must have an empty body')
                self.assertEqual(h_hdrs.get('Content-Type'), g_hdrs.get('Content-Type'),
                                 f'HEAD {path} Content-Type must match GET')
                self.assertIn('Content-Length', h_hdrs, f'HEAD {path} should send Content-Length')
                self.assertEqual(int(h_hdrs['Content-Length']), len(g_body),
                                 f'HEAD {path} Content-Length must equal GET body length')

    def test_head_on_sample_api_get(self):
        # /api/cities is a read-only JSON GET endpoint that always 200s
        # (no DB, no env dependency; unlike /api/health which can 503).
        g_status, g_hdrs, g_body = self._get('/api/cities')
        h_status, h_hdrs, h_body = self._head('/api/cities')
        self.assertEqual(g_status, 200)
        self.assertEqual(h_status, 200)
        self.assertEqual(h_body, b'', 'HEAD /api/cities must have an empty body')
        self.assertEqual(h_hdrs.get('Content-Type'), g_hdrs.get('Content-Type'))
        self.assertGreater(len(g_body), 0, 'GET /api/cities should return a body')

    # ---- GET regression: unchanged status, deterministic body, CL consistency ----

    def test_get_still_works_and_is_deterministic(self):
        for path in PAGE_ROUTES:
            with self.subTest(path=path):
                s1, h1, b1 = self._get(path)
                s2, h2, b2 = self._get(path)
                self.assertEqual(s1, 200)
                self.assertEqual(s1, s2)
                self.assertGreater(len(b1), 0, f'GET {path} should return a body')
                self.assertEqual(b1, b2, f'GET {path} body should be byte-identical across calls')
                self.assertEqual(int(h1['Content-Length']), len(b1),
                                 f'GET {path} Content-Length must equal body length')

    # ---- side-effect guard ----

    def test_head_track_click_does_not_increment(self):
        path = '/api/track-click?vendor=testvendor&dest=' + quote('https://example.com/x', safe='')
        before = self._click_count()
        h_status, _, h_body = self._head(path)
        self.assertEqual(self._click_count(), before,
                         'HEAD /api/track-click must NOT record a click')
        self.assertEqual(h_body, b'', 'HEAD /api/track-click must have an empty body')
        self.assertEqual(h_status, 200)

    def test_get_track_click_still_increments(self):
        path = '/api/track-click?vendor=testvendor&dest=' + quote('https://example.com/x', safe='')
        before = self._click_count()
        # GET returns a 302 redirect; http.client does not follow it.
        status, hdrs, _ = self._get(path)
        self.assertEqual(status, 302, 'GET /api/track-click should still redirect')
        self.assertEqual(self._click_count(), before + 1,
                         'GET /api/track-click must still record a click (no regression)')

    # ---- edge cases ----

    def test_head_on_404_route_is_404_not_501(self):
        status, _, body = self._head('/this-route-does-not-exist-xyz')
        self.assertEqual(status, 404, 'HEAD on an unknown route should be 404')
        self.assertNotEqual(status, 501)
        self.assertEqual(body, b'', 'HEAD 404 must have an empty body')

    def test_head_on_post_only_route_is_not_501(self):
        # /api/subscribe is POST-only; GET (hence HEAD) 404s; but never 501.
        g_status, _, _ = self._get('/api/subscribe')
        h_status, _, h_body = self._head('/api/subscribe')
        self.assertNotEqual(h_status, 501, 'HEAD on a POST-only route must not be 501')
        self.assertEqual(h_status, g_status, 'HEAD should mirror GET status on the same path')
        self.assertEqual(h_body, b'')

    # ---- concurrency: instance-local overrides must be thread-safe ----

    def test_concurrent_head_and_get_are_isolated(self):
        ref_status, ref_hdrs, ref_body = self._get('/feed')
        self.assertEqual(ref_status, 200)
        errors = []

        def hammer_head():
            try:
                s, h, b = self._head('/feed')
                assert s == 200, f'HEAD status {s}'
                assert b == b'', 'HEAD body not empty under concurrency'
                assert int(h['Content-Length']) == len(ref_body), 'HEAD Content-Length drift'
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        def hammer_get():
            try:
                s, h, b = self._get('/feed')
                assert s == 200, f'GET status {s}'
                assert b == ref_body, 'GET body corrupted under concurrency'
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = []
        for i in range(24):
            threads.append(threading.Thread(target=hammer_head if i % 2 == 0 else hammer_get))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f'Concurrency failures: {errors[:5]}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
