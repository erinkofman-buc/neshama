#!/usr/bin/env python3
"""One-shot obituary de-duplication. Run once, from the Render Shell, then never again.

    python dedupe_obituaries_2026_08_26.py             # DRY RUN (default, read-only)
    python dedupe_obituaries_2026_08_26.py --execute    # writes, in ONE transaction

Background. `generate_obituary_id()` hashes source + name + date_of_death, so an
obituary scraped before the funeral home publishes a date hashes differently from
the same obituary after. The result is duplicate rows for one person. `/api/obituaries`
has been hiding them at read time since forever; the weekly digest was not, which is
what Paperman & Sons reported.

Merge rules (Erin's rulings, 2026-08-26):
  * The OLDEST row's `id` survives. Memorial URLs get shared in WhatsApp groups and
    indexed by Google; breaking one is the failure mode this site cannot afford.
  * Every other field takes the NEWEST non-empty value, so the fullest content wins.
  * EXCEPT `deceased_name`, which takes the MOST COMPLETE variant, compared by length
    after stripping zero-width characters and collapsing whitespace. Newest-wins was
    silently dropping honorifics ("Dr. Randy Leifer" -> "Randy Leifer") and nee names.
  * EXCEPT `date_of_death`, which refuses any pre-1990 value onto a survivor whose own
    date is empty. Three rows carry a birth date in that column (1924 / 1932 / 1940);
    an obituary scraped in 2026 cannot have a 1924 death date, and this column feeds
    the yahrzeit calculation. Logged to data-quality-backlog.md. The rule is general,
    not a hardcode of those three ids.

Safety:
  * Dry run is the DEFAULT. Nothing writes without --execute.
  * The whole operation is ONE transaction, opened with BEGIN IMMEDIATE.
  * Invariants are checked BEFORE COMMIT. Any mismatch rolls the whole thing back.
  * References are re-pointed at the survivor BEFORE the duplicate rows are deleted,
    so nothing is orphaned. ~9,200 `comments` rows depend on this.
  * Hidden rows (hidden=1) are excluded entirely and never touched.
"""

import argparse
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend'))
from daily_digest import _normalize_name  # noqa: E402  (the battle-tested matcher)

DB_PATH = os.environ.get('DATABASE_PATH', '/data/neshama.db')

# Tables holding a foreign key to obituaries.id. Re-pointed, never deleted.
FK_TABLES = [
    ('comments', 'obituary_id'),
    ('shiva_support', 'obituary_id'),
    ('yahrzeit_reminders', 'obituary_id'),
    ('shiva_analytics', 'obituary_id'),
    ('tributes', 'obituary_id'),
]

SUSPECT_YEAR = re.compile(r'\b(1[0-9]{2}\d|19[0-8]\d)\b')


def clean_name(value):
    """Strip zero-width/format characters and collapse whitespace.

    Funeral homes inject U+200B and friends. Without this the polluted variant wins
    the most-complete comparison on raw length and an invisible control character
    gets written into a real person's name.
    """
    if not value:
        return ''
    stripped = ''.join(c for c in value if unicodedata.category(c) != 'Cf')
    return ' '.join(stripped.split())


def build_plan(conn):
    """Recompute the merge plan against the LIVE table. Never trust a stale plan:
    the scrapers keep running and may have added rows since the rehearsal."""
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        'SELECT * FROM obituaries WHERE COALESCE(hidden, 0) = 0')]

    groups = defaultdict(list)
    for row in rows:
        groups[(_normalize_name(row.get('deceased_name') or ''),
                row.get('source') or '')].append(row)

    plan = []
    for key, cluster in groups.items():
        if len(cluster) < 2 or not key[0]:
            continue
        cluster.sort(key=lambda r: (r.get('first_seen') or r.get('last_updated') or '',
                                    r.get('id') or ''))
        survivor, dropped = cluster[0], cluster[1:]
        merged, held = {}, []

        for field in survivor.keys():
            if field == 'id':
                continue
            if field in ('first_seen', 'last_updated'):
                values = [r.get(field) for r in cluster if r.get(field)]
                if values:
                    merged[field] = min(values) if field == 'first_seen' else max(values)
                continue
            if field == 'deceased_name':
                names = [clean_name(r.get(field)) for r in cluster if clean_name(r.get(field))]
                if names:
                    merged[field] = max(names, key=len)
                continue
            value = survivor.get(field)
            for other in dropped:
                if other.get(field) not in (None, '', 0):
                    value = other.get(field)
            if field == 'date_of_death' and not survivor.get(field) and value \
                    and SUSPECT_YEAR.search(str(value)):
                held.append(str(value))
                value = survivor.get(field)
            merged[field] = value

        changed = {f: v for f, v in merged.items() if survivor.get(f) != v}
        plan.append({'key': key, 'survivor': survivor, 'dropped': dropped,
                     'changed': changed, 'held': held})
    return rows, plan


def count_visible(conn):
    return conn.execute(
        'SELECT COUNT(*) FROM obituaries WHERE COALESCE(hidden, 0) = 0').fetchone()[0]


def count_orphans(conn):
    out = {}
    for table, column in FK_TABLES:
        try:
            out[table] = conn.execute(
                f'SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL '
                f'AND {column} NOT IN (SELECT id FROM obituaries)').fetchone()[0]
        except sqlite3.Error:
            out[table] = None
    return out


