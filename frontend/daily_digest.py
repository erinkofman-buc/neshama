#!/usr/bin/env python3
"""
Neshama Daily Email Digest
Sends daily obituary updates to confirmed subscribers
Run via cron: 0 7 * * * /path/to/daily_digest.py
"""

import sqlite3
from datetime import datetime, timedelta
import os
import re as _re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType
from subscription_manager import EmailSubscriptionManager
import logging
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

            if obit.get('funeral_datetime'):
                detail_text = f'Funeral: {obit["funeral_datetime"]}'
                if obit.get('funeral_location'):
                    detail_text += f' &mdash; {obit["funeral_location"]}'
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">{detail_text}</p>'

            if obit.get('shiva_info'):
                shiva_preview = obit['shiva_info'][:150]
                if len(obit['shiva_info']) > 150:
                    shiva_preview += '...'
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Shiva: {shiva_preview}</p>'

            if obit.get('burial_location'):
                details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #5c534a; line-height: 1.5;">Burial: {obit["burial_location"]}</p>'

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

        # Get all new obituaries (unfiltered) to check if there's anything new
        all_obituaries = self.get_new_obituaries(hours=24)

        quiet_day = not all_obituaries

        if quiet_day:
            logging.info(" No new obituaries in the last 24 hours. Sending quiet-day digest.")
            quiet_html = self.generate_quiet_day_html()
        else:
            logging.info(f" Found {len(all_obituaries)} new obituar{'y' if len(all_obituaries) == 1 else 'ies'}")

        # Pre-fetch location-filtered obituary lists, deduplicated
        toronto_obits = deduplicate_obituaries(self.get_new_obituaries(hours=24, location='toronto')) if not quiet_day else []
        montreal_obits = deduplicate_obituaries(self.get_new_obituaries(hours=24, location='montreal')) if not quiet_day else []

        # Get daily subscribers with preferences
        daily_subscribers = self.subscription_manager.get_subscribers_by_preference(frequency='daily')
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

            # Check scraper freshness
            conn = sqlite3.connect(self.db_path, timeout=30)
            cursor = conn.cursor()
            cursor.execute('SELECT source, MAX(scraped_at) as latest FROM obituaries GROUP BY source')
            scraper_lines = []
            for row in cursor.fetchall():
                source, latest = row
                if latest:
                    try:
                        hours_ago = round((datetime.now() - datetime.fromisoformat(latest)).total_seconds() / 3600, 1)
                        status = 'OK' if hours_ago < 6 else 'STALE'
                        scraper_lines.append(f"  {source}: {hours_ago}h ago ({status})")
                    except Exception:
                        scraper_lines.append(f"  {source}: {latest}")
                else:
                    scraper_lines.append(f"  {source}: no data")
            conn.close()

            scraper_summary = '\n'.join(scraper_lines) if scraper_lines else '  No scraper data'
            error_summary = '\n'.join(f'  - {e}' for e in errors) if errors else '  None'

            plain_text = f"""Neshama Daily Health Report — {datetime.now().strftime('%B %d, %Y')}

DIGEST RESULTS
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
                    subject=f'[Neshama Health] {datetime.now().strftime("%b %d")} — {obit_count} obits, {sent} sent, {failed} failed',
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
