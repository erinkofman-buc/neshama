#!/usr/bin/env python3
"""
Neshama API Server v1.3
Serves frontend, API endpoints, email subscriptions (SendGrid double opt-in), and payment integration
Auto-scrapes on startup to handle Render free tier ephemeral storage
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
import os
import re
import subprocess
import threading
from urllib.parse import urlparse, parse_qs
from datetime import datetime

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(FRONTEND_DIR, '..', 'neshama.db'))

# Import vendor seed script
try:
    sys_path_parent = os.path.join(FRONTEND_DIR, '..')
    import sys as _sys
    if sys_path_parent not in _sys.path:
        _sys.path.insert(0, sys_path_parent)
    from seed_vendors import seed_vendors, create_tables as create_vendor_tables
    VENDORS_AVAILABLE = True
except Exception as e:
    VENDORS_AVAILABLE = False
    print(f"  Vendor directory: Not available ({e})")

# Import EmailSubscriptionManager
try:
    import sys
    sys.path.insert(0, FRONTEND_DIR)
    from subscription_manager import EmailSubscriptionManager
    subscription_mgr = EmailSubscriptionManager(db_path=DB_PATH)
    EMAIL_AVAILABLE = True
    print(f"  Email subscription: {'SendGrid connected' if subscription_mgr.sendgrid_api_key else 'TEST MODE (console logging)'}")
except Exception as e:
    EMAIL_AVAILABLE = False
    subscription_mgr = None
    print(f"  Email subscription: Not available ({e})")

# Optional Stripe import
try:
    from payment_manager import PaymentManager
    payment_mgr = PaymentManager(db_path=DB_PATH)
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False
    payment_mgr = None

# Background scrape status tracking
_scrape_status = {
    'running': False,
    'last_started': None,
    'last_completed': None,
    'last_result': None,
    'last_error': None,
}

# Optional Shiva Support import
try:
    from shiva_manager import ShivaManager
    shiva_mgr = ShivaManager(db_path=DB_PATH)
    SHIVA_AVAILABLE = True
    print(f"  Shiva support: Available")
except Exception as e:
    SHIVA_AVAILABLE = False
    shiva_mgr = None
    print(f"  Shiva support: Not available ({e})")

class NeshamaAPIHandler(BaseHTTPRequestHandler):

    STATIC_FILES = {
        '/': ('landing.html', 'text/html'),
        '/landing.html': ('landing.html', 'text/html'),
        '/feed': ('index.html', 'text/html'),
        '/index.html': ('index.html', 'text/html'),
        '/app.js': ('app.js', 'application/javascript'),
        '/about': ('about.html', 'text/html'),
        '/about.html': ('about.html', 'text/html'),
        '/faq': ('faq.html', 'text/html'),
        '/faq.html': ('faq.html', 'text/html'),
        '/privacy': ('privacy.html', 'text/html'),
        '/privacy.html': ('privacy.html', 'text/html'),
        '/premium-modal': ('premium_modal.html', 'text/html'),
        '/premium_modal.html': ('premium_modal.html', 'text/html'),
        '/premium-success': ('premium_success.html', 'text/html'),
        '/premium_success.html': ('premium_success.html', 'text/html'),
        '/premium-cancelled': ('premium_cancelled.html', 'text/html'),
        '/premium_cancelled.html': ('premium_cancelled.html', 'text/html'),
        '/email_popup.html': ('email_popup.html', 'text/html'),
        '/premium': ('premium.html', 'text/html'),
        '/premium.html': ('premium.html', 'text/html'),
        '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
        '/manifest.json': ('manifest.json', 'application/manifest+json'),
        '/sw.js': ('sw.js', 'application/javascript'),
        '/icon-192.png': ('icon-192.png', 'image/png'),
        '/icon-512.png': ('icon-512.png', 'image/png'),
        '/apple-touch-icon.png': ('apple-touch-icon.png', 'image/png'),
        '/shiva/organize': ('shiva-organize.html', 'text/html'),
        '/shiva-organize.html': ('shiva-organize.html', 'text/html'),
        '/shiva/guide': ('shiva-guide.html', 'text/html'),
        '/shiva-guide.html': ('shiva-guide.html', 'text/html'),
        '/shiva/caterers': ('shiva-caterers.html', 'text/html'),
        '/shiva-caterers.html': ('shiva-caterers.html', 'text/html'),
        '/shiva/caterers/apply': ('shiva-caterer-apply.html', 'text/html'),
        '/shiva-caterer-apply.html': ('shiva-caterer-apply.html', 'text/html'),
        '/shiva-essentials': ('shiva-essentials.html', 'text/html'),
        '/shiva-essentials.html': ('shiva-essentials.html', 'text/html'),
        '/what-to-bring-to-a-shiva': ('what-to-bring-to-a-shiva.html', 'text/html'),
        '/what-to-bring-to-a-shiva.html': ('what-to-bring-to-a-shiva.html', 'text/html'),
        '/directory': ('directory.html', 'text/html'),
        '/directory.html': ('directory.html', 'text/html'),
        '/sitemap.xml': ('sitemap.xml', 'application/xml'),
    }

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # API endpoints
        if path == '/api/obituaries':
            query_params = parse_qs(parsed_path.query)
            city_filter = query_params.get('city', [None])[0]
            self.get_obituaries(city_filter)
        elif path == '/api/search':
            query_params = parse_qs(parsed_path.query)
            search_query = query_params.get('q', [''])[0]
            self.search_obituaries(search_query)
        elif path == '/api/status':
            self.get_status()
        elif path == '/api/subscribers/count':
            self.get_subscriber_count()
        elif path == '/api/community-stats':
            self.get_community_stats()
        elif path == '/api/tributes/counts':
            self.get_tribute_counts()
        # Single obituary API
        elif path.startswith('/api/obituary/'):
            obit_id = path[len('/api/obituary/'):]
            self.get_single_obituary(obit_id)
        # Tributes API
        elif path.startswith('/api/tributes/'):
            obit_id = path[len('/api/tributes/'):]
            self.get_tributes(obit_id)
        # Caterer API endpoints
        elif path == '/api/caterers':
            self.get_caterers()
        elif path.startswith('/api/caterers/pending'):
            self.get_pending_caterers()
        # Vendor API endpoints
        elif path == '/api/vendors':
            self.get_vendors()
        elif path.startswith('/api/vendors/'):
            slug = path[len('/api/vendors/'):]
            self.get_vendor_by_slug(slug)
        # Vendor detail pages (/directory/slug)
        elif path.startswith('/directory/') and path != '/directory/' and path not in self.STATIC_FILES:
            self.serve_vendor_page()
        # Shiva API endpoints
        elif path.startswith('/api/shiva/obituary/'):
            obit_id = path[len('/api/shiva/obituary/'):]
            self.get_shiva_by_obituary(obit_id)
        elif path.startswith('/api/shiva/') and path.endswith('/meals'):
            support_id = path[len('/api/shiva/'):-len('/meals')]
            self.get_shiva_meals(support_id)
        elif path.startswith('/api/shiva/') and not path.endswith('/meals'):
            support_id = path[len('/api/shiva/'):]
            self.get_shiva_details(support_id)
        # Shiva pages
        elif path.startswith('/shiva/') and path not in self.STATIC_FILES:
            self.serve_shiva_page()
        # Memorial pages
        elif path.startswith('/memorial/'):
            self.serve_memorial_page()
        # Dynamic routes for email confirmation and unsubscribe
        elif path.startswith('/confirm/'):
            token = path[len('/confirm/'):]
            self.handle_confirm(token)
        elif path.startswith('/unsubscribe/'):
            token = path[len('/unsubscribe/'):]
            self.handle_unsubscribe_page(token)
        elif path == '/manage-subscription':
            self.handle_manage_subscription()
        elif path == '/admin/backup':
            self.handle_admin_backup()
        elif path == '/admin/scrape':
            self.handle_admin_scrape()
        elif path == '/admin/scrape-status':
            self.handle_scrape_status()
        elif path == '/admin/digest':
            self.handle_admin_digest()
        elif path in self.STATIC_FILES:
            self.serve_static(path)
        else:
            self.send_404()

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        if path == '/admin/restore':
            self.handle_admin_restore(body)
        elif path == '/api/subscribe':
            self.handle_subscribe(body)
        elif path == '/api/unsubscribe-feedback':
            self.handle_unsubscribe_feedback(body)
        elif path == '/api/tributes':
            self.handle_submit_tribute(body)
        elif path == '/api/create-checkout':
            self.handle_create_checkout(body)
        elif path == '/webhook':
            self.handle_webhook(body)
        elif path == '/api/caterers/apply':
            self.handle_caterer_apply(body)
        elif path.startswith('/api/caterers/') and path.endswith('/approve'):
            caterer_id = path[len('/api/caterers/'):-len('/approve')]
            self.handle_caterer_approve(caterer_id)
        elif path.startswith('/api/caterers/') and path.endswith('/reject'):
            caterer_id = path[len('/api/caterers/'):-len('/reject')]
            self.handle_caterer_reject(caterer_id)
        elif path == '/api/vendor-leads':
            self.handle_vendor_lead(body)
        elif path == '/api/shiva':
            self.handle_create_shiva(body)
        elif path.startswith('/api/shiva/') and path.endswith('/remove-signup'):
            support_id = path[len('/api/shiva/'):-len('/remove-signup')]
            self.handle_remove_signup(support_id, body)
        elif path.startswith('/api/shiva/') and path.endswith('/signup'):
            support_id = path[len('/api/shiva/'):-len('/signup')]
            self.handle_meal_signup(support_id, body)
        elif path.startswith('/api/shiva/') and path.endswith('/report'):
            support_id = path[len('/api/shiva/'):-len('/report')]
            self.handle_shiva_report(support_id, body)
        else:
            self.send_404()

    def do_PUT(self):
        """Handle PUT requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        if path.startswith('/api/shiva/'):
            support_id = path[len('/api/shiva/'):]
            self.handle_update_shiva(support_id, body)
        else:
            self.send_404()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_cors_headers()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.end_headers()

    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Stripe-Signature')

    def serve_static(self, path):
        """Serve static files from the frontend directory"""
        filename, content_type = self.STATIC_FILES[path]
        filepath = os.path.join(FRONTEND_DIR, filename)
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            if content_type.startswith('text/') or content_type in ('application/javascript', 'application/manifest+json'):
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            else:
                self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            if content_type in ('image/svg+xml', 'image/png', 'application/manifest+json'):
                self.send_header('Cache-Control', 'public, max-age=86400')
            else:
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_404()

    # ── API: Obituaries ──────────────────────────────────────

    def get_obituaries(self, city=None):
        """Get all obituaries from database, optionally filtered by city"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if city:
                cursor.execute('SELECT * FROM obituaries WHERE city = ? ORDER BY last_updated DESC', (city,))
            else:
                cursor.execute('SELECT * FROM obituaries ORDER BY last_updated DESC')
            obituaries = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': obituaries,
                'meta': {'total': len(obituaries)}
            })
        except Exception as e:
            self.send_error_response(str(e))

    def search_obituaries(self, query):
        """Search obituaries by name"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM obituaries
                WHERE deceased_name LIKE ? OR hebrew_name LIKE ?
                ORDER BY last_updated DESC
            ''', (f'%{query}%', f'%{query}%'))

            obituaries = [dict(row) for row in cursor.fetchall()]
            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': obituaries,
                'meta': {'total': len(obituaries), 'query': query}
            })
        except Exception as e:
            self.send_error_response(str(e))

    def get_status(self):
        """Get database statistics"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM obituaries')
            total = cursor.fetchone()[0]

            cursor.execute('SELECT source, COUNT(*) FROM obituaries GROUP BY source')
            by_source = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute('SELECT COUNT(*) FROM comments')
            total_comments = cursor.fetchone()[0]

            sub_count = 0
            try:
                cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE')
                sub_count = cursor.fetchone()[0]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'total_obituaries': total,
                    'by_source': by_source,
                    'total_comments': total_comments,
                    'total_subscribers': sub_count
                }
            })
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Email Subscriptions (Double Opt-In) ─────────────

    def handle_subscribe(self, body):
        """Handle email subscription with double opt-in"""
        try:
            data = json.loads(body)
            email = data.get('email', '').strip().lower()

            if not email or '@' not in email:
                self.send_json_response({'status': 'error', 'message': 'Invalid email'}, 400)
                return

            if EMAIL_AVAILABLE:
                result = subscription_mgr.subscribe(email)
                if result.get('status') == 'success' and SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()
                self.send_json_response(result)
            else:
                # Fallback: direct insert (no double opt-in)
                db_path = self.get_db_path()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                cursor.execute('''
                    INSERT OR IGNORE INTO subscribers (email, confirmed, subscribed_at, confirmed_at)
                    VALUES (?, TRUE, ?, ?)
                ''', (email, now, now))
                conn.commit()
                conn.close()
                if SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()
                self.send_json_response({
                    'status': 'success',
                    'message': 'Successfully subscribed to daily updates!'
                })

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_confirm(self, token):
        """Handle email confirmation via token"""
        if not token:
            self.send_404()
            return

        if EMAIL_AVAILABLE:
            result = subscription_mgr.confirm_subscription(token)
            # Serve a nice HTML confirmation page
            status_class = 'success' if result['status'] == 'success' else 'error'
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subscription Confirmed - Neshama</title>
    <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;600&family=Cormorant+Garamond:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Crimson Pro', serif; background: linear-gradient(135deg, #FAF9F6 0%, #F5F5DC 100%); color: #3E2723; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem; }}
        .container {{ max-width: 500px; background: white; border-radius: 1.5rem; padding: 3rem; box-shadow: 0 10px 40px rgba(62,39,35,0.08); text-align: center; }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ font-family: 'Cormorant Garamond', serif; font-size: 2rem; font-weight: 400; margin-bottom: 1rem; }}
        p {{ font-size: 1.1rem; line-height: 1.6; margin-bottom: 1.5rem; }}
        .btn {{ display: inline-block; background: #D2691E; color: white; padding: 0.75rem 2rem; border-radius: 2rem; text-decoration: none; font-family: 'Crimson Pro', serif; font-size: 1.1rem; }}
        .btn:hover {{ background: #c45a1a; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{"✅" if status_class == "success" else "❌"}</div>
        <h1>{"Subscription Confirmed!" if status_class == "success" else "Confirmation Failed"}</h1>
        <p>{result['message']}</p>
        <a href="/feed" class="btn">View Obituaries</a>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            content = html.encode('utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error_response('Email subscription system not available', 503)

    def handle_unsubscribe_page(self, token):
        """Handle unsubscribe via token - process and show page"""
        if not token:
            self.send_404()
            return

        if EMAIL_AVAILABLE:
            result = subscription_mgr.unsubscribe(token)
            email = result.get('email', '')

            # Serve unsubscribe.html with email injected
            filepath = os.path.join(FRONTEND_DIR, 'unsubscribe.html')
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    html = f.read()
                # Inject email into the page via script
                inject_script = f'<script>document.getElementById("emailDisplay").textContent = "{email}";</script>'
                html = html.replace('</body>', f'{inject_script}</body>')
                content = html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_404()
        else:
            self.send_error_response('Email subscription system not available', 503)

    def handle_unsubscribe_feedback(self, body):
        """Handle unsubscribe feedback submission"""
        try:
            data = json.loads(body)
            email = data.get('email', '')
            reasons = data.get('reasons', [])

            # Log the feedback
            print(f"[Unsubscribe Feedback] {email}: {', '.join(reasons)}")

            # Store in database
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create feedback table if needed
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS unsubscribe_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT,
                    reasons TEXT,
                    created_at TEXT
                )
            ''')
            cursor.execute('''
                INSERT INTO unsubscribe_feedback (email, reasons, created_at)
                VALUES (?, ?, ?)
            ''', (email, json.dumps(reasons), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            self.send_json_response({'status': 'success', 'message': 'Feedback received'})

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def get_subscriber_count(self):
        """Get subscriber count"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE')
            count = cursor.fetchone()[0]
            conn.close()
            self.send_json_response({'status': 'success', 'count': count})
        except Exception as e:
            self.send_json_response({'status': 'success', 'count': 0})

    # ── API: Single Obituary & Memorial ─────────────────────────

    def get_single_obituary(self, obit_id):
        """Get a single obituary by ID"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM obituaries WHERE id = ?', (obit_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                self.send_json_response({'status': 'success', 'data': dict(row)})
            else:
                self.send_json_response({'status': 'error', 'message': 'Obituary not found'}, 404)
        except Exception as e:
            self.send_error_response(str(e))

    def serve_memorial_page(self):
        """Serve the memorial page template (JS handles data loading)"""
        filepath = os.path.join(FRONTEND_DIR, 'memorial.html')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_404()

    # ── API: Tributes ─────────────────────────────────────────

    def get_tributes(self, obit_id):
        """Get tributes for an obituary"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM tributes WHERE obituary_id = ? ORDER BY created_at DESC',
                (obit_id,)
            )
            tributes = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_json_response({'status': 'success', 'data': tributes, 'count': len(tributes)})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': [], 'count': 0})

    def get_tribute_counts(self):
        """Get tribute counts for all obituaries"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT obituary_id, COUNT(*) as count FROM tributes GROUP BY obituary_id'
            )
            counts = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            self.send_json_response({'status': 'success', 'data': counts})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': {}})

    def handle_submit_tribute(self, body):
        """Handle tribute submission"""
        try:
            data = json.loads(body)
            obit_id = data.get('obituary_id', '').strip()
            author = data.get('author_name', '').strip()
            message = data.get('message', '').strip()
            relationship = data.get('relationship', '').strip()

            if not obit_id or not author or not message:
                self.send_json_response({'status': 'error', 'message': 'Name and message are required'}, 400)
                return

            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                'INSERT INTO tributes (obituary_id, author_name, message, relationship, created_at) VALUES (?, ?, ?, ?, ?)',
                (obit_id, author, message, relationship, now)
            )
            conn.commit()
            tribute_id = cursor.lastrowid
            conn.close()

            if SHIVA_AVAILABLE:
                shiva_mgr._trigger_backup()

            self.send_json_response({
                'status': 'success',
                'message': 'Tribute submitted',
                'id': tribute_id
            })
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Community Stats ──────────────────────────────────

    def get_community_stats(self):
        """Get community-wide statistics"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM obituaries')
            total_obituaries = cursor.fetchone()[0]

            total_tributes = 0
            try:
                cursor.execute('SELECT COUNT(*) FROM tributes')
                total_tributes = cursor.fetchone()[0]
            except Exception:
                pass

            sub_count = 0
            try:
                cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE')
                sub_count = cursor.fetchone()[0]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'souls_remembered': total_obituaries,
                    'tributes_left': total_tributes,
                    'community_members': sub_count
                }
            })
        except Exception as e:
            self.send_json_response({
                'status': 'success',
                'data': {'souls_remembered': 0, 'tributes_left': 0, 'community_members': 0}
            })

    # ── Admin: Scraper ─────────────────────────────────────────

    def handle_admin_scrape(self):
        """Run scrapers via admin endpoint (async - returns immediately)"""
        global _scrape_status
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        if _scrape_status['running']:
            self.send_json_response({
                'status': 'already_running',
                'message': 'Scraper is already running',
                'started': _scrape_status['last_started']
            })
            return

        # Mark as running and return 200 immediately
        _scrape_status['running'] = True
        _scrape_status['last_started'] = datetime.now().isoformat()
        _scrape_status['last_result'] = None
        _scrape_status['last_error'] = None

        def run_scrape_background():
            global _scrape_status
            project_root = os.path.join(FRONTEND_DIR, '..')
            try:
                result = subprocess.run(
                    ['python', 'master_scraper.py'],
                    capture_output=True,
                    text=True,
                    cwd=project_root,
                    timeout=300
                )
                _scrape_status['last_result'] = {
                    'returncode': result.returncode,
                    'stdout': result.stdout[-2000:] if result.stdout else '',
                    'stderr': result.stderr[-500:] if result.stderr else '',
                }
                _scrape_status['last_completed'] = datetime.now().isoformat()
                print(f"[Scraper] Background scrape completed (exit code {result.returncode})")
            except subprocess.TimeoutExpired:
                _scrape_status['last_error'] = 'Scraper timed out after 5 minutes'
                _scrape_status['last_completed'] = datetime.now().isoformat()
                print("[Scraper] Background scrape timed out")
            except Exception as e:
                _scrape_status['last_error'] = str(e)
                _scrape_status['last_completed'] = datetime.now().isoformat()
                print(f"[Scraper] Background scrape error: {e}")
            finally:
                _scrape_status['running'] = False

        thread = threading.Thread(target=run_scrape_background, daemon=True)
        thread.start()

        self.send_json_response({
            'status': 'started',
            'message': 'Scraper started in background',
            'started': _scrape_status['last_started'],
            'check_status': '/admin/scrape-status'
        })

    def handle_scrape_status(self):
        """Check the status of the background scraper"""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        self.send_json_response({
            'running': _scrape_status['running'],
            'last_started': _scrape_status['last_started'],
            'last_completed': _scrape_status['last_completed'],
            'last_result': _scrape_status['last_result'],
            'last_error': _scrape_status['last_error'],
        })

    def handle_admin_digest(self):
        """Send daily email digest via admin endpoint"""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        try:
            from daily_digest import DailyDigestSender
            sender = DailyDigestSender(db_path=DB_PATH)
            result = sender.send_daily_digest()
            self.send_json_response({
                'status': 'success',
                'digest': result
            })
        except Exception as e:
            self.send_error_response(f'Digest error: {str(e)}', 500)

    # ── Admin: Backup / Restore ─────────────────────────────

    def handle_admin_backup(self):
        """Return full backup JSON of all critical tables."""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        if not SHIVA_AVAILABLE:
            self.send_error_response('Shiva manager not available', 503)
            return

        data = shiva_mgr.get_backup_data()
        self.send_json_response(data)

    def handle_admin_restore(self, body):
        """Restore from uploaded backup JSON."""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        if not SHIVA_AVAILABLE:
            self.send_error_response('Shiva manager not available', 503)
            return

        try:
            data = json.loads(body)
            restored = shiva_mgr.restore_from_data(data)
            self.send_json_response({
                'status': 'success',
                'message': f'Restored {restored} rows',
                'rows_restored': restored
            })
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Payment / Stripe ────────────────────────────────

    def handle_create_checkout(self, body):
        """Create Stripe checkout session"""
        if not STRIPE_AVAILABLE:
            self.send_json_response({
                'status': 'info',
                'message': 'Stripe not configured yet. Set STRIPE_SECRET_KEY environment variable.',
                'test_mode': True
            })
            return

        try:
            data = json.loads(body)
            email = data.get('email', '')
            success_url = data.get('success_url', 'https://neshama.ca/premium-success')
            cancel_url = data.get('cancel_url', 'https://neshama.ca/premium-cancelled')

            result = payment_mgr.create_checkout_session(email, success_url, cancel_url)
            self.send_json_response(result)

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_manage_subscription(self):
        """Redirect to Stripe Customer Portal for subscription management"""
        if not STRIPE_AVAILABLE:
            self.send_json_response({
                'status': 'info',
                'message': 'Stripe not configured. Set STRIPE_SECRET_KEY.'
            })
            return

        # Get email from query params
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        email = query_params.get('email', [''])[0]

        if not email:
            # Serve a page that asks for email
            html = """<!DOCTYPE html>
