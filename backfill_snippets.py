"""
Backfill obituary_snippet for existing obituaries that don't have one.

Per HANDOFF-obituaries.md. Run ONCE after the schema migration deploys.
Cost: ~$1 for ~500 obits at Haiku pricing. Trivial — not worth caching/deduping.

Safety:
- Idempotent: skips rows that already have a snippet
- Rate-limited: 0.3s sleep between calls (be kind to the API even though we're well under limits)
- Resumable: each obit commits independently — if it crashes mid-run, restart and it picks up where it left off
- Hidden obits: skipped (won't surface on the feed anyway)

Usage:
    # 1. Make sure ANTHROPIC_API_KEY is set (export ... or .env file)
    # 2. Make sure schema migration has run (database_setup.py adds 3 columns)
    # 3. Dry-run first to see what will happen:
    #        python3 backfill_snippets.py --dry-run
    # 4. Run for real:
    #        python3 backfill_snippets.py
    # 5. To override the default DB path:
    #        DATABASE_PATH=/data/neshama.db python3 backfill_snippets.py
"""

import os
import sys
import time
import sqlite3
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from snippet import extract_snippet


def main(dry_run=False):
    db_path = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "neshama.db"),
    )

    if not os.path.exists(db_path):
        print(f"❌ DB not found at {db_path}")
        sys.exit(1)

    if not dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set. Export it or add to .env.")
        print("   Dry-run mode (--dry-run) doesn't need the key — only counts what would be processed.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Find obits that need a snippet:
    # - have obituary_text
    # - don't yet have a snippet
    # - aren't hidden (no point spending tokens on hidden rows)
    rows = conn.execute(
        """
        SELECT id, deceased_name, obituary_text
        FROM obituaries
        WHERE obituary_snippet IS NULL
          AND obituary_text IS NOT NULL
          AND length(obituary_text) > 80
          AND COALESCE(hidden, 0) = 0
        ORDER BY date_of_death DESC
        """
    ).fetchall()

    total = len(rows)
    print(f"\n=== Backfill snippets ({total} obits) ===")
    if dry_run:
        print("(DRY RUN — no API calls, no DB writes)\n")
    else:
        print("(LIVE — will call Anthropic API and update DB)\n")

    if total == 0:
        print("Nothing to backfill. All obits already have snippets (or none qualify).")
        return

    # Show first 3 obits we'd hit, for sanity check
    print("First 3 obits in queue:")
    for row in rows[:3]:
        preview = row["obituary_text"][:80].replace("\n", " ")
        print(f"  id={row['id']:5}  {row['deceased_name'][:30]:30}  {preview}...")

    if dry_run:
        print(f"\nDry-run complete. Would process {total} obits. Estimated cost: ~${total * 0.002:.2f}")
        return

    print(f"\nStarting in 3 seconds — Ctrl+C to abort...")
    time.sleep(3)

    succeeded = failed = empty = 0
    for i, row in enumerate(rows, 1):
        snippet = extract_snippet(row["obituary_text"])
        try:
            conn.execute(
                """
                UPDATE obituaries
                SET obituary_snippet = ?,
                    snippet_reviewed = 0,
                    snippet_generated_at = ?
                WHERE id = ?
                """,
                (snippet, datetime.utcnow().isoformat(), row["id"]),
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"  [{i:4}/{total}] id={row['id']:5}  DB write failed: {e}")
            failed += 1
            continue

        if snippet is None:
            empty += 1
            status = "(none)"
        else:
            succeeded += 1
            status = snippet[:80]

        # Progress every 25 rows + the final one
        if i % 25 == 0 or i == total:
            print(f"  [{i:4}/{total}] id={row['id']:5}  → {status}")

        # Be kind to the API — well under rate limits but no need to hammer
        time.sleep(0.3)

    print(f"\nDone. Succeeded: {succeeded}, Empty (NULL/no content): {empty}, Failed: {failed}")
    print("Run /admin/snippets queue to review pending snippets before they go live on the feed.")
    print("(Admin queue route NOT YET BUILT — will need to be added in next sprint per HANDOFF-obituaries.md.)")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    main(dry_run=dry_run)
