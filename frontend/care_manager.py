"""
Neshama Care Coordination Manager
Manages family coordination pages for end-of-life care at home.
Reuses meal coordination patterns from ShivaManager.
"""

import json
import logging
import secrets
import sqlite3
import uuid
from datetime import datetime

import html as html_mod

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class CareManager:
    def __init__(self, db_path='neshama.db'):
        self.db_path = db_path
        self.setup_database()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        conn.row_factory = sqlite3.Row
        return conn

    def setup_database(self):
        """Create care coordination tables idempotently."""
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=30000')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS care_pages (
                id TEXT PRIMARY KEY,
                loved_one_name TEXT NOT NULL,
                family_name TEXT NOT NULL,
                organizer_name TEXT NOT NULL,
                organizer_email TEXT NOT NULL,
                organizer_phone TEXT,
                organizer_relationship TEXT NOT NULL,
                address TEXT,
                visiting_hours_start TEXT,
                visiting_hours_end TEXT,
                meals_needed INTEGER DEFAULT 1,
                meal_servings INTEGER DEFAULT 6,
                dietary_notes TEXT,
                privacy TEXT DEFAULT 'open',
                status TEXT DEFAULT 'active',
                magic_token TEXT NOT NULL,
                share_token TEXT NOT NULL,
                privacy_consent INTEGER NOT NULL DEFAULT 0,
                transitioned_to_shiva TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS care_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                care_page_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (care_page_id) REFERENCES care_pages(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS care_visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                care_page_id TEXT NOT NULL,
                visitor_name TEXT NOT NULL,
                visitor_email TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                visit_time TEXT,
                message TEXT,
                status TEXT DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                FOREIGN KEY (care_page_id) REFERENCES care_pages(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS care_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                care_page_id TEXT NOT NULL,
                volunteer_name TEXT NOT NULL,
                volunteer_email TEXT NOT NULL,
                volunteer_phone TEXT,
                meal_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                meal_description TEXT,
                num_servings INTEGER DEFAULT 4,
                dietary_notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (care_page_id) REFERENCES care_pages(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS care_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                care_page_id TEXT NOT NULL,
                description TEXT NOT NULL,
                assigned_name TEXT,
                assigned_email TEXT,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL,
                claimed_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (care_page_id) REFERENCES care_pages(id)
            )
        ''')

        conn.commit()
        conn.close()
        logging.info("[Care] Database tables initialized")

    def _sanitize(self, text, max_len=500):
        if not text:
            return ''
        return html_mod.escape(str(text).strip()[:max_len])

    def _validate_email(self, email):
        email = str(email).strip().lower()[:254]
        if '@' not in email or '.' not in email.split('@')[-1]:
            return None
        return email

    # ── Create Care Page ──────────────────────────────────────

    def create_page(self, data):
        """Create a new care coordination page."""
        loved_one = self._sanitize(data.get('loved_one_name', ''), 200)
        family_name = self._sanitize(data.get('family_name', ''), 200)
        org_name = self._sanitize(data.get('organizer_name', ''), 200)
        org_email = self._validate_email(data.get('organizer_email', ''))
        org_relationship = self._sanitize(data.get('organizer_relationship', ''), 100)

        if not loved_one:
            return {'status': 'error', 'message': 'Name of your loved one is required'}
        if not family_name:
            return {'status': 'error', 'message': 'Family name is required'}
        if not org_name:
            return {'status': 'error', 'message': 'Your name is required'}
        if not org_email:
            return {'status': 'error', 'message': 'A valid email is required'}
        if not org_relationship:
            return {'status': 'error', 'message': 'Your relationship is required'}
        if not data.get('privacy_consent'):
            return {'status': 'error', 'message': 'Privacy consent is required'}

        page_id = str(uuid.uuid4())
        magic_token = secrets.token_urlsafe(32)
        share_token = secrets.token_urlsafe(16)
        now = datetime.now().isoformat()

        privacy = data.get('privacy', 'open')
        if privacy not in ('open', 'private'):
            privacy = 'open'

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO care_pages (
                id, loved_one_name, family_name,
                organizer_name, organizer_email, organizer_phone, organizer_relationship,
                address, visiting_hours_start, visiting_hours_end,
                meals_needed, meal_servings, dietary_notes,
                privacy, magic_token, share_token, privacy_consent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            page_id, loved_one, family_name,
            org_name, org_email,
            self._sanitize(data.get('organizer_phone', ''), 20),
            org_relationship,
            self._sanitize(data.get('address', ''), 500),
            data.get('visiting_hours_start', ''),
            data.get('visiting_hours_end', ''),
            1 if data.get('meals_needed', True) else 0,
            int(data.get('meal_servings', 6)),
            self._sanitize(data.get('dietary_notes', ''), 500),
            privacy, magic_token, share_token, 1, now
        ))

        # Create default starter tasks
        default_tasks = [
            'Pick up prescriptions from pharmacy',
            'Grocery run — essentials for the house',
            'Prepare a meal for the family',
            'Help with laundry or tidying',
            'Walk the dog / care for pets'
        ]
        for task_desc in default_tasks:
            cursor.execute('''
                INSERT INTO care_tasks (care_page_id, description, created_at)
                VALUES (?, ?, ?)
            ''', (page_id, task_desc, now))

        conn.commit()
        conn.close()

        return {
            'status': 'success',
            'id': page_id,
            'magic_token': magic_token,
            'share_token': share_token,
            'family_name': family_name,
            'loved_one_name': loved_one
        }

    # ── Get Care Page ─────────────────────────────────────────

    def get_page(self, page_id, token=None):
        """Retrieve a care page by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM care_pages WHERE id = ? AND status = ?', (page_id, 'active'))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {'status': 'not_found'}

        page = dict(row)
        is_organizer = (token and token == page.get('magic_token'))

        # Don't expose sensitive fields
        safe_page = {
            'id': page['id'],
            'loved_one_name': page['loved_one_name'],
            'family_name': page['family_name'],
            'visiting_hours_start': page.get('visiting_hours_start', ''),
            'visiting_hours_end': page.get('visiting_hours_end', ''),
            'meals_needed': page.get('meals_needed', 1),
            'meal_servings': page.get('meal_servings', 6),
            'dietary_notes': page.get('dietary_notes', ''),
            'privacy': page.get('privacy', 'open'),
            'created_at': page['created_at'],
        }

        if is_organizer:
            safe_page['organizer_name'] = page['organizer_name']
            safe_page['organizer_email'] = page['organizer_email']
            safe_page['address'] = page.get('address', '')
            safe_page['is_organizer'] = True

        # Get updates
        cursor.execute('''
            SELECT id, author_name, message, created_at
            FROM care_updates WHERE care_page_id = ?
            ORDER BY created_at DESC LIMIT 20
        ''', (page_id,))
        safe_page['updates'] = [dict(r) for r in cursor.fetchall()]

        # Get visitors (next 14 days)
        cursor.execute('''
            SELECT id, visitor_name, visit_date, visit_time, message, created_at
            FROM care_visitors WHERE care_page_id = ? AND status = 'confirmed'
            ORDER BY visit_date ASC, visit_time ASC
        ''', (page_id,))
        safe_page['visitors'] = [dict(r) for r in cursor.fetchall()]

        # Get meals (next 14 days)
        cursor.execute('''
            SELECT id, volunteer_name, meal_date, meal_type, meal_description, num_servings, created_at
            FROM care_meals WHERE care_page_id = ?
            ORDER BY meal_date ASC, meal_type ASC
        ''', (page_id,))
        safe_page['meals'] = [dict(r) for r in cursor.fetchall()]

        # Get tasks
        cursor.execute('''
            SELECT id, description, assigned_name, status, created_at, claimed_at
            FROM care_tasks WHERE care_page_id = ?
            ORDER BY status ASC, created_at ASC
        ''', (page_id,))
        safe_page['tasks'] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return {'status': 'success', 'data': safe_page}

    # ── Post Update ───────────────────────────────────────────

    def post_update(self, page_id, data):
        """Post a family update."""
        author = self._sanitize(data.get('author_name', ''), 200)
        message = self._sanitize(data.get('message', ''), 2000)
        if not author or not message:
            return {'status': 'error', 'message': 'Name and message are required'}

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO care_updates (care_page_id, author_name, message, created_at)
            VALUES (?, ?, ?, ?)
        ''', (page_id, author, message, now))
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Update posted'}

    # ── Sign Up to Visit ──────────────────────────────────────

    def add_visitor(self, page_id, data):
        """Sign up for a visit."""
        name = self._sanitize(data.get('visitor_name', ''), 200)
        email = self._validate_email(data.get('visitor_email', ''))
        visit_date = str(data.get('visit_date', '')).strip()[:10]
        visit_time = self._sanitize(data.get('visit_time', ''), 20)
        message = self._sanitize(data.get('message', ''), 500)

        if not name or not email or not visit_date:
            return {'status': 'error', 'message': 'Name, email, and date are required'}

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO care_visitors (care_page_id, visitor_name, visitor_email, visit_date, visit_time, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (page_id, name, email, visit_date, visit_time, message, now))
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Visit scheduled'}

    # ── Sign Up for Meal ──────────────────────────────────────

    def add_meal(self, page_id, data):
        """Sign up to bring a meal."""
        name = self._sanitize(data.get('volunteer_name', ''), 200)
        email = self._validate_email(data.get('volunteer_email', ''))
        meal_date = str(data.get('meal_date', '')).strip()[:10]
        meal_type = data.get('meal_type', 'dinner')
        if meal_type not in ('lunch', 'dinner'):
            meal_type = 'dinner'
        description = self._sanitize(data.get('meal_description', ''), 500)

        if not name or not email or not meal_date:
            return {'status': 'error', 'message': 'Name, email, and date are required'}

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO care_meals (care_page_id, volunteer_name, volunteer_email, meal_date, meal_type, meal_description, num_servings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (page_id, name, email, meal_date, meal_type, description, int(data.get('num_servings', 4)), now))
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Meal sign-up confirmed'}

    # ── Claim a Task ──────────────────────────────────────────

    def claim_task(self, task_id, data):
        """Claim an open task."""
        name = self._sanitize(data.get('name', ''), 200)
        email = self._validate_email(data.get('email', ''))
        if not name or not email:
            return {'status': 'error', 'message': 'Name and email are required'}

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE care_tasks SET assigned_name = ?, assigned_email = ?, status = 'claimed', claimed_at = ?
            WHERE id = ? AND status = 'open'
        ''', (name, email, now, task_id))

        if cursor.rowcount == 0:
            conn.close()
            return {'status': 'error', 'message': 'Task is no longer available'}

        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Task claimed'}

    # ── Add Task (organizer) ──────────────────────────────────

    def add_task(self, page_id, data):
        """Add a new task (organizer only)."""
        description = self._sanitize(data.get('description', ''), 500)
        if not description:
            return {'status': 'error', 'message': 'Task description is required'}

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO care_tasks (care_page_id, description, created_at)
            VALUES (?, ?, ?)
        ''', (page_id, description, now))
        conn.commit()
        conn.close()
        return {'status': 'success', 'message': 'Task added'}
