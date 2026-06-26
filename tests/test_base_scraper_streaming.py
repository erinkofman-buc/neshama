#!/usr/bin/env python3
"""
Tests for base_scraper streaming behaviour (Task 3).

base_scraper.run() must upsert each obituary immediately (streaming) rather than
accumulating a full parsed list before storing. This keeps peak memory bounded
to a single record regardless of how many listings a funeral home publishes,
and it must NOT change which/how many records are stored.

Also verifies deterministic session cleanup (self.session.close() in finally).

Network-free: fetch_obituary_listings / parse_obituary are overridden with
synthetic data; no funeral-home HTTP calls, no real database.
"""

import os
import sys
import gc
import tracemalloc
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from base_scraper import BaseScraper

# Each synthetic obituary carries a large, UNIQUE text blob so that retaining
# all N records (the old accumulate-then-store behaviour) shows up clearly in
# tracemalloc, while streaming keeps peak ~ one blob.
BLOB_CHARS = 200_000


class _CloseSpyDB:
    """Minimal fake DB that records only small strings (never the obit dict),
    so tracemalloc reflects the scraper's retention, not the fake's."""
    def __init__(self):
        self.upsert_count = 0
        self.names = []

    def upsert_obituary(self, obit_data):
        self.upsert_count += 1
        self.names.append(obit_data['deceased_name'])  # small string only
        return (f'id-{self.upsert_count}', 'inserted')

    def upsert_comment(self, obit_id, comment):
        return None

    def log_scraper_run(self, **kwargs):
        pass


class _CloseSpySession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _SyntheticScraper(BaseScraper):
    def __init__(self, n):
        super().__init__(source_name='Synthetic Home', city_slug='toronto',
                         base_url='https://example.test')
        self._n = n
        self.db = _CloseSpyDB()
        self.session = _CloseSpySession()

    def fetch_obituary_listings(self):
        return [{'i': i} for i in range(self._n)]

    def parse_obituary(self, raw):
        i = raw['i']
        # Fresh large blob per record (distinct objects, not a shared string).
        blob = (f'record-{i}-' * (BLOB_CHARS // 10))[:BLOB_CHARS]
        return {
            'source': 'Synthetic Home',
            'source_url': f'https://example.test/{i}',
            'condolence_url': f'https://example.test/{i}',
            'deceased_name': f'Person Number {i}',
            'city': 'Toronto',
            'obituary_text': blob,
        }

    def extract_comments(self, url):
        return []


def _peak_bytes_for_run(n):
    """Peak traced bytes for the NEW streaming run()."""
    gc.collect()
    scraper = _SyntheticScraper(n)
    tracemalloc.start()
    scraper.run()
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak, scraper


def _peak_bytes_for_accumulate(n):
    """Peak traced bytes for a faithful reproduction of the OLD behaviour:
    parse ALL records into a list, then store the full list. This is the
    reference point streaming must beat by a wide margin."""
    gc.collect()
    scraper = _SyntheticScraper(n)
    tracemalloc.start()
    raw = scraper.fetch_obituary_listings()
    parsed = []
    for r in raw:
        od = scraper.post_process(scraper.parse_obituary(r))
        if od:
            parsed.append(od)            # full list resident before commit
    scraper.store_results(parsed)
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


class BaseScraperStreamingTest(unittest.TestCase):

    def test_upsert_called_once_per_record_incrementally(self):
        scraper = _SyntheticScraper(25)
        scraper.run()
        self.assertEqual(scraper.db.upsert_count, 25,
                         'upsert_obituary should be called once per record')

    def test_no_records_dropped_or_duplicated(self):
        # Final stored set must be identical to input; same count, same names,
        # same order; i.e. streaming matches accumulate-then-store semantics.
        n = 200
        scraper = _SyntheticScraper(n)
        scraper.run()
        expected = [f'Person Number {i}' for i in range(n)]
        self.assertEqual(scraper.db.names, expected)
        self.assertEqual(len(scraper.db.names), len(set(scraper.db.names)),
                         'no duplicates')

    def test_session_closed_in_finally(self):
        scraper = _SyntheticScraper(5)
        scraper.run()
        self.assertTrue(scraper.session.closed,
                        'self.session.close() must run (finally cleanup)')

    def test_session_closed_even_on_failure(self):
        scraper = _SyntheticScraper(5)

        def boom():
            raise RuntimeError('listing fetch failed')

        scraper.fetch_obituary_listings = boom
        with self.assertRaises(RuntimeError):
            scraper.run()
        self.assertTrue(scraper.session.closed,
                        'session must be closed even when the run raises')

    def test_streaming_peak_far_below_accumulate(self):
        # Compare, at the SAME N and under identical process conditions, the new
        # streaming run() against a faithful reproduction of the old
        # accumulate-then-store path. Streaming holds ~1 record; accumulate holds
        # all N, so the gap is huge and stable (robust to interpreter noise).
        n = 2000
        stream_peak, scraper = _peak_bytes_for_run(n)
        accumulate_peak = _peak_bytes_for_accumulate(n)

        self.assertEqual(scraper.db.upsert_count, n, 'streaming must process all records')

        # Streaming peak must be a small fraction of the accumulate peak.
        self.assertLess(
            stream_peak, accumulate_peak / 10,
            f'streaming not meaningfully lower than accumulate: '
            f'stream={stream_peak} bytes, accumulate={accumulate_peak} bytes')

        # Absolute bound: with N*blob ~= 400MB of data flowing through, a bounded
        # stream must peak at a tiny fraction of the total it processes.
        total_data = n * BLOB_CHARS
        self.assertLess(
            stream_peak, total_data / 20,
            f'streaming peak {stream_peak} bytes too high for {total_data} bytes processed '
            f'- looks accumulated, not streamed')

    def test_streaming_2000_beats_accumulating_100(self):
        # The sharpest noise-robust proof that streaming does NOT scale with N:
        # streaming 2000 records peaks LOWER than merely accumulating 100. That
        # can only hold if streaming retains ~1 record rather than all N.
        stream_large = _peak_bytes_for_run(2000)[0]
        acc_small = _peak_bytes_for_accumulate(100)
        self.assertLess(
            stream_large, acc_small,
            f'streaming N=2000 ({stream_large} bytes) should peak below '
            f'accumulating N=100 ({acc_small} bytes)')

        # And the accumulate reference itself must scale with N (sanity: confirms
        # the blobs are distinct objects and the metric is measuring retention).
        acc_large = _peak_bytes_for_accumulate(2000)
        self.assertGreater(
            acc_large / max(acc_small, 1), 8.0,
            f'accumulate should scale ~20x with N: {acc_small} -> {acc_large}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
