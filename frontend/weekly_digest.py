#!/usr/bin/env python3
"""
Neshama Weekly Email Digest
Sends weekly obituary roundup to subscribers who chose weekly frequency.
Run via cron: 0 9 * * 0 /path/to/weekly_digest.py  (every Sunday 9 AM)
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import os
import re as _re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType
from subscription_manager import EmailSubscriptionManager


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

# Map location values to funeral home source names
LOCATION_SOURCES = {
    'toronto': ["Steeles Memorial Chapel", "Benjamin's Park Memorial Chapel"],
    'montreal': ["Paperman & Sons"],
}


class WeeklyDigestSender:
    def __init__(self, db_path='neshama.db', sendgrid_api_key=None):
        """Initialize weekly digest sender"""
        self.db_path = db_path
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get('SENDGRID_API_KEY')
        self.from_email = 'updates@neshama.ca'
        self.from_name = 'Neshama'
        self.subscription_manager = EmailSubscriptionManager(db_path, sendgrid_api_key)

    def get_weekly_obituaries(self, location=None):
        """Get obituaries posted in the last 7 days, optionally filtered by location"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_time = (datetime.now() - timedelta(days=7)).isoformat()

        if location and location in LOCATION_SOURCES:
            sources = LOCATION_SOURCES[location]
            placeholders = ','.join('?' for _ in sources)
            cursor.execute(f'''
                SELECT * FROM obituaries
                WHERE last_updated >= ?
                AND source IN ({placeholders})
                ORDER BY last_updated DESC
            ''', [cutoff_time] + sources)
        else:
            cursor.execute('''
                SELECT * FROM obituaries
                WHERE last_updated >= ?
                ORDER BY last_updated DESC
            ''', (cutoff_time,))

        obituaries = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return obituaries

    def generate_weekly_html(self, obituaries):
        """Generate HTML email content for weekly digest, grouped by day"""
        if not obituaries:
            return None

        count = len(obituaries)
        now = datetime.now()
        week_start = (now - timedelta(days=7)).strftime('%B %d')
        week_end = now.strftime('%B %d, %Y')

        # Group obituaries by day
        by_day = defaultdict(list)
        for obit in obituaries:
            try:
                updated = obit.get('last_updated', '')
                if updated:
                    day_key = updated[:10]  # YYYY-MM-DD
                    by_day[day_key].append(obit)
            except Exception:
                by_day['unknown'].append(obit)

        # Sort days descending
        sorted_days = sorted(by_day.keys(), reverse=True)

        # Build day sections
        day_sections = ''
        for day_key in sorted_days:
            day_obits = by_day[day_key]
            try:
                day_label = datetime.strptime(day_key, '%Y-%m-%d').strftime('%A, %B %d')
            except ValueError:
                day_label = day_key

            obit_rows = ''
            for obit in day_obits:
                name = obit['deceased_name']
                if obit.get('hebrew_name'):
                    name += ' \u05d6\u05f4\u05dc'

                details = ''
                if obit.get('hebrew_name'):
                    details += f'<p style="margin: 0 0 4px 0; font-size: 14px; color: #9e9488; direction: rtl; text-align: left;">{obit["hebrew_name"]}</p>'

                source = obit.get('source', '')

                obit_rows += f'''
        <tr><td style="padding: 16px 0; border-bottom: 1px solid #f0ebe5;">
            <p style="margin: 0 0 2px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 17px; color: #3E2723;">{name}</p>
            <p style="margin: 0 0 6px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 12px; color: #9e9488;">{source}</p>
            {details}
            <p style="margin: 6px 0 0 0;"><a href="{obit['condolence_url']}" style="font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #3E2723; text-decoration: underline;">Read obituary</a></p>
        </td></tr>'''

            day_sections += f'''
    <!-- Day: {day_label} -->
    <tr><td style="padding: 24px 0 8px 0;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; font-weight: 600; color: #5c534a; text-transform: uppercase; letter-spacing: 0.05em;">{day_label}</p>
    </td></tr>
    {obit_rows}'''

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
        <p style="margin: 0 0 6px 0;">This week in our community</p>
        <p style="margin: 0; font-size: 14px; color: #9e9488;">{week_start} &ndash; {week_end}</p>
        <p style="margin: 16px 0 0 0;">{count} obituar{'y was' if count == 1 else 'ies were'} posted this week.</p>
    </td></tr>

    <!-- Obituaries by day -->
    {day_sections}

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

    def send_digest_to_subscriber(self, email, unsubscribe_token, html_content, locations=None):
        """Send weekly digest email to a single subscriber"""
        if not self.sendgrid_api_key:
            print(f"  \u26a0\ufe0f  Would send weekly digest to {email}")
            return {'success': True, 'test_mode': True}

        unsubscribe_url = f"https://neshama.ca/unsubscribe/{unsubscribe_token}"
        html_with_unsubscribe = html_content.replace('{{unsubscribe_url}}', unsubscribe_url)

        now = datetime.now()
        week_start = (now - timedelta(days=7)).strftime('%b %d')
        week_end = now.strftime('%b %d, %Y')

        # Location-aware subject line
        loc_list = [l.strip() for l in (locations or 'toronto,montreal').split(',')]
        if loc_list == ['toronto']:
            community = 'the Toronto Jewish community'
        elif loc_list == ['montreal']:
            community = 'the Montreal Jewish community'
        else:
            community = 'the Jewish community'
        subject = f'This week in {community} \u2014 {week_start}\u2013{week_end}'

        try:
            plain_text = _html_to_plain(html_with_unsubscribe)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject=subject,
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_with_unsubscribe)
            )

            # RFC 8058 — required by Gmail/Yahoo for one-click unsubscribe
            message.add_header('List-Unsubscribe', f'<{unsubscribe_url}>')
            message.add_header('List-Unsubscribe-Post', 'List-Unsubscribe=One-Click')

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            return {'success': True, 'status_code': response.status_code}

        except Exception as e:
            print(f"\u274c Failed to send to {email}: {str(e)}")
            return {'success': False, 'error': str(e)}

    def send_weekly_digest(self):
        """Send weekly digest to weekly-frequency subscribers, filtered by location"""
        print(f"\n{'='*70}")
        print(f" NESHAMA WEEKLY DIGEST")
        print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        # Check if there are any obituaries this week
        all_obituaries = self.get_weekly_obituaries()

        if not all_obituaries:
            print("\u2139\ufe0f  No new obituaries in the last 7 days. Skipping email send.")
            print(f"\n{'='*70}\n")
            return {
                'status': 'skipped',
                'reason': 'no_new_content',
                'subscribers_count': 0
            }

        print(f"📰 Found {len(all_obituaries)} obituar{'y' if len(all_obituaries) == 1 else 'ies'} this week")

        # Pre-fetch location-filtered lists
        toronto_obits = self.get_weekly_obituaries(location='toronto')
        montreal_obits = self.get_weekly_obituaries(location='montreal')

        # Get weekly subscribers with preferences
        weekly_subscribers = self.subscription_manager.get_subscribers_by_preference(frequency='weekly')
        print(f"📧 Sending to {len(weekly_subscribers)} weekly subscriber{'s' if len(weekly_subscribers) != 1 else ''}\n")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for email, unsubscribe_token, frequency, locations in weekly_subscribers:
            locations = locations or 'toronto,montreal'
            loc_list = [l.strip() for l in locations.split(',')]

            # Build this subscriber's obituary list
            subscriber_obits = []
            if 'toronto' in loc_list:
                subscriber_obits.extend(toronto_obits)
            if 'montreal' in loc_list:
                subscriber_obits.extend(montreal_obits)

            # Deduplicate by id and sort
            seen = set()
            unique_obits = []
            for o in subscriber_obits:
                if o['id'] not in seen:
                    seen.add(o['id'])
                    unique_obits.append(o)
            unique_obits.sort(key=lambda x: x.get('last_updated', ''), reverse=True)

            if not unique_obits:
                skipped_count += 1
                print(f"  \u23ed\ufe0f  {email} \u2014 no obits for {locations}")
                continue

            html_content = self.generate_weekly_html(unique_obits)
            result = self.send_digest_to_subscriber(email, unsubscribe_token, html_content, locations)

            if result.get('success'):
                sent_count += 1
                print(f"  \u2705 {email} ({len(unique_obits)} obits)")
                cursor.execute('''
                    UPDATE subscribers
                    SET last_email_sent = ?
                    WHERE email = ?
                ''', (datetime.now().isoformat(), email))
            else:
                failed_count += 1
                print(f"  \u274c {email} \u2014 {result.get('error', 'Unknown error')}")

        conn.commit()
        conn.close()

        print(f"\n{'='*70}")
        print(f" SUMMARY")
        print(f"{'='*70}")
        print(f" Obituaries this week: {len(all_obituaries)}")
        print(f" Sent: {sent_count}")
        print(f" Skipped (no matching obits): {skipped_count}")
        print(f" Failed: {failed_count}")
        print(f" Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        return {
            'status': 'success',
            'obituaries_count': len(all_obituaries),
            'subscribers_sent': sent_count,
            'subscribers_skipped': skipped_count,
            'subscribers_failed': failed_count
        }


if __name__ == '__main__':
    sender = WeeklyDigestSender()
    result = sender.send_weekly_digest()
