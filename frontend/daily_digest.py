#!/usr/bin/env python3
"""
Neshama Daily Email Digest
Sends daily obituary updates to confirmed subscribers
Run via cron: 0 7 * * * /path/to/daily_digest.py
"""

import sqlite3
from datetime import datetime, timedelta
import os
import sys as _sys
import re as _re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType
import sys as _sys
from subscription_manager import EmailSubscriptionManager

# field_hygiene and scraper_health live at the repo root next to
# database_setup.py so the scrapers can import them too. The digests run from
# frontend/, hence the hop.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
from field_hygiene import display_value
from scraper_health import (
    collect_source_health, format_health_lines, broken_sources,
)

import logging

# obituary_identity lives at the repo root next to database_setup.py, so the
# scrapers can import it too. daily_digest runs from frontend/, hence the hop.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)
from obituary_identity import announce_key
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def _normalize_name(name):
    """Normalize an obituary name for dedup comparison.
    Strips: née/born clauses, Hebrew honorifics (ז״ל), titles (Dr., Rabbi, etc.),
    then lowercases and collapses whitespace."""
    if not name:
        return ''
    import unicodedata as _ud
    # Strip zero-width characters (funeral homes inject these, causes false duplicates)
    n = ''.join(c for c in name if _ud.category(c) != 'Cf')
    # Remove ALL parenthesized content: nicknames "(Jerry)", née "(née Smith)", etc.
    n = _re.sub(r'\s*\([^)]*\)', '', n)
    # Remove ז״ל / ז"ל honorific specifically (not all Hebrew text)
    n = _re.sub(r'\s*\u05d6[\u05f4״"]\u05dc\s*', '', n)
    # Remove titles
    n = _re.sub(r'^(Dr\.|Rabbi|Rev\.|Cantor|Mr\.|Mrs\.|Ms\.)\s+', '', n, flags=_re.IGNORECASE)
    # Collapse whitespace, strip, lowercase
    n = _re.sub(r'\s+', ' ', n).strip().lower()
    return n


def _funeral_date(obit):
    """Extract just the date portion from funeral_datetime for grouping."""
    dt = obit.get('funeral_datetime') or ''
    # Try to find a date like "March 24" or "2026-03-24"
    m = _re.search(r'(\w+ \d{1,2})', dt)
    if m:
        return m.group(1).lower()
    m = _re.search(r'(\d{4}-\d{2}-\d{2})', dt)
    if m:
        return m.group(1)
    return ''


def _pick_best(group):
    """From a list of duplicate obituaries, pick the one with the most detail."""
    def _score(o):
        s = 0
        if o.get('funeral_datetime'):
            s += len(o['funeral_datetime'])
        if o.get('shiva_info'):
            s += len(o['shiva_info'])
        if o.get('burial_location'):
            s += 10
        if o.get('livestream_available'):
            s += 5
        if o.get('hebrew_name'):
            s += 10
        if o.get('funeral_location'):
            s += 10
        return s
    return max(group, key=_score)


def deduplicate_obituaries(obituaries):
    """Remove duplicate obituaries conservatively.
    Only merges when normalized names match AND both have the same non-empty funeral date.
    When in doubt, keeps both entries — a duplicate is better than a missing person."""
    if not obituaries:
        return obituaries

    # Phase 1: Group by (normalized_name, funeral_date)
    groups = {}
    for obit in obituaries:
        key = (_normalize_name(obit.get('deceased_name', '')), _funeral_date(obit))
        groups.setdefault(key, []).append(obit)

    # Phase 2: Merge groups with same name+source where one has no date
    # (handles preliminary "details to follow" entries superseded by full obituaries)
    by_name_source = {}
    for key, group in groups.items():
        norm_name = key[0]
        if not norm_name:
            continue
        for obit in group:
            ns_key = (norm_name, obit.get('source', ''))
            by_name_source.setdefault(ns_key, []).append((key, obit))

    merged_away = set()  # keys to skip because they were merged into another group
    for ns_key, entries in by_name_source.items():
        if len(entries) < 2:
            continue
        # Check if we have both dated and undated entries for same name+source
        dated = [(k, o) for k, o in entries if k[1]]
        undated = [(k, o) for k, o in entries if not k[1]]
        if dated and undated:
            # Merge undated into the dated group (preliminary → full)
            target_key = dated[0][0]
            for uk, uo in undated:
                groups.setdefault(target_key, []).append(uo)
                if uk in groups and uo in groups[uk]:
                    groups[uk].remove(uo)
                    if not groups[uk]:
                        merged_away.add(uk)
                logging.info(f"[Dedup] Merged preliminary entry for '{ns_key[0]}' ({ns_key[1]}) into dated group")

    result = []
    for key, group in groups.items():
        if key in merged_away:
            continue
        norm_name = key[0]
        if len(group) == 1 or not norm_name:
            result.extend(group)
        else:
            best = _pick_best(group)
            result.append(best)
            if len(group) > 1:
                dupes = [o.get('deceased_name', '?') + ' (' + o.get('source', '?') + ')' for o in group if o is not best]
                logging.info(f"[Dedup] Merged {len(group)} entries for '{norm_name}': kept {best.get('source', '?')}, dropped {dupes}")

    return result


