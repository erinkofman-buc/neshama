#!/usr/bin/env python3
"""
Neshama API Server v1.4
Serves frontend, API endpoints, email subscriptions (SendGrid double opt-in), and payment integration
Auto-scrapes on startup to handle Render free tier ephemeral storage
"""

from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
import html as html_mod
import json
import sqlite3
import os
import re
import sys
import subprocess
import threading
from urllib.parse import urlparse, parse_qs, unquote
import urllib.request
from datetime import datetime, timedelta, timezone as _tz
import pytz
import logging

import signal
import time as _time_module
import hmac
import hashlib
from email.utils import formatdate as _format_http_date

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
if FRONTEND_DIR not in sys.path:
    sys.path.insert(0, FRONTEND_DIR)
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(FRONTEND_DIR, '..', 'neshama.db'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 1200))  # 20 minutes default
_SERVER_START_TIME = datetime.now(tz=_tz.utc)

# ── Early Lock Recovery ─────────────────────────────────
# MUST run before any module-level DB connections (managers, etc.)
# Remove ALL lock/journal files so the DB opens clean.
if os.path.exists(DB_PATH):
    for _suffix in ['-wal', '-shm', '-journal']:
        _lock_file = DB_PATH + _suffix
        if os.path.exists(_lock_file):
            try:
                os.remove(_lock_file)
                logging.info(f"[EarlyRecovery] Removed {_suffix}")
            except Exception as _e:
                logging.warning(f"[EarlyRecovery] Could not remove {_suffix}: {_e}")
    # Open and immediately close to verify DB is accessible
    try:
        _rc = sqlite3.connect(DB_PATH, timeout=5, isolation_level=None)
        _rc.execute('PRAGMA journal_mode=DELETE')
        _rc.execute('PRAGMA busy_timeout=30000')
        _rc.close()
        del _rc
        logging.info("[EarlyRecovery] DB opened clean in DELETE mode")
    except Exception as _e:
        logging.warning(f"[EarlyRecovery] {_e}")


def ensure_wal_mode(db_path=None):
    """Force WAL journal mode on startup to prevent database locking under concurrent access.
    Must be called AFTER lock recovery and BEFORE the server accepts requests."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=30)
    current = conn.execute('PRAGMA journal_mode').fetchone()[0]
    if current.lower() != 'wal':
        result = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        logging.info(f"[Startup] SQLite journal mode changed from {current} to {result}")
    else:
        logging.info("[Startup] SQLite journal mode already WAL")
    conn.close()


def _connect_db(db_path=None):
    """Create a SQLite connection with busy timeout and autocommit.
    Autocommit prevents Python's implicit transactions from holding write locks."""
    conn = sqlite3.connect(db_path or DB_PATH, timeout=30, isolation_level=None)
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

# ── Rate Limiter ─────────────────────────────────────────
# Simple in-memory rate limiter for email-sending endpoints.
# Keyed by (client_ip, endpoint). Allows max N calls per window.
_rate_limit_store = {}  # key -> list of timestamps
_RATE_LIMIT_WINDOW = 300   # 5 minutes
_RATE_LIMIT_MAX_CALLS = 3  # max 3 email-sends per 5 min per IP
_rate_limit_last_cleanup = 0  # epoch time of last full cleanup
_RATE_LIMIT_CLEANUP_INTERVAL = 600  # full cleanup every 10 minutes


def _check_rate_limit(client_ip, endpoint, max_calls=_RATE_LIMIT_MAX_CALLS, window=_RATE_LIMIT_WINDOW):
    """Return True if the request is within rate limits, False if exceeded."""
    global _rate_limit_last_cleanup
    key = (client_ip, endpoint)
    now = _time_module.time()

    # Periodic full cleanup to prevent unbounded growth
    if now - _rate_limit_last_cleanup > _RATE_LIMIT_CLEANUP_INTERVAL:
        _rate_limit_last_cleanup = now
        stale_keys = [k for k, ts in _rate_limit_store.items()
                      if not ts or now - max(ts) > _RATE_LIMIT_WINDOW]
        for k in stale_keys:
            del _rate_limit_store[k]

    timestamps = _rate_limit_store.get(key, [])
    # Prune old entries for this key
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

# Periodic scraper thread health
_last_digest_run = {
    'ran_at': None,
    'result': None,
    'error': None,
}

