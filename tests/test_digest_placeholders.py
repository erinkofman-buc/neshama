#!/usr/bin/env python3
"""
Golden-file test: no placeholder junk may reach a rendered digest.

Every fixture below is a real value taken from the production database or from a
digest email Erin actually received between 2026-08-27 and 2026-09-01:

    "Shiva: Shiva Location"                       281 Steeles rows
    "Shiva: Shiva Details"                          4 Steeles rows
    "Burial: Dawes Road Cemetery"                 348 Steeles rows (ALL of them)
    "Shiva: Address: Shiva details to follow; Shiva details to follow"
                                                  Norma Bigman, Paperman, Aug 31

Run:  python3 -m pytest tests/test_digest_placeholders.py -v
"""

import os
import sys
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.abspath(REPO_ROOT))
sys.path.insert(0, os.path.abspath(os.path.join(REPO_ROOT, 'frontend')))

from field_hygiene import (
    is_placeholder, clean_field, collapse_duplicate_fragments, scrub_obituary_row
)
from daily_digest import DailyDigestSender


# Strings that must never appear in a rendered digest, in the exact form a
# reader would see them.
FORBIDDEN_IN_OUTPUT = [
    'Shiva: Shiva Location',
    'Shiva: Shiva Details',
    'Shiva: Shiva Information',
    'Shiva: Address: Shiva details to follow',
    'Shiva: details to follow',
    'Shiva: Details to follow',
    'Shiva: TBD',
    'Shiva: N/A',
    'Burial: Burial Location',
    'Burial: Cemetery',
    'Funeral: Funeral Location',
    'details to follow; Shiva details to follow',
]


def obit(**overrides):
    row = {
        'id': 'row-1',
        'source': 'Steeles Memorial Chapel',
        'source_url': 'https://steelesmemorialchapel.com/condolence/test-person/',
        'condolence_url': 'https://steelesmemorialchapel.com/condolence/test-person/',
        'deceased_name': 'Test Person',
        'hebrew_name': None,
        'funeral_datetime': None,
        'funeral_location': None,
        'shiva_info': None,
        'burial_location': None,
        'livestream_available': 0,
        'shiva_private': 0,
    }
    row.update(overrides)
    return row


class PlaceholderDetectionTests(unittest.TestCase):

    def test_production_placeholders_are_detected(self):
        for value in [
            'Shiva Location', 'shiva location', '  Shiva Location  ',
            'Shiva Details', 'Shiva Information', 'Shiva',
            'Burial Location', 'Burial Service Location', 'Cemetery',
            'Funeral Location', 'Address', 'Details', 'TBD', 'TBA', 'N/A',
            'To be announced', 'Details to follow', 'Shiva details to follow.',
            'details will follow', '', '   ', None, '-', ';',
        ]:
            with self.subTest(value=value):
                self.assertTrue(is_placeholder(value), f'{value!r} should be junk')

    def test_real_values_are_kept(self):
        for value in [
            'The Dawes Road Cemetery, 3169 St. Clair Avenue East., Scarborough ON',
            'Shiva at 6635 Mackle Road, Cote Saint-Luc, QC',
            'Shiva hours: Thursday, following burial, until 4:00 p.m.',
            'Pardes Chaim Cemetery',
            'Chapel Service',
            'Shiva will be observed at the family home on Tuesday',
        ]:
            with self.subTest(value=value):
                self.assertFalse(is_placeholder(value), f'{value!r} is real data')
                self.assertIsNotNone(clean_field(value))

    def test_a_real_value_mentioning_the_label_survives(self):
        """Substring matching would wrongly kill this. Exact matching does not."""
        value = 'Shiva location: 12 Bathurst Street, Toronto'
        self.assertFalse(is_placeholder(value))
        self.assertEqual(clean_field(value), value)


class FragmentCollapsingTests(unittest.TestCase):

    def test_duplicate_fragments_collapse(self):
        self.assertEqual(
            collapse_duplicate_fragments('Pardes Chaim; Pardes Chaim'),
            'Pardes Chaim')

    def test_the_norma_bigman_string_collapses_to_nothing(self):
        """The exact Aug 31 email defect. Both fragments are non-answers."""
        value = 'Address: Shiva details to follow; Shiva details to follow'
        self.assertIsNone(clean_field(value))

    def test_placeholder_fragment_dropped_but_real_one_kept(self):
        value = ('Shiva details to follow.; Address: 6565 Collins, Cote Saint-Luc, QC; '
                 'Dates: 2026-06-26 to 2026-07-01')
        cleaned = clean_field(value)
        self.assertIsNotNone(cleaned)
        self.assertNotIn('details to follow', cleaned.lower())
        self.assertIn('6565 Collins', cleaned)
        self.assertIn('2026-06-26', cleaned)


