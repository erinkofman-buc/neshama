#!/usr/bin/env python3
"""
Neshama Email Queue Processor — V2

Processes the email_log table every 15 minutes via APScheduler.
Handles 7 scheduled email types + retry logic for failed sends.

Email types:
  - day_before_reminder:  7 PM night before meal date
  - morning_of_reminder:  8 AM morning of meal date
  - uncovered_alert:      7 PM for tomorrow's uncovered slots
  - daily_summary:        8 PM daily during active shiva
  - guestbook_digest:     8 PM daily — new tribute summary for organizer
  - thank_you:            Day after shiva_end_date
  - (retry failed):       Any email_log row with status='failed' < 24h old

All emails: From updates@neshama.ca | Warm/white/dignified tone
"""

import html as html_mod
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta

import pytz

logger = logging.getLogger(__name__)

TORONTO_TZ = pytz.timezone('America/Toronto')
FROM_EMAIL = 'updates@neshama.ca'
FROM_NAME = 'Neshama'
MAX_RETRIES = 3


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


def _email_wrapper(inner_html):
    """Standard Neshama email wrapper — warm/white/dignified."""
    return f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;background:#ffffff;">
    {inner_html}
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""


def _format_date(date_str):
    """Format YYYY-MM-DD to 'Monday, February 26, 2026'."""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%A, %B %d, %Y')
    except Exception:
        return date_str


def _send_via_sendgrid(sendgrid_key, to_email, to_name, subject, html_content):
    """Send one email via SendGrid. Returns (success, sendgrid_message_id, error_msg)."""
    plain_text = _html_to_plain(html_content)

    if not sendgrid_key:
        logger.info(f"[EmailQueue] TEST MODE — would send to {to_email}: {subject}")
        return True, 'test-mode', None

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=subject,
            plain_text_content=Content(MimeType.text, plain_text),
            html_content=Content(MimeType.html, html_content),
        )
        sg = SendGridAPIClient(sendgrid_key)
        response = sg.send(message)
        msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
        return True, msg_id, None
    except Exception as e:
        logger.exception(f"[EmailQueue] SendGrid error sending to {to_email}")
        return False, None, str(e)


# ── Email body generators ────────────────────────────────────

def _day_before_reminder_html(vol_name, meal_type, meal_date, family_name,
                               address, drop_off_instructions):
    first = html_mod.escape(vol_name.split()[0]) if vol_name else 'Friend'
    instructions_block = ''
    if drop_off_instructions:
        instructions_block = f'''
        <div style="background:#FFF8E1;border:2px solid #FFD54F;border-radius:12px;padding:1.25rem;margin:1rem 0;">
            <p style="font-size:0.75rem;color:#F57F17;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Drop-off Instructions</p>
            <p style="font-size:1rem;margin:0;">{html_mod.escape(drop_off_instructions)}</p>
        </div>'''

    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Reminder for Tomorrow</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">Thank you for supporting the {html_mod.escape(family_name)} family.</p>
    </div>
    <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Your Meal</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(meal_type)} &middot; {_format_date(meal_date)}</p>
    </div>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Shiva Location</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(address)}</p>
    </div>
    {instructions_block}
    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">
        {html_mod.escape(first)}, your generosity means the world.
    </p>""")


def _morning_of_reminder_html(vol_name, meal_type, meal_date, family_name,
                               address, drop_off_instructions):
    first = html_mod.escape(vol_name.split()[0]) if vol_name else 'Friend'
    instructions_block = ''
    if drop_off_instructions:
        instructions_block = f'''
        <div style="background:#FFF8E1;border:2px solid #FFD54F;border-radius:12px;padding:1.25rem;margin:1rem 0;">
            <p style="font-size:0.75rem;color:#F57F17;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Drop-off Instructions</p>
            <p style="font-size:1rem;margin:0;">{html_mod.escape(drop_off_instructions)}</p>
        </div>'''

    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Today's the Day</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">A gentle reminder about your meal for the {html_mod.escape(family_name)} family.</p>
    </div>
    <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Your Meal</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(meal_type)} &middot; {_format_date(meal_date)}</p>
    </div>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Shiva Location</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(address)}</p>
    </div>
    {instructions_block}
    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">
        May their memory be a blessing.
    </p>""")


