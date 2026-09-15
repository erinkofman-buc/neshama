#!/usr/bin/env python3
"""
Benjamin's listing-newsletter ingestion (benjamins_newsletter.py).

Fixtures are real issues of the e-mail, captured 2026-09-15 from Erin's
inbox: the five most recent (Sep 12 PM to Sep 14 PM) plus Aug 30 PM, which is
the most recent issue that carries SHIVA and UNVEILING rows. Their details
links contain the control-byte damage a quoted-printable decoder leaves
behind, exactly as a forwarded copy arrives. The raw-MIME test builds a
message with Benjamin's unescaped "=" so the direct-subscription path is
covered too.

Run:  python3 -m pytest tests/test_benjamins_newsletter.py -v
"""

import glob
import json
import os
import quopri
import sqlite3
import sys
import tempfile
import unittest
from email.message import EmailMessage

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, REPO_ROOT)

import benjamins_newsletter as bn  # noqa: E402
from database_setup import NeshamaDatabase  # noqa: E402
from obituary_identity import source_key  # noqa: E402

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'benjamins_newsletter')
PUBLIC_ROWS = os.environ.get(
    'BENJAMINS_PUBLIC_ROWS',
    '/private/tmp/claude-501/-Users-erinkofman-Desktop-Neshama/a05a1d8d-6e09-49e0-9205-61f8af56ba5b/scratchpad/benjamins_public_rows.json')


def load_fixtures():
    out = []
    for path in sorted(glob.glob(os.path.join(FIXTURE_DIR, '*.json'))):
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        d['_name'] = os.path.basename(path)
        out.append(d)
    return out


FIXTURES = load_fixtures()


def listing_rows(parsed):
    """Rows that came from the LISTINGS table (they carry a funeral date)."""
    return [r for r in parsed['rows'] if r.get('funeral_datetime')]


class ServiceNumberRecovery(unittest.TestCase):
    def test_intact(self):
        self.assertEqual(bn.recover_snum('https://x/ServiceDetails.aspx?snum=142306&fg=0'), '142306')
        self.assertEqual(bn.recover_snum('https://x/ServiceDetails?snum=87767'), '87767')

    def test_decoder_damage(self):
        # '=14' eaten into byte 0x14, '=12' into 0x12, '=87' into 0x87
        self.assertEqual(bn.recover_snum('https://x/ServiceDetails.aspx?snum\x142306&fg=0'), '142306')
        self.assertEqual(bn.recover_snum('https://x/ServiceDetails.aspx?snum\x124824&fg=0'), '124824')
        self.assertEqual(bn.recover_snum('https://x/ServiceDetails.aspx?snum\x87767&fg=0'), '87767')

    def test_unrecoverable(self):
        self.assertIsNone(bn.recover_snum('https://x/ServiceDetails.aspx?snum�2306'))
        self.assertIsNone(bn.recover_snum(None))

    def test_repair_escapes_only_bare_equals(self):
        self.assertEqual(bn.repair_quoted_printable('a?snum=142306&b'), 'a?snum=3D142306&b')
        self.assertEqual(bn.repair_quoted_printable('a?snum=3D142306&b'), 'a?snum=3D142306&b')
        self.assertEqual(bn.repair_quoted_printable(b'snum=87767'), b'snum=3D87767')


