#!/usr/bin/env python3
"""
Scraper freshness, measured honestly.

The problem
-----------
"Freshness" was two different questions answered by one number, and the number
answered the wrong one.

The Monday health email computed:

    SELECT source, MAX(scraped_at) FROM obituaries GROUP BY source

`scraped_at` is written on INSERT and never on UPDATE, so that expression means
"when did we last store a NEW obituary from this source" - not "did the scraper
run". A funeral home with a quiet week is indistinguishable from a scraper that
has been failing for a month. The 2026-08-31 report is the proof:

    Benjamin's Park Memorial Chapel: 642.3h ago (STALE)     <- genuinely broken
    Misaskim: 28.6h ago (STALE)                             <- just quiet
    Steeles Memorial Chapel: 20.3h ago (STALE)              <- just quiet
    Paperman & Sons: 13.7h ago (STALE)                      <- just quiet

Three of those four scrapers were running perfectly. The cron runs every 20
minutes, so a 6-hour threshold on "last new obituary" flags a normal overnight
as a failure. Four STALE lines every week is how a real 27-day outage stayed
invisible: the signal was indistinguishable from the noise it sat in.

`/api/health` was already repointed at scraper_log on 2026-04-30 for exactly this
reason, but the health EMAIL never was, and the API version still has the second
half of the bug: it filters on run_time only, never on status, so a scraper that
has failed 121 times in 24 hours still reads "fresh".

The fix
-------
Report BOTH numbers and be explicit about which one means broken:

    last_successful_scrape   scraper_log, status='success'   -> drives STALE
    last_new_obituary        obituaries.MAX(scraped_at)      -> informational

A source is STALE only when it has not SUCCEEDED within roughly three cron
intervals. A source that is running fine but has published nothing is reported
as "quiet", which is not a fault and does not need Erin's attention on a Monday
morning.
"""

import os
import sqlite3
from datetime import datetime, timedelta

# The periodic scraper interval, matching api_server's SCRAPE_INTERVAL default.
DEFAULT_SCRAPE_INTERVAL_SECONDS = int(os.environ.get('SCRAPE_INTERVAL', 1200))

# Three cron intervals, with a floor so a short interval does not produce a
# hair-trigger. At the 20-minute default this is a 1-hour window, and the floor
# keeps it at 1 hour even if the interval is lowered.
STALE_MULTIPLIER = 3
MIN_STALE_WINDOW_SECONDS = 3600

TRACKED_SOURCES = (
    'Steeles Memorial Chapel',
    "Benjamin's Park Memorial Chapel",
    'Misaskim',
    'Paperman & Sons',
)


def stale_window_seconds(interval_seconds=None):
    interval = interval_seconds or DEFAULT_SCRAPE_INTERVAL_SECONDS
    return max(interval * STALE_MULTIPLIER, MIN_STALE_WINDOW_SECONDS)


def _hours_since(timestamp, now=None):
    if not timestamp:
        return None
    try:
        then = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    now = now or datetime.now()
    if then.tzinfo is not None and now.tzinfo is None:
        then = then.replace(tzinfo=None)
    return (now - then).total_seconds() / 3600.0


