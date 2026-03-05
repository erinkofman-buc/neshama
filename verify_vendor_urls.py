#!/usr/bin/env python3
"""
Neshama Vendor URL Verification Script
Checks all vendor websites for broken links, flags vendors with no contact info,
and detects potential duplicates.

Usage: python3 verify_vendor_urls.py
"""

import sqlite3
import os
import ssl
import urllib.request
from urllib.error import URLError, HTTPError
from collections import defaultdict
from difflib import SequenceMatcher


DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neshama.db'))

# Headers to avoid bot-blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

TIMEOUT = 10  # seconds


def get_vendors(conn):
    """Query all vendors from the database. Handles both schemas (with/without instagram)."""
    cursor = conn.cursor()

    # Try with instagram column first, fall back without it
    try:
        cursor.execute("SELECT id, name, slug, category, vendor_type, description, address, neighborhood, phone, website, kosher_status, delivery, delivery_area, image_url, featured, created_at, email, instagram FROM vendors")
        has_instagram = True
    except sqlite3.OperationalError:
        cursor.execute("SELECT id, name, slug, category, vendor_type, description, address, neighborhood, phone, website, kosher_status, delivery, delivery_area, image_url, featured, created_at, email FROM vendors")
        has_instagram = False

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    vendors = []
    for row in rows:
        vendor = dict(zip(columns, row))
        if not has_instagram:
            vendor['instagram'] = None
        vendors.append(vendor)
    return vendors


def check_url(url):
    """
    Check if a URL is reachable via HEAD request.
    Returns (status_code, error_message). One of them will be None.
    """
    if not url or not url.strip():
        return None, 'empty'

    url = url.strip()
    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Create SSL context that doesn't verify certificates (some small vendor sites
    # have expired/self-signed certs, we still want to know if the server responds)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, method='HEAD', headers=HEADERS)

    try:
        response = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        return response.getcode(), None
    except HTTPError as e:
        # Some servers reject HEAD, try GET
        if e.code == 405:
            try:
                req_get = urllib.request.Request(url, method='GET', headers=HEADERS)
                response = urllib.request.urlopen(req_get, timeout=TIMEOUT, context=ctx)
                return response.getcode(), None
            except HTTPError as e2:
                return e2.code, f'HTTP {e2.code}'
            except Exception as e2:
                return None, str(e2)
        return e.code, f'HTTP {e.code}'
    except URLError as e:
        return None, f'URL Error: {e.reason}'
    except TimeoutError:
        return None, 'Timeout (10s)'
    except Exception as e:
        return None, str(e)


def find_duplicates(vendors):
    """Find vendors with identical or very similar names."""
    dupes = []
    names = [(v['id'], v['name']) for v in vendors]

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            id_a, name_a = names[i]
            id_b, name_b = names[j]

            # Exact match (case-insensitive)
            if name_a.strip().lower() == name_b.strip().lower():
                dupes.append((id_a, name_a, id_b, name_b, 1.0))
                continue

            # Fuzzy match
            ratio = SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()
            if ratio >= 0.85:
                dupes.append((id_a, name_a, id_b, name_b, round(ratio, 2)))

    return dupes


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print(f"Set DB_PATH env var or ensure neshama.db is in {os.path.dirname(os.path.abspath(__file__))}")
        return

    conn = sqlite3.connect(DB_PATH)
    vendors = get_vendors(conn)
    print(f"Found {len(vendors)} vendors in database.\n")

    working = []
    broken = []
    no_contact = []

    for v in vendors:
        vid = v['id']
        name = v['name']
        website = (v.get('website') or '').strip()
        phone = (v.get('phone') or '').strip()
        email = (v.get('email') or '').strip()
        instagram = (v.get('instagram') or '').strip()

        if not website:
            # No website -- check if there's any other contact info
            has_other_contact = bool(phone or email or instagram)
            if not has_other_contact:
                no_contact.append({'id': vid, 'name': name})
                print(f"  [{len(working) + len(broken) + len(no_contact)}/{len(vendors)}] {name} -- NO CONTACT INFO")
            else:
                # Has phone/email/instagram but no website -- skip URL check
                print(f"  [{len(working) + len(broken) + len(no_contact)}/{len(vendors)}] {name} -- no website (has other contact)")
            continue

        # Check the URL
        print(f"  [{len(working) + len(broken) + len(no_contact) + 1}/{len(vendors)}] Checking {name} ({website})...", end=' ', flush=True)
        status, error = check_url(website)

        if status and 200 <= status < 400:
            working.append({'id': vid, 'name': name, 'url': website, 'status': status})
            print(f"OK ({status})")
        else:
            err_display = error if error else f'HTTP {status}'
            broken.append({'id': vid, 'name': name, 'url': website, 'error': err_display})
            print(f"BROKEN ({err_display})")

    # --- Report ---
    print("\n" + "=" * 70)
    print("VENDOR URL VERIFICATION REPORT")
    print("=" * 70)

    print(f"\n--- WORKING ({len(working)}) ---")
    if working:
        for v in sorted(working, key=lambda x: x['name']):
            print(f"  {v['name']:40s} {v['url']:50s} [{v['status']}]")
    else:
        print("  (none)")

    print(f"\n--- BROKEN ({len(broken)}) ---")
    if broken:
        for v in sorted(broken, key=lambda x: x['name']):
            print(f"  {v['name']:40s} {v['url']:50s} [{v['error']}]")
    else:
        print("  (none)")

    print(f"\n--- NO WEBSITE + NO PHONE ({len(no_contact)}) ---")
    if no_contact:
        for v in sorted(no_contact, key=lambda x: x['name']):
            print(f"  {v['name']}")
    else:
        print("  (none)")

    # --- Duplicate check ---
    print(f"\n--- DUPLICATE CHECK ---")
    dupes = find_duplicates(vendors)
    if dupes:
        for id_a, name_a, id_b, name_b, ratio in dupes:
            match_type = "EXACT" if ratio == 1.0 else f"{int(ratio * 100)}% similar"
            print(f"  [{match_type}] #{id_a} \"{name_a}\"  <-->  #{id_b} \"{name_b}\"")
    else:
        print("  No duplicates found.")

    # --- Summary ---
    total_flagged = len(broken) + len(no_contact)
    print(f"\nSummary: {len(working)} working, {len(broken)} broken, {len(no_contact)} no-contact, {len(dupes)} potential duplicates")
    print(f"Total vendors flagged for review: {total_flagged}")

    # --- Optional deletion ---
    if total_flagged > 0:
        ids_to_delete = [v['id'] for v in broken] + [v['id'] for v in no_contact]
        print(f"\nDelete {total_flagged} broken/no-contact vendors from the database? (y/n): ", end='', flush=True)
        answer = input().strip().lower()
        if answer == 'y':
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM vendors WHERE id IN ({','.join('?' * len(ids_to_delete))})",
                ids_to_delete
            )
            conn.commit()
            print(f"Deleted {cursor.rowcount} vendors.")
        else:
            print("No vendors deleted.")
    else:
        print("\nNo vendors to delete.")

    conn.close()
    print("Done.")


if __name__ == '__main__':
    main()
