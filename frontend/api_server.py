#!/usr/bin/env python3
"""
Neshama API Server v1.3
Serves frontend, API endpoints, email subscriptions (SendGrid double opt-in), and payment integration
Auto-scrapes on startup to handle Render free tier ephemeral storage
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import html as html_mod
import json
import sqlite3
import os
import re
import subprocess
import threading
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime
import pytz
import logging

import time as _time_module

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(FRONTEND_DIR, '..', 'neshama.db'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 1200))  # 20 minutes default

# ── Rate Limiter ─────────────────────────────────────────
# Simple in-memory rate limiter for email-sending endpoints.
# Keyed by (client_ip, endpoint). Allows max N calls per window.
_rate_limit_store = {}  # key -> list of timestamps
_RATE_LIMIT_WINDOW = 300   # 5 minutes
_RATE_LIMIT_MAX_CALLS = 3  # max 3 email-sends per 5 min per IP


def _check_rate_limit(client_ip, endpoint, max_calls=_RATE_LIMIT_MAX_CALLS, window=_RATE_LIMIT_WINDOW):
    """Return True if the request is within rate limits, False if exceeded."""
    key = (client_ip, endpoint)
    now = _time_module.time()
    timestamps = _rate_limit_store.get(key, [])
    # Prune old entries
    timestamps = [t for t in timestamps if now - t < window]
    if len(timestamps) >= max_calls:
        _rate_limit_store[key] = timestamps
        return False
    timestamps.append(now)
    _rate_limit_store[key] = timestamps
    return True


def _html_to_plain(html_str):
    """Convert HTML email to readable plain text"""
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

# Import vendor seed script
try:
    sys_path_parent = os.path.join(FRONTEND_DIR, '..')
    import sys as _sys
    if sys_path_parent not in _sys.path:
        _sys.path.insert(0, sys_path_parent)
    from seed_vendors import seed_vendors, create_tables as create_vendor_tables, backfill_vendor_emails
    VENDORS_AVAILABLE = True
except Exception as e:
    VENDORS_AVAILABLE = False
    logging.info(f" Vendor directory: Not available ({e})")

# Import EmailSubscriptionManager
try:
    import sys
    sys.path.insert(0, FRONTEND_DIR)
    from subscription_manager import EmailSubscriptionManager
    subscription_mgr = EmailSubscriptionManager(db_path=DB_PATH)
    EMAIL_AVAILABLE = True
    logging.info(f" Email subscription: {'SendGrid connected' if subscription_mgr.sendgrid_api_key else 'TEST MODE (console logging)'}")
except Exception as e:
    EMAIL_AVAILABLE = False
    subscription_mgr = None
    logging.info(f" Email subscription: Not available ({e})")

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
    logging.info(f" Shiva support: Available")
except Exception as e:
    SHIVA_AVAILABLE = False
    shiva_mgr = None
    logging.info(f" Shiva support: Not available ({e})")

# Email queue processor (v2)
try:
    from email_queue import process_email_queue, log_immediate_email
    EMAIL_QUEUE_AVAILABLE = True
    logging.info(f" Email queue: Available")
except Exception as e:
    EMAIL_QUEUE_AVAILABLE = False
    logging.info(f" Email queue: Not available ({e})")

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
        '/og-image.png': ('og-image.png', 'image/png'),
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
        '/gifts': ('gifts.html', 'text/html'),
        '/gifts.html': ('gifts.html', 'text/html'),
        '/gifts/plant-a-tree': ('plant-a-tree.html', 'text/html'),
        '/plant-a-tree': ('plant-a-tree.html', 'text/html'),
        '/sitemap.xml': ('sitemap.xml', 'application/xml'),
        '/robots.txt': ('robots.txt', 'text/plain'),
    }

    def do_GET(self):
        """Handle GET requests"""
        _req_start = _time_module.time()
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Health check endpoint (fast path, no auth)
        if path == '/api/health':
            self._handle_health_check()
            self._log_request('GET', path, 200, _req_start)
            return

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
        elif path == '/api/scraper-status':
            self.get_scraper_status()
        elif path == '/api/subscribers/count':
            self.get_subscriber_count()
        elif path == '/api/community-stats':
            self.get_community_stats()
        elif path == '/api/directory-stats':
            self.get_directory_stats()
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
        elif path == '/api/gift-vendors':
            self.get_gift_vendors()
        elif path == '/api/track-click':
            self.handle_track_click()
        elif path.startswith('/api/vendors/'):
            slug = path[len('/api/vendors/'):]
            self.get_vendor_by_slug(slug)
        # Vendor detail pages (/directory/slug)
        elif path.startswith('/directory/') and path != '/directory/' and path not in self.STATIC_FILES:
            self.serve_vendor_page()
        # Shiva access request routes (must be before /api/shiva/ catch-all)
        elif path == '/api/shiva-access/approve':
            self.handle_access_approve()
        elif path == '/api/shiva-access/deny':
            self.handle_access_deny()
        # V2: Email verification
        elif path == '/api/shiva/verify-email':
            self.handle_verify_email()
        # V2: Accept co-organizer invite
        elif path == '/api/shiva/accept-invite':
            self.handle_accept_co_organizer()
        # V2: List co-organizers (must be before /api/shiva/{id} catch-all)
        elif path.startswith('/api/shiva/') and path.endswith('/co-organizers'):
            support_id = path[len('/api/shiva/'):-len('/co-organizers')]
            self.handle_list_co_organizers(support_id)
        # Shiva API endpoints
        elif path.startswith('/api/shiva/obituary/'):
            obit_id = path[len('/api/shiva/obituary/'):]
            self.get_shiva_by_obituary(obit_id)
        elif path.startswith('/api/shiva/') and path.endswith('/meals'):
            support_id = path[len('/api/shiva/'):-len('/meals')]
            self.get_shiva_meals(support_id)
        # V3: Get updates
        elif path.startswith('/api/shiva/') and path.endswith('/updates'):
            support_id = path[len('/api/shiva/'):-len('/updates')]
            self.handle_get_updates(support_id)
        elif path.startswith('/api/shiva/') and not path.endswith('/meals') and not path.endswith('/updates'):
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
        elif path == '/api/vendor-views':
            self.handle_vendor_view(body)
        elif path == '/api/shiva-access/request':
            self.handle_access_request(body)
        elif path == '/api/shiva':
            self.handle_create_shiva(body)
        elif path.startswith('/api/shiva/') and path.endswith('/remove-signup'):
            support_id = path[len('/api/shiva/'):-len('/remove-signup')]
            self.handle_remove_signup(support_id, body)
        # V2: Multi-date signup
        elif path.startswith('/api/shiva/') and path.endswith('/signup-multi'):
            support_id = path[len('/api/shiva/'):-len('/signup-multi')]
            self.handle_meal_signup_multi(support_id, body)
        elif path.startswith('/api/shiva/') and path.endswith('/signup'):
            support_id = path[len('/api/shiva/'):-len('/signup')]
            self.handle_meal_signup(support_id, body)
        # V2: Co-organizer invite
        elif path.startswith('/api/shiva/') and '/co-organizers/invite' in path:
            support_id = path[len('/api/shiva/'):path.index('/co-organizers/invite')]
            self.handle_invite_co_organizer(support_id, body)
        # V2: Co-organizer revoke
        elif path.startswith('/api/shiva/') and '/co-organizers/' in path and path.endswith('/revoke'):
            parts = path[len('/api/shiva/'):].split('/co-organizers/')
            support_id = parts[0]
            co_id = parts[1].replace('/revoke', '')
            self.handle_revoke_co_organizer(support_id, co_id, body)
        # V3: Post update / delete update
        elif path.startswith('/api/shiva/') and path.endswith('/updates'):
            support_id = path[len('/api/shiva/'):-len('/updates')]
            self.handle_post_update(support_id, body)
        # V3: Send thank-you notes
        elif path.startswith('/api/shiva/') and path.endswith('/send-thank-you'):
            support_id = path[len('/api/shiva/'):-len('/send-thank-you')]
            self.handle_send_thank_you(support_id, body)
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
                cursor.execute('''
                    SELECT o.*,
                           CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                    FROM obituaries o
                    LEFT JOIN shiva_support s
                      ON s.obituary_id = o.id AND s.status = 'active'
                    WHERE o.city = ?
                    ORDER BY o.last_updated DESC
                ''', (city,))
            else:
                cursor.execute('''
                    SELECT o.*,
                           CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                    FROM obituaries o
                    LEFT JOIN shiva_support s
                      ON s.obituary_id = o.id AND s.status = 'active'
                    ORDER BY o.last_updated DESC
                ''')
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
                SELECT o.*,
                       CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                FROM obituaries o
                LEFT JOIN shiva_support s
                  ON s.obituary_id = o.id AND s.status = 'active'
                WHERE o.deceased_name LIKE ? OR o.hebrew_name LIKE ?
                ORDER BY o.last_updated DESC
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

    def get_scraper_status(self):
        """Get last scraper run time for freshness indicator"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            last_run = None
            try:
                cursor.execute('''
                    SELECT MAX(run_time) as last_run
                    FROM scraper_log
                    WHERE status = 'success'
                ''')
                row = cursor.fetchone()
                if row and row[0]:
                    last_run = row[0]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'last_run': last_run,
                    'interval_minutes': SCRAPE_INTERVAL // 60,
                    'shabbat_mode': is_shabbat()
                }
            })
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Email Subscriptions (Double Opt-In) ─────────────

    def handle_subscribe(self, body):
        """Handle email subscription with double opt-in and preferences"""
        try:
            data = json.loads(body)
            email = data.get('email', '').strip().lower()
            frequency = data.get('frequency', 'daily')
            locations = data.get('locations', 'toronto,montreal')
            consent = data.get('consent', False)

            # Normalize locations: accept list or comma-string
            if isinstance(locations, list):
                locations = ','.join(locations)

            if not email or '@' not in email:
                self.send_json_response({'status': 'error', 'message': 'Invalid email'}, 400)
                return

            # CASL: require explicit consent
            if not consent:
                self.send_json_response({'status': 'error', 'message': 'Consent is required to subscribe'}, 400)
                return

            if EMAIL_AVAILABLE:
                result = subscription_mgr.subscribe(email, frequency, locations)
                if result.get('status') == 'success' and SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()
                self.send_json_response(result)
            else:
                # Fallback: direct insert (no double opt-in)
                # Apply same email regex validation as subscription_manager
                if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email):
                    self.send_json_response({'status': 'error', 'message': 'Please enter a valid email address'}, 400)
                    return
                # Validate frequency/locations in fallback path
                if frequency not in ('daily', 'weekly'):
                    frequency = 'daily'
                valid_locs = {'toronto', 'montreal'}
                loc_list = [l.strip() for l in locations.split(',') if l.strip() in valid_locs]
                if not loc_list:
                    loc_list = ['toronto', 'montreal']
                locations = ','.join(sorted(loc_list))

                db_path = self.get_db_path()
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                cursor.execute('''
                    INSERT OR IGNORE INTO subscribers (email, confirmed, subscribed_at, confirmed_at, frequency, locations)
                    VALUES (?, TRUE, ?, ?, ?, ?)
                ''', (email, now, now, frequency, locations))
                conn.commit()
                conn.close()
                if SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()
                self.send_json_response({
                    'status': 'success',
                    'message': 'Successfully subscribed!'
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
        <p>{html_mod.escape(result['message'])}</p>
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
                safe_email = html_mod.escape(email).replace('"', '&quot;').replace("'", "&#39;")
                inject_script = f'<script>document.getElementById("emailDisplay").textContent = "{safe_email}";</script>'
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
            logging.info(f"[Unsubscribe Feedback] {email}: {', '.join(reasons)}")

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

    def get_directory_stats(self):
        """Get platform activity stats for caterer directory social proof"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM obituaries')
            obituary_count = cursor.fetchone()[0]

            active_shiva_count = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM shiva_support WHERE status = 'active'")
                active_shiva_count = cursor.fetchone()[0]
            except Exception:
                pass

            caterer_count = 0
            try:
                cursor.execute("SELECT COUNT(*) FROM caterer_partners WHERE status = 'approved'")
                caterer_count = cursor.fetchone()[0]
            except Exception:
                pass

            # Fall back to vendors table if no approved caterer_partners
            if caterer_count == 0:
                try:
                    cursor.execute("SELECT COUNT(*) FROM vendors WHERE vendor_type = 'food'")
                    caterer_count = cursor.fetchone()[0]
                except Exception:
                    pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'obituary_count': obituary_count,
                    'active_shiva_count': active_shiva_count,
                    'caterer_count': caterer_count
                }
            })
        except Exception as e:
            self.send_json_response({
                'status': 'success',
                'data': {'obituary_count': 0, 'active_shiva_count': 0, 'caterer_count': 0}
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
                logging.info(f"[Scraper] Background scrape completed (exit code {result.returncode})")
            except subprocess.TimeoutExpired:
                _scrape_status['last_error'] = 'Scraper timed out after 5 minutes'
                _scrape_status['last_completed'] = datetime.now().isoformat()
                logging.info("[Scraper] Background scrape timed out")
            except Exception as e:
                _scrape_status['last_error'] = str(e)
                _scrape_status['last_completed'] = datetime.now().isoformat()
                logging.error(f"[Scraper] Background scrape error: {e}")
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
        try:
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
        except Exception as e:
            self.send_error_response(str(e))

    def get_pending_caterers(self):
        """Get pending caterer applications (admin only)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        if not self._check_admin_token():
            self.send_error_response('Unauthorized', 403)
            return
        try:
            result = shiva_mgr.get_pending_applications()
            self.send_json_response(result)
        except Exception as e:
            self.send_error_response(str(e))

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
        try:
            result = shiva_mgr.approve_caterer(caterer_id)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_caterer_reject(self, caterer_id):
        """Reject a caterer application (admin only)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        if not self._check_admin_token():
            self.send_error_response('Unauthorized', 403)
            return
        try:
            result = shiva_mgr.reject_caterer(caterer_id)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: Vendor Directory ─────────────────────────────

    def get_vendors(self):
        """Get food vendors"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM vendors WHERE vendor_type = 'food' ORDER BY featured DESC, name ASC")
            except Exception:
                cursor.execute('SELECT * FROM vendors ORDER BY featured DESC, name ASC')
            vendors = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_json_response({'status': 'success', 'data': vendors})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': []})

    def get_gift_vendors(self):
        """Get gift vendors"""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vendors WHERE vendor_type = 'gift' ORDER BY featured DESC, name ASC")
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
        """Handle vendor lead form submission and send alert email to vendor"""
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

            # Look up vendor email for alert
            vendor_email = None
            try:
                cursor.execute('SELECT email FROM vendors WHERE id = ?', (vendor_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    vendor_email = row[0]
            except Exception:
                pass

            conn.close()

            # Log the lead
            logging.info(f"[Vendor Lead] {contact_name} ({contact_email}) -> {vendor_name}")

            # Send alert email to vendor
            if vendor_email:
                self._send_vendor_lead_alert(
                    vendor_email=vendor_email,
                    vendor_name=vendor_name,
                    contact_name=contact_name,
                    contact_email=contact_email,
                    event_type=event_type,
                    event_date=event_date,
                    estimated_guests=estimated_guests,
                    message=message
                )

            self.send_json_response({
                'status': 'success',
                'message': 'Inquiry submitted successfully',
                'id': lead_id
            })

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_vendor_lead_alert(self, vendor_email, vendor_name, contact_name,
                                 contact_email, event_type, event_date,
                                 estimated_guests, message):
        """Send lead alert email to vendor"""
        event_label = {
            'shiva': 'Shiva Meals',
            'community_event': 'Community Event',
            'private_event': 'Private Event',
            'other': 'Other'
        }.get(event_type, event_type or 'Not specified')

        # Escape all user input to prevent HTML injection
        safe_name = html_mod.escape(contact_name or '')
        safe_email = html_mod.escape(contact_email or '')
        safe_event = html_mod.escape(event_label)
        safe_vendor = html_mod.escape(vendor_name or '')
        safe_date = html_mod.escape(str(event_date or ''))
        safe_guests = html_mod.escape(str(estimated_guests or ''))
        safe_message = html_mod.escape(message or '')

        details_rows = f'''
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a; border-bottom: 1px solid #e8e0d8;">
        <strong style="color: #3E2723;">Name:</strong> {safe_name}
    </td></tr>
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a; border-bottom: 1px solid #e8e0d8;">
        <strong style="color: #3E2723;">Email:</strong> <a href="mailto:{safe_email}" style="color: #D2691E;">{safe_email}</a>
    </td></tr>
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a; border-bottom: 1px solid #e8e0d8;">
        <strong style="color: #3E2723;">Event type:</strong> {safe_event}
    </td></tr>'''

        if event_date:
            details_rows += f'''
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a; border-bottom: 1px solid #e8e0d8;">
        <strong style="color: #3E2723;">Date:</strong> {safe_date}
    </td></tr>'''

        if estimated_guests:
            details_rows += f'''
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a; border-bottom: 1px solid #e8e0d8;">
        <strong style="color: #3E2723;">Guests:</strong> {safe_guests}
    </td></tr>'''

        if message:
            details_rows += f'''
    <tr><td style="padding: 8px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; color: #5c534a;">
        <strong style="color: #3E2723;">Message:</strong><br>{safe_message}
    </td></tr>'''

        html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; background-color: #ffffff; -webkit-font-smoothing: antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #ffffff;">
<tr><td align="center" style="padding: 40px 20px;">
<table role="presentation" width="500" cellpadding="0" cellspacing="0" style="max-width: 500px; width: 100%;">

    <tr><td style="padding-bottom: 20px; border-bottom: 1px solid #e8e0d8;">
        <span style="font-family: Georgia, 'Times New Roman', serif; font-size: 22px; color: #3E2723; letter-spacing: 0.02em;">Neshama</span>
    </td></tr>

    <tr><td style="padding: 24px 0 8px 0;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 20px; color: #D2691E; font-weight: 600;">New inquiry for {safe_vendor}</p>
    </td></tr>

    <tr><td style="padding: 8px 0 20px 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0;">Someone is interested in your services through Neshama. Here are their details:</p>
    </td></tr>

    {details_rows}

    <tr><td style="padding: 24px 0 0 0; font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.7; color: #3E2723;">
        <p style="margin: 0;">You can reply directly to this email to reach {safe_name}.</p>
    </td></tr>

    <tr><td style="padding-top: 28px; border-top: 1px solid #e8e0d8; margin-top: 20px;">
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #9e9488; line-height: 1.6;">Neshama &middot; Toronto, ON</p>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>'''

        subject = f"New inquiry from {contact_name} \u2014 Neshama"

        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        if sendgrid_key:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail, Email, To, Content, ReplyTo, MimeType
                plain_text = _html_to_plain(html)
                msg = Mail(
                    from_email=Email('updates@neshama.ca', 'Neshama'),
                    to_emails=To(vendor_email),
                    subject=subject,
                    plain_text_content=Content(MimeType.text, plain_text),
                    html_content=Content(MimeType.html, html)
                )
                msg.reply_to = ReplyTo(contact_email, contact_name)
                sg = SendGridAPIClient(sendgrid_key)
                response = sg.send(msg)
                logging.info(f"[Vendor Lead Email] Sent to {vendor_email} (status {response.status_code})")
            except Exception as e:
                logging.error(f"[Vendor Lead Email] Failed to send to {vendor_email}: {e}")
        else:
            logging.info(f"[Vendor Lead Email] TEST MODE — would send to {vendor_email}")
            logging.info(f" Subject: {subject}")
            logging.info(f" From: {contact_name} <{contact_email}> (reply-to)")

    # ── API: Click Tracking ─────────────────────────────────

    def handle_track_click(self):
        """Track vendor click and redirect to destination"""
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        vendor_slug = query_params.get('vendor', [''])[0]
        dest_url = query_params.get('dest', [''])[0]

        if not dest_url:
            self.send_404()
            return

        # Decode the URL
        dest_url = unquote(dest_url)

        # Log click to database
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vendor_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_slug TEXT NOT NULL,
                    destination_url TEXT,
                    referrer_page TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            referrer = self.headers.get('Referer', '')
            cursor.execute(
                'INSERT INTO vendor_clicks (vendor_slug, destination_url, referrer_page) VALUES (?, ?, ?)',
                (vendor_slug, dest_url, referrer)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"[Click] Failed to log click: {e}")

        # 302 redirect to destination
        self.send_response(302)
        self.send_header('Location', dest_url)
        self.send_cors_headers()
        self.end_headers()

    # ── API: Vendor View Tracking ─────────────────────────────

    def handle_vendor_view(self, body):
        """Track a vendor profile page view"""
        try:
            data = json.loads(body)
            vendor_slug = data.get('vendor_slug', '').strip()

            if not vendor_slug:
                self.send_json_response({'status': 'error', 'message': 'vendor_slug required'}, 400)
                return

            referrer_page = data.get('referrer_page', '')

            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vendor_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_slug TEXT NOT NULL,
                    referrer_page TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_views_vendor ON vendor_views(vendor_slug)
            ''')

            cursor.execute(
                'INSERT INTO vendor_views (vendor_slug, referrer_page) VALUES (?, ?)',
                (vendor_slug, referrer_page)
            )
            conn.commit()
            conn.close()

            self.send_json_response({'status': 'success'})

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            logging.error(f"[View] Failed to log view: {e}")
            self.send_json_response({'status': 'error', 'message': str(e)}, 500)

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
        try:
            result = shiva_mgr.get_support_by_obituary(obit_id)
            self.send_json_response(result)
        except Exception as e:
            self.send_error_response(str(e))

    def get_shiva_details(self, support_id):
        """Get shiva support page details (no address)"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'not_found'})
            return
        try:
            # Check for organizer token or access token in query params
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('token', [None])[0]
            access_token = query_params.get('access', [None])[0]

            if token:
                result = shiva_mgr.get_support_for_organizer(support_id, token)
            else:
                result = shiva_mgr.get_support_by_id(support_id, access_token=access_token)
            self.send_json_response(result)
        except Exception as e:
            self.send_error_response(str(e))

    def get_shiva_meals(self, support_id):
        """Get meal signups for a shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'success', 'data': []})
            return
        try:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('token', [None])[0]

            if token:
                result = shiva_mgr.get_signups_for_organizer(support_id, token)
            else:
                result = shiva_mgr.get_signups(support_id)
            self.send_json_response(result)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_create_shiva(self, body):
        """Create a new shiva support page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            obit_id = data.get('obituary_id')
            shiva_mgr.track_event('organize_start', obit_id)
            # Allow force_create to bypass fuzzy name matching
            if data.get('force_create'):
                data['_skip_similar'] = True
            result = shiva_mgr.create_support(data)
            if result['status'] == 'success':
                shiva_mgr.track_event('organize_complete', obit_id)
                shiva_mgr._trigger_backup()
                # V2: Send email verification
                self._send_verification_email(result)
            status_code = 200 if result['status'] in ('success', 'duplicate', 'similar_found') else 400
            # Don't expose verification_token to client
            safe_result = dict(result)
            safe_result.pop('verification_token', None)
            safe_result.pop('organizer_email', None)
            self.send_json_response(safe_result, status_code)
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
                # Send confirmation email (logged to email_log)
                self._send_signup_confirmation(data, result, support_id)
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_verification_email(self, result):
        """Send email verification link to organizer after page creation."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        email = result.get('organizer_email', '')
        token = result.get('verification_token', '')
        family_name = result.get('family_name', '')
        shiva_id = result.get('id', '')

        if not email or not token:
            return

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        verify_url = f"{base_url}/api/shiva/verify-email?token={token}"

        html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Verify Your Email</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(family_name)} shiva support page</p>
    </div>
    <p style="font-size:1rem;line-height:1.6;">
        Thank you for setting up a shiva support page. Please verify your email
        to enable email notifications and reminders.
    </p>
    <div style="text-align:center;margin:2rem 0;">
        <a href="{html_mod.escape(verify_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.85rem 2.5rem;border-radius:2rem;text-decoration:none;font-size:1.1rem;">Verify Email</a>
    </div>
    <p style="font-size:0.85rem;color:#B2BEB5;">If you didn't create this page, you can safely ignore this email.</p>
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

        plain_text = _html_to_plain(html_content)

        if not sendgrid_key:
            logging.info(f"[Verification] Would send verification to {email}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email as SGEmail, To, Content, MimeType

            message = Mail(
                from_email=SGEmail('updates@neshama.ca', 'Neshama'),
                to_emails=To(email),
                subject=f'Verify your email — {family_name} shiva page',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Verification] Sent to {email}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, shiva_id, 'verification',
                                        email, None, sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Verification] Failed to log email")
        except Exception:
            logging.exception("[Verification] Email error")

    def _send_signup_confirmation(self, signup_data, result, support_id):
        """Send confirmation email to volunteer after meal signup (background)"""
        try:
            sendgrid_key = os.environ.get('SENDGRID_API_KEY')
            vol_email = signup_data.get('volunteer_email', '').strip()
            vol_name = signup_data.get('volunteer_name', 'Friend')
            meal_date = signup_data.get('meal_date', '')
            meal_type = signup_data.get('meal_type', '')
            meal_desc = signup_data.get('meal_description', '')
            will_serve = signup_data.get('will_serve', False)
            address = result.get('address', '')
            instructions = result.get('special_instructions', '')
            family_name = result.get('family_name', 'the family')

            if not vol_email:
                return

            # Format date nicely
            try:
                from datetime import datetime as dt
                d = dt.strptime(meal_date, '%Y-%m-%d')
                formatted_date = d.strftime('%A, %B %d, %Y')
            except Exception:
                formatted_date = meal_date

            will_serve_line = ''
            if will_serve:
                will_serve_line = '<p style="color:#558b2f;font-weight:600;margin-top:0.5rem;">You\'ve offered to help serve — the family will be so grateful.</p>'

            instructions_block = ''
            if instructions:
                instructions_block = f'<p style="font-size:0.95rem;color:#8a9a8d;font-style:italic;margin-top:0.5rem;">{html_mod.escape(instructions)}</p>'

            html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.8rem;font-weight:400;color:#3E2723;margin:0;">Thank You, {html_mod.escape(vol_name.split()[0])}</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">Your kindness means more than you know.</p>
    </div>

    <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Your Meal Signup</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(meal_type)} &middot; {html_mod.escape(formatted_date)}</p>
        {('<p style="font-size:0.95rem;color:#3E2723;margin-top:0.3rem;">Bringing: ' + html_mod.escape(meal_desc) + '</p>') if meal_desc else ''}
        {will_serve_line}
    </div>

    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Shiva Location</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(address)}</p>
        {instructions_block}
    </div>

    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">May their memory be a blessing</p>

    <div style="text-align:center;margin-top:1rem;">
        <a href="https://neshama.ca/shiva/{html_mod.escape(support_id)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View Meal Schedule</a>
    </div>

    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

            plain_text = _html_to_plain(html_content)

            if not sendgrid_key:
                logging.info(f"[Meal Signup Email] Would send confirmation to {vol_email}")
                logging.info(f" {meal_type} on {formatted_date} for {family_name}")
                return

            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(vol_email),
                subject=f'Your meal signup for {family_name} - Neshama',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )

            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Meal Signup] Confirmation email sent to {vol_email}")

            # Log to email_log for audit trail
            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, support_id, 'signup_confirmation',
                                        vol_email, vol_name,
                                        related_signup_id=result.get('signup_id'),
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Meal Signup] Failed to log email")

        except Exception:
            logging.exception("[Meal Signup] Email error")
            # Log the failure
            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, support_id, 'signup_confirmation',
                                        vol_email, vol_name,
                                        related_signup_id=result.get('signup_id'),
                                        status='failed')
                except Exception:
                    pass

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

    # ── API: V3 — Updates Feed + Thank-You Notes ──────────────

    def handle_get_updates(self, support_id):
        """Get updates for a shiva page (public)."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            result = shiva_mgr.get_updates(support_id)
            self.send_json_response(result)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_post_update(self, support_id, body):
        """Post an update or delete an update."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.get('token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
                return

            # Handle delete action
            if data.get('_action') == 'delete':
                update_id = data.get('update_id')
                if not update_id:
                    self.send_json_response({'status': 'error', 'message': 'update_id required'}, 400)
                    return
                result = shiva_mgr.delete_update(support_id, token, update_id)
                self.send_json_response(result, 200 if result['status'] == 'success' else 400)
                return

            # Post new update
            message = data.get('message', '').strip()
            if not message:
                self.send_json_response({'status': 'error', 'message': 'Message is required'}, 400)
                return

            result = shiva_mgr.post_update(support_id, token, message)
            if result['status'] == 'success' and data.get('email_volunteers'):
                # Rate limit email sends
                client_ip = self._get_client_ip()
                if not _check_rate_limit(client_ip, 'email_update'):
                    logging.warning(f"[RateLimit] Email update rate limit exceeded for {client_ip}")
                    # Still post the update, just skip the email
                else:
                    self._email_update_to_volunteers(support_id, message)

            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _email_update_to_volunteers(self, support_id, message):
        """Send organizer update via email to all volunteers."""
        try:
            if not EMAIL_AVAILABLE or not subscription_mgr or not subscription_mgr.sendgrid_api_key:
                return

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get shiva info
            cursor.execute('SELECT family_name, organizer_name FROM shiva_support WHERE id = ?', (support_id,))
            shiva = cursor.fetchone()
            if not shiva:
                conn.close()
                return
            shiva = dict(shiva)

            # Get unique volunteer emails
            cursor.execute('''
                SELECT DISTINCT volunteer_name, volunteer_email
                FROM meal_signups
                WHERE shiva_support_id = ? AND volunteer_email IS NOT NULL
            ''', (support_id,))
            volunteers = [dict(row) for row in cursor.fetchall()]
            conn.close()

            if not volunteers:
                return

            family_name = shiva.get('family_name', 'the family')
            escaped_message = html_mod.escape(message)

            for vol in volunteers:
                subject = f"Update from the {family_name} shiva"
                html_body = f"""
                <div style="font-family: Georgia, serif; max-width: 560px; margin: 0 auto; padding: 2rem; background: #fffaf5; border-radius: 12px;">
                    <h2 style="color: #3e2723; font-size: 1.2rem; margin-bottom: 1rem;">Update from the {html_mod.escape(family_name)} shiva</h2>
                    <div style="background: white; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #d4a574; margin-bottom: 1.5rem;">
                        <p style="color: #3e2723; font-size: 1rem; line-height: 1.6; margin: 0;">{escaped_message}</p>
                    </div>
                    <p style="color: #6d4c41; font-size: 0.85rem;">
                        -- {html_mod.escape(shiva.get('organizer_name', 'The organizer'))}
                    </p>
                    <hr style="border: none; border-top: 1px solid #e8d5c4; margin: 1.5rem 0;">
                    <p style="color: #9e9e9e; font-size: 0.75rem; text-align: center;">
                        Sent via <a href="https://neshama.ca" style="color: #d4a574;">Neshama</a>
                    </p>
                </div>
                """
                plain_text = _html_to_plain(html_body)
                try:
                    from sendgrid import SendGridAPIClient
                    from sendgrid.helpers.mail import Mail, From, Header
                    sg = SendGridAPIClient(subscription_mgr.sendgrid_api_key)
                    mail = Mail(
                        from_email=From('updates@neshama.ca', 'Neshama'),
                        to_emails=vol['volunteer_email'],
                        subject=subject,
                        html_content=html_body,
                        plain_text_content=plain_text
                    )
                    mail.header = Header('List-Unsubscribe', '<mailto:unsubscribe@neshama.ca>')
                    sg.send(mail)
                except Exception as email_err:
                    logging.error(f"Failed to email update to {vol['volunteer_email']}: {email_err}")
        except Exception as e:
            logging.error(f"Error emailing updates: {e}")

    def handle_send_thank_you(self, support_id, body):
        """Queue thank-you notes to all volunteers."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.get('token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
                return
            # Rate limit thank-you sends
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'send_thank_you', max_calls=2, window=600):
                self._send_rate_limit_error()
                return
            result = shiva_mgr.send_thank_you_notes(support_id, token)
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
            token = data.pop('magic_token', '') or data.pop('token', '')
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

    # ── API: V2 — Co-organizers ─────────────────────────────

    def handle_invite_co_organizer(self, support_id, body):
        """Invite a co-organizer to help manage a shiva page."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.pop('magic_token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
                return
            result = shiva_mgr.invite_co_organizer(support_id, token, data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
                # Send invite email
                self._send_co_organizer_invite_email(result)
            status_code = 200 if result['status'] == 'success' else 400
            # Don't expose token to client
            safe_result = {'status': result['status'], 'message': result.get('message', '')}
            if result.get('invite_id'):
                safe_result['invite_id'] = result['invite_id']
            self.send_json_response(safe_result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_accept_co_organizer(self):
        """Accept a co-organizer invitation via token link."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [''])[0]
        if not token:
            self._serve_access_result_page('Error', 'Invalid invitation link.')
            return
        result = shiva_mgr.accept_co_organizer_invite(token)
        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            dashboard_url = f"{base_url}/shiva/{result['shiva_id']}?token={result['token']}"
            self._serve_access_result_page(
                'Welcome, Co-Organizer!',
                f'You are now a co-organizer for the {result["family_name"]} shiva. '
                f'<a href="{dashboard_url}" style="color:#D2691E;">Go to dashboard &rarr;</a>'
            )
        elif result['status'] == 'already_accepted':
            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            dashboard_url = f"{base_url}/shiva/{result['shiva_id']}?token={result['token']}"
            self._serve_access_result_page(
                'Already Accepted',
                f'You are already a co-organizer. '
                f'<a href="{dashboard_url}" style="color:#D2691E;">Go to dashboard &rarr;</a>'
            )
        else:
            self._serve_access_result_page('Error', result.get('message', 'Something went wrong.'))

    def handle_revoke_co_organizer(self, support_id, co_id, body):
        """Revoke a co-organizer's access."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.get('magic_token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
                return
            result = shiva_mgr.revoke_co_organizer(support_id, token, co_id)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_list_co_organizers(self, support_id):
        """List co-organizers for a shiva page."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [''])[0]
        if not token:
            self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
            return
        try:
            result = shiva_mgr.list_co_organizers(support_id, token)
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_co_organizer_invite_email(self, result):
        """Send invitation email to a co-organizer."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_key:
            logging.info(f"[Co-organizer] Would send invite to {result['invitee_email']}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            accept_url = f"{base_url}/api/shiva/accept-invite?token={result['co_token']}"

            html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Co-Organizer Invitation</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(result['family_name'])} shiva</p>
    </div>
    <p style="font-size:1rem;line-height:1.6;">
        {html_mod.escape(result['organizer_name'])} has invited you to help co-organize the
        <strong>{html_mod.escape(result['family_name'])}</strong> shiva support page on Neshama.
    </p>
    <p style="font-size:0.95rem;color:#5c534a;">
        As a co-organizer you'll be able to view signups, manage the meal schedule,
        and update page details.
    </p>
    <div style="text-align:center;margin:2rem 0;">
        <a href="{html_mod.escape(accept_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.85rem 2.5rem;border-radius:2rem;text-decoration:none;font-size:1.1rem;">Accept Invitation</a>
    </div>
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(result['invitee_email'], result['invitee_name']),
                subject=f"You're invited to co-organize — {result['family_name']} shiva",
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Co-organizer] Invite sent to {result['invitee_email']}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, result['shiva_id'], 'co_organizer_invite',
                                        result['invitee_email'], result['invitee_name'],
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Co-organizer] Failed to log email")
        except Exception:
            logging.exception("[Co-organizer] Invite email error")

    # ── API: V2 — Multi-date signup ──────────────────────────

    def handle_meal_signup_multi(self, support_id, body):
        """Handle multi-date meal signup (V2)."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Shiva support not available'}, 503)
            return
        try:
            data = json.loads(body)
            data['shiva_support_id'] = support_id
            result = shiva_mgr.signup_meals_multi(data)
            if result['status'] == 'success':
                shiva_mgr.track_event('meal_signup_multi', support_id)
                shiva_mgr._trigger_backup()
                # Send grouped confirmation email
                self._send_multi_signup_confirmation(data, result, support_id)
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_multi_signup_confirmation(self, data, result, support_id):
        """Send grouped confirmation email for multi-date signup."""
        try:
            sendgrid_key = os.environ.get('SENDGRID_API_KEY')
            vol_email = data.get('volunteer_email', '').strip()
            vol_name = data.get('volunteer_name', 'Friend')
            family_name = result.get('family_name', 'the family')
            address = result.get('address', '')

            if not vol_email:
                return

            # Build date list
            signups = result.get('signups', [])
            meal_type = data.get('meal_type', 'Meal')
            date_items = ''
            for s in signups:
                try:
                    d = datetime.strptime(s['date'], '%Y-%m-%d')
                    formatted = d.strftime('%A, %B %d')
                except Exception:
                    formatted = s['date']
                date_items += f'<li style="margin:0.3rem 0;">{html_mod.escape(meal_type)} &middot; {formatted}</li>'

            html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.8rem;font-weight:400;color:#3E2723;margin:0;">Thank You, {html_mod.escape(vol_name.split()[0])}</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">You signed up for {len(signups)} meals!</p>
    </div>
    <div style="background:#f1f8e9;border:2px solid #a5d6a7;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">Your Meal Signups</p>
        <ul style="padding-left:1.5rem;margin:0;list-style:none;">{date_items}</ul>
    </div>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Shiva Location</p>
        <p style="font-size:1.1rem;font-weight:600;margin:0;">{html_mod.escape(address)}</p>
    </div>
    <p style="text-align:center;font-size:0.95rem;color:#8a9a8d;font-style:italic;margin:1.5rem 0;">May their memory be a blessing</p>
    <div style="text-align:center;margin-top:1rem;">
        <a href="https://neshama.ca/shiva/{html_mod.escape(support_id)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View Meal Schedule</a>
    </div>
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

            plain_text = _html_to_plain(html_content)

            if not sendgrid_key:
                logging.info(f"[Multi Signup] Would send confirmation to {vol_email} for {len(signups)} meals")
                return

            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(vol_email),
                subject=f'Your {len(signups)} meal signups for {family_name} — Neshama',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Multi Signup] Confirmation sent to {vol_email}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, support_id, 'signup_confirmation',
                                        vol_email, vol_name,
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Multi Signup] Failed to log email")
        except Exception:
            logging.exception("[Multi Signup] Email error")

    # ── API: V2 — Email Verification ─────────────────────────

    def handle_verify_email(self):
        """Handle organizer email verification via token link."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [''])[0]
        if not token:
            self._serve_access_result_page('Error', 'Invalid verification link.')
            return
        result = shiva_mgr.verify_email(token)
        if result['status'] == 'success':
            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            dashboard_url = f"{base_url}/shiva/{result['shiva_id']}?token={result['magic_token']}"
            self._serve_access_result_page(
                'Email Verified!',
                f'Your email has been verified for the {result["family_name"]} shiva page. '
                f'<a href="{dashboard_url}" style="color:#D2691E;">Go to your dashboard &rarr;</a>'
            )
        elif result['status'] == 'already_verified':
            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            dashboard_url = f"{base_url}/shiva/{result['shiva_id']}?token={result['magic_token']}"
            self._serve_access_result_page(
                'Already Verified',
                f'Your email is already verified. '
                f'<a href="{dashboard_url}" style="color:#D2691E;">Go to your dashboard &rarr;</a>'
            )
        else:
            self._serve_access_result_page('Error', result.get('message', 'Something went wrong.'))

    # ── API: Shiva Access Requests ────────────────────────────

    def handle_access_request(self, body):
        """Handle access request for a private shiva page"""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            result = shiva_mgr.create_access_request(data)

            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
                # Send email to organizer
                self._send_access_request_email(result)

            status_code = 200 if result['status'] in ('success', 'already_approved') else 400
            # Don't expose organizer_email/key to client
            safe_result = {
                'status': result['status'],
                'message': result.get('message', '')
            }
            if result['status'] == 'already_approved':
                safe_result['access_token'] = result['access_token']
            self.send_json_response(safe_result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_access_approve(self):
        """Approve an access request via organizer email link"""
        if not SHIVA_AVAILABLE:
            self.send_error_response('Not available', 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        request_id = query_params.get('request_id', [''])[0]
        organizer_key = query_params.get('organizer_key', [''])[0]

        if not request_id or not organizer_key:
            self._serve_access_result_page('Error', 'Invalid approval link.')
            return

        result = shiva_mgr.approve_access_request(request_id, organizer_key)

        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
            # Send approval email to requester
            self._send_access_approved_email(result)
            self._serve_access_result_page(
                'Access Granted',
                f'{result["requester_name"]} can now view the full {result["family_name"]} shiva page.'
            )
        else:
            self._serve_access_result_page('Error', result.get('message', 'Something went wrong.'))

    def handle_access_deny(self):
        """Deny an access request via organizer email link"""
        if not SHIVA_AVAILABLE:
            self.send_error_response('Not available', 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        request_id = query_params.get('request_id', [''])[0]
        organizer_key = query_params.get('organizer_key', [''])[0]

        if not request_id or not organizer_key:
            self._serve_access_result_page('Error', 'Invalid link.')
            return

        result = shiva_mgr.deny_access_request(request_id, organizer_key)

        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
            # Send denial email to requester
            self._send_access_denied_email(result)
            self._serve_access_result_page(
                'Request Declined',
                f'The request from {result["requester_name"]} has been declined.'
            )
        else:
            self._serve_access_result_page('Error', result.get('message', 'Something went wrong.'))

    def _serve_access_result_page(self, title, message):
        """Serve a simple result page for approve/deny actions"""
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Neshama</title>
    <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@300;400;600&family=Cormorant+Garamond:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Crimson Pro', serif; background: linear-gradient(135deg, #FAF9F6 0%, #F5F5DC 100%); color: #3E2723; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem; }}
        .container {{ max-width: 500px; background: white; border-radius: 1.5rem; padding: 3rem; box-shadow: 0 10px 40px rgba(62,39,35,0.08); text-align: center; }}
        h1 {{ font-family: 'Cormorant Garamond', serif; font-size: 2rem; font-weight: 400; margin-bottom: 1rem; }}
        p {{ font-size: 1.1rem; line-height: 1.6; margin-bottom: 1.5rem; }}
        .btn {{ display: inline-block; background: #D2691E; color: white; padding: 0.75rem 2rem; border-radius: 2rem; text-decoration: none; font-family: 'Crimson Pro', serif; font-size: 1.1rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p>{message}</p>
        <a href="/" class="btn">Return to Neshama</a>
    </div>
</body>
</html>"""
        content = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_access_request_email(self, result):
        """Send email to organizer about new access request"""
        if not EMAIL_AVAILABLE or not subscription_mgr.sendgrid_api_key:
            logging.info(f"[Access] Would email {result['organizer_email']}: access request from {result['requester_name']}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            approve_url = f"{base_url}/api/shiva-access/approve?request_id={result['request_id']}&organizer_key={result['organizer_key']}"
            deny_url = f"{base_url}/api/shiva-access/deny?request_id={result['request_id']}&organizer_key={result['organizer_key']}"

            msg_line = ''
            if result.get('requester_message'):
                msg_line = f'<p style="background:#FAF9F6;padding:1rem;border-radius:0.5rem;border-left:3px solid #D2691E;margin:1rem 0;">They wrote: "{result["requester_message"]}"</p>'

            html = f"""
            <div style="font-family:Georgia,serif;max-width:500px;margin:0 auto;color:#3E2723;">
                <h2 style="color:#D2691E;font-size:1.5rem;">Shiva Access Request</h2>
                <p><strong>{result['requester_name']}</strong> ({result['requester_email']}) is requesting access to the <strong>{result['family_name']}</strong> shiva page.</p>
                {msg_line}
                <div style="margin:2rem 0;">
                    <a href="{approve_url}" style="display:inline-block;background:#4CAF50;color:white;padding:0.75rem 2rem;border-radius:2rem;text-decoration:none;margin-right:1rem;font-size:1rem;">Approve</a>
                    <a href="{deny_url}" style="display:inline-block;background:#f44336;color:white;padding:0.75rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">Deny</a>
                </div>
                <p style="font-size:0.85rem;color:#B2BEB5;">You are receiving this because you organized the {result['family_name']} shiva page on Neshama.</p>
            </div>"""

            plain_text = _html_to_plain(html)
            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(result['organizer_email']),
                subject=f"Shiva access request from {result['requester_name']}",
                plain_text_content=Content("text/plain", plain_text),
                html_content=Content("text/html", html)
            )
            sg = SendGridAPIClient(subscription_mgr.sendgrid_api_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Access] Sent request email to organizer: {result['organizer_email']}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    shiva_id = result.get('shiva_id') or result.get('request_id', '')
                    log_immediate_email(DB_PATH, shiva_id, 'access_request',
                                        result['organizer_email'], None,
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Access] Failed to log email")
        except Exception as e:
            logging.error(f"[Access] Failed to send request email: {e}")

    def _send_access_approved_email(self, result):
        """Send approval email to requester with access link"""
        if not EMAIL_AVAILABLE or not subscription_mgr.sendgrid_api_key:
            logging.info(f"[Access] Would email {result['requester_email']}: approved for {result['family_name']}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            access_url = f"{base_url}/shiva/{result['shiva_id']}?access={result['access_token']}"

            html = f"""
            <div style="font-family:Georgia,serif;max-width:500px;margin:0 auto;color:#3E2723;">
                <h2 style="color:#D2691E;font-size:1.5rem;">You've Been Approved</h2>
                <p>The organizer of the <strong>{result['family_name']}</strong> shiva has approved your request.</p>
                <p>You can now view the full shiva details including address, dietary information, and sign up to bring a meal.</p>
                <div style="margin:2rem 0;text-align:center;">
                    <a href="{access_url}" style="display:inline-block;background:#D2691E;color:white;padding:0.85rem 2.5rem;border-radius:2rem;text-decoration:none;font-size:1.1rem;">View Shiva Details</a>
                </div>
                <p style="font-size:0.9rem;color:#B2BEB5;">Bookmark this link to access the page again later.</p>
            </div>"""

            plain_text = _html_to_plain(html)
            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(result['requester_email']),
                subject=f"You've been approved \u2014 {result['family_name']} shiva details",
                plain_text_content=Content("text/plain", plain_text),
                html_content=Content("text/html", html)
            )
            sg = SendGridAPIClient(subscription_mgr.sendgrid_api_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Access] Sent approval email to: {result['requester_email']}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, result.get('shiva_id', ''), 'access_approved',
                                        result['requester_email'], result.get('requester_name'),
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Access] Failed to log email")
        except Exception as e:
            logging.error(f"[Access] Failed to send approval email: {e}")

    def _send_access_denied_email(self, result):
        """Send denial email to requester"""
        if not EMAIL_AVAILABLE or not subscription_mgr.sendgrid_api_key:
            logging.info(f"[Access] Would email {result['requester_email']}: denied for {result['family_name']}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            html = f"""
            <div style="font-family:Georgia,serif;max-width:500px;margin:0 auto;color:#3E2723;">
                <h2 style="color:#D2691E;font-size:1.5rem;">Shiva Access Update</h2>
                <p>The organizer of the <strong>{result['family_name']}</strong> shiva has chosen to manage meal coordination privately.</p>
                <p>Thank you for your thoughtfulness. Your care and compassion mean a great deal to the family during this difficult time.</p>
                <p style="font-size:0.9rem;color:#B2BEB5;margin-top:2rem;">Neshama \u2014 Every soul remembered</p>
            </div>"""

            plain_text = _html_to_plain(html)
            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(result['requester_email']),
                subject='Shiva access update',
                plain_text_content=Content("text/plain", plain_text),
                html_content=Content("text/html", html)
            )
            sg = SendGridAPIClient(subscription_mgr.sendgrid_api_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Access] Sent denial email to: {result['requester_email']}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, result.get('shiva_id', ''), 'access_denied',
                                        result['requester_email'], result.get('requester_name'),
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Access] Failed to log email")
        except Exception as e:
            logging.error(f"[Access] Failed to send denial email: {e}")

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
        """Send error response with friendly message for 500s"""
        if status >= 500:
            logging.error(f"[API] Server error: {message}")
            friendly = self._friendly_error(message)
        else:
            friendly = str(message)
        self.send_json_response({
            'status': 'error',
            'error': {'message': friendly}
        }, status)

    def send_404(self):
        """Send 404 response"""
        self.send_error_response('Endpoint not found', 404)

    def _log_request(self, method, path, status, start_time):
        """Log request with method, path, status code, and response time."""
        elapsed_ms = (_time_module.time() - start_time) * 1000
        logging.info(f"[API] {method} {path} {status} {elapsed_ms:.0f}ms")

    def _handle_health_check(self):
        """GET /api/health — returns service status with counts."""
        try:
            db_path = self.get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            obit_count = 0
            vendor_count = 0
            try:
                cursor.execute('SELECT COUNT(*) FROM obituaries')
                obit_count = cursor.fetchone()[0]
            except Exception:
                pass
            try:
                cursor.execute('SELECT COUNT(*) FROM vendors')
                vendor_count = cursor.fetchone()[0]
            except Exception:
                pass
            conn.close()
            self.send_json_response({
                'status': 'ok',
                'obituaries': obit_count,
                'vendors': vendor_count
            })
        except Exception:
            self.send_json_response({'status': 'ok', 'obituaries': 0, 'vendors': 0})

    def _get_client_ip(self):
        """Get client IP from headers or socket."""
        forwarded = self.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return self.client_address[0] if self.client_address else '0.0.0.0'

    def _send_rate_limit_error(self):
        """Send a 429 Too Many Requests response."""
        self.send_json_response({
            'status': 'error',
            'message': 'Too many requests. Please wait a few minutes before trying again.'
        }, 429)

    def _friendly_error(self, raw_message):
        """Convert technical error messages to user-friendly text."""
        msg = str(raw_message)
        # Hide SQL / Python internals from users
        if 'sqlite3' in msg.lower() or 'operationalerror' in msg.lower():
            return 'A database error occurred. Please try again later.'
        if 'no such table' in msg.lower():
            return 'Service is initializing. Please try again in a moment.'
        if 'database is locked' in msg.lower():
            return 'The server is busy. Please try again in a moment.'
        if 'filenotfounderror' in msg.lower() or 'database file not found' in msg.lower():
            return 'Service temporarily unavailable. Please try again later.'
        # Keep it short for other errors
        if len(msg) > 200:
            return 'An unexpected error occurred. Please try again later.'
        return msg

    def log_message(self, format, *args):
        """Custom logging"""
        logging.info(f"[API] {format % args}")

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
                    logging.info(f"[Startup] Database has {count} obituaries, skipping auto-scrape")
            except Exception:
                pass

        if needs_scrape:
            logging.info("[Startup] Database empty - running auto-scrape in background...")
            result = subprocess.run(
                ['python', 'master_scraper.py'],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=300
            )
            if result.returncode == 0:
                logging.info("[Startup] Auto-scrape completed successfully")
            else:
                logging.info(f"[Startup] Auto-scrape had issues: {result.stderr[:200]}")
    except Exception as e:
        logging.error(f"[Startup] Auto-scrape error (non-fatal): {e}")


def is_shabbat():
    """Check if current time is during Shabbat (Friday 6 PM – Saturday 9 PM Toronto time).
    Uses conservative window that covers candle lighting through havdalah year-round."""
    tz = pytz.timezone('America/Toronto')
    now = datetime.now(tz)
    # Friday = 4 (weekday()), Saturday = 5
    if now.weekday() == 4 and now.hour >= 18:
        return True
    if now.weekday() == 5 and now.hour < 21:
        return True
    return False


def periodic_scraper():
    """Run scrapers every SCRAPE_INTERVAL seconds in background thread.
    Keeps obituary data fresh between server restarts.
    Pauses during Shabbat (Friday evening – Saturday night)."""
    import time as _time
    project_root = os.path.join(FRONTEND_DIR, '..')
    while True:
        _time.sleep(SCRAPE_INTERVAL)
        if is_shabbat():
            logging.info(f"[Scraper] Shabbat — scraping paused")
            continue
        try:
            logging.info(f"[Scraper] Periodic scrape starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            result = subprocess.run(
                ['python', 'master_scraper.py'],
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=300
            )
            if result.returncode == 0:
                logging.info(f"[Scraper] Periodic scrape completed successfully")
            else:
                logging.info(f"[Scraper] Scrape had issues: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            logging.info("[Scraper] Periodic scrape timed out after 300s (non-fatal)")
        except Exception as e:
            logging.error(f"[Scraper] Periodic scrape error (non-fatal): {e}")


def run_server(port=None):
    """Start the API server"""
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, NeshamaAPIHandler)

    # Launch auto-scrape in background thread (non-blocking)
    scrape_thread = threading.Thread(target=auto_scrape_on_startup, daemon=True)
    scrape_thread.start()

    # Launch periodic scraper (every 20 min by default)
    periodic_thread = threading.Thread(target=periodic_scraper, daemon=True)
    periodic_thread.start()
    logging.info(f"[Scraper] Periodic scraper started (every {SCRAPE_INTERVAL // 60} minutes)")

    # Launch email queue processor via APScheduler (every 15 min)
    if EMAIL_QUEUE_AVAILABLE:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler = BackgroundScheduler(daemon=True)
            scheduler.add_job(
                process_email_queue,
                'interval',
                minutes=15,
                args=[DB_PATH],
                id='email_queue',
                name='Process shiva email queue',
                max_instances=1,
            )
            scheduler.start()
            logging.info(f"[EmailQueue] Scheduler started (every 15 minutes)")
        except Exception as e:
            logging.error(f"[EmailQueue] Scheduler failed to start: {e}")
            logging.info(f" Install with: pip install apscheduler")

    logging.info(f"\n{'='*60}")
    logging.info(f" NESHAMA API SERVER v2.0")
    logging.info(f"{'='*60}")
    logging.info(f"\n Running on: http://0.0.0.0:{port}")
    logging.info(f"\n Pages:")
    logging.info(f" / - Landing page")
    logging.info(f" /feed - Obituary feed")
    logging.info(f" /memorial/{{id}} - Memorial page")
    logging.info(f" /about - About")
    logging.info(f" /faq - FAQ")
    logging.info(f" /privacy - Privacy Policy")
    logging.info(f" /confirm/{{token}} - Email confirmation")
    logging.info(f" /unsubscribe/{{token}} - Unsubscribe")
    logging.info(f" /manage-subscription - Stripe customer portal")
    logging.info(f" /premium-success - Payment success")
    logging.info(f" /premium-cancelled - Payment cancelled")
    logging.info(f" /shiva/organize - Set up shiva support")
    logging.info(f" /shiva/{{id}} - Community support page")
    logging.info(f"\n API Endpoints:")
    logging.info(f" GET /api/obituaries - All obituaries")
    logging.info(f" GET /api/obituary/{{id}} - Single obituary")
    logging.info(f" GET /api/search?q=name - Search")
    logging.info(f" GET /api/status - Database stats")
    logging.info(f" GET /api/scraper-status - Scraper freshness info")
    logging.info(f" GET /api/community-stats - Community statistics")
    logging.info(f" GET /api/tributes/{{id}} - Tributes for obituary")
    logging.info(f" GET /api/tributes/counts - All tribute counts")
    logging.info(f" GET /api/subscribers/count - Subscriber count")
    logging.info(f" POST /api/subscribe - Email subscription")
    logging.info(f" POST /api/tributes - Submit tribute")
    logging.info(f" POST /api/unsubscribe-feedback - Unsubscribe feedback")
    logging.info(f" POST /api/create-checkout - Stripe checkout")
    logging.info(f" POST /webhook - Stripe webhook")
    logging.info(f" GET /api/shiva/obituary/{{id}} - Check shiva support")
    logging.info(f" GET /api/shiva/{{id}} - Shiva support details")
    logging.info(f" GET /api/shiva/{{id}}/meals - Meal signups")
    logging.info(f" POST /api/shiva - Create shiva support")
    logging.info(f" POST /api/shiva/{{id}}/signup - Volunteer meal signup")
    logging.info(f" POST /api/shiva/{{id}}/report - Report shiva page")
    logging.info(f" POST /api/shiva/{{id}}/remove-signup - Remove signup (organizer)")
    logging.info(f" PUT /api/shiva/{{id}} - Update shiva support")
    logging.info(f" GET /api/caterers - Approved caterers")
    logging.info(f" POST /api/caterers/apply - Caterer application")
    logging.info(f" GET /api/caterers/pending - Pending applications (admin)")
    logging.info(f" POST /api/caterers/{{id}}/approve - Approve caterer (admin)")
    logging.info(f" POST /api/caterers/{{id}}/reject - Reject caterer (admin)")
    logging.info(f" GET /api/vendors - All vendors")
    logging.info(f" GET /api/vendors/{{slug}} - Vendor by slug")
    logging.info(f" POST /api/vendor-leads - Vendor inquiry")
    logging.info(f" GET /directory/{{slug}} - Vendor detail page")
    logging.info(f" GET /admin/backup - Download backup JSON (admin)")
    logging.info(f" POST /admin/restore - Upload backup JSON (admin)")
    logging.info(f"\n Email: {'SendGrid connected' if EMAIL_AVAILABLE and subscription_mgr.sendgrid_api_key else 'TEST MODE' if EMAIL_AVAILABLE else 'Not available'}")
    logging.info(f" Stripe: {'Connected' if STRIPE_AVAILABLE else 'Not configured (set STRIPE_SECRET_KEY)'}")
    logging.info(f" Shiva support: {'Available' if SHIVA_AVAILABLE else 'Not available'}")

    # Archive expired shiva support pages + seed caterer data
    if SHIVA_AVAILABLE:
        try:
            shiva_mgr.archive_expired()
        except Exception as e:
            logging.info(f" Shiva archive check: {e}")
        # Seed pre-approved caterers for shiva directory
        seed_caterers = [
            {
                'business_name': 'Jem Salads',
                'contact_name': 'Jem Salads Team',
                'email': 'info@jemsalads.com',
                'phone': '(416) 785-6161',
                'website': 'https://www.jemsalads.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'certified_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$',
                'shiva_menu_description': 'Fresh, wholesome platters and prepared meals with generous portions. Extensive experience catering shiva meals with flexible delivery timing. Platters and hot meals available, feeds 10\u201350+.',
            },
            {
                'business_name': 'TOBEN Food by Design',
                'contact_name': 'TOBEN Team',
                'email': 'info@tobenfoodbydesign.com',
                'phone': '(647) 344-8323',
                'website': 'https://www.tobenfoodbydesign.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$$',
                'shiva_menu_description': 'Full-service caterer with 15+ years experience catering shiva and celebrations of life. Comforting, customized menus with kosher-style, gluten-free, and vegan options. Dedicated event manager works with each family.',
            },
            {
                'business_name': 'The Food Dudes',
                'contact_name': 'Food Dudes Team',
                'email': 'info@thefooddudes.com',
                'phone': '(647) 340-3833',
                'website': 'https://thefooddudes.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$$',
                'shiva_menu_description': 'Chef-driven catering with seasonal, scratch-made menus. Known for high-quality comfort food and accommodating dietary restrictions. A reliable choice for families wanting something beyond traditional deli.',
            },
            {
                'business_name': 'Pusateri\u2019s Fine Foods',
                'contact_name': 'Pusateri\u2019s Catering',
                'email': 'catering@pusateris.com',
                'phone': '(416) 785-9100',
                'website': 'https://www.pusateris.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$$$',
                'shiva_menu_description': 'Toronto\u2019s premier grocer and caterer. Beautifully prepared platters, entrees, and desserts with high-quality ingredients. Full-service catering including event coordination. Ideal for upscale shiva meals.',
            },
            {
                'business_name': 'Nortown Foods',
                'contact_name': 'Nortown Catering',
                'email': 'info@nortownfoods.com',
                'phone': '(416) 789-2921',
                'website': 'https://www.nortownfoods.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$$',
                'shiva_menu_description': 'Premium grocer with full catering services, butcher shop, and prepared foods counter. Hot meals, salads, deli platters, and baked goods. Over 50 years serving the Toronto Jewish community. A one-stop shop for shiva meals.',
            },
            {
                'business_name': 'Pickle Barrel Catering',
                'contact_name': 'Pickle Barrel Catering',
                'email': 'catering@picklebarrel.com',
                'phone': '(905) 479-2070',
                'website': 'https://picklebarrelcatering.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'Extensive catering menu with sandwich platters, salads, hot entrees, and dessert trays. Reliable for feeding groups of 10 to 200+. Online ordering and flexible scheduling make last-minute shiva meals easy.',
            },
            {
                'business_name': 'Centre Street Deli',
                'contact_name': 'Centre Street Deli Team',
                'email': 'info@centrestreetdeli.com',
                'phone': '(905) 731-8037',
                'website': 'https://www.centrestreetdeli.com',
                'delivery_area': 'Thornhill & GTA',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$',
                'shiva_menu_description': 'Classic Thornhill Jewish deli since 1988. Montreal-style smoked meat, corned beef, matzo ball soup, and deli platters. Catering trays are a community staple for shiva meals.',
            },
            {
                'business_name': 'United Bakers Dairy Restaurant',
                'contact_name': 'United Bakers Team',
                'email': 'info@unitedbakers.ca',
                'phone': '(416) 789-0519',
                'website': 'https://www.unitedbakers.ca',
                'delivery_area': 'Toronto',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'Iconic Toronto dairy restaurant since 1912. Famous for blintzes, pierogies, and homestyle Jewish comfort food. Dairy/vegetarian focus makes it ideal for shiva meals in kosher homes where meat separation matters.',
            },
            {
                'business_name': 'Encore Catering',
                'contact_name': 'Encore Team',
                'email': 'info@encorecatering.com',
                'phone': '(416) 661-4460',
                'website': 'https://encorecatering.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'kosher_style',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'Family-owned caterer since 1979 with a dedicated shiva meals program. Online ordering, delivery to the shiva home Mon\u2013Sat. Over 40 years of experience serving the community with comforting, reliable meals.',
            },
            {
                'business_name': 'Mitzuyan Kosher Catering',
                'contact_name': 'Mitzuyan Team',
                'email': 'info@mitzuyankoshercatering.com',
                'phone': '(416) 419-5260',
                'website': 'https://mitzuyankoshercatering.com',
                'delivery_area': 'Toronto, Thornhill & GTA',
                'kosher_level': 'certified_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$$',
                'shiva_menu_description': 'COR-certified kosher caterer since 2004. Modern kosher menus for shiva, with mobile catering to any location. Specializes in comforting, beautifully presented meals for mourning families.',
            },
            {
                'business_name': 'Ely\u2019s Fine Foods',
                'contact_name': 'Ely\u2019s Team',
                'email': 'info@elysfinefoods.com',
                'phone': '(416) 782-3231',
                'website': 'https://elysfinefoods.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'certified_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$$',
                'shiva_menu_description': 'COR-certified kosher catering and takeout with 25+ years serving the Toronto Jewish community. Dedicated shiva meal packages delivered to the home. Salads, soups, chicken, beef, and fish dishes.',
            },
            {
                'business_name': 'Grodzinski Bakery',
                'contact_name': 'Grodzinski Team',
                'email': 'info@grodzinskibakery.com',
                'phone': '(416) 789-0785',
                'website': 'https://www.grodzinskibakery.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'certified_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'COR-certified kosher, nut-free bakery. Challah, cakes, sandwich platters, breakfast platters, and dessert trays. Toronto and Thornhill locations. A staple for shiva baked goods and morning platters.',
            },
            {
                'business_name': 'Marron Bistro',
                'contact_name': 'Marron Bistro Team',
                'email': 'info@marronbistro.com',
                'phone': '(416) 784-0128',
                'website': 'https://www.marronbistro.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'certified_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$$$',
                'shiva_menu_description': 'COR-certified kosher fine dining in Forest Hill. Elegant catering for shiva and private events. An upscale kosher option for families wanting a refined, comforting meal.',
            },
            {
                'business_name': 'Daniel et Daniel',
                'contact_name': 'Daniel et Daniel Team',
                'email': 'info@danieletdaniel.ca',
                'phone': '(416) 968-9275',
                'website': 'https://www.danieletdaniel.ca',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$$$',
                'shiva_menu_description': 'Premium full-service caterer since 1980. Custom seasonal menus with dietary accommodation. Experienced, elegant catering for families wanting something beyond traditional deli. Full event coordination available.',
            },
            {
                'business_name': 'Longo\u2019s',
                'contact_name': 'Longo\u2019s Catering',
                'email': 'catering@longos.com',
                'phone': '(416) 385-3113',
                'website': 'https://www.longos.com/catering',
                'delivery_area': 'GTA (multiple locations)',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'Italian grocery chain with extensive catering. Pasta trays, antipasti, cheese boards, salad platters, and desserts. Affordable and reliable for feeding groups. 48-hour advance ordering.',
            },
            {
                'business_name': 'Summerhill Market',
                'contact_name': 'Summerhill Catering',
                'email': 'catering@summerhillmarket.com',
                'phone': '(416) 921-2714',
                'website': 'https://www.summerhillmarket.com',
                'delivery_area': 'Toronto',
                'kosher_level': 'not_kosher',
                'has_delivery': False,
                'has_online_ordering': False,
                'price_range': '$$$',
                'shiva_menu_description': 'Premium Toronto grocer and caterer. Beautifully prepared platters, entrees, and desserts with high-quality ingredients. Known for elegant presentation. Pickup from Summerhill or Mt. Pleasant locations.',
            },
            {
                'business_name': 'Cumbrae\u2019s',
                'contact_name': 'Cumbrae\u2019s Team',
                'email': 'info@cumbraes.com',
                'phone': '(416) 485-5620',
                'website': 'https://cumbraes.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$$$',
                'shiva_menu_description': 'Premium butcher offering ethically raised meats and prepared comfort foods \u2014 lasagna, shepherd\u2019s pie, mac and cheese, and ready-to-heat entrees. A thoughtful option for families who want high-quality comfort food delivered.',
            },
            {
                'business_name': 'iQ Food Co',
                'contact_name': 'iQ Catering Team',
                'email': 'catering@iqfoodco.com',
                'phone': '(647) 340-6892',
                'website': 'https://www.iq-catering.com',
                'delivery_area': 'Toronto',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': True,
                'price_range': '$$',
                'shiva_menu_description': 'Seasonal, scratch-made healthy meals. Plant-forward menu with dairy, poultry, and fish options. Accommodates gluten-free, dairy-free, and vegan needs. A lighter, health-conscious option alongside traditional comfort food.',
            },
        ]
        for caterer in seed_caterers:
            try:
                shiva_mgr.seed_caterer(caterer)
            except Exception as e:
                logging.info(f" Caterer seed ({caterer['business_name']}): {e}")
    # Seed vendor directory
    if VENDORS_AVAILABLE:
        try:
            seed_vendors(DB_PATH)
            backfill_vendor_emails(DB_PATH)
            logging.info(f" Vendor directory: Seeded")
        except Exception as e:
            logging.info(f" Vendor seed: {e}")

    if SHIVA_AVAILABLE:
        # Auto-restore from backup if critical tables are empty
        try:
            if shiva_mgr.needs_restore():
                logging.info("[Startup] Critical tables empty — restoring from backup.json...")
                shiva_mgr.restore_from_file()
            else:
                logging.info(" Backup restore: not needed")
        except Exception as e:
            logging.info(f" Backup restore: {e}")
    logging.info(f"\n Press Ctrl+C to stop")
    logging.info(f"{'='*60}\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("\n\n Server stopped")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