def collect_source_health(conn, sources=TRACKED_SOURCES, now=None,
                          interval_seconds=None, shabbat=False):
    """Return per-source health for every tracked funeral home.

    Each entry carries:
        last_successful_scrape  ISO string or None
        last_failed_scrape      ISO string or None
        last_new_obituary       ISO string or None
        hours_since_success     float or None
        hours_since_new         float or None
        stale                   True only when the SCRAPER is not succeeding
        quiet                   scraper healthy, no new obituaries lately
        last_error              the most recent error message, if failing
    """
    now = now or datetime.now()
    window_hours = stale_window_seconds(interval_seconds) / 3600.0

    successes, failures, errors, newest = {}, {}, {}, {}

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT source, MAX(run_time) FROM scraper_log "
            "WHERE status = 'success' GROUP BY source")
        successes = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            "SELECT source, MAX(run_time) FROM scraper_log "
            "WHERE status != 'success' GROUP BY source")
        failures = {row[0]: row[1] for row in cursor.fetchall()}

        # Most recent error text per source, for the report.
        cursor.execute(
            "SELECT source, error_message FROM scraper_log "
            "WHERE status != 'success' AND error_message IS NOT NULL "
            "AND id IN (SELECT MAX(id) FROM scraper_log "
            "           WHERE status != 'success' GROUP BY source)")
        errors = {row[0]: row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute(
            'SELECT source, MAX(scraped_at) FROM obituaries GROUP BY source')
        newest = {row[0]: row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        pass

    report = {}
    for source in sources:
        success_at = successes.get(source)
        hours_success = _hours_since(success_at, now)
        hours_new = _hours_since(newest.get(source), now)

        if shabbat:
            # Scrapers are paused Friday sunset to Saturday sunset by design.
            stale = False
        elif hours_success is None:
            stale = True          # never succeeded, or no log at all
        else:
            stale = hours_success > window_hours

        report[source] = {
            'last_successful_scrape': success_at,
            'last_failed_scrape': failures.get(source),
            'last_new_obituary': newest.get(source),
            'hours_since_success': (round(hours_success, 1)
                                    if hours_success is not None else None),
            'hours_since_new': (round(hours_new, 1)
                                if hours_new is not None else None),
            'stale': stale,
            'quiet': (not stale) and (hours_new is None or hours_new > 24),
            'last_error': errors.get(source),
        }
    return report


def format_health_lines(report):
    """Render the per-source block for the Monday health email.

    Deliberately verbose about WHY a source is flagged. The old one-number
    format is what let a real outage hide among three false alarms.
    """
    lines = []
    for source in sorted(report):
        entry = report[source]
        since_success = entry['hours_since_success']
        since_new = entry['hours_since_new']

        if entry['stale']:
            if since_success is None:
                status = 'BROKEN - no successful scrape on record'
            else:
                status = f'BROKEN - last successful scrape {since_success}h ago'
        elif entry['quiet']:
            status = f'ok (scraper healthy, no new obituaries for {since_new}h)'
        else:
            status = 'ok'

        lines.append(f'  {source}: {status}')

        if entry['stale']:
            if since_new is not None:
                lines.append(f'      last new obituary: {since_new}h ago')
            if entry['last_error']:
                error = ' '.join(str(entry['last_error']).split())[:160]
                lines.append(f'      last error: {error}')
    return '\n'.join(lines) if lines else '  No scraper data'


def broken_sources(report):
    return sorted(s for s, entry in report.items() if entry['stale'])


# ── bot-protection detection ──────────────────────────────────────────────────
# Benjamin's Park Memorial Chapel put its site behind a Cloudflare managed
# challenge some time around 2026-08-05. Reproduced 2026-09-02:
#
#   GET https://benjaminsparkmemorialchapel.ca/Home.aspx
#     -> HTTP 403, server: cloudflare, cf-mitigated: challenge
#        <title>Just a moment...</title>
#
# The scraper's parser is fine. It never receives HTML to parse. Detecting this
# specifically matters because "403" in a log reads like a transient error,
# whereas "the site turned on bot protection" is a decision for a human.

class BotProtectionBlocked(Exception):
    """The site served a bot-protection challenge instead of content."""


_CHALLENGE_MARKERS = (
    'just a moment',
    'checking your browser',
    'cf-browser-verification',
    'challenges.cloudflare.com',
    'enable javascript and cookies to continue',
)


def is_bot_challenge(response):
    """True when an HTTP response is a bot-protection interstitial."""
    if response is None:
        return False

    headers = getattr(response, 'headers', {}) or {}
    if headers.get('cf-mitigated') == 'challenge':
        return True

    status = getattr(response, 'status_code', None)
    if status not in (401, 403, 429, 503):
        return False

    try:
        body = (response.text or '')[:4000].lower()
    except Exception:
        return False
    return any(marker in body for marker in _CHALLENGE_MARKERS)
