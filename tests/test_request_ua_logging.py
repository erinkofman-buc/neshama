#!/usr/bin/env python3
"""
Test that the request log line (_log_request) includes the User-Agent.

Purpose: identify automated probes (e.g. the HEAD uptime checks that were
501ing) from the logs on the next live cycle.

Network-free: only talks to a local NeshamaAPIHandler on a loopback port, and
captures the emitted log records via a handler on the root logger.
"""

import os
import sys
import logging
import sqlite3
import tempfile
import threading
import unittest
import http.client
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

DISTINCTIVE_UA = 'NeshamaProbeTest/9.9 (uptime-checker)'


def _free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class _ListHandler(logging.Handler):
    """Captures formatted log messages into a thread-safe list."""
    def __init__(self):
        super().__init__()
        self.lines = []
        self._lock = threading.Lock()

    def emit(self, record):
        with self._lock:
            self.lines.append(record.getMessage())


class RequestUALoggingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_fd, cls.db_path = tempfile.mkstemp(suffix='.db')
        os.environ['DATABASE_PATH'] = cls.db_path
        # Minimal table so the server boots cleanly.
        conn = sqlite3.connect(cls.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS vendors "
                     "(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT, website TEXT, instagram TEXT)")
        conn.commit()
        conn.close()

        cls.log_handler = _ListHandler()
        logging.getLogger().addHandler(cls.log_handler)
        logging.getLogger().setLevel(logging.INFO)

        import api_server
        from api_server import NeshamaAPIHandler
        # Pin DB path to our temp DB (DB_PATH is resolved once at import; this
        # keeps a full-suite run from falling back to the real neshama.db).
        api_server.DB_PATH = cls.db_path
        cls.port = _free_port()
        cls.server = ThreadingHTTPServer(('127.0.0.1', cls.port), NeshamaAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        logging.getLogger().removeHandler(cls.log_handler)
        os.close(cls.db_fd)
        os.unlink(cls.db_path)

    def _head(self, path, ua):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            conn.request('HEAD', path, headers={'User-Agent': ua})
            resp = conn.getresponse()
            resp.read()
            return resp.status
        finally:
            conn.close()

    def test_head_request_logs_user_agent(self):
        before = len(self.log_handler.lines)
        status = self._head('/feed', DISTINCTIVE_UA)
        self.assertEqual(status, 200)

        new_lines = self.log_handler.lines[before:]
        api_lines = [ln for ln in new_lines if ln.startswith('[API] HEAD /feed')]
        self.assertTrue(api_lines, f'no [API] HEAD log line captured; got: {new_lines[-5:]}')

        ua_line = next((ln for ln in api_lines if f'UA="{DISTINCTIVE_UA}"' in ln), None)
        self.assertIsNotNone(
            ua_line,
            f'User-Agent not found in request log line. HEAD lines: {api_lines}')
        # Sanity: the line is the method/path/status/timing format, not a header dump.
        self.assertIn('200', ua_line)
        self.assertIn('ms UA=', ua_line)

    def test_missing_user_agent_logs_dash(self):
        # No UA header -> the log line should still render with a '-' placeholder.
        before = len(self.log_handler.lines)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            # http.client adds a Host header but no User-Agent by default.
            conn.putrequest('HEAD', '/help', skip_accept_encoding=True)
            conn.endheaders()
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 200)
        finally:
            conn.close()

        new_lines = self.log_handler.lines[before:]
        head_lines = [ln for ln in new_lines if ln.startswith('[API] HEAD /help')]
        self.assertTrue(head_lines, f'no HEAD /help log line; got {new_lines[-5:]}')
        self.assertTrue(any('UA="-"' in ln for ln in head_lines),
                        f'expected UA="-" placeholder, got {head_lines}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
