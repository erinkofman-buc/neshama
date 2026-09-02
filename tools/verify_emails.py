#!/usr/bin/env python3
"""
Self-check for everything that reaches a subscriber's inbox.

    python3 tools/verify_emails.py            # tests + render + scan
    python3 tools/verify_emails.py --open      # also open the sample in a browser
    python3 tools/verify_emails.py --quiet     # verdict only

Run this before merging anything that touches the digest path.

Why it exists
-------------
Four separate defects reached real inboxes in August 2026 and none of them were
caught before Erin read them:

  * David Wayne De Leon announced as new in both the Aug 27 and Aug 28 digests
  * "Shiva: Shiva Location" in 281 rows, "Burial: Dawes Road Cemetery" in 348
  * "Shiva: Address: Shiva details to follow; Shiva details to follow"
  * Two [Neshama Health] reports five seconds apart, one reading all zeros

Everything here runs offline against fixtures. It never touches production, never
sends mail, and needs no SendGrid key.

Exit code is 0 only when the tests pass AND the rendered sample is clean.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import webbrowser

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, 'frontend'))

# Test files that cover the email path. Missing files are skipped rather than
# failed, so this command is useful before all four sprint branches have landed.
DIGEST_TEST_FILES = [
    'tests/test_dedup_key.py',
    'tests/test_digest_placeholders.py',
    'tests/test_digest_subscriber_guard.py',
    'tests/test_scraper_freshness.py',
    'tests/test_email_queue.py',
]

# Strings that must never appear in a rendered digest, as a reader would see
# them. Add to this list whenever a new junk pattern is found in a real email.
FORBIDDEN = [
    'Shiva: Shiva Location',
    'Shiva: Shiva Details',
    'Shiva: Shiva Information',
    'Shiva: Address: Shiva details to follow',
    'Shiva: details to follow',
    'Shiva: Details to follow',
    'Shiva: TBD',
    'Shiva: TBA',
    'Shiva: N/A',
    'Shiva: None',
    'Burial: Burial Location',
    'Burial: Cemetery',
    'Burial: TBD',
    'Funeral: Funeral Location',
    'details to follow; Shiva details to follow',
    '{{unsubscribe_url}}',      # template variable that failed to substitute
    'None',                     # a bare Python None rendered into the email
]

# One fixture per defect that has actually shipped, plus a clean control.
FIXTURES = [
    {
        'id': 'de-leon',
        'source': 'Steeles Memorial Chapel',
        'source_url': 'https://steelesmemorialchapel.com/condolence/david-wayne-de-leon/',
        'condolence_url': 'https://steelesmemorialchapel.com/condolence/david-wayne-de-leon/',
        'deceased_name': 'David Wayne De Leon',
        'shiva_info': 'Shiva Location',
        'burial_location': 'Dawes Road Cemetery',
        'livestream_available': 1,
    },
    {
        'id': 'oppenheimer',
        'source': 'Steeles Memorial Chapel',
        'source_url': 'https://steelesmemorialchapel.com/condolence/j-oppenheimer/',
        'condolence_url': 'https://steelesmemorialchapel.com/condolence/j-oppenheimer/',
        'deceased_name': 'Jacqueline Myrna Oppenheimer',
        'shiva_info': 'Shiva Details',
        'burial_location': 'Dawes Road Cemetery',
    },
    {
        'id': 'bigman',
        'source': 'Paperman & Sons',
        'source_url': 'https://www.paperman.com/funerals/Norma-Bigman-ABCD1234',
        'condolence_url': 'https://www.paperman.com/funerals/Norma-Bigman-ABCD1234',
        'deceased_name': 'Norma Bigman (nee Manhaim)',
        'funeral_datetime': 'Tuesday, September 1 at 11:00AM',
        'funeral_location': 'Chapel Service',
        'shiva_info': 'Address: Shiva details to follow; Shiva details to follow',
    },
    {
        'id': 'sweep',
        'source': 'Misaskim',
        'source_url': 'https://misaskim.ca/shiva-listings/placeholder-sweep/',
        'condolence_url': 'https://misaskim.ca/shiva-listings/placeholder-sweep/',
        'deceased_name': 'Placeholder Sweep',
        'funeral_datetime': 'Wednesday, September 2 at 1:00PM',
        'funeral_location': 'Funeral Location',
        'shiva_info': 'TBD',
        'burial_location': 'Cemetery',
    },
    {
        'id': 'clean-control',
        'source': 'Paperman & Sons',
        'source_url': 'https://www.paperman.com/funerals/Sandra-Dubrofsky-998C37A6',
        'condolence_url': 'https://www.paperman.com/funerals/Sandra-Dubrofsky-998C37A6',
        'deceased_name': 'Sandra Dubrofsky (nee Cherry)',
        'funeral_datetime': 'Thursday, September 3 at 11:00AM',
        'funeral_location': 'Chapel Service',
        'burial_location': 'Kehal Israel Memorial Park',
        'shiva_info': ('Shiva hours: Thursday, following burial, until 4:00 p.m. '
                       'and 7:00 to 9:00 p.m.'),
        'livestream_available': 1,
    },
]

# Things that MUST survive rendering. A suppression bug that hides real detail
# is as bad as a placeholder that leaks.
REQUIRED = [
    'David Wayne De Leon',
    'Sandra Dubrofsky',
    'Kehal Israel Memorial Park',
    'Thursday, September 3 at 11:00AM',
    'Shiva hours: Thursday',
    'Read full obituary',
]


def _c(text, colour):
    if not sys.stdout.isatty():
        return text
    return {'red': '\033[31m', 'green': '\033[32m',
            'yellow': '\033[33m', 'bold': '\033[1m'}[colour] + text + '\033[0m'


def run_tests(quiet=False):
    present = [f for f in DIGEST_TEST_FILES
               if os.path.exists(os.path.join(REPO_ROOT, f))]
    missing = [f for f in DIGEST_TEST_FILES if f not in present]

    print(_c('== digest test suite ==', 'bold'))
    for f in missing:
        print(f'   skipped (not on this branch): {f}')
    if not present:
        print(_c('   no digest tests found', 'yellow'))
        return True

    result = subprocess.run(
        [sys.executable, '-m', 'pytest', *present, '-q',
         '--no-header', '-p', 'no:cacheprovider'],
        cwd=REPO_ROOT, capture_output=True, text=True)
    tail = [ln for ln in result.stdout.strip().split('\n') if ln.strip()]
    if quiet:
        print('   ' + (tail[-1] if tail else '(no output)'))
    else:
        for line in tail[-14:]:
            print('   ' + line)
    ok = result.returncode == 0
    print('   ' + (_c('PASS', 'green') if ok else _c('FAIL', 'red')))
    return ok


def render_sample():
    """Render a digest from the fixtures above. Returns (html, plain)."""
    from daily_digest import DailyDigestSender, _html_to_plain
    sender = DailyDigestSender.__new__(DailyDigestSender)   # no DB, no SendGrid
    html = sender.generate_email_html(FIXTURES)
    if not html:
        raise SystemExit('generate_email_html returned nothing')
    html = html.replace('{{unsubscribe_url}}',
                        'https://neshama.ca/unsubscribe/SAMPLE')
    return html, _html_to_plain(html)


def scan(html, plain):
    print(_c('== rendered sample scan ==', 'bold'))
    problems = []

    for needle in FORBIDDEN:
        for label, body in (('html', html), ('text', plain)):
            if needle in body:
                problems.append(f'placeholder leaked into {label}: {needle!r}')

    for needle in REQUIRED:
        if needle not in html:
            problems.append(f'real content missing from html: {needle!r}')

    if problems:
        for p in problems:
            print('   ' + _c('FAIL ', 'red') + p)
    else:
        print('   ' + _c('PASS', 'green') +
              f'  {len(FORBIDDEN)} junk patterns absent, '
              f'{len(REQUIRED)} real values present')
    return not problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--open', action='store_true',
                    help='open the rendered sample in a browser')
    ap.add_argument('--quiet', action='store_true', help='verdict only')
    args = ap.parse_args()

    tests_ok = run_tests(quiet=args.quiet)
    print()

    html, plain = render_sample()
    out = os.path.join(tempfile.gettempdir(), 'neshama-sample-digest.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)

    render_ok = scan(html, plain)
    print(f'\n   sample written to {out}')
    if args.open:
        webbrowser.open('file://' + out)

    if not args.quiet:
        print(_c('\n== plain-text alternative, as a reader sees it ==', 'bold'))
        for line in plain.split('\n')[:30]:
            print('   ' + line)

    ok = tests_ok and render_ok
    print()
    print(_c('VERIFY-EMAILS: PASS', 'green') if ok
          else _c('VERIFY-EMAILS: FAIL - do not merge', 'red'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
