#!/usr/bin/env python3
"""
Tests for the SQLite backup writer (ShivaManager.backup_to_file), its restore
path, and the freshness check in the Mac off-box pull script.

Why these exist:

  Production OOM-restarted on 2026-09-20. The old backup_to_file loaded every
  BACKUP_TABLES row into Python dicts and json.dump'd them (~330 MB peak on a
  512 MB instance), from a new unlocked thread on every write. /data/backup.json
  then sat at 2026-09-18 for four days, and the Mac pull kept logging OK on the
  stale copy because it only checked that the file parsed.

Run:  python3 -m pytest tests/test_backup_sqlite.py -v
"""

import gzip
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'frontend'))

import shiva_manager
from shiva_manager import ShivaManager

PULL_SCRIPT = os.path.join(REPO_ROOT, 'tools', 'neshama-backup-pull.sh')


def make_manager(dirpath, seed=True):
    """A ShivaManager on a fresh WAL-mode DB in dirpath, like production."""
    db_path = os.path.join(dirpath, 'neshama.db')
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE IF NOT EXISTS obituaries (id TEXT PRIMARY KEY, deceased_name TEXT, source TEXT)')
    conn.commit()
    conn.close()
    mgr = ShivaManager(db_path=db_path)
    if seed:
        seed_rows(db_path)
    return mgr


def seed_rows(db_path, shiva_id='shiva-1', family='Cohen'):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        'INSERT INTO shiva_support (id, organizer_name, organizer_email, organizer_relationship, '
        'family_name, shiva_start_date, shiva_end_date, magic_token, privacy_consent, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (shiva_id, 'Organizer', 'org@example.com', 'child', family,
         '2026-09-20', '2026-09-27', 'tok-' + shiva_id, 1, now)
    )
    for i in range(3):
        conn.execute(
            'INSERT INTO meal_signups (shiva_support_id, volunteer_name, volunteer_email, '
            'meal_date, meal_type, privacy_consent, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (shiva_id, f'Vol {i}', f'v{i}@example.com', '2026-09-21', 'dinner', 1, now)
        )
    for i in range(5):
        conn.execute('INSERT OR IGNORE INTO obituaries (id, deceased_name, source) VALUES (?, ?, ?)',
                     (f'{shiva_id}-obit-{i}', f'Person {i}', 'Steeles'))
    conn.commit()
    conn.close()


def open_backup(gz_path, dirpath):
    """Decompress backup.db.gz into dirpath and return a connection to it."""
    out = os.path.join(dirpath, 'opened.db')
    with gzip.open(gz_path, 'rb') as fin, open(out, 'wb') as fout:
        shutil.copyfileobj(fin, fout)
    return sqlite3.connect(out)


class BackupWriterTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mgr = make_manager(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_backup_is_valid_gz_sqlite_with_meta_and_matching_counts(self):
        result = self.mgr.backup_to_file()
        self.assertIsNotNone(result)
        gz_path = os.path.join(self.tmp, 'backup.db.gz')
        self.assertEqual(result['path'], gz_path)
        self.assertTrue(os.path.exists(gz_path))
        self.assertEqual(result['bytes'], os.path.getsize(gz_path))

        bk = open_backup(gz_path, self.tmp)
        self.assertEqual(bk.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        # Self-contained: no WAL left behind in the copy
        self.assertEqual(bk.execute('PRAGMA journal_mode').fetchone()[0], 'delete')
        meta = dict(bk.execute('SELECT key, value FROM _backup_meta').fetchall())
        bk.close()

        exported = datetime.fromisoformat(meta['exported_at'])
        self.assertIsNotNone(exported.tzinfo, 'exported_at must carry a UTC offset')
        self.assertLess(abs((datetime.now(timezone.utc) - exported).total_seconds()), 60)
        self.assertEqual(meta['exported_at'], result['exported_at'])

        src = sqlite3.connect(self.mgr.db_path)
        for table in ('shiva_support', 'meal_signups', 'obituaries', 'email_log'):
            n = src.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            self.assertEqual(int(meta[f'rows.{table}']), n, table)
        src.close()
        self.assertEqual(meta['rows.meal_signups'], '3')
        self.assertEqual(meta['rows.obituaries'], '5')

    def test_no_temp_files_left_and_legacy_json_untouched(self):
        legacy = os.path.join(self.tmp, 'backup.json')
        with open(legacy, 'w') as f:
            f.write('{"legacy": true}')
        self.mgr.backup_to_file()
        leftovers = sorted(f for f in os.listdir(self.tmp) if f.startswith('backup'))
        self.assertEqual(leftovers, ['backup.db.gz', 'backup.json'])
        with open(legacy) as f:
            self.assertEqual(f.read(), '{"legacy": true}')

    def test_stale_temp_files_from_killed_run_are_cleared(self):
        for name in ('backup.db.tmp', 'backup.db.tmp-journal', 'backup.db.gz.tmp'):
            with open(os.path.join(self.tmp, name), 'w') as f:
                f.write('garbage from a killed run')
        self.assertIsNotNone(self.mgr.backup_to_file())
        self.assertEqual(sorted(f for f in os.listdir(self.tmp) if f.startswith('backup')),
                         ['backup.db.gz'])

    def test_second_backup_replaces_first(self):
        self.mgr.backup_to_file()
        seed_rows(self.mgr.db_path, shiva_id='shiva-2', family='Levi')
        self.mgr.backup_to_file()
        bk = open_backup(os.path.join(self.tmp, 'backup.db.gz'), self.tmp)
        self.assertEqual(bk.execute('SELECT COUNT(*) FROM shiva_support').fetchone()[0], 2)
        bk.close()

    def test_backup_error_is_logged_not_raised(self):
        with patch.object(ShivaManager, '_write_db_backup', side_effect=OSError('disk full')):
            self.assertIsNone(self.mgr.backup_to_file())

    def test_backup_completes_while_writes_continue(self):
        """A held read snapshot means concurrent writes never restart or break the copy."""
        stop = threading.Event()
        errors = []

        def writer():
            conn = sqlite3.connect(self.mgr.db_path, timeout=30)
            i = 0
            while not stop.is_set():
                try:
                    conn.execute('INSERT INTO obituaries (id, deceased_name, source) VALUES (?, ?, ?)',
                                 (f'w-{i}', 'Writer', 'Test'))
                    conn.commit()
                except Exception as e:
                    errors.append(e)
                i += 1
            conn.close()

        t = threading.Thread(target=writer)
        t.start()
        try:
            with patch.object(ShivaManager, 'BACKUP_PAGES_PER_STEP', 1):
                result = self.mgr.backup_to_file()
        finally:
            stop.set()
            t.join()
        self.assertIsNotNone(result)
        self.assertEqual(errors, [])
        bk = open_backup(result['path'], self.tmp)
        self.assertEqual(bk.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        meta_rows = int(bk.execute("SELECT value FROM _backup_meta WHERE key='rows.obituaries'").fetchone()[0])
        self.assertEqual(bk.execute('SELECT COUNT(*) FROM obituaries').fetchone()[0], meta_rows)
        bk.close()


class BackupConcurrencyTests(unittest.TestCase):
    """Never two backups at once; triggers during a run coalesce into one more pass."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mgr = make_manager(self.tmp, seed=False)
        self.active = 0
        self.max_active = 0
        self.runs = 0
        self.counter_lock = threading.Lock()
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        self._wait_idle()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _slow_write(self, mgr_self):
        with self.counter_lock:
            self.active += 1
            self.runs += 1
            self.max_active = max(self.max_active, self.active)
        self.release.wait(5)
        with self.counter_lock:
            self.active -= 1
        return {}

    def _state(self):
        return shiva_manager._BACKUP_STATE.get(os.path.abspath(self.mgr.db_path), {})

    def _wait_idle(self, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with shiva_manager._BACKUP_STATE_LOCK:
                if not self._state().get('running'):
                    return True
            time.sleep(0.01)
        return False

    def _wait_runs(self, n, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline and self.runs < n:
            time.sleep(0.01)

    def test_burst_of_triggers_runs_once_plus_one_coalesced_pass(self):
        with patch.object(ShivaManager, '_write_db_backup', autospec=True, side_effect=self._slow_write):
            self.mgr._trigger_backup()
            self._wait_runs(1)
            self.assertEqual(self.runs, 1)
            # 25 writes land while the first backup is still copying
            threads = [threading.Thread(target=self.mgr._trigger_backup) for _ in range(25)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertTrue(self._state()['dirty'])
            self.release.set()
            self.assertTrue(self._wait_idle())
        self.assertEqual(self.runs, 2)
        self.assertEqual(self.max_active, 1)

    def test_single_trigger_runs_once(self):
        self.release.set()
        with patch.object(ShivaManager, '_write_db_backup', autospec=True, side_effect=self._slow_write):
            self.mgr._trigger_backup()
            self.assertTrue(self._wait_idle())
        self.assertEqual(self.runs, 1)

    def test_scheduled_call_waits_for_triggered_backup(self):
        """backup_to_file (the daily job) and the trigger worker never overlap."""
        with patch.object(ShivaManager, '_write_db_backup', autospec=True, side_effect=self._slow_write):
            self.mgr._trigger_backup()
            self._wait_runs(1)
            direct = [threading.Thread(target=self.mgr.backup_to_file) for _ in range(3)]
            for t in direct:
                t.start()
            time.sleep(0.1)
            self.assertEqual(self.max_active, 1)
            self.release.set()
            for t in direct:
                t.join()
            self.assertTrue(self._wait_idle())
        self.assertEqual(self.runs, 4)
        self.assertEqual(self.max_active, 1)

    def test_real_triggers_produce_a_valid_backup(self):
        seed_rows(self.mgr.db_path)
        for _ in range(10):
            self.mgr._trigger_backup()
        self.assertTrue(self._wait_idle())
        bk = open_backup(os.path.join(self.tmp, 'backup.db.gz'), self.tmp)
        self.assertEqual(bk.execute('SELECT COUNT(*) FROM shiva_support').fetchone()[0], 1)
        bk.close()


class RestoreTests(unittest.TestCase):

    def setUp(self):
        self.src_dir = tempfile.mkdtemp()
        self.dst_dir = tempfile.mkdtemp()
        self.src = make_manager(self.src_dir)
        self.dst = make_manager(self.dst_dir, seed=False)

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
        shutil.rmtree(self.dst_dir, ignore_errors=True)

    def _count(self, mgr, table):
        conn = sqlite3.connect(mgr.db_path)
        n = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        conn.close()
        return n

    def test_needs_restore_false_without_any_backup(self):
        self.assertFalse(self.dst.needs_restore())
        self.assertEqual(self.dst.restore_from_file(), 0)

    def test_restore_from_db_gz_into_empty_db(self):
        self.src.backup_to_file()
        shutil.copy(os.path.join(self.src_dir, 'backup.db.gz'), self.dst_dir)
        self.assertTrue(self.dst.needs_restore())

        restored = self.dst.restore_from_file()
        self.assertEqual(restored, 1 + 3 + 5)
        self.assertEqual(self._count(self.dst, 'shiva_support'), 1)
        self.assertEqual(self._count(self.dst, 'meal_signups'), 3)
        self.assertEqual(self._count(self.dst, 'obituaries'), 5)
        self.assertFalse(self.dst.needs_restore())
        # Temp decompressed copy cleaned up, backup itself kept
        self.assertEqual(sorted(f for f in os.listdir(self.dst_dir) if f.startswith('backup')),
                         ['backup.db.gz'])

    def test_restore_is_insert_or_ignore(self):
        self.src.backup_to_file()
        shutil.copy(os.path.join(self.src_dir, 'backup.db.gz'), self.dst_dir)
        self.dst.restore_from_file()
        self.assertEqual(self.dst.restore_from_file(), 0)
        self.assertEqual(self._count(self.dst, 'meal_signups'), 3)

    def test_restore_tolerates_column_drift(self):
        """A backup with an extra column restores into a DB that lacks it."""
        conn = sqlite3.connect(self.src.db_path)
        conn.execute('ALTER TABLE obituaries ADD COLUMN only_in_backup TEXT')
        conn.commit()
        conn.close()
        self.src.backup_to_file()
        shutil.copy(os.path.join(self.src_dir, 'backup.db.gz'), self.dst_dir)
        self.dst.restore_from_file()
        self.assertEqual(self._count(self.dst, 'obituaries'), 5)

    def test_fallback_to_legacy_json(self):
        data = self.src.get_backup_data()
        with open(os.path.join(self.dst_dir, 'backup.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f)
        self.assertTrue(self.dst.needs_restore())
        self.assertGreater(self.dst.restore_from_file(), 0)
        self.assertEqual(self._count(self.dst, 'shiva_support'), 1)
        self.assertEqual(self._count(self.dst, 'meal_signups'), 3)

    def test_db_gz_preferred_over_legacy_json(self):
        # Legacy JSON holds a different, older shiva; the .db.gz must win
        other_dir = tempfile.mkdtemp()
        try:
            other = make_manager(other_dir, seed=False)
            seed_rows(other.db_path, shiva_id='old-json-shiva', family='Stale')
            with open(os.path.join(self.dst_dir, 'backup.json'), 'w', encoding='utf-8') as f:
                json.dump(other.get_backup_data(), f)
        finally:
            shutil.rmtree(other_dir, ignore_errors=True)
        self.src.backup_to_file()
        shutil.copy(os.path.join(self.src_dir, 'backup.db.gz'), self.dst_dir)

        self.dst.restore_from_file()
        conn = sqlite3.connect(self.dst.db_path)
        ids = [r[0] for r in conn.execute('SELECT id FROM shiva_support')]
        conn.close()
        self.assertEqual(ids, ['shiva-1'])

    def test_needs_restore_false_when_db_has_data(self):
        self.src.backup_to_file()
        self.assertFalse(self.src.needs_restore())


@unittest.skipUnless(shutil.which('sqlite3') and shutil.which('bash'), 'needs sqlite3 CLI and bash')
class PullScriptFreshnessTests(unittest.TestCase):
    """Runs the real verify path of tools/neshama-backup-pull.sh (--verify, no SSH)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_backup(self, exported_at, obituaries=3, with_meta=True):
        path = os.path.join(self.tmp, 'candidate.db')
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE obituaries (id TEXT PRIMARY KEY)')
        conn.executemany('INSERT INTO obituaries VALUES (?)', [(f'o{i}',) for i in range(obituaries)])
        if with_meta:
            conn.execute('CREATE TABLE _backup_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            if exported_at is not None:
                conn.execute("INSERT INTO _backup_meta VALUES ('exported_at', ?)", (exported_at,))
        conn.commit()
        conn.close()
        return path

    def _verify(self, path):
        env = dict(os.environ, NESHAMA_BACKUP_DIR=self.tmp)
        proc = subprocess.run(['bash', PULL_SCRIPT, '--verify', path], env=env,
                              capture_output=True, text=True, timeout=60)
        with open(os.path.join(self.tmp, 'backup.log')) as f:
            log = f.read()
        return proc.returncode, log

    def _ago(self, hours):
        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec='seconds')

    def test_fresh_backup_passes(self):
        code, log = self._verify(self._make_backup(self._ago(1)))
        self.assertEqual(code, 0, log)
        self.assertIn('OK   ', log)
        self.assertIn('obituaries=3', log)

    def test_real_writer_output_passes(self):
        mgr = make_manager(self.tmp)
        result = mgr.backup_to_file()
        out = os.path.join(self.tmp, 'pulled.db')
        with gzip.open(result['path'], 'rb') as fin, open(out, 'wb') as fout:
            shutil.copyfileobj(fin, fout)
        code, log = self._verify(out)
        self.assertEqual(code, 0, log)

    def test_offset_other_than_utc_is_handled(self):
        toronto = datetime.now(timezone(timedelta(hours=-4))) - timedelta(hours=2)
        code, log = self._verify(self._make_backup(toronto.isoformat(timespec='seconds')))
        self.assertEqual(code, 0, log)

    def test_stale_backup_fails_with_age(self):
        code, log = self._verify(self._make_backup(self._ago(30)))
        self.assertEqual(code, 1)
        self.assertIn('FAIL', log)
        self.assertIn('STALE', log)
        self.assertRegex(log, r'is 30\.\dh old')

    def test_just_over_limit_fails(self):
        code, log = self._verify(self._make_backup(self._ago(26.2)))
        self.assertEqual(code, 1)
        self.assertIn('STALE', log)

    def test_missing_meta_table_fails(self):
        code, log = self._verify(self._make_backup(None, with_meta=False))
        self.assertEqual(code, 1)
        self.assertIn('no exported_at', log)

    def test_missing_exported_at_row_fails(self):
        code, log = self._verify(self._make_backup(None))
        self.assertEqual(code, 1)
        self.assertIn('no exported_at', log)

    def test_naive_timestamp_fails(self):
        naive = datetime.now().isoformat(timespec='seconds')
        code, log = self._verify(self._make_backup(naive))
        self.assertEqual(code, 1)
        self.assertIn('no exported_at', log)

    def test_no_obituaries_fails(self):
        code, log = self._verify(self._make_backup(self._ago(1), obituaries=0))
        self.assertEqual(code, 1)
        self.assertIn('no obituaries', log)

    def test_not_a_database_fails(self):
        path = os.path.join(self.tmp, 'junk.db')
        with open(path, 'w') as f:
            f.write('<html>error page</html>')
        code, log = self._verify(path)
        self.assertEqual(code, 1)
        self.assertIn('integrity_check', log)


if __name__ == '__main__':
    unittest.main()