def _uncovered_alert_html(family_name, uncovered_dates, shiva_url):
    date_rows = ''
    for d in uncovered_dates:
        date_rows += f'<li style="margin:0.3rem 0;font-size:1rem;">{_format_date(d)}</li>'
    count = len(uncovered_dates)
    plural = 'date has' if count == 1 else 'dates have'

    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Meal Coverage Update</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(family_name)} shiva support page</p>
    </div>
    <div style="background:#FFF8E1;border:2px solid #FFD54F;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.95rem;color:#F57F17;font-weight:600;margin-bottom:0.5rem;">
            {count} upcoming {plural} no meal signups yet:
        </p>
        <ul style="padding-left:1.5rem;margin:0;">{date_rows}</ul>
    </div>
    <p style="text-align:center;font-size:0.95rem;color:#5c534a;margin:1rem 0;">
        Consider sharing the page link with friends and community members who may want to help.
    </p>
    <div style="text-align:center;margin-top:1rem;">
        <a href="{html_mod.escape(shiva_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View Meal Schedule</a>
    </div>""")


def _daily_summary_html(family_name, today_str, summary_data, shiva_url):
    """summary_data: dict with 'total_signups', 'today_meals', 'tomorrow_meals', 'uncovered_count'"""
    today_section = ''
    if summary_data.get('today_meals'):
        meals_html = ''
        for m in summary_data['today_meals']:
            meals_html += f'<li style="margin:0.3rem 0;">{html_mod.escape(m["volunteer_name"])} &middot; {html_mod.escape(m["meal_type"])}</li>'
        today_section = f'''
        <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;">
            <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Today's Meals</p>
            <ul style="padding-left:1.5rem;margin:0;">{meals_html}</ul>
        </div>'''
    else:
        today_section = '''
        <div style="background:#FFF8E1;border:2px solid #FFD54F;border-radius:12px;padding:1.25rem;margin:1rem 0;">
            <p style="font-size:0.95rem;color:#F57F17;margin:0;">No meals signed up for today.</p>
        </div>'''

    uncovered_note = ''
    if summary_data.get('uncovered_count', 0) > 0:
        uncovered_note = f'<p style="font-size:0.95rem;color:#F57F17;margin:0.5rem 0;">{summary_data["uncovered_count"]} upcoming date(s) still need coverage.</p>'

    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Daily Summary</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(family_name)} &middot; {_format_date(today_str)}</p>
    </div>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{summary_data.get('total_signups', 0)} total meal signups so far</p>
        {uncovered_note}
    </div>
    {today_section}
    <div style="text-align:center;margin-top:1rem;">
        <a href="{html_mod.escape(shiva_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View Dashboard</a>
    </div>""")


