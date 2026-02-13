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
        elif path == '/admin/scrape':
            self.handle_admin_scrape()
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

        if path == '/api/subscribe':
            self.handle_subscribe(body)
        elif path == '/api/unsubscribe-feedback':
            self.handle_unsubscribe_feedback(body)
        elif path == '/api/tributes':
            self.handle_submit_tribute(body)
        elif path == '/api/create-checkout':
            self.handle_create_checkout(body)
        elif path == '/webhook':
            self.handle_webhook(body)
        else:
            self.send_404()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_cors_headers()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.end_headers()

    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Stripe-Signature')

    def serve_static(self, path):
        """Serve static files from the frontend directory"""
        filename, content_type = self.STATIC_FILES[path]
        filepath = os.path.join(FRONTEND_DIR, filename)
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            if content_type.startswith('text/') or content_type == 'application/javascript':
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            else:
                self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            if content_type in ('image/svg+xml',):
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
        """Run scrapers via admin endpoint"""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if admin_secret:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
            if token != admin_secret:
                self.send_error_response('Unauthorized', 403)
                return

        project_root = os.path.join(FRONTEND_DIR, '..')
        try:
            result = subprocess.run(
                ['python', 'master_scraper.py'],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=300
            )
            output = result.stdout + '\n' + result.stderr
            html = f"""<!DOCTYPE html><html><head><title>Scraper Output</title>
<style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:2rem}}
pre{{white-space:pre-wrap;word-wrap:break-word}}h1{{color:#D2691E}}</style></head>
<body><h1>Scraper Output</h1><pre>{output}</pre>
<p><a href="/api/status" style="color:#D2691E">Check API status</a> |
<a href="/feed" style="color:#D2691E">View feed</a></p></body></html>"""
            content = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except subprocess.TimeoutExpired:
            self.send_error_response('Scraper timed out after 5 minutes', 504)
        except Exception as e:
            self.send_error_response(f'Scraper error: {str(e)}', 500)

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
    print(f"\n Email: {'SendGrid connected' if EMAIL_AVAILABLE and subscription_mgr.sendgrid_api_key else 'TEST MODE' if EMAIL_AVAILABLE else 'Not available'}")
    print(f" Stripe: {'Connected' if STRIPE_AVAILABLE else 'Not configured (set STRIPE_SECRET_KEY)'}")
    print(f"\n Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