def count_normalized_dupes(conn):
    rows = conn.execute(
        'SELECT deceased_name, source FROM obituaries '
        'WHERE COALESCE(hidden, 0) = 0').fetchall()
    seen = defaultdict(int)
    for name, source in rows:
        seen[(_normalize_name(name or ''), source or '')] += 1
    return sum(1 for k, n in seen.items() if n > 1 and k[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true',
                    help='actually write. Without this the script is read-only.')
    ap.add_argument('--db', default=DB_PATH)
    args = ap.parse_args()

    print(f'database : {args.db}')
    print(f'mode     : {"EXECUTE (writes)" if args.execute else "DRY RUN (read-only)"}')
    if not os.path.exists(args.db):
        sys.exit(f'FATAL: no database at {args.db}')

    # busy_timeout is generous on purpose: the scrapers write to this same file and
    # we would rather wait for a gap than fail. isolation_level=None so WE control
    # the transaction boundary rather than Python opening one implicitly.
    conn = sqlite3.connect(args.db, timeout=60, isolation_level=None)
    conn.execute('PRAGMA busy_timeout=60000')

    before_visible = count_visible(conn)
    before_orphans = count_orphans(conn)
    before_dupes = count_normalized_dupes(conn)

    _, plan = build_plan(conn)
    dropped_ids = [d['id'] for p in plan for d in p['dropped']]
    expected_after = before_visible - len(dropped_ids)

    refs = {}
    if dropped_ids:
        marks = ','.join('?' * len(dropped_ids))
        for table, column in FK_TABLES:
            try:
                refs[table] = conn.execute(
                    f'SELECT COUNT(*) FROM {table} WHERE {column} IN ({marks})',
                    dropped_ids).fetchone()[0]
            except sqlite3.Error:
                refs[table] = 0

    print()
    print('=== PLAN (computed against the live table just now) ===')
    print(f'  visible obituaries      : {before_visible}')
    print(f'  duplicate clusters      : {len(plan)}')
    print(f'  rows to delete          : {len(dropped_ids)}')
    print(f'  expected after          : {expected_after}')
    print(f'  normalized dupes now    : {before_dupes}')
    print(f'  suspect dates held NULL : {sum(len(p["held"]) for p in plan)}')
    print(f'  survivors gaining a name: '
          f'{sum(1 for p in plan if "deceased_name" in p["changed"])}')
    print('  references to re-point  :')
    for table, n in refs.items():
        print(f'      {table:<22} {n}')
    print('  pre-existing orphans (NOT ours, must not change):')
    for table, n in before_orphans.items():
        print(f'      {table:<22} {n}')

    if not plan:
        print('\nNothing to do.')
        return

    if not args.execute:
        print('\nDRY RUN complete. Nothing was written. Re-run with --execute to apply.')
        return

    print('\n=== EXECUTING (single transaction) ===')
    try:
        conn.execute('BEGIN IMMEDIATE')  # take the write lock up front, not halfway

        for p in plan:
            sid = p['survivor']['id']
            drop = [d['id'] for d in p['dropped']]
            marks = ','.join('?' * len(drop))
            for table, column in FK_TABLES:
                try:
                    conn.execute(
                        f'UPDATE {table} SET {column} = ? WHERE {column} IN ({marks})',
                        [sid] + drop)
                except sqlite3.Error:
                    pass  # table absent on this deployment; nothing to re-point
            if p['changed']:
                sets = ', '.join(f'"{f}" = ?' for f in p['changed'])
                conn.execute(f'UPDATE obituaries SET {sets} WHERE id = ?',
                             list(p['changed'].values()) + [sid])
            conn.execute(f'DELETE FROM obituaries WHERE id IN ({marks})', drop)

        # ── invariants, checked INSIDE the transaction ──
        after_visible = count_visible(conn)
        after_orphans = count_orphans(conn)
        after_dupes = count_normalized_dupes(conn)
        survivors = [p['survivor']['id'] for p in plan]
        marks = ','.join('?' * len(survivors))
        survivors_present = conn.execute(
            f'SELECT COUNT(*) FROM obituaries WHERE id IN ({marks})', survivors).fetchone()[0]

        problems = []
        if after_visible != expected_after:
            problems.append(f'row count {after_visible}, expected {expected_after}')
        if survivors_present != len(survivors):
            problems.append(f'survivors present {survivors_present}, expected {len(survivors)}')
        if after_dupes != 0:
            problems.append(f'{after_dupes} normalized duplicates remain')
        for table in before_orphans:
            if after_orphans.get(table) != before_orphans.get(table):
                problems.append(f'{table} orphans {before_orphans.get(table)} -> '
                                f'{after_orphans.get(table)}')

        if problems:
            conn.execute('ROLLBACK')
            print('\n*** ROLLED BACK. Nothing changed. ***')
            for pr in problems:
                print(f'    FAILED: {pr}')
            sys.exit(1)

        conn.execute('COMMIT')
        print('  committed.')
        print()
        print('=== RESULT ===')
        print(f'  obituaries : {before_visible} -> {after_visible}')
        print(f'  clusters merged            : {len(plan)}')
        print(f'  rows deleted               : {len(dropped_ids)}')
        print(f'  survivor ids preserved     : {survivors_present}/{len(survivors)}')
        print(f'  normalized dupes remaining : {after_dupes}')
        for table in before_orphans:
            print(f'  {table + " orphans":<28} {before_orphans[table]} -> {after_orphans[table]}'
                  '  (unchanged)')
    except Exception as exc:
        try:
            conn.execute('ROLLBACK')
        except sqlite3.Error:
            pass
        print(f'\n*** ROLLED BACK on error. Nothing changed. ***\n    {exc}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