def _guestbook_digest_html(organizer_name, family_name, new_count, breakdown, memorial_url):
    """Guestbook digest email — warm summary of new tributes for the organizer."""
    first = html_mod.escape(organizer_name.split()[0]) if organizer_name else 'Friend'
    # Build breakdown line: e.g. "3 condolences, 1 memory, 1 candle lit"
    parts = []
    for entry_type, count in breakdown.items():
        if count <= 0:
            continue
        if entry_type == 'condolence':
            parts.append(f'{count} condolence{"s" if count != 1 else ""}')
        elif entry_type == 'memory':
            parts.append(f'{count} {"memories" if count != 1 else "memory"}')
        elif entry_type == 'candle':
            parts.append(f'{count} candle{"s" if count != 1 else ""} lit')
        else:
            parts.append(f'{count} {html_mod.escape(entry_type)}{"s" if count != 1 else ""}')
    breakdown_text = ', '.join(parts) if parts else f'{new_count} new entries'

    plural = 'entries' if new_count != 1 else 'entry'

    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">New Guestbook Entries</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">For the {html_mod.escape(family_name)} family memorial</p>
    </div>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;text-align:center;">
        <p style="font-size:1.2rem;font-weight:600;color:#3E2723;margin:0 0 0.5rem;">
            {new_count} new {plural} since yesterday
        </p>
        <p style="font-size:1rem;color:#5c534a;margin:0;">
            {html_mod.escape(breakdown_text)}
        </p>
    </div>
    <p style="text-align:center;font-size:0.95rem;color:#5c534a;margin:1rem 0;">
        {html_mod.escape(first)}, people are thinking of your family and
        taking the time to share their thoughts. Each entry is a small
        act of love.
    </p>
    <div style="text-align:center;margin-top:1rem;">
        <a href="{html_mod.escape(memorial_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View the Guestbook</a>
    </div>
    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">
        May their memory be a blessing.
    </p>""")


def _thank_you_html(vol_name, family_name, shiva_url):
    first = html_mod.escape(vol_name.split()[0]) if vol_name else 'Friend'
    return _email_wrapper(f"""
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.8rem;font-weight:400;color:#3E2723;margin:0;">Thank You, {first}</h1>
        <p style="color:#8a9a8d;font-size:1.1rem;margin-top:0.25rem;">Your kindness meant the world.</p>
    </div>
    <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;text-align:center;">
        <p style="font-size:1.05rem;color:#3E2723;margin:0;">
            The shiva period for the <strong>{html_mod.escape(family_name)}</strong> family has ended.
            Your support during this difficult time made a real difference.
        </p>
    </div>
    <p style="text-align:center;font-size:1rem;color:#5c534a;margin:1.5rem 0;">
        When community shows up, grief becomes a little more bearable.<br>
        Thank you for being part of that community.
    </p>
    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">
        May their memory be a blessing.
    </p>""")


# ── Queue helpers ─────────────────────────────────────────────

def _log_email(cursor, shiva_support_id, email_type, recipient_email,
               recipient_name=None, related_signup_id=None, scheduled_for=None):
    """Insert a row into email_log. Returns the new row id."""
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO email_log
            (shiva_support_id, email_type, recipient_email, recipient_name,
             related_signup_id, scheduled_for, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    ''', (shiva_support_id, email_type, recipient_email, recipient_name,
          related_signup_id, scheduled_for, now))
    return cursor.lastrowid


def _mark_sent(cursor, email_id, sendgrid_message_id=None):
    """Mark an email_log row as sent."""
    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE email_log SET status='sent', sent_at=?, sendgrid_message_id=?
        WHERE id=?
    ''', (now, sendgrid_message_id, email_id))


def _mark_failed(cursor, email_id, error_message):
    """Mark an email_log row as failed."""
    cursor.execute('''
        UPDATE email_log SET status='failed', error_message=? WHERE id=?
    ''', (error_message, email_id))


def _already_sent(cursor, shiva_support_id, email_type, extra_where='', extra_params=()):
    """Check if an email of this type was already sent (dedup)."""
    cursor.execute(f'''
        SELECT id FROM email_log
        WHERE shiva_support_id=? AND email_type=? AND status IN ('sent','pending')
        {extra_where}
    ''', (shiva_support_id, email_type) + extra_params)
    return cursor.fetchone() is not None


# ── The 7 email type processors ──────────────────────────────

def _process_day_before_reminders(cursor, sendgrid_key, now_toronto):
    """Day-before reminders: send at 7 PM for tomorrow's confirmed meals."""
    if now_toronto.hour < 19:
        return 0
    tomorrow = (now_toronto + timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT ms.id, ms.volunteer_name, ms.volunteer_email, ms.meal_type,
               ms.meal_date, ms.shiva_support_id,
               ss.family_name, ss.shiva_address, ss.shiva_city,
               ss.drop_off_instructions
        FROM meal_signups ms
        JOIN shiva_support ss ON ms.shiva_support_id = ss.id
        WHERE ms.meal_date = ?
          AND (ms.status IS NULL OR ms.status = 'confirmed')
          AND ms.reminder_day_before = 0
          AND ss.status = 'active'
    ''', (tomorrow,))
    rows = cursor.fetchall()
    sent = 0
    for row in rows:
        signup_id, vol_name, vol_email, meal_type, meal_date, support_id, \
            family_name, address, city, drop_off = row
        if city:
            address = f'{address}, {city}'

        html = _day_before_reminder_html(vol_name, meal_type, meal_date,
                                          family_name, address, drop_off)
        subject = f'Reminder: your meal for {family_name} is tomorrow'
        email_id = _log_email(cursor, support_id, 'day_before_reminder',
                              vol_email, vol_name, signup_id)
        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, vol_email,
                                              vol_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            cursor.execute('UPDATE meal_signups SET reminder_day_before=1 WHERE id=?',
                           (signup_id,))
            sent += 1
        else:
            _mark_failed(cursor, email_id, err)
    return sent


def _process_morning_of_reminders(cursor, sendgrid_key, now_toronto):
    """Morning-of reminders: send at 8 AM on the day of the meal."""
    if now_toronto.hour < 8:
        return 0
    today = now_toronto.strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT ms.id, ms.volunteer_name, ms.volunteer_email, ms.meal_type,
               ms.meal_date, ms.shiva_support_id,
               ss.family_name, ss.shiva_address, ss.shiva_city,
               ss.drop_off_instructions
        FROM meal_signups ms
        JOIN shiva_support ss ON ms.shiva_support_id = ss.id
        WHERE ms.meal_date = ?
          AND (ms.status IS NULL OR ms.status = 'confirmed')
          AND ms.reminder_morning_of = 0
          AND ss.status = 'active'
    ''', (today,))
    rows = cursor.fetchall()
    sent = 0
    for row in rows:
        signup_id, vol_name, vol_email, meal_type, meal_date, support_id, \
            family_name, address, city, drop_off = row
        if city:
            address = f'{address}, {city}'

        html = _morning_of_reminder_html(vol_name, meal_type, meal_date,
                                          family_name, address, drop_off)
        subject = f'Today: your meal for {family_name}'
        email_id = _log_email(cursor, support_id, 'morning_of_reminder',
                              vol_email, vol_name, signup_id)
        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, vol_email,
                                              vol_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            cursor.execute('UPDATE meal_signups SET reminder_morning_of=1 WHERE id=?',
                           (signup_id,))
            sent += 1
        else:
            _mark_failed(cursor, email_id, err)
    return sent


