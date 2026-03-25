#!/usr/bin/env python3
"""
Send Passover subscriber email — one-time campaign mailer.

Usage:
    python3 marketing-kit/send_passover_email.py          # dry run (no emails sent)
    python3 marketing-kit/send_passover_email.py --send   # actually send

- Fetches all confirmed, active subscribers from the database
- Uses the existing Neshama email wrapper style (warm, white, Georgia serif)
- Rate limits to 1 email per second
- Logs sent emails to marketing-kit/passover_send_log.json to avoid double-sends
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, 'neshama.db')
SEND_LOG_PATH = os.path.join(SCRIPT_DIR, 'passover_send_log.json')

# ---------------------------------------------------------------------------
# Email config
# ---------------------------------------------------------------------------
FROM_EMAIL = 'updates@neshama.ca'
FROM_NAME = 'Neshama'
SUBJECT = 'Before the first seder'


def _html_to_plain(html_str):
    """Convert HTML email to readable plain text."""
    text = html_str
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'</td>', ' ', text)
    text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', r'\2 (\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&middot;', '-', text)
    text = re.sub(r'&mdash;|&ndash;', '-', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _build_email_html(unsubscribe_url):
    """Build the Passover email HTML using the exact draft copy and the Neshama wrapper style."""
    return f"""<!DOCTYPE html>
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
    <tr><td style="padding-bottom: 32px; border-bottom: 1px solid #e8e0d8;">
        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; color: #3E2723; letter-spacing: 0.02em;">Neshama</span>
    </td></tr>

    <!-- Body -->
    <tr><td style="padding: 32px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 16px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0 0 20px 0;">Good morning.</p>

        <p style="margin: 0 0 20px 0;">Passover begins Wednesday evening. For many in our community, this is a season of warmth &mdash; family around the table, familiar melodies, food that connects us to memory.</p>

        <p style="margin: 0 0 20px 0;">For those carrying grief, the seder can feel different. An empty chair. A recipe no one else makes quite the same way. A voice missing from the songs.</p>

        <p style="margin: 0 0 20px 0;">If this Pesach feels heavier than usual &mdash; or if you know someone for whom it might &mdash; we wrote something that may help:</p>

        <!-- Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #3E2723; border-radius: 4px;">
            <a href="https://neshama.ca/first-passover-after-loss" style="display: inline-block; padding: 13px 32px; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">Your First Passover After a Loss</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 20px 0;">It is okay to hold both things at the table: the gratitude and the ache.</p>

        <p style="margin: 0;">Wishing you a meaningful Pesach.</p>

        <p style="margin: 20px 0 0 0;">&mdash; Neshama</p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0 0 6px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">contact@neshama.ca</a></p>
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;"><a href="{unsubscribe_url}" style="color: #9e9488;">Unsubscribe</a></p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def get_active_subscribers():
    """Fetch all confirmed, active subscribers with their unsubscribe tokens."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT email, unsubscribe_token
        FROM subscribers
        WHERE confirmed = TRUE
        AND unsubscribed_at IS NULL
        ORDER BY subscribed_at
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows


def load_send_log():
    """Load the send log (emails already sent) to avoid double-sends."""
    if os.path.exists(SEND_LOG_PATH):
        with open(SEND_LOG_PATH, 'r') as f:
            return json.load(f)
    return {}


def save_send_log(log):
    """Persist the send log."""
    with open(SEND_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)


def send_email(sendgrid_key, to_email, html_content):
    """Send one email via SendGrid. Returns (success, error_msg)."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

    plain_text = _html_to_plain(html_content)

    message = Mail(
        from_email=Email(FROM_EMAIL, FROM_NAME),
        to_emails=To(to_email),
        subject=SUBJECT,
        plain_text_content=Content(MimeType.text, plain_text),
        html_content=Content(MimeType.html, html_content),
    )
    sg = SendGridAPIClient(sendgrid_key)
    response = sg.send(message)
    return True, None


def main():
    parser = argparse.ArgumentParser(description='Send Passover subscriber email')
    parser.add_argument('--send', action='store_true',
                        help='Actually send emails (default is dry run)')
    args = parser.parse_args()

    dry_run = not args.send

    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN — no emails will be sent. Use --send to send.")
        logger.info("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("LIVE SEND MODE — emails will be sent!")
        logger.info("=" * 60)

    # Check SendGrid key for live sends
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    if not dry_run and not sendgrid_key:
        logger.error("SENDGRID_API_KEY not set. Aborting.")
        sys.exit(1)

    # Load subscribers
    subscribers = get_active_subscribers()
    logger.info(f"Found {len(subscribers)} active subscribers")

    if not subscribers:
        logger.info("No subscribers to email. Exiting.")
        return

    # Load send log to skip already-sent
    send_log = load_send_log()
    already_sent = set(send_log.get('sent', []))

    to_send = [(email, token) for email, token in subscribers if email not in already_sent]
    skipped = len(subscribers) - len(to_send)

    if skipped:
        logger.info(f"Skipping {skipped} already-sent subscribers")

    logger.info(f"Will send to {len(to_send)} subscribers")

    if not to_send:
        logger.info("All subscribers already emailed. Nothing to do.")
        return

    # Send loop
    sent_count = 0
    fail_count = 0

    for i, (email, unsub_token) in enumerate(to_send, 1):
        unsub_url = f"https://neshama.ca/unsubscribe/{unsub_token}" if unsub_token else "https://neshama.ca"
        html = _build_email_html(unsub_url)

        if dry_run:
            logger.info(f"[DRY RUN] [{i}/{len(to_send)}] Would send to: {email}")
            sent_count += 1
        else:
            try:
                success, err = send_email(sendgrid_key, email, html)
                logger.info(f"[SENT] [{i}/{len(to_send)}] {email}")
                sent_count += 1

                # Record in send log immediately
                if 'sent' not in send_log:
                    send_log['sent'] = []
                send_log['sent'].append(email)
                send_log[email] = {
                    'sent_at': datetime.now().isoformat(),
                    'status': 'sent'
                }
                save_send_log(send_log)

            except Exception as e:
                logger.error(f"[FAILED] [{i}/{len(to_send)}] {email}: {e}")
                fail_count += 1

            # Rate limit: 1 per second
            if i < len(to_send):
                time.sleep(1)

    # Summary
    logger.info("=" * 60)
    logger.info(f"{'DRY RUN ' if dry_run else ''}COMPLETE")
    logger.info(f"  Sent: {sent_count}")
    if fail_count:
        logger.info(f"  Failed: {fail_count}")
    if skipped:
        logger.info(f"  Skipped (already sent): {skipped}")
    logger.info(f"  Total subscribers: {len(subscribers)}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