_periodic_scraper_status = {
    'alive': False,
    'last_heartbeat': None,
    'cycle_count': 0,
    'consecutive_failures': 0,
    'last_stdout': None,
    'last_stderr': None,
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

# Optional Yahrzeit Reminder import
try:
    from yahrzeit_manager import YahrzeitManager
    yahrzeit_mgr = YahrzeitManager(db_path=DB_PATH)
    YAHRZEIT_AVAILABLE = True
    logging.info(f" Yahrzeit reminders: Available")
except Exception as e:
    YAHRZEIT_AVAILABLE = False
    yahrzeit_mgr = None
    logging.info(f" Yahrzeit reminders: Not available ({e})")

# Email queue processor (v2)
try:
    from email_queue import process_email_queue, log_immediate_email
    EMAIL_QUEUE_AVAILABLE = True
    logging.info(f" Email queue: Available")
except Exception as e:
    EMAIL_QUEUE_AVAILABLE = False
    logging.info(f" Email queue: Not available ({e})")

class NeshamaAPIHandler(BaseHTTPRequestHandler):

    def end_headers(self):
        """Override to inject security headers on ALL responses."""
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

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
        '/terms': ('terms.html', 'text/html'),
        '/terms.html': ('terms.html', 'text/html'),
        '/premium-modal': ('premium_modal.html', 'text/html'),
        '/premium_modal.html': ('premium_modal.html', 'text/html'),
        '/premium-success': ('premium_success.html', 'text/html'),
        '/premium_success.html': ('premium_success.html', 'text/html'),
        '/premium-cancelled': ('premium_cancelled.html', 'text/html'),
        '/premium_cancelled.html': ('premium_cancelled.html', 'text/html'),
        '/email_popup.html': ('email_popup.html', 'text/html'),
        '/premium': ('premium.html', 'text/html'),
        '/premium.html': ('premium.html', 'text/html'),
        '/sustain': ('premium.html', 'text/html'),
        '/sustain-success': ('premium_success.html', 'text/html'),
        '/sustain-cancelled': ('premium_cancelled.html', 'text/html'),
        '/favicon.svg': ('favicon.svg', 'image/svg+xml'),
        '/manifest.json': ('manifest.json', 'application/manifest+json'),
        '/sw.js': ('sw.js', 'application/javascript'),
        '/icon-192.png': ('icon-192.png', 'image/png'),
        '/icon-512.png': ('icon-512.png', 'image/png'),
        '/apple-touch-icon.png': ('apple-touch-icon.png', 'image/png'),
        '/og-image.png': ('og-image.png', 'image/png'),
        '/shiva/organize': ('shiva-organize.html', 'text/html'),
        '/shiva-organize': ('shiva-organize.html', 'text/html'),
        '/shiva-organize.html': ('shiva-organize.html', 'text/html'),
        '/shiva/guide': ('shiva-guide.html', 'text/html'),
        '/shiva-guide.html': ('shiva-guide.html', 'text/html'),
        '/shiva/caterers': ('shiva-caterers.html', 'text/html'),
        '/shiva-caterers.html': ('shiva-caterers.html', 'text/html'),
        '/shiva/caterers/apply': ('shiva-caterer-apply.html', 'text/html'),
        '/shiva-caterer-apply.html': ('shiva-caterer-apply.html', 'text/html'),
        '/shiva-essentials': ('shiva-essentials.html', 'text/html'),
        '/shiva-essentials.html': ('shiva-essentials.html', 'text/html'),
        '/demo': ('demo.html', 'text/html'),
        '/help': ('help.html', 'text/html'),
        '/help/food': ('directory.html', 'text/html'),
        '/help/gifts': ('gifts.html', 'text/html'),
        '/help/supplies': ('shiva-essentials.html', 'text/html'),
        '/what-to-bring-to-a-shiva': ('what-to-bring-to-a-shiva.html', 'text/html'),
        '/what-to-bring-to-a-shiva.html': ('what-to-bring-to-a-shiva.html', 'text/html'),
        '/first-passover-after-loss': ('first-passover-after-loss.html', 'text/html'),
        '/first-passover-after-loss.html': ('first-passover-after-loss.html', 'text/html'),
        '/how-to-sit-shiva': ('how-to-sit-shiva.html', 'text/html'),
        '/how-to-sit-shiva.html': ('how-to-sit-shiva.html', 'text/html'),
        '/what-is-yahrzeit': ('what-is-yahrzeit.html', 'text/html'),
        '/what-is-yahrzeit.html': ('what-is-yahrzeit.html', 'text/html'),
        '/kosher-shiva-food': ('kosher-shiva-food.html', 'text/html'),
        '/kosher-shiva-food.html': ('kosher-shiva-food.html', 'text/html'),
        '/shiva-preparation-checklist': ('shiva-preparation-checklist.html', 'text/html'),
        '/shiva-preparation-checklist.html': ('shiva-preparation-checklist.html', 'text/html'),
        '/jewish-funeral-etiquette': ('jewish-funeral-etiquette.html', 'text/html'),
        '/jewish-funeral-etiquette.html': ('jewish-funeral-etiquette.html', 'text/html'),
        '/condolence-messages': ('condolence-messages.html', 'text/html'),
        '/condolence-messages.html': ('condolence-messages.html', 'text/html'),
        '/directory': ('directory.html', 'text/html'),
        '/directory.html': ('directory.html', 'text/html'),
        '/gifts': ('gifts.html', 'text/html'),
        '/gifts.html': ('gifts.html', 'text/html'),
        '/gifts/plant-a-tree': ('plant-a-tree.html', 'text/html'),
        '/plant-a-tree': ('plant-a-tree.html', 'text/html'),
        '/yahrzeit': ('yahrzeit.html', 'text/html'),
        '/yahrzeit.html': ('yahrzeit.html', 'text/html'),
        '/find-my-page': ('find-my-page.html', 'text/html'),
        '/dashboard': ('dashboard.html', 'text/html'),
        '/cofounder': ('dashboard.html', 'text/html'),
        '/dashboard.html': ('dashboard.html', 'text/html'),
        '/partner': ('partner.html', 'text/html'),
        '/partner.html': ('partner.html', 'text/html'),
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
        elif path == '/api/scraper-thread':
            if not self._check_admin_auth():
                return
            self.send_json_response({'status': 'success', 'data': _periodic_scraper_status})
        elif path == '/api/digest-status':
            self.handle_digest_status()
        elif path == '/api/digest-trigger':
            self.handle_digest_trigger()
        elif path == '/api/scheduler-status':
            self.handle_scheduler_status()
        elif path == '/api/subscriber-list':
            self.handle_subscriber_list()
        elif path == '/api/subscribers/count':
            self.get_subscriber_count()
        elif path == '/api/community-stats':
            self.get_community_stats()
        elif path == '/api/directory-stats':
            self.get_directory_stats()
        elif path == '/api/dashboard-stats':
            self.get_dashboard_stats()
        elif path == '/api/referral-stats':
            self.get_referral_stats()
        elif path == '/api/tributes/counts':
            self.get_tribute_counts()
        # Single obituary API
        elif path.startswith('/api/obituary/'):
            obit_id = path[len('/api/obituary/'):]
            self.get_single_obituary(obit_id)
        # Tributes API
        elif path.startswith('/api/tributes/') and path.endswith('/keepsake.pdf'):
            obit_id = path[len('/api/tributes/'):-len('/keepsake.pdf')]
            self.handle_keepsake_pdf(obit_id)
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
            query_params = parse_qs(parsed_path.query)
            city_filter = query_params.get('city', [None])[0]
            self.get_vendors(city_filter)
        elif path == '/api/gift-vendors':
            self.get_gift_vendors()
        elif path == '/api/track-click':
            self.handle_track_click()
        elif path.startswith('/api/vendor-analytics/'):
            slug = path[len('/api/vendor-analytics/'):]
            self.get_vendor_analytics(slug)
        elif path.startswith('/api/vendors/'):
            slug = path[len('/api/vendors/'):]
            self.get_vendor_by_slug(slug)
        # Vendor analytics page (/vendor-analytics/slug)
        elif path.startswith('/vendor-analytics/') and path != '/vendor-analytics/':
            self.serve_vendor_analytics_page()
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
        # V4: Accept host transfer (must be before /api/shiva/{id} catch-all)
        elif path == '/api/shiva/accept-transfer':
            self.handle_accept_host_transfer()
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
        # Yahrzeit confirm/unsubscribe routes
        elif path.startswith('/yahrzeit/confirm/'):
            token = path[len('/yahrzeit/confirm/'):]
            self.handle_yahrzeit_confirm(token)
        elif path.startswith('/yahrzeit/unsubscribe/'):
            token = path[len('/yahrzeit/unsubscribe/'):]
            self.handle_yahrzeit_unsubscribe(token)
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
        elif path == '/admin/subscribers':
            self.handle_admin_subscribers()
        elif path == '/admin/unlock-db':
            self.handle_admin_unlock_db()
        # Redirects
        elif path == '/shiva-guide':
            self.send_response(301)
            self.send_header('Location', '/what-to-bring-to-a-shiva')
            self.end_headers()
            self._log_request('GET', path, 301, _req_start)
            return
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
        if content_length > 1048576:  # 1 MB max body size
            self.send_error_response('Payload Too Large', 413)
            return
        body = self.rfile.read(content_length) if content_length > 0 else b''

        if path == '/admin/restore':
            self.handle_admin_restore(body)
        elif path == '/admin/confirm-subscriber':
            self.handle_admin_confirm_subscriber(body)
        elif path == '/admin/confirm-all-subscribers':
            self.handle_admin_confirm_all_subscribers(body)
        elif path == '/admin/add-subscriber':
            self.handle_admin_add_subscriber(body)
        elif path == '/admin/delete-subscribers':
            self.handle_admin_delete_subscribers(body)
        elif path == '/admin/delete-obituary':
            self.handle_admin_delete_obituary(body)
        elif path == '/admin/hide-obituary':
            self.handle_admin_hide_obituary(body)
        elif path == '/api/yahrzeit/subscribe':
            self.handle_yahrzeit_subscribe(body)
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
        elif path == '/api/track-referral':
            self.handle_track_referral(body)
        elif path == '/api/find-my-page':
            self.handle_find_my_page(body)
        elif path == '/api/shiva-access/request':
            self.handle_access_request(body)
        elif path == '/api/shiva':
            self.handle_create_shiva(body)
        # V4: Transfer host
        elif path.startswith('/api/shiva/') and path.endswith('/transfer-host'):
            support_id = path[len('/api/shiva/'):-len('/transfer-host')]
            self.handle_transfer_host(support_id, body)
        # V4: Cancel transfer
        elif path.startswith('/api/shiva/') and path.endswith('/cancel-transfer'):
            support_id = path[len('/api/shiva/'):-len('/cancel-transfer')]
            self.handle_cancel_transfer(support_id, body)
        # V4: Volunteer cancel own signup
        elif path.startswith('/api/shiva/') and path.endswith('/cancel-signup'):
            support_id = path[len('/api/shiva/'):-len('/cancel-signup')]
            self.handle_cancel_own_signup(support_id, body)
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
        # V4: Donation prompt tracking
        elif path.startswith('/api/shiva/') and path.endswith('/donation-prompt'):
            support_id = path[len('/api/shiva/'):-len('/donation-prompt')]
            self.handle_donation_prompt(support_id, body)
        elif path.startswith('/api/shiva/') and path.endswith('/donation'):
            support_id = path[len('/api/shiva/'):-len('/donation')]
            self.handle_donation(support_id, body)
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
        if content_length > 1048576:  # 1 MB max body size
            self.send_error_response('Payload Too Large', 413)
            return
        body = self.rfile.read(content_length) if content_length > 0 else b''

        # V4: Volunteer edit own signup — PUT /api/shiva/{id}/signup/{signupId}
        if path.startswith('/api/shiva/') and '/signup/' in path:
            parts = path[len('/api/shiva/'):].split('/signup/')
            if len(parts) == 2:
                support_id = parts[0]
                signup_id = parts[1]
                self.handle_edit_signup(support_id, signup_id, body)
                return
        if path.startswith('/api/shiva/'):
            support_id = path[len('/api/shiva/'):]
            self.handle_update_shiva(support_id, body)
        else:
            self.send_404()

    def do_DELETE(self):
        """Handle DELETE requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Admin: delete a tribute entry by ID
        # DELETE /api/tributes/{obituary_id}/{entry_id}?key=ADMIN_KEY
        if path.startswith('/api/tributes/'):
            parts = path[len('/api/tributes/'):].split('/')
            if len(parts) == 2:
                obit_id, entry_id = parts
                self.handle_delete_tribute(obit_id, entry_id)
                return
        self.send_404()

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_cors_headers()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.end_headers()

    def send_cors_headers(self):
        """Send CORS headers — restrict to neshama.ca for security"""
        origin = self.headers.get('Origin', '')
        allowed_origins = ['https://neshama.ca', 'https://www.neshama.ca']
        if os.environ.get('DEV_MODE', '').lower() == 'true':
            allowed_origins.append('http://localhost:5000')
        if origin in allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            self.send_header('Access-Control-Allow-Origin', 'https://neshama.ca')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Stripe-Signature, X-Admin-Key, Authorization')
        self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

    def serve_static(self, path):
        """Serve static files from the frontend directory with cache-busting headers"""
        filename, content_type = self.STATIC_FILES[path]
        filepath = os.path.join(FRONTEND_DIR, filename)
        try:
            with open(filepath, 'rb') as f:
                content = f.read()

            # Generate ETag from content hash for conditional requests
            etag = '"' + hashlib.md5(content).hexdigest() + '"'

            # Check If-None-Match for conditional GET (304 Not Modified)
            if_none_match = self.headers.get('If-None-Match', '')
            if if_none_match == etag:
                self.send_response(304)
                self.send_header('ETag', etag)
                self.end_headers()
                return

            # Get file modification time for Last-Modified header
            mtime = os.path.getmtime(filepath)
            last_modified = _format_http_date(mtime, usegmt=True)

            self.send_response(200)
            if content_type.startswith('text/') or content_type in ('application/javascript', 'application/manifest+json'):
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            else:
                self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('ETag', etag)
            self.send_header('Last-Modified', last_modified)

            # Cache-Control strategy per content type:
            # - HTML: always revalidate so users get latest after deploy
            # - Service worker: must never be cached (sw.js)
            # - CSS/JS: cache 1 hour, revalidate after
            # - Images/icons/manifest: cache 1 day
            if content_type == 'text/html' or filename == 'sw.js':
                self.send_header('Cache-Control', 'no-cache')
            elif content_type in ('image/svg+xml', 'image/png', 'application/manifest+json'):
                self.send_header('Cache-Control', 'public, max-age=86400')
            elif content_type in ('application/javascript', 'text/css'):
                self.send_header('Cache-Control', 'public, max-age=3600')
            else:
                self.send_header('Cache-Control', 'no-cache')

            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_404()

    # ── API: Obituaries ──────────────────────────────────────

    def get_obituaries(self, city=None):
        """Get all obituaries from database, optionally filtered by city"""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Filter out hidden obituaries (junk/test entries flagged via admin)
            hidden_filter = "AND COALESCE(o.hidden, 0) = 0"

            if city:
                cursor.execute(f'''
                    SELECT o.*,
                           CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                    FROM obituaries o
                    LEFT JOIN shiva_support s
                      ON s.obituary_id = o.id AND s.status = 'active'
                    WHERE o.city = ?
                    {hidden_filter}
                    ORDER BY o.last_updated DESC
                ''', (city,))
            else:
                cursor.execute(f'''
                    SELECT o.*,
                           CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                    FROM obituaries o
                    LEFT JOIN shiva_support s
                      ON s.obituary_id = o.id AND s.status = 'active'
                    WHERE 1=1
                    {hidden_filter}
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
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT o.*,
                       CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS has_shiva
                FROM obituaries o
                LEFT JOIN shiva_support s
                  ON s.obituary_id = o.id AND s.status = 'active'
                WHERE (o.deceased_name LIKE ? OR o.hebrew_name LIKE ?)
                AND COALESCE(o.hidden, 0) = 0
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
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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
            # Rate limit: 5 subscribes per 5 minutes per IP
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'subscribe', max_calls=5, window=300):
                self._send_rate_limit_error()
                return

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
                # Add spam folder reminder to success messages
                if result.get('status') == 'success' and 'confirm' in result.get('message', '').lower():
                    result['message'] = (
                        'Please check your inbox (and spam folder) for a confirmation email '
                        'from updates@neshama.ca. Click the link to complete your subscription.'
                    )
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
                conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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
        """Get guestbook entries for an obituary, with optional type filter"""
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            entry_type = params.get('type', [None])[0]

            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = 'SELECT id, obituary_id, author_name, message, relationship, created_at, entry_type, prayer_text, is_candle FROM tributes WHERE obituary_id = ?'
            args = [obit_id]
            if entry_type and entry_type in ('memory', 'condolence', 'prayer', 'candle'):
                query += ' AND entry_type = ?'
                args.append(entry_type)
            query += ' ORDER BY created_at DESC'

            cursor.execute(query, args)
            tributes = [dict(row) for row in cursor.fetchall()]
            conn.close()
            self.send_json_response({'status': 'success', 'data': tributes, 'count': len(tributes)})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': [], 'count': 0})

    def get_tribute_counts(self):
        """Get tribute counts for all obituaries"""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT obituary_id, COUNT(*) as count FROM tributes GROUP BY obituary_id'
            )
            counts = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            self.send_json_response({'status': 'success', 'data': counts})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': {}})

    VALID_ENTRY_TYPES = ('memory', 'condolence', 'prayer', 'candle')

    def handle_submit_tribute(self, body):
        """Handle guestbook entry submission (memory, condolence, prayer, or candle)"""
        try:
            # Rate limit: 5 entries per 5 minutes per IP
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'tribute', max_calls=5, window=300):
                self.send_json_response({'status': 'error', 'message': 'Please wait before submitting another entry.'}, 429)
                return

            data = json.loads(body)
            import re as _re_mod
            obit_id = data.get('obituary_id', '').strip()
            author = _re_mod.sub(r'<[^>]+>', '', data.get('author_name', '').strip())
            message = _re_mod.sub(r'<[^>]+>', '', data.get('message', '').strip())
            relationship = _re_mod.sub(r'<[^>]+>', '', data.get('relationship', '').strip())
            entry_type = data.get('entry_type', 'condolence').strip()
            prayer_text = _re_mod.sub(r'<[^>]+>', '', data.get('prayer_text', '').strip())

            # Validate entry type
            if entry_type not in self.VALID_ENTRY_TYPES:
                self.send_json_response({'status': 'error', 'message': 'Invalid entry type'}, 400)
                return

            # All types require name and obituary
            if not obit_id or not author:
                self.send_json_response({'status': 'error', 'message': 'Name is required'}, 400)
                return

            # Type-specific validation
            if entry_type in ('memory', 'condolence') and not message:
                self.send_json_response({'status': 'error', 'message': 'Message is required'}, 400)
                return
            if entry_type == 'prayer' and not prayer_text and not message:
                self.send_json_response({'status': 'error', 'message': 'Please select or write a prayer'}, 400)
                return
            # Candle: message is optional

            is_candle = 1 if entry_type == 'candle' else 0

            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                '''INSERT INTO tributes
                   (obituary_id, author_name, message, relationship, created_at, entry_type, prayer_text, is_candle)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (obit_id, author, message, relationship, now, entry_type, prayer_text or None, is_candle)
            )
            conn.commit()
            tribute_id = cursor.lastrowid
            conn.close()

            if SHIVA_AVAILABLE:
                shiva_mgr._trigger_backup()

            self.send_json_response({
                'status': 'success',
                'message': 'Entry added to guestbook',
                'id': tribute_id
            })
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_delete_tribute(self, obit_id, entry_id):
        """Delete a guestbook entry by ID (admin only via X-Admin-Key header)"""
        try:
            admin_key = os.environ.get('ADMIN_KEY', '')
            if not admin_key:
                self.send_json_response({'status': 'error', 'message': 'Admin key not configured'}, 403)
                return
            req_key = self.headers.get('X-Admin-Key', '')
            if not hmac.compare_digest(str(req_key), str(admin_key)):
                self.send_json_response({'status': 'error', 'message': 'Unauthorized'}, 403)
                return

            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM tributes WHERE obituary_id = ? AND id = ?',
                (obit_id, int(entry_id))
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted:
                if SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()
                self.send_json_response({'status': 'success', 'message': f'Tribute {entry_id} deleted'})
            else:
                self.send_json_response({'status': 'error', 'message': 'Entry not found'}, 404)
        except Exception as e:
            self.send_error_response(str(e))

    # ── API: PDF Keepsake ──────────────────────────────────────

    def handle_keepsake_pdf(self, obit_id):
        """Generate and serve a PDF keepsake of all guestbook entries for an obituary."""
        try:
            # Rate limit: 10 PDFs per 5 minutes per IP
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'keepsake_pdf', max_calls=10, window=300):
                self.send_json_response({'status': 'error', 'message': 'Please wait before generating another PDF.'}, 429)
                return

            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get obituary data
                cursor.execute('SELECT * FROM obituaries WHERE id = ?', (obit_id,))
                obit_row = cursor.fetchone()
                if not obit_row:
                    self.send_json_response({'status': 'error', 'message': 'Obituary not found'}, 404)
                    return

                obituary_data = dict(obit_row)

                # Get all guestbook entries
                cursor.execute(
                    'SELECT * FROM tributes WHERE obituary_id = ? ORDER BY created_at DESC',
                    (obit_id,)
                )
                tributes_data = [dict(row) for row in cursor.fetchall()]
            finally:
                conn.close()

            # Generate PDF
            from pdf_keepsake import generate_keepsake_pdf
            pdf_bytes = generate_keepsake_pdf(obituary_data, tributes_data)

            # Serve as download
            safe_name = re.sub(r'[^\w\s-]', '', obituary_data.get('deceased_name', 'memorial')).strip()
            safe_name = re.sub(r'\s+', '-', safe_name)
            if not safe_name:
                safe_name = 'memorial'
            filename = f'Guestbook-Keepsake-{safe_name}.pdf'

            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(pdf_bytes)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(pdf_bytes)

        except ImportError as e:
            logging.error(f'[PDF] reportlab not installed: {e}')
            self.send_json_response({
                'status': 'error',
                'message': 'PDF generation not available (reportlab missing)'
            }, 503)
        except Exception as e:
            logging.error(f'[PDF] Keepsake generation error: {e}')
            self.send_error_response('Failed to generate keepsake PDF')

    # ── API: Community Stats ──────────────────────────────────

    def get_community_stats(self):
        """Get community-wide statistics"""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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

    # ── API: Dashboard Stats (Cofounder) ────────────────────────

    def get_dashboard_stats(self):
        """Consolidated stats endpoint for the cofounder dashboard.
        Public (no PII) — only aggregate counts and vendor click data."""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Core counts
            obituary_count = 0
            vendor_count = 0
            caterer_count = 0
            subscriber_count = 0
            tribute_count = 0
            active_shiva_count = 0
            total_clicks = 0

            try:
                cursor.execute('SELECT COUNT(*) FROM obituaries')
                obituary_count = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute('SELECT COUNT(*) FROM vendors')
                vendor_count = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute("SELECT COUNT(*) FROM caterer_partners WHERE status = 'approved'")
                caterer_count = cursor.fetchone()[0]
            except Exception:
                pass
            if caterer_count == 0:
                try:
                    cursor.execute("SELECT COUNT(*) FROM vendors WHERE vendor_type = 'food'")
                    caterer_count = cursor.fetchone()[0]
                except Exception:
                    pass

            try:
                cursor.execute('SELECT COUNT(*) FROM subscribers WHERE confirmed = TRUE')
                subscriber_count = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute('SELECT COUNT(*) FROM tributes')
                tribute_count = cursor.fetchone()[0]
            except Exception:
                pass

            try:
                cursor.execute("SELECT COUNT(*) FROM shiva_support WHERE status = 'active'")
                active_shiva_count = cursor.fetchone()[0]
            except Exception:
                pass

            # Vendor click tracking
            vendor_clicks = []
            try:
                cursor.execute('''
                    SELECT
                        vc.vendor_slug,
                        COUNT(vc.id) as click_count,
                        MAX(vc.created_at) as last_click,
                        COALESCE(vv.view_count, 0) as view_count
                    FROM vendor_clicks vc
                    LEFT JOIN (
                        SELECT vendor_slug, COUNT(*) as view_count
                        FROM vendor_views
                        GROUP BY vendor_slug
                    ) vv ON vc.vendor_slug = vv.vendor_slug
                    GROUP BY vc.vendor_slug
                    ORDER BY click_count DESC
                    LIMIT 50
                ''')
                vendor_clicks = [dict(row) for row in cursor.fetchall()]
                cursor.execute('SELECT COUNT(*) FROM vendor_clicks')
                total_clicks = cursor.fetchone()[0]
            except Exception:
                pass

            # Recent obituaries (last 8)
            recent_obituaries = []
            try:
                cursor.execute('''
                    SELECT id, name, funeral_home, scraped_at as date_added
                    FROM obituaries
                    ORDER BY scraped_at DESC
                    LIMIT 8
                ''')
                recent_obituaries = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

            # Recent tributes (last 8)
            recent_tributes = []
            try:
                cursor.execute('''
                    SELECT id, author_name, message, created_at
                    FROM tributes
                    ORDER BY created_at DESC
                    LIMIT 8
                ''')
                recent_tributes = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'obituaries': obituary_count,
                    'vendors': vendor_count,
                    'caterers': caterer_count,
                    'subscribers': subscriber_count,
                    'tributes': tribute_count,
                    'active_shiva': active_shiva_count,
                    'total_clicks': total_clicks,
                    'vendor_clicks': vendor_clicks,
                    'recent_obituaries': recent_obituaries,
                    'recent_tributes': recent_tributes
                }
            })
        except Exception as e:
            logging.error(f"[Dashboard] Stats error: {e}")
            self.send_json_response({
                'status': 'success',
                'data': {
                    'obituaries': 0, 'vendors': 0, 'caterers': 0,
                    'subscribers': 0, 'tributes': 0, 'active_shiva': 0,
                    'total_clicks': 0, 'vendor_clicks': [],
                    'recent_obituaries': [], 'recent_tributes': []
                }
            })

    # ── Admin: Scraper ─────────────────────────────────────────

    def handle_admin_scrape(self):
        """Run scrapers via admin endpoint (async - returns immediately)"""
        global _scrape_status
        if not self._check_admin_auth():
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
        if not self._check_admin_auth():
            return

        self.send_json_response({
            'running': _scrape_status['running'],
            'last_started': _scrape_status['last_started'],
            'last_completed': _scrape_status['last_completed'],
            'last_result': _scrape_status['last_result'],
            'last_error': _scrape_status['last_error'],
        })

    def handle_admin_subscribers(self):
        """List all subscribers with their status"""
        if not self._check_admin_auth():
            return

        try:
            conn = _connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, confirmed, frequency, locations, subscribed_at,
                       confirmed_at, last_email_sent, unsubscribed_at
                FROM subscribers ORDER BY subscribed_at DESC
            ''')
            rows = cursor.fetchall()
            conn.close()
            subscribers = []
            for r in rows:
                subscribers.append({
                    'email': r[0],
                    'confirmed': bool(r[1]),
                    'frequency': r[2],
                    'locations': r[3],
                    'subscribed_at': r[4],
                    'confirmed_at': r[5],
                    'last_email_sent': r[6],
                    'unsubscribed': r[7] is not None
                })
            self.send_json_response({
                'total': len(subscribers),
                'confirmed': sum(1 for s in subscribers if s['confirmed']),
                'unconfirmed': sum(1 for s in subscribers if not s['confirmed']),
                'subscribers': subscribers
            })
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_confirm_subscriber(self, body):
        """Manually confirm a subscriber by email"""
        if not self._check_admin_auth():
            return

        try:
            data = json.loads(body.decode('utf-8'))
            email = data.get('email', '').strip().lower()
            if not email:
                self.send_error_response('Email required', 400)
                return

            conn = _connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE subscribers SET confirmed = TRUE, confirmed_at = ?
                WHERE email = ? AND confirmed = FALSE
            ''', (datetime.now().isoformat(), email))
            updated = cursor.rowcount
            conn.commit()
            conn.close()

            if updated:
                self.send_json_response({'status': 'confirmed', 'email': email})
            else:
                self.send_json_response({'status': 'not_found_or_already_confirmed', 'email': email})
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_confirm_all_subscribers(self, body):
        """Confirm ALL unconfirmed subscribers (bulk fix for SPF/spam issues)"""
        if not self._check_admin_auth():
            return

        try:
            conn = _connect_db()
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Get list of unconfirmed subscribers before updating (for logging)
            cursor.execute('''
                SELECT email, subscribed_at FROM subscribers
                WHERE confirmed = FALSE AND unsubscribed_at IS NULL
            ''')
            unconfirmed = cursor.fetchall()

            if not unconfirmed:
                self.send_json_response({
                    'status': 'ok',
                    'message': 'No unconfirmed subscribers found',
                    'confirmed_count': 0
                })
                conn.close()
                return

            # Confirm all unconfirmed subscribers
            cursor.execute('''
                UPDATE subscribers SET confirmed = TRUE, confirmed_at = ?
                WHERE confirmed = FALSE AND unsubscribed_at IS NULL
            ''', (now,))
            confirmed_count = cursor.rowcount
            conn.commit()
            conn.close()

            # Log each confirmed subscriber
            for email, subscribed_at in unconfirmed:
                logging.info(f"[Admin] Auto-confirmed subscriber: {email} (subscribed: {subscribed_at})")

            logging.info(f"[Admin] Bulk confirmed {confirmed_count} subscribers")

            self.send_json_response({
                'status': 'success',
                'message': f'Confirmed {confirmed_count} subscribers',
                'confirmed_count': confirmed_count,
                'emails': [row[0] for row in unconfirmed]
            })
        except Exception as e:
            logging.error(f"[Admin] Error confirming all subscribers: {e}")
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_add_subscriber(self, body):
        """Add a pre-confirmed subscriber (admin bypass, no double opt-in)"""
        if not self._check_admin_auth():
            return

        try:
            data = json.loads(body.decode('utf-8'))
            email = data.get('email', '').strip().lower()
            frequency = data.get('frequency', 'daily')
            locations = data.get('locations', 'toronto,montreal')

            if not email:
                self.send_error_response('Email required', 400)
                return

            conn = _connect_db()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            import secrets
            unsubscribe_token = secrets.token_urlsafe(32)

            cursor.execute('''
                INSERT OR IGNORE INTO subscribers
                (email, confirmed, confirmation_token, subscribed_at, confirmed_at,
                 unsubscribe_token, frequency, locations)
                VALUES (?, TRUE, ?, ?, ?, ?, ?, ?)
            ''', (email, secrets.token_urlsafe(32), now, now, unsubscribe_token, frequency, locations))

            if cursor.rowcount:
                conn.commit()
                logging.info(f"[Admin] Added pre-confirmed subscriber: {email}")
                self.send_json_response({'status': 'added', 'email': email})
            else:
                self.send_json_response({'status': 'already_exists', 'email': email})
            conn.close()
        except Exception as e:
            logging.error(f"[Admin] Error adding subscriber: {e}")
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_delete_subscribers(self, body):
        """Delete subscribers matching a pattern (e.g. smoketest addresses)"""
        if not self._check_admin_auth():
            return

        try:
            data = json.loads(body.decode('utf-8'))
            pattern = data.get('pattern', '').strip()
            if not pattern:
                self.send_error_response('Pattern required (e.g. "smoketest%@neshama.ca")', 400)
                return

            conn = _connect_db()
            cursor = conn.cursor()
            cursor.execute('SELECT email FROM subscribers WHERE email LIKE ?', (pattern,))
            matches = [row[0] for row in cursor.fetchall()]

            if not matches:
                conn.close()
                self.send_json_response({'status': 'ok', 'message': 'No matches', 'deleted': 0})
                return

            cursor.execute('DELETE FROM subscribers WHERE email LIKE ?', (pattern,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            for email in matches:
                logging.info(f"[Admin] Deleted subscriber: {email}")

            self.send_json_response({
                'status': 'success',
                'deleted': deleted,
                'emails': matches
            })
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_delete_obituary(self, body):
        """Delete obituaries by ID. POST /admin/delete-obituary?key=ADMIN_SECRET
        Body: {"ids": ["id1", "id2", ...]}"""
        if not self._check_admin_auth():
            return

        try:
            data = json.loads(body.decode('utf-8'))
            ids = data.get('ids', [])
            if not ids or not isinstance(ids, list):
                self.send_error_response('ids array required', 400)
                return

            conn = _connect_db()
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in ids])
            cursor.execute(f'SELECT id, deceased_name FROM obituaries WHERE id IN ({placeholders})', ids)
            found = cursor.fetchall()

            if not found:
                conn.close()
                self.send_json_response({'status': 'ok', 'message': 'No matching obituaries', 'deleted': 0})
                return

            cursor.execute(f'DELETE FROM obituaries WHERE id IN ({placeholders})', ids)
            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            for obit_id, name in found:
                logging.info(f"[Admin] Deleted obituary: {name} (id={obit_id})")

            self.send_json_response({
                'status': 'success',
                'deleted': deleted,
                'removed': [{'id': r[0], 'name': r[1]} for r in found]
            })
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_hide_obituary(self, body):
        """Hide/unhide obituaries by ID. POST /admin/hide-obituary?key=ADMIN_SECRET
        Body: {"ids": ["id1", "id2", ...], "hidden": true}
        Set hidden=false to unhide."""
        if not self._check_admin_auth():
            return

        try:
            data = json.loads(body.decode('utf-8'))
            ids = data.get('ids', [])
            hidden = 1 if data.get('hidden', True) else 0
            if not ids or not isinstance(ids, list):
                self.send_error_response('ids array required', 400)
                return

            conn = _connect_db()
            cursor = conn.cursor()

            # Ensure hidden column exists
            try:
                cursor.execute('ALTER TABLE obituaries ADD COLUMN hidden INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass

            placeholders = ','.join(['?' for _ in ids])
            cursor.execute(f'SELECT id, deceased_name FROM obituaries WHERE id IN ({placeholders})', ids)
            found = cursor.fetchall()

            if not found:
                conn.close()
                self.send_json_response({'status': 'ok', 'message': 'No matching obituaries', 'updated': 0})
                return

            cursor.execute(f'UPDATE obituaries SET hidden = ? WHERE id IN ({placeholders})', [hidden] + ids)
            updated = cursor.rowcount
            conn.commit()
            conn.close()

            action = 'Hidden' if hidden else 'Unhidden'
            for obit_id, name in found:
                logging.info(f"[Admin] {action} obituary: {name} (id={obit_id})")

            self.send_json_response({
                'status': 'success',
                'action': action.lower(),
                'updated': updated,
                'entries': [{'id': r[0], 'name': r[1]} for r in found]
            })
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    def handle_admin_unlock_db(self):
        """Force-clear SQLite locks by switching DELETE→WAL journal mode.
        GET /admin/unlock-db?key=ADMIN_SECRET"""
        if not self._check_admin_auth():
            return

        steps = []
        try:
            db_path = self.get_db_path()

            # Step 1: Remove lock files
            for suffix in ['-wal', '-shm']:
                lock_file = db_path + suffix
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    steps.append(f'Removed {suffix}')
                else:
                    steps.append(f'No {suffix} file')

            # Step 2: Open fresh in DELETE mode
            conn = sqlite3.connect(db_path, timeout=5)
            mode = conn.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
            steps.append(f'Switched to {mode}')

            # Step 3: Write test
            conn.execute('PRAGMA busy_timeout=5000')
            conn.execute("INSERT INTO scraper_log (source, run_time, status) VALUES ('unlock_test', datetime('now'), 'ok')")
            conn.commit()
            conn.close()
            steps.append('Write test PASSED')

            self.send_json_response({'status': 'success', 'steps': steps})
        except Exception as e:
            steps.append(f'ERROR: {str(e)}')
            self.send_json_response({'status': 'error', 'steps': steps, 'error': str(e)}, 500)

    def handle_admin_digest(self):
        """Send daily email digest via admin endpoint"""
        if not self._check_admin_auth():
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

    def handle_digest_status(self):
        """Public endpoint showing last digest run status + recent history from DB.
        Add ?run=1 to manually trigger the digest (admin auth required)."""
        import json as _json

        # Manual trigger: /api/digest-status?run=1 (requires admin auth)
        parsed = urlparse(self.path)
        if parse_qs(parsed.query).get('run', [''])[0] == '1':
            if not self._check_admin_auth():
                return
            try:
                from daily_digest import DailyDigestSender
                sg_key = os.environ.get('SENDGRID_API_KEY')
                sender = DailyDigestSender(db_path=DB_PATH, sendgrid_api_key=sg_key)
                result = sender.send_daily_digest()
                global _last_digest_run
                ran_at = datetime.now(tz=_tz.utc).isoformat()
                _last_digest_run['ran_at'] = ran_at
                _last_digest_run['result'] = result
                _last_digest_run['error'] = None
                try:
                    dconn = sqlite3.connect(DB_PATH, timeout=30)
                    dc = dconn.cursor()
                    dc.execute('''CREATE TABLE IF NOT EXISTS digest_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ran_at TEXT NOT NULL, result TEXT, error TEXT)''')
                    dc.execute('INSERT INTO digest_runs (ran_at, result, error) VALUES (?, ?, ?)',
                               (ran_at, _json.dumps(result), None))
                    dconn.commit()
                    dconn.close()
                except Exception:
                    pass
                self.send_json_response({'status': 'triggered', 'result': result})
                return
            except Exception as e:
                self.send_json_response({'status': 'trigger_error', 'error': str(e)}, 500)
                return

        response = dict(_last_digest_run)
        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('''SELECT ran_at, result, error FROM digest_runs
                             ORDER BY id DESC LIMIT 5''')
            history = []
            for row in cursor.fetchall():
                ran_at, result_str, error = row
                try:
                    result = _json.loads(result_str) if result_str else None
                except Exception:
                    result = result_str
                history.append({'ran_at': ran_at, 'result': result, 'error': error})
            conn.close()
            response['history'] = history
        except Exception:
            response['history'] = []
        self.send_json_response(response)

    def handle_digest_trigger(self):
        """Manually trigger the daily digest (admin auth required). Safe to call multiple times
        — won't double-send because daily_digest.py checks email_log for dedup."""
        if not self._check_admin_auth():
            return
        try:
            from daily_digest import DailyDigestSender
            sg_key = os.environ.get('SENDGRID_API_KEY')
            if not sg_key:
                self.send_json_response({'status': 'error', 'message': 'No SendGrid API key'}, 500)
                return
            sender = DailyDigestSender(db_path=DB_PATH, sendgrid_api_key=sg_key)
            result = sender.send_daily_digest()

            global _last_digest_run
            ran_at = datetime.now(tz=_tz.utc).isoformat()
            _last_digest_run['ran_at'] = ran_at
            _last_digest_run['result'] = result
            _last_digest_run['error'] = None

            # Also persist to DB
            import json as _json
            try:
                dconn = sqlite3.connect(DB_PATH, timeout=30)
                dc = dconn.cursor()
                dc.execute('''CREATE TABLE IF NOT EXISTS digest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ran_at TEXT NOT NULL, result TEXT, error TEXT)''')
                dc.execute('INSERT INTO digest_runs (ran_at, result, error) VALUES (?, ?, ?)',
                           (ran_at, _json.dumps(result), None))
                dconn.commit()
                dconn.close()
            except Exception:
                pass

            self.send_json_response({'status': 'success', 'result': result})
        except Exception as e:
            self.send_json_response({'status': 'error', 'message': str(e)}, 500)

    def handle_scheduler_status(self):
        """Show all APScheduler jobs and their next run times."""
        try:
            jobs = []
            if 'scheduler' in globals() or hasattr(self, '_scheduler'):
                pass
            # Try to access the module-level scheduler
            import sys
            server_module = sys.modules.get('__main__')
            sched = getattr(server_module, 'scheduler', None) if server_module else None
            if not sched:
                # Try the local scope where it was defined
                self.send_json_response({'status': 'scheduler not accessible', 'note': 'scheduler is defined in local scope of run_server()'})
                return
            for job in sched.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': str(job.next_run_time),
                    'trigger': str(job.trigger),
                })
            self.send_json_response({'status': 'ok', 'jobs': jobs})
        except Exception as e:
            self.send_json_response({'status': 'error', 'message': str(e)})

    def handle_subscriber_list(self):
        """Subscriber summary endpoint (admin auth required, emails masked for privacy)."""
        if not self._check_admin_auth():
            return
        try:
            conn = _connect_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, confirmed, frequency, locations, subscribed_at,
                       confirmed_at, last_email_sent, unsubscribed_at
                FROM subscribers ORDER BY subscribed_at DESC
            ''')
            rows = cursor.fetchall()
            conn.close()

            def _mask(email):
                local, domain = email.split('@', 1)
                return local[0] + '***@' + domain if len(local) > 1 else '***@' + domain

            subscribers = []
            for r in rows:
                subscribers.append({
                    'email': _mask(r[0]),
                    'confirmed': bool(r[1]),
                    'frequency': r[2],
                    'locations': r[3],
                    'subscribed_at': r[4],
                    'confirmed_at': r[5],
                    'last_email_sent': r[6],
                    'active': bool(r[1]) and r[7] is None,
                })
            active = [s for s in subscribers if s['active']]
            self.send_json_response({
                'total': len(subscribers),
                'active': len(active),
                'daily': sum(1 for s in active if s.get('frequency') == 'daily'),
                'weekly': sum(1 for s in active if s.get('frequency') == 'weekly'),
                'subscribers': subscribers,
            })
        except Exception as e:
            self.send_error_response(f'Error: {str(e)}', 500)

    # ── Admin: Backup / Restore ─────────────────────────────

    def handle_admin_backup(self):
        """Return full backup JSON of all critical tables."""
        if not self._check_admin_auth():
            return

        if not SHIVA_AVAILABLE:
            self.send_error_response('Shiva manager not available', 503)
            return

        data = shiva_mgr.get_backup_data()
        self.send_json_response(data)

    def handle_admin_restore(self, body):
        """Restore from uploaded backup JSON."""
        if not self._check_admin_auth():
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
            success_url = data.get('success_url', 'https://neshama.ca/sustain-success')
            cancel_url = data.get('cancel_url', 'https://neshama.ca/sustain-cancelled')

            amount = data.get('amount', 18)
            result = payment_mgr.create_checkout_session(email, success_url, cancel_url, amount=amount)
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
        """Verify admin token from Authorization header, X-Admin-Key header, or ?token= query param.
        Returns True if authorized."""
        admin_token = os.environ.get('ADMIN_TOKEN', '')
        if not admin_token:
            return False
        # Check headers first, fall back to query param
        token = ''
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        elif self.headers.get('X-Admin-Key', ''):
            token = self.headers.get('X-Admin-Key', '')
        else:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('token', [''])[0]
        return hmac.compare_digest(str(token), str(admin_token))

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
            city_filter = query_params.get('city', [None])[0]
            has_filters = any(filters.values())
            if has_filters:
                result = shiva_mgr.get_caterers_filtered(filters)
            else:
                result = shiva_mgr.get_approved_caterers()

            # Filter by city if specified
            if city_filter and city_filter.lower() in ('toronto', 'montreal') and result.get('data'):
                city = city_filter.lower()
                montreal_keywords = ['montreal', 'montréal', 'côte-saint-luc', 'cote-saint-luc',
                                     'outremont', 'mile end', 'snowdon', 'hampstead', 'westmount',
                                     'dollard', 'mount royal', 'plateau', 'saint-henri', 'old montreal', ', qc']
                filtered = []
                for c in result['data']:
                    area = (c.get('delivery_area') or '').lower()
                    is_montreal = any(kw in area for kw in montreal_keywords)
                    if city == 'montreal' and is_montreal:
                        filtered.append(c)
                    elif city == 'toronto' and not is_montreal:
                        filtered.append(c)
                result['data'] = filtered

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

    def get_vendors(self, city_filter=None):
        """Get food vendors, optionally filtered by city"""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM vendors WHERE vendor_type = 'food' ORDER BY featured DESC, name ASC")
            except Exception:
                cursor.execute('SELECT * FROM vendors ORDER BY featured DESC, name ASC')
            vendors = [dict(row) for row in cursor.fetchall()]
            conn.close()

            # Filter by city if specified
            if city_filter and city_filter.lower() in ('toronto', 'montreal'):
                city = city_filter.lower()
                montreal_keywords = ['montreal', 'montréal', 'côte-saint-luc', 'cote-saint-luc',
                                     'outremont', 'mile end', 'snowdon', 'hampstead', 'westmount',
                                     'dollard', 'mount royal', 'plateau', 'saint-henri', 'old montreal', ', qc']
                filtered = []
                for v in vendors:
                    area = (v.get('delivery_area') or '').lower()
                    addr = (v.get('address') or '').lower()
                    neighborhood = (v.get('neighborhood') or '').lower()
                    combined = f'{area} {addr} {neighborhood}'

                    is_montreal = any(kw in combined for kw in montreal_keywords)

                    if city == 'montreal' and is_montreal:
                        filtered.append(v)
                    elif city == 'toronto' and not is_montreal:
                        filtered.append(v)
                vendors = filtered

            self.send_json_response({'status': 'success', 'data': vendors})
        except Exception as e:
            self.send_json_response({'status': 'success', 'data': []})

    def get_gift_vendors(self):
        """Get gift vendors"""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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

        # Validate destination URL — prevent open redirect attacks
        parsed_dest = urlparse(dest_url)
        if parsed_dest.scheme not in ('http', 'https') or not parsed_dest.netloc:
            logging.warning(f"[Click] Blocked redirect to invalid URL: {dest_url}")
            self.send_404()
            return

        # Log click to database
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
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
            conn = _connect_db(db_path)
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

    # ── Vendor Analytics Page + API ──────────────────────────

    def serve_vendor_analytics_page(self):
        """Serve the vendor analytics HTML page for /vendor-analytics/{slug}"""
        filepath = os.path.join(FRONTEND_DIR, 'vendor-analytics.html')
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

    def get_vendor_analytics(self, slug):
        """GET /api/vendor-analytics/{slug} — vendor-specific performance data"""
        if not slug:
            self.send_json_response({'status': 'error', 'message': 'Vendor slug required'}, 400)
            return

        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check vendor exists
            vendor_name = slug.replace('-', ' ').title()
            try:
                cursor.execute('SELECT name FROM vendors WHERE slug = ?', (slug,))
                row = cursor.fetchone()
                if row:
                    vendor_name = row['name']
            except Exception:
                pass

            # Total clicks
            total_clicks = 0
            first_click = None
            try:
                cursor.execute('SELECT COUNT(*) as cnt, MIN(created_at) as first_at FROM vendor_clicks WHERE vendor_slug = ?', (slug,))
                row = cursor.fetchone()
                total_clicks = row['cnt'] or 0
                first_click = row['first_at']
            except Exception:
                pass

            # Total views
            total_views = 0
            first_view = None
            try:
                cursor.execute('SELECT COUNT(*) as cnt, MIN(created_at) as first_at FROM vendor_views WHERE vendor_slug = ?', (slug,))
                row = cursor.fetchone()
                total_views = row['cnt'] or 0
                first_view = row['first_at']
            except Exception:
                pass

            # Total leads
            total_leads = 0
            try:
                cursor.execute('''
                    SELECT COUNT(*) as cnt FROM vendor_leads vl
                    JOIN vendors v ON vl.vendor_id = v.id
                    WHERE v.slug = ?
                ''', (slug,))
                total_leads = cursor.fetchone()['cnt'] or 0
            except Exception:
                pass

            # First activity date
            first_activity = None
            if first_click and first_view:
                first_activity = min(first_click, first_view)[:10]
            elif first_click:
                first_activity = first_click[:10]
            elif first_view:
                first_activity = first_view[:10]

            # Weekly trend (last 4 weeks)
            weekly_trend = []
            try:
                cursor.execute('''
                    SELECT
                        strftime('%Y-W%W', created_at) as week_key,
                        CASE
                            WHEN strftime('%W', created_at) = strftime('%W', 'now') THEN 'This week'
                            WHEN strftime('%W', created_at) = strftime('%W', 'now', '-7 days') THEN 'Last week'
                            WHEN strftime('%W', created_at) = strftime('%W', 'now', '-14 days') THEN '2 weeks ago'
                            ELSE '3+ weeks ago'
                        END as week_label,
                        COUNT(*) as clicks
                    FROM vendor_clicks
                    WHERE vendor_slug = ?
                    AND created_at >= datetime('now', '-28 days')
                    GROUP BY week_key
                    ORDER BY week_key ASC
                ''', (slug,))
                click_weeks = {row['week_key']: {'week_label': row['week_label'], 'clicks': row['clicks'], 'views': 0} for row in cursor.fetchall()}

                cursor.execute('''
                    SELECT
                        strftime('%Y-W%W', created_at) as week_key,
                        CASE
                            WHEN strftime('%W', created_at) = strftime('%W', 'now') THEN 'This week'
                            WHEN strftime('%W', created_at) = strftime('%W', 'now', '-7 days') THEN 'Last week'
                            WHEN strftime('%W', created_at) = strftime('%W', 'now', '-14 days') THEN '2 weeks ago'
                            ELSE '3+ weeks ago'
                        END as week_label,
                        COUNT(*) as views
                    FROM vendor_views
                    WHERE vendor_slug = ?
                    AND created_at >= datetime('now', '-28 days')
                    GROUP BY week_key
                    ORDER BY week_key ASC
                ''', (slug,))
                for row in cursor.fetchall():
                    wk = row['week_key']
                    if wk in click_weeks:
                        click_weeks[wk]['views'] = row['views']
                    else:
                        click_weeks[wk] = {'week_label': row['week_label'], 'clicks': 0, 'views': row['views']}

                weekly_trend = sorted(click_weeks.values(), key=lambda x: x.get('week_label', ''))
            except Exception:
                pass

            # Top referrers (where views/clicks come from)
            top_referrers = []
            try:
                cursor.execute('''
                    SELECT referrer_page, COUNT(*) as count
                    FROM (
                        SELECT referrer_page FROM vendor_views WHERE vendor_slug = ?
                        UNION ALL
                        SELECT referrer_page FROM vendor_clicks WHERE vendor_slug = ?
                    )
                    GROUP BY referrer_page
                    ORDER BY count DESC
                    LIMIT 10
                ''', (slug, slug))
                top_referrers = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'vendor_name': vendor_name,
                    'vendor_slug': slug,
                    'total_views': total_views,
                    'total_clicks': total_clicks,
                    'total_leads': total_leads,
                    'first_activity': first_activity,
                    'weekly_trend': weekly_trend,
                    'top_referrers': top_referrers
                }
            })

        except Exception as e:
            logging.error(f"[VendorAnalytics] Error for {slug}: {e}")
            self.send_json_response({'status': 'error', 'message': str(e)}, 500)

    # ── API: Referral Tracking ─────────────────────────────

    def handle_track_referral(self, body):
        """Track a referral visit (POST /api/track-referral)"""
        try:
            data = json.loads(body)
            ref_code = data.get('ref', '').strip()
            page = data.get('page', '/').strip()

            if not ref_code:
                self.send_json_response({'status': 'error', 'message': 'ref required'}, 400)
                return

            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref_code TEXT NOT NULL,
                    page TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(ref_code)
            ''')

            cursor.execute(
                'INSERT INTO referrals (ref_code, page, created_at) VALUES (?, ?, ?)',
                (ref_code, page, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()

            self.send_json_response({'status': 'success'})

        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            logging.error(f"[Referral] Failed to log referral: {e}")
            self.send_json_response({'status': 'error', 'message': str(e)}, 500)

    def get_referral_stats(self):
        """Get referral tracking stats (GET /api/referral-stats).
        Public (no PII) — only channel names and visit counts."""
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Overall stats by ref_code
            by_channel = []
            total = 0
            try:
                cursor.execute('''
                    SELECT ref_code,
                           COUNT(*) as visits,
                           MIN(created_at) as first_visit,
                           MAX(created_at) as last_visit
                    FROM referrals
                    GROUP BY ref_code
                    ORDER BY visits DESC
                ''')
                by_channel = [dict(row) for row in cursor.fetchall()]
                cursor.execute('SELECT COUNT(*) FROM referrals')
                total = cursor.fetchone()[0]
            except Exception:
                pass

            # Last 7 days trend
            daily_trend = []
            try:
                cursor.execute('''
                    SELECT DATE(created_at) as day,
                           ref_code,
                           COUNT(*) as visits
                    FROM referrals
                    WHERE created_at >= DATE('now', '-7 days')
                    GROUP BY day, ref_code
                    ORDER BY day DESC, visits DESC
                ''')
                daily_trend = [dict(row) for row in cursor.fetchall()]
            except Exception:
                pass

            conn.close()

            self.send_json_response({
                'status': 'success',
                'data': {
                    'total_referrals': total,
                    'by_channel': by_channel,
                    'daily_trend': daily_trend,
                }
            })
        except Exception as e:
            logging.error(f"[Referral] Stats error: {e}")
            self.send_json_response({
                'status': 'success',
                'data': {'total_referrals': 0, 'by_channel': [], 'daily_trend': []}
            })

    # ── API: Find My Page (Link Recovery) ───────────────────

    def handle_find_my_page(self, body):
        """Look up email across all tables and send recovery email with links."""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self.send_json_response({'status': 'error', 'message': 'Invalid request'}, 400)
            return

        email = (data.get('email') or '').strip().lower()
        if not email or '@' not in email:
            self.send_json_response({'status': 'error', 'message': 'Please enter a valid email address.'}, 400)
            return

        # Rate limit: 3 lookups per 10 minutes per IP
        client_ip = self._get_client_ip()
        if not _check_rate_limit(client_ip, 'find_my_page', max_calls=3, window=600):
            self._send_rate_limit_error()
            return

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        found_pages = []

        try:
            conn = _connect_db()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Shiva pages organized by this email
            cursor.execute('''
                SELECT id, family_name, status, magic_token, created_at
                FROM shiva_support
                WHERE LOWER(organizer_email) = ?
                ORDER BY created_at DESC
            ''', (email,))
            for row in cursor.fetchall():
                token_param = f"?token={row['magic_token']}" if row['magic_token'] else ''
                found_pages.append({
                    'type': 'shiva_organizer',
                    'label': f"Shiva page you organized for {row['family_name']}",
                    'url': f"{base_url}/shiva/{row['id']}{token_param}",
                    'status': row['status'] or 'active',
                    'date': row['created_at'],
                })

            # 2. Meal signups by this email
            cursor.execute('''
                SELECT ms.shiva_support_id, ms.meal_type, ms.meal_date, ms.volunteer_name,
                       ss.family_name
                FROM meal_signups ms
                JOIN shiva_support ss ON ms.shiva_support_id = ss.id
                WHERE LOWER(ms.volunteer_email) = ?
                ORDER BY ms.meal_date DESC
            ''', (email,))
            seen_shiva = set()
            for row in cursor.fetchall():
                sid = row['shiva_support_id']
                if sid not in seen_shiva:
                    seen_shiva.add(sid)
                    found_pages.append({
                        'type': 'meal_signup',
                        'label': f"Meal signup for {row['family_name']} family",
                        'url': f"{base_url}/shiva/{sid}",
                        'date': row['meal_date'],
                    })

            # 3. Yahrzeit reminders set by this email
            cursor.execute('''
                SELECT id, deceased_name, hebrew_date_of_death
                FROM yahrzeit_reminders
                WHERE LOWER(subscriber_email) = ? AND confirmed = 1
                ORDER BY created_at DESC
            ''', (email,))
            for row in cursor.fetchall():
                found_pages.append({
                    'type': 'yahrzeit',
                    'label': f"Yahrzeit reminder for {row['deceased_name']}",
                    'url': f"{base_url}/yahrzeit",
                    'date': row['hebrew_date_of_death'] or '',
                })

            # 4. Co-organizer invitations
            cursor.execute('''
                SELECT co.shiva_support_id, ss.family_name, co.status
                FROM shiva_co_organizers co
                JOIN shiva_support ss ON co.shiva_support_id = ss.id
                WHERE LOWER(co.email) = ?
                ORDER BY co.created_at DESC
            ''', (email,))
            for row in cursor.fetchall():
                sid = row['shiva_support_id']
                if sid not in seen_shiva:
                    seen_shiva.add(sid)
                    found_pages.append({
                        'type': 'co_organizer',
                        'label': f"Co-organizer for {row['family_name']} shiva",
                        'url': f"{base_url}/shiva/{sid}",
                        'date': '',
                    })

            conn.close()
        except Exception as e:
            logging.error(f"[FindMyPage] Database error: {e}")
            self.send_json_response({'status': 'error', 'message': 'Something went wrong. Please try again.'}, 500)
            return

        # Always respond success (don't reveal whether email exists)
        # But only send email if there are actually pages found
        if found_pages:
            self._send_find_my_page_email(email, found_pages, base_url)

        self.send_json_response({'status': 'success'})

    def _send_find_my_page_email(self, email, pages, base_url):
        """Send recovery email with all found page links."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')

        # Build page list HTML
        pages_html = ''
        for page in pages:
            icon = '🏠' if page['type'] == 'shiva_organizer' else '🍽' if page['type'] == 'meal_signup' else '🕯' if page['type'] == 'yahrzeit' else '👥'
            label = html_mod.escape(page['label'])
            url = html_mod.escape(page['url'])
            pages_html += f'''
            <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1rem 1.25rem;margin:0.75rem 0;">
                <p style="font-size:1rem;margin:0 0 0.5rem;font-weight:600;color:#3E2723;">{icon} {label}</p>
                <a href="{url}" style="color:#D2691E;text-decoration:none;font-size:0.95rem;word-break:break-all;">{url}</a>
            </div>'''

        html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Your Neshama Pages</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">Here are all the pages associated with your email.</p>
    </div>
    {pages_html}
    <p style="text-align:center;font-size:0.9rem;color:#8a9a8d;margin-top:1.5rem;">
        Save this email so you always have your links.
    </p>
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="{base_url}" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

        if not sendgrid_key:
            logging.info(f"[FindMyPage] Would send {len(pages)} page links to {email}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Content, MimeType

            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=('updates@neshama.ca', 'Neshama'),
                to_emails=email,
                subject=f'Your Neshama pages ({len(pages)} found)',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            sg.send(message)
            logging.info(f"[FindMyPage] Sent {len(pages)} page links to {email}")
        except Exception as e:
            logging.error(f"[FindMyPage] Email send error: {e}")

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
            if 'no such table' in str(e):
                self.send_json_response({'status': 'not_found'}, 404)
            else:
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
                # Send welcome email with share links
                self._send_welcome_email(result)
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

    def _send_welcome_email(self, result):
        """Send warm welcome email to organizer after page creation, with share links."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        email = result.get('organizer_email', '')
        family_name = result.get('family_name', '')
        shiva_id = result.get('id', '')
        magic_token = result.get('magic_token', '')

        if not email:
            return

        base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
        shiva_page_url = f"{base_url}/shiva/{shiva_id}"
        edit_url = f"{shiva_page_url}?token={magic_token}"

        import urllib.parse
        share_text = f"Help coordinate meals for the {family_name} shiva: {shiva_page_url}"
        wa_url = f"https://wa.me/?text={urllib.parse.quote(share_text)}"
        email_url = f"mailto:?subject={urllib.parse.quote(family_name + ' — Shiva Meal Coordination')}&body={urllib.parse.quote(share_text)}"
        sms_url = f"sms:?body={urllib.parse.quote(share_text)}"

        share_btn_style = "display:inline-block;padding:0.6rem 1.25rem;border-radius:2rem;text-decoration:none;font-size:0.95rem;margin:0.25rem;"

        html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Your shiva page is ready</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">for the {html_mod.escape(family_name)} family</p>
    </div>
    <p style="font-size:1rem;line-height:1.6;">
        Thank you for taking care of this. The community can now sign up to bring meals
        and show their support.
    </p>

    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1.5rem 0;">
        <p style="font-size:0.75rem;color:#558b2f;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">Share This Page</p>
        <p style="font-size:1rem;margin:0 0 1rem;">Send this link to family and friends so they can sign up to bring meals:</p>
        <p style="font-size:1rem;margin:0 0 1rem;"><a href="{html_mod.escape(shiva_page_url)}" style="color:#D2691E;text-decoration:none;font-weight:600;">{html_mod.escape(shiva_page_url)}</a></p>
        <div style="text-align:center;">
            <a href="{html_mod.escape(wa_url)}" style="{share_btn_style}background:#25D366;color:white;">Share via WhatsApp</a>
            <a href="{html_mod.escape(email_url)}" style="{share_btn_style}background:#D2691E;color:white;">Share via Email</a>
            <a href="{html_mod.escape(sms_url)}" style="{share_btn_style}background:#3E2723;color:white;">Share via Text</a>
        </div>
    </div>

    <div style="background:white;border:1px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1.5rem 0;">
        <p style="font-size:0.75rem;color:#D2691E;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Your Organizer Link</p>
        <p style="font-size:0.95rem;margin:0;">Use this link to manage the page, view signups, and invite co-organizers:</p>
        <p style="font-size:0.95rem;margin:0.5rem 0 0;word-break:break-all;"><a href="{html_mod.escape(edit_url)}" style="color:#D2691E;text-decoration:none;">{html_mod.escape(edit_url)}</a></p>
        <p style="font-size:0.8rem;color:#B2BEB5;margin-top:0.5rem;">Keep this link private &mdash; it gives full editing access to the page.</p>
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
            logging.info(f"[Welcome] Would send welcome email to {email}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email as SGEmail, To, Content, MimeType

            message = Mail(
                from_email=SGEmail('updates@neshama.ca', 'Neshama'),
                to_emails=To(email),
                subject=f'Your shiva page is ready \u2014 {family_name}',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Welcome] Sent to {email}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, shiva_id, 'welcome',
                                        email, None, sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Welcome] Failed to log email")
        except Exception:
            logging.exception("[Welcome] Email error")

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

            conn = _connect_db()
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

    # ── API: V4 — Pass Host ─────────────────────────────────

    def handle_transfer_host(self, support_id, body):
        """Initiate a host transfer to a new organizer."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.pop('magic_token', '') or data.pop('token', '')
            if not token:
                self.send_json_response({'status': 'error', 'message': 'Authorization required'}, 401)
                return
            # Rate limit
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'transfer_host', max_calls=3, window=600):
                self._send_rate_limit_error()
                return
            result = shiva_mgr.initiate_host_transfer(support_id, token, data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
                self._send_host_transfer_email(result)
            status_code = 200 if result['status'] == 'success' else 400
            # Don't expose transfer_token to client
            safe_result = {'status': result['status'], 'message': result.get('message', '')}
            if result.get('transfer_id'):
                safe_result['transfer_id'] = result['transfer_id']
            self.send_json_response(safe_result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_accept_host_transfer(self):
        """Accept a host transfer via token link."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        token = query_params.get('token', [''])[0]
        if not token:
            self._serve_access_result_page('Error', 'Invalid transfer link.')
            return
        result = shiva_mgr.accept_host_transfer(token)
        if result['status'] == 'success':
            shiva_mgr._trigger_backup()
            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            dashboard_url = f"{base_url}/shiva/{result['shiva_id']}?token={result['new_magic_token']}"
            self._serve_access_result_page(
                'You Are Now the Host',
                f'You are now the primary organizer for the <strong>{html_mod.escape(result["family_name"])}</strong> shiva page. '
                f'{html_mod.escape(result["old_organizer_name"])} has been moved to co-organizer and still has view access.<br><br>'
                f'<a href="{html_mod.escape(dashboard_url)}" style="color:#D2691E;">Go to your dashboard &rarr;</a>'
            )
        else:
            self._serve_access_result_page('Error', html_mod.escape(result.get('message', 'Something went wrong.')))

    def handle_cancel_transfer(self, support_id, body):
        """Cancel a pending host transfer."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            token = data.pop('magic_token', '') or data.pop('token', '')
            transfer_id = data.get('transfer_id')
            if not token or not transfer_id:
                self.send_json_response({'status': 'error', 'message': 'Authorization and transfer ID required'}, 401)
                return
            result = shiva_mgr.cancel_host_transfer(support_id, token, transfer_id)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_host_transfer_email(self, result):
        """Send transfer invitation email to new host."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_key:
            logging.info(f"[Transfer] Would send transfer invite to {result['to_email']}")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')
            accept_url = f"{base_url}/api/shiva/accept-transfer?token={result['transfer_token']}"

            html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Host Transfer Request</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(result['family_name'])} shiva</p>
    </div>
    <p style="font-size:1rem;line-height:1.6;">
        {html_mod.escape(result['from_name'])} would like to transfer primary organizer authority
        for the <strong>{html_mod.escape(result['family_name'])}</strong> shiva support page to you.
    </p>
    <p style="font-size:0.95rem;color:#5c534a;line-height:1.6;">
        As the new host, you will be able to manage all meal signups, invite co-organizers,
        send thank-you notes, and edit page details. {html_mod.escape(result['from_name'])} will
        remain as a co-organizer with view access.
    </p>
    <div style="text-align:center;margin:2rem 0;">
        <a href="{html_mod.escape(accept_url)}" style="display:inline-block;background:#D2691E;color:white;padding:0.85rem 2.5rem;border-radius:2rem;text-decoration:none;font-size:1.1rem;">Accept &amp; Become Host</a>
    </div>
    <p style="font-size:0.85rem;color:#8a9a8d;text-align:center;">
        This link expires in 72 hours. If you did not expect this, you can safely ignore it.
    </p>
    <hr style="border:none;border-top:1px solid #D4C5B9;margin:2rem 0 1rem;">
    <p style="text-align:center;font-size:0.8rem;color:#8a9a8d;">
        Neshama &middot; Community support when it matters most<br>
        <a href="https://neshama.ca" style="color:#D2691E;text-decoration:none;">neshama.ca</a>
    </p>
</div>"""

            plain_text = _html_to_plain(html_content)
            message = Mail(
                from_email=Email('updates@neshama.ca', 'Neshama'),
                to_emails=To(result['to_email'], result['to_name']),
                subject=f"Host transfer request — {result['family_name']} shiva",
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            msg_id = response.headers.get('X-Message-Id', '') if response.headers else ''
            logging.info(f"[Transfer] Invite sent to {result['to_email']}")

            if EMAIL_QUEUE_AVAILABLE:
                try:
                    log_immediate_email(DB_PATH, result['shiva_id'], 'host_transfer',
                                        result['to_email'], result['to_name'],
                                        sendgrid_message_id=msg_id)
                except Exception:
                    logging.exception("[Transfer] Failed to log email")
        except Exception:
            logging.exception("[Transfer] Email error")

    # ── API: V4 — Volunteer Self-Edit / Cancel ────────────────

    def handle_edit_signup(self, support_id, signup_id, body):
        """Handle volunteer editing their own signup."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            result = shiva_mgr.edit_signup(support_id, signup_id, data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_cancel_own_signup(self, support_id, body):
        """Handle volunteer cancelling their own signup."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            result = shiva_mgr.cancel_own_signup(support_id, data)
            if result['status'] == 'success':
                shiva_mgr._trigger_backup()
                # Send cancellation notification to organizer
                self._send_cancellation_notification(result, support_id)
            status_code = 200 if result['status'] == 'success' else 400
            # Don't expose organizer_email
            safe_result = {'status': result['status'], 'message': result.get('message', '')}
            self.send_json_response(safe_result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def _send_cancellation_notification(self, result, support_id):
        """Send email to organizer about a volunteer cancellation."""
        sendgrid_key = os.environ.get('SENDGRID_API_KEY')
        org_email = result.get('organizer_email', '')
        if not sendgrid_key or not org_email:
            logging.info(f"[Cancel] Would notify {org_email}: {result.get('volunteer_name')} cancelled")
            return

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content, MimeType

            vol_name = result.get('volunteer_name', 'A volunteer')
            meal_date = result.get('meal_date', '')
            meal_type = result.get('meal_type', '')
            family_name = result.get('family_name', 'your shiva page')

            try:
                d = datetime.strptime(meal_date, '%Y-%m-%d')
                formatted_date = d.strftime('%A, %B %d')
            except Exception:
                formatted_date = meal_date

            base_url = os.environ.get('BASE_URL', 'https://neshama.ca')

            html_content = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <div style="text-align:center;margin-bottom:1.5rem;">
        <h1 style="font-size:1.6rem;font-weight:400;color:#3E2723;margin:0;">Meal Cancellation</h1>
        <p style="color:#8a9a8d;font-size:1.05rem;margin-top:0.25rem;">{html_mod.escape(family_name)} shiva</p>
    </div>
    <p style="font-size:1rem;line-height:1.6;">
        <strong>{html_mod.escape(vol_name)}</strong> has cancelled their <strong>{html_mod.escape(meal_type)}</strong>
        signup for <strong>{formatted_date}</strong>.
    </p>
    <p style="font-size:0.95rem;color:#5c534a;">
        This meal slot is now open. You may want to share the page to find a replacement.
    </p>
    <div style="text-align:center;margin:2rem 0;">
        <a href="{base_url}/shiva/{html_mod.escape(support_id)}" style="display:inline-block;background:#D2691E;color:white;padding:0.7rem 2rem;border-radius:2rem;text-decoration:none;font-size:1rem;">View Meal Schedule</a>
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
                to_emails=To(org_email),
                subject=f'Meal cancellation — {vol_name} for {formatted_date}',
                plain_text_content=Content(MimeType.text, plain_text),
                html_content=Content(MimeType.html, html_content)
            )
            sg = SendGridAPIClient(sendgrid_key)
            sg.send(message)
            logging.info(f"[Cancel] Notification sent to {org_email}")
        except Exception:
            logging.exception("[Cancel] Notification email error")

    # ── API: V4 — Donation Prompt ────────────────────────────

    def handle_donation_prompt(self, support_id, body):
        """Record that a donation prompt was shown."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            email = data.get('email', '')
            trigger_type = data.get('trigger_type', 'shiva_thankyou')
            if not email:
                self.send_json_response({'status': 'error', 'message': 'Email required'}, 400)
                return
            result = shiva_mgr.record_donation_prompt(email, support_id, trigger_type)
            self.send_json_response(result, 200)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_donation(self, support_id, body):
        """Record a donation conversion."""
        if not SHIVA_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Not available'}, 503)
            return
        try:
            data = json.loads(body)
            email = data.get('email', '')
            if not email:
                self.send_json_response({'status': 'error', 'message': 'Email required'}, 400)
                return
            result = shiva_mgr.record_donation(email, support_id)
            self.send_json_response(result, 200)
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

    # ── Yahrzeit Handlers ─────────────────────────────────────

    def handle_yahrzeit_subscribe(self, body):
        """Handle yahrzeit reminder subscription"""
        if not YAHRZEIT_AVAILABLE:
            self.send_json_response({'status': 'error', 'message': 'Yahrzeit reminders not available'}, 503)
            return
        try:
            data = json.loads(body)

            # Rate limit
            client_ip = self._get_client_ip()
            if not _check_rate_limit(client_ip, 'yahrzeit_subscribe', max_calls=5, window=300):
                self._send_rate_limit_error()
                return

            result = yahrzeit_mgr.subscribe(data)

            if result['status'] == 'success':
                # Send confirmation email
                yahrzeit_mgr.send_confirmation_email(result)
                # Trigger backup
                if SHIVA_AVAILABLE:
                    shiva_mgr._trigger_backup()

            # Don't expose confirmation_token to client
            safe_result = dict(result)
            safe_result.pop('confirmation_token', None)
            safe_result.pop('email', None)

            status_code = 200 if result['status'] == 'success' else 400
            self.send_json_response(safe_result, status_code)
        except json.JSONDecodeError:
            self.send_json_response({'status': 'error', 'message': 'Invalid JSON'}, 400)
        except Exception as e:
            self.send_error_response(str(e))

    def handle_yahrzeit_confirm(self, token):
        """Handle yahrzeit confirmation link click"""
        if not YAHRZEIT_AVAILABLE:
            self.send_error_response('Yahrzeit reminders not available', 503)
            return
        try:
            result = yahrzeit_mgr.confirm(token)

            # Serve a simple confirmation page (HTML-escape user data)
            if result['status'] in ('success', 'already_confirmed'):
                deceased = html_mod.escape(result.get('deceased_name', 'your loved one'))
                hebrew = html_mod.escape(result.get('hebrew_date', '') or '')
                hebrew_line = f'<p style="color:#6b7c6e; font-size:0.95rem;">Hebrew date: <strong>{hebrew}</strong></p>' if hebrew else ''
                message = html_mod.escape(result.get('message', 'Your yahrzeit reminder is now active.'))
                html = self._yahrzeit_result_page('Reminder Confirmed', message, hebrew_line)
            else:
                message = result.get('message', 'Invalid confirmation link.')
                html = self._yahrzeit_result_page('Unable to Confirm', message, '', is_error=True)

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            self.send_error_response(str(e))

    def handle_yahrzeit_unsubscribe(self, token):
        """Handle yahrzeit unsubscribe link click"""
        if not YAHRZEIT_AVAILABLE:
            self.send_error_response('Yahrzeit reminders not available', 503)
            return
        try:
            result = yahrzeit_mgr.unsubscribe(token)

            if result['status'] in ('success', 'already_unsubscribed'):
                message = html_mod.escape(result.get('message', 'You have been unsubscribed.'))
                html = self._yahrzeit_result_page('Unsubscribed', message, '')
            else:
                message = html_mod.escape(result.get('message', 'Invalid unsubscribe link.'))
                html = self._yahrzeit_result_page('Unable to Unsubscribe', message, '', is_error=True)

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            self.send_error_response(str(e))

    def _yahrzeit_result_page(self, title, message, extra_html='', is_error=False):
        """Generate a simple result page for yahrzeit confirm/unsubscribe."""
        color = '#b71c1c' if is_error else 'var(--dark-brown, #3E2723)'
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Neshama</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Source Serif 4', serif; background: linear-gradient(135deg, #FAF9F6, #F5F5DC); color: #3E2723; line-height: 1.7; min-height: 100vh; margin: 0; }}
        .top-nav {{ display: flex; align-items: center; padding: 0 2rem; height: 56px; background: rgba(255,255,255,0.96); border-bottom: 1px solid rgba(212,197,185,0.3); }}
        .nav-logo {{ font-family: 'Cormorant Garamond', serif; font-size: 1.5rem; font-weight: 500; color: #3E2723; text-decoration: none; }}
        .container {{ max-width: 560px; margin: 3rem auto; padding: 3rem 2rem; text-align: center; }}
        h1 {{ font-family: 'Cormorant Garamond', serif; font-size: clamp(1.8rem, 4vw, 2.2rem); font-weight: 400; margin-bottom: 1rem; color: {color}; }}
        p {{ font-size: 1.05rem; margin-bottom: 0.75rem; }}
        .back-link {{ display: inline-block; margin-top: 1.5rem; color: #D2691E; text-decoration: none; font-size: 1rem; }}
    </style>
</head>
<body>
    <nav class="top-nav"><a href="/" class="nav-logo">Neshama</a></nav>
    <div class="container">
        <h1>{title}</h1>
        <p>{message}</p>
        {extra_html}
        <a href="/" class="back-link">Return to Neshama &rarr;</a>
    </div>
</body>
</html>'''

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
        """GET /api/health — comprehensive service health check.
        Returns status of every subsystem so smoke tests can verify nothing broke."""
        checks = {}
        all_ok = True

        # 1. Database connection + table counts
        try:
            db_path = self.get_db_path()
            conn = _connect_db(db_path)
            cursor = conn.cursor()

            for table, min_expected in [('obituaries', 50), ('vendors', 80), ('subscribers', 0)]:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    checks[table] = {'ok': True, 'count': count}
                    if count < min_expected:
                        checks[table]['warning'] = f'Expected {min_expected}+, got {count}'
                except Exception as e:
                    checks[table] = {'ok': False, 'error': str(e)}
                    all_ok = False

            # Test DB is writable + diagnostics
            journal_mode = 'unknown'
            wal_exists = os.path.exists(db_path + '-wal')
            shm_exists = os.path.exists(db_path + '-shm')
            subprocess_write = 'not_tested'
            try:
                journal_mode = cursor.execute('PRAGMA journal_mode').fetchone()[0]
                conn.close()  # Close read connection first

                # Test write with autocommit connection (isolation_level=None)
                # This bypasses Python's implicit transaction management
                test_conn = sqlite3.connect(db_path, timeout=5, isolation_level=None)
                test_conn.execute('PRAGMA busy_timeout=5000')
                test_conn.execute("INSERT INTO scraper_log (source, run_time, status) VALUES ('health_check', datetime('now'), 'test')")
                test_conn.close()
                checks['db_writable'] = {'ok': True, 'journal_mode': journal_mode}
            except Exception as e:
                # Try subprocess write as diagnostic (use 'python' not 'python3' for Render)
                try:
                    result = subprocess.run(
                        ['python', '-c',
                         f"import sqlite3; c=sqlite3.connect('{db_path}',timeout=5,isolation_level=None); c.execute('PRAGMA busy_timeout=5000'); c.execute(\"INSERT INTO scraper_log (source,run_time,status) VALUES ('subprocess_test',datetime('now'),'ok')\"); c.close(); print('WRITE_OK')"],
                        capture_output=True, text=True, timeout=15
                    )
                    subprocess_write = (result.stdout.strip() + ' ' + result.stderr.strip())[:500]
                except Exception as se:
                    subprocess_write = str(se)[:200]

                # Check if disk itself is writable
                disk_writable = False
                try:
                    test_file = db_path + '.writetest'
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    disk_writable = True
                except Exception:
                    disk_writable = False

                # Count open file descriptors to DB (shows leaked connections)
                open_fds = 0
                fd_details = []
                try:
                    import glob as _glob
                    pid = os.getpid()
                    for fd_path in sorted(_glob.glob(f'/proc/{pid}/fd/*')):
                        try:
                            target = os.readlink(fd_path)
                            if db_path in target or 'neshama' in target:
                                fd_num = os.path.basename(fd_path)
                                open_fds += 1
                                fd_details.append(f'fd{fd_num}={os.path.basename(target)}')
                        except Exception:
                            pass
                except Exception:
                    open_fds = -1  # /proc not available

                # Check file permissions
                import stat
                db_stat = {}
                try:
                    s = os.stat(db_path)
                    db_stat = {
                        'mode': oct(s.st_mode),
                        'size': s.st_size,
                        'uid': s.st_uid,
                        'writable': os.access(db_path, os.W_OK),
                    }
                except Exception as se:
                    db_stat = {'error': str(se)}

                checks['db_writable'] = {
                    'ok': False,
                    'error': str(e),
                    'journal_mode': journal_mode,
                    'wal_file': wal_exists,
                    'shm_file': shm_exists,
                    'disk_writable': disk_writable,
                    'db_file': db_stat,
                    'open_fds_to_db': open_fds,
                    'fd_details': fd_details[:10],
                    'subprocess_write': subprocess_write,
                }
                all_ok = False

            # Re-open connection for remaining checks
            conn = _connect_db(db_path)
            cursor = conn.cursor()

            # Scraper freshness — check both DB timestamps AND scraper thread heartbeat
            # The scraper may be running fine but find no new obituaries (common evenings/overnight)
            # So: if scraper thread heartbeat is recent (<40 min), data freshness is informational only
            # Grace periods: don't flag stale during Shabbat or within 5 min of startup
            try:
                cursor.execute('SELECT source, MAX(scraped_at) as latest FROM obituaries GROUP BY source')
                three_hours_ago = (datetime.now(tz=_tz.utc) - timedelta(hours=3)).isoformat()
                shabbat_now = is_shabbat()
                startup_grace = (datetime.now(tz=_tz.utc) - _SERVER_START_TIME).total_seconds() < 300
                scraper_status = {}
                for row in cursor.fetchall():
                    source = row[0]
                    latest = row[1]
                    is_fresh = latest and latest >= three_hours_ago
                    scraper_status[source] = {'latest': latest, 'fresh': is_fresh}

                # If scraper thread has a recent heartbeat, it's running — stale data just means
                # no new obituaries were posted, which is normal. Don't fail health check for this.
                scraper_heartbeat = _periodic_scraper_status.get('last_heartbeat')
                scraper_thread_active = False
                if scraper_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(scraper_heartbeat)
                        minutes_since_hb = (datetime.now(tz=_tz.utc) - hb_time).total_seconds() / 60
                        scraper_thread_active = minutes_since_hb < 40
                    except Exception:
                        pass

                if shabbat_now:
                    checks['scraper_freshness'] = {'ok': True, 'shabbat': True, 'sources': scraper_status}
                elif startup_grace:
                    checks['scraper_freshness'] = {'ok': True, 'startup_grace': True, 'sources': scraper_status}
                elif scraper_thread_active:
                    # Thread is running — stale data is informational, not a failure
                    checks['scraper_freshness'] = {
                        'ok': True,
                        'thread_active': True,
                        'note': 'Scraper running but no new obituaries found recently',
                        'sources': scraper_status
                    }
                else:
                    # Thread is dead AND data is stale — real problem
                    stale_sources = [s for s, v in scraper_status.items() if not v['fresh']]
                    if stale_sources:
                        all_ok = False
                    checks['scraper_freshness'] = {'ok': not stale_sources, 'sources': scraper_status}
            except Exception as e:
                checks['scraper_freshness'] = {'ok': False, 'error': str(e)}

            conn.close()
        except Exception as e:
            checks['database'] = {'ok': False, 'error': str(e)}
            all_ok = False

        # Scraper thread watchdog — if last heartbeat > 40min, mark unhealthy
        try:
            last_hb = _periodic_scraper_status.get('last_heartbeat')
            if last_hb:
                hb_time = datetime.fromisoformat(last_hb).replace(tzinfo=_tz.utc)
                minutes_since = (datetime.now(tz=_tz.utc) - hb_time).total_seconds() / 60
                scraper_thread_ok = minutes_since < 40 or is_shabbat()
            else:
                # No heartbeat yet — server just started, give grace period
                scraper_thread_ok = True
            checks['scraper_thread'] = {
                'ok': scraper_thread_ok,
                'last_heartbeat': last_hb,
                'cycle_count': _periodic_scraper_status.get('cycle_count', 0),
                'consecutive_failures': _periodic_scraper_status.get('consecutive_failures', 0),
            }
            if not scraper_thread_ok:
                all_ok = False
        except Exception as e:
            checks['scraper_thread'] = {'ok': False, 'error': str(e)}
            all_ok = False

        # 2. Email subsystem (optional — doesn't fail health check)
        checks['email'] = {
            'ok': EMAIL_AVAILABLE,
            'sendgrid_connected': EMAIL_AVAILABLE and subscription_mgr and bool(subscription_mgr.sendgrid_api_key),
            'critical': False
        }

        # 2b. Daily digest last run status
        checks['daily_digest'] = {
            'last_ran_at': _last_digest_run.get('ran_at'),
            'result': _last_digest_run.get('result'),
            'error': _last_digest_run.get('error'),
        }

        # 3. Shiva subsystem (optional — doesn't fail health check)
        checks['shiva'] = {'ok': SHIVA_AVAILABLE, 'critical': False}

        # 4. Yahrzeit subsystem (optional)
        checks['yahrzeit'] = {'ok': YAHRZEIT_AVAILABLE, 'critical': False}

        # 5. Stripe subsystem (optional)
        checks['stripe'] = {'ok': STRIPE_AVAILABLE, 'critical': False}

        # 6. Vendors subsystem (optional)
        checks['vendor_directory'] = {'ok': VENDORS_AVAILABLE, 'critical': False}

        # 7. Static files spot check
        critical_pages = ['/', '/feed', '/directory', '/gifts', '/shiva/organize',
                          '/how-to-sit-shiva', '/what-is-yahrzeit', '/kosher-shiva-food', '/shiva-preparation-checklist',
                          '/yahrzeit', '/find-my-page', '/dashboard']
        missing = []
        for page in critical_pages:
            if page == '/':
                fname = 'index.html'
            elif page in self.STATIC_FILES:
                fname = self.STATIC_FILES[page][0]
            else:
                continue
            if not os.path.exists(os.path.join(FRONTEND_DIR, fname)):
                missing.append(page)
        checks['static_files'] = {'ok': len(missing) == 0}
        if missing:
            checks['static_files']['missing'] = missing
            all_ok = False

        # 8. Disk usage check (/data/ partition)
        try:
            import shutil as _shutil
            data_dir = os.path.dirname(os.path.abspath(DB_PATH))
            disk = _shutil.disk_usage(data_dir)
            disk_usage_pct = round((disk.used / disk.total) * 100, 1)
            disk_free_mb = round(disk.free / (1024 * 1024), 1)
            checks['disk'] = {
                'ok': disk_usage_pct < 80,
                'disk_usage_percent': disk_usage_pct,
                'disk_free_mb': disk_free_mb,
            }
            if disk_usage_pct >= 80:
                logging.warning(f"[Health] Disk usage is {disk_usage_pct}% — only {disk_free_mb} MB free")
                all_ok = False
        except Exception as e:
            checks['disk'] = {'ok': True, 'error': str(e), 'note': 'Could not check disk usage'}

        status_code = 200 if all_ok else 503
        self.send_json_response({
            'status': 'ok' if all_ok else 'degraded',
            'checks': checks
        }, status_code)

    def _check_admin_auth(self):
        """Check admin authentication via Authorization header, X-Admin-Key header, or ?key= query param.
        Returns True if authorized, False if not (and sends 403 response).
        ALWAYS requires ADMIN_SECRET to be set — never allows unauthenticated access."""
        admin_secret = os.environ.get('ADMIN_SECRET', '')
        if not admin_secret:
            self.send_json_response({'status': 'error', 'message': 'Admin not configured'}, 403)
            return False
        # Check headers first, fall back to query param
        token = ''
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        elif self.headers.get('X-Admin-Key', ''):
            token = self.headers.get('X-Admin-Key', '')
        else:
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            token = query_params.get('key', [''])[0]
        if not hmac.compare_digest(str(token), str(admin_secret)):
            self.send_error_response('Unauthorized', 403)
            return False
        return True

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
                conn = _connect_db(db_path_to_check)
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


def _run_health_watchdog():
    """Check system health after each scraper run.
    Logs warnings for: stale data, DB lock, low obituary counts, SendGrid issues.
    Sends alert email to contact@neshama.ca if critical issues detected."""
    issues = []
    try:
        conn = _connect_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check 1: Database writable
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS _health_check (ts TEXT)")
            cursor.execute("INSERT INTO _health_check VALUES (?)", (datetime.now(tz=_tz.utc).isoformat(),))
            conn.commit()
            cursor.execute("DELETE FROM _health_check")
            conn.commit()
        except Exception as e:
            issues.append(f"DB WRITE FAILED: {e}")

        # Check 2: Scraper freshness — only alert if scraper thread is ALSO dead
        # Stale data + active thread = no new obituaries posted (normal evenings/overnight)
        # Stale data + dead thread = real problem
        try:
            scraper_heartbeat = _periodic_scraper_status.get('last_heartbeat')
            scraper_thread_active = False
            if scraper_heartbeat:
                try:
                    hb_time = datetime.fromisoformat(scraper_heartbeat)
                    minutes_since_hb = (datetime.now(tz=_tz.utc) - hb_time).total_seconds() / 60
                    scraper_thread_active = minutes_since_hb < 40
                except Exception:
                    pass

            cursor.execute('''
                SELECT source, MAX(scraped_at) as latest
                FROM obituaries GROUP BY source
            ''')
            six_hours_ago = (datetime.now(tz=_tz.utc) - timedelta(hours=6)).isoformat()
            for row in cursor.fetchall():
                if row['latest'] and row['latest'] < six_hours_ago:
                    hours_stale = round((datetime.now(tz=_tz.utc) - datetime.fromisoformat(row['latest']).replace(tzinfo=_tz.utc)).total_seconds() / 3600, 1)
                    if scraper_thread_active:
                        logging.info(f"[Watchdog] {row['source']} data is {hours_stale}h old but scraper thread is active — no new obituaries posted")
                    else:
                        issues.append(f"STALE DATA: {row['source']} — last scraped {hours_stale}h ago (scraper thread not responding)")
        except Exception as e:
            issues.append(f"Freshness check failed: {e}")

        # Check 3: Subscriber count
        try:
            cursor.execute("SELECT COUNT(*) as total, COUNT(CASE WHEN confirmed THEN 1 END) as confirmed FROM subscribers")
            row = cursor.fetchone()
            if row:
                logging.info(f"[Watchdog] Subscribers: {row['total']} total, {row['confirmed']} confirmed")
        except Exception:
            pass

        # Check 4: SendGrid API key present
        if not os.environ.get('SENDGRID_API_KEY'):
            issues.append("SENDGRID_API_KEY not set — digest emails running in TEST MODE")

        conn.close()

    except Exception as e:
        issues.append(f"Watchdog DB connection failed: {e}")

    if issues:
        for issue in issues:
            logging.error(f"[Watchdog] {issue}")
        # Try to send alert email
        _send_health_alert(issues)
    else:
        logging.info("[Watchdog] All systems healthy")


def _send_health_alert(issues):
    """Send health alert email to contact@neshama.ca via SendGrid"""
    sg_key = os.environ.get('SENDGRID_API_KEY')
    if not sg_key:
        logging.error("[Watchdog] Cannot send alert — no SendGrid key")
        return
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        issue_list = '\n'.join(f'- {i}' for i in issues)
        msg = Mail(
            from_email='updates@neshama.ca',
            to_emails='contact@neshama.ca',
            subject=f'[Neshama Alert] {len(issues)} system issue(s) detected',
            plain_text_content=f'Health watchdog found issues at {datetime.now(tz=_tz.utc).isoformat()}:\n\n{issue_list}\n\nCheck Render logs for details.'
        )
        sg = SendGridAPIClient(sg_key)
        sg.send(msg)
        logging.info(f"[Watchdog] Alert email sent to contact@neshama.ca")
    except Exception as e:
        logging.error(f"[Watchdog] Failed to send alert: {e}")


# Track consecutive scraper failures to avoid alert spam
_scraper_fail_count = 0

def periodic_scraper():
    """Run scrapers every SCRAPE_INTERVAL seconds in background thread.
    Keeps obituary data fresh between server restarts.
    Pauses during Shabbat (Friday evening – Saturday night).
    Runs health watchdog after each cycle."""
    global _scraper_fail_count, _periodic_scraper_status
    import time as _time
    project_root = os.path.join(FRONTEND_DIR, '..')
    _periodic_scraper_status['alive'] = True
    # Run first cycle after a short delay (60s) to let the server finish starting,
    # then use full SCRAPE_INTERVAL for subsequent cycles.
    _time.sleep(60)
    while True:
        _periodic_scraper_status['last_heartbeat'] = datetime.now(tz=_tz.utc).isoformat()
        if is_shabbat():
            logging.info(f"[Scraper] Shabbat — scraping paused")
            _time.sleep(SCRAPE_INTERVAL)
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
            _periodic_scraper_status['cycle_count'] += 1
            _periodic_scraper_status['last_stdout'] = (result.stdout or '')[-500:]
            _periodic_scraper_status['last_stderr'] = (result.stderr or '')[-500:]
            if result.returncode == 0:
                logging.info(f"[Scraper] Periodic scrape completed successfully")
                _scraper_fail_count = 0
                _periodic_scraper_status['consecutive_failures'] = 0
            else:
                _scraper_fail_count += 1
                _periodic_scraper_status['consecutive_failures'] += 1
                logging.warning(f"[Scraper] Scrape had issues (fail #{_scraper_fail_count}): {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            _scraper_fail_count += 1
            _periodic_scraper_status['consecutive_failures'] += 1
            _periodic_scraper_status['last_stderr'] = 'TIMEOUT after 300s'
            logging.warning(f"[Scraper] Periodic scrape timed out after 300s (fail #{_scraper_fail_count})")
        except Exception as e:
            _scraper_fail_count += 1
            _periodic_scraper_status['consecutive_failures'] += 1
            _periodic_scraper_status['last_stderr'] = str(e)
            logging.error(f"[Scraper] Periodic scrape error (fail #{_scraper_fail_count}): {e}")

        # Run health watchdog every 6th cycle (~2 hours) or on failures
        cycle_count = getattr(periodic_scraper, '_cycle', 0) + 1
        periodic_scraper._cycle = cycle_count
        if cycle_count % 6 == 0 or _scraper_fail_count >= 3:
            _run_health_watchdog()

        _time.sleep(SCRAPE_INTERVAL)


def run_server(port=None):
    """Start the API server"""
    if port is None:
        port = int(os.environ.get('PORT', 5000))

    # Initialize core database tables (obituaries, comments, scraper_log, tributes, referrals).
    # These were previously created by database_setup.py in the build step, but Render's
    # persistent disk at /data/ isn't available during builds — only at runtime.
    try:
        from database_setup import initialize_database
        initialize_database()
    except Exception as e:
        logging.warning(f"[Startup] database_setup: {e}")

    # Recovery: clear stale SQLite locks from crashed processes.
    # On Render persistent disk, filesystem-level locks survive restarts.
    # Nuclear fix: copy DB to break all lock associations, then replace original.
    import shutil
    db_backup = DB_PATH + '.recovery'
    try:
        # Quick write test first (autocommit to avoid Python's implicit transactions)
        test_conn = sqlite3.connect(DB_PATH, timeout=3, isolation_level=None)
        test_conn.execute('PRAGMA busy_timeout=3000')
        test_conn.execute("INSERT INTO scraper_log (source, run_time, status) VALUES ('startup_test', datetime('now'), 'ok')")
        test_conn.close()
        logging.info("[Startup] DB write test PASSED — no lock recovery needed")
    except Exception as write_err:
        logging.warning(f"[Startup] DB write test FAILED ({write_err}) — attempting lock recovery")
        try:
            try:
                test_conn.close()
            except Exception:
                pass

            # Remove stale WAL/SHM files
            for suffix in ['-wal', '-shm']:
                lock_file = DB_PATH + suffix
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        logging.info(f"[Startup] Removed {lock_file}")
                    except Exception as e:
                        logging.warning(f"[Startup] Could not remove {lock_file}: {e}")

            # Copy DB to new file (breaks all filesystem locks)
            shutil.copy2(DB_PATH, db_backup)
            os.remove(DB_PATH)
            shutil.move(db_backup, DB_PATH)
            logging.info("[Startup] DB copied to break filesystem locks")

            # Verify write works on the fresh copy (autocommit)
            verify_conn = sqlite3.connect(DB_PATH, timeout=5, isolation_level=None)
            verify_conn.execute('PRAGMA busy_timeout=30000')
            verify_conn.execute("INSERT INTO scraper_log (source, run_time, status) VALUES ('lock_recovery', datetime('now'), 'ok')")
            verify_conn.close()
            logging.info("[Startup] DB lock recovery: write test PASSED after copy")
        except Exception as recovery_err:
            logging.error(f"[Startup] DB lock recovery FAILED: {recovery_err}")
            # Clean up backup if it exists
            if os.path.exists(db_backup):
                try:
                    os.remove(db_backup)
                except Exception:
                    pass

    # REMOVED: Auto-confirm stale subscribers — violates CASL double opt-in.
    # If confirmation emails go to spam, fix deliverability (SPF/DKIM/DMARC)
    # instead of bypassing consent. Use /admin/confirm-subscriber for manual cases.

    # Force WAL mode after all lock recovery is complete.
    # WAL prevents readers from blocking writers under concurrent access.
    # This must run on every startup because DELETE mode or lock recovery can revert it.
    ensure_wal_mode(DB_PATH)

    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, NeshamaAPIHandler)

    # Launch auto-scrape in background thread (non-blocking)
    scrape_thread = threading.Thread(target=auto_scrape_on_startup, daemon=True)
    scrape_thread.start()

    # Launch periodic scraper (every 20 min by default)
    periodic_thread = threading.Thread(target=periodic_scraper, daemon=True)
    periodic_thread.start()
    logging.info(f"[Scraper] Periodic scraper started (every {SCRAPE_INTERVAL // 60} minutes)")

    # Launch APScheduler for all background jobs (email queue, digests, yahrzeit, reports)
    # Scheduler must start even if email_queue import fails — digests don't depend on it
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(daemon=True)

        # Email queue processor (every 15 min) — only if available
        if EMAIL_QUEUE_AVAILABLE:
            scheduler.add_job(
                process_email_queue,
                'interval',
                minutes=15,
                args=[DB_PATH],
                id='email_queue',
                name='Process shiva email queue',
                max_instances=1,
            )
        else:
            logging.info("[Scheduler] Email queue not available — skipping email queue job")

        # Add yahrzeit daily processor (9 AM Toronto time)
        if YAHRZEIT_AVAILABLE:
            try:
                from yahrzeit_processor import process_yahrzeit_reminders
                scheduler.add_job(
                    process_yahrzeit_reminders,
                    'cron',
                    hour=9,
                    minute=0,
                    timezone='America/Toronto',
                    args=[DB_PATH],
                    id='yahrzeit_reminders',
                    name='Process yahrzeit reminders',
                    max_instances=1,
                )
                logging.info(f"[Yahrzeit] Scheduler added (daily at 9 AM Toronto)")
            except Exception as e:
                logging.error(f"[Yahrzeit] Failed to add scheduler job: {e}")

        # Add daily digest (7 AM ET, Sun-Fri, skip Shabbat)
        try:
            from daily_digest import DailyDigestSender

            def _save_digest_run(ran_at, result, error):
                """Persist digest run to DB for history across restarts."""
                try:
                    import json
                    dconn = sqlite3.connect(DB_PATH, timeout=30)
                    dc = dconn.cursor()
                    dc.execute('''CREATE TABLE IF NOT EXISTS digest_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ran_at TEXT NOT NULL,
                        result TEXT,
                        error TEXT
                    )''')
                    dc.execute('INSERT INTO digest_runs (ran_at, result, error) VALUES (?, ?, ?)',
                               (ran_at, json.dumps(result) if result else None, error))
                    # Keep only last 30 runs
                    dc.execute('DELETE FROM digest_runs WHERE id NOT IN (SELECT id FROM digest_runs ORDER BY id DESC LIMIT 30)')
                    dconn.commit()
                    dconn.close()
                except Exception as e:
                    logging.error(f"[DailyDigest] Failed to save run to DB: {e}")

            def _run_daily_digest():
                global _last_digest_run
                ran_at = datetime.now(tz=_tz.utc).isoformat()
                _last_digest_run['ran_at'] = ran_at
                _last_digest_run['error'] = None
                _last_digest_run['result'] = None

                if is_shabbat():
                    logging.info("[DailyDigest] Shabbat — skipping digest")
                    _last_digest_run['result'] = 'skipped_shabbat'
                    _save_digest_run(ran_at, 'skipped_shabbat', None)
                    return
                try:
                    sg_key = os.environ.get('SENDGRID_API_KEY')
                    if not sg_key:
                        logging.error("[DailyDigest] SENDGRID_API_KEY not set — digest will run in TEST MODE (no emails sent)")
                    sender = DailyDigestSender(db_path=DB_PATH, sendgrid_api_key=sg_key)
                    result = sender.send_daily_digest()
                    _last_digest_run['result'] = result
                    _save_digest_run(ran_at, result, None)
                    logging.info(f"[DailyDigest] Completed: {result}")
                except Exception as e:
                    _last_digest_run['error'] = str(e)
                    _save_digest_run(ran_at, None, str(e))
                    logging.error(f"[DailyDigest] Error: {e}", exc_info=True)
            scheduler.add_job(
                _run_daily_digest,
                'cron',
                hour=7,
                minute=0,
                day_of_week='mon-fri,sun',
                timezone='America/Toronto',
                id='daily_digest',
                name='Send daily obituary digest',
                max_instances=1,
            )
            logging.info(f"[DailyDigest] Scheduler added (daily at 7 AM ET, Sun-Fri)")

            # Missed digest recovery: use a thread instead of APScheduler date trigger
            # (APScheduler date jobs can miss if run_date passes before scheduler.start())
            def _check_missed_digest():
                """Run 2 min after startup — if today's digest was missed, send it now."""
                import time
                time.sleep(120)  # Wait 2 min for server to fully stabilize
                logging.info("[DailyDigest] Recovery check starting...")
                try:
                    if is_shabbat():
                        logging.info("[DailyDigest] Recovery: Shabbat, skipping")
                        return
                    tz = pytz.timezone('America/Toronto')
                    now = datetime.now(tz)
                    # Only recover if it's after 7 AM and before 10 PM
                    if now.hour < 7 or now.hour >= 22:
                        logging.info(f"[DailyDigest] Recovery: outside window (hour={now.hour}), skipping")
                        return
                    # Check if digest already ran today
                    today_str = now.strftime('%Y-%m-%d')
                    try:
                        dconn = sqlite3.connect(DB_PATH, timeout=10)
                        dc = dconn.cursor()
                        dc.execute('SELECT ran_at, result FROM digest_runs ORDER BY id DESC LIMIT 1')
                        row = dc.fetchone()
                        dconn.close()
                        if row and row[0] and today_str in row[0]:
                            logging.info(f"[DailyDigest] Recovery: already ran today at {row[0]}")
                            return
                    except Exception as db_err:
                        logging.info(f"[DailyDigest] Recovery: no digest_runs table yet ({db_err}), proceeding")

                    logging.info(f"[DailyDigest] Recovery: missed today's digest, sending now")
                    _run_daily_digest()
                except Exception as e:
                    logging.error(f"[DailyDigest] Recovery check error: {e}", exc_info=True)

            recovery_thread = threading.Thread(target=_check_missed_digest, daemon=True, name='digest-recovery')
            recovery_thread.start()
            logging.info("[DailyDigest] Recovery thread started (will check in 2 min)")
        except Exception as e:
            logging.error(f"[DailyDigest] Failed to add scheduler job: {e}")

        # Add weekly digest (Sunday 9 AM ET)
        try:
            from weekly_digest import WeeklyDigestSender
            def _run_weekly_digest():
                try:
                    sg_key = os.environ.get('SENDGRID_API_KEY')
                    if not sg_key:
                        logging.error("[WeeklyDigest] SENDGRID_API_KEY not set — running in TEST MODE")
                    sender = WeeklyDigestSender(db_path=DB_PATH, sendgrid_api_key=sg_key)
                    sender.send_weekly_digest()
                except Exception as e:
                    logging.error(f"[WeeklyDigest] Error: {e}")
            scheduler.add_job(
                _run_weekly_digest,
                'cron',
                hour=9,
                minute=0,
                day_of_week='sun',
                timezone='America/Toronto',
                id='weekly_digest',
                name='Send weekly obituary digest',
                max_instances=1,
            )
            logging.info(f"[WeeklyDigest] Scheduler added (Sunday at 9 AM ET)")
        except Exception as e:
            logging.error(f"[WeeklyDigest] Failed to add scheduler job: {e}")

        # Add monthly vendor report (1st of month, 9 AM ET)
        try:
            from vendor_report import run_monthly_reports
            def _run_vendor_report():
                try:
                    run_monthly_reports(db_path=DB_PATH)
                except Exception as e:
                    logging.error(f"[VendorReport] Error: {e}")
            scheduler.add_job(
                _run_vendor_report,
                'cron',
                day=1,
                hour=9,
                minute=0,
                timezone='America/Toronto',
                id='vendor_report',
                name='Send monthly vendor reports',
                max_instances=1,
            )
            logging.info(f"[VendorReport] Scheduler added (1st of month at 9 AM ET)")
        except Exception as e:
            logging.error(f"[VendorReport] Failed to add scheduler job: {e}")

        # Add weekly offsite backup (Sunday 3 AM ET — emails backup JSON)
        try:
            def _run_offsite_backup():
                try:
                    sendgrid_key = os.environ.get('SENDGRID_API_KEY')
                    admin_email = os.environ.get('ADMIN_EMAIL', 'contact@neshama.ca')
                    if not sendgrid_key:
                        logging.info("[OffsiteBackup] No SendGrid key — skipping email backup")
                        return
                    if not SHIVA_AVAILABLE:
                        logging.error("[OffsiteBackup] Shiva manager unavailable — cannot backup")
                        return

                    import base64 as b64
                    backup_data = shiva_mgr.get_backup_data()
                    backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
                    row_count = sum(len(rows) for rows in backup_data.get('tables', {}).values())
                    table_count = len([t for t in backup_data.get('tables', {}) if backup_data['tables'][t]])
                    timestamp = datetime.now().strftime('%Y-%m-%d')
                    filename = f"neshama-backup-{timestamp}.json"

                    # Build summary for email body
                    table_summary = ""
                    for tname, rows in backup_data.get('tables', {}).items():
                        if rows:
                            table_summary += f"<li>{tname}: {len(rows)} rows</li>"

                    html_body = f"""
<div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:2rem;color:#3E2723;">
    <h2 style="font-size:1.4rem;font-weight:400;margin-bottom:1rem;">Weekly Database Backup</h2>
    <p style="font-size:1rem;color:#555;">Automated backup from <strong>neshama.ca</strong></p>
    <div style="background:#FAF9F6;border:2px solid #D4C5B9;border-radius:12px;padding:1.25rem;margin:1rem 0;">
        <p style="margin:0 0 0.5rem;font-weight:600;">Backup Summary</p>
        <p style="margin:0;font-size:0.95rem;">Date: {timestamp}</p>
        <p style="margin:0;font-size:0.95rem;">Tables: {table_count}</p>
        <p style="margin:0;font-size:0.95rem;">Total rows: {row_count}</p>
        <ul style="margin:0.75rem 0 0;padding-left:1.25rem;font-size:0.9rem;color:#555;">
            {table_summary}
        </ul>
    </div>
    <p style="font-size:0.9rem;color:#8a9a8d;">The full backup JSON is attached. Save this email or download the attachment to Google Drive.</p>
</div>"""

                    encoded_attachment = b64.b64encode(backup_json.encode('utf-8')).decode('utf-8')
                    sg_data = {
                        "personalizations": [{"to": [{"email": admin_email}]}],
                        "from": {"email": "reminders@neshama.ca", "name": "Neshama Backup"},
                        "subject": f"Neshama Weekly Backup — {timestamp} ({row_count} rows)",
                        "content": [{"type": "text/html", "value": html_body}],
                        "attachments": [{
                            "content": encoded_attachment,
                            "type": "application/json",
                            "filename": filename,
                            "disposition": "attachment",
                        }]
                    }

                    req = urllib.request.Request(
                        'https://api.sendgrid.com/v3/mail/send',
                        data=json.dumps(sg_data).encode('utf-8'),
                        headers={
                            'Authorization': f'Bearer {sendgrid_key}',
                            'Content-Type': 'application/json',
                        },
                        method='POST'
                    )
                    response = urllib.request.urlopen(req, timeout=30)
                    logging.info(f"[OffsiteBackup] Emailed backup to {admin_email} ({row_count} rows, {len(backup_json)} bytes)")
                except Exception as e:
                    logging.error(f"[OffsiteBackup] Error: {e}")

            scheduler.add_job(
                _run_offsite_backup,
                'cron',
                hour=3,
                minute=0,
                day_of_week='sun',
                timezone='America/Toronto',
                id='offsite_backup',
                name='Email weekly backup',
                max_instances=1,
            )
            logging.info(f"[OffsiteBackup] Scheduler added (Sunday at 3 AM ET)")
        except Exception as e:
            logging.error(f"[OffsiteBackup] Failed to add scheduler job: {e}")

        scheduler.start()
        logging.info(f"[Scheduler] APScheduler started — all background jobs active")
    except Exception as e:
        logging.error(f"[Scheduler] APScheduler failed to start: {e}")
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
    logging.info(f" /sustain - Community sustainer page")
    logging.info(f" /sustain-success - Payment success")
    logging.info(f" /sustain-cancelled - Payment cancelled")
    logging.info(f" /shiva/organize - Set up shiva support")
    logging.info(f" /shiva/{{id}} - Community support page")
    logging.info(f" /find-my-page - Link recovery")
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
    logging.info(f" POST /api/find-my-page - Link recovery lookup")
    logging.info(f" GET /admin/backup - Download backup JSON (admin)")
    logging.info(f" POST /admin/restore - Upload backup JSON (admin)")
    logging.info(f"\n Email: {'SendGrid connected' if EMAIL_AVAILABLE and subscription_mgr.sendgrid_api_key else 'TEST MODE' if EMAIL_AVAILABLE else 'Not available'}")
    logging.info(f" Stripe: {'Connected' if STRIPE_AVAILABLE else 'Not configured (set STRIPE_SECRET_KEY)'}")
    logging.info(f" Shiva support: {'Available' if SHIVA_AVAILABLE else 'Not available'}")
    logging.info(f" Offsite backup: Sunday 3 AM ET (email)")

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
                'email': 'jem.salads@gmail.com',
                'phone': '(416) 886-1804',
                'website': 'https://www.jemsalads.com',
                'delivery_area': 'Toronto & GTA',
                'kosher_level': 'not_kosher',
                'has_delivery': True,
                'has_online_ordering': False,
                'price_range': '$$',
                'shiva_menu_description': 'Fresh, wholesome salad platters and prepared meals with generous portions. Great for lighter shiva meals. Platters for 10-50+ guests with flexible delivery timing.',
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

    # ── Run data migrations ──────────────────────────────────
    try:
        conn = _connect_db()
        cursor = conn.cursor()

        # Migration 2026-03-21: Add source column to vendors table
        # Tracks origin of vendor records (seed, migration, user, partner_app)
        # so migration code never deletes user-submitted vendors.
        try:
            cursor.execute("ALTER TABLE vendors ADD COLUMN source TEXT DEFAULT 'seed'")
            logging.info(" Migrations: added source column to vendors")
        except Exception:
            pass  # Column already exists

        # Migration 2026-02-28: Fix vendor miscategorizations
        vendor_updates = [
            ("UPDATE vendors SET category = 'Restaurants & Delis', featured = 0, "
             "description = 'Fresh, wholesome salad platters and prepared meals with generous portions. "
             "Great option for lighter shiva meals. Platters for 10-50+ guests with flexible delivery timing.' "
             "WHERE slug = 'jem-salads' AND category != 'Restaurants & Delis'"),
            "UPDATE vendors SET category = 'Caterers' WHERE slug = 'yummy-market' AND category != 'Caterers'",
            "UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'centre-street-deli' AND category != 'Restaurants & Delis'",
            "UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'schmaltz-appetizing' AND category != 'Restaurants & Delis'",
            "UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'snowdon-deli' AND category != 'Restaurants & Delis'",
            "UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'schwartzs-deli' AND category != 'Restaurants & Delis'",
            "UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'lesters-deli' AND category != 'Restaurants & Delis'",
            "UPDATE vendors SET category = 'Kosher Restaurants & Caterers' WHERE slug = 'wok--bowl' AND category != 'Kosher Restaurants & Caterers'",
            "UPDATE vendors SET category = 'Gift Baskets' WHERE slug = 'gifting-kosher-canada' AND category != 'Gift Baskets'",
            # Migration 2026-02-28b: Fix Bagel World false kosher certification + wrong address
            ("UPDATE vendors SET kosher_status = 'not_certified', address = '336 Wilson Ave, Toronto, ON', "
             "website = 'https://bagelworld.ca', "
             "description = 'Popular North York bagel shop since 1963, offering fresh bagels, cream cheese spreads, lox platters, and catering trays. Jewish-owned, kosher-style cooking but not formally certified.' "
             "WHERE slug = 'bagel-world' AND kosher_status != 'not_certified'"),
        ]
        total_changed = 0
        for sql in vendor_updates:
            cursor.execute(sql)
            total_changed += cursor.rowcount

        # Fix Jem Salads in caterer_partners table (false kosher certification)
        cursor.execute(
            "UPDATE caterer_partners SET kosher_level = 'not_kosher', "
            "shiva_menu_description = 'Fresh, wholesome salad platters and prepared meals with generous portions. "
            "Great for lighter shiva meals. Platters for 10-50+ guests with flexible delivery timing.' "
            "WHERE email = 'jem.salads@gmail.com' AND kosher_level != 'not_kosher'"
        )
        total_changed += cursor.rowcount

        # Migration 2026-03-04: Fix vendor kosher labels per Jordana feedback (SUPERSEDED by 2026-03-12 below)
        mar4_updates = [
            "UPDATE vendors SET kosher_status = '' WHERE name = 'What A Bagel' AND kosher_status = 'COR'",
            "UPDATE vendors SET kosher_status = '' WHERE name = 'Gryfe''s Bagel Bakery' AND kosher_status = 'COR'",
            "UPDATE vendors SET kosher_status = '' WHERE name = 'Kiva''s Bagels' AND kosher_status = 'COR'",
            "UPDATE vendors SET kosher_status = '' WHERE name = 'Sonny Langers Dairy & Vegetarian Caterers' AND kosher_status = 'COR'",
            "UPDATE vendors SET kosher_status = '' WHERE name = 'Me-Va-Me' AND kosher_status = 'COR'",
            # Remove nonexistent vendors
            # Pizza Pita re-added Mar 22, 2026 — DELETE removed
            "DELETE FROM vendors WHERE name = 'Shwarma Express' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Pita Box' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Migration 2026-03-05: Remove unverified vendors (no working website/instagram)
            "DELETE FROM vendors WHERE name = 'Butzi Gift Baskets' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Dani Gifts' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Gifts for Every Reason' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Baskets n'' Stuf' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Romi''s Bakery' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Kapara' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Olive Branch' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Noah''s Natural Foods' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Migration 2026-03-05: Remove vendors with dead URLs (DNS failure / connection refused / HTTP 500)
            "DELETE FROM vendors WHERE name = 'Chanoch Sushi' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'BSTRO Pret-a-Manger' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Eden Hall Kosher Caterer' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Chagall' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Migration 2026-03-05: Remove ghost entries (no website, no phone, no email, no Instagram)
            "DELETE FROM vendors WHERE name = 'A&T Fruit Market' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Becked Goods' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Bubbies Bagels' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Candy Catchers' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Chocolate Charm' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Dave Young Fruit Market' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'SugarMommy Chocolates' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Sweetsie''s Cookies' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Remove vendors with dead websites (403 - hosting expired/removed)
            "DELETE FROM vendors WHERE name = 'Bagel World' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Rotisserie Laurier' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Pizza Cafe' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Slice N Bites' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Le Plezl' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Move memorial candles from gifts to home/essentials category
            "UPDATE vendors SET vendor_type = 'food', category = 'Shiva Supplies' WHERE name = 'Ner Mitzvah 7-Day Shiva Memorial Candle'",
            "UPDATE vendors SET vendor_type = 'food', category = 'Shiva Supplies' WHERE name = '24-Hour Yahrzeit Memorial Candles (Multipack)'",
        ]
        for sql in mar4_updates:
            cursor.execute(sql)
            total_changed += cursor.rowcount

        # Migration 2026-03-09: Jordana vendor fixes round 2
        mar9_updates = [
            # Remove vendors that no longer exist or are not appropriate
            "DELETE FROM vendors WHERE name = 'Miami Grill' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Village Pizza Kosher' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Citrus Traiteur' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = '24-Hour Yahrzeit Memorial Candles (Multipack)' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Ner Mitzvah 7-Day Shiva Memorial Candle' AND (source IS NULL OR source = 'seed' OR source = '')",
            "DELETE FROM vendors WHERE name = 'Bubby''s New York Bagels' AND (source IS NULL OR source = 'seed' OR source = '')",
            # Rename Bubby's → Bubby's Bagels
            "UPDATE vendors SET name = 'Bubby''s Bagels' WHERE name = 'Bubby''s'",
            # Rename Il Paesano → Paisanos + add website
            "UPDATE vendors SET name = 'Paisanos', website = 'https://thepaisanos.ca' WHERE name = 'Il Paesano'",
            # Add websites to existing vendors
            "UPDATE vendors SET website = 'https://www.gryfes.ca' WHERE name = 'Gryfe''s Bagel Bakery' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://kivasbagels.ca' WHERE name = 'Kiva''s Bagels' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://www.daiterskitchen.ca' WHERE name = 'Daiter''s Kitchen' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://cafesheli.com' WHERE name = 'Cafe Sheli' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://maineventmauzone.shop' WHERE name = 'Main Event Catering' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://chenoys-deli.goto-where.com' WHERE name = 'Chenoy''s Deli' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://goldenchopstick.ca' WHERE name = 'Golden Chopsticks' AND (website IS NULL OR website = '')",
            "UPDATE vendors SET website = 'https://shalomindia.ca' WHERE name = 'Shalom India' AND (website IS NULL OR website = '')",
            # AB Cookies website is dead (DNS doesn't resolve) — clear it
            "UPDATE vendors SET website = '' WHERE slug = 'ab-cookies' AND website = 'https://abcookies.co'",
        ]
        for sql in mar9_updates:
            cursor.execute(sql)
            total_changed += cursor.rowcount

        # Add new vendors (Mar 9) — only if they don't already exist
        new_vendors_mar9 = [
            ("Pizza Cafe", "Kosher Restaurants & Caterers", "COR-certified kosher pizza restaurant. Pizza, pasta, and Italian favourites. Affordable catering options for shiva meals.", "Toronto, ON", "Toronto", "", "https://www.pizzacafe.ca", "COR", 1, "Toronto", "food"),
            ("Aroma Espresso Bar", "Restaurants & Delis", "Israeli-born cafe chain with multiple locations. Coffee, pastries, salads, sandwiches, and shakshuka. A warm, familiar option for lighter shiva meals.", "Multiple locations, Toronto, ON", "GTA", "", "https://www.aromaespressobar.ca", "not_certified", 1, "Toronto,North York", "food"),
            ("Chop Hop", "Kosher Restaurants & Caterers", "Restaurant offering fresh, flavourful meals. A great option for shiva catering and family-style meals.", "Toronto, ON", "Toronto", "", "https://www.chophop.com", "", 1, "Toronto", "food"),
        ]
        for v in new_vendors_mar9:
            cursor.execute("SELECT id FROM vendors WHERE name = ?", (v[0],))
            if not cursor.fetchone():
                import re as _re
                slug = _re.sub(r'-+', '-', _re.sub(r'[\s]+', '-', _re.sub(r'[^a-z0-9\s-]', '', v[0].lower().strip())))
                cursor.execute("""INSERT INTO vendors (name, slug, category, description, address, neighborhood, phone, website, kosher_status, delivery, delivery_area, vendor_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (v[0], slug, v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10]))
                total_changed += 1

        # Migration 2026-03-09b: Outscraper pipeline — 12 verified vendors
        outscraper_vendors = [
            ("Beyond Delish Kosher Food Catering", "Caterers",
             "COR-certified kosher caterer on Bathurst. Full-service catering from intimate gatherings to large events. Fresh ingredients, Lubavitch shechita available. A trusted choice for shiva meals and community events.",
             "5987 Bathurst St, North York, ON M2R 1Z3", "North York", "", "https://www.beyonddelish.ca", "COR", 1, "Toronto,North York,Thornhill/Vaughan", "food"),
            ("Apex Kosher Catering", "Caterers",
             "Kosher caterer in North York offering full-service catering for lifecycle events. Professional team, flexible menus, and reliable service for families who need it most.",
             "100 Elder St, North York, ON M3H 5G7", "North York", "", "https://www.apexkoshercatering.com", "COR", 1, "Toronto,North York,Thornhill/Vaughan", "food"),
            ("Mitzuyan Kosher Catering", "Caterers",
             "Toronto''s modern kosher catering company. Full-service catering with contemporary menus and professional execution. A fresh option for shiva meals and community gatherings.",
             "18 Reiner Rd, Toronto, ON M3H 2K9", "North York", "", "https://mitzuyankoshercatering.com", "COR", 1, "Toronto,North York", "food"),
            ("F + B Kosher Catering", "Caterers",
             "COR-certified kosher caterer on Dufferin. The caterer of choice at many top venues throughout the GTA. Professional service for weddings, bar/bat mitzvahs, and community events.",
             "5000 Dufferin St Unit P, North York, ON M3H 5T5", "North York", "", "https://fbkosher.com", "COR", 1, "Toronto,North York,GTA-wide", "food"),
            ("Menchens Glatt Kosher Catering", "Caterers",
             "Glatt kosher catering in North York. Gourmet menus for weddings, bar/bat mitzvahs, and milestone events. A long-standing name in Toronto''s kosher catering community.",
             "470 Glencairn Ave, North York, ON M5N 1V8", "North York", "", "http://menchens.ca", "COR", 1, "Toronto,North York,Thornhill/Vaughan,GTA-wide", "food"),
            ("Noah Kosher Sushi", "Kosher Restaurants & Caterers",
             "COR-certified kosher sushi in the Bathurst corridor. A unique and crowd-pleasing option for shiva meals — sushi platters that everyone appreciates.",
             "4119 Bathurst St, North York, ON M3H 3P4", "Bathurst Manor", "", "http://www.noahkoshersushi.ca", "COR", 0, "North York", "food"),
            ("Royal Dairy Cafe & Catering", "Kosher Restaurants & Caterers",
             "Kosher dairy cafe and catering in Thornhill. Light meals, salads, fish, and baked goods. A warm, welcoming option for dairy shiva meals and lighter gatherings.",
             "10 Disera Dr Unit 100, Thornhill, ON L4J 0A7", "Thornhill", "", "https://royaldairycafe.com", "COR", 1, "Thornhill/Vaughan,North York", "food"),
            ("Pancer''s Original Deli", "Restaurants & Delis",
             "Legendary Toronto Jewish deli on Bathurst. Smoked meat, corned beef, and classic deli platters that have served the community for decades. A comforting, familiar choice for shiva catering.",
             "3856 Bathurst St, North York, ON M3H 3N3", "Bathurst Manor", "", "http://www.pancersoriginaldeli.com", "not_certified", 1, "Toronto,North York", "food"),
            ("Zelden''s Deli and Desserts", "Restaurants & Delis",
             "Jewish-style deli and desserts on Yonge. Sandwiches, salads, baked goods, and catering platters. A dependable choice when you need food for the family.",
             "1446 Yonge St, Toronto, ON M4T 1Y5", "Midtown", "", "http://www.zeldensdelianddesserts.com", "not_certified", 1, "Toronto", "food"),
            ("Richmond Kosher Bakery", "Bagel Shops & Bakeries",
             "COR-certified kosher bakery on Bathurst. Fresh breads, challahs, pastries, and cakes. A neighbourhood staple for Shabbat baking and shiva dessert trays.",
             "4119 Bathurst St Unit 1, North York, ON M3H 3P4", "Bathurst Manor", "", "http://richmondkosherbakery.com", "COR", 0, "North York", "food"),
            ("Aba''s Bagel Company", "Bagel Shops & Bakeries",
             "Fresh bagels and baked goods on Eglinton West. Hand-rolled, kettle-boiled bagels with a loyal following. Platters available for gatherings.",
             "884A Eglinton Ave W, Toronto, ON M6C 2B6", "Midtown", "", "https://abasbagel.com", "not_certified", 0, "Toronto", "food"),
            ("Zuchter Berk Kosher Caterers", "Caterers",
             "Established kosher caterer serving Toronto''s Jewish community. Full-service catering for lifecycle events, shiva meals, and community gatherings.",
             "2301 Keele St, Toronto, ON M6M 3Z9", "Toronto", "", "http://www.zbcaterers.com", "COR", 1, "Toronto,North York,GTA-wide", "food"),
        ]
        for v in outscraper_vendors:
            cursor.execute("SELECT id FROM vendors WHERE name = ?", (v[0].replace("''", "'"),))
            if not cursor.fetchone():
                import re as _re
                clean_name = v[0].replace("''", "'")
                slug = _re.sub(r'-+', '-', _re.sub(r'[\s]+', '-', _re.sub(r'[^a-z0-9\s-]', '', clean_name.lower().strip())))
                cursor.execute("""INSERT INTO vendors (name, slug, category, description, address, neighborhood, phone, website, kosher_status, delivery, delivery_area, vendor_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (clean_name, slug, v[1], v[2].replace("''", "'"), v[3], v[4], v[5], v[6], v[7], v[8], v[9], v[10]))
                total_changed += 1

        # Migration 2026-03-12: Remove "not_certified" label — confusing, implies certification
        # These vendors are not certified; better to show no kosher badge at all
        cursor.execute("UPDATE vendors SET kosher_status = '' WHERE kosher_status = 'Kosher Style'")
        ks_count = cursor.rowcount
        if ks_count > 0:
            logging.info(f" Migrations: removed 'Kosher Style' label from {ks_count} vendors")
        total_changed += ks_count

        # Migration 2026-03-12b: Fix 3 vendors missing website URLs (orange button fix)
        # Update ALL rows for these vendors (not just empty ones) to ensure consistency
        vendor_url_fixes = [
            "UPDATE vendors SET website = 'https://www.bubbysbagels.com', phone = '(416) 862-2435' WHERE name = 'Bubby''s Bagels'",
            "UPDATE vendors SET website = 'https://www.haymishebakery.com', phone = '(416) 781-4212' WHERE name = 'Haymishe Bakery'",
            "UPDATE vendors SET website = 'https://umamisushi.ca', phone = '(416) 782-3375' WHERE name = 'Umami Sushi'",
        ]
        for sql in vendor_url_fixes:
            cursor.execute(sql)

        # Migration 2026-03-12c: Remove duplicate vendor rows (keep lowest ID)
        cursor.execute("""
            DELETE FROM vendors WHERE id NOT IN (
                SELECT MIN(id) FROM vendors GROUP BY name
            )
        """)
        dedup_count = cursor.rowcount
        if dedup_count > 0:
            logging.info(f" Migrations: removed {dedup_count} duplicate vendor rows")
            total_changed += cursor.rowcount

        # Migration 2026-03-09: Auto-confirm all existing unconfirmed subscribers
        # At 15 subscribers, all are intentional signups. The double opt-in confirmation
        # email was going to spam (SPF was broken until Mar 6), so many never confirmed.
        cursor.execute("""
            UPDATE subscribers SET confirmed = TRUE, confirmed_at = COALESCE(confirmed_at, datetime('now'))
            WHERE confirmed = FALSE AND unsubscribed_at IS NULL
        """)
        confirmed_count = cursor.rowcount
        if confirmed_count > 0:
            logging.info(f" Migrations: auto-confirmed {confirmed_count} unconfirmed subscribers")
        total_changed += confirmed_count

        # Migration 2026-03-13: Add Jordana's Mar 12 vendors that weren't in production
        new_vendors = [
            ('Me Va Mi Kitchen Express', 'me-va-mi-kitchen-express', 'Caterers', 'food',
             'Kosher kitchen offering fresh prepared meals, catering trays, and family-style platters. Convenient pickup and delivery for shiva homes and community events.',
             'Toronto, ON', 'Toronto', '', 'https://mevamekitchenexpress.ca/', None, 'COR', 1, 'Toronto'),
            ('Pantry Foods', 'pantry-foods', 'Caterers', 'food',
             'Kosher grocery and prepared foods. Ready-made meals, platters, and pantry staples delivered to shiva homes.',
             'Toronto, ON', 'Toronto', '', 'https://pantryfoods.ca/', None, 'COR', 1, 'Toronto'),
            ('AB Cookies', 'ab-cookies', 'Baked Goods', 'food',
             'Beautiful custom cookies and sweet treats. Gift boxes perfect for bringing something special to a shiva home.',
             'Toronto, ON', 'Toronto', '', '', '@abcookies.co', 'not_certified', 0, ''),
            ('Skye Dough Cookies', 'skye-dough-cookies', 'Baked Goods', 'food',
             'Beautiful custom cookies and cookie gift boxes. A sweet, thoughtful gift to bring to a shiva home.',
             'Toronto, ON', 'Toronto', '', '', 'skyedoughcookies', 'not_certified', 0, ''),
        ]
        for v in new_vendors:
            cursor.execute("""
                INSERT OR IGNORE INTO vendors (name, slug, category, vendor_type, description,
                    address, neighborhood, phone, website, instagram, kosher_status, delivery, delivery_area, featured, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
            """, v)
            if cursor.rowcount:
                logging.info(f" Migrations: added vendor '{v[0]}'")
                total_changed += 1

        # Migration 2026-03-13b: Fix Orly's Kitchen category to 'Caterers'
        cursor.execute("UPDATE vendors SET category = 'Caterers' WHERE slug = 'orlys-kitchen' AND category != 'Caterers'")
        if cursor.rowcount:
            logging.info(f" Migrations: fixed Orly's Kitchen category to Caterers")
            total_changed += cursor.rowcount

        # Migration 2026-03-13c: Me Va Mi and Pantry should be caterers (food), NOT gift vendors
        # seed_vendors.py added them as vendor_type='gift' but Jordana says caterers only
        for slug in ['me-va-mi-kitchen-express', 'pantry-foods']:
            cursor.execute("UPDATE vendors SET vendor_type = 'food' WHERE slug = ? AND vendor_type = 'gift'", (slug,))
            if cursor.rowcount:
                logging.info(f" Migrations: moved {slug} from gift to food vendors")
                total_changed += cursor.rowcount

        conn.commit()
    except Exception as e:
        logging.info(f" Migrations phase 1: {e}")

    # Phase 2: Vendor cleanup (separate try/except so one failure doesn't block others)
    try:
        conn = _connect_db()
        cursor = conn.cursor()
        total_changed = 0

        # Remove vendors that don't belong
        for slug in ['kosher-quality-bakery-deli', 'mattis-kitchen', 'jojos-pizza', 'longos', 'scaramouche-restaurant', 'whole-foods-market-yorkville']:
            cursor.execute("DELETE FROM vendors WHERE slug = ?", (slug,))
            if cursor.rowcount:
                logging.info(f" Migrations: removed vendor {slug}")
                total_changed += cursor.rowcount

        # Remove duplicate Paisanos and Bubby's (keep first of each)
        for name_pattern in ['%Paisano%', '%Bubby%']:
            cursor.execute(f"DELETE FROM vendors WHERE name LIKE ? AND rowid NOT IN (SELECT MIN(rowid) FROM vendors WHERE name LIKE ?)", (name_pattern, name_pattern))
            if cursor.rowcount:
                logging.info(f" Migrations: removed duplicates matching {name_pattern}")
                total_changed += cursor.rowcount

        # Fix kosher_status: Chop Hop and Me Va Mi are NOT COR
        cursor.execute("UPDATE vendors SET kosher_status = '' WHERE slug = 'chop-hop'")
        total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET kosher_status = 'not_certified' WHERE slug = 'me-va-mi-kitchen-express' AND kosher_status = 'COR'")
        total_changed += cursor.rowcount

        # Me Va Mi and Pantry should be caterers (food), NOT gift vendors
        for slug in ['me-va-mi-kitchen-express', 'pantry-foods']:
            cursor.execute("UPDATE vendors SET vendor_type = 'food' WHERE slug = ? AND vendor_type = 'gift'", (slug,))
            if cursor.rowcount:
                logging.info(f" Migrations: moved {slug} from gift to food vendors")
                total_changed += cursor.rowcount

        # Fix Orly's Kitchen category
        cursor.execute("UPDATE vendors SET category = 'Caterers' WHERE slug = 'orlys-kitchen' AND category != 'Caterers'")
        total_changed += cursor.rowcount

        # Add Candy Catchers gift vendor
        cursor.execute("""
            INSERT OR IGNORE INTO vendors (name, slug, category, vendor_type, description,
                address, neighborhood, phone, website, kosher_status, delivery, delivery_area, featured, created_at)
            VALUES ('Candy Catchers', 'candy-catchers', 'Gift Baskets', 'gift',
                'Creative kosher candy and treat gift boxes. Colourful, fun gift options perfect for bringing to a shiva home or sending condolences.',
                'Toronto, ON', 'Toronto', '', 'https://candycatchers.com/', 'Kosher', 1, 'Toronto,GTA', 0, datetime('now'))
        """)
        if cursor.rowcount:
            logging.info(f" Migrations: added Candy Catchers gift vendor")
            total_changed += cursor.rowcount

        # Add Boards by Dani gift vendor (Jordana Mar 19)
        cursor.execute("""
            INSERT OR IGNORE INTO vendors (name, slug, category, vendor_type, description,
                address, neighborhood, phone, website, kosher_status, delivery, delivery_area, featured, created_at)
            VALUES ('Boards by Dani', 'boards-by-dani', 'Chocolate & Sweets', 'gift',
                'Beautiful custom charcuterie and dessert boards. Perfect for bringing to a shiva home — artfully arranged platters that show you care. Toronto-based with local delivery.',
                'Toronto, ON', 'Toronto', '', 'https://boardsbydani.com', 'not_certified', 1, 'Toronto,GTA', 0, datetime('now'))
        """)
        if cursor.rowcount:
            logging.info(f" Migrations: added Boards by Dani gift vendor")
            total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET instagram = 'boards_by_dani' WHERE slug = 'boards-by-dani' AND (instagram IS NULL OR instagram = '')")

        # Migration 2026-03-13f: Add missing websites for all vendors
        website_updates = [
            ('beautys-luncheonette', 'https://www.beautys.ca/', None),
            ('bistro-grande', 'https://bistrogrande.com/', None),
            ('bubbys', 'https://www.bubbysbagels.com/', None),
            ('dr-laffa', 'https://drlaffa.com/', None),
            ('harbord-bakery', 'https://www.harbordbakery.ca/', None),
            ('haymishe-bakery', 'https://www.haymishebakery.com/', 'haymishebakeryto'),
            ('hermes-bakery', 'http://hermesbakery.com/', None),
            ('me-va-me', 'https://www.mevame.com/', None),
            ('oinegs-kosher', 'https://www.oinegshabbes.com/', 'oinegskosher'),
            ('orlys-kitchen', 'https://orly-grill.com/', None),
            ('pizza-pita-prime', 'https://pizzapitaprime.order-online.ai/', None),
            ('sushi-inn', 'https://www.sushiinn.net/', None),
            ('tov-li-pizza-falafel', 'https://tov-li.com/', None),
            ('umami-sushi', 'https://www.umamisushi.ca/', None),
            ('wilenskys-light-lunch', 'http://www.wilenskys.com/', None),
            ('boulangerie-cheskie', None, 'cheskiebakery'),
            ('lefalafel-plus', None, 'lefalafel_+'),
        ]
        for slug, website, instagram in website_updates:
            parts = []
            params = []
            if website:
                parts.append("website = ?")
                params.append(website)
            if instagram:
                parts.append("instagram = ?")
                params.append(instagram)
            if parts:
                params.append(slug)
                cursor.execute(f"UPDATE vendors SET {', '.join(parts)} WHERE slug = ? AND (website IS NULL OR website = '')", params)
                if cursor.rowcount:
                    logging.info(f" Migrations: added website/instagram for {slug}")
                    total_changed += cursor.rowcount

        # Update Bubby's Bagels website to menu page
        cursor.execute("UPDATE vendors SET website = 'https://www.bubbysbagels.com/menu' WHERE slug LIKE 'bubby%' AND website = 'https://www.bubbysbagels.com/'")
        total_changed += cursor.rowcount

        # Migration 2026-03-18: Aroma is NOT COR certified; Aba's is Kosher Style
        cursor.execute("UPDATE vendors SET kosher_status = 'not_certified' WHERE slug = 'aroma-espresso-bar' AND kosher_status = 'COR'")
        total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET kosher_status = '' WHERE slug = 'abas-bagel-company' AND kosher_status = 'not_certified'")
        total_changed += cursor.rowcount

        # Migration 2026-03-18b: Remove duplicate Beyond Delish, fix Aroma description, fix Skye Dough category
        cursor.execute("DELETE FROM vendors WHERE slug = 'beyond-delish-kosher-food-catering'")
        total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET description = 'Israeli-born cafe chain with multiple locations. Coffee, pastries, salads, sandwiches, and shakshuka. A warm, familiar option for lighter shiva meals.' WHERE slug = 'aroma-espresso-bar'")
        total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET category = 'Restaurants & Delis' WHERE slug = 'aroma-espresso-bar' AND category = 'Kosher Restaurants & Caterers'")
        total_changed += cursor.rowcount
        cursor.execute("UPDATE vendors SET category = 'Baked Goods' WHERE slug = 'skye-dough-cookies' AND category = 'Gift Baskets'")
        total_changed += cursor.rowcount

        # Migration 2026-03-22: Remove Aish Tanoor (out of business per Jordana)
        cursor.execute("DELETE FROM vendors WHERE slug = 'aish-tanoor' AND (source IS NULL OR source = 'seed' OR source = '')")
        total_changed += cursor.rowcount

        # Ensure Becked Goods exists (seed may not insert if deploy cached old code)
        cursor.execute("SELECT id FROM vendors WHERE slug = 'becked-goods'")
        if not cursor.fetchone():
            cursor.execute("""INSERT INTO vendors (name, slug, category, vendor_type, description, address, neighborhood,
                phone, website, instagram, kosher_status, delivery, delivery_area, image_url, featured, created_at)
                VALUES ('Becked Goods', 'becked-goods', 'Baked Goods', 'gift',
                'Homemade baked goods and cookie gifts. A warm, personal option for bringing something sweet to a shiva home.',
                'Toronto, ON', 'Toronto', '', 'https://beckedgoods.com', '', 'not_certified', 1, 'Toronto', '', 0, datetime('now'))""")
            total_changed += cursor.rowcount

        # Migration 2026-03-22: Pre-launch cleanup — remove all test shiva data
        # All 15 entries are from jordanamednick@gmail.com and erinkofman@gmail.com, created before launch
        test_shiva_ids = [
            '0eedaece-a905-47aa-bb8e-17f538a580f5',
            '6e5f0b1a-17b2-43bc-8560-64b21657e9c8',
            '419201d3-85e8-4b09-84de-8fa5be0e600a',
            'e1be5002-a954-4b94-9f5f-c2adb4031656',
            'cb507512-d887-4d27-994e-25bc3e5dc984',
            'a3ffb4a5-05f1-41e4-8fdb-6eee15cbe85a',
            '457ac6f5-a281-4fc2-81f0-bcc3550d2b38',
            '46f1c9d9-a3fd-44a2-b7be-cd53431a5b57',
            'fedf1bf9-64b8-4f06-948c-50438a630968',
            '712e8edd-1284-4214-8c7c-48f48b550586',
            '70af9f5b-c854-473e-89b4-8c96a6fe7543',
            '86a37d29-447a-4bde-98c8-d1bf5cf3e8b0',
            '5ce56d41-181f-4d83-8a56-ca1dae7ef3a0',
            '1625aaa4-28b7-4b79-8a04-ee798d110a30',
            'a38d6385-7776-49d0-b40a-cf3bb9bbba46',
        ]
        placeholders = ','.join('?' * len(test_shiva_ids))
        # Clean up related tables first (use correct FK column names), then shiva_support
        for table in ['meal_signups', 'shiva_co_organizers', 'shiva_updates']:
            try:
                cursor.execute(f"DELETE FROM {table} WHERE shiva_support_id IN ({placeholders})", test_shiva_ids)
                total_changed += cursor.rowcount
            except Exception:
                pass
        cursor.execute(f"DELETE FROM shiva_support WHERE id IN ({placeholders})", test_shiva_ids)
        total_changed += cursor.rowcount

        # Migration 2026-03-22b: Remove all 'Kosher Style' labels from vendors
        cursor.execute("UPDATE vendors SET kosher_status = '' WHERE kosher_status = 'Kosher Style'")
        total_changed += cursor.rowcount

        # Migration 2026-03-22c: Remove kosher label from Chop Hop (not kosher)
        cursor.execute("UPDATE vendors SET kosher_status = '' WHERE slug = 'chop-hop'")
        total_changed += cursor.rowcount

        # Migration 2026-03-22d: Add Toben Food by Design as a caterer (non-kosher)
        cursor.execute("SELECT id FROM vendors WHERE slug = 'toben-food-by-design'")
        if not cursor.fetchone():
            cursor.execute("""INSERT INTO vendors (name, slug, category, vendor_type, description,
                address, neighborhood, phone, website, kosher_status, delivery, delivery_area, featured, created_at)
                VALUES ('Toben Food by Design', 'toben-food-by-design', 'Caterers', 'food',
                'Full-service caterer with 15+ years experience catering shiva and celebrations of life. High-end, customized menus with dietary accommodations including gluten-free and vegan options.',
                'Toronto, ON', 'Toronto', '(647) 344-8323', 'https://tobenfoodbydesign.com', '', 1, 'Toronto,GTA', 0, datetime('now'))""")
            total_changed += cursor.rowcount

        # Migration 2026-03-22e: Strip honorific suffixes (A"H, Z"L, etc.) from obituary names
        # Covers: A"H, a"h, Z"L, ZT"L, OB"M with straight/curly/Hebrew quotes, no quotes, spaces
        _q = r'["' + "'" + r'\u2018\u2019\u201c\u201d\u201e\u05f4\u2033\u02bc]'
        suffix_patterns = [
            # With various quote marks
            (r'%A"H', ), (r'%a"h', ), (r'%A\u05f4H', ), (r'%A\u201cH', ), (r'%A\u201dH', ),
            (r'%Z"L', ), (r'%z"l', ), (r'%ZT"L', ), (r'%zt"l', ),
            (r'%OB"M', ), (r'%ob"m', ),
            # Without quotes
            (r'% AH', ), (r'% ah', ), (r'% ZL', ), (r'% zl', ),
            (r'% ZTL', ), (r'% ztl', ), (r'% OBM', ), (r'% obm', ),
            # Hebrew ע"ה
            (r'%\u05e2\u05f4\u05d4', ), (r'%\u05e2"\u05d4', ),
        ]
        # Use Python to do the cleaning since SQLite regex support is limited
        cursor.execute("SELECT id, deceased_name FROM obituaries")
        import re as _re
        _honorific_q = r'[\u0022\u0027\u2018\u2019\u201c\u201d\u201e\u05f4\u2033\u02bc]'
        _honorific_re = _re.compile(
            r'\s*(?:'
            r'z\s*' + _honorific_q + r'?\s*l'
            r'|a\s*' + _honorific_q + r'?\s*h'
            r'|zt\s*' + _honorific_q + r'?\s*l'
            r'|ob\s*' + _honorific_q + r'?\s*m'
            r'|\u05e2[\u0022\u05f4\u2033]?\u05d4'
            r')\s*$',
            _re.IGNORECASE
        )
        cleaned_count = 0
        for row in cursor.fetchall():
            obit_id, name = row
            cleaned = _honorific_re.sub('', name).strip()
            if cleaned != name:
                cursor.execute("UPDATE obituaries SET deceased_name = ? WHERE id = ?", (cleaned, obit_id))
                cleaned_count += 1
        if cleaned_count > 0:
            logging.info(f" Migrations: stripped honorific suffixes from {cleaned_count} obituary names")
        total_changed += cleaned_count

        conn.commit()
        conn.close()
        if total_changed > 0:
            logging.info(f" Migrations: {total_changed} rows updated")
        else:
            logging.info(f" Migrations: already up to date")
    except Exception as e:
        logging.info(f" Migrations phase 2: {e}")

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

    # ── SIGTERM handler — backup data before Render rebuild ───
    def _sigterm_handler(signum, frame):
        logging.info("[SIGTERM] Received SIGTERM — backing up data before exit...")
        if SHIVA_AVAILABLE:
            try:
                shiva_mgr.backup_to_file()
                logging.info("[SIGTERM] Backup complete")
            except Exception as e:
                logging.error(f"[SIGTERM] Backup failed: {e}")
        httpd.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sigterm_handler)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("\n\n Server stopped")
        if SHIVA_AVAILABLE:
            try:
                shiva_mgr.backup_to_file()
                logging.info("[Shutdown] Backup complete")
            except Exception as e:
                logging.error(f"[Shutdown] Backup failed: {e}")
        httpd.shutdown()

if __name__ == '__main__':
    run_server()
