#!/usr/bin/env python3
"""Seed (or remove) the Paperman's demo sample shiva.

Why this exists
---------------
The Paperman's remote demo (see vault: Neshama/papermans-demo-runbook.md) needs a
shiva page that looks lived-in, never an empty form. There is no existing seed
mechanism, so this script creates ONE shiva_support page plus a handful of
meal_signups through the app's own write path (ShivaManager.create_support),
then marks it private so it stays out of any public surface.

Design choices (deliberate, see runbook + _NOW.md):
  * Uses ShivaManager.create_support() for the shiva row so we inherit the real
    validation + the current column set (no hand-rolled INSERT that can drift).
  * privacy = 'private'  -> the page is reachable ONLY with its magic token in
    the URL. There is no public "browse shivas" list, and the active-shiva count
    only appears on the admin dashboard, so a private demo is invisible to the
    public. Erin opens it with the token link during the screen-share.
  * source = 'funeral_home' and a distinctive organizer_email
    (DEMO_EMAIL below) make the row trivially findable and removable.
  * Records the id + token + URLs to a sidecar JSON next to this script so the
    page can be reopened and cleanly torn down after the demo.

Environment, not a flag, picks the target DB
---------------------------------------------
The script writes to whatever DATABASE_PATH points at (default ../neshama.db),
exactly like api_server.py. Run it locally against a temp DB to rehearse; run it
in the Render shell (where DATABASE_PATH is the persistent disk DB) to seed prod.
It never auto-selects an environment.

Usage:
    python3 seed_demo_shiva.py create        # seed (refuses if already seeded)
    python3 seed_demo_shiva.py info          # show the recorded id/token/links
    python3 seed_demo_shiva.py remove        # delete the demo shiva + its rows
    python3 seed_demo_shiva.py create --start-date 2026-06-07
    DATABASE_PATH=/tmp/demo.db python3 seed_demo_shiva.py create --base-url http://localhost:5050
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

# Import ShivaManager from the frontend package.
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
sys.path.insert(0, FRONTEND_DIR)
from shiva_manager import ShivaManager  # noqa: E402

DEFAULT_DB = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neshama.db'),
)
SIDECAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.demo-shiva.json')

# The unique handle that marks this row as the demo and makes removal targeted.
DEMO_EMAIL = 'demo-papermans@neshama.ca'

# --- Demo content (Montreal-flavoured, per runbook Part 3) -------------------
FAMILY_NAME = 'Greenberg'
DECEASED = 'Sol Greenberg, z"l'
ORGANIZER_NAME = 'Rachel Greenberg'
SHIVA_CITY = 'Montreal'
SHIVA_SUB_AREA = 'Hampstead'
SHIVA_ADDRESS = '00 Demo Street, Hampstead'  # placeholder; private + token-gated
GUESTS_PER_MEAL = 18


def next_sunday(from_day=None):
    d = from_day or date.today()
    # weekday(): Mon=0 .. Sun=6
    days = (6 - d.weekday()) % 7
    days = days or 7  # always the upcoming Sunday, never today
    return d + timedelta(days=days)


def claimed_meals(start):
    """A mix of filled and open nights so the calendar looks alive.
    Open nights (Mon lunch, Tue dinner) are simply absent -> they render as open.
    """
    iso = lambda offset: (start + timedelta(days=offset)).isoformat()
    return [
        # (date, meal_type, volunteer_name, description, servings)
        (iso(0), 'Dinner', 'The Adler family', 'Roast chicken, kugel, and salad', 18),
        (iso(1), 'Dinner', 'Rachel & David Stein', 'Deli platter and sides', 18),
        (iso(2), 'Lunch', 'Hampstead chesed committee', 'Dairy lunch spread', 18),
    ]


def find_existing(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, magic_token FROM shiva_support WHERE organizer_email = ?",
            (DEMO_EMAIL,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None  # schema not initialised yet
    finally:
        conn.close()


def write_sidecar(payload):
    with open(SIDECAR, 'w') as f:
        json.dump(payload, f, indent=2)


def read_sidecar():
    if os.path.exists(SIDECAR):
        with open(SIDECAR) as f:
            return json.load(f)
    return None


def urls(base_url, sid, token):
    return {
        'family_view': f"{base_url}/shiva/view?id={sid}&token={token}",
        'organizer_dashboard': f"{base_url}/shiva/dashboard?id={sid}&token={token}",
    }


def cmd_create(args):
    db_path = args.db
    base_url = args.base_url

    # Instantiate first: ShivaManager.__init__ runs setup_database(), which
    # builds the schema idempotently. Only then is it safe to query for a dup.
    mgr = ShivaManager(db_path=db_path)

    existing = find_existing(db_path)
    if existing:
        print(f"Demo shiva already exists (id={existing['id']}). "
              f"Run `info` to see links or `remove` first.")
        return 1

    start = (datetime.strptime(args.start_date, '%Y-%m-%d').date()
             if args.start_date else next_sunday())
    end = start + timedelta(days=4)  # Sun..Thu

    data = {
        'organizer_name': ORGANIZER_NAME,
        'organizer_email': DEMO_EMAIL,
        'organizer_relationship': 'Daughter',
        'family_name': FAMILY_NAME,
        'shiva_address': SHIVA_ADDRESS,
        'shiva_city': SHIVA_CITY,
        'shiva_sub_area': SHIVA_SUB_AREA,
        'shiva_start_date': start.isoformat(),
        'shiva_end_date': end.isoformat(),
        'guests_per_meal': GUESTS_PER_MEAL,
        'special_instructions': (
            'In loving memory of ' + DECEASED + '. '
            'No visiting during Shabbat (Friday sundown to Saturday night).'
        ),
        'family_notes': 'DEMO PAGE - Paperman & Sons walkthrough. Safe to delete.',
        'source': 'funeral_home',
        'privacy_consent': True,
        '_skip_similar': True,
    }

    result = mgr.create_support(data)
    if result.get('status') != 'success':
        print(f"create_support failed: {result}")
        return 1

    sid = result['id']
    token = result['magic_token']

    # Post-create adjustments the public create path does not expose:
    #  - force privacy=private so the page is token-only
    #  - stamp pause_shabbat on (Shabbat-aware, matches runbook)
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE shiva_support SET privacy = 'private', pause_shabbat = 1 WHERE id = ?",
            (sid,),
        )
        # Claimed meals so the calendar looks lived-in.
        now = datetime.now().isoformat()
        for mdate, mtype, vol, desc, servings in claimed_meals(start):
            cur.execute(
                """INSERT INTO meal_signups (
                       shiva_support_id, volunteer_name, volunteer_email, volunteer_phone,
                       meal_date, meal_type, meal_description, num_servings,
                       will_serve, privacy_consent, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, vol, DEMO_EMAIL, None, mdate, mtype, desc, servings, 0, 1, now),
            )
    finally:
        conn.close()

    link = urls(base_url, sid, token)
    payload = {
        'id': sid,
        'magic_token': token,
        'organizer_email': DEMO_EMAIL,
        'family_name': FAMILY_NAME,
        'deceased': DECEASED,
        'privacy': 'private',
        'shiva_start_date': start.isoformat(),
        'shiva_end_date': end.isoformat(),
        'db_path': os.path.abspath(db_path),
        'base_url': base_url,
        'created_at': datetime.now().isoformat(),
        **link,
    }
    write_sidecar(payload)

    print("Demo shiva seeded (private).")
    print(f"  id:    {sid}")
    print(f"  dates: {start.isoformat()} -> {end.isoformat()}")
    print(f"  family view:        {link['family_view']}")
    print(f"  organizer dashboard:{link['organizer_dashboard']}")
    print(f"  sidecar:            {SIDECAR}")
    return 0