class RowScrubbingTests(unittest.TestCase):

    def test_api_row_is_scrubbed(self):
        row = scrub_obituary_row({
            'deceased_name': 'Test Person',
            'shiva_info': 'Shiva Location',
            'burial_location': 'Cemetery',
            'funeral_location': 'Chapel Service',
        })
        self.assertIsNone(row['shiva_info'])
        self.assertIsNone(row['burial_location'])
        self.assertEqual(row['funeral_location'], 'Chapel Service')

    def test_dawes_road_cemetery_is_NOT_treated_as_a_placeholder(self):
        """Deliberate, and the reason the 348 bad rows need a data fix.

        All 348 Steeles rows carry burial_location "Dawes Road Cemetery" because
        the old scraper matched the site's nav menu. But that string is also a
        REAL cemetery, and it is genuinely David Wayne De Leon's burial place.
        A content-based rule cannot tell the two apart, and one that tried would
        delete correct data.

        So this layer deliberately leaves it alone. The scraper fix stops new
        rows from getting it wrong; the existing rows are wrong DATA that looks
        like right data, and only a re-scrape can repair them.
        """
        row = scrub_obituary_row({'burial_location': 'Dawes Road Cemetery'})
        self.assertEqual(row['burial_location'], 'Dawes Road Cemetery')

    def test_names_are_never_scrubbed(self):
        row = scrub_obituary_row({'deceased_name': 'Details', 'shiva_info': 'Details'})
        self.assertEqual(row['deceased_name'], 'Details')
        self.assertIsNone(row['shiva_info'])


class RenderedDigestGoldenTests(unittest.TestCase):
    """Render a real digest from junk fixtures and assert the junk is gone."""

    def setUp(self):
        self.sender = DailyDigestSender.__new__(DailyDigestSender)

    def _render(self, rows):
        html = self.sender.generate_email_html(rows)
        self.assertIsNotNone(html)
        return html

    def test_no_forbidden_string_survives_rendering(self):
        rows = [
            obit(id='a', deceased_name='David Wayne De Leon',
                 shiva_info='Shiva Location', burial_location='Dawes Road Cemetery'),
            obit(id='b', deceased_name='Jacqueline Myrna Oppenheimer',
                 shiva_info='Shiva Details', burial_location='Dawes Road Cemetery'),
            obit(id='c', deceased_name='Norma Bigman', source='Paperman & Sons',
                 shiva_info='Address: Shiva details to follow; Shiva details to follow',
                 funeral_location='Chapel Service',
                 funeral_datetime='Tuesday, September 1 at 11:00AM'),
            obit(id='d', deceased_name='Placeholder Sweep',
                 shiva_info='TBD', burial_location='Cemetery',
                 funeral_location='Funeral Location',
                 funeral_datetime='Wednesday, September 2 at 1:00PM'),
        ]
        html = self._render(rows)
        for forbidden in FORBIDDEN_IN_OUTPUT:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, html,
                                 f'placeholder leaked into the digest: {forbidden!r}')

    def test_real_detail_still_renders(self):
        rows = [obit(
            deceased_name='Sandra Dubrofsky',
            source='Paperman & Sons',
            funeral_datetime='Thursday, September 3 at 11:00AM',
            funeral_location='Chapel Service',
            burial_location='Kehal Israel Memorial Park',
            shiva_info='Shiva hours: Thursday, following burial, until 4:00 p.m.',
        )]
        html = self._render(rows)
        self.assertIn('Sandra Dubrofsky', html)
        self.assertIn('Kehal Israel Memorial Park', html)
        self.assertIn('Thursday, September 3 at 11:00AM', html)
        self.assertIn('Shiva hours: Thursday', html)

    def test_private_shiva_reads_as_private_not_as_a_placeholder(self):
        rows = [obit(deceased_name='David Wayne De Leon',
                     shiva_info=None, shiva_private=1)]
        html = self._render(rows)
        self.assertIn('Shiva: private', html)
        self.assertNotIn('Shiva Location', html)

    def test_an_obituary_with_only_junk_still_renders_its_name_and_link(self):
        """Suppressing lines must never suppress the person."""
        rows = [obit(deceased_name='Minimal Record',
                     shiva_info='Shiva Location', burial_location='Cemetery')]
        html = self._render(rows)
        self.assertIn('Minimal Record', html)
        self.assertIn('Read full obituary', html)

    def test_plain_text_alternative_is_also_clean(self):
        from daily_digest import _html_to_plain
        rows = [obit(deceased_name='David Wayne De Leon',
                     shiva_info='Shiva Location',
                     burial_location='Dawes Road Cemetery')]
        plain = _html_to_plain(self._render(rows))
        for forbidden in FORBIDDEN_IN_OUTPUT:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, plain)


if __name__ == '__main__':
    unittest.main(verbosity=2)