class DisplayName(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(bn.display_name('Bean, Sharon'), 'Sharon Bean')
        self.assertEqual(bn.display_name('Baker, Harriet "Honey"'), 'Harriet "Honey" Baker')
        self.assertEqual(bn.display_name('Kosoy (Nakelsky), Jodi Sheryl'), 'Jodi Sheryl Kosoy (Nakelsky)')
        self.assertEqual(bn.display_name('Wolfe, Q.C./K.C., Morley S.'), 'Morley S. Wolfe, Q.C./K.C.')
        self.assertEqual(bn.display_name('Raider-Dvorkin, Esta'), 'Esta Raider-Dvorkin')
        self.assertEqual(bn.display_name('Madonna'), 'Madonna')


class FuneralFields(unittest.TestCase):
    def test_time_first_chapel(self):
        self.assertEqual(bn._funeral_fields('September 14, 2026', '11:30 am, Chapel'),
                         ('September 14, 2026 at 11:30am', "Benjamin's Park Memorial Chapel"))

    def test_time_first_named_place(self):
        self.assertEqual(bn._funeral_fields('September 15, 2026', '12:00 pm, Beth Tzedec Memorial Park'),
                         ('September 15, 2026 at 12:00pm', 'Beth Tzedec Memorial Park'))

    def test_place_only(self):
        self.assertEqual(bn._funeral_fields('September 14, 2026', 'Service in London, England.'),
                         ('September 14, 2026', 'Service in London, England.'))

    def test_monitor_notice(self):
        self.assertEqual(bn._funeral_fields('September 16, 2026', 'Please monitor this website for updates.'),
                         ('September 16, 2026', None))


class RealIssues(unittest.TestCase):
    def test_fixtures_present(self):
        self.assertGreaterEqual(len(FIXTURES), 6)

    def test_each_issue_parses_to_expectation(self):
        for fx in FIXTURES:
            with self.subTest(issue=fx['_name']):
                parsed = bn.parse_issue(fx['html'])
                exp = fx['expect']
                self.assertEqual(parsed['issue_label'], exp['issue_label'])
                rows = listing_rows(parsed)
                self.assertEqual(len(rows), exp['listing_rows'], [r['deceased_name'] for r in rows])
                self.assertEqual(parsed['skipped_courtesy'], exp['courtesy_rows_skipped'])
                self.assertEqual(len(parsed['shiva']), exp['shiva_rows'])
                got = [r['source_url'].rsplit('=', 1)[1] for r in rows]
                self.assertEqual(got, exp['listing_snums'])
                for r in parsed['rows']:
                    self.assertTrue(r['source_url'].startswith('https://benjaminsparkmemorialchapel.ca/ServiceDetails?snum='))
                    self.assertNotIn('\x14', r['source_url'])
                    self.assertNotIn(',', r['deceased_name'].split(' ')[0])
                if 'unveiling_snum_must_be_absent' in exp:
                    self.assertNotIn(exp['unveiling_snum_must_be_absent'], got)
                    self.assertNotIn(exp['unveiling_snum_must_be_absent'], parsed['shiva'])

    def test_courtesy_rows_never_become_benjamins_obituaries(self):
        names = set()
        for fx in FIXTURES:
            for r in bn.parse_issue(fx['html'])['rows']:
                names.add(r['deceased_name'])
        for courtesy in ('Roman Gorelik', 'Nathan Sugar', 'Harold Sommers', 'Brenda Glazer',
                         'Avi Avrum Benshabat', 'Nachum Woolf', 'Berthe Glasroth'):
            self.assertNotIn(courtesy, names)

    def test_shiva_rows_carry_address_and_survive_without_a_listing(self):
        fx = next(f for f in FIXTURES if f['_name'] == '2026-08-30-PM.json')
        parsed = bn.parse_issue(fx['html'])
        by_snum = {r['source_url'].rsplit('=', 1)[1]: r for r in parsed['rows']}
        # Teperman's funeral (Aug 26) is no longer listed; the shiva row alone must still produce her row.
        self.assertIn('142268', by_snum)
        self.assertEqual(by_snum['142268']['deceased_name'], 'Leanna Ruth Teperman')
        self.assertEqual(by_snum['142268']['shiva_address'], '7905 Bayview Avenue, PH 1214, Thornhill, Ontario')
        self.assertIn('Please check the specific funeral for visiting times', by_snum['142268']['shiva_info'])
        self.assertIsNone(by_snum['142268']['funeral_datetime'])
        # Kosoy has a shiva row with no address line: row exists, no shiva fields invented.
        self.assertIn('142274', by_snum)
        self.assertNotIn('shiva_address', by_snum['142274'])
        # A listed funeral with a photo keeps it.
        self.assertTrue(by_snum['142279']['photo_url'].endswith('WEINER-Larry-aspect-ratio-635-596.jpg'))
        self.assertEqual(by_snum['142279']['funeral_datetime'], 'August 30, 2026 at 10:00am')

    def test_photo_and_name_forms_on_sep_14(self):
        fx = next(f for f in FIXTURES if f['_name'] == '2026-09-14-PM.json')
        by = {r['source_url'].rsplit('=', 1)[1]: r for r in bn.parse_issue(fx['html'])['rows']}
        self.assertEqual(by['142309']['deceased_name'], 'Harriet "Honey" Baker')
        self.assertEqual(by['142313']['funeral_location'], 'Service in London, England.')
        self.assertEqual(by['142314']['funeral_datetime'], 'September 16, 2026')
        self.assertIsNone(by['142314']['funeral_location'])
        self.assertIsNone(by['142311']['photo_url'])


class RawMimeQuotedPrintable(unittest.TestCase):
    """The direct-subscription path: Benjamin's leaves '=' bare inside snum links."""

    def _benjamins_style_message(self, html):
        msg = EmailMessage()
        msg['Subject'] = "Benjamin's Park Memorial Chapel: Sunday, 30 August 2026 PM"
        msg['From'] = 'noreply@benjamins.ca'
        msg['To'] = 'listings@benjamins.ca'
        msg['Date'] = 'Sun, 30 Aug 2026 20:52:31 -0400'
        msg.set_content(html, subtype='html', cte='quoted-printable')
        raw = msg.as_bytes()
        # Reproduce their bug: the '=' of 'snum=NNNN' is sent unescaped.
        return raw.replace(b'snum=3D', b'snum=')

    def test_repair_then_decode_keeps_service_numbers(self):
        fx = next(f for f in FIXTURES if f['_name'] == '2026-08-30-PM.json')
        clean_html = fx['html'].replace('snum\x14', 'snum=14').replace('snum\x12', 'snum=12')
        raw = self._benjamins_style_message(clean_html)
        self.assertIn(b'snum=142279', raw)                       # bare '=' present in the wire form
        # A standards decoder eats it ...
        mangled = quopri.decodestring(raw.split(b'\n\n', 1)[1])
        self.assertIn(b'snum\x142279', mangled)
        # ... and our path does not.
        html, subject, sent_at = bn.html_from_message(raw)
        self.assertIn('snum=142279', html)
        self.assertEqual(subject, "Benjamin's Park Memorial Chapel: Sunday, 30 August 2026 PM")
        self.assertEqual(sent_at.isoformat(), '2026-08-30T20:52:31-04:00')
        parsed = bn.parse_issue(html)
        self.assertEqual([r['source_url'].rsplit('=', 1)[1] for r in listing_rows(parsed)],
                         fx['expect']['listing_snums'])

    def test_forwarded_copy_still_parses(self):
        # Erin's back-fill: Gmail re-encodes correctly but the damage is already in the body.
        fx = next(f for f in FIXTURES if f['_name'] == '2026-09-12-PM.json')
        msg = EmailMessage()
        msg['Subject'] = "Fwd: " + fx['subject']
        msg['From'] = 'erin@example.com'
        msg['Date'] = 'Tue, 15 Sep 2026 09:00:00 -0400'
        msg.set_content('<div>---------- Forwarded message ---------</div>' + fx['html'], subtype='html', cte='quoted-printable')
        html, subject, _ = bn.html_from_message(msg.as_bytes())
        self.assertIn(bn.SUBJECT_MARK, subject)
        parsed = bn.parse_issue(html)
        self.assertEqual([r['source_url'].rsplit('=', 1)[1] for r in listing_rows(parsed)], fx['expect']['listing_snums'])


class MergePreserving(unittest.TestCase):
    def test_existing_fields_survive(self):
        existing = {'id': 'abc', 'source': "Benjamin's Park Memorial Chapel", 'deceased_name': 'Sharon Bean',
                    'source_url': 'https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=142306&fg=0',
                    'date_of_death': 'September 10, 2026', 'obituary_text': 'BEAN, Sharon - On Thursday ...',
                    'hebrew_name': 'Shifra Perel Bat Yaacov', 'funeral_datetime': None, 'funeral_location': None,
                    'photo_url': None, 'shiva_address': '49 Waterloo Avenue', 'shiva_info': 'Shiva visits ...'}
        new = {'source': "Benjamin's Park Memorial Chapel", 'deceased_name': 'Sharon Bean',
               'source_url': 'https://benjaminsparkmemorialchapel.ca/ServiceDetails?snum=142306',
               'funeral_datetime': 'September 14, 2026 at 11:30am', 'funeral_location': "Benjamin's Park Memorial Chapel",
               'photo_url': None}
        merged = bn.merge_preserving(existing, new)
        self.assertEqual(merged['date_of_death'], 'September 10, 2026')
        self.assertEqual(merged['obituary_text'], 'BEAN, Sharon - On Thursday ...')
        self.assertEqual(merged['hebrew_name'], 'Shifra Perel Bat Yaacov')
        self.assertEqual(merged['shiva_address'], '49 Waterloo Avenue')
        self.assertEqual(merged['funeral_datetime'], 'September 14, 2026 at 11:30am')
        self.assertEqual(merged['source_url'], 'https://benjaminsparkmemorialchapel.ca/ServiceDetails?snum=142306')

    def test_no_existing_row(self):
        new = {'source': 'x', 'deceased_name': 'y', 'source_url': 'z'}
        self.assertEqual(bn.merge_preserving(None, new), new)


class IngestIntoDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, 'neshama.db')
        self.db = NeshamaDatabase(self.path)
        self.db.create_tables()

    def _count(self, where='1=1'):
        c = sqlite3.connect(self.path)
        n = c.execute(f'SELECT COUNT(*) FROM obituaries WHERE {where}').fetchone()[0]
        c.close()
        return n

    def _row(self, snum):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        r = c.execute('SELECT * FROM obituaries WHERE source_key = ?', (f'benjamins:{snum}',)).fetchall()
        c.close()
        return [dict(x) for x in r]

    def test_existing_row_updates_in_place_and_keeps_its_fields(self):
        # A row the old details-page scraper wrote, in the OLD url form.
        self.db.upsert_obituary({
            'source': "Benjamin's Park Memorial Chapel", 'deceased_name': 'Sharon Bean',
            'source_url': 'https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=142306&fg=0',
            'condolence_url': 'https://benjaminsparkmemorialchapel.ca/ServiceDetails.aspx?snum=142306&fg=0',
            'date_of_death': 'September 10, 2026', 'obituary_text': 'BEAN, Sharon - On Thursday, September 10, 2026.',
            'hebrew_name': 'Shifra Perel Bat Yaacov', 'shiva_address': '49 Waterloo Avenue, Toronto',
        })
        before = self._row('142306')
        self.assertEqual(len(before), 1)
        fx = next(f for f in FIXTURES if f['_name'] == '2026-09-14-PM.json')
        rows = bn.parse_issue(fx['html'])['rows']
        new, updated = bn.ingest_rows(self.db, rows)
        after = self._row('142306')
        self.assertEqual(len(after), 1, 'the existing service forked')
        self.assertEqual(after[0]['id'], before[0]['id'])
        self.assertEqual(after[0]['date_of_death'], 'September 10, 2026')
        self.assertEqual(after[0]['obituary_text'], 'BEAN, Sharon - On Thursday, September 10, 2026.')
        self.assertEqual(after[0]['hebrew_name'], 'Shifra Perel Bat Yaacov')
        self.assertEqual(after[0]['shiva_address'], '49 Waterloo Avenue, Toronto')
        self.assertEqual(after[0]['funeral_datetime'], 'September 14, 2026 at 11:30am')
        self.assertEqual(after[0]['funeral_location'], "Benjamin's Park Memorial Chapel")
        self.assertTrue(after[0]['photo_url'].endswith('BEAN-Sharon-scaled-e1789147941469-150x173.jpg'))
        self.assertEqual(self._count(), 1 + (len(rows) - 1))
        self.assertEqual(new, len(rows) - 1)
        self.assertEqual(updated, 1)

    def test_reingest_is_idempotent(self):
        fx = next(f for f in FIXTURES if f['_name'] == '2026-09-14-PM.json')
        rows = bn.parse_issue(fx['html'])['rows']
        bn.ingest_rows(self.db, rows)
        n = self._count()
        bn.ingest_rows(self.db, rows)
        bn.ingest_rows(self.db, bn.parse_issue(next(f for f in FIXTURES if f['_name'] == '2026-09-14-AM.json')['html'])['rows'])
        self.assertEqual(self._count(), n, 'a second pass minted new rows')
        keys = sqlite3.connect(self.path).execute(
            'SELECT source_key, COUNT(*) FROM obituaries GROUP BY source_key HAVING COUNT(*) > 1').fetchall()
        self.assertEqual(keys, [], 'forked source_keys')

    def test_record_issue_uses_the_issue_time(self):
        from datetime import datetime, timezone, timedelta
        sent = datetime(2026, 9, 14, 20, 51, 44, tzinfo=timezone(timedelta(hours=-4)))
        bn.record_issue(self.db, 'Monday, 14 September 2026 PM Update', sent, 11, 3, 8)
        r = sqlite3.connect(self.path).execute(
            "SELECT source, run_time, status, obituaries_found, error_message FROM scraper_log").fetchone()
        self.assertEqual(r, ("Benjamin's Park Memorial Chapel", '2026-09-15T00:51:44', 'newsletter', 11,
                             'issue=Monday, 14 September 2026 PM Update'))

    @unittest.skipUnless(os.path.exists(PUBLIC_ROWS), 'public Benjamin\'s rows snapshot not available')
    def test_all_325_existing_services_update_in_place(self):
        """Seed the production set of Benjamin's rows (public API snapshot,
        325 rows), ingest all six real issues, and assert: no existing service
        gains a second row, ids are unchanged, only genuinely new services add
        rows, and re-running changes nothing."""
        with open(PUBLIC_ROWS, encoding='utf-8') as f:
            seed = json.load(f)
        for r in seed:
            row = {k: v for k, v in r.items() if k in (
                'source', 'deceased_name', 'source_url', 'date_of_death', 'funeral_datetime',
                'funeral_location', 'burial_location', 'shiva_info', 'photo_url')}
            row['condolence_url'] = row['source_url']      # what the old scraper always set
            self.db.upsert_obituary(row)
        # The public snapshot still carries the unmerged duplicate pairs (old
        # ?sid=&snum= form next to the ?snum=&fg= form); the source_key path
        # folds each pair onto one row, so distinct services < rows.
        distinct = {source_key(r['source'], r['source_url']) for r in seed}
        self.assertEqual(self._count(), len(distinct))
        c = sqlite3.connect(self.path)
        ids_before = dict(c.execute('SELECT source_key, id FROM obituaries').fetchall())
        dod_before = dict(c.execute('SELECT source_key, date_of_death FROM obituaries').fetchall())
        c.close()

        all_rows = []
        for fx in FIXTURES:
            all_rows.extend(bn.parse_issue(fx['html'])['rows'])
        # None of the six issues reaches back to a service already in the
        # snapshot (its newest row is 2026-08-04), so also synthesize what a
        # newsletter row for ten REAL existing services would look like, using
        # their own names, across both historical URL forms.
        sample = [r for r in seed if r.get('source_url')][:5] + [r for r in seed if '?sid=' in (r.get('source_url') or '')][:5]
        for r in sample:
            snum = source_key(r['source'], r['source_url']).split(':')[1]
            first, _, last = r['deceased_name'].rpartition(' ')
            all_rows.append(bn._make_row(snum, f"{last}, {first}", 'September 20, 2026 at 10:00am',
                                         "Benjamin's Park Memorial Chapel", None, None, None))
        self.assertEqual(len(sample), 10)
        bn.ingest_rows(self.db, all_rows)
        incoming = {source_key("Benjamin's Park Memorial Chapel", r['source_url']) for r in all_rows}
        existing_hit = incoming & set(ids_before)
        brand_new = incoming - set(ids_before)

        c = sqlite3.connect(self.path)
        ids_after = dict(c.execute('SELECT source_key, id FROM obituaries').fetchall())
        dod_after = dict(c.execute('SELECT source_key, date_of_death FROM obituaries').fetchall())
        forks = c.execute('SELECT source_key, COUNT(*) FROM obituaries GROUP BY source_key HAVING COUNT(*) > 1').fetchall()
        c.close()
        self.assertEqual(forks, [])
        self.assertEqual(len(ids_after), len(distinct) + len(brand_new))
        self.assertEqual(len(existing_hit), 10, 'the ten synthesized rows must land on existing services')
        for k in existing_hit:
            self.assertEqual(ids_after[k], ids_before[k], f'{k} changed id')
            self.assertEqual(dod_after[k], dod_before[k], f'{k} lost its death date')
        c = sqlite3.connect(self.path)
        updated_when = dict(c.execute(
            'SELECT source_key, funeral_datetime FROM obituaries WHERE source_key IN (%s)' % ','.join('?' * len(existing_hit)),
            list(existing_hit)).fetchall())
        c.close()
        self.assertTrue(all(v == 'September 20, 2026 at 10:00am' for v in updated_when.values()), updated_when)
        n = self._count()
        bn.ingest_rows(self.db, all_rows)
        self.assertEqual(self._count(), n)
        print(f'\n[325-row check] seeded {len(seed)}, incoming services {len(incoming)}, '
              f'matched existing {len(existing_hit)}, genuinely new {len(brand_new)}, forks 0')


if __name__ == '__main__':
    unittest.main()
