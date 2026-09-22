#!/usr/bin/env python3
"""
Tests for the memorial server-render and the generated sitemap.

Why these exist: Search Console reported 14 memorial URLs as soft 404s. The
memorial page shipped as a JS shell with a "We Couldn't Find This Memorial"
block in every page's markup, so anything that did not (or could not) run the
client fetch read a not-found page on a 200. The sitemap listed no memorial or
vendor pages at all, and did list two pages that are noindex.

Run:  python3 -m pytest tests/test_memorial_ssr.py -v
"""

import os
import re
import sys
import sqlite3
import tempfile
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(REPO_ROOT))
sys.path.insert(0, os.path.abspath(os.path.join(REPO_ROOT, 'frontend')))

import api_server  # noqa: E402

TEMPLATE = open(os.path.join(REPO_ROOT, 'frontend', 'memorial.html'), encoding='utf-8').read()
STATIC_SITEMAP = open(os.path.join(REPO_ROOT, 'frontend', 'sitemap.xml'), 'rb').read()


def make_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute('''CREATE TABLE obituaries (
        id TEXT PRIMARY KEY, deceased_name TEXT, hebrew_name TEXT, obituary_text TEXT,
        photo_url TEXT, source TEXT, source_url TEXT, source_key TEXT, condolence_url TEXT,
        date_of_death TEXT, yahrzeit_date TEXT, funeral_datetime TEXT, funeral_location TEXT,
        burial_info TEXT, livestream_url TEXT, shiva_address TEXT, shiva_info TEXT,
        first_seen TEXT, last_updated TEXT, hidden INTEGER DEFAULT 0)''')
    conn.execute('CREATE TABLE vendors (slug TEXT)')
    rows = [
        # id, name, source_key, first_seen, hidden
        ('keep', 'Joseph Hayeems', 'steeles:hayeems', '2026-09-01T10:00:00', 0),
        ('later', 'Joseph Hayeems (Start Time May Be Delayed)', 'steeles:hayeems', '2026-09-02T10:00:00', 0),
        ('solo', 'Ruth Adler', 'paperman:adler', '2026-09-03T10:00:00', 0),
        ('nokey', 'No Key Person', None, '2026-09-03T11:00:00', 0),
        ('junk', 'test', 'steeles:junk', '2026-09-04T10:00:00', 1),
    ]
    for oid, name, key, seen, hidden in rows:
        conn.execute('INSERT INTO obituaries (id, deceased_name, source_key, first_seen, last_updated, hidden) '
                     'VALUES (?, ?, ?, ?, ?, ?)', (oid, name, key, seen, seen, hidden))
    conn.execute("INSERT INTO vendors VALUES ('nortown-foods'), ('united-bakers'), (''), (NULL)")
    conn.commit()
    conn.close()
    return path


