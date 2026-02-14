#!/usr/bin/env python3
"""
Neshama Shiva Support Manager
Handles community-coordinated meal delivery during the shiva mourning period.
Privacy-first: addresses are only revealed to confirmed volunteers.
"""

import sqlite3
import uuid
import secrets
import os
from datetime import datetime, timedelta


class ShivaManager:
    def __init__(self, db_path='neshama.db'):
        self.db_path = db_path
        self.setup_database()

    # ── Database Setup ────────────────────────────────────────

    def setup_database(self):
        """Create shiva support tables idempotently."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_support (
                id TEXT PRIMARY KEY,
                obituary_id TEXT NOT NULL,
                organizer_name TEXT NOT NULL,
                organizer_email TEXT NOT NULL,
                organizer_phone TEXT,
                organizer_relationship TEXT NOT NULL,
                family_name TEXT NOT NULL,
                shiva_address TEXT NOT NULL,
                shiva_city TEXT,
                shiva_start_date TEXT NOT NULL,
                shiva_end_date TEXT NOT NULL,
                pause_shabbat INTEGER DEFAULT 1,
                dietary_notes TEXT,
                special_instructions TEXT,
                donation_url TEXT,
                donation_label TEXT,
                status TEXT DEFAULT 'active',
                magic_token TEXT NOT NULL,
                privacy_consent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                archived_at TEXT,
                FOREIGN KEY (obituary_id) REFERENCES obituaries(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meal_signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                volunteer_name TEXT NOT NULL,
                volunteer_email TEXT NOT NULL,
                volunteer_phone TEXT,
                meal_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                meal_description TEXT,
                num_servings INTEGER DEFAULT 4,
                privacy_consent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donation_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                url TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
            )
        ''')

        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shiva_obituary ON shiva_support(obituary_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shiva_status ON shiva_support(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meals_shiva ON meal_signups(shiva_support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meals_date ON meal_signups(meal_date)')

        conn.commit()
        conn.close()

    # ── Helpers ───────────────────────────────────────────────

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _is_shabbat(self, date_str):
        """Check if a date falls on Shabbat (Friday sunset to Saturday sunset).
        For simplicity: Friday and Saturday are marked as Shabbat days."""
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.weekday() in (4, 5)  # 4=Friday, 5=Saturday

    def _validate_date_range(self, start_date, end_date):
        """Validate that dates are proper ISO format and end >= start."""
        try:
            s = datetime.strptime(start_date, '%Y-%m-%d')
            e = datetime.strptime(end_date, '%Y-%m-%d')
            if e < s:
                return False, 'End date must be on or after start date'
            if (e - s).days > 30:
                return False, 'Shiva period cannot exceed 30 days'
            return True, None
        except ValueError:
            return False, 'Invalid date format. Use YYYY-MM-DD.'

    # ── Create Support Page ───────────────────────────────────

    def create_support(self, data):
        """Create a new shiva support page.
        Returns: {status, id, magic_token} or {status, error}
        """
        required = ['obituary_id', 'organizer_name', 'organizer_email',
                     'organizer_relationship', 'family_name', 'shiva_address',
                     'shiva_start_date', 'shiva_end_date']

        for field in required:
            if not data.get(field, '').strip():
                return {'status': 'error', 'message': f'Missing required field: {field}'}

        if not data.get('privacy_consent'):
            return {'status': 'error', 'message': 'Privacy consent is required'}

        # Validate dates
        valid, err = self._validate_date_range(data['shiva_start_date'], data['shiva_end_date'])
        if not valid:
            return {'status': 'error', 'message': err}

        # Check for duplicates
        dup = self.check_duplicate_organizer(data['obituary_id'], data['organizer_email'])
        if dup and dup.get('exists'):
            return {
                'status': 'duplicate',
                'message': 'A support page already exists for this memorial.',
                'existing_organizer_first_name': dup.get('organizer_first_name', ''),
                'existing_id': dup.get('id', ''),
                'created_at': dup.get('created_at', '')
            }

        support_id = str(uuid.uuid4())
        magic_token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO shiva_support (
                    id, obituary_id, organizer_name, organizer_email, organizer_phone,
                    organizer_relationship, family_name, shiva_address, shiva_city,
                    shiva_start_date, shiva_end_date, pause_shabbat,
                    dietary_notes, special_instructions, donation_url, donation_label,
                    status, magic_token, privacy_consent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
            ''', (
                support_id,
                data['obituary_id'].strip(),
                data['organizer_name'].strip(),
                data['organizer_email'].strip().lower(),
                data.get('organizer_phone', '').strip() or None,
                data['organizer_relationship'].strip(),
                data['family_name'].strip(),
                data['shiva_address'].strip(),
                data.get('shiva_city', '').strip() or None,
                data['shiva_start_date'].strip(),
                data['shiva_end_date'].strip(),
                1 if data.get('pause_shabbat', True) else 0,
                data.get('dietary_notes', '').strip() or None,
                data.get('special_instructions', '').strip() or None,
                data.get('donation_url', '').strip() or None,
                data.get('donation_label', '').strip() or None,
                magic_token,
                1,
                now
            ))
            conn.commit()
            return {
                'status': 'success',
                'id': support_id,
                'magic_token': magic_token
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    # ── Get Support (Public - no address) ─────────────────────

    def get_support_by_obituary(self, obituary_id):
        """Get active support page for an obituary. Address EXCLUDED."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, obituary_id, organizer_name, organizer_relationship,
                   family_name, shiva_city, shiva_start_date, shiva_end_date,
                   pause_shabbat, dietary_notes, special_instructions,
                   donation_url, donation_label, status, created_at
            FROM shiva_support
            WHERE obituary_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (obituary_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'status': 'success', 'data': dict(row)}
        return {'status': 'not_found', 'message': 'No active support page for this memorial'}

    def get_support_by_id(self, support_id):
        """Get support page by ID. Address EXCLUDED from public response."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, obituary_id, organizer_name, organizer_relationship,
                   family_name, shiva_city, shiva_start_date, shiva_end_date,
                   pause_shabbat, dietary_notes, special_instructions,
                   donation_url, donation_label, status, created_at
            FROM shiva_support
            WHERE id = ?
        ''', (support_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'status': 'success', 'data': dict(row)}
        return {'status': 'not_found', 'message': 'Support page not found'}

    # ── Get Support (Organizer - includes address) ────────────

    def get_support_for_organizer(self, support_id, magic_token):
        """Get full support data including address. Requires magic_token."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM shiva_support WHERE id = ? AND magic_token = ?
        ''', (support_id, magic_token))
        row = cursor.fetchone()
        conn.close()

        if row:
            data = dict(row)
            del data['magic_token']  # Never expose the token in responses
            return {'status': 'success', 'data': data}
        return {'status': 'error', 'message': 'Invalid support ID or token'}

    # ── Update Support (Organizer) ────────────────────────────

    def update_support(self, support_id, magic_token, data):
        """Update support page. Requires magic_token for authorization."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Verify ownership
        cursor.execute('SELECT id FROM shiva_support WHERE id = ? AND magic_token = ?',
                        (support_id, magic_token))
        if not cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Invalid support ID or token'}

        updatable = [
            'family_name', 'shiva_address', 'shiva_city', 'shiva_start_date',
            'shiva_end_date', 'pause_shabbat', 'dietary_notes',
            'special_instructions', 'donation_url', 'donation_label'
        ]

        sets = []
        vals = []
        for field in updatable:
            if field in data:
                sets.append(f'{field} = ?')
                val = data[field]
                if field == 'pause_shabbat':
                    val = 1 if val else 0
                vals.append(val)

        if not sets:
            conn.close()
            return {'status': 'error', 'message': 'No fields to update'}

        vals.append(support_id)
        cursor.execute(f"UPDATE shiva_support SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        conn.close()

        return {'status': 'success', 'message': 'Support page updated'}

    # ── Meal Signup ───────────────────────────────────────────

    def signup_meal(self, data):
        """Sign up to bring a meal. Returns shiva address on success."""
        required = ['shiva_support_id', 'volunteer_name', 'volunteer_email',
                     'meal_date', 'meal_type']

        for field in required:
            if not data.get(field, '').strip():
                return {'status': 'error', 'message': f'Missing required field: {field}'}

        if not data.get('privacy_consent'):
            return {'status': 'error', 'message': 'Privacy consent is required'}

        if data['meal_type'] not in ('Lunch', 'Dinner'):
            return {'status': 'error', 'message': 'Meal type must be Lunch or Dinner'}

        support_id = data['shiva_support_id'].strip()
        meal_date = data['meal_date'].strip()

        conn = self._get_conn()
        cursor = conn.cursor()

        # Get support page
        cursor.execute('SELECT * FROM shiva_support WHERE id = ? AND status = ?',
                        (support_id, 'active'))
        support = cursor.fetchone()
        if not support:
            conn.close()
            return {'status': 'error', 'message': 'Support page not found or is no longer active'}

        support = dict(support)

        # Validate date within shiva range
        try:
            md = datetime.strptime(meal_date, '%Y-%m-%d')
            sd = datetime.strptime(support['shiva_start_date'], '%Y-%m-%d')
            ed = datetime.strptime(support['shiva_end_date'], '%Y-%m-%d')
            if md < sd or md > ed:
                conn.close()
                return {'status': 'error', 'message': 'Selected date is outside the shiva period'}
        except ValueError:
            conn.close()
            return {'status': 'error', 'message': 'Invalid date format'}

        # Check Shabbat
        if support['pause_shabbat'] and self._is_shabbat(meal_date):
            conn.close()
            return {'status': 'error', 'message': 'This date falls on Shabbat and is not available for meal coordination'}

        # Check for duplicate signup (same date + meal type)
        cursor.execute('''
            SELECT id FROM meal_signups
            WHERE shiva_support_id = ? AND meal_date = ? AND meal_type = ?
        ''', (support_id, meal_date, data['meal_type']))
        if cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Someone has already signed up for this meal slot'}

        now = datetime.now().isoformat()
        try:
            cursor.execute('''
                INSERT INTO meal_signups (
                    shiva_support_id, volunteer_name, volunteer_email, volunteer_phone,
                    meal_date, meal_type, meal_description, num_servings,
                    privacy_consent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                support_id,
                data['volunteer_name'].strip(),
                data['volunteer_email'].strip().lower(),
                data.get('volunteer_phone', '').strip() or None,
                meal_date,
                data['meal_type'].strip(),
                data.get('meal_description', '').strip() or None,
                int(data.get('num_servings', 4)),
                1,
                now
            ))
            conn.commit()

            # Return address only to confirmed volunteer
            return {
                'status': 'success',
                'message': 'Thank you for signing up to help!',
                'signup_id': cursor.lastrowid,
                'shiva_address': support['shiva_address'],
                'shiva_city': support.get('shiva_city', ''),
                'special_instructions': support.get('special_instructions', '')
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    # ── Get Signups ───────────────────────────────────────────

    def get_signups(self, support_id):
        """Get all meal signups for a support page (for calendar display)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, meal_date, meal_type, volunteer_name, meal_description,
                   num_servings, created_at
            FROM meal_signups
            WHERE shiva_support_id = ?
            ORDER BY meal_date, meal_type
        ''', (support_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Only show first name of volunteer for privacy
        for row in rows:
            name = row.get('volunteer_name', '')
            row['volunteer_name'] = name.split()[0] if name else 'Anonymous'

        return {'status': 'success', 'data': rows}

    # ── Get Available Dates ───────────────────────────────────

    def get_available_dates(self, support_id):
        """Return date range with Shabbat and existing signups marked."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM shiva_support WHERE id = ?', (support_id,))
        support = cursor.fetchone()
        if not support:
            conn.close()
            return {'status': 'not_found', 'message': 'Support page not found'}

        support = dict(support)

        # Get existing signups
        cursor.execute('''
            SELECT meal_date, meal_type FROM meal_signups
            WHERE shiva_support_id = ?
        ''', (support_id,))
        signups = {}
        for row in cursor.fetchall():
            d = row['meal_date']
            if d not in signups:
                signups[d] = []
            signups[d].append(row['meal_type'])

        conn.close()

        # Build date list
        start = datetime.strptime(support['shiva_start_date'], '%Y-%m-%d')
        end = datetime.strptime(support['shiva_end_date'], '%Y-%m-%d')
        dates = []
        current = start

        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            is_shabbat = self._is_shabbat(date_str)
            booked = signups.get(date_str, [])

            dates.append({
                'date': date_str,
                'day_name': current.strftime('%A'),
                'is_shabbat': is_shabbat,
                'paused': is_shabbat and bool(support['pause_shabbat']),
                'lunch_taken': 'Lunch' in booked,
                'dinner_taken': 'Dinner' in booked
            })
            current += timedelta(days=1)

        return {'status': 'success', 'dates': dates}

    # ── Duplicate Detection ───────────────────────────────────

    def check_duplicate_organizer(self, obituary_id, organizer_email):
        """Check if a support page already exists for this obituary."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, organizer_name, created_at
            FROM shiva_support
            WHERE obituary_id = ? AND status = 'active'
            LIMIT 1
        ''', (obituary_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            row = dict(row)
            first_name = row['organizer_name'].split()[0] if row['organizer_name'] else ''
            return {
                'exists': True,
                'id': row['id'],
                'organizer_first_name': first_name,
                'created_at': row['created_at']
            }
        return {'exists': False}

    # ── Auto-Archive ──────────────────────────────────────────

    def archive_expired(self):
        """Archive support pages 30 days after shiva_end_date."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        now = datetime.now().isoformat()

        cursor.execute('''
            UPDATE shiva_support
            SET status = 'archived', archived_at = ?
            WHERE status = 'active' AND shiva_end_date < ?
        ''', (now, cutoff))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        if count > 0:
            print(f"[Shiva] Archived {count} expired support page(s)")
        return count
