#!/usr/bin/env python3
"""
Neshama Yahrzeit Reminder Manager
Manages annual yahrzeit (Hebrew death anniversary) reminders.
Users subscribe to receive email reminders before the yahrzeit of a loved one,
with Kaddish text and candle-lighting guidance.
"""

import sqlite3
import uuid
import secrets
import os
import re
import html as html_mod
import threading
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Hebrew date conversion (hdate >= 1.0 API)
try:
    from hdate import HebrewDate as HDate, Months as HMonths
    HDATE_AVAILABLE = True
except ImportError:
    HDATE_AVAILABLE = False
    HDate = None
    HMonths = None
    logging.warning("[Yahrzeit] hdate library not installed — Hebrew date conversion unavailable")


# Kaddish transliteration for email templates
KADDISH_TEXT = """Yitgadal v'yitkadash sh'mei raba.
B'alma di v'ra chirutei,
v'yamlich malchutei,
b'chayeichon uv'yomeichon
uv'chayei d'chol beit Yisrael,
ba'agala uviz'man kariv. V'im'ru: Amen.

Y'hei sh'mei raba m'varach
l'alam ul'almei almaya.

Yitbarach v'yishtabach v'yitpa'ar
v'yitromam v'yitnasei,
v'yit'hadar v'yit'aleh v'yit'halal
sh'mei d'Kud'sha B'rich Hu,
l'eila min kol birchata v'shirata,
tushb'chata v'nechemata,
da'amiran b'alma. V'im'ru: Amen.

Y'hei sh'lama raba min sh'maya,
v'chayim aleinu v'al kol Yisrael.
V'im'ru: Amen.

Oseh shalom bim'romav,
Hu ya'aseh shalom aleinu,
v'al kol Yisrael.
V'im'ru: Amen."""