def _git_sha():
    """Best-effort git commit of the running code, host-agnostic.

    The point is that the phantom is very likely NOT on Render (Erin's dashboard
    shows one service), so RENDER_GIT_COMMIT will be empty on it. Reading the SHA
    from the deployed .git directory works on any host and needs no git binary,
    so whatever the phantom is running on, its health report still names the
    commit it is running.
    """
    for var in ('RENDER_GIT_COMMIT', 'RAILWAY_GIT_COMMIT_SHA',
                'SOURCE_VERSION', 'HEROKU_SLUG_COMMIT', 'GIT_COMMIT', 'GIT_SHA'):
        val = os.environ.get(var)
        if val:
            return val[:12]
    # Fall back to reading .git directly (no subprocess, no git binary needed).
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        head_path = os.path.join(repo_root, '.git', 'HEAD')
        with open(head_path, 'r') as fh:
            head = fh.read().strip()
        if head.startswith('ref:'):
            ref = head.split(' ', 1)[1].strip()
            with open(os.path.join(repo_root, '.git', ref)) as rf:
                return rf.read().strip()[:12]
        return head[:12]        # detached HEAD: HEAD holds the SHA directly
    except Exception:
        return '(unknown)'


def instance_fingerprint():
    """Identify which deployment this process is, for the health report.

    Two [Neshama Health] reports arrived five seconds apart on Aug 17, Aug 24 and
    Aug 31 2026, and nothing in either email said which process sent it. That
    ambiguity is what made the second one hard to place. Every health report now
    names its own deployment: host, service id, git SHA, DB path.

    Render populates the RENDER_* variables; other hosts populate their own, and
    the git SHA falls back to reading .git so it is present no matter the host.
    """
    import socket

    # Service id: whichever platform's identifier is set. This is the field most
    # likely to name the phantom outright.
    service = None
    for var in ('RENDER_SERVICE_NAME', 'RENDER_SERVICE_ID',
                'RAILWAY_SERVICE_NAME', 'FLY_APP_NAME', 'HEROKU_APP_NAME',
                'WEBSITE_SITE_NAME', 'K_SERVICE'):
        if os.environ.get(var):
            service = f"{var}={os.environ[var][:24]}"
            break

    parts = [
        f"host={socket.gethostname()}",
        f"service={service if service else '(none set - not a known PaaS)'}",
        f"sha={_git_sha()}",
        f"db={os.environ.get('DATABASE_PATH', '(default relative path)')}",
    ]
    # Keep the finer-grained Render fields when present; harmless elsewhere.
    for label, var in (('branch', 'RENDER_GIT_BRANCH'),
                       ('instance', 'RENDER_INSTANCE_ID')):
        value = os.environ.get(var)
        if value:
            parts.append(f"{label}={value[:12]}")
    return ' '.join(parts)


def _html_to_plain(html):
    """Convert HTML email to readable plain text"""
    text = html
    text = _re.sub(r'<br\s*/?>','\n', text)
    text = _re.sub(r'</p>', '\n\n', text)
    text = _re.sub(r'</tr>', '\n', text)
    text = _re.sub(r'</td>', ' ', text)
    text = _re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'\2 (\1)', text)
    text = _re.sub(r'<[^>]+>', '', text)
    text = _re.sub(r'&middot;', '-', text)
    text = _re.sub(r'&mdash;|&ndash;', '-', text)
    text = _re.sub(r'&[a-z]+;', '', text)
    text = _re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

