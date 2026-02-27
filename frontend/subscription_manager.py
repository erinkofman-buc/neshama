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
        conn = sqlite3.connect(self.db_path)
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

        conn = sqlite3.connect(self.db_path)
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
                    # Previously unsubscribed — allow resubscription
                    confirmation_token = self.generate_token()
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmed = FALSE,
                            confirmation_token = ?,
                            subscribed_at = ?,
                            unsubscribed_at = NULL,
                            bounce_count = 0,
                            frequency = ?,
                            locations = ?
                        WHERE email = ?
                    ''', (confirmation_token, now.isoformat(), frequency, locations, email))
                else:
                    # Exists but not confirmed — resend confirmation
                    confirmation_token = self.generate_token()
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmation_token = ?,
                            subscribed_at = ?,
                            frequency = ?,
                            locations = ?
                        WHERE email = ?
                    ''', (confirmation_token, now.isoformat(), frequency, locations, email))
            else:
                # New subscriber
                confirmation_token = self.generate_token()
                unsubscribe_token = self.generate_token()

                cursor.execute('''
                    INSERT INTO subscribers (
                        email, confirmed, confirmation_token,
                        subscribed_at, unsubscribe_token,
                        frequency, locations
                    ) VALUES (?, FALSE, ?, ?, ?, ?, ?)
                ''', (email, confirmation_token, now.isoformat(),
                      unsubscribe_token, frequency, locations))

            conn.commit()

            # Send confirmation email
            self.send_confirmation_email(email, confirmation_token, frequency, locations)

            return {
                'status': 'success',
                'message': 'Check your email to confirm your subscription'
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        """Send welcome email after confirmation"""
        # Implementation similar to confirmation email
        logging.info(f" Welcome email would be sent to {email}")
    
    def send_already_subscribed_email(self, email):
        """Send reminder email if already subscribed"""
        # Implementation for reminder email
        logging.info(f" Already-subscribed email would be sent to {email}")
    
    def get_confirmed_subscribers(self):
        """Get list of all confirmed subscribers"""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
