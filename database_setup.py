#!/usr/bin/env python3
"""
Neshama Database Setup
Creates and manages the SQLite database for storing obituary data
"""

import sqlite3
import hashlib
from datetime import datetime
import os

class NeshamaDatabase:
    def __init__(self, db_path=None):
        """Initialize database connection"""
        self.db_path = db_path or os.environ.get('DATABASE_PATH', 'neshama.db')
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def create_tables(self):
        """Create all necessary tables with proper schema"""
        self.connect()

        # Main obituaries table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS obituaries (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                deceased_name TEXT NOT NULL,
                hebrew_name TEXT,
                date_of_death TEXT,
                yahrzeit_date TEXT,
                funeral_datetime TEXT,
                funeral_location TEXT,
                burial_location TEXT,
                shiva_info TEXT,
                obituary_text TEXT,
                condolence_url TEXT,
                livestream_url TEXT,
                livestream_available INTEGER DEFAULT 0,
                photo_url TEXT,
                city TEXT DEFAULT 'Toronto',
                scraped_at TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                content_hash TEXT NOT NULL
            )
        ''')

        # Comments table - linked to obituaries
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obituary_id TEXT NOT NULL,
                commenter_name TEXT,
                comment_text TEXT NOT NULL,
                posted_at TEXT,
                scraped_at TEXT NOT NULL,
                FOREIGN KEY (obituary_id) REFERENCES obituaries(id)
            )
        ''')

        # Create indexes for performance
        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obituary_updated
            ON obituaries(last_updated DESC)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obituary_source
            ON obituaries(source)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obituary_name
            ON obituaries(deceased_name)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_obituary_city
            ON obituaries(city)
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_comments_obituary
            ON comments(obituary_id)
        ''')

        # Scraper log table for monitoring
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                run_time TEXT NOT NULL,
                status TEXT NOT NULL,
                obituaries_found INTEGER DEFAULT 0,
                new_obituaries INTEGER DEFAULT 0,
                updated_obituaries INTEGER DEFAULT 0,
                error_message TEXT,
                duration_seconds REAL
            )
        ''')

        # Tributes table - condolence messages left by visitors
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obituary_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                message TEXT NOT NULL,
                relationship TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (obituary_id) REFERENCES obituaries(id)
            )
        ''')

        self.cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tributes_obituary
            ON tributes(obituary_id)
        ''')

        self.conn.commit()
        self.close()

    def generate_obituary_id(self, source, deceased_name, date_of_death):
        """Generate unique ID for obituary using hash"""
        key = f"{source}_{deceased_name}_{date_of_death}".lower()
        return hashlib.md5(key.encode()).hexdigest()

    def generate_content_hash(self, obituary_data):
        """Generate hash of content to detect changes"""
        # Combine key fields that might change
        content = f"{obituary_data.get('funeral_datetime', '')}_" \
                  f"{obituary_data.get('shiva_info', '')}_" \
                  f"{obituary_data.get('livestream_url', '')}"
        return hashlib.md5(content.encode()).hexdigest()

    def upsert_obituary(self, obituary_data):
        """Insert new obituary or update existing one"""
        self.connect()

        # Generate IDs and hashes
        obit_id = self.generate_obituary_id(
            obituary_data['source'],
            obituary_data['deceased_name'],
            obituary_data.get('date_of_death', '')
        )

        content_hash = self.generate_content_hash(obituary_data)
        now = datetime.now().isoformat()

        # Check if obituary exists
        self.cursor.execute('SELECT id, content_hash FROM obituaries WHERE id = ?', (obit_id,))
        existing = self.cursor.fetchone()

        if existing:
            # Update if content changed
            if existing[1] != content_hash:
                self.cursor.execute('''
                    UPDATE obituaries SET
                        hebrew_name = ?,
                        date_of_death = ?,
                        yahrzeit_date = ?,
                        funeral_datetime = ?,
                        funeral_location = ?,
                        burial_location = ?,
                        shiva_info = ?,
                        obituary_text = ?,
                        livestream_url = ?,
                        livestream_available = ?,
                        photo_url = ?,
                        last_updated = ?,
                        content_hash = ?
                    WHERE id = ?
                ''', (
                    obituary_data.get('hebrew_name'),
                    obituary_data.get('date_of_death'),
                    obituary_data.get('yahrzeit_date'),
                    obituary_data.get('funeral_datetime'),
                    obituary_data.get('funeral_location'),
                    obituary_data.get('burial_location'),
                    obituary_data.get('shiva_info'),
                    obituary_data.get('obituary_text'),
                    obituary_data.get('livestream_url'),
                    1 if obituary_data.get('livestream_url') else 0,
                    obituary_data.get('photo_url'),
                    now,
                    content_hash,
                    obit_id
                ))
                action = 'updated'
            else:
                action = 'unchanged'
        else:
            # Insert new obituary
            self.cursor.execute('''
                INSERT INTO obituaries (
                    id, source, source_url, deceased_name, hebrew_name,
                    date_of_death, yahrzeit_date, funeral_datetime,
                    funeral_location, burial_location, shiva_info,
                    obituary_text, condolence_url, livestream_url,
                    livestream_available, photo_url, city, scraped_at,
                    first_seen, last_updated, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                obit_id,
                obituary_data['source'],
                obituary_data['source_url'],
                obituary_data['deceased_name'],
                obituary_data.get('hebrew_name'),
                obituary_data.get('date_of_death'),
                obituary_data.get('yahrzeit_date'),
                obituary_data.get('funeral_datetime'),
                obituary_data.get('funeral_location'),
                obituary_data.get('burial_location'),
                obituary_data.get('shiva_info'),
                obituary_data.get('obituary_text'),
                obituary_data['condolence_url'],
                obituary_data.get('livestream_url'),
                1 if obituary_data.get('livestream_url') else 0,
                obituary_data.get('photo_url'),
                obituary_data.get('city', 'Toronto'),
                now,
                now,
                now,
                content_hash
            ))
            action = 'inserted'

        self.conn.commit()
        self.close()
        return obit_id, action

    def upsert_comment(self, obituary_id, comment_data):
        """Insert comment if it doesn't already exist"""
        self.connect()

        # Check for duplicate
        self.cursor.execute('''
            SELECT id FROM comments
            WHERE obituary_id = ?
            AND commenter_name = ?
            AND comment_text = ?
            AND posted_at = ?
        ''', (
            obituary_id,
            comment_data.get('commenter_name'),
            comment_data['comment_text'],
            comment_data.get('posted_at')
        ))

        if self.cursor.fetchone():
            self.close()
            return None  # Duplicate, skip

        # Insert new comment
        now = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO comments (
                obituary_id, commenter_name, comment_text,
                posted_at, scraped_at
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            obituary_id,
            comment_data.get('commenter_name'),
            comment_data['comment_text'],
            comment_data.get('posted_at'),
            now
        ))

        comment_id = self.cursor.lastrowid
        self.conn.commit()
        self.close()
        return comment_id

    def log_scraper_run(self, source, status, stats=None, error=None, duration=None):
        """Log scraper execution for monitoring"""
        self.connect()

        now = datetime.now().isoformat()
        self.cursor.execute('''
            INSERT INTO scraper_log (
                source, run_time, status, obituaries_found,
                new_obituaries, updated_obituaries, error_message,
                duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            source,
            now,
            status,
            stats.get('found', 0) if stats else 0,
            stats.get('new', 0) if stats else 0,
            stats.get('updated', 0) if stats else 0,
            error,
            duration
        ))

        self.conn.commit()
        self.close()

    def get_recent_obituaries(self, days=7, source=None):
        """Retrieve recent obituaries"""
        self.connect()

        if source:
            self.cursor.execute('''
                SELECT * FROM obituaries
                WHERE source = ?
                AND datetime(last_updated) > datetime('now', '-' || ? || ' days')
                ORDER BY last_updated DESC
            ''', (source, days))
        else:
            self.cursor.execute('''
                SELECT * FROM obituaries
                WHERE datetime(last_updated) > datetime('now', '-' || ? || ' days')
                ORDER BY last_updated DESC
            ''', (days,))

        results = self.cursor.fetchall()
        self.close()
        return results

    def get_comments_for_obituary(self, obituary_id):
        """Get all comments for a specific obituary"""
        self.connect()

        self.cursor.execute('''
            SELECT * FROM comments
            WHERE obituary_id = ?
            ORDER BY posted_at ASC
        ''', (obituary_id,))

        results = self.cursor.fetchall()
        self.close()
        return results

def initialize_database():
    """Create database and tables if they don't exist"""
    db_path = os.environ.get('DATABASE_PATH', 'neshama.db')
    db = NeshamaDatabase(db_path)
    db.create_tables()
    print("✅ Database initialized successfully")
    print(f"   Location: {os.path.abspath(db.db_path)}")

if __name__ == '__main__':
    initialize_database()
