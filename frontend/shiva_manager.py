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
import json
import threading
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


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
                obituary_id TEXT,
                organizer_name TEXT NOT NULL,
                organizer_email TEXT NOT NULL,
                organizer_phone TEXT,
                organizer_relationship TEXT NOT NULL,
                family_name TEXT NOT NULL,
                shiva_address TEXT NOT NULL,
                shiva_city TEXT,
                shiva_sub_area TEXT,
                shiva_start_date TEXT NOT NULL,
                shiva_end_date TEXT NOT NULL,
                pause_shabbat INTEGER DEFAULT 1,
                guests_per_meal INTEGER DEFAULT 20,
                dietary_notes TEXT,
                special_instructions TEXT,
                donation_url TEXT,
                donation_label TEXT,
                status TEXT DEFAULT 'active',
                magic_token TEXT NOT NULL,
                privacy_consent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                archived_at TEXT
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
                will_serve INTEGER DEFAULT 0,
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                obituary_id TEXT,
                created_at TEXT NOT NULL
            )
        ''')

        # Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shiva_obituary ON shiva_support(obituary_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_shiva_status ON shiva_support(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meals_shiva ON meal_signups(shiva_support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_meals_date ON meal_signups(meal_date)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                reporter_name TEXT NOT NULL,
                reporter_email TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS caterer_partners (
                id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                website TEXT,
                instagram TEXT,
                delivery_area TEXT NOT NULL,
                kosher_level TEXT NOT NULL DEFAULT 'not_kosher',
                has_delivery INTEGER DEFAULT 0,
                has_online_ordering INTEGER DEFAULT 0,
                price_range TEXT DEFAULT '$$',
                shiva_menu_description TEXT NOT NULL,
                logo_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_id TEXT NOT NULL,
                requester_name TEXT NOT NULL,
                requester_email TEXT NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'pending',
                access_token TEXT,
                organizer_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                responded_at TEXT,
                FOREIGN KEY (shiva_id) REFERENCES shiva_support(id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_caterer_status ON caterer_partners(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_caterer_email ON caterer_partners(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analytics_event ON shiva_analytics(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analytics_date ON shiva_analytics(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reports_shiva ON shiva_reports(shiva_support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_shiva ON shiva_access_requests(shiva_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_token ON shiva_access_requests(access_token)')

        # Migration: add guests_per_meal column if missing (for existing databases)
        try:
            cursor.execute('SELECT guests_per_meal FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE shiva_support ADD COLUMN guests_per_meal INTEGER DEFAULT 20')

        # Migration: add privacy column if missing
        try:
            cursor.execute('SELECT privacy FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE shiva_support ADD COLUMN privacy TEXT DEFAULT 'public'")

        # Migration: add recommended_vendors column if missing
        try:
            cursor.execute('SELECT recommended_vendors FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE shiva_support ADD COLUMN recommended_vendors TEXT')

        # Migration: add will_serve column to meal_signups if missing
        try:
            cursor.execute('SELECT will_serve FROM meal_signups LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE meal_signups ADD COLUMN will_serve INTEGER DEFAULT 0')

        # Migration: add organizer_update column if missing
        try:
            cursor.execute('SELECT organizer_update FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE shiva_support ADD COLUMN organizer_update TEXT')

        # Migration: add family_notes column if missing
        try:
            cursor.execute('SELECT family_notes FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE shiva_support ADD COLUMN family_notes TEXT')

        # Migration: convert 'unknown' obituary_ids to NULL
        cursor.execute("UPDATE shiva_support SET obituary_id = NULL WHERE obituary_id IN ('unknown', '')")

        # Unique index: only one active shiva page per obituary
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_shiva_obituary_unique
            ON shiva_support(obituary_id)
            WHERE obituary_id IS NOT NULL AND status = 'active'
        ''')

        # ── V2 Migrations ────────────────────────────────────────

        # V2: shiva_support — 7 new columns
        for col, defn in [
            ('drop_off_instructions', 'TEXT'),
            ('notification_prefs', "TEXT DEFAULT '{\"instant\":true,\"daily_summary\":true,\"uncovered_alert\":true}'"),
            ('verification_status', "TEXT DEFAULT 'verified'"),
            ('verification_token', 'TEXT'),
            ('verified_at', 'TEXT'),
            ('source', "TEXT DEFAULT 'web_standalone'"),
            ('is_demo', 'INTEGER DEFAULT 0'),
        ]:
            try:
                cursor.execute(f'SELECT {col} FROM shiva_support LIMIT 1')
            except sqlite3.OperationalError:
                cursor.execute(f'ALTER TABLE shiva_support ADD COLUMN {col} {defn}')

        # V2: meal_signups — 5 new columns
        for col, defn in [
            ('signup_group_id', 'TEXT'),
            ('status', "TEXT DEFAULT 'confirmed'"),
            ('cancelled_at', 'TEXT'),
            ('reminder_day_before', 'INTEGER DEFAULT 0'),
            ('reminder_morning_of', 'INTEGER DEFAULT 0'),
        ]:
            try:
                cursor.execute(f'SELECT {col} FROM meal_signups LIMIT 1')
            except sqlite3.OperationalError:
                cursor.execute(f'ALTER TABLE meal_signups ADD COLUMN {col} {defn}')

        # V2: shiva_co_organizers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_co_organizers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                magic_token TEXT NOT NULL,
                invited_by_email TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                accepted_at TEXT,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_coorg_shiva ON shiva_co_organizers(shiva_support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_coorg_email ON shiva_co_organizers(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_coorg_token ON shiva_co_organizers(magic_token)')

        # V2: email_log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                email_type TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                recipient_name TEXT,
                related_signup_id INTEGER,
                scheduled_for TEXT,
                sent_at TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                sendgrid_message_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id),
                FOREIGN KEY (related_signup_id) REFERENCES meal_signups(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_shiva ON email_log(shiva_support_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_status ON email_log(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_scheduled ON email_log(scheduled_for)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_type ON email_log(email_type)')

        # ── V3 Migrations ────────────────────────────────────────

        # V3: meal_signups — alternative contribution columns
        for col, defn in [
            ('alternative_type', 'TEXT'),
            ('alternative_note', 'TEXT'),
        ]:
            try:
                cursor.execute(f'SELECT {col} FROM meal_signups LIMIT 1')
            except sqlite3.OperationalError:
                cursor.execute(f'ALTER TABLE meal_signups ADD COLUMN {col} {defn}')

        # V3: shiva_updates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shiva_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shiva_support_id TEXT NOT NULL,
                message TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_updates_shiva ON shiva_updates(shiva_support_id)')

        # V3: thank_you_sent column on shiva_support
        try:
            cursor.execute('SELECT thank_you_sent FROM shiva_support LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE shiva_support ADD COLUMN thank_you_sent INTEGER DEFAULT 0')

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

    MAX_FIELD_LENGTH = 500
    MAX_TEXT_LENGTH = 2000

    def _sanitize_text(self, value, max_len=None):
        """Truncate text fields to prevent abuse."""
        if not value:
            return value
        limit = max_len or self.MAX_FIELD_LENGTH
        return str(value)[:limit].strip()

    def _validate_url(self, url):
        """Validate URL starts with http:// or https:// to prevent javascript: XSS."""
        if not url:
            return url
        url = url.strip()
        if url.lower().startswith(('http://', 'https://')):
            return url
        return None

    def _validate_email(self, email):
        """Basic server-side email validation."""
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return None
        return email.strip().lower()[:254]

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

    def _normalize_obituary_id(self, obit_id):
        """Normalize obituary_id: treat 'unknown', empty string as None."""
        if not obit_id or str(obit_id).strip() in ('unknown', ''):
            return None
        return str(obit_id).strip()

    def create_support(self, data):
        """Create a new shiva support page.
        Returns: {status, id, magic_token} or {status, error}
        """
        required = ['organizer_name', 'organizer_email',
                     'organizer_relationship', 'family_name', 'shiva_address',
                     'shiva_start_date', 'shiva_end_date']

        for field in required:
            if not data.get(field, '').strip():
                return {'status': 'error', 'message': f'Missing required field: {field}'}

        if not data.get('privacy_consent'):
            return {'status': 'error', 'message': 'Privacy consent is required'}

        # Validate email
        clean_email = self._validate_email(data.get('organizer_email', ''))
        if not clean_email:
            return {'status': 'error', 'message': 'Invalid email address'}

        # Validate donation_url (prevent javascript: XSS)
        donation_url = self._validate_url(data.get('donation_url', '').strip())
        if data.get('donation_url', '').strip() and not donation_url:
            return {'status': 'error', 'message': 'Donation URL must start with http:// or https://'}

        # Validate dates
        valid, err = self._validate_date_range(data['shiva_start_date'], data['shiva_end_date'])
        if not valid:
            return {'status': 'error', 'message': err}

        # Normalize obituary_id
        obit_id = self._normalize_obituary_id(data.get('obituary_id'))

        # Check for duplicates by obituary_id
        if obit_id:
            dup = self.check_duplicate_organizer(obit_id, data['organizer_email'])
            if dup and dup.get('exists'):
                return {
                    'status': 'duplicate',
                    'message': 'A support page already exists for this memorial.',
                    'existing_organizer_first_name': dup.get('organizer_first_name', ''),
                    'existing_id': dup.get('id', ''),
                    'created_at': dup.get('created_at', '')
                }

        # Fuzzy name match for standalone pages (no obituary_id)
        if not obit_id and not data.get('_skip_similar'):
            similar = self.find_similar_shiva(data['family_name'])
            if similar:
                return {
                    'status': 'similar_found',
                    'message': 'We found existing shiva pages with a similar family name.',
                    'matches': similar
                }

        support_id = str(uuid.uuid4())
        magic_token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()

        conn = self._get_conn()
        cursor = conn.cursor()

        privacy = data.get('privacy', 'public')
        if privacy not in ('public', 'private'):
            privacy = 'public'

        # Validate recommended_vendors (JSON array of slugs, max 5)
        recommended_vendors = None
        raw_vendors = data.get('recommended_vendors')
        if raw_vendors and isinstance(raw_vendors, list):
            # Sanitize: only keep strings, max 5
            clean_slugs = [str(s).strip()[:100] for s in raw_vendors if s][:5]
            if clean_slugs:
                recommended_vendors = json.dumps(clean_slugs)

        # V2 fields
        drop_off = self._sanitize_text(data.get('drop_off_instructions', ''), self.MAX_TEXT_LENGTH) or None
        source = data.get('source', 'web_standalone')
        if source not in ('web_claim', 'web_standalone', 'funeral_home', 'auto_created'):
            source = 'web_standalone'

        # V2: Email verification — generate token, set status to 'pending'
        verification_token = secrets.token_urlsafe(32)
        verification_status = 'pending'

        try:
            cursor.execute('''
                INSERT INTO shiva_support (
                    id, obituary_id, organizer_name, organizer_email, organizer_phone,
                    organizer_relationship, family_name, shiva_address, shiva_city, shiva_sub_area,
                    shiva_start_date, shiva_end_date, pause_shabbat, guests_per_meal,
                    dietary_notes, special_instructions, donation_url, donation_label,
                    status, magic_token, privacy_consent, privacy, recommended_vendors,
                    family_notes, created_at,
                    drop_off_instructions, source, verification_status, verification_token
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                support_id,
                obit_id,
                self._sanitize_text(data['organizer_name'], 200),
                clean_email,
                self._sanitize_text(data.get('organizer_phone', ''), 30) or None,
                self._sanitize_text(data['organizer_relationship'], 50),
                self._sanitize_text(data['family_name'], 200),
                self._sanitize_text(data['shiva_address']),
                self._sanitize_text(data.get('shiva_city', ''), 100) or None,
                self._sanitize_text(data.get('shiva_sub_area', ''), 100) or None,
                data['shiva_start_date'].strip()[:10],
                data['shiva_end_date'].strip()[:10],
                1 if data.get('pause_shabbat', True) else 0,
                max(1, min(200, int(data.get('guests_per_meal', 20)))),
                self._sanitize_text(data.get('dietary_notes', ''), self.MAX_TEXT_LENGTH) or None,
                self._sanitize_text(data.get('special_instructions', ''), self.MAX_TEXT_LENGTH) or None,
                donation_url,
                self._sanitize_text(data.get('donation_label', ''), 200) or None,
                magic_token,
                1,
                privacy,
                recommended_vendors,
                self._sanitize_text(data.get('family_notes', ''), self.MAX_TEXT_LENGTH) or None,
                now,
                drop_off,
                source,
                verification_status,
                verification_token,
            ))
            conn.commit()
            return {
                'status': 'success',
                'id': support_id,
                'magic_token': magic_token,
                'verification_token': verification_token,
                'organizer_email': clean_email,
                'family_name': self._sanitize_text(data['family_name'], 200),
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    # ── Get Support (Public - no address) ─────────────────────

    def get_support_by_obituary(self, obituary_id):
        """Get active support page for an obituary. Address EXCLUDED."""
        if not obituary_id or obituary_id in ('unknown', ''):
            return {'status': 'not_found', 'message': 'No obituary ID provided'}
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, obituary_id, organizer_name, organizer_relationship,
                   family_name, shiva_city, shiva_sub_area, shiva_start_date, shiva_end_date,
                   pause_shabbat, guests_per_meal, dietary_notes, special_instructions,
                   donation_url, donation_label, status, privacy, recommended_vendors,
                   organizer_update, family_notes, created_at
            FROM shiva_support
            WHERE obituary_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
        ''', (obituary_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'status': 'success', 'data': dict(row)}
        return {'status': 'not_found', 'message': 'No active support page for this memorial'}

    def get_support_by_id(self, support_id, access_token=None):
        """Get support page by ID. Address EXCLUDED from public response.
        For private pages, dietary_notes and special_instructions are also excluded
        unless a valid access_token is provided."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, obituary_id, organizer_name, organizer_relationship,
                   family_name, shiva_city, shiva_sub_area, shiva_start_date, shiva_end_date,
                   pause_shabbat, guests_per_meal, dietary_notes, special_instructions,
                   donation_url, donation_label, status, privacy, recommended_vendors,
                   organizer_update, family_notes, created_at
            FROM shiva_support
            WHERE id = ?
        ''', (support_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'status': 'not_found', 'message': 'Support page not found'}

        data = dict(row)

        # For private pages, check access token
        if data.get('privacy') == 'private':
            has_access = False
            if access_token:
                cursor.execute('''
                    SELECT id FROM shiva_access_requests
                    WHERE shiva_id = ? AND access_token = ? AND status = 'approved'
                ''', (support_id, access_token))
                has_access = cursor.fetchone() is not None

            if not has_access:
                # Return limited data for private pages
                conn.close()
                return {
                    'status': 'success',
                    'data': {
                        'id': data['id'],
                        'obituary_id': data['obituary_id'],
                        'organizer_name': data['organizer_name'],
                        'organizer_relationship': data['organizer_relationship'],
                        'family_name': data['family_name'],
                        'shiva_city': data.get('shiva_city'),
                        'shiva_sub_area': data.get('shiva_sub_area'),
                        'shiva_start_date': data['shiva_start_date'],
                        'shiva_end_date': data['shiva_end_date'],
                        'status': data['status'],
                        'privacy': 'private',
                        'created_at': data['created_at'],
                    },
                    'access': 'limited'
                }
            else:
                data['access'] = 'granted'

        conn.close()
        return {'status': 'success', 'data': data}

    # ── Get Support (Organizer - includes address) ────────────

    def get_support_for_organizer(self, support_id, magic_token):
        """Get full support data including address. Requires magic_token.
        V2: Also accepts co-organizer tokens."""
        conn = self._get_conn()
        cursor = conn.cursor()
        row = self._verify_organizer(cursor, support_id, magic_token)
        conn.close()

        if row:
            data = dict(row)
            data.pop('magic_token', None)  # Never expose the token in responses
            return {'status': 'success', 'data': data}
        return {'status': 'error', 'message': 'Invalid support ID or token'}

    # ── Update Support (Organizer) ────────────────────────────

    def update_support(self, support_id, magic_token, data):
        """Update support page. Requires magic_token for authorization.
        V2: Also accepts co-organizer tokens."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Verify ownership (primary or co-organizer)
        if not self._verify_organizer(cursor, support_id, magic_token):
            conn.close()
            return {'status': 'error', 'message': 'Invalid support ID or token'}

        updatable = [
            'family_name', 'shiva_address', 'shiva_city', 'shiva_sub_area', 'shiva_start_date',
            'shiva_end_date', 'pause_shabbat', 'guests_per_meal', 'dietary_notes',
            'special_instructions', 'donation_url', 'donation_label', 'privacy',
            'recommended_vendors', 'organizer_update', 'family_notes',
            'drop_off_instructions', 'notification_prefs',
        ]

        sets = []
        vals = []
        for field in updatable:
            if field in data:
                sets.append(f'{field} = ?')
                val = data[field]
                if field == 'privacy':
                    val = val if val in ('public', 'private') else 'public'
                elif field == 'pause_shabbat':
                    val = 1 if val else 0
                elif field == 'guests_per_meal':
                    val = max(1, min(200, int(val) if val else 20))
                elif field == 'donation_url':
                    val = self._validate_url(val) if val else None
                elif field == 'recommended_vendors':
                    if isinstance(val, list):
                        clean_slugs = [str(s).strip()[:100] for s in val if s][:5]
                        val = json.dumps(clean_slugs) if clean_slugs else None
                    else:
                        val = None
                elif field in ('dietary_notes', 'special_instructions', 'family_notes',
                              'drop_off_instructions'):
                    val = self._sanitize_text(val, self.MAX_TEXT_LENGTH)
                elif field == 'organizer_update':
                    val = self._sanitize_text(val, 280)
                elif field == 'notification_prefs':
                    # Validate JSON structure
                    try:
                        prefs = json.loads(val) if isinstance(val, str) else val
                        val = json.dumps({
                            'instant': bool(prefs.get('instant', True)),
                            'daily_summary': bool(prefs.get('daily_summary', True)),
                            'uncovered_alert': bool(prefs.get('uncovered_alert', True)),
                        })
                    except Exception:
                        val = '{"instant":true,"daily_summary":true,"uncovered_alert":true}'
                else:
                    val = self._sanitize_text(val)
                vals.append(val)

        if not sets:
            conn.close()
            return {'status': 'error', 'message': 'No fields to update'}

        vals.append(support_id)
        cursor.execute(f"UPDATE shiva_support SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
        conn.close()

        return {'status': 'success', 'message': 'Support page updated'}

    # ── Co-Organizers ─────────────────────────────────────────

    def _verify_organizer(self, cursor, support_id, magic_token):
        """Check if token belongs to primary organizer or accepted co-organizer.
        Returns the shiva_support row (as dict) if authorized, else None."""
        # Check primary organizer
        cursor.execute('SELECT * FROM shiva_support WHERE id = ? AND magic_token = ?',
                        (support_id, magic_token))
        row = cursor.fetchone()
        if row:
            return dict(row)

        # Check co-organizer
        cursor.execute('''
            SELECT ss.* FROM shiva_support ss
            JOIN shiva_co_organizers co ON co.shiva_support_id = ss.id
            WHERE ss.id = ? AND co.magic_token = ? AND co.status = 'accepted'
        ''', (support_id, magic_token))
        row = cursor.fetchone()
        return dict(row) if row else None

    def invite_co_organizer(self, support_id, magic_token, data):
        """Invite a co-organizer. Only primary organizer can invite."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Only primary organizer can invite
        cursor.execute('SELECT * FROM shiva_support WHERE id = ? AND magic_token = ?',
                        (support_id, magic_token))
        shiva = cursor.fetchone()
        if not shiva:
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized — only the primary organizer can invite co-organizers'}

        shiva = dict(shiva)
        name = self._sanitize_text(data.get('name', ''), 200)
        email = self._validate_email(data.get('email', ''))

        if not name or not email:
            conn.close()
            return {'status': 'error', 'message': 'Name and email are required'}

        # Don't invite self
        if email.lower() == shiva['organizer_email'].lower():
            conn.close()
            return {'status': 'error', 'message': 'You cannot invite yourself'}

        # Check for existing invite
        cursor.execute('''
            SELECT id, status FROM shiva_co_organizers
            WHERE shiva_support_id = ? AND email = ?
        ''', (support_id, email.lower()))
        existing = cursor.fetchone()
        if existing:
            st = existing['status']
            if st == 'accepted':
                conn.close()
                return {'status': 'error', 'message': f'{name} is already a co-organizer'}
            elif st == 'pending':
                conn.close()
                return {'status': 'error', 'message': f'An invitation is already pending for {email}'}
            # If revoked, allow re-invite (fall through — delete old row)
            cursor.execute('DELETE FROM shiva_co_organizers WHERE id = ?', (existing['id'],))

        co_token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO shiva_co_organizers
                (shiva_support_id, name, email, magic_token, invited_by_email, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        ''', (support_id, name, email.lower(), co_token, shiva['organizer_email'], now))
        conn.commit()
        invite_id = cursor.lastrowid
        conn.close()

        return {
            'status': 'success',
            'message': f'Invitation sent to {name}',
            'invite_id': invite_id,
            'co_token': co_token,
            'invitee_name': name,
            'invitee_email': email.lower(),
            'family_name': shiva['family_name'],
            'organizer_name': shiva['organizer_name'],
            'shiva_id': support_id,
        }

    def accept_co_organizer_invite(self, token):
        """Accept a co-organizer invitation via magic token link."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT co.*, ss.family_name, ss.id as shiva_id
            FROM shiva_co_organizers co
            JOIN shiva_support ss ON co.shiva_support_id = ss.id
            WHERE co.magic_token = ?
        ''', (token,))
        invite = cursor.fetchone()

        if not invite:
            conn.close()
            return {'status': 'error', 'message': 'Invalid invitation link'}
        if invite['status'] == 'accepted':
            conn.close()
            return {'status': 'already_accepted', 'message': 'You are already a co-organizer',
                    'shiva_id': invite['shiva_id'], 'token': token}
        if invite['status'] == 'revoked':
            conn.close()
            return {'status': 'error', 'message': 'This invitation has been revoked'}

        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE shiva_co_organizers SET status = 'accepted', accepted_at = ?
            WHERE magic_token = ?
        ''', (now, token))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'You are now a co-organizer for the {invite["family_name"]} shiva',
            'shiva_id': invite['shiva_id'],
            'family_name': invite['family_name'],
            'token': token,
        }

    def revoke_co_organizer(self, support_id, magic_token, co_organizer_id):
        """Revoke a co-organizer. Only primary organizer can revoke."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM shiva_support WHERE id = ? AND magic_token = ?',
                        (support_id, magic_token))
        if not cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        cursor.execute('''
            UPDATE shiva_co_organizers SET status = 'revoked'
            WHERE id = ? AND shiva_support_id = ?
        ''', (co_organizer_id, support_id))
        if cursor.rowcount == 0:
            conn.close()
            return {'status': 'error', 'message': 'Co-organizer not found'}

        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Co-organizer access revoked'}

    def list_co_organizers(self, support_id, magic_token):
        """List all co-organizers for a shiva page. Requires organizer auth."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if not self._verify_organizer(cursor, support_id, magic_token):
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        cursor.execute('''
            SELECT id, name, email, status, created_at, accepted_at
            FROM shiva_co_organizers
            WHERE shiva_support_id = ? AND status != 'revoked'
            ORDER BY created_at
        ''', (support_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return {'status': 'success', 'data': rows}

    # ── Privacy / Access Requests ─────────────────────────────

    def create_access_request(self, data):
        """Create an access request for a private shiva page."""
        shiva_id = data.get('shiva_id', '').strip()
        name = self._sanitize_text(data.get('requester_name', ''), 200)
        email = self._validate_email(data.get('requester_email', ''))
        message = self._sanitize_text(data.get('message', ''), self.MAX_TEXT_LENGTH)

        if not shiva_id or not name or not email:
            return {'status': 'error', 'message': 'Name and email are required'}

        conn = self._get_conn()
        cursor = conn.cursor()

        # Verify shiva page exists and is private
        cursor.execute('SELECT id, family_name, organizer_email, privacy FROM shiva_support WHERE id = ?', (shiva_id,))
        shiva = cursor.fetchone()
        if not shiva:
            conn.close()
            return {'status': 'error', 'message': 'Shiva page not found'}
        if shiva['privacy'] != 'private':
            conn.close()
            return {'status': 'error', 'message': 'This shiva page is public'}

        # Check for duplicate pending request
        cursor.execute('''
            SELECT id FROM shiva_access_requests
            WHERE shiva_id = ? AND requester_email = ? AND status = 'pending'
        ''', (shiva_id, email))
        if cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'You already have a pending request'}

        # Check if already approved
        cursor.execute('''
            SELECT access_token FROM shiva_access_requests
            WHERE shiva_id = ? AND requester_email = ? AND status = 'approved'
        ''', (shiva_id, email))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return {'status': 'already_approved', 'message': 'You already have access', 'access_token': existing['access_token']}

        organizer_key = secrets.token_urlsafe(24)
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT INTO shiva_access_requests (shiva_id, requester_name, requester_email,
                                               message, status, organizer_key, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        ''', (shiva_id, name, email, message, organizer_key, now))
        conn.commit()
        request_id = cursor.lastrowid
        conn.close()

        return {
            'status': 'success',
            'message': 'Access request submitted',
            'request_id': request_id,
            'organizer_email': shiva['organizer_email'],
            'family_name': shiva['family_name'],
            'requester_name': name,
            'requester_email': email,
            'requester_message': message,
            'organizer_key': organizer_key,
        }

    def approve_access_request(self, request_id, organizer_key):
        """Approve an access request. Returns requester info for email."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, s.family_name, s.id as shiva_id
            FROM shiva_access_requests r
            JOIN shiva_support s ON r.shiva_id = s.id
            WHERE r.id = ? AND r.organizer_key = ?
        ''', (request_id, organizer_key))
        req = cursor.fetchone()

        if not req:
            conn.close()
            return {'status': 'error', 'message': 'Invalid request or key'}
        if req['status'] != 'pending':
            conn.close()
            return {'status': 'error', 'message': f'Request already {req["status"]}'}

        access_token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()

        cursor.execute('''
            UPDATE shiva_access_requests
            SET status = 'approved', access_token = ?, responded_at = ?
            WHERE id = ?
        ''', (access_token, now, request_id))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'Access granted to {req["requester_name"]}',
            'requester_name': req['requester_name'],
            'requester_email': req['requester_email'],
            'family_name': req['family_name'],
            'shiva_id': req['shiva_id'],
            'access_token': access_token,
        }

    def deny_access_request(self, request_id, organizer_key):
        """Deny an access request. Returns requester info for email."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, s.family_name
            FROM shiva_access_requests r
            JOIN shiva_support s ON r.shiva_id = s.id
            WHERE r.id = ? AND r.organizer_key = ?
        ''', (request_id, organizer_key))
        req = cursor.fetchone()

        if not req:
            conn.close()
            return {'status': 'error', 'message': 'Invalid request or key'}
        if req['status'] != 'pending':
            conn.close()
            return {'status': 'error', 'message': f'Request already {req["status"]}'}

        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE shiva_access_requests
            SET status = 'denied', responded_at = ?
            WHERE id = ?
        ''', (now, request_id))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'Request from {req["requester_name"]} denied',
            'requester_name': req['requester_name'],
            'requester_email': req['requester_email'],
            'family_name': req['family_name'],
        }

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

        # Validate email
        vol_email = self._validate_email(data.get('volunteer_email', ''))
        if not vol_email:
            return {'status': 'error', 'message': 'Invalid email address'}

        support_id = data['shiva_support_id'].strip()
        meal_date = data['meal_date'].strip()[:10]

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

        # Alternative contributions skip the duplicate check
        is_alternative = bool(data.get('alternative_type'))

        if not is_alternative:
            # Check for duplicate signup (same date + meal type)
            cursor.execute('''
                SELECT id FROM meal_signups
                WHERE shiva_support_id = ? AND meal_date = ? AND meal_type = ?
                  AND (status IS NULL OR status != 'alternative')
            ''', (support_id, meal_date, data['meal_type']))
            if cursor.fetchone():
                conn.close()
                return {'status': 'error', 'message': 'Someone has already signed up for this meal slot'}

        now = datetime.now().isoformat()
        try:
            num_servings = 4
            try:
                num_servings = max(1, min(50, int(data.get('num_servings', 4))))
            except (ValueError, TypeError):
                pass

            will_serve = 1 if data.get('will_serve') else 0

            signup_group_id = data.get('signup_group_id')
            alt_type = self._sanitize_text(data.get('alternative_type', ''), 50) or None
            alt_note = self._sanitize_text(data.get('alternative_note', ''), self.MAX_TEXT_LENGTH) or None
            signup_status = 'alternative' if is_alternative else 'confirmed'

            cursor.execute('''
                INSERT INTO meal_signups (
                    shiva_support_id, volunteer_name, volunteer_email, volunteer_phone,
                    meal_date, meal_type, meal_description, num_servings,
                    will_serve, privacy_consent, created_at, signup_group_id,
                    status, alternative_type, alternative_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                support_id,
                self._sanitize_text(data['volunteer_name'], 200),
                vol_email,
                self._sanitize_text(data.get('volunteer_phone', ''), 30) or None,
                meal_date,
                data['meal_type'].strip(),
                self._sanitize_text(data.get('meal_description', ''), self.MAX_TEXT_LENGTH) or None,
                num_servings,
                will_serve,
                1,
                now,
                signup_group_id,
                signup_status,
                alt_type,
                alt_note,
            ))
            conn.commit()

            # Return address only to confirmed volunteer
            addr = support.get('shiva_address', '')
            if support.get('shiva_city'):
                addr += ', ' + support['shiva_city']
            return {
                'status': 'success',
                'message': 'Thank you for signing up to help!',
                'signup_id': cursor.lastrowid,
                'shiva_address': support.get('shiva_address', ''),
                'shiva_city': support.get('shiva_city', ''),
                'special_instructions': support.get('special_instructions', ''),
                'family_name': support.get('family_name', ''),
                'address': addr
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def signup_meals_multi(self, data):
        """Sign up for multiple dates at once. V2 multi-date signup.
        data['meal_dates'] = ['2026-03-01', '2026-03-02', ...]
        Returns grouped results with a single signup_group_id."""
        import uuid
        meal_dates = data.get('meal_dates', [])
        if not meal_dates or not isinstance(meal_dates, list):
            return {'status': 'error', 'message': 'meal_dates must be a non-empty list'}
        if len(meal_dates) > 14:
            return {'status': 'error', 'message': 'Maximum 14 dates per signup'}

        group_id = str(uuid.uuid4())
        results = []
        errors = []

        for date in meal_dates:
            single_data = dict(data)
            single_data['meal_date'] = date
            single_data['signup_group_id'] = group_id
            single_data.pop('meal_dates', None)
            result = self.signup_meal(single_data)
            if result['status'] == 'success':
                results.append({'date': date, 'signup_id': result['signup_id']})
            else:
                errors.append({'date': date, 'error': result['message']})

        if not results:
            return {'status': 'error', 'message': 'No dates could be signed up',
                    'errors': errors}

        # Use first successful result for address data
        first = self.signup_meal.__wrapped__(self, {**data, 'meal_date': results[0]['date']}) if False else None
        # Re-fetch address from DB
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT shiva_address, shiva_city, special_instructions, family_name FROM shiva_support WHERE id=?',
                       (data.get('shiva_support_id', ''),))
        support = cursor.fetchone()
        conn.close()

        addr = ''
        family_name = ''
        if support:
            support = dict(support)
            addr = support.get('shiva_address', '')
            if support.get('shiva_city'):
                addr += ', ' + support['shiva_city']
            family_name = support.get('family_name', '')

        return {
            'status': 'success',
            'message': f'Signed up for {len(results)} meal{"s" if len(results) > 1 else ""}!',
            'signup_group_id': group_id,
            'signups': results,
            'errors': errors,
            'address': addr,
            'family_name': family_name,
            'shiva_address': support.get('shiva_address', '') if support else '',
            'shiva_city': support.get('shiva_city', '') if support else '',
            'special_instructions': support.get('special_instructions', '') if support else '',
        }

    # ── Get Signups ───────────────────────────────────────────

    def get_signups(self, support_id):
        """Get all meal signups for a support page (for calendar display)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, meal_date, meal_type, volunteer_name, meal_description,
                   num_servings, will_serve, created_at,
                   status, alternative_type, alternative_note
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
        if not obituary_id:
            return {'exists': False}
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

    def find_similar_shiva(self, family_name):
        """Find active shiva pages with a similar family name (fuzzy match).
        Used to prevent duplicate standalone shiva pages."""
        if not family_name or len(family_name.strip()) < 2:
            return []

        name = family_name.strip().lower()
        # Strip common prefixes like "The", "Family" for matching
        clean = name.replace('the ', '').replace(' family', '').strip()
        if len(clean) < 2:
            return []

        conn = self._get_conn()
        cursor = conn.cursor()
        # Search for active shiva pages created in last 60 days with similar family name
        cutoff = (datetime.now() - timedelta(days=60)).isoformat()
        cursor.execute('''
            SELECT id, family_name, shiva_start_date, shiva_end_date, organizer_name, created_at
            FROM shiva_support
            WHERE status = 'active' AND created_at > ?
            ORDER BY created_at DESC
        ''', (cutoff,))
        rows = cursor.fetchall()
        conn.close()

        matches = []
        for row in rows:
            row = dict(row)
            existing_name = (row['family_name'] or '').lower()
            existing_clean = existing_name.replace('the ', '').replace(' family', '').strip()
            # Match if the core family name is contained in either direction
            if clean in existing_clean or existing_clean in clean:
                first_name = row['organizer_name'].split()[0] if row['organizer_name'] else ''
                matches.append({
                    'id': row['id'],
                    'family_name': row['family_name'],
                    'shiva_start_date': row['shiva_start_date'],
                    'shiva_end_date': row['shiva_end_date'],
                    'organizer_first_name': first_name,
                    'created_at': row['created_at']
                })

        return matches[:5]  # Return at most 5 matches

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
            logging.info(f"[Shiva] Archived {count} expired support page(s)")
        return count

    # ── Analytics ─────────────────────────────────────────────

    def track_event(self, event_type, obituary_id=None):
        """Record an analytics event. Fire-and-forget, never raises."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO shiva_analytics (event_type, obituary_id, created_at) VALUES (?, ?, ?)',
                (event_type, obituary_id, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_signups_for_organizer(self, support_id, magic_token):
        """Get full meal signup details for organizer. Includes email/phone.
        V2: Also accepts co-organizer tokens."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if not self._verify_organizer(cursor, support_id, magic_token):
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        cursor.execute('''
            SELECT id, meal_date, meal_type, volunteer_name, volunteer_email,
                   volunteer_phone, meal_description, num_servings, will_serve, created_at
            FROM meal_signups
            WHERE shiva_support_id = ?
            ORDER BY meal_date, meal_type
        ''', (support_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {'status': 'success', 'data': rows}

    def remove_signup(self, support_id, signup_id, magic_token):
        """Remove a meal signup. Requires organizer magic_token.
        V2: Also accepts co-organizer tokens."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if not self._verify_organizer(cursor, support_id, magic_token):
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        try:
            cursor.execute('DELETE FROM meal_signups WHERE id = ? AND shiva_support_id = ?',
                            (int(signup_id), support_id))
            if cursor.rowcount == 0:
                conn.close()
                return {'status': 'error', 'message': 'Signup not found'}
            conn.commit()
            return {'status': 'success', 'message': 'Signup removed'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def report_page(self, data):
        """Report a shiva support page as potentially unauthorized."""
        required = ['shiva_support_id', 'reporter_name', 'reporter_email', 'reason']
        for field in required:
            if not data.get(field, '').strip():
                return {'status': 'error', 'message': f'Missing required field: {field}'}

        clean_email = self._validate_email(data.get('reporter_email', ''))
        if not clean_email:
            return {'status': 'error', 'message': 'Invalid email address'}

        conn = self._get_conn()
        cursor = conn.cursor()

        # Verify the support page exists
        cursor.execute('SELECT id FROM shiva_support WHERE id = ?', (data['shiva_support_id'],))
        if not cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Support page not found'}

        try:
            cursor.execute('''
                INSERT INTO shiva_reports (shiva_support_id, reporter_name, reporter_email, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data['shiva_support_id'],
                self._sanitize_text(data['reporter_name'], 200),
                clean_email,
                self._sanitize_text(data['reason'], self.MAX_TEXT_LENGTH),
                datetime.now().isoformat()
            ))
            conn.commit()
            return {'status': 'success', 'message': 'Report submitted. We will review this page.'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def get_analytics(self):
        """Get analytics summary counts."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT event_type, COUNT(*) as count FROM shiva_analytics GROUP BY event_type'
        )
        counts = {row['event_type']: row['count'] for row in cursor.fetchall()}
        conn.close()
        return {'status': 'success', 'data': counts}

    # ── Caterer Partners ──────────────────────────────────────

    def submit_caterer_application(self, data):
        """Submit a caterer partner application."""
        required = ['business_name', 'contact_name', 'email', 'delivery_area',
                     'kosher_level', 'shiva_menu_description']
        for field in required:
            if not data.get(field, '').strip():
                return {'status': 'error', 'message': f'Missing required field: {field}'}

        if not data.get('privacy_consent'):
            return {'status': 'error', 'message': 'Privacy consent is required'}

        clean_email = self._validate_email(data.get('email', ''))
        if not clean_email:
            return {'status': 'error', 'message': 'Invalid email address'}

        website = self._validate_url(data.get('website', '').strip()) if data.get('website', '').strip() else None
        if data.get('website', '').strip() and not website:
            return {'status': 'error', 'message': 'Website must start with http:// or https://'}

        valid_kosher = ('certified_kosher', 'kosher_style', 'not_kosher')
        kosher = data.get('kosher_level', '').strip()
        if kosher not in valid_kosher:
            return {'status': 'error', 'message': 'Invalid kosher level'}

        valid_price = ('$', '$$', '$$$')
        price = data.get('price_range', '$$').strip()
        if price not in valid_price:
            price = '$$'

        caterer_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = self._get_conn()
        cursor = conn.cursor()

        # Check for duplicate application by email
        cursor.execute('SELECT id, status FROM caterer_partners WHERE email = ?', (clean_email,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            status = dict(existing)['status']
            if status == 'approved':
                return {'status': 'error', 'message': 'This email is already registered as an approved caterer.'}
            elif status == 'pending':
                return {'status': 'error', 'message': 'An application with this email is already pending review.'}

        try:
            cursor.execute('''
                INSERT INTO caterer_partners (
                    id, business_name, contact_name, email, phone, website, instagram,
                    delivery_area, kosher_level, has_delivery, has_online_ordering,
                    price_range, shiva_menu_description, logo_url,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ''', (
                caterer_id,
                self._sanitize_text(data['business_name'], 200),
                self._sanitize_text(data['contact_name'], 200),
                clean_email,
                self._sanitize_text(data.get('phone', ''), 30) or None,
                website,
                self._sanitize_text(data.get('instagram', ''), 200) or None,
                self._sanitize_text(data['delivery_area']),
                kosher,
                1 if data.get('has_delivery') else 0,
                1 if data.get('has_online_ordering') else 0,
                price,
                self._sanitize_text(data['shiva_menu_description'], self.MAX_TEXT_LENGTH),
                self._validate_url(data.get('logo_url', '').strip()) if data.get('logo_url', '').strip() else None,
                now, now
            ))
            conn.commit()
            return {'status': 'success', 'id': caterer_id}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def get_pending_applications(self):
        """Get all pending caterer applications (admin only)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM caterer_partners WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {'status': 'success', 'data': rows}

    def approve_caterer(self, caterer_id):
        """Approve a caterer application."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM caterer_partners WHERE id = ?', (caterer_id,))
        if not cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Caterer not found'}
        cursor.execute(
            'UPDATE caterer_partners SET status = ?, updated_at = ? WHERE id = ?',
            ('approved', datetime.now().isoformat(), caterer_id)
        )
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Caterer approved'}

    def reject_caterer(self, caterer_id):
        """Reject a caterer application."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM caterer_partners WHERE id = ?', (caterer_id,))
        if not cursor.fetchone():
            conn.close()
            return {'status': 'error', 'message': 'Caterer not found'}
        cursor.execute(
            'UPDATE caterer_partners SET status = ?, updated_at = ? WHERE id = ?',
            ('rejected', datetime.now().isoformat(), caterer_id)
        )
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Caterer rejected'}

    def get_approved_caterers(self):
        """Get all approved caterers (public)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, business_name, contact_name, email, phone, website, instagram,
                   delivery_area, kosher_level, has_delivery, has_online_ordering,
                   price_range, shiva_menu_description, logo_url, created_at
            FROM caterer_partners WHERE status = 'approved'
            ORDER BY created_at ASC
        ''')
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {'status': 'success', 'data': rows}

    def get_caterers_filtered(self, filters):
        """Get approved caterers with optional filters."""
        conditions = ["status = 'approved'"]
        params = []

        if filters.get('kosher'):
            conditions.append("kosher_level IN ('certified_kosher', 'kosher_style')")
        if filters.get('delivery'):
            conditions.append('has_delivery = 1')
        if filters.get('online_ordering'):
            conditions.append('has_online_ordering = 1')

        where = ' AND '.join(conditions)

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT id, business_name, contact_name, email, phone, website, instagram,
                   delivery_area, kosher_level, has_delivery, has_online_ordering,
                   price_range, shiva_menu_description, logo_url, created_at
            FROM caterer_partners WHERE {where}
            ORDER BY created_at ASC
        ''', params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {'status': 'success', 'data': rows}

    def seed_caterer(self, data):
        """Seed a pre-approved caterer (for initial data). Skips if email exists."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM caterer_partners WHERE email = ?',
                        (data.get('email', ''),))
        if cursor.fetchone():
            conn.close()
            return {'status': 'exists'}

        caterer_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        try:
            cursor.execute('''
                INSERT INTO caterer_partners (
                    id, business_name, contact_name, email, phone, website, instagram,
                    delivery_area, kosher_level, has_delivery, has_online_ordering,
                    price_range, shiva_menu_description, logo_url,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?)
            ''', (
                caterer_id,
                data.get('business_name', ''),
                data.get('contact_name', ''),
                data.get('email', ''),
                data.get('phone'),
                data.get('website'),
                data.get('instagram'),
                data.get('delivery_area', ''),
                data.get('kosher_level', 'kosher_style'),
                1 if data.get('has_delivery') else 0,
                1 if data.get('has_online_ordering') else 0,
                data.get('price_range', '$$'),
                data.get('shiva_menu_description', ''),
                data.get('logo_url'),
                now, now
            ))
            conn.commit()
            return {'status': 'success', 'id': caterer_id}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    # ── Backup & Restore ─────────────────────────────────────

    BACKUP_TABLES = [
        'shiva_support', 'meal_signups', 'caterer_partners',
        'donation_links', 'shiva_reports',
    ]

    def _get_backup_path(self):
        """Return backup.json path next to the database file."""
        return os.path.join(os.path.dirname(os.path.abspath(self.db_path)), 'backup.json')

    def get_backup_data(self):
        """Export all critical tables (including subscribers/tributes) as a dict."""
        conn = self._get_conn()
        cursor = conn.cursor()
        tables = {}

        for table in self.BACKUP_TABLES:
            try:
                cursor.execute(f'SELECT * FROM {table}')
                columns = [desc[0] for desc in cursor.description]
                tables[table] = [dict(zip(columns, row)) for row in cursor.fetchall()]
            except Exception:
                tables[table] = []

        # Also back up subscribers and tributes (managed by api_server directly)
        for table in ('subscribers', 'tributes'):
            try:
                cursor.execute(f'SELECT * FROM {table}')
                columns = [desc[0] for desc in cursor.description]
                tables[table] = [dict(zip(columns, row)) for row in cursor.fetchall()]
            except Exception:
                tables[table] = []

        conn.close()
        return {
            'version': 1,
            'exported_at': datetime.now().isoformat(),
            'tables': tables
        }

    def backup_to_file(self):
        """Write all critical tables to backup.json next to the database."""
        try:
            data = self.get_backup_data()
            backup_path = self._get_backup_path()
            tmp_path = backup_path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, backup_path)
            row_count = sum(len(rows) for rows in data['tables'].values())
            logging.info(f"[Backup] Saved {row_count} rows to {backup_path}")
        except Exception as e:
            logging.error(f"[Backup] Error: {e}")

    def restore_from_data(self, data):
        """Restore tables from a backup data dict. Uses INSERT OR IGNORE to avoid duplicates."""
        conn = self._get_conn()
        cursor = conn.cursor()
        restored = 0

        all_tables = self.BACKUP_TABLES + ['subscribers', 'tributes']
        tables = data.get('tables', {})

        for table in all_tables:
            rows = tables.get(table, [])
            if not rows:
                continue
            columns = list(rows[0].keys())
            placeholders = ', '.join(['?'] * len(columns))
            col_names = ', '.join(columns)
            for row in rows:
                try:
                    cursor.execute(
                        f'INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({placeholders})',
                        [row.get(c) for c in columns]
                    )
                    restored += cursor.rowcount
                except Exception as e:
                    logging.info(f"[Restore] Skipping row in {table}: {e}")

        conn.commit()
        conn.close()
        logging.info(f"[Restore] Restored {restored} rows across {len(all_tables)} tables")
        return restored

    def restore_from_file(self):
        """Restore from backup.json if it exists."""
        backup_path = self._get_backup_path()
        if not os.path.exists(backup_path):
            logging.info("[Restore] No backup file found")
            return 0
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.info(f"[Restore] Loading backup from {data.get('exported_at', 'unknown')}")
            return self.restore_from_data(data)
        except Exception as e:
            logging.error(f"[Restore] Error reading backup: {e}")
            return 0

    def needs_restore(self):
        """Return True if shiva_support table is empty AND backup.json exists."""
        backup_path = self._get_backup_path()
        if not os.path.exists(backup_path):
            return False
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM shiva_support')
            count = cursor.fetchone()[0]
            conn.close()
            return count == 0
        except Exception:
            return True

    def _trigger_backup(self):
        """Run backup_to_file in a background thread to avoid slowing responses."""
        thread = threading.Thread(target=self.backup_to_file, daemon=True)
        thread.start()

    # ── Email Verification ────────────────────────────────────

    def verify_email(self, token):
        """Verify organizer email via token link. Returns shiva page info."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, family_name, organizer_email, verification_status, magic_token
            FROM shiva_support
            WHERE verification_token = ?
        ''', (token,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {'status': 'error', 'message': 'Invalid verification link'}

        row = dict(row)
        if row['verification_status'] == 'verified':
            conn.close()
            return {
                'status': 'already_verified',
                'message': 'Email already verified',
                'shiva_id': row['id'],
                'magic_token': row['magic_token'],
            }

        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE shiva_support
            SET verification_status = 'verified',
                verified_at = ?,
                verification_token = NULL
            WHERE verification_token = ?
        ''', (now, token))
        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': 'Email verified successfully',
            'shiva_id': row['id'],
            'family_name': row['family_name'],
            'magic_token': row['magic_token'],
        }

    def admin_verify_email(self, support_id):
        """Admin-approve email verification (manual override)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE shiva_support
            SET verification_status = 'admin_approved',
                verified_at = ?,
                verification_token = NULL
            WHERE id = ?
        ''', (now, support_id))
        if cursor.rowcount == 0:
            conn.close()
            return {'status': 'error', 'message': 'Shiva page not found'}
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Email manually verified'}

    # ── V3: Organizer Updates ─────────────────────────────────

    def post_update(self, support_id, magic_token, message):
        """Post an organizer update to the shiva page."""
        if not message or not message.strip():
            return {'status': 'error', 'message': 'Update message is required'}

        conn = self._get_conn()
        cursor = conn.cursor()

        support = self._verify_organizer(cursor, support_id, magic_token)
        if not support:
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        now = datetime.now().isoformat()
        organizer_name = support.get('organizer_name', 'Organizer')

        cursor.execute('''
            INSERT INTO shiva_updates (shiva_support_id, message, created_by, created_at)
            VALUES (?, ?, ?, ?)
        ''', (support_id, self._sanitize_text(message, self.MAX_TEXT_LENGTH), organizer_name, now))

        update_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {'status': 'success', 'update_id': update_id}

    def get_updates(self, support_id):
        """Get all updates for a shiva page (public)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, message, created_by, created_at
            FROM shiva_updates
            WHERE shiva_support_id = ?
            ORDER BY created_at DESC
        ''', (support_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {'status': 'success', 'data': rows}

    def delete_update(self, support_id, magic_token, update_id):
        """Delete an organizer update."""
        conn = self._get_conn()
        cursor = conn.cursor()

        support = self._verify_organizer(cursor, support_id, magic_token)
        if not support:
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        cursor.execute('''
            DELETE FROM shiva_updates
            WHERE id = ? AND shiva_support_id = ?
        ''', (update_id, support_id))

        if cursor.rowcount == 0:
            conn.close()
            return {'status': 'error', 'message': 'Update not found'}

        conn.commit()
        conn.close()
        return {'status': 'success'}

    # ── V3: Thank-You Notes ───────────────────────────────────

    def send_thank_you_notes(self, support_id, magic_token):
        """Queue thank-you emails to all volunteers who signed up.
        Can only be sent once per shiva page."""
        conn = self._get_conn()
        cursor = conn.cursor()

        support = self._verify_organizer(cursor, support_id, magic_token)
        if not support:
            conn.close()
            return {'status': 'error', 'message': 'Unauthorized'}

        if support.get('thank_you_sent'):
            conn.close()
            return {'status': 'error', 'message': 'Thank-you notes have already been sent'}

        # Get all unique volunteer emails
        cursor.execute('''
            SELECT DISTINCT volunteer_name, volunteer_email
            FROM meal_signups
            WHERE shiva_support_id = ? AND volunteer_email IS NOT NULL
        ''', (support_id,))
        volunteers = [dict(row) for row in cursor.fetchall()]

        if not volunteers:
            conn.close()
            return {'status': 'error', 'message': 'No volunteers to thank'}

        now = datetime.now().isoformat()
        queued = 0
        family_name = support.get('family_name', 'the family')

        for vol in volunteers:
            # Check email_log for dedup
            cursor.execute('''
                SELECT id FROM email_log
                WHERE shiva_support_id = ? AND email_type = 'thank_you'
                  AND recipient_email = ?
            ''', (support_id, vol['volunteer_email']))
            if cursor.fetchone():
                continue  # Already queued/sent

            cursor.execute('''
                INSERT INTO email_log (
                    shiva_support_id, email_type, recipient_email, recipient_name,
                    status, created_at
                ) VALUES (?, 'thank_you', ?, ?, 'pending', ?)
            ''', (support_id, vol['volunteer_email'], vol['volunteer_name'], now))
            queued += 1

        # Mark as sent
        cursor.execute('UPDATE shiva_support SET thank_you_sent = 1 WHERE id = ?', (support_id,))

        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'message': f'Thank-you notes queued for {queued} volunteer{"s" if queued != 1 else ""}',
            'count': queued
        }