def cmd_info(args):
    sc = read_sidecar()
    if not sc:
        print("No sidecar found. Has the demo been seeded yet?")
        return 1
    print(json.dumps(sc, indent=2))
    return 0


def cmd_remove(args):
    db_path = args.db
    sid = args.id
    if not sid:
        sc = read_sidecar()
        if sc:
            sid = sc.get('id')
        if not sid:
            existing = find_existing(db_path)
            sid = existing['id'] if existing else None
    if not sid:
        print("Nothing to remove (no id given, no sidecar, no row by demo email).")
        return 1

    conn = sqlite3.connect(db_path, isolation_level=None)
    total = 0
    try:
        cur = conn.cursor()
        # Child tables first, mirroring the test-shiva cleanup in api_server.py.
        for table in ('meal_signups', 'shiva_co_organizers', 'shiva_updates'):
            try:
                cur.execute(f"DELETE FROM {table} WHERE shiva_support_id = ?", (sid,))
                total += cur.rowcount
            except sqlite3.OperationalError:
                pass  # table may not exist in older schemas
        cur.execute("DELETE FROM shiva_support WHERE id = ?", (sid,))
        total += cur.rowcount
    finally:
        conn.close()

    if os.path.exists(SIDECAR):
        os.remove(SIDECAR)
    print(f"Removed demo shiva {sid} and related rows ({total} rows deleted).")
    return 0


def main():
    p = argparse.ArgumentParser(description="Seed/remove the Paperman's demo sample shiva.")
    p.add_argument('command', choices=['create', 'info', 'remove'])
    p.add_argument('--db', default=DEFAULT_DB, help='SQLite DB path (default: $DATABASE_PATH or ../neshama.db)')
    p.add_argument('--base-url', default=os.environ.get('BASE_URL', 'https://neshama.ca'),
                   help='Base URL for the printed links (default: $BASE_URL or https://neshama.ca)')
    p.add_argument('--start-date', help='Shiva start date YYYY-MM-DD (default: upcoming Sunday)')
    p.add_argument('--id', help='Explicit shiva id for remove (overrides sidecar)')
    args = p.parse_args()

    if args.command == 'create':
        return cmd_create(args)
    if args.command == 'info':
        return cmd_info(args)
    if args.command == 'remove':
        return cmd_remove(args)
    return 1


if __name__ == '__main__':
    sys.exit(main())