class DailyDigestSender:
    def __init__(self, db_path='neshama.db', sendgrid_api_key=None):
        """Initialize daily digest sender"""
        self.db_path = db_path
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get('SENDGRID_API_KEY')
        self.from_email = 'updates@neshama.ca'
        self.from_name = 'Neshama'
        self.subscription_manager = EmailSubscriptionManager(db_path, sendgrid_api_key)
        
    # Map location values to funeral home source names
    LOCATION_SOURCES = {
        'toronto': ["Steeles Memorial Chapel", "Benjamin's Park Memorial Chapel", "Misaskim"],
        'montreal': ["Paperman & Sons"],
    }

    def get_new_obituaries(self, hours=24, location=None):
        """Get obituaries first seen in the last N hours, optionally filtered by location.
        Uses COALESCE(first_seen, last_updated) so name corrections by funeral homes
        don't cause repeats, with fallback for records missing first_seen."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        if location and location in self.LOCATION_SOURCES:
            sources = self.LOCATION_SOURCES[location]
            placeholders = ','.join('?' for _ in sources)
            cursor.execute(f'''
                SELECT * FROM obituaries
                WHERE COALESCE(first_seen, last_updated) >= ?
                AND source IN ({placeholders})
                AND COALESCE(hidden, 0) = 0
                ORDER BY COALESCE(first_seen, last_updated) DESC
            ''', [cutoff_time] + sources)
        else:
            cursor.execute('''
                SELECT * FROM obituaries
                WHERE COALESCE(first_seen, last_updated) >= ?
                AND COALESCE(hidden, 0) = 0
                ORDER BY COALESCE(first_seen, last_updated) DESC
            ''', (cutoff_time,))

        obituaries = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return obituaries

    # ── digest sent-log ───────────────────────────────────────────────────
    # Independent of the identity key. Even if a key bug ever mints a second
    # row for someone, the sent-log refuses to announce that person twice,
    # because it is keyed on the funeral home's own id, not on our row id.

    def announced_keys(self, digest_type='daily'):
        """Every announce_key this digest type has already sent."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT announce_key FROM announced_obituaries WHERE digest_type = ?',
                (digest_type,)
            )
            return {row[0] for row in cursor.fetchall()}
        except sqlite3.OperationalError as e:
            # Table not created yet (first boot after deploy). Announce normally.
            logging.info(f"[SentLog] No sent-log yet ({e}) - proceeding without it")
            return set()
        finally:
            conn.close()

    def filter_unannounced(self, obituaries, announced):
        """Drop obituaries already announced, loudly enough to be greppable."""
        kept = []
        for obit in obituaries:
            key = announce_key(
                obit.get('source'), obit.get('source_url'), obit.get('id')
            )
            if key in announced:
                logging.info(
                    f"[SentLog] Suppressing repeat announcement: "
                    f"{obit.get('deceased_name')!r} ({key})"
                )
                continue
            kept.append(obit)
        return kept

    def record_announced(self, obituaries, digest_type='daily'):
        """Mark obituaries as announced. INSERT OR IGNORE - idempotent."""
        if not obituaries:
            return 0
        conn = sqlite3.connect(self.db_path, timeout=30)
        now = datetime.now().isoformat()
        written = 0
        try:
            cursor = conn.cursor()
            for obit in obituaries:
                key = announce_key(
                    obit.get('source'), obit.get('source_url'), obit.get('id')
                )
                cursor.execute(
                    'INSERT OR IGNORE INTO announced_obituaries '
                    '(announce_key, digest_type, obituary_id, announced_at) '
                    'VALUES (?, ?, ?, ?)',
                    (key, digest_type, obit.get('id'), now)
                )
                written += cursor.rowcount
            conn.commit()
        except sqlite3.OperationalError as e:
            logging.error(f"[SentLog] Could not record announcements: {e}")
        finally:
            conn.close()
        return written
    
    def generate_quiet_day_html(self):
        """Generate HTML email for days with no new obituaries"""
        html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width: 560px; width: 100%;">

    <!-- Header -->
    <tr><td style="padding-bottom: 24px; border-bottom: 1px solid #e8e0d8;">
        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; color: #3E2723; letter-spacing: 0.02em;">Neshama</span>
    </td></tr>

    <!-- Greeting -->
    <tr><td style="padding: 28px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0 0 6px 0;">Good morning, {datetime.now().strftime('%B %d')}.</p>
        <p style="margin: 0 0 16px 0;">No new obituary notices were posted in the last 24 hours.</p>
        <p style="margin: 0;">We are here when the community needs us.</p>
    </td></tr>

    <!-- Footer links -->
    <tr><td style="padding: 28px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #5c534a; line-height: 1.7;">
        <p style="margin: 0 0 4px 0;"><a href="https://neshama.ca" style="color: #3E2723; text-decoration: underline;">Visit Neshama</a></p>
        <p style="margin: 0;"><a href="https://neshama.ca/what-to-bring-to-a-shiva" style="color: #3E2723; text-decoration: underline;">Visiting a shiva? See what to bring</a></p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; margin-top: 12px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0 0 6px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;"><a href="{{{{unsubscribe_url}}}}" style="color: #9e9488;">Unsubscribe</a> &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">Contact us</a></p>
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''
        return html

    def generate_email_html(self, obituaries):
        """Generate HTML email content"""
        if not obituaries:
            return None

        count = len(obituaries)

        # Build obituary rows
        obit_rows = ''
        for obit in obituaries:
            # Name line
            name = obit['deceased_name']
            if obit.get('hebrew_name'):
                name += ' \u05d6\u05f4\u05dc'

            # Details
            details = ''
            if obit.get('hebrew_name'):
                details += f'<p style="margin: 0 0 6px 0; font-size: 15px; color: #9e9488; direction: rtl; text-align: left;">{obit["hebrew_name"]}</p>'

            # Every value below goes through display_value(), which returns None
            # for a section label, an empty non-answer, or a value that collapses
            # to nothing once duplicated fragments are removed. Omitting a line
            # always beats printing junk: a missing "Shiva:" line reads as "not
            # announced yet", which is true, whereas "Shiva: Shiva Location"
            # reads as a broken website in a bereavement email.
            funeral_when = display_value(obit.get('funeral_datetime'))
            funeral_where = display_value(obit.get('funeral_location'))
            if funeral_when:
                detail_text = f'Funeral: {funeral_when}'
                if funeral_where:
                    detail_text += f' &middot; {funeral_where}'
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">{detail_text}</p>'

            shiva_value = display_value(obit.get('shiva_info'))
            if shiva_value:
                shiva_preview = shiva_value[:150]
                if len(shiva_value) > 150:
                    shiva_preview += '...'
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Shiva: {shiva_preview}</p>'
            elif obit.get('shiva_private'):
                details += '<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Shiva: private</p>'

            burial_value = display_value(obit.get('burial_location'))
            if burial_value:
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Burial: {burial_value}</p>'

            if obit.get('livestream_available'):
                details += '<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Livestream available</p>'

            # Source line
            source = obit.get('source', '')

            obit_rows += f'''
    <tr><td style="padding: 24px 0; border-bottom: 1px solid #e8e0d8;">
        <p style="margin: 0 0 4px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 19px; color: #3E2723;">{name}</p>
        <p style="margin: 0 0 10px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488;">{source}</p>
        {details}
        <p style="margin: 10px 0 0 0;"><a href="{obit['condolence_url']}" target="_blank" rel="noopener noreferrer" style="font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #3E2723; text-decoration: underline;">Read full obituary</a></p>
    </td></tr>'''

        html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #ffffff; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width: 560px; width: 100%;">

    <!-- Header -->
    <tr><td style="padding-bottom: 24px; border-bottom: 1px solid #e8e0d8;">
        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; color: #3E2723; letter-spacing: 0.02em;">Neshama</span>
    </td></tr>

    <!-- Greeting -->
    <tr><td style="padding: 28px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0 0 6px 0;">Good morning, {datetime.now().strftime('%B %d')}.</p>
        <p style="margin: 0;">{count} new obituar{'y was' if count == 1 else 'ies were'} posted in the last 24 hours.</p>
    </td></tr>

    <!-- Obituaries -->
    {obit_rows}

    <!-- Footer links -->
    <tr><td style="padding: 28px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #5c534a; line-height: 1.7;">
        <p style="margin: 0 0 4px 0;"><a href="https://neshama.ca" style="color: #3E2723; text-decoration: underline;">View all on Neshama</a></p>
        <p style="margin: 0;"><a href="https://neshama.ca/what-to-bring-to-a-shiva" style="color: #3E2723; text-decoration: underline;">Visiting a shiva? See what to bring</a></p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; margin-top: 12px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0 0 6px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;"><a href="{{{{unsubscribe_url}}}}" style="color: #9e9488;">Unsubscribe</a> &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">Contact us</a></p>
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

        return html
    
    def send_digest_to_subscriber(self, email, unsubscribe_token, html_content, locations=None, obit_count=None):
        """Send digest email to a single subscriber"""
        if not self.sendgrid_api_key:
            logging.error(f"[DailyDigest] CANNOT send to {email} — no SendGrid API key (TEST MODE)")
            return {'success': False, 'error': 'No SendGrid API key', 'test_mode': True}

        # Replace unsubscribe URL
        unsubscribe_url = f"https://neshama.ca/unsubscribe/{unsubscribe_token}"
        html_with_unsubscribe = html_content.replace('{{unsubscribe_url}}', unsubscribe_url)

        # Location-aware, action-signaling subject line.
        # Research finding: count-led subjects beat date-only. "4 obituaries today" reads as
        # information; "Today in the Jewish community — April 28" reads as filler.
        # Em dash removed (brand voice). Middle dot is a clean separator, not a dash.
        loc_list = [l.strip() for l in (locations or 'toronto,montreal').split(',')]
        if loc_list == ['toronto']:
            community = 'the Toronto Jewish community'
        elif loc_list == ['montreal']:
            community = 'the Montreal Jewish community'
        else:
            community = 'the Jewish community'

        if obit_count is None or obit_count == 0:
            subject = f'Quiet day · {community}'
        elif obit_count == 1:
            subject = f'1 obituary today · {community}'
        else:
            subject = f'{obit_count} obituaries today · {community}'

        try:
            plain_text = _html_to_plain(html_with_unsubscribe)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject=subject,
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_with_unsubscribe)
            )

            # Add unsubscribe headers for email clients (RFC 8058)
            from sendgrid.helpers.mail import Header
            message.header = Header('List-Unsubscribe', f'<{unsubscribe_url}>')
            message.header = Header('List-Unsubscribe-Post', 'List-Unsubscribe=One-Click')

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            return {'success': True, 'status_code': response.status_code}
            
        except Exception as e:
            logging.error(f" Failed to send to {email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_daily_digest(self):
        """Send daily digest to daily-frequency subscribers, filtered by location"""
        logging.info(f"\n{'='*70}")
        logging.info(f" NESHAMA DAILY DIGEST")
        logging.info(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*70}\n")

        # Get all new obituaries (unfiltered) to check if there's anything new.
        # The sent-log filter runs here so a person announced yesterday cannot
        # reappear today, whatever happened to their row in between.
        announced = self.announced_keys('daily')
        all_obituaries = self.filter_unannounced(
            self.get_new_obituaries(hours=24), announced
        )

        quiet_day = not all_obituaries

        if quiet_day:
            logging.info(" No new obituaries in the last 24 hours. Sending quiet-day digest.")
            quiet_html = self.generate_quiet_day_html()
        else:
            logging.info(f" Found {len(all_obituaries)} new obituar{'y' if len(all_obituaries) == 1 else 'ies'}")

        # Pre-fetch location-filtered obituary lists, deduplicated
        toronto_obits = deduplicate_obituaries(self.filter_unannounced(
            self.get_new_obituaries(hours=24, location='toronto'), announced
        )) if not quiet_day else []
        montreal_obits = deduplicate_obituaries(self.filter_unannounced(
            self.get_new_obituaries(hours=24, location='montreal'), announced
        )) if not quiet_day else []

        # Everything actually placed in at least one subscriber's email. Recorded
        # only after a successful send, so a total SendGrid outage does not
        # permanently suppress an obituary nobody ever received.
        announced_this_run = {}

        # Get daily subscribers with preferences
        daily_subscribers = self.subscription_manager.get_subscribers_by_preference(frequency='daily')

        # GUARD: a digest run that can see obituaries but zero confirmed
        # subscribers is not a quiet day, it is a process looking at the wrong
        # database. Production has had 68 to 69 active subscribers all August.
        #
        # This is what produced the second [Neshama Health] report Erin received
        # at 11:00:00Z on Aug 17, Aug 24 and Aug 31, each reading
        # "Obituaries 5-6, Sent 0, Active 0, Pending 0, Unsubscribed 0" while
        # the real run five seconds later read 54 sent and 69 active.
        #
        # Skip the send rather than proceeding, and make the health report say so
        # loudly. Silently reporting zeros is what let this run undetected since
        # at least Aug 17.
        stats = self.subscription_manager.get_stats()
        if stats.get('active', 0) == 0:
            logging.error(
                "[DailyDigest] ABORTING: 0 confirmed subscribers in %s. "
                "This instance can see %d obituaries but has an empty subscriber "
                "table, which means it is not the production database. "
                "No digest sent. Instance: %s",
                self.db_path, len(all_obituaries), instance_fingerprint()
            )
            result = {
                'status': 'skipped_no_subscribers',
                'obituaries_count': len(all_obituaries),
                'subscribers_sent': 0,
                'subscribers_skipped': 0,
                'subscribers_failed': 0,
                'instance': instance_fingerprint(),
            }
            self._send_health_summary(result)
            return result

        logging.info(f" Sending to {len(daily_subscribers)} daily subscriber{'s' if len(daily_subscribers) != 1 else ''}\n")

        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        sent_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        for email, unsubscribe_token, frequency, locations in daily_subscribers:
            locations = locations or 'toronto,montreal'
            loc_list = [l.strip() for l in locations.split(',')]

            if quiet_day:
                html_content = quiet_html
            else:
                # Build this subscriber's obituary list
                subscriber_obits = []
                if 'toronto' in loc_list:
                    subscriber_obits.extend(toronto_obits)
                if 'montreal' in loc_list:
                    subscriber_obits.extend(montreal_obits)

                # Deduplicate by id and sort by first_seen desc
                seen = set()
                unique_obits = []
                for o in subscriber_obits:
                    if o['id'] not in seen:
                        seen.add(o['id'])
                        unique_obits.append(o)
                # Cross-location dedup: same person scraped by two funeral homes (e.g., Steeles + Misaskim)
                # has different DB ids, so id-dedup misses them. Re-run name-normalized dedup over the
                # combined toronto+montreal list to catch these. Naomi Bendon shipped twice in Apr 28 send
                # because of this gap. `deduplicate_obituaries` is conservative — keeps both when in doubt.
                unique_obits = deduplicate_obituaries(unique_obits)
                unique_obits.sort(key=lambda x: x.get('first_seen') or x.get('last_updated', ''), reverse=True)

                if not unique_obits:
                    # No obits for this subscriber's location, but other locations have obits.
                    # Send quiet-day digest instead of skipping entirely.
                    logging.info(f" {email} — no obits for {locations}, sending quiet-day digest")
                    html_content = self.generate_quiet_day_html()
                else:
                    # Generate per-subscriber email HTML
                    html_content = self.generate_email_html(unique_obits)
            # Pass obit count so subject line can use action-signal format ("4 obituaries today · ...")
            obit_count_for_subject = 0 if quiet_day else len(unique_obits)
            result = self.send_digest_to_subscriber(email, unsubscribe_token, html_content, locations, obit_count=obit_count_for_subject)

            if result.get('success'):
                sent_count += 1
                if quiet_day:
                    logging.info(f" {email} (quiet day)")
                else:
                    logging.info(f" {email} ({len(unique_obits)} obits)")
                    for _o in unique_obits:
                        announced_this_run[_o['id']] = _o
                cursor.execute('''
                    UPDATE subscribers
                    SET last_email_sent = ?
                    WHERE email = ?
                ''', (datetime.now().isoformat(), email))
            else:
                failed_count += 1
                error_msg = result.get('error', 'Unknown error')
                errors.append(f"{email}: {error_msg}")
                logging.error(f" {email} — {error_msg}")

        conn.commit()
        conn.close()

        recorded = self.record_announced(list(announced_this_run.values()), 'daily')
        if recorded:
            logging.info(f"[SentLog] Recorded {recorded} newly-announced obituaries")

        logging.info(f"\n{'='*70}")
        logging.info(f" SUMMARY")
        logging.info(f"{'='*70}")
        logging.info(f" Obituaries: {len(all_obituaries)}")
        logging.info(f" Sent: {sent_count}")
        logging.info(f" Skipped (no matching obits): {skipped_count}")
        logging.error(f" Failed: {failed_count}")
        logging.info(f" Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"{'='*70}\n")

        result = {
            'status': 'success',
            'obituaries_count': len(all_obituaries),
            'subscribers_sent': sent_count,
            'subscribers_skipped': skipped_count,
            'subscribers_failed': failed_count
        }
        if errors:
            result['errors'] = errors

        # Send health summary to contact@neshama.ca
        self._send_health_summary(result)

        return result

    def _send_health_summary(self, digest_result):
        """Send daily health report to contact@neshama.ca after digest completes."""
        if not self.sendgrid_api_key:
            logging.info("[DailyDigest] Skipping health summary — no SendGrid key")
            return

        try:
            # Gather stats
            stats = self.subscription_manager.get_stats()
            obit_count = digest_result.get('obituaries_count', 0)
            sent = digest_result.get('subscribers_sent', 0)
            failed = digest_result.get('subscribers_failed', 0)
            skipped = digest_result.get('subscribers_skipped', 0)
            errors = digest_result.get('errors', [])

            # Scraper freshness. See scraper_health.py for why this changed:
            # the old query was MAX(obituaries.scraped_at), which answers "when
            # did we last store a NEW obituary", not "is the scraper working".
            # It reported all four sources STALE every week, so a genuine 27-day
            # Benjamin's outage was indistinguishable from three quiet weekends.
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                health = collect_source_health(conn)
            finally:
                conn.close()

            scraper_summary = format_health_lines(health)
            broken = broken_sources(health)
            error_summary = '\n'.join(f'  - {e}' for e in errors) if errors else '  None'

            # Two independent alarms, both of which belong at the top and in
            # the subject rather than buried in a block a reader has learned to
            # skim. They can fire together.
            banner = ''
            subject_prefix = ''

            if stats['active'] == 0:
                banner += (
                    "*** NO CONFIRMED SUBSCRIBERS IN THIS DATABASE ***\n"
                    "The digest was NOT sent. This process can see obituaries but\n"
                    "its subscriber table is empty, so it is not reading the\n"
                    "production database. Expect production to report ~69 active.\n"
                    "If a second Render service (staging, a preview environment, an\n"
                    "old worker) is running with the production SendGrid key, this\n"
                    "is it. Check the INSTANCE line below.\n\n"
                )
                subject_prefix += 'NO SUBSCRIBERS - '

            if broken:
                banner += (
                    '*** SCRAPER NOT SUCCEEDING: ' + ', '.join(broken) + ' ***\n'
                    'These sources have not completed a successful scrape within\n'
                    'three cron intervals. This is a real failure, not a quiet week.\n\n'
                )
                subject_prefix += f'SCRAPER DOWN ({len(broken)}) - '

            plain_text = f"""Neshama Daily Health Report - {datetime.now().strftime('%B %d, %Y')}

{banner}INSTANCE
  {instance_fingerprint()}

DIGEST RESULTS
  Status: {digest_result.get('status', 'success')}
  Obituaries: {obit_count}
  Sent: {sent}
  Skipped: {skipped}
  Failed: {failed}

SUBSCRIBERS
  Active: {stats['active']}
  Pending: {stats['pending']}
  Unsubscribed: {stats['unsubscribed']}

SCRAPER FRESHNESS
{scraper_summary}

ERRORS
{error_summary}
"""

            # Only send health summary on Mondays (reduce inbox noise)
            if datetime.now().weekday() == 0:  # Monday
                message = Mail(
                    from_email=Email(self.from_email, self.from_name),
                    to_emails=To('contact@neshama.ca'),
                    subject=(f'[Neshama Health] {subject_prefix}'
                             f'{datetime.now().strftime("%b %d")} - {obit_count} obits, '
                             f'{sent} sent, {failed} failed'),
                    plain_text_content=Content(MimeType.text, plain_text)
                )

                sg = SendGridAPIClient(self.sendgrid_api_key)
                sg.send(message)
                logging.info("[DailyDigest] Weekly health summary sent to contact@neshama.ca")
            else:
                logging.info(f"[DailyDigest] Health: {obit_count} obits, {sent} sent, {failed} failed (email suppressed — Monday only)")

        except Exception as e:
            logging.error(f"[DailyDigest] Failed to send health summary: {e}")

if __name__ == '__main__':
    sender = DailyDigestSender()
    result = sender.send_daily_digest()