def _process_uncovered_alerts(cursor, sendgrid_key, now_toronto):
    """Uncovered-slot alerts: 7 PM, check tomorrow+ for 0 signups."""
    if now_toronto.hour < 19:
        return 0
    today = now_toronto.strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT id, family_name, organizer_email, organizer_name,
               shiva_start_date, shiva_end_date, notification_prefs, magic_token
        FROM shiva_support
        WHERE status = 'active'
          AND shiva_end_date >= ?
    ''', (today,))
    shivas = cursor.fetchall()
    sent = 0
    for shiva in shivas:
        shiva_id, family_name, org_email, org_name, start_date, end_date, \
            notif_prefs, magic_token = shiva

        # Check notification preference
        try:
            import json as _json
            prefs = _json.loads(notif_prefs) if notif_prefs else {}
        except Exception:
            prefs = {}
        if not prefs.get('uncovered_alert', True):
            continue

        # Dedup: skip if already sent today
        if _already_sent(cursor, shiva_id, 'uncovered_alert',
                         "AND DATE(created_at)=?", (today,)):
            continue

        # Find dates with no signups from tomorrow onward
        tomorrow = (now_toronto + timedelta(days=1)).strftime('%Y-%m-%d')
        try:
            sd = max(datetime.strptime(start_date, '%Y-%m-%d'),
                     datetime.strptime(tomorrow, '%Y-%m-%d'))
            ed = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            continue

        uncovered = []
        d = sd
        while d <= ed:
            date_str = d.strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM meal_signups
                WHERE shiva_support_id=? AND meal_date=?
                  AND (status IS NULL OR status='confirmed')
            ''', (shiva_id, date_str))
            if cursor.fetchone()[0] == 0:
                uncovered.append(date_str)
            d += timedelta(days=1)

        if not uncovered:
            continue

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        shiva_url = f'{base_url}/shiva/{shiva_id}?token={magic_token}'
        html = _uncovered_alert_html(family_name, uncovered, shiva_url)
        subject = f'{len(uncovered)} uncovered meal date{"s" if len(uncovered) > 1 else ""} — {family_name}'
        email_id = _log_email(cursor, shiva_id, 'uncovered_alert', org_email, org_name)
        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, org_email,
                                              org_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            sent += 1
        else:
            _mark_failed(cursor, email_id, err)
    return sent


