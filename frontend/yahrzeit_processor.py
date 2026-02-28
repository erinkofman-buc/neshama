#!/usr/bin/env python3
"""
Neshama Yahrzeit Reminder Processor
Daily scheduled job that checks for upcoming yahrzeits and sends reminders.
Called by APScheduler once daily at 9 AM Toronto time.
"""

import logging
from datetime import datetime, timedelta

import pytz

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TORONTO_TZ = pytz.timezone('America/Toronto')


def is_shabbat_pause():
    """Check if we're in the Shabbat pause window (Fri 6PM - Sat 9PM Toronto time)."""
    now = datetime.now(TORONTO_TZ)
    weekday = now.weekday()  # 0=Mon, 4=Fri, 5=Sat

    if weekday == 4 and now.hour >= 18:  # Friday after 6 PM
        return True
    if weekday == 5 and now.hour < 21:   # Saturday before 9 PM
        return True
    return False


def process_yahrzeit_reminders(db_path):
    """Process all active yahrzeit reminders and send emails as needed.
    Called daily by APScheduler.

    Logic:
    - For each confirmed, non-unsubscribed reminder:
      - Compute next yahrzeit Gregorian date
      - 7 days before: send week-ahead reminder (if not already sent this Hebrew year)
      - Day-of: send day-of reminder (if not already sent this Hebrew year)
    - Respects Shabbat pause
    - Tracks last_reminder_hebrew_year to prevent duplicate sends
    """
    if is_shabbat_pause():
        logging.info("[Yahrzeit] Shabbat pause — skipping reminder processing")
        return

    try:
        from yahrzeit_manager import YahrzeitManager
        mgr = YahrzeitManager(db_path=db_path)
    except Exception as e:
        logging.error(f"[Yahrzeit] Failed to initialize manager: {e}")
        return

    reminders = mgr.get_active_reminders()
    if not reminders:
        logging.info("[Yahrzeit] No active reminders to process")
        return

    today = datetime.now().date()
    sent_count = 0
    error_count = 0

    for reminder in reminders:
        try:
            h_month = reminder.get('hebrew_month')
            h_day = reminder.get('hebrew_day')

            if not h_month or not h_day:
                # Try to re-convert if Hebrew date data is missing
                result = mgr.convert_to_hebrew_date(reminder['date_of_death'])
                if result:
                    _, h_month, h_day, _ = result
                else:
                    continue

            # Get next yahrzeit date
            next_yahrzeit = mgr.get_next_yahrzeit_gregorian(h_month, h_day)
            if not next_yahrzeit:
                continue

            yahrzeit_date, hebrew_year = next_yahrzeit
            days_until = (yahrzeit_date - today).days

            # Skip if we already sent a reminder for this Hebrew year
            last_year = reminder.get('last_reminder_hebrew_year')
            if last_year and last_year >= hebrew_year:
                continue

            # Day-of reminder
            if days_until == 0:
                success = mgr.send_yahrzeit_reminder(reminder, 'day_of')
                if success:
                    mgr.update_reminder_sent(reminder['id'], hebrew_year)
                    sent_count += 1
                    logging.info(f"[Yahrzeit] Day-of reminder sent for {reminder['deceased_name']}")
                else:
                    error_count += 1

            # Week-ahead reminder (7 days before)
            elif days_until == 7:
                success = mgr.send_yahrzeit_reminder(reminder, 'week_ahead')
                if success:
                    # Don't update last_reminder_hebrew_year yet — save that for day-of
                    # But do update last_reminder_sent timestamp
                    mgr.update_reminder_timestamp(reminder['id'])
                    sent_count += 1
                    logging.info(f"[Yahrzeit] Week-ahead reminder sent for {reminder['deceased_name']}")
                else:
                    error_count += 1

        except Exception as e:
            logging.error(f"[Yahrzeit] Error processing reminder {reminder.get('id', '?')}: {e}")
            error_count += 1

    logging.info(f"[Yahrzeit] Processing complete: {sent_count} sent, {error_count} errors, {len(reminders)} total")
