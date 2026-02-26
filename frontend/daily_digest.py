#!/usr/bin/env python3
"""
Neshama Daily Email Digest
Sends daily obituary updates to confirmed subscribers
Run via cron: 0 7 * * * /path/to/daily_digest.py
"""

import sqlite3
from datetime import datetime, timedelta
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from subscription_manager import EmailSubscriptionManager

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
        'toronto': ["Steeles Memorial Chapel", "Benjamin's Park Memorial Chapel"],
        'montreal': ["Paperman & Sons"],
    }

    def get_new_obituaries(self, hours=24, location=None):
        """Get obituaries posted in the last N hours, optionally filtered by location"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        if location and location in self.LOCATION_SOURCES:
            sources = self.LOCATION_SOURCES[location]
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
        <p style="margin: 10px 0 0 0;"><a href="{obit['condolence_url']}" style="font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #3E2723; text-decoration: underline;">Read full obituary</a></p>
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
    
    def send_digest_to_subscriber(self, email, unsubscribe_token, html_content, locations=None):
        """Send digest email to a single subscriber"""
        if not self.sendgrid_api_key:
            print(f"⚠️  Would send digest to {email}")
            return {'success': True, 'test_mode': True}

        # Replace unsubscribe URL
        unsubscribe_url = f"https://neshama.ca/unsubscribe/{unsubscribe_token}"
        html_with_unsubscribe = html_content.replace('{{unsubscribe_url}}', unsubscribe_url)

        # Location-aware subject line
        loc_list = [l.strip() for l in (locations or 'toronto,montreal').split(',')]
        if loc_list == ['toronto']:
            community = 'the Toronto Jewish community'
        elif loc_list == ['montreal']:
            community = 'the Montreal Jewish community'
        else:
            community = 'the Jewish community'
        subject = f'Today in {community} — {datetime.now().strftime("%B %d, %Y")}'

        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject=subject,
                html_content=Content("text/html", html_with_unsubscribe)
            )
            
            # Add unsubscribe headers for email clients (RFC 8058)
            message.add_header('List-Unsubscribe', f'<{unsubscribe_url}>')
            message.add_header('List-Unsubscribe-Post', 'List-Unsubscribe=One-Click')
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            return {'success': True, 'status_code': response.status_code}
            
        except Exception as e:
            print(f"❌ Failed to send to {email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_daily_digest(self):
        """Send daily digest to daily-frequency subscribers, filtered by location"""
        print(f"\n{'='*70}")
        print(f" NESHAMA DAILY DIGEST")
        print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        # Get all new obituaries (unfiltered) to check if there's anything new
        all_obituaries = self.get_new_obituaries(hours=24)

        if not all_obituaries:
            print("ℹ️  No new obituaries in the last 24 hours. Skipping email send.")
            print(f"\n{'='*70}\n")
            return {
                'status': 'skipped',
                'reason': 'no_new_content',
                'subscribers_count': 0
            }

        print(f"📰 Found {len(all_obituaries)} new obituar{'y' if len(all_obituaries) == 1 else 'ies'}")

        # Pre-fetch location-filtered obituary lists
        toronto_obits = self.get_new_obituaries(hours=24, location='toronto')
        montreal_obits = self.get_new_obituaries(hours=24, location='montreal')

        # Get daily subscribers with preferences
        daily_subscribers = self.subscription_manager.get_subscribers_by_preference(frequency='daily')
        print(f"📧 Sending to {len(daily_subscribers)} daily subscriber{'s' if len(daily_subscribers) != 1 else ''}\n")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for email, unsubscribe_token, frequency, locations in daily_subscribers:
            locations = locations or 'toronto,montreal'
            loc_list = [l.strip() for l in locations.split(',')]

            # Build this subscriber's obituary list
            subscriber_obits = []
            if 'toronto' in loc_list:
                subscriber_obits.extend(toronto_obits)
            if 'montreal' in loc_list:
                subscriber_obits.extend(montreal_obits)

            # Deduplicate by id and sort by last_updated desc
            seen = set()
            unique_obits = []
            for o in subscriber_obits:
                if o['id'] not in seen:
                    seen.add(o['id'])
                    unique_obits.append(o)
            unique_obits.sort(key=lambda x: x.get('last_updated', ''), reverse=True)

            if not unique_obits:
                skipped_count += 1
                print(f"  ⏭️  {email} — no obits for {locations}")
                continue

            # Generate per-subscriber email HTML
            html_content = self.generate_email_html(unique_obits)
            result = self.send_digest_to_subscriber(email, unsubscribe_token, html_content, locations)

            if result.get('success'):
                sent_count += 1
                print(f"  ✅ {email} ({len(unique_obits)} obits)")
                cursor.execute('''
                    UPDATE subscribers
                    SET last_email_sent = ?
                    WHERE email = ?
                ''', (datetime.now().isoformat(), email))
            else:
                failed_count += 1
                print(f"  ❌ {email} — {result.get('error', 'Unknown error')}")

        conn.commit()
        conn.close()

        print(f"\n{'='*70}")
        print(f" SUMMARY")
        print(f"{'='*70}")
        print(f" Obituaries: {len(all_obituaries)}")
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
    sender = DailyDigestSender()
    result = sender.send_daily_digest()