class MemorialBodyTests(unittest.TestCase):

    def row(self, **over):
        base = {
            'id': 'solo', 'deceased_name': 'Ruth <Adler>', 'hebrew_name': 'Rivka bat Moshe',
            'obituary_text': 'ADLER, Ruth - Beloved <b>mother</b>.', 'photo_url': 'https://x.test/p.jpg',
            'source': 'Paperman & Sons', 'condolence_url': 'https://paperman.test/c/1',
            'date_of_death': '2026-09-14', 'yahrzeit_date': '12 Tishrei 5787',
            'funeral_datetime': 'September 15, 2026 at 11:30am', 'funeral_location': 'Chapel',
            'burial_info': 'Pardes Shalom', 'livestream_url': 'javascript:alert(1)',
            'shiva_address': '12 Secret Crescent', 'shiva_info': 'Shiva at 12 Secret Crescent',
        }
        base.update(over)
        return base

    def test_not_found_block_removed_and_content_visible(self):
        html = api_server.render_memorial_body(TEMPLATE, self.row())
        self.assertNotIn("We Couldn't Find This Memorial", html)
        self.assertIn('id="memorialContent" data-ssr="1"', html)
        self.assertIn('id="pageLoading" style="display: none;"', html)

    def test_hero_and_text_are_escaped(self):
        html = api_server.render_memorial_body(TEMPLATE, self.row())
        self.assertIn('id="heroName">Ruth &lt;Adler&gt;</h1>', html)
        self.assertIn('Beloved &lt;b&gt;mother&lt;/b&gt;.', html)
        self.assertIn('Date of Passing: Monday, September 14, 2026', html)
        self.assertIn('Rivka bat Moshe', html)

    def test_shiva_card_is_never_server_rendered(self):
        html = api_server.render_memorial_body(TEMPLATE, self.row())
        self.assertNotIn('12 Secret Crescent', html)
        self.assertNotIn('Shiva Information', html.split('<script', 1)[0])

    def test_services_and_source_link(self):
        html = api_server.render_memorial_body(TEMPLATE, self.row())
        self.assertIn('Funeral Service', html)
        self.assertIn('Pardes Shalom', html)
        self.assertIn('href="https://paperman.test/c/1"', html)
        self.assertIn('id="sourceName">Paperman &amp; Sons</span>', html)
        # A non-http livestream url is dropped, not rendered as a link.
        self.assertNotIn('javascript:alert', html)

    def test_street_addresses_stripped_from_obituary_text(self):
        text = ('Shiva will be held at the home of Dan and Shelley, 12 Secret Crescent '
                'North York M2P 1L7, from 2 to 4.')
        html = api_server.render_memorial_body(TEMPLATE, self.row(obituary_text=text))
        self.assertNotIn('Secret Crescent', html)
        self.assertNotIn('M2P 1L7', html)
        self.assertIn('home of Dan and Shelley, (address not shown), from 2 to 4.', html)

    def test_address_forms_seen_in_production(self):
        strip = api_server.strip_street_addresses
        cases = {
            '34 Mellowood Drive, Toronto, Ontario, M2L 2E3, Monday': '(address not shown), Monday',
            'at 409 Russell Hill Road, Toronto, Ontario M4V 2V3. Memorial': 'at (address not shown). Memorial',
            '251 avenue des Pins Ouest, Montreal, QC, H2W 1R6.': '(address not shown).',
            "lieu à 1639 Rue de l'Everest, Montréal, QC H4R 2Y5.": 'lieu à (address not shown).',
            '(2401 2e Rue, Sainte-Sophie, Quebec, J5J 1N6).': '((address not shown)).',
            'at 2333 rue Sherbrooke Ouest Wednesday at 11': 'at (address not shown) Wednesday at 11',
            '(5380 Bourret ave, Montreal, QC, H3X 1J2)': '((address not shown))',
        }
        for given, expected in cases.items():
            self.assertEqual(strip(given), expected, given)

    def test_dates_counts_and_plots_are_not_addresses(self):
        strip = api_server.strip_street_addresses
        for text in ('passed away on Monday, March 2, 2026 at 10:00 a.m.',
                     'Beth Tzedek Memorial Park, Section 5 Row 3.',
                     'survived by 3 grandchildren and 12 Great grandchildren. Born 1932.'):
            self.assertEqual(strip(text), text)

    def test_nameless_row_leaves_template_untouched(self):
        self.assertEqual(api_server.render_memorial_body(TEMPLATE, self.row(deceased_name='')), TEMPLATE)

    def test_client_keeps_ssr_content_when_refresh_fails(self):
        self.assertIn("content.getAttribute('data-ssr')", TEMPLATE)


class CanonicalAndSitemapTests(unittest.TestCase):

    def setUp(self):
        self.db = make_db()

    def tearDown(self):
        os.remove(self.db)

    def test_duplicate_points_at_oldest_survivor(self):
        later = api_server.fetch_memorial_row(self.db, 'later')
        self.assertEqual(api_server.memorial_canonical_id(self.db, later), 'keep')
        keep = api_server.fetch_memorial_row(self.db, 'keep')
        self.assertEqual(api_server.memorial_canonical_id(self.db, keep), 'keep')

    def test_row_without_source_key_is_self_canonical(self):
        row = api_server.fetch_memorial_row(self.db, 'nokey')
        self.assertEqual(api_server.memorial_canonical_id(self.db, row), 'nokey')

    def test_unknown_id(self):
        self.assertIsNone(api_server.fetch_memorial_row(self.db, 'nope'))

    def test_sitemap_lists_one_url_per_person_and_no_hidden(self):
        xml = api_server.build_sitemap_xml(STATIC_SITEMAP, self.db).decode('utf-8')
        mem = re.findall(r'/memorial/([^<]+)</loc>', xml)
        self.assertEqual(sorted(mem), ['keep', 'nokey', 'solo'])
        self.assertIn('https://neshama.ca/directory/nortown-foods</loc>', xml)
        self.assertNotIn('https://neshama.ca/directory/</loc>', xml)
        self.assertIn('<lastmod>2026-09-01</lastmod>', xml)
        self.assertTrue(xml.rstrip().endswith('</urlset>'))

    def test_static_sitemap_has_no_noindex_or_blocked_pages(self):
        static = STATIC_SITEMAP.decode('utf-8')
        for path in ('/find-home-care', '/care-setup', '/find-a-death-doula', '/shiva/view',
                     '/shiva/dashboard', '/dashboard', '/shiva-caterers-montreal', '/shiva-essentials'):
            self.assertNotIn('https://neshama.ca' + path + '</loc>', static)
        robots = open(os.path.join(REPO_ROOT, 'frontend', 'robots.txt')).read()
        self.assertIn('Sitemap: https://neshama.ca/sitemap.xml', robots)
        disallowed = [l.split(':', 1)[1].strip() for l in robots.splitlines() if l.startswith('Disallow:')]
        for loc in re.findall(r'<loc>https://neshama\.ca([^<]*)</loc>', static):
            self.assertFalse(any((loc or '/').startswith(d) for d in disallowed), loc)

    def test_db_failure_falls_back_to_static(self):
        self.assertEqual(api_server.build_sitemap_xml(STATIC_SITEMAP, '/nonexistent/dir/x.db'), STATIC_SITEMAP)


if __name__ == '__main__':
    unittest.main()
