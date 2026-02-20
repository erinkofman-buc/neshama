#!/usr/bin/env python3
"""
Neshama Email Subscription System
Handles email subscriptions with double opt-in via SendGrid
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime
import os
import json

# SendGrid imports (install with: pip3 install sendgrid)
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

class EmailSubscriptionManager:
    def __init__(self, db_path='neshama.db', sendgrid_api_key=None):
        """Initialize subscription manager"""
        self.db_path = db_path
        self.sendgrid_api_key = sendgrid_api_key or os.environ.get('SENDGRID_API_KEY')
        self.from_email = 'erinkofman@gmail.com'
        self.from_name = 'Neshama'
        
        if not self.sendgrid_api_key:
            print("⚠️  Warning: SENDGRID_API_KEY not set")
        
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
    
    def subscribe(self, email):
        """
        Subscribe a new email address
        Returns: {'status': 'success'/'error', 'message': '...'}
        """
        email = email.lower().strip()
        
        # Validate email format (basic)
        if '@' not in email or '.' not in email:
            return {
                'status': 'error',
                'message': 'Invalid email address'
            }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if already exists
            cursor.execute('SELECT confirmed, unsubscribed_at FROM subscribers WHERE email = ?', (email,))
            existing = cursor.fetchone()
            
            if existing:
                confirmed, unsubscribed_at = existing
                
                if confirmed and not unsubscribed_at:
                    # Already subscribed and confirmed - send reminder email
                    self.send_already_subscribed_email(email)
                    # Don't tell them they're already subscribed (privacy)
                    return {
                        'status': 'success',
                        'message': 'Check your email to confirm'
                    }
                elif unsubscribed_at:
                    # Previously unsubscribed - allow resubscription
                    confirmation_token = self.generate_token()
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmed = FALSE,
                            confirmation_token = ?,
                            subscribed_at = ?,
                            unsubscribed_at = NULL,
                            bounce_count = 0
                        WHERE email = ?
                    ''', (confirmation_token, datetime.now().isoformat(), email))
                else:
                    # Exists but not confirmed - resend confirmation
                    confirmation_token = self.generate_token()
                    cursor.execute('''
                        UPDATE subscribers SET
                            confirmation_token = ?,
                            subscribed_at = ?
                        WHERE email = ?
                    ''', (confirmation_token, datetime.now().isoformat(), email))
            else:
                # New subscriber
                confirmation_token = self.generate_token()
                unsubscribe_token = self.generate_token()
                
                cursor.execute('''
                    INSERT INTO subscribers (
                        email, confirmed, confirmation_token,
                        subscribed_at, unsubscribe_token
                    ) VALUES (?, FALSE, ?, ?, ?)
                ''', (email, confirmation_token, datetime.now().isoformat(), unsubscribe_token))
            
            conn.commit()
            
            # Send confirmation email
            self.send_confirmation_email(email, confirmation_token)
            
            return {
                'status': 'success',
                'message': 'Check your email to confirm your subscription'
            }
            
        except Exception as e:
            conn.rollback()
            print(f"Subscription error: {str(e)}")
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
                SELECT email, confirmed FROM subscribers 
                WHERE confirmation_token = ?
            ''', (token,))
            
            result = cursor.fetchone()
            
            if not result:
                return {
                    'status': 'error',
                    'message': 'Invalid or expired confirmation link'
                }
            
            email, confirmed = result
            
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
            
            return {
                'status': 'success',
                'message': f'Successfully subscribed! You will receive daily updates at {email}'
            }
            
        except Exception as e:
            conn.rollback()
            print(f"Confirmation error: {str(e)}")
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
            print(f"Unsubscribe error: {str(e)}")
            return {
                'status': 'error',
                'message': 'Unsubscribe failed. Please try again.'
            }
        finally:
            conn.close()
    
    def send_confirmation_email(self, email, token):
        """Send double opt-in confirmation email"""
        if not self.sendgrid_api_key:
            print(f"⚠️  Would send confirmation email to {email} with token {token}")
            print(f"   Confirmation link: https://neshama.ca/confirm/{token}")
            return
        
        confirmation_url = f"https://neshama.ca/confirm/{token}"
        
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

        <p style="margin: 0 0 20px 0;">Neshama sends a quiet daily update when new obituaries are posted from Toronto-area funeral homes, including funeral times, shiva details, and links to full obituaries.</p>

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
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject='Confirm your subscription - Neshama',
                html_content=Content("text/html", html_content)
            )
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            print(f"✅ Confirmation email sent to {email}")
            
        except Exception as e:
            print(f"❌ Failed to send confirmation email: {str(e)}")
    
    def send_welcome_email(self, email):
        """Send welcome email after confirmation"""
        # Implementation similar to confirmation email
        print(f"✅ Welcome email would be sent to {email}")
    
    def send_already_subscribed_email(self, email):
        """Send reminder email if already subscribed"""
        # Implementation for reminder email
        print(f"✅ Already-subscribed email would be sent to {email}")
    
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
    
    print("\n" + "="*60)
    print(" NESHAMA EMAIL SUBSCRIPTION SYSTEM")
    print("="*60 + "\n")
    
    stats = manager.get_stats()
    print(f"Active subscribers: {stats['active']}")
    print(f"Pending confirmation: {stats['pending']}")
    print(f"Unsubscribed: {stats['unsubscribed']}")
    print(f"\nTotal: {stats['total']}")
    
    print("\n" + "="*60 + "\n")
