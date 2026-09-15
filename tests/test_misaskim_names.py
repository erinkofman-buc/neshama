#!/usr/bin/env python3
"""
Misaskim name extraction: card chrome must never leak into a person's name.

Taken from production on 2026-09-14/15. The listing card's <a> has no heading,
so the scraper reads the anchor's full text. get_text(strip=True) joined the
text nodes with no separator, so the "All Shiva Listings" nav link and the
"C$180" donation figure arrived glued onto the name:

    'RAV DOVID SCHUR Z"LAll'        (2026-09-14)
    'RAV DOVID SCHUR Z"LAll C$'     (2026-09-15)

The changing suffix forked a second row for the same man.

Run:  python3 -m pytest tests/test_misaskim_names.py -v
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, REPO_ROOT)

import misaskim_scraper as ms  # noqa: E402


# Mirrors the live card markup as of 2026-09-15: name in a span, then the nav
# link text, the two action labels, and the LevCharity progress block. No heading.
def card(name, raised='C$180'):
    return f'''
    <a href="https://misaskim.ca/shiva-listings/{ms._extract_slug(name.lower().replace(' ', '-').replace('"', ''))}/">
      <span class="campaign-title">{name}</span>
      <span class="nav-link">All Shiva Listings</span>
      <span class="btn">Donate in memory</span>
      <span class="btn">View shiva information</span>
      <div class="progress"><span>{raised}</span><span>0% of</span><span>C$0</span><span>goal</span></div>
    </a>'''


PAGE = f'''<html><body>
  <a href="/shiva-listings/">Shiva Listings</a>
  {card('RAV DOVID SCHUR Z"L', 'C$180')}
  {card('MR. NACHUM WOOLF Z”L', 'C$0')}
  {card('MRS. ROCHELLE BARBRA GROSSMAN A"H', 'C$1,250.50')}
  <a href="https://misaskim.ca/shiva-listings/with-heading/">
    <h3>MRS. BRENDA LEV A”H</h3><span>All Shiva Listings</span><span>Donate in memory</span>
  </a>
</body></html>'''


class NameFromCardText(unittest.TestCase):
    def test_spaced_chrome_is_dropped(self):
        text = 'RAV DOVID SCHUR Z"L All Shiva Listings Donate in memory View shiva information C$180 0% of C$0 goal'
        self.assertEqual(ms._name_from_card_text(text), 'RAV DOVID SCHUR Z"L')

    def test_glued_chrome_is_dropped(self):
        # The exact failure shape: no separator between the honorific and "All".
        text = 'RAV DOVID SCHUR Z"LAll Shiva ListingsDonate in memoryView shiva informationC$1800% ofC$0goal'
        self.assertEqual(ms._name_from_card_text(text), 'RAV DOVID SCHUR Z"L')

    def test_currency_alone_is_dropped(self):
        self.assertEqual(ms._name_from_card_text('MR. NACHUM WOOLF Z”L C$'), 'MR. NACHUM WOOLF Z”L')

    def test_plain_name_untouched(self):
        self.assertEqual(ms._name_from_card_text('MRS. CHERYL SONENBERG A”H'), 'MRS. CHERYL SONENBERG A”H')

    def test_empty(self):
        self.assertEqual(ms._name_from_card_text(''), '')
        self.assertEqual(ms._name_from_card_text(None), '')


class ScrapeListingsPage(unittest.TestCase):
    def _scrape(self, html):
        resp = MagicMock()
        resp.text = html
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        with patch.object(ms.requests, 'get', return_value=resp):
            listings, _ = ms.scrape_listings_page(ms.BASE_URL)
        return {l['slug']: l['name'] for l in listings}

    def test_live_card_shape_yields_clean_names(self):
        names = self._scrape(PAGE)
        self.assertEqual(names['rav-dovid-schur-zl'], 'RAV DOVID SCHUR Z"L')
        self.assertEqual(names['mr.-nachum-woolf-z”l'], 'MR. NACHUM WOOLF Z”L')
        self.assertEqual(names['mrs.-rochelle-barbra-grossman-ah'], 'MRS. ROCHELLE BARBRA GROSSMAN A"H')
        self.assertEqual(names['with-heading'], 'MRS. BRENDA LEV A”H')

    def test_no_name_carries_chrome(self):
        for name in self._scrape(PAGE).values():
            for junk in ('All', 'C$', 'Donate', 'View', 'goal', '%'):
                self.assertNotIn(junk, name, f'{junk!r} leaked into {name!r}')


if __name__ == '__main__':
    unittest.main()
