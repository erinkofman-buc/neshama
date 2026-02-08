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
        self.from_email = 'erinkofman@gmail.com'
        self.from_name = 'Neshama'
        self.subscription_manager = EmailSubscriptionManager(db_path, sendgrid_api_key)
        
    def get_new_obituaries(self, hours=24):
        """Get obituaries posted in the last N hours"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
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
        
        # Header
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: 'Georgia', serif; line-height: 1.6; color: #3E2723; max-width: 600px; margin: 0 auto; }
                .header { text-align: center; padding: 20px 0; border-bottom: 2px solid #D4C5B9; }
                .title { font-size: 28px; color: #3E2723; margin: 0; }
                .hebrew { font-size: 20px; color: #B2BEB5; }
                .greeting { padding: 20px; font-size: 16px; }
                .obituary-card { background: #FAF9F6; border-left: 4px solid #D2691E; padding: 20px; margin: 20px 0; border-radius: 8px; }
                .name { font-size: 24px; font-weight: 600; color: #3E2723; margin-bottom: 5px; }
                .hebrew-name { font-size: 18px; color: #B2BEB5; margin-bottom: 15px; direction: rtl; }
                .source { font-size: 14px; color: #B2BEB5; margin-bottom: 10px; }
                .detail { margin: 8px 0; font-size: 15px; }
                .detail-label { font-weight: 600; color: #D2691E; }
                .read-more { display: inline-block; background: #D2691E; color: white; padding: 10px 25px; text-decoration: none; border-radius: 20px; margin-top: 15px; font-size: 14px; }
                .footer { text-align: center; padding: 20px; color: #B2BEB5; font-size: 13px; border-top: 1px solid #D4C5B9; margin-top: 30px; }
                .footer a { color: #D2691E; text-decoration: none; }
            </style>
        </head>
        <body>
            <div class="header">
                <div class="hebrew">נשמה</div>
                <h1 class="title">Neshama</h1>
            </div>
            
            <div class="greeting">
                <p>Good morning,</p>
        """
        
        # Count
        count = len(obituaries)
        html += f"<p><strong>{count} new obituar{'y was' if count == 1 else 'ies were'} posted in the last 24 hours:</strong></p>"
        html += "</div>"
        
        # Obituary cards
        for obit in obituaries:
            html += '<div class="obituary-card">'
            
            # Name
            html += f'<div class="name">{obit["deceased_name"]}'
            if obit.get('hebrew_name'):
                html += ' ז״ל'  # May their memory be a blessing
            html += '</div>'
            
            # Hebrew name
            if obit.get('hebrew_name'):
                html += f'<div class="hebrew-name">{obit["hebrew_name"]}</div>'
            
            # Source
            html += f'<div class="source">{obit["source"]}</div>'
            
            # Funeral
            if obit.get('funeral_datetime'):
                html += f'<div class="detail"><span class="detail-label">🕯️ Funeral:</span> {obit["funeral_datetime"]}'
                if obit.get('funeral_location'):
                    html += f'<br>&nbsp;&nbsp;&nbsp;{obit["funeral_location"]}'
                html += '</div>'
            
            # Shiva
            if obit.get('shiva_info'):
                shiva_preview = obit['shiva_info'][:150]
                if len(obit['shiva_info']) > 150:
                    shiva_preview += '...'
                html += f'<div class="detail"><span class="detail-label">🏠 Shiva:</span> {shiva_preview}</div>'
            
            # Burial
            if obit.get('burial_location'):
                html += f'<div class="detail"><span class="detail-label">Burial:</span> {obit["burial_location"]}</div>'
            
            # Livestream badge
            if obit.get('livestream_available'):
                html += '<div class="detail"><span class="detail-label">📺 Livestream Available</span></div>'
            
            # Read more button
            html += f'<a href="{obit["condolence_url"]}" class="read-more">Read Full Obituary →</a>'
            
            html += '</div>'
        
        # Footer with unsubscribe
        html += """
            <div class="footer">
                <p><a href="https://neshama.ca">View all on Neshama.ca</a></p>
                <p><a href="{{unsubscribe_url}}">Unsubscribe</a> | <a href="mailto:contact@neshama.ca">Contact Us</a></p>
                <p style="margin-top: 15px;">
                    Neshama - Every soul remembered<br>
                    Toronto, ON, Canada
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_digest_to_subscriber(self, email, unsubscribe_token, html_content):
        """Send digest email to a single subscriber"""
        if not self.sendgrid_api_key:
            print(f"⚠️  Would send digest to {email}")
            return {'success': True, 'test_mode': True}
        
        # Replace unsubscribe URL
        unsubscribe_url = f"https://neshama.ca/unsubscribe/{unsubscribe_token}"
        html_with_unsubscribe = html_content.replace('{{unsubscribe_url}}', unsubscribe_url)
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(email),
                subject=f'Neshama Daily Update',
                html_content=Content("text/html", html_with_unsubscribe)
            )
            
            # Add unsubscribe header for email clients
            message.add_header('List-Unsubscribe', f'<{unsubscribe_url}>')
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            return {'success': True, 'status_code': response.status_code}
            
        except Exception as e:
            print(f"❌ Failed to send to {email}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_daily_digest(self):
        """Send daily digest to all confirmed subscribers"""
        print(f"\n{'='*70}")
        print(f" NESHAMA DAILY DIGEST")
        print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Get new obituaries
        obituaries = self.get_new_obituaries(hours=24)
        
        if not obituaries:
            print("ℹ️  No new obituaries in the last 24 hours. Skipping email send.")
            print(f"\n{'='*70}\n")
            return {
                'status': 'skipped',
                'reason': 'no_new_content',
                'subscribers_count': 0
            }
        
        print(f"📰 Found {len(obituaries)} new obituar{'y' if len(obituaries) == 1 else 'ies'}")
        
        # Generate email HTML
        html_content = self.generate_email_html(obituaries)
        
        # Get confirmed subscribers
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email, unsubscribe_token 
            FROM subscribers 
            WHERE confirmed = TRUE 
            AND unsubscribed_at IS NULL
        ''')
        
        subscribers = cursor.fetchall()
        print(f"📧 Sending to {len(subscribers)} subscriber{'s' if len(subscribers) != 1 else ''}\n")
        
        # Send to each subscriber
        sent_count = 0
        failed_count = 0
        
        for email, unsubscribe_token in subscribers:
            result = self.send_digest_to_subscriber(email, unsubscribe_token, html_content)
            
            if result.get('success'):
                sent_count += 1
                print(f"  ✅ {email}")
                
                # Update last_email_sent
                cursor.execute('''
                    UPDATE subscribers 
                    SET last_email_sent = ? 
                    WHERE email = ?
                ''', (datetime.now().isoformat(), email))
            else:
                failed_count += 1
                print(f"  ❌ {email} - {result.get('error', 'Unknown error')}")
        
        conn.commit()
        conn.close()
        
        print(f"\n{'='*70}")
        print(f" SUMMARY")
        print(f"{'='*70}")
        print(f" Obituaries: {len(obituaries)}")
        print(f" Sent: {sent_count}")
        print(f" Failed: {failed_count}")
        print(f" Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        return {
            'status': 'success',
            'obituaries_count': len(obituaries),
            'subscribers_sent': sent_count,
            'subscribers_failed': failed_count
        }

if __name__ == '__main__':
    sender = DailyDigestSender()
    result = sender.send_daily_digest()
