#!/usr/bin/env python3
"""
Neshama Monthly Vendor Performance Report
Sends each vendor a summary of their profile views, website clicks, and quote requests.
Run via cron: 0 9 1 * * python3 /path/to/vendor_report.py
"""

import sqlite3
import os
import re as _re
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'neshama.db'))
FROM_EMAIL = 'updates@neshama.ca'
FROM_NAME = 'Neshama'


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


def get_vendor_stats(db_path=None):
    """Get 30-day stats for each vendor that has an email"""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=30)).isoformat()

    # Get vendors with email addresses
    cursor.execute("SELECT id, name, slug, email FROM vendors WHERE email IS NOT NULL AND email != ''")
    vendors = [dict(row) for row in cursor.fetchall()]

    results = []
    for v in vendors:
        slug = v['slug']
        vendor_id = v['id']

        # Views
        views = 0
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM vendor_views WHERE vendor_slug = ? AND created_at >= ?",
                (slug, cutoff)
            )
            views = cursor.fetchone()[0]
        except Exception:
            pass

        # Clicks
        clicks = 0
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM vendor_clicks WHERE vendor_slug = ? AND created_at >= ?",
                (slug, cutoff)
            )
            clicks = cursor.fetchone()[0]
        except Exception:
            pass

        # Leads (inquiries)
        leads = 0
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM vendor_leads WHERE vendor_id = ? AND created_at >= ?",
                (vendor_id, cutoff)
            )
            leads = cursor.fetchone()[0]
        except Exception:
            pass

        # Only include vendors with at least 1 view
        if views > 0:
            results.append({
                'name': v['name'],
                'email': v['email'],
                'views': views,
                'clicks': clicks,
                'leads': leads,
            })

    conn.close()
    return results


def generate_report_html(vendor_name, views, clicks, leads):
    """Generate monthly report email HTML for a vendor"""
    def stat_box(label, value):
        return f'''<td align="center" style="padding: 16px 12px; width: 33%;">
            <p style="margin: 0 0 4px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 28px; font-weight: 700; color: #3E2723;">{value}</p>
            <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; text-transform: uppercase; letter-spacing: 0.05em;">{label}</p>
        </td>'''

    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; background-color: #ffffff; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="500" cellpadding="0" cellspacing="0" style="max-width: 500px; width: 100%;">

    <tr><td style="padding-bottom: 20px; border-bottom: 1px solid #e8e0d8;">
        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; color: #3E2723; letter-spacing: 0.02em;">Neshama</span>
    </td></tr>

    <tr><td style="padding: 24px 0 8px 0;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 20px; color: #D2691E; font-weight: 600;">Your monthly listing update</p>
    </td></tr>

    <tr><td style="padding: 8px 0 24px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0;">Hi {vendor_name},</p>
        <p style="margin: 12px 0 0 0;">Here's how your Neshama listing performed over the last 30 days:</p>
    </td></tr>

    <tr><td>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: #FAF9F6; border-radius: 8px; border: 1px solid #e8e0d8;">
        <tr>
            {stat_box("Profile views", views)}
            {stat_box("Website clicks", clicks)}
            {stat_box("Inquiries", leads)}
        </tr>
        </table>
    </td></tr>

    <tr><td style="padding: 24px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0;">Families in the community are finding your listing when they need help the most. Thank you for being part of the Neshama network.</p>
    </td></tr>

    <tr><td style="padding: 20px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #5c534a;">
        <p style="margin: 0;">Questions? Reply to this email any time.</p>
    </td></tr>

    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8; margin-top: 20px;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''
    return html


def send_report(email, vendor_name, html):
    """Send the report email to a vendor"""
    subject = "Your Neshama listing \u2014 monthly update"

    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    if sendgrid_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, ReplyTo, MimeType
            plain_text = _html_to_plain(html)
            msg = Mail(
                from_email=Email(FROM_EMAIL, FROM_NAME),
                to_emails=To(email),
                subject=subject,
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html)
            )
            msg.reply_to = ReplyTo('contact@neshama.ca', 'Neshama')
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(msg)
            logging.info(f" Sent to {email} (status {response.status_code})")
            return True
        except Exception as e:
            logging.error(f" Failed to send to {email}: {e}")
            return False
    else:
        logging.info(f" TEST MODE — would send to {email}")
        logging.info(f" Subject: {subject}")
        return True


def run_monthly_reports(db_path=None):
    """Send monthly performance reports to all eligible vendors"""
    logging.info(f"\n{'='*60}")
    logging.info(f" NESHAMA VENDOR MONTHLY REPORT")
    logging.info(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"{'='*60}\n")

    stats = get_vendor_stats(db_path)

    if not stats:
        logging.info("No vendors with activity to report.")
        logging.info(f"\n{'='*60}\n")
        return

    logging.info(f"Sending reports to {len(stats)} vendor(s):\n")

    sent = 0
    failed = 0
    for v in stats:
        logging.info(f" {v['name']} — {v['views']} views, {v['clicks']} clicks, {v['leads']} inquiries")
        html = generate_report_html(v['name'], v['views'], v['clicks'], v['leads'])
        if send_report(v['email'], v['name'], html):
            sent += 1
        else:
            failed += 1

    logging.info(f"\n{'='*60}")
    logging.error(f" SUMMARY: {sent} sent, {failed} failed")
    logging.info(f"{'='*60}\n")


if __name__ == '__main__':
    run_monthly_reports()
