#!/usr/bin/env python3
"""
Neshama Email Subscription System
Handles email subscriptions with double opt-in via SendGrid
"""

import sqlite3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
import os
import json

# SendGrid imports (install with: pip3 install sendgrid)
import re as _re
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


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

class EmailSubscriptionManager:
    # Rate limiting: max 3 subscribe attempts per email per 10 minutes
    _subscribe_attempts = {}

    def __init__(self, db_path='neshama.db', sendgrid_api_key=None):
        """Initialize subscription manager"""
        self.db_path = db_path
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get('SENDGRID_API_KEY')
        self.from_email = 'updates@neshama.ca'
        self.from_name = 'Neshama'
        
        if not self.sendgrid_api_key:
            logging.warning(" Warning: SENDGRID_API_KEY not set")
        
        self.create_subscribers_table()
    
    def create_subscribers_table(self):
        """Create subscribers table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmation_token TEXT UNIQUE,
                subscribed_at TEXT NOT NULL,
                confirmed_at TEXT,
                last_email_sent TEXT,
                unsubscribed_at TEXT,
                unsubscribe_token TEXT UNIQUE,
                bounce_count INTEGER DEFAULT 0
            )
        ''')
        
        # Migration: add frequency and locations columns if missing
        cursor.execute("PRAGMA table_info(subscribers)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'frequency' not in columns:
            cursor.execute("ALTER TABLE subscribers ADD COLUMN frequency TEXT DEFAULT 'daily'")
            logging.info(" DB migration: added 'frequency' column to subscribers")
        if 'locations' not in columns:
            cursor.execute("ALTER TABLE subscribers ADD COLUMN locations TEXT DEFAULT 'toronto,montreal'")
            logging.info(" DB migration: added 'locations' column to subscribers")
        if 'source' not in columns:
            cursor.execute("ALTER TABLE subscribers ADD COLUMN source TEXT DEFAULT NULL")
            logging.info(" DB migration: added 'source' column to subscribers (lead-magnet attribution)")

        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_subscriber_email
            ON subscribers(email)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_subscriber_confirmed 
            ON subscribers(confirmed)
        ''')
        
        conn.commit()
        conn.close()
        
    def generate_token(self):
        """Generate secure random token"""
        return secrets.token_urlsafe(32)
    
    def subscribe(self, email, frequency='daily', locations='toronto,montreal'):
        """
        Subscribe a new email address with preferences
        Returns: {'status': 'success'/'error', 'message': '...'}
        """
        email = email.lower().strip()

        # Rate limiting: max 3 attempts per email per 10 minutes
        now = datetime.now()
        attempts = self._subscribe_attempts.get(email, [])
        # Purge old attempts
        attempts = [t for t in attempts if (now - t).total_seconds() < 600]
        if len(attempts) >= 3:
            return {
                'status': 'error',
                'message': 'Too many attempts. Please try again in a few minutes.'
            }
        attempts.append(now)
        self._subscribe_attempts[email] = attempts

        # Validate email with proper regex
        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            return {
                'status': 'error',
                'message': 'Please enter a valid email address'
            }

        # Validate frequency
        if frequency not in ('daily', 'weekly'):
            frequency = 'daily'

        # Validate locations
        valid_locs = {'toronto', 'montreal'}
        loc_list = [l.strip() for l in locations.split(',') if l.strip() in valid_locs]
        if not loc_list:
            loc_list = ['toronto', 'montreal']
        locations = ','.join(sorted(loc_list))

        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        try:
            # Check if already exists
            cursor.execute('SELECT confirmed, unsubscribed_at FROM subscribers WHERE email = ?', (email,))
            existing = cursor.fetchone()

            if existing:
                confirmed, unsubscribed_at = existing

                if confirmed and not unsubscribed_at:
                    # Already subscribed and confirmed — send reminder
                    self.send_already_subscribed_email(email)
                    # Don't reveal they're already subscribed (privacy)
                    return {
                        'status': 'success',
                        'message': 'Check your email to confirm'
                    }
                elif unsubscribed_at:
                    # Previously unsubscribed — allow resubscription, auto-confirm
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmed = TRUE,
                            confirmed_at = ?,
                            subscribed_at = ?,
                            unsubscribed_at = NULL,
                            bounce_count = 0,
                            frequency = ?,
                            locations = ?
                        WHERE email = ?
                    ''', (now.isoformat(), now.isoformat(), frequency, locations, email))
                else:
                    # Exists but not confirmed — auto-confirm now
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmed = TRUE,
                            confirmed_at = ?,
                            subscribed_at = ?,
                            frequency = ?,
                            locations = ?
                        WHERE email = ?
                    ''', (now.isoformat(), now.isoformat(), frequency, locations, email))
            else:
                # New subscriber — auto-confirm (double opt-in disabled)
                unsubscribe_token = self.generate_token()

                cursor.execute('''
                    INSERT INTO subscribers (
                        email, confirmed,
                        subscribed_at, confirmed_at, unsubscribe_token,
                        frequency, locations
                    ) VALUES (?, TRUE, ?, ?, ?, ?, ?)
                ''', (email, now.isoformat(), now.isoformat(),
                      unsubscribe_token, frequency, locations))

            conn.commit()

            # Send welcome email instead of confirmation
            try:
                self.send_welcome_email(email)
            except Exception as e:
                logging.warning(f"Welcome email failed for {email}: {e}")

            return {
                'status': 'success',
                'message': 'You are subscribed! Check your inbox for a welcome email.'
            }

        except Exception as e:
            conn.rollback()
            logging.error(f"Subscription error: {str(e)}")
            return {
                'status': 'error',
                'message': 'Subscription failed. Please try again.'
            }
        finally:
            conn.close()
    
    def confirm_subscription(self, token):
        """
        Confirm subscription via token from email
        Returns: {'status': 'success'/'error', 'message': '...'}
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT email, confirmed, frequency, locations, subscribed_at FROM subscribers
                WHERE confirmation_token = ?
            ''', (token,))

            result = cursor.fetchone()

            if not result:
                return {
                    'status': 'error',
                    'message': 'Invalid or expired confirmation link'
                }

            email, confirmed, frequency, locations, subscribed_at = result
            frequency = frequency or 'daily'
            locations = locations or 'toronto,montreal'

            # Token expires after 72 hours
            if subscribed_at:
                try:
                    subscribed_time = datetime.fromisoformat(subscribed_at)
                    if (datetime.now() - subscribed_time) > timedelta(hours=72):
                        return {
                            'status': 'error',
                            'message': 'This confirmation link has expired. Please subscribe again.'
                        }
                except (ValueError, TypeError):
                    pass

            if confirmed:
                return {
                    'status': 'success',
                    'message': 'You are already subscribed!'
                }

            # Confirm subscription
            cursor.execute('''
                UPDATE subscribers SET
                    confirmed = TRUE,
                    confirmed_at = ?
                WHERE confirmation_token = ?
            ''', (datetime.now().isoformat(), token))

            conn.commit()

            # Send welcome email
            self.send_welcome_email(email)

            # Build a human-readable preference summary
            loc_parts = [l.strip().title() for l in locations.split(',')]
            if len(loc_parts) == 2:
                loc_str = f'{loc_parts[0]} and {loc_parts[1]}'
            else:
                loc_str = loc_parts[0] if loc_parts else 'Toronto and Montreal'

            return {
                'status': 'success',
                'message': f'Successfully subscribed! You will receive {frequency} updates for {loc_str} at {email}'
            }

        except Exception as e:
            conn.rollback()
            logging.error(f"Confirmation error: {str(e)}")
            return {
                'status': 'error',
                'message': 'Confirmation failed. Please try again.'
            }
        finally:
            conn.close()
    
    def unsubscribe(self, token):
        """
        Unsubscribe via token from email
        Returns: {'status': 'success'/'error', 'message': '...', 'email': '...'}
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT email FROM subscribers 
                WHERE unsubscribe_token = ?
                AND unsubscribed_at IS NULL
            ''', (token,))
            
            result = cursor.fetchone()
            
            if not result:
                return {
                    'status': 'error',
                    'message': 'Invalid unsubscribe link or already unsubscribed'
                }
            
            email = result[0]
            
            # Unsubscribe
            cursor.execute('''
                UPDATE subscribers SET
                    unsubscribed_at = ?
                WHERE unsubscribe_token = ?
            ''', (datetime.now().isoformat(), token))
            
            conn.commit()
            
            return {
                'status': 'success',
                'message': 'You have been unsubscribed from Neshama emails',
                'email': email
            }
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Unsubscribe error: {str(e)}")
            return {
                'status': 'error',
                'message': 'Unsubscribe failed. Please try again.'
            }
        finally:
            conn.close()
    
    def send_confirmation_email(self, email, token, frequency='daily', locations='toronto,montreal'):
        """Send double opt-in confirmation email"""
        if not self.sendgrid_api_key:
            logging.info(f" Would send confirmation email to {email} with token {token}")
            logging.info(f" Confirmation link: https://neshama.ca/confirm/{token}")
            logging.info(f" Preferences: {frequency}, {locations}")
            return

        confirmation_url = f"https://neshama.ca/confirm/{token}"

        # Build location description
        loc_parts = [l.strip().title() for l in locations.split(',')]
        if len(loc_parts) == 2:
            loc_str = 'Toronto and Montreal'
        elif 'toronto' in locations:
            loc_str = 'Toronto'
        else:
            loc_str = 'Montreal'

        freq_desc = 'a quiet daily update' if frequency == 'daily' else 'a weekly roundup'

        html_content = f"""<!DOCTYPE html>
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
        <p style="margin: 0 0 20px 0;">Thank you for signing up.</p>

        <p style="margin: 0 0 20px 0;">Neshama sends {freq_desc} when new obituaries are posted from {loc_str} funeral homes, including funeral times, shiva details, and links to full obituaries.</p>

        <p style="margin: 0 0 28px 0;">To start receiving these updates, please confirm your email address.</p>

        <!-- Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #3E2723; border-radius: 4px;">
            <a href="{confirmation_url}" style="display: inline-block; padding: 13px 32px; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">Confirm subscription</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 20px 0;">You can unsubscribe at any time with one click.</p>

        <p style="margin: 0; font-size: 13px; color: #9e9488; line-height: 1.6;">If the button above doesn't work, copy and paste this link into your browser:<br>
        <span style="color: #9e9488; word-break: break-all;">{confirmation_url}</span></p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0 0 6px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">If you didn't request this, you can safely ignore this email.</p>
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">contact@neshama.ca</a></p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
        
        try:
            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject='Confirm your subscription - Neshama',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            logging.info(f" Confirmation email sent to {email}")
            
        except Exception as e:
            logging.error(f" Failed to send confirmation email: {str(e)}")
    
    def send_welcome_email(self, email):
        """Send welcome email after confirmation — Email 1 of the 3-email drip sequence."""
        if not self.sendgrid_api_key:
            logging.info(f" Would send welcome email to {email}")
            return

        html_content = f"""<!DOCTYPE html>
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
        <p style="margin: 0 0 20px 0;">Welcome to Neshama.</p>

        <p style="margin: 0 0 20px 0;">You are now subscribed to receive obituary updates from Toronto and Montreal funeral homes. Each update includes funeral times, shiva details, and links to full obituaries so you can show up for the people in your community when it matters most.</p>

        <p style="margin: 0 0 20px 0;">If you would like to see what Neshama looks like in action, take a quick look around.</p>

        <!-- Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #3E2723; border-radius: 4px;">
            <a href="https://neshama.ca/demo" style="display: inline-block; padding: 13px 32px; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">See how Neshama works</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 20px 0;">Neshama was built by two women in Toronto who believe showing up for each other shouldn't be this hard.</p>

        <p style="margin: 0 0 20px 0;">You can unsubscribe at any time with one click from any email we send.</p>

        <p style="margin: 0; font-size: 14px; color: #5c534a; line-height: 1.6;">If you have questions or feedback, reach us at <a href="mailto:contact@neshama.ca" style="color: #3E2723;">contact@neshama.ca</a>.</p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">contact@neshama.ca</a></p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        try:
            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject='Welcome to Neshama',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            logging.info(f" Welcome email sent to {email}")

        except Exception as e:
            logging.error(f" Failed to send welcome email: {str(e)}")
    
    def send_already_subscribed_email(self, email):
        """Send reminder email if already subscribed"""
        if not self.sendgrid_api_key:
            logging.warning("No SendGrid API key — skipping already-subscribed email")
            return

        html_content = """<!DOCTYPE html>
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
        <p style="margin: 0 0 20px 0;">You're already subscribed to Neshama daily updates.</p>

        <p style="margin: 0 0 20px 0;">We wanted to let you know that your subscription is active and you're all set. You'll continue to receive updates when new obituaries are posted from Toronto and Montreal funeral homes.</p>

        <p style="margin: 0 0 20px 0;">No action is needed on your part.</p>

        <!-- Button -->
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 0 0 28px 0;">
        <tr><td style="background-color: #3E2723; border-radius: 4px;">
            <a href="https://neshama.ca/feed" style="display: inline-block; padding: 13px 32px; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #ffffff; text-decoration: none; letter-spacing: 0.02em;">View latest obituaries</a>
        </td></tr>
        </table>

        <p style="margin: 0 0 20px 0;">You can unsubscribe at any time with one click from any email we send.</p>

        <p style="margin: 0; font-size: 14px; color: #5c534a; line-height: 1.6;">If you have questions or feedback, reach us at <a href="mailto:contact@neshama.ca" style="color: #3E2723;">contact@neshama.ca</a>.</p>
    </td></tr>

    <!-- Footer -->
    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON &middot; <a href="mailto:contact@neshama.ca" style="color: #9e9488;">contact@neshama.ca</a></p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        try:
            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject="You're already subscribed to Neshama",
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )

            sg = SendGridAPIClient(self.sendgrid_api_key)
            sg.send(message)

            logging.info(f" Already-subscribed email sent to {email}")

        except Exception as e:
            logging.error(f" Failed to send already-subscribed email: {str(e)}")

    # ── Lead-magnet flow ─────────────────────────────────────
    # Lead-magnet subscribers skip double opt-in: the offer is the PDF and they
    # need it now. Confirmed=TRUE on insert, source tag for analytics, send the
    # welcome with the PDF link immediately.

    def subscribe_to_lead_magnet(self, email, source='lead-magnet-shiva-guide'):
        """Subscribe via lead magnet — immediate confirmation, no double opt-in.
        Returns: {'status': 'success'/'error', 'message': '...'}"""
        email = (email or '').lower().strip()

        # Rate limit (same as regular subscribe): max 3 per email per 10 minutes
        now = datetime.now()
        attempts = self._subscribe_attempts.get(email, [])
        attempts = [t for t in attempts if (now - t).total_seconds() < 600]
        if len(attempts) >= 3:
            return {'status': 'error', 'message': 'Too many attempts. Please try again in a few minutes.'}
        attempts.append(now)
        self._subscribe_attempts[email] = attempts

        if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
            return {'status': 'error', 'message': 'Please enter a valid email address.'}

        # Sanitize source tag — short, alphanumeric+dashes only, capped length
        source = re.sub(r'[^a-zA-Z0-9_-]', '', (source or 'lead-magnet').strip())[:64] or 'lead-magnet'

        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        try:
            now_iso = now.isoformat()
            # INSERT OR IGNORE: if email already subscribed, just resend the welcome
            cursor.execute('''
                INSERT OR IGNORE INTO subscribers
                (email, confirmed, subscribed_at, confirmed_at, frequency, locations, source)
                VALUES (?, TRUE, ?, ?, 'weekly', 'toronto,montreal', ?)
            ''', (email, now_iso, now_iso, source))
            inserted = cursor.rowcount > 0
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            logging.error(f"[LeadMagnet] DB error for {email}: {e}")
            return {'status': 'error', 'message': 'Something went wrong. Please try again.'}
        conn.close()

        # Always send the welcome+PDF — new subscribers AND repeat clicks
        try:
            self.send_lead_magnet_welcome_email(email)
        except Exception as e:
            logging.error(f"[LeadMagnet] Email send failed for {email}: {e}")
            # Don't fail the request — they're subscribed. They can re-request.

        msg = 'Check your email — your guide is on the way.' if inserted \
            else 'You were already on our list. Sending your guide again now.'
        return {'status': 'success', 'message': msg}

    def send_lead_magnet_welcome_email(self, email):
        """Send The Shiva Guide PDF link as a warm welcome email.
        PDF is linked (not attached) — simpler delivery, no attachment-size concerns,
        and the link works as a re-download anytime."""
        if not self.sendgrid_api_key:
            logging.info(f"[LeadMagnet] TEST MODE — would send Shiva Guide welcome to {email}")
            logging.info(f"[LeadMagnet] PDF link would be: https://neshama.ca/shiva-guide.pdf")
            return

        pdf_url = "https://neshama.ca/shiva-guide.pdf"
        landing_url = "https://neshama.ca/shiva-guide"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#ffffff; -webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 20px;">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px; width:100%;">

    <tr><td style="padding-bottom:32px; border-bottom:1px solid #e8e0d8;">
        <span style="font-family:Georgia,'Times New Roman',serif; font-size:22px; color:#3E2723; letter-spacing:0.02em;">Neshama</span>
    </td></tr>

    <tr><td style="padding:32px 0; font-family:Georgia,'Times New Roman',serif; font-size:16px; line-height:1.7; color:#3E2723;">
        <p style="margin:0 0 20px 0;">Thank you for downloading The Shiva Guide.</p>

        <p style="margin:0 0 28px 0;">Save it somewhere you'll find it later — your phone, your saved files, your inbox starred folder. The most useful time to read it is before you need to.</p>

        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 32px 0;">
        <tr><td style="background-color:#D2691E; border-radius:4px;">
            <a href="{pdf_url}" style="display:inline-block; padding:13px 32px; font-family:Georgia,'Times New Roman',serif; font-size:15px; color:#ffffff; text-decoration:none; letter-spacing:0.02em;">Download The Shiva Guide (PDF)</a>
        </td></tr>
        </table>

        <p style="margin:0 0 14px 0;">A few things to know:</p>

        <p style="margin:0 0 14px 0;">&middot; If a friend or family member is sitting shiva right now, the meal coordination tool at <a href="https://neshama.ca/shiva/organize" style="color:#D2691E;">neshama.ca/shiva/organize</a> takes about five minutes to set up. It saves families from the lasagna pile-up.</p>

        <p style="margin:0 0 14px 0;">&middot; If you'd like to set a yahrzeit reminder for someone you love, you can do that at <a href="https://neshama.ca/yahrzeit" style="color:#D2691E;">neshama.ca/yahrzeit</a>.</p>

        <p style="margin:0 0 28px 0;">&middot; If you ever have a question, just reply to this email. We read every one.</p>

        <p style="margin:0 0 8px 0;">Thank you for being part of this. Neshama exists because our community shows up for each other.</p>

        <p style="margin:0 0 4px 0;">Warmly,</p>
        <p style="margin:0 0 28px 0;">Jordana &amp; Erin<br><span style="color:#9e9488; font-size:14px;">Founders, Neshama</span></p>

        <p style="margin:0; font-size:13px; color:#9e9488; line-height:1.6;">P.S. If this guide is useful to someone you know, please share it. The PDF is yours to forward freely, or send them to <a href="{landing_url}" style="color:#9e9488;">{landing_url}</a>.</p>
    </td></tr>

    <tr><td style="padding-top:28px; border-top:1px solid #e8e0d8;">
        <p style="margin:0; font-family:Georgia,'Times New Roman',serif; font-size:13px; color:#9e9488; line-height:1.6;">Neshama &middot; Toronto, ON &middot; <a href="mailto:contact@neshama.ca" style="color:#9e9488;">contact@neshama.ca</a></p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

        try:
            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject='Your Shiva Guide is here',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(self.sendgrid_api_key)
            sg.send(message)
            logging.info(f"[LeadMagnet] Welcome+PDF email sent to {email}")
        except Exception as e:
            logging.error(f"[LeadMagnet] SendGrid send error for {email}: {e}")
            raise

    def get_confirmed_subscribers(self):
        """Get list of all confirmed subscribers"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT email, subscribed_at, last_email_sent
            FROM subscribers
            WHERE confirmed = TRUE
            AND unsubscribed_at IS NULL
            ORDER BY subscribed_at DESC
        ''')

        subscribers = cursor.fetchall()
        conn.close()

        return subscribers

    def get_subscribers_by_preference(self, frequency=None, location=None):
        """
        Get confirmed subscribers filtered by frequency and/or location.
        Returns: list of (email, unsubscribe_token, frequency, locations) tuples
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        query = '''
            SELECT email, unsubscribe_token, frequency, locations
            FROM subscribers
            WHERE confirmed = TRUE
            AND unsubscribed_at IS NULL
        '''
        params = []

        if frequency:
            query += " AND frequency = ?"
            params.append(frequency)

        if location:
            query += " AND locations LIKE ?"
            params.append(f'%{location}%')

        query += " ORDER BY subscribed_at DESC"

        cursor.execute(query, params)
        subscribers = cursor.fetchall()
        conn.close()

        return subscribers
    
    def get_stats(self):
        """Get subscription statistics"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE AND unsubscribed_at IS NULL')
        active = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = FALSE')
        pending = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM subscribers WHERE unsubscribed_at IS NOT NULL')
        unsubscribed = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'active': active,
            'pending': pending,
            'unsubscribed': unsubscribed,
            'total': active + pending
        }

if __name__ == '__main__':
    # Test the subscription system
    manager = EmailSubscriptionManager()
    
    logging.info("\n" + "="*60)
    logging.info(" NESHAMA EMAIL SUBSCRIPTION SYSTEM")
    logging.info("="*60 + "\n")
    
    stats = manager.get_stats()
    logging.info(f"Active subscribers: {stats['active']}")
    logging.info(f"Pending confirmation: {stats['pending']}")
    logging.info(f"Unsubscribed: {stats['unsubscribed']}")
    logging.info(f"\nTotal: {stats['total']}")
    
    logging.info("\n" + "="*60 + "\n")