class YahrzeitManager:
    def __init__(self, db_path='neshama.db'):
        self.db_path = db_path
        self.sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        self.base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        self.setup_database()

    # ── Database Setup ────────────────────────────────────────

    def setup_database(self):
        """Create yahrzeit_reminders table idempotently."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS yahrzeit_reminders (
                id TEXT PRIMARY KEY,
                deceased_name TEXT NOT NULL,
                hebrew_name TEXT,
                date_of_death TEXT NOT NULL,
                hebrew_date_of_death TEXT,
                hebrew_month INTEGER,
                hebrew_day INTEGER,
                subscriber_email TEXT NOT NULL,
                obituary_id TEXT,
                confirmed INTEGER DEFAULT 0,
                confirmation_token TEXT UNIQUE,
                unsubscribe_token TEXT UNIQUE,
                subscribed_at TEXT NOT NULL,
                confirmed_at TEXT,
                unsubscribed_at TEXT,
                last_reminder_sent TEXT,
                last_reminder_hebrew_year INTEGER,
                created_at TEXT NOT NULL
            )
        ''')

        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_email ON yahrzeit_reminders(subscriber_email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_confirmed ON yahrzeit_reminders(confirmed)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_hebrew_date ON yahrzeit_reminders(hebrew_month, hebrew_day)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_obituary ON yahrzeit_reminders(obituary_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_confirm_token ON yahrzeit_reminders(confirmation_token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_yahr_unsub_token ON yahrzeit_reminders(unsubscribe_token)')

        conn.commit()
        conn.close()

    # ── Helpers ───────────────────────────────────────────────

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _validate_email(self, email):
        """Basic server-side email validation."""
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return None
        return email.strip().lower()[:254]

    def _sanitize_text(self, value, max_len=500):
        """Truncate text fields to prevent abuse."""
        if not value:
            return value
        return str(value)[:max_len].strip()

    # ── Hebrew Date Conversion ────────────────────────────────

    def convert_to_hebrew_date(self, gregorian_str):
        """Convert a Gregorian date string (YYYY-MM-DD) to Hebrew date components.
        Returns: (hebrew_str, hebrew_month, hebrew_day, hebrew_year) or None on failure.
        """
        if not HDATE_AVAILABLE:
            logging.warning("[Yahrzeit] Cannot convert date — hdate not installed")
            return None

        try:
            d = datetime.strptime(gregorian_str, '%Y-%m-%d').date()
            hd = HDate.from_gdate(d)

            h_day = hd.day
            h_month_enum = hd.month
            h_month = h_month_enum.value  # int
            h_year = hd.year

            # hdate 1.x Months enum (Tishrei-first):
            # TISHREI=1, MARCHESHVAN=2, KISLEV=3, TEVET=4, SHVAT=5, ADAR=6,
            # ADAR_I=7, ADAR_II=8, NISAN=9, IYYAR=10, SIVAN=11, TAMMUZ=12,
            # AV=13, ELUL=14
            month_names = {
                1: 'Tishrei', 2: 'Cheshvan', 3: 'Kislev', 4: 'Tevet',
                5: 'Shevat', 6: 'Adar', 7: 'Adar I', 8: 'Adar II',
                9: 'Nisan', 10: 'Iyar', 11: 'Sivan', 12: 'Tammuz',
                13: 'Av', 14: 'Elul',
            }
            month_name = month_names.get(h_month, h_month_enum.name.title())
            hebrew_str = f"{h_day} {month_name} {h_year}"

            return (hebrew_str, h_month, h_day, h_year)
        except Exception as e:
            logging.error(f"[Yahrzeit] Hebrew date conversion error: {e}")
            return None

    def get_next_yahrzeit_gregorian(self, hebrew_month, hebrew_day):
        """Find the next occurrence of a yahrzeit in the Gregorian calendar.
        Handles Adar edge cases for leap/non-leap years.
        Returns: (gregorian_date, hebrew_year) or None.
        """
        if not HDATE_AVAILABLE:
            return None

        try:
            today = datetime.now().date()

            # Strategy: try to construct a HebrewDate directly for this year and next
            # hdate 1.x Months: ADAR=6, ADAR_I=7, ADAR_II=8
            # Get current Hebrew year
            hd_today = HDate.from_gdate(today)
            current_h_year = hd_today.year

            for year_offset in range(2):  # Check this year and next
                h_year = current_h_year + year_offset
                target_month = hebrew_month

                # Adar edge cases:
                # If yahrzeit is in ADAR_II (8) but target year is not a leap year,
                # fall back to ADAR (6)
                # If yahrzeit is in ADAR_I (7) but target year is not a leap year,
                # fall back to ADAR (6)
                try:
                    month_enum = HMonths(target_month)
                    candidate = HDate(year=h_year, month=month_enum, day=hebrew_day)
                    greg_date = candidate.to_gdate()
                    if greg_date >= today:
                        return (greg_date, h_year)
                except (ValueError, TypeError):
                    # Month doesn't exist in this year (e.g. ADAR_II in non-leap year)
                    # Fall back to ADAR (6)
                    if target_month in (7, 8):  # ADAR_I or ADAR_II
                        try:
                            fallback = HDate(year=h_year, month=HMonths(6), day=hebrew_day)
                            greg_date = fallback.to_gdate()
                            if greg_date >= today:
                                return (greg_date, h_year)
                        except (ValueError, TypeError):
                            continue
                    continue

            return None
        except Exception as e:
            logging.error(f"[Yahrzeit] Next yahrzeit calculation error: {e}")
            return None

    # ── Subscribe ─────────────────────────────────────────────

    def subscribe(self, data):
        """Subscribe to yahrzeit reminders.
        data: {deceased_name, date_of_death, email, hebrew_name?, obituary_id?}
        Returns: {status, message, id?}
        """
        deceased_name = self._sanitize_text(data.get('deceased_name', ''), 200)
        date_of_death = data.get('date_of_death', '').strip()[:10]
        email = self._validate_email(data.get('email', ''))
        hebrew_name = self._sanitize_text(data.get('hebrew_name', ''), 200) or None
        obituary_id = data.get('obituary_id', '').strip() or None

        if not deceased_name:
            return {'status': 'error', 'message': 'Name of the deceased is required'}
        if not date_of_death:
            return {'status': 'error', 'message': 'Date of death is required'}
        if not email:
            return {'status': 'error', 'message': 'A valid email address is required'}

        # Validate date format
        try:
            datetime.strptime(date_of_death, '%Y-%m-%d')
        except ValueError:
            return {'status': 'error', 'message': 'Invalid date format. Please use YYYY-MM-DD.'}

        # Convert to Hebrew date
        hebrew_result = self.convert_to_hebrew_date(date_of_death)
        hebrew_date_str = None
        hebrew_month = None
        hebrew_day = None

        if hebrew_result:
            hebrew_date_str, hebrew_month, hebrew_day, _ = hebrew_result

        # Check for duplicate (same email + same deceased name + same date)
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, confirmed, unsubscribed_at FROM yahrzeit_reminders
                WHERE subscriber_email = ? AND deceased_name = ? AND date_of_death = ?
            ''', (email, deceased_name, date_of_death))
            existing = cursor.fetchone()

            if existing:
                existing = dict(existing)
                if existing['confirmed'] and not existing['unsubscribed_at']:
                    return {'status': 'error', 'message': 'You already have a yahrzeit reminder set for this person.'}
                elif existing['unsubscribed_at']:
                    # Re-subscribe: reset the record
                    new_confirm_token = secrets.token_urlsafe(32)
                    new_unsub_token = secrets.token_urlsafe(32)
                    now = datetime.now().isoformat()
                    cursor.execute('''
                        UPDATE yahrzeit_reminders
                        SET confirmed = 0, confirmation_token = ?, unsubscribe_token = ?,
                            unsubscribed_at = NULL, subscribed_at = ?,
                            hebrew_date_of_death = ?, hebrew_month = ?, hebrew_day = ?,
                            hebrew_name = ?
                        WHERE id = ?
                    ''', (new_confirm_token, new_unsub_token, now,
                          hebrew_date_str, hebrew_month, hebrew_day, hebrew_name,
                          existing['id']))
                    conn.commit()
                    return {
                        'status': 'success',
                        'message': 'Please check your email to confirm your yahrzeit reminder.',
                        'id': existing['id'],
                        'confirmation_token': new_confirm_token,
                        'email': email,
                        'deceased_name': deceased_name,
                        'hebrew_date': hebrew_date_str,
                    }

            # Create new record
            reminder_id = str(uuid.uuid4())
            confirmation_token = secrets.token_urlsafe(32)
            unsubscribe_token = secrets.token_urlsafe(32)
            now = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO yahrzeit_reminders (
                    id, deceased_name, hebrew_name, date_of_death,
                    hebrew_date_of_death, hebrew_month, hebrew_day,
                    subscriber_email, obituary_id, confirmed,
                    confirmation_token, unsubscribe_token,
                    subscribed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            ''', (
                reminder_id, deceased_name, hebrew_name, date_of_death,
                hebrew_date_str, hebrew_month, hebrew_day,
                email, obituary_id,
                confirmation_token, unsubscribe_token,
                now, now,
            ))
            conn.commit()
            return {
                'status': 'success',
                'message': 'Please check your email to confirm your yahrzeit reminder.',
                'id': reminder_id,
                'confirmation_token': confirmation_token,
                'email': email,
                'deceased_name': deceased_name,
                'hebrew_date': hebrew_date_str,
            }
        except Exception as e:
            logging.error(f"[Yahrzeit] Subscribe error: {e}")
            return {'status': 'error', 'message': 'Something went wrong. Please try again.'}
        finally:
            conn.close()

    # ── Confirm ───────────────────────────────────────────────

    def confirm(self, token):
        """Double opt-in confirmation. Token expires after 72 hours."""
        if not token:
            return {'status': 'error', 'message': 'Invalid confirmation link'}

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, deceased_name, subscriber_email, confirmed, subscribed_at,
                   hebrew_date_of_death
            FROM yahrzeit_reminders
            WHERE confirmation_token = ?
        ''', (token,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'status': 'error', 'message': 'Invalid or expired confirmation link'}

        row = dict(row)

        if row['confirmed']:
            conn.close()
            return {
                'status': 'already_confirmed',
                'message': f'Your yahrzeit reminder for {row["deceased_name"]} is already active.',
                'deceased_name': row['deceased_name'],
            }

        # Check 72-hour expiry
        subscribed = datetime.fromisoformat(row['subscribed_at'])
        if datetime.now() - subscribed > timedelta(hours=72):
            conn.close()
            return {'status': 'error', 'message': 'This confirmation link has expired. Please sign up again.'}

        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE yahrzeit_reminders
            SET confirmed = 1, confirmed_at = ?, confirmation_token = NULL
            WHERE confirmation_token = ?
        ''', (now, token))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'Your yahrzeit reminder for {row["deceased_name"]} is now active. You will receive a reminder each year before the yahrzeit.',
            'deceased_name': row['deceased_name'],
            'hebrew_date': row.get('hebrew_date_of_death'),
        }

    # ── Unsubscribe ───────────────────────────────────────────

    def unsubscribe(self, token):
        """Unsubscribe from yahrzeit reminders."""
        if not token:
            return {'status': 'error', 'message': 'Invalid unsubscribe link'}

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, deceased_name, unsubscribed_at
            FROM yahrzeit_reminders
            WHERE unsubscribe_token = ?
        ''', (token,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'status': 'error', 'message': 'Invalid unsubscribe link'}

        row = dict(row)

        if row['unsubscribed_at']:
            conn.close()
            return {
                'status': 'already_unsubscribed',
                'message': f'You have already unsubscribed from yahrzeit reminders for {row["deceased_name"]}.',
            }

        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE yahrzeit_reminders
            SET unsubscribed_at = ?
            WHERE unsubscribe_token = ?
        ''', (now, token))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'You have been unsubscribed from yahrzeit reminders for {row["deceased_name"]}. You will no longer receive annual reminders.',
            'deceased_name': row['deceased_name'],
        }

    # ── Email Templates ───────────────────────────────────────

    def send_confirmation_email(self, data):
        """Send double opt-in confirmation email.
        data: {email, deceased_name, confirmation_token, hebrew_date?}
        """
        if not self.sendgrid_api_key:
            logging.info(f"[Yahrzeit] TEST MODE — confirmation email to {data['email']}")
            return True

        confirm_url = f"{self.base_url}/yahrzeit/confirm/{data['confirmation_token']}"

        # HTML-escape all user-supplied values to prevent XSS
        safe_name = html_mod.escape(data.get('deceased_name', ''))
        safe_hebrew = html_mod.escape(data.get('hebrew_date', '') or '')

        hebrew_line = ''
        if safe_hebrew:
            hebrew_line = f'<p style="font-size:15px; color:#6b7c6e; margin:0 0 24px;">Hebrew date of passing: <strong>{safe_hebrew}</strong></p>'

        html_content = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#ffffff; font-family:Georgia, 'Times New Roman', serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;">
<tr><td align="center" style="padding:40px 20px;">
<table width="100%" style="max-width:560px;">
    <tr><td style="padding-bottom:32px;">
        <h1 style="font-family:Georgia, serif; font-size:24px; font-weight:400; color:#3E2723; margin:0 0 8px;">
            Confirm Your Yahrzeit Reminder
        </h1>
        <p style="font-size:16px; color:#3E2723; line-height:1.7; margin:0 0 24px;">
            You requested an annual yahrzeit reminder for <strong>{safe_name}</strong>.
        </p>
        {hebrew_line}
        <p style="font-size:15px; color:#3E2723; line-height:1.7; margin:0 0 24px;">
            Each year before the yahrzeit, we will send you a gentle reminder with the Hebrew date,
            candle-lighting guidance, and the Mourner's Kaddish.
        </p>
        <p style="margin:0 0 32px;">
            <a href="{confirm_url}"
               style="display:inline-block; background:#3E2723; color:#ffffff; padding:14px 36px;
                      text-decoration:none; border-radius:6px; font-size:16px; font-family:Georgia, serif;">
                Confirm My Reminder
            </a>
        </p>
        <p style="font-size:13px; color:#999; margin:0;">
            This link expires in 72 hours. If you did not request this, you can safely ignore this email.
        </p>
    </td></tr>
    <tr><td style="border-top:1px solid #eee; padding-top:24px;">
        <p style="font-size:13px; color:#999; text-align:center; margin:0;">
            Neshama &middot; Taking care of each other
        </p>
    </td></tr>
</table>
</td></tr>
</table>
</body></html>'''

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Content

            message = Mail(
                from_email=('reminders@neshama.ca', 'Neshama'),
                to_emails=data['email'],
                subject=f'Confirm your yahrzeit reminder for {data.get("deceased_name", "")}',
            )
            message.content = [Content('text/html', html_content)]

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            logging.info(f"[Yahrzeit] Confirmation email sent to {data['email']} (status {response.status_code})")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logging.error(f"[Yahrzeit] Failed to send confirmation email: {e}")
            return False

    def send_yahrzeit_reminder(self, reminder, reminder_type='week_ahead'):
        """Send a yahrzeit reminder email.
        reminder: dict row from DB
        reminder_type: 'week_ahead' or 'day_of'
        """
        if not self.sendgrid_api_key:
            logging.info(f"[Yahrzeit] TEST MODE — {reminder_type} reminder to {reminder['subscriber_email']}")
            return True

        unsubscribe_url = f"{self.base_url}/yahrzeit/unsubscribe/{reminder['unsubscribe_token']}"

        # HTML-escape all user-supplied values
        deceased_name = html_mod.escape(reminder.get('deceased_name', ''))
        hebrew_name = html_mod.escape(reminder.get('hebrew_name', '') or '')
        hebrew_date = html_mod.escape(reminder.get('hebrew_date_of_death', '') or '')
        safe_obit_id = html_mod.escape(reminder.get('obituary_id', '') or '')

        name_display = deceased_name
        if hebrew_name:
            name_display = f"{deceased_name} ({hebrew_name})"

        # Memorial page link if we have an obituary_id
        memorial_link = ''
        if safe_obit_id:
            memorial_link = f'''<p style="font-size:15px; margin:24px 0;">
                <a href="{self.base_url}/memorial/{safe_obit_id}"
                   style="color:#D2691E; text-decoration:none;">
                    Visit the memorial page &rarr;
                </a>
            </p>'''

        # Subject uses unescaped name (email subjects don't render HTML)
        raw_name = reminder.get('deceased_name', '')

        if reminder_type == 'day_of':
            subject = f'Today is the yahrzeit of {raw_name}'
            heading = f'Today is the Yahrzeit of {name_display}'
            intro = f'''<p style="font-size:16px; color:#3E2723; line-height:1.7; margin:0 0 24px;">
                Today marks the yahrzeit of <strong>{name_display}</strong>.
                May their memory be a blessing.
            </p>'''
        else:
            subject = f'The yahrzeit of {raw_name} is approaching'
            heading = f'The Yahrzeit of {name_display} Is Approaching'
            intro = f'''<p style="font-size:16px; color:#3E2723; line-height:1.7; margin:0 0 12px;">
                The yahrzeit of <strong>{name_display}</strong> is approaching.
            </p>
            <p style="font-size:15px; color:#6b7c6e; margin:0 0 24px;">
                Hebrew date: <strong>{hebrew_date}</strong>
            </p>'''

        kaddish_html = KADDISH_TEXT.replace('\n\n', '</p><p style="font-size:14px; color:#3E2723; line-height:1.8; margin:0 0 16px; font-style:italic;">').replace('\n', '<br>')
        kaddish_section = f'''<p style="font-size:14px; color:#3E2723; line-height:1.8; margin:0 0 16px; font-style:italic;">{kaddish_html}</p>'''

        html_content = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#ffffff; font-family:Georgia, 'Times New Roman', serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;">
<tr><td align="center" style="padding:40px 20px;">
<table width="100%" style="max-width:560px;">
    <tr><td style="padding-bottom:32px;">
        <h1 style="font-family:Georgia, serif; font-size:22px; font-weight:400; color:#3E2723; margin:0 0 16px;">
            {heading}
        </h1>
        {intro}

        <div style="background:#FAF9F6; border-left:3px solid #D2691E; padding:20px 24px; margin:0 0 24px; border-radius:0 6px 6px 0;">
            <h2 style="font-family:Georgia, serif; font-size:16px; font-weight:600; color:#3E2723; margin:0 0 8px;">
                Candle Lighting
            </h2>
            <p style="font-size:15px; color:#3E2723; line-height:1.7; margin:0;">
                It is customary to light a yahrzeit candle at sundown on the evening before the yahrzeit.
                The candle burns for approximately 24 hours, symbolizing the eternal light of the soul.
                <em>"The soul of a person is the lamp of God."</em> (Proverbs 20:27)
            </p>
        </div>

        <div style="background:#FAF9F6; padding:24px; border-radius:6px; margin:0 0 24px;">
            <h2 style="font-family:Georgia, serif; font-size:16px; font-weight:600; color:#3E2723; margin:0 0 12px;">
                Mourner's Kaddish
            </h2>
            {kaddish_section}
        </div>

        {memorial_link}
    </td></tr>
    <tr><td style="border-top:1px solid #eee; padding-top:24px;">
        <p style="font-size:13px; color:#999; text-align:center; margin:0 0 8px;">
            Yahrzeit reminders are free, always.
            <a href="{self.base_url}/sustain" style="color:#D2691E; text-decoration:none;">Help sustain Neshama</a>.
        </p>
        <p style="font-size:12px; color:#ccc; text-align:center; margin:0;">
            <a href="{unsubscribe_url}" style="color:#ccc; text-decoration:underline;">Unsubscribe from this reminder</a>
        </p>
    </td></tr>
</table>
</td></tr>
</table>
</body></html>'''

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Content

            message = Mail(
                from_email=('reminders@neshama.ca', 'Neshama'),
                to_emails=reminder['subscriber_email'],
                subject=subject,
            )
            message.content = [Content('text/html', html_content)]

            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            logging.info(f"[Yahrzeit] {reminder_type} reminder sent to {reminder['subscriber_email']} for {deceased_name} (status {response.status_code})")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logging.error(f"[Yahrzeit] Failed to send {reminder_type} reminder: {e}")
            return False

    # ── Get All Active Reminders (for processor) ──────────────

    def get_active_reminders(self):
        """Get all confirmed, non-unsubscribed reminders."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM yahrzeit_reminders
            WHERE confirmed = 1 AND unsubscribed_at IS NULL
        ''')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def update_reminder_sent(self, reminder_id, hebrew_year):
        """Mark a reminder as sent for a specific Hebrew year."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE yahrzeit_reminders
            SET last_reminder_sent = ?, last_reminder_hebrew_year = ?
            WHERE id = ?
        ''', (now, hebrew_year, reminder_id))
        conn.commit()
        conn.close()

    def update_reminder_timestamp(self, reminder_id):
        """Update last_reminder_sent timestamp only (for week-ahead reminders)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            'UPDATE yahrzeit_reminders SET last_reminder_sent = ? WHERE id = ?',
            (now, reminder_id)
        )
        conn.commit()
        conn.close()