<html><head><title>Manage Subscription</title>
<link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;600&display=swap" rel="stylesheet">
<style>body{font-family:'Crimson Pro',serif;background:linear-gradient(135deg,#FAF9F6,#F5F5DC);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:2rem}
.box{background:white;padding:3rem;border-radius:1.5rem;max-width:400px;width:100%;text-align:center;box-shadow:0 10px 40px rgba(62,39,35,0.08)}
h2{font-size:1.8rem;margin-bottom:1rem;color:#3E2723}p{color:#B2BEB5;margin-bottom:1.5rem}
input{width:100%;padding:1rem;border:2px solid #D4C5B9;border-radius:2rem;font-size:1rem;margin-bottom:1rem;font-family:inherit}
button{background:#D2691E;color:white;border:none;padding:1rem 2rem;border-radius:2rem;font-size:1rem;cursor:pointer;font-family:inherit;width:100%}
button:hover{background:#c45a1a}</style></head>
<body><div class="box"><h2>Manage Subscription</h2><p>Enter your email to manage your premium subscription</p>
<form onsubmit="event.preventDefault();window.location='/manage-subscription?email='+encodeURIComponent(document.getElementById('e').value)">
<input type="email" id="e" placeholder="Your email" required><button type="submit">Continue</button></form></div></body></html>"""
            content = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        result = payment_mgr.create_customer_portal_session(
            email,
            return_url='https://neshama.ca/feed'
        )

        if 'url' in result:
            # Redirect to Stripe Customer Portal
            self.send_response(302)
            self.send_header('Location', result['url'])
            self.end_headers()
        else:
            self.send_json_response({
                'status': 'error',
                'message': result.get('error', 'No subscription found for this email')
            }, 404)

    def handle_webhook(self, body):
        """Handle Stripe webhook"""
        if not STRIPE_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Stripe not configured'}, 400)
            return

        try:
            signature = self.headers.get('Stripe-Signature', '')
            webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

            result = payment_mgr.handle_webhook(body, signature, webhook_secret)

            if result['status'] == 'success':
                self.send_json_response(result)
            else:
                self.send_json_response(result, 400)

        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Caterer Partners ─────────────────────────────

    def _check_admin_token(self):
        """Verify admin token from query params."""
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [''])[0]
        admin_token = os.environ.get('ADMIN_TOKEN', 'neshama-admin-2026')
        return token == admin_token

    def get_caterers(self):
        """Get approved caterers with optional filters"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'success', 'data': []})
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        filters = {
            'kosher': query_params.get('kosher', [None])[0] == 'true',
            'delivery': query_params.get('delivery', [None])[0] == 'true',
            'online_ordering': query_params.get('online_ordering', [None])[0] == 'true',
        }
        has_filters = any(filters.values())
        if has_filters:
            result = shiva_mgr.get_caterers_filtered(filters)
        else:
            result = shiva_mgr.get_approved_caterers()
        self.send_json_response(result)

    def get_pending_caterers(self):
        """Get pending caterer applications (admin only)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        if not self._check_admin_token():
            self.send_error_response('Unauthorized', 403)
            return
        result = shiva_mgr.get_pending_applications()
        self.send_json_response(result)

    def handle_caterer_apply(self, body):
        """Handle caterer application submission"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            result = shiva_mgr.submit_caterer_application(data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_caterer_approve(self, caterer_id):
        """Approve a caterer application (admin only)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        if not self._check_admin_token():
            self.send_error_response('Unauthorized', 403)
            return
        result = shiva_mgr.approve_caterer(caterer_id)
        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
        status_code = 200 if result['status'] == 'success' else 400
        self.send_json_response(result, status_code)

    def handle_caterer_reject(self, caterer_id):
        """Reject a caterer application (admin only)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        if not self._check_admin_token():
            self.send_error_response('Unauthorized', 403)
            return
        result = shiva_mgr.reject_caterer(caterer_id)
        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
        status_code = 200 if result['status'] == 'success' else 400
        self.send_json_response(result, status_code)

    # ── API: Vendor Directory ─────────────────────────────

    def get_vendors(self):
        """Get all vendors, optionally filtered by category or kosher status"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vendors ORDER BY featured DESC, name ASC')
            vendors = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_json_response({'status': 'success', 'data': vendors})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': []})

    def get_vendor_by_slug(self, slug):
        """Get a single vendor by slug"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vendors WHERE slug = ?', (slug,))
            row = cursor.fetchone()
            conn.close()
            if row:
                self.send_json_response({'status': 'success', 'data': dict(row)})
            else:
                self.send_json_response({'status': 'error', 'message': 'Vendor not found'}, 404)
        except Exception as e:
            self.send_error_response(str(e))

    def serve_vendor_page(self):
        """Serve the vendor detail page template (JS handles data loading)"""
        filepath = os.path.join(FRONTEND_DIR, 'vendor-detail.html')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_404()

    def handle_vendor_lead(self, body):
        """Handle vendor lead form submission"""
        try:
            data = json.loads(body)
            contact_name = data.get('contact_name', '').strip()
            contact_email = data.get('contact_email', '').strip()
            vendor_id = data.get('vendor_id')
            vendor_name = data.get('vendor_name', '').strip()
            event_type = data.get('event_type', '').strip()
            event_date = data.get('event_date', '').strip()
            estimated_guests = data.get('estimated_guests')
            message = data.get('message', '').strip()

            if not contact_name or not contact_email or not vendor_id:
                self.send_json_response({
                    'status': 'error',
                    'message': 'Name, email, and vendor are required'
                }, 400)
                return

            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute('''
                INSERT INTO vendor_leads (vendor_id, vendor_name, contact_name, contact_email,
                                          event_type, event_date, estimated_guests, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (vendor_id, vendor_name, contact_name, contact_email,
                  event_type, event_date, estimated_guests, message, now))

            conn.commit()
            lead_id = cursor.lastrowid
            conn.close()

            # Log the lead
            print(f"[Vendor Lead] {contact_name} ({contact_email}) -> {vendor_name}")

            self.send_json_response({
                'status': 'success',
                'message': 'Inquiry submitted successfully',
                'id': lead_id
            })

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Shiva Support ─────────────────────────────────

    def serve_shiva_page(self):
        """Serve the shiva community view page (JS handles data loading)"""
        filepath = os.path.join(FRONTEND_DIR, 'shiva-view.html')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(content)
            # Track page view
            if SHIVA_AVAILABLE:
                path = urlparse(self.path).path
                support_id = path[len('/shiva/'):] if path.startswith('/shiva/') else None
                shiva_mgr.track_event('page_view', support_id)
        except FileNotFoundError:
            self.send_404()

    def get_shiva_by_obituary(self, obit_id):
        """Check if shiva support exists for an obituary"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'not_found', 'message': 'Shiva support not available'})
            return
        result = shiva_mgr.get_support_by_obituary(obit_id)
        self.send_json_response(result)

    def get_shiva_details(self, support_id):
        """Get shiva support page details (no address)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'not_found'})
            return
        # Check for organizer token in query params
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [None])[0]

        if token:
            result = shiva_mgr.get_support_for_organizer(support_id, token)
        else:
            result = shiva_mgr.get_support_by_id(support_id)
        self.send_json_response(result)

    def get_shiva_meals(self, support_id):
        """Get meal signups for a shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'success', 'data': []})
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [None])[0]

        if token:
            result = shiva_mgr.get_signups_for_organizer(support_id, token)
        else:
            result = shiva_mgr.get_signups(support_id)
        self.send_json_response(result)

    def handle_create_shiva(self, body):
        """Create a new shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            obit_id = data.get('obituary_id')
            shiva_mgr.track_event('organize_start', obit_id)
            result = shiva_mgr.create_support(data)
            if result['status'] == 'success':
                shiva_mgr.track_event('organize_complete', obit_id)
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] in ('success', 'duplicate') else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_meal_signup(self, support_id, body):
        """Handle volunteer meal signup"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            data['shiva_support_id'] = support_id
            result = shiva_mgr.signup_meal(data)
            if result['status'] == 'success':
                shiva_mgr.track_event('meal_signup', support_id)
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_remove_signup(self, support_id, body):
        """Handle organizer removing a meal signup"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.get('magic_token', '')
            signup_id = data.get('signup_id')
            if not token or not signup_id:
                self.send_json_response({'status': 'error', 'message': 'Token and signup_id required'}, 400)
                return
            result = shiva_mgr.remove_signup(support_id, signup_id, token)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_shiva_report(self, support_id, body):
        """Handle report of a shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            data['shiva_support_id'] = support_id
            result = shiva_mgr.report_page(data)
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_update_shiva(self, support_id, body):
        """Handle organizer update to shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.pop('magic_token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization token required'}, 401)
                return
            result = shiva_mgr.update_support(support_id, token, data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    # ── Helpers ──────────────────────────────────────────────

    def get_db_path(self):
        """Get path to database file"""
        possible_paths = [
            DB_PATH,
            os.path.join(FRONTEND_DIR, '..', 'neshama.db'),
            os.path.expanduser('~/Desktop/Neshama/neshama.db'),
            './neshama.db',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        raise FileNotFoundError('Database file not found.')

    def send_json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        response = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(response.encode('utf-8'))

    def send_error_response(self, message, status=500):
        """Send error response"""
        self.send_json_response({
            'status': 'error',
            'error': {'message': message}
        }, status)

    def send_404(self):
        """Send 404 response"""
        self.send_error_response('Endpoint not found', 404)

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[API] {format % args}")

def auto_scrape_on_startup():
    """Run scrapers in background thread on startup to populate database.
    Handles Render free tier ephemeral storage - data is lost on restart,
    so we re-scrape each time the server starts."""
    project_root = os.path.join(FRONTEND_DIR, '..')
    try:
        # Check if database is empty
        db_path_to_check = DB_PATH
        if not os.path.exists(db_path_to_check):
            # Try fallback paths
            for p in [os.path.join(FRONTEND_DIR, '..', 'neshama.db'), './neshama.db']:
                if os.path.exists(p):
                    db_path_to_check = p
                    break

        needs_scrape = True
        if os.path.exists(db_path_to_check):
            try:
                conn = sqlite3.connect(db_path_to_check)
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM obituaries')
                count = cursor.fetchone()[0]
                conn.close()
                if count > 0:
                    needs_scrape = False
                    print(f"[Startup] Database has {count} obituaries, skipping auto-scrape")
            except Exception:
                pass

        if needs_scrape:
            print("[Startup] Database empty - running auto-scrape in background...")
            result = subprocess.run(
                ['python', 'master_scraper.py'],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=300
            )
            if result.returncode == 0:
                print("[Startup] Auto-scrape completed successfully")
            else:
                print(f"[Startup] Auto-scrape had issues: {result.stderr[:200]}")
    except Exception as e:
        print(f"[Startup] Auto-scrape error (non-fatal): {e}")


def run_server(port=None):
    """Start the API server"""
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, NeshamaAPIHandler)

    # Launch auto-scrape in background thread (non-blocking)
    scrape_thread = threading.Thread(target=auto_scrape_on_startup, daemon=True)
    scrape_thread.start()

    print(f"\n{'='*60}")
    print(f" NESHAMA API SERVER v2.0")
    print(f"{'='*60}")
    print(f"\n Running on: http://0.0.0.0:{port}")
    print(f"\n Pages:")
    print(f"   /                          - Landing page")
    print(f"   /feed                      - Obituary feed")
    print(f"   /memorial/{{id}}             - Memorial page")
    print(f"   /about                     - About")
    print(f"   /faq                       - FAQ")
    print(f"   /privacy                   - Privacy Policy")
    print(f"   /confirm/{{token}}           - Email confirmation")
    print(f"   /unsubscribe/{{token}}       - Unsubscribe")
    print(f"   /manage-subscription       - Stripe customer portal")
    print(f"   /premium-success           - Payment success")
    print(f"   /premium-cancelled         - Payment cancelled")
    print(f"   /shiva/organize            - Set up shiva support")
    print(f"   /shiva/{{id}}               - Community support page")
    print(f"\n API Endpoints:")
    print(f"   GET  /api/obituaries       - All obituaries")
    print(f"   GET  /api/obituary/{{id}}    - Single obituary")
    print(f"   GET  /api/search?q=name    - Search")
    print(f"   GET  /api/status           - Database stats")
    print(f"   GET  /api/community-stats  - Community statistics")
    print(f"   GET  /api/tributes/{{id}}    - Tributes for obituary")
    print(f"   GET  /api/tributes/counts  - All tribute counts")
    print(f"   GET  /api/subscribers/count - Subscriber count")
    print(f"   POST /api/subscribe        - Email subscription")
    print(f"   POST /api/tributes         - Submit tribute")
    print(f"   POST /api/unsubscribe-feedback - Unsubscribe feedback")
    print(f"   POST /api/create-checkout  - Stripe checkout")
    print(f"   POST /webhook              - Stripe webhook")
    print(f"   GET  /api/shiva/obituary/{{id}} - Check shiva support")
    print(f"   GET  /api/shiva/{{id}}      - Shiva support details")
    print(f"   GET  /api/shiva/{{id}}/meals - Meal signups")
    print(f"   POST /api/shiva            - Create shiva support")
    print(f"   POST /api/shiva/{{id}}/signup - Volunteer meal signup")
    print(f"   POST /api/shiva/{{id}}/report - Report shiva page")
    print(f"   POST /api/shiva/{{id}}/remove-signup - Remove signup (organizer)")
    print(f"   PUT  /api/shiva/{{id}}      - Update shiva support")
    print(f"   GET  /api/caterers         - Approved caterers")
    print(f"   POST /api/caterers/apply   - Caterer application")
    print(f"   GET  /api/caterers/pending - Pending applications (admin)")
    print(f"   POST /api/caterers/{{id}}/approve - Approve caterer (admin)")
    print(f"   POST /api/caterers/{{id}}/reject  - Reject caterer (admin)")
    print(f"   GET  /api/vendors          - All vendors")
    print(f"   GET  /api/vendors/{{slug}}   - Vendor by slug")
    print(f"   POST /api/vendor-leads     - Vendor inquiry")
    print(f"   GET  /directory/{{slug}}     - Vendor detail page")
    print(f"   GET  /admin/backup             - Download backup JSON (admin)")
    print(f"   POST /admin/restore            - Upload backup JSON (admin)")
    print(f"\n Email: {'SendGrid connected' if EMAIL_AVAILABLE and subscription_mgr.sendgrid_api_key else 'TEST MODE' if EMAIL_AVAILABLE else 'Not available'}")
    print(f" Stripe: {'Connected' if STRIPE_AVAILABLE else 'Not configured (set STRIPE_SECRET_KEY)'}")
    print(f" Shiva support: {'Available' if SHIVA_AVAILABLE else 'Not available'}")

    # Archive expired shiva support pages + seed caterer data
    if SHIVA_AVAILABLE:
        try:
            shiva_mgr.archive_expired()
        except Exception as e:
            print(f"  Shiva archive check: {e}")
        # Seed Jem Salads as pre-approved caterer
        try:
            shiva_mgr.seed_caterer({
                'business_name': 'Jem Salads',
                'contact_name': 'Jem Salads Team',
                'email': 'info@jemsalads.com',
                'phone': '(416) 785-6161',
                'website': 'https://www.jemsalads.com',
                'delivery_area': 'Toronto',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$',
                'shiva_menu_description': 'Jem Salads specializes in fresh, wholesome platters and prepared meals with a focus on quality ingredients and generous portions. They have extensive experience catering shiva meals and understand the specific needs of mourning families \u2014 from dietary requirements to flexible delivery timing. Platters and hot meals available, feeds 10\u201350+.',
            })
        except Exception as e:
            print(f"  Caterer seed: {e}")
    # Seed vendor directory
    if VENDORS_AVAILABLE:
        try:
            seed_vendors(DB_PATH)
            print(f"  Vendor directory: Seeded")
        except Exception as e:
            print(f"  Vendor seed: {e}")

    if SHIVA_AVAILABLE:
        # Auto-restore from backup if critical tables are empty
        try:
            if shiva_mgr.needs_restore():
                print("[Startup] Critical tables empty — restoring from backup.json...")
                shiva_mgr.restore_from_file()
            else:
                print("  Backup restore: not needed")
        except Exception as e:
            print(f"  Backup restore: {e}")
    print(f"\n Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