def _process_daily_summaries(cursor, sendgrid_key, now_toronto):
    """Daily organizer summary: 8 PM during active shiva period."""
    if now_toronto.hour < 20:
        return 0
    today = now_toronto.strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT id, family_name, organizer_email, organizer_name,
               shiva_start_date, shiva_end_date, notification_prefs, magic_token
        FROM shiva_support
        WHERE status = 'active'
          AND shiva_start_date <= ?
          AND shiva_end_date >= ?
    ''', (today, today))
    shivas = cursor.fetchall()
    sent = 0
    for shiva in shivas:
        shiva_id, family_name, org_email, org_name, start_date, end_date, \
            notif_prefs, magic_token = shiva

        try:
            import json as _json
            prefs = _json.loads(notif_prefs) if notif_prefs else {}
        except Exception:
            prefs = {}
        if not prefs.get('daily_summary', True):
            continue

        if _already_sent(cursor, shiva_id, 'daily_summary',
                         "AND DATE(created_at)=?", (today,)):
            continue

        # Gather summary data
        cursor.execute('SELECT COUNT(*) FROM meal_signups WHERE shiva_support_id=? AND (status IS NULL OR status=\'confirmed\')',
                       (shiva_id,))
        total = cursor.fetchone()[0]

        cursor.execute('''
            SELECT volunteer_name, meal_type FROM meal_signups
            WHERE shiva_support_id=? AND meal_date=? AND (status IS NULL OR status='confirmed')
        ''', (shiva_id, today))
        today_meals = [{'volunteer_name': r[0], 'meal_type': r[1]} for r in cursor.fetchall()]

        # Count uncovered future dates
        try:
            ed = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            continue
        uncovered_count = 0
        d = now_toronto + timedelta(days=1)
        while d.strftime('%Y-%m-%d') <= end_date:
            date_str = d.strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT COUNT(*) FROM meal_signups
                WHERE shiva_support_id=? AND meal_date=? AND (status IS NULL OR status='confirmed')
            ''', (shiva_id, date_str))
            if cursor.fetchone()[0] == 0:
                uncovered_count += 1
            d += timedelta(days=1)

        summary_data = {
            'total_signups': total,
            'today_meals': today_meals,
            'uncovered_count': uncovered_count,
        }
        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        shiva_url = f'{base_url}/shiva/{shiva_id}?token={magic_token}'
        html = _daily_summary_html(family_name, today, summary_data, shiva_url)
        subject = f'Daily summary — {family_name} shiva'
        email_id = _log_email(cursor, shiva_id, 'daily_summary', org_email, org_name)
        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, org_email,
                                              org_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            sent += 1
        else:
            _mark_failed(cursor, email_id, err)
    return sent


