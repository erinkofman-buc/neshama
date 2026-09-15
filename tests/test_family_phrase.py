#!/usr/bin/env python3
"""
family_phrase(): the signup confirmation must never read "for the The Gorelik
Family family". Organizers type the family name themselves and most type it
with "The ... Family" already in it (live case: "The Gorelik Family",
2026-09-15). Bare surnames still get wrapped.

Run:  python3 -m pytest tests/test_family_phrase.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'frontend'))

from api_server import family_phrase  # noqa: E402


class FamilyPhrase(unittest.TestCase):
    def test_live_case_is_not_doubled(self):
        self.assertEqual(family_phrase('The Gorelik Family'), 'The Gorelik Family')

    def test_bare_surname_is_wrapped(self):
        self.assertEqual(family_phrase('Gorelik'), 'the Gorelik family')

    def test_leading_the_on_bare_surname(self):
        self.assertEqual(family_phrase('The Gorelik'), 'the Gorelik family')

    def test_lowercase_family_kept_as_typed(self):
        self.assertEqual(family_phrase('gorelik family'), 'the gorelik family')

    def test_hyphenated_name(self):
        self.assertEqual(family_phrase('The Cohen-Levy Family'), 'The Cohen-Levy Family')

    def test_family_inside_another_word_is_not_the_word(self):
        self.assertEqual(family_phrase('Famille Cohen'), 'the Famille Cohen family')

    def test_empty_and_placeholder(self):
        for v in ('', None, '   ', 'Family', 'the family', 'The Family'):
            self.assertEqual(family_phrase(v), 'the family', repr(v))


if __name__ == '__main__':
    unittest.main()
