#!/bin/bash
#
# Weekly off-box backup for Neshama.
#
# Pulls /data/backup.db.gz off the Render disk to this Mac and keeps the last 4.
# This exists because the only working backup mechanism lives on the SAME Render
# disk as the database it protects (see decisions-log 2026-08-26). A disk loss
# takes both. This job is the off-box copy.
#
# No secrets. Authentication is the SSH key already registered on the Render
# account; nothing is read from disk, pasted, or logged.
#
# Install:  cp tools/neshama-backup-pull.sh ~/Neshama-backups/neshama-backup-pull.sh
#           launchctl load ~/Library/LaunchAgents/ca.neshama.backup.plist
# Run now:  bash ~/Neshama-backups/neshama-backup-pull.sh
# Check a local file only (no SSH):
#           bash ~/Neshama-backups/neshama-backup-pull.sh --verify FILE.db
# Logs:     ~/Neshama-backups/backup.log
#
# CHANGED 2026-09-22: the server now writes a gzipped SQLite copy
# (backup.db.gz, made with SQLite's online backup API) instead of backup.json.
# The JSON export was a suspect in the 2026-09-20 OOM restart, and
# /data/backup.json had been stuck at 2026-09-18 for four days while this job
# kept logging OK on the stale copy. So a pull now also has to prove it is
# FRESH: the copy carries its own exported_at in a _backup_meta table, and
# anything older than MAX_AGE_HOURS fails loudly.

set -uo pipefail

REMOTE="srv-d64g2rsr85hc73brjot0@ssh.oregon.render.com"
REMOTE_FILE="/data/backup.db.gz"
DEST_DIR="${NESHAMA_BACKUP_DIR:-$HOME/Neshama-backups}"
KEEP=4
MAX_AGE_HOURS=26
LOG="$DEST_DIR/backup.log"
STAMP="$(date +%Y%m%d-%H%M)"
TARGET="$DEST_DIR/neshama-backup-$STAMP.db"

mkdir -p "$DEST_DIR"
chmod 700 "$DEST_DIR"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }

# A failed backup is renamed to *.db.failed so it is kept for inspection but
# never matches neshama-backup-*.db, and so can never count toward KEEP and
# push a good copy out during pruning.
keep_failed() {
    mv -f "$1" "$1.failed" 2>/dev/null
    log "KEEPING $1.failed for inspection"
}

# Print the age in hours of the backup's exported_at (UTC ISO-8601 with an
# offset), followed by the raw value. Prints "missing" if there is no usable
# timestamp. python3 does the date math because macOS date is BSD date.
backup_age() {
    python3 - "$1" <<'PY' 2>>"$LOG"
import sqlite3, sys
from datetime import datetime, timezone
try:
    con = sqlite3.connect(sys.argv[1])
    row = con.execute("SELECT value FROM _backup_meta WHERE key = 'exported_at'").fetchone()
    ts = datetime.fromisoformat(row[0])
    if ts.tzinfo is None:
        raise ValueError("exported_at has no UTC offset")
    age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    print(f"{age:.1f} {row[0]}")
except Exception:
    print("missing")
PY
}

# Verify a decompressed backup is a real, fresh backup: not a truncated
# transfer, not an error page, not a stale copy. A file that exists is not a
# backup; a file that passes integrity_check, contains obituaries and was
# exported within MAX_AGE_HOURS is.
verify_backup() {
    local file="$1"
    local size integrity count age_line age exported_at
    size=$(stat -f%z "$file" 2>/dev/null || echo 0)

    integrity=$(sqlite3 -readonly "$file" "PRAGMA integrity_check" 2>>"$LOG" | head -n 1)
    if [ "$integrity" != "ok" ]; then
        log "FAIL $file integrity_check returned '${integrity:-nothing}' (size=$size)"
        return 1
    fi

    count=$(sqlite3 -readonly "$file" "SELECT COUNT(*) FROM obituaries" 2>>"$LOG")
    if ! [ "$count" -ge 1 ] 2>/dev/null; then
        log "FAIL $file has no obituaries (count=${count:-none}, size=$size)"
        return 1
    fi

    age_line=$(backup_age "$file")
    if [ "$age_line" = "missing" ] || [ -z "$age_line" ]; then
        log "FAIL $file has no exported_at in _backup_meta (size=$size)"
        return 1
    fi
    age=${age_line%% *}
    exported_at=${age_line#* }
    if ! python3 -c "import sys; sys.exit(0 if float(sys.argv[1]) <= float(sys.argv[2]) else 1)" "$age" "$MAX_AGE_HOURS"; then
        log "FAIL $file is STALE: exported_at=$exported_at is ${age}h old (limit ${MAX_AGE_HOURS}h). The server has stopped refreshing backup.db.gz."
        return 1
    fi

    log "OK   $file  size=$size  obituaries=$count  exported_at=$exported_at  age=${age}h"
    return 0
}

if [ "${1:-}" = "--verify" ]; then
    if [ -z "${2:-}" ]; then
        echo "usage: $0 --verify FILE.db" >&2
        exit 2
    fi
    log "VERIFY $2"
    verify_backup "$2"
    exit $?
fi

log "START pulling $REMOTE_FILE"

# The server already writes it gzipped, so just stream it down the SSH
# connection. No server-side gzip, no scp, no copy left in /tmp on the server.
if ! ssh -o BatchMode=yes -o ConnectTimeout=30 "$REMOTE" \
     "cat $REMOTE_FILE" > "$DEST_DIR/nb-$STAMP.gz" 2>>"$LOG"; then
    log "FAIL could not pull from the server. Is the SSH key still registered? Does $REMOTE_FILE exist yet?"
    rm -f "$DEST_DIR/nb-$STAMP.gz"
    exit 1
fi

# A failed remote command can still exit 0 while producing an empty stream.
if [ ! -s "$DEST_DIR/nb-$STAMP.gz" ]; then
    log "FAIL transfer produced an empty file"
    rm -f "$DEST_DIR/nb-$STAMP.gz"
    exit 1
fi

if ! gunzip -t "$DEST_DIR/nb-$STAMP.gz" 2>>"$LOG"; then
    log "FAIL gunzip -t says the transfer is not a valid gzip (truncated?)"
    rm -f "$DEST_DIR/nb-$STAMP.gz"
    exit 1
fi

if ! gunzip -c "$DEST_DIR/nb-$STAMP.gz" > "$TARGET" 2>>"$LOG"; then
    log "FAIL gunzip failed"
    rm -f "$DEST_DIR/nb-$STAMP.gz" "$TARGET"
    exit 1
fi
rm -f "$DEST_DIR/nb-$STAMP.gz"
chmod 600 "$TARGET"

if ! verify_backup "$TARGET"; then
    keep_failed "$TARGET"
    exit 1
fi

# Retain the last KEEP verified backups. Deletes by newest-first ordering rather
# than by age, so a run of failures can never delete the last good copy.
cd "$DEST_DIR" || exit 1
ls -t neshama-backup-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f "$old" && log "PRUNE removed $old"
done

log "DONE  $(ls -1 neshama-backup-*.db 2>/dev/null | wc -l | tr -d ' ') backup(s) retained"