def _process_guestbook_digests(cursor, sendgrid_key, now_toronto):
    """Guestbook digest: 8 PM, notify organizer of new tributes since last digest."""
    if now_toronto.hour < 20:
        return 0
    today = now_toronto.strftime('%Y-%m-%d')
    # Active shiva_support entries that have a linked obituary (guestbook)
    cursor.execute('''
        SELECT id, obituary_id, family_name, organizer_email, organizer_name,
               notification_prefs, magic_token
        FROM shiva_support
        WHERE status = 'active'
          AND obituary_id IS NOT NULL
    ''')
    shivas = cursor.fetchall()
    sent = 0
    for shiva in shivas:
        shiva_id, obituary_id, family_name, org_email, org_name, \
            notif_prefs, magic_token = shiva

        # Check notification preference
        try:
            import json as _json
            prefs = _json.loads(notif_prefs) if notif_prefs else {}
        except Exception:
            prefs = {}
        if not prefs.get('guestbook_digest', True):
            continue

        # Dedup: skip if already sent today
        if _already_sent(cursor, shiva_id, 'guestbook_digest',
                         "AND DATE(created_at)=?", (today,)):
            continue

        # Determine cutoff: last digest sent_at, or 24h ago
        cursor.execute('''
            SELECT sent_at FROM email_log
            WHERE shiva_support_id=? AND email_type='guestbook_digest'
              AND status='sent'
            ORDER BY sent_at DESC LIMIT 1
        ''', (shiva_id,))
        last_row = cursor.fetchone()
        if last_row and last_row[0]:
            cutoff = last_row[0]
        else:
            cutoff = (now_toronto - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')

        # Count new tributes since cutoff, grouped by entry_type
        cursor.execute('''
            SELECT entry_type, COUNT(*) FROM tributes
            WHERE obituary_id = ? AND created_at > ?
            GROUP BY entry_type
        ''', (obituary_id, cutoff))
        type_rows = cursor.fetchall()
        if not type_rows:
            continue

        breakdown = {}
        new_count = 0
        for entry_type, count in type_rows:
            breakdown[entry_type or 'tribute'] = count
            new_count += count

        if new_count == 0:
            continue

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        memorial_url = f'{base_url}/memorial/{obituary_id}'
        html = _guestbook_digest_html(org_name, family_name, new_count,
                                       breakdown, memorial_url)
        subject = f'{new_count} new guestbook {"entries" if new_count != 1 else "entry"} for {family_name}'
        email_id = _log_email(cursor, shiva_id, 'guestbook_digest',
                              org_email, org_name)
        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, org_email,
                                              org_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            sent += 1
        else:
            _mark_failed(cursor, email_id, err)
    return sent


def _process_thank_yous(cursor, sendgrid_key, now_toronto):
    """Thank-you emails: sent day after shiva_end_date to all volunteers."""
    yesterday = (now_toronto - timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT id, family_name, shiva_end_date
        FROM shiva_support
        WHERE status = 'active'
          AND shiva_end_date = ?
    ''', (yesterday,))
    shivas = cursor.fetchall()
    sent = 0
    for shiva in shivas:
        shiva_id, family_name, end_date = shiva

        # Dedup: skip if thank_you already sent for this shiva
        if _already_sent(cursor, shiva_id, 'thank_you'):
            continue

        # Get all volunteers who signed up
        cursor.execute('''
            SELECT DISTINCT volunteer_name, volunteer_email, id
            FROM meal_signups
            WHERE shiva_support_id=? AND (status IS NULL OR status='confirmed')
        ''', (shiva_id,))
        volunteers = cursor.fetchall()

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        shiva_url = f'{base_url}/shiva/{shiva_id}'
        for vol in volunteers:
            vol_name, vol_email, signup_id = vol
            html = _thank_you_html(vol_name, family_name, shiva_url)
            subject = f'Thank you for supporting the {family_name} family'
            email_id = _log_email(cursor, shiva_id, 'thank_you',
                                  vol_email, vol_name, signup_id)
            ok, msg_id, err = _send_via_sendgrid(sendgrid_key, vol_email,
                                                  vol_name, subject, html)
            if ok:
                _mark_sent(cursor, email_id, msg_id)
                sent += 1
            else:
                _mark_failed(cursor, email_id, err)

        # Archive the shiva page after sending thank-yous
        cursor.execute("UPDATE shiva_support SET status='archived', archived_at=? WHERE id=?",
                       (datetime.now().isoformat(), shiva_id))
    return sent


def _process_retries(cursor, sendgrid_key):
    """Retry failed emails from the last 24 hours (max 3 attempts per email)."""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    cursor.execute('''
        SELECT el.id, el.shiva_support_id, el.email_type, el.recipient_email,
               el.recipient_name, el.related_signup_id
        FROM email_log el
        WHERE el.status = 'failed'
          AND el.created_at > ?
    ''', (cutoff,))
    failed_rows = cursor.fetchall()
    retried = 0
    for row in failed_rows:
        email_id, shiva_id, email_type, recipient_email, recipient_name, signup_id = row

        # Count previous attempts (include skipped to avoid re-counting)
        cursor.execute('''
            SELECT COUNT(*) FROM email_log
            WHERE shiva_support_id=? AND email_type=? AND recipient_email=?
              AND related_signup_id IS ? AND status IN ('sent','failed','skipped')
        ''', (shiva_id, email_type, recipient_email, signup_id))
        attempts = cursor.fetchone()[0]
        if attempts >= MAX_RETRIES:
            cursor.execute("UPDATE email_log SET status='skipped' WHERE id=?", (email_id,))
            continue

        # Re-generate the email content based on type
        # For retries, we rebuild the email from the original data
        html, subject = _rebuild_email_for_retry(cursor, shiva_id, email_type,
                                                  recipient_email, recipient_name,
                                                  signup_id)
        if not html:
            cursor.execute("UPDATE email_log SET status='skipped', error_message='Could not rebuild email' WHERE id=?",
                           (email_id,))
            continue

        ok, msg_id, err = _send_via_sendgrid(sendgrid_key, recipient_email,
                                              recipient_name, subject, html)
        if ok:
            _mark_sent(cursor, email_id, msg_id)
            retried += 1
        else:
            _mark_failed(cursor, email_id, err)
    return retried


def _rebuild_email_for_retry(cursor, shiva_id, email_type, recipient_email,
                              recipient_name, signup_id):
    """Rebuild email HTML+subject from stored data for retry. Returns (html, subject) or (None, None)."""
    cursor.execute('SELECT family_name, shiva_address, shiva_city, drop_off_instructions, magic_token FROM shiva_support WHERE id=?',
                   (shiva_id,))
    shiva = cursor.fetchone()
    if not shiva:
        return None, None
    family_name, address, city, drop_off, magic_token = shiva
    if city:
        address = f'{address}, {city}'
    base_url = os.environ.get('BASE_URL', 'https://neshama.ca')

    if email_type in ('day_before_reminder', 'morning_of_reminder') and signup_id:
        cursor.execute('SELECT meal_type, meal_date FROM meal_signups WHERE id=?', (signup_id,))
        meal = cursor.fetchone()
        if not meal:
            return None, None
        meal_type, meal_date = meal
        if email_type == 'day_before_reminder':
            html = _day_before_reminder_html(recipient_name, meal_type, meal_date,
                                              family_name, address, drop_off)
            subject = f'Reminder: your meal for {family_name} is tomorrow'
        else:
            html = _morning_of_reminder_html(recipient_name, meal_type, meal_date,
                                              family_name, address, drop_off)
            subject = f'Today: your meal for {family_name}'
        return html, subject

    elif email_type == 'thank_you':
        shiva_url = f'{base_url}/shiva/{shiva_id}'
        html = _thank_you_html(recipient_name, family_name, shiva_url)
        return html, f'Thank you for supporting the {family_name} family'

    elif email_type == 'uncovered_alert':
        shiva_url = f'{base_url}/shiva/{shiva_id}?token={magic_token}'
        html = _uncovered_alert_html(family_name, ['(see page)'], shiva_url)
        return html, f'Uncovered meal dates — {family_name}'

    elif email_type == 'daily_summary':
        shiva_url = f'{base_url}/shiva/{shiva_id}?token={magic_token}'
        html = _daily_summary_html(family_name, datetime.now().strftime('%Y-%m-%d'),
                                    {'total_signups': 0, 'today_meals': [], 'uncovered_count': 0},
                                    shiva_url)
        return html, f'Daily summary — {family_name} shiva'

    elif email_type == 'guestbook_digest':
        # For retry, fetch obituary_id and rebuild with current new-tribute counts
        cursor.execute('SELECT obituary_id FROM shiva_support WHERE id=?', (shiva_id,))
        obit_row = cursor.fetchone()
        if not obit_row or not obit_row[0]:
            return None, None
        obituary_id = obit_row[0]
        # Use 24h window for retry rebuild
        cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
        cursor.execute('''
            SELECT entry_type, COUNT(*) FROM tributes
            WHERE obituary_id = ? AND created_at > ?
            GROUP BY entry_type
        ''', (obituary_id, cutoff))
        type_rows = cursor.fetchall()
        breakdown = {}
        new_count = 0
        for entry_type, count in type_rows:
            breakdown[entry_type or 'tribute'] = count
            new_count += count
        if new_count == 0:
            return None, None
        memorial_url = f'{base_url}/memorial/{obituary_id}'
        html = _guestbook_digest_html(recipient_name, family_name, new_count,
                                       breakdown, memorial_url)
        plural = 'entries' if new_count != 1 else 'entry'
        return html, f'{new_count} new guestbook {plural} for {family_name}'

    return None, None


# ── Main entry point ──────────────────────────────────────────

def process_email_queue(db_path):
    """Process all pending scheduled emails. Called by APScheduler every 15 minutes.

    Processes 7 email types in order:
      1. Day-before reminders (7 PM)
      2. Morning-of reminders (8 AM)
      3. Uncovered-slot alerts (7 PM)
      4. Daily organizer summaries (8 PM)
      5. Guestbook digest (8 PM)
      6. Thank-you emails (day after shiva ends)
      7. Retry failed sends (<24h old, max 3 attempts)
    """
    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
    now_toronto = datetime.now(TORONTO_TZ)

    # Respect Shabbat
    weekday = now_toronto.weekday()
    if (weekday == 4 and now_toronto.hour >= 18) or (weekday == 5 and now_toronto.hour < 21):
        logger.info("[EmailQueue] Shabbat — email processing paused")
        return {'paused': 'shabbat'}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    results = {}
    try:
        results['day_before_reminders'] = _process_day_before_reminders(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['morning_of_reminders'] = _process_morning_of_reminders(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['uncovered_alerts'] = _process_uncovered_alerts(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['daily_summaries'] = _process_daily_summaries(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['guestbook_digests'] = _process_guestbook_digests(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['thank_yous'] = _process_thank_yous(cursor, sendgrid_key, now_toronto)
        conn.commit()

        results['retries'] = _process_retries(cursor, sendgrid_key)
        conn.commit()
    except Exception:
        logger.exception("[EmailQueue] Error processing email queue")
        conn.rollback()
    finally:
        conn.close()

    total = sum(v for v in results.values() if isinstance(v, int))
    if total > 0:
        logger.info(f"[EmailQueue] Processed {total} emails: {results}")
    return results


def log_immediate_email(db_path, shiva_support_id, email_type, recipient_email,
                        recipient_name=None, related_signup_id=None,
                        sendgrid_message_id=None, status='sent'):
    """Log an immediately-sent email (signup confirmations, access requests, etc.)
    to email_log for audit trail. Called after synchronous sends."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO email_log
            (shiva_support_id, email_type, recipient_email, recipient_name,
             related_signup_id, status, sent_at, sendgrid_message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (shiva_support_id, email_type, recipient_email, recipient_name,
          related_signup_id, status, now, sendgrid_message_id, now))
    conn.commit()
    conn.close()
