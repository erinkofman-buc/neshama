#!/usr/bin/env python3
"""
Benjamin's Park Memorial Chapel: ingest the funeral home's own listing e-mail.

Why this exists (decisions-log 2026-09-15). Benjamin's rebuilt their site in
August 2026 and Cloudflare now serves a managed challenge to every datacenter
network we can run from (Render's Oregon IP and GitHub-hosted runners both got
HTTP 403 / cf-mitigated: challenge on 2026-09-15). We do not evade that. What
Benjamin's does publish to anyone who asks is a twice-daily "Listing Summary"
e-mail, sent to every address entered in the "Funeral email listings" form on
their home page. This module reads that e-mail from a dedicated mailbox over
IMAP, parses it, and hands rows to the same source_key / upsert path every
other scraper uses. No request is ever made to Benjamin's web site.

What the e-mail contains, and the rules that follow from it:

  * LISTINGS: a date heading per day, then one row per service: the name as
    "Last, First", an info line ("11:30 am, Chapel", "12:00 pm, Beth Tzedec
    Memorial Park", "Service in Montreal.", "Please monitor this website for
    updates."), sometimes a photo, and a "(details)" link carrying the service
    number (snum). Rows WITHOUT a details link are other funeral homes'
    services carried as a courtesy ("Chapel at Steeles", "Bathurst Lawn
    Memorial Park, 11:00 AM") and are SKIPPED; the Steeles and Paperman
    scrapers bring those in.
  * SHIVA: the same name and details link, with the shiva address as the info
    line. Rows here may belong to funerals that already passed.
  * UNVEILING: not obituaries; ignored.

Two hazards handled here:

  1. Quoted-printable. Benjamin's encodes the mail as quoted-printable but
     leaves the "=" in "snum=142306" unescaped, so a standards-compliant
     decoder reads "=14" as byte 0x14 and the link arrives as "snum\\x142306".
     For mail we receive directly, repair_quoted_printable() escapes those
     "=" signs BEFORE decoding. For mail forwarded from another client (Erin's
     back-fill of the archive), the damage is already baked in and
     recover_snum() rebuilds the number from the stray byte.
  2. Field loss. The newsletter carries fewer fields than a details page
     (no death date, no notice text, no Hebrew name). upsert_obituary()
     overwrites every column from the dict it is given, so each row is merged
     against the existing row first and only fields the newsletter actually
     carries are overridden. Existing data is never blanked.

Environment (Render):
  BENJAMINS_IMAP_HOST      default imap.gmail.com
  BENJAMINS_IMAP_USER      the dedicated mailbox address
  BENJAMINS_IMAP_PASSWORD  an app password for that mailbox only
  BENJAMINS_IMAP_FOLDER    default INBOX

Cadence: the api_server scheduler runs this once every 4 hours. Any failure
skips the cycle and is logged; nothing retries inside the window.
"""

import email
import email.policy
import imaplib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database_setup import NeshamaDatabase  # noqa: E402
from obituary_identity import source_key as compute_source_key  # noqa: E402

SOURCE_NAME = "Benjamin's Park Memorial Chapel"
CHAPEL_NAME = "Benjamin's Park Memorial Chapel"
SUBJECT_MARK = "Park Memorial Chapel:"
DETAILS_URL = "https://benjaminsparkmemorialchapel.ca/ServiceDetails?snum={snum}"
LOG_STATUS = "newsletter"          # scraper_log.status for an ingested issue
FRESHNESS_HOURS = 24               # two issues a day; older than this is stale

ENV_HOST = "BENJAMINS_IMAP_HOST"
ENV_USER = "BENJAMINS_IMAP_USER"
ENV_PASSWORD = "BENJAMINS_IMAP_PASSWORD"
ENV_FOLDER = "BENJAMINS_IMAP_FOLDER"

# Fields the newsletter can carry. Anything else on an existing row is kept.
NEWSLETTER_FIELDS = (
    "deceased_name", "source_url", "funeral_datetime", "funeral_location",
    "photo_url", "shiva_info", "shiva_address",
)


# ── Quoted-printable repair ──────────────────────────────────────────────────

def repair_quoted_printable(text):
    """Escape the '=' Benjamin's leaves bare in 'snum=NNNNNN' inside a
    quoted-printable body, so the standard decoder keeps the digits.

    A correctly encoded link reads 'snum=3D142306' and is left alone.
    """
    if isinstance(text, bytes):
        return re.sub(rb"snum=(?!3D)(?=\d)", b"snum=3D", text)
    return re.sub(r"snum=(?!3D)(?=\d)", "snum=3D", text)


def recover_snum(href):
    """Return the service number from a details link, intact or damaged.

    'snum=142306'        -> '142306'
    'snum\\x142306'       -> '142306'  (decoder ate '=14' into byte 0x14)
    'snum\\x874824'       -> '874824'  (any byte below 0x100 restores two digits)
    """
    if not href:
        return None
    m = re.search(r"snum(?:=|%3[dD])(\d+)", href)
    if m:
        return m.group(1)
    m = re.search(r"snum([^\d&\s=])(\d+)", href)
    if m and ord(m.group(1)) < 0x100:
        return "%02X" % ord(m.group(1)) + m.group(2)
    return None


# ── MIME handling ───────────────────────────────────────────────────────────

def html_from_message(raw_bytes):
    """Extract the HTML body from a raw RFC822 message, repairing the
    quoted-printable damage first. Returns (html, subject, sent_at)."""
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    subject = str(msg.get("Subject", "") or "")
    sent_at = None
    try:
        sent_at = parsedate_to_datetime(msg.get("Date"))
    except Exception:
        sent_at = None
    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        cte = (part.get("Content-Transfer-Encoding", "") or "").lower().strip()
        if cte == "quoted-printable":
            payload = part.get_payload(decode=False)
            part.set_payload(repair_quoted_printable(payload))
        data = part.get_payload(decode=True)
        charset = part.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace"), subject, sent_at
    return None, subject, sent_at


# ── Parsing ─────────────────────────────────────────────────────────────────

_TIME_FIRST = re.compile(r"^\s*(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\s*,\s*(.+?)\s*$", re.I)
_PLACE_FIRST = re.compile(r"^\s*(.+?)\s*,\s*(\d{1,2}:\d{2}\s*[ap]\.?m\.?)\s*$", re.I)
_MONITOR = re.compile(r"please monitor this website", re.I)


def display_name(listed):
    """'Bean, Sharon' -> 'Sharon Bean'; 'Kosoy (Nakelsky), Jodi Sheryl' ->
    'Jodi Sheryl Kosoy (Nakelsky)'; 'Wolfe, Q.C./K.C., Morley S.' ->
    'Morley S. Wolfe, Q.C./K.C.'. A name with no comma is returned as is."""
    parts = [p.strip() for p in (listed or "").split(",") if p.strip()]
    if len(parts) < 2:
        return " ".join((listed or "").split())
    last, first, middle = parts[0], parts[-1], parts[1:-1]
    name = f"{first} {last}"
    if middle:
        name += ", " + ", ".join(middle)
    return " ".join(name.split())


def _heading_date(text):
    """'Monday September 14, 2026' -> 'September 14, 2026' (matches the
    format the details-page scraper stored in funeral_datetime)."""
    t = " ".join((text or "").split())
    m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", t)
    return m.group(1) if m else t or None


def _funeral_fields(date_text, info):
    """Split an info line into (funeral_datetime, funeral_location)."""
    info = " ".join((info or "").split())
    if not info or _MONITOR.search(info):
        return date_text, None
    m = _TIME_FIRST.match(info)
    if m:
        t, place = m.group(1), m.group(2)
    else:
        m = _PLACE_FIRST.match(info)
        if m:
            place, t = m.group(1), m.group(2)
        else:
            return date_text, info
    if place.strip().rstrip(".").lower() == "chapel":
        place = CHAPEL_NAME
    when = f"{date_text} at {t.lower().replace(' ', '')}" if date_text else t
    return when, place


def _rows_of(table):
    """Yield (kind, payload) for a listing table: ('date', text) for a heading
    row, ('row', dict) for a service row."""
    for tr in table.find_all("tr", recursive=False):
        heading = tr.find("div", class_="style3")
        if heading is not None:
            yield "date", heading.get_text(" ", strip=True)
            continue
        name = tr.find("span", class_="name")
        if name is None:
            continue
        info = tr.find("span", class_="info")
        link = None
        for a in tr.find_all("a", href=True):
            if "snum" in a["href"]:
                link = a["href"]
                break
        img = tr.find("img")
        yield "row", {
            "listed_name": name.get_text(" ", strip=True),
            "info": info.get_text(" ", strip=True) if info else "",
            "href": link,
            "snum": recover_snum(link) if link else None,
            "photo_url": img["src"] if img and img.get("src") else None,
        }


def parse_issue(html):
    """Parse one Listing Summary e-mail into obituary dicts.

    Returns {'issue_label', 'rows', 'skipped_courtesy', 'shiva'} where rows are
    ready for upsert (after merge_preserving) and shiva maps snum -> address.
    """
    soup = BeautifulSoup(html, "html.parser")
    label = None
    summary = soup.find("p", class_="listingSummary")
    if summary is not None:
        label = summary.get_text(" ", strip=True).replace("Listing Summary:", "").strip()

    # SHIVA section first, so listing rows can carry their shiva line.
    shiva = {}
    shiva_note = None
    anchor = soup.find("a", attrs={"name": "shiva"})
    if anchor is not None:
        table = anchor.find_next("table")
        heading_between = anchor.find_next("a", attrs={"name": "unveiling"})
        if table is not None and (heading_between is None or _precedes(table, heading_between)):
            for kind, row in _rows_of(table):
                if kind == "row" and row["snum"]:
                    shiva[row["snum"]] = {"address": row["info"] or None,
                                          "listed_name": row["listed_name"],
                                          "photo_url": row["photo_url"]}
            note = table.find_next("div")
            if note is not None and "visiting times" in note.get_text(" ", strip=True).lower():
                shiva_note = note.get_text(" ", strip=True).lstrip("* ").strip()

    rows, skipped = [], 0
    seen = set()
    anchor = soup.find("a", attrs={"name": "listings"})
    table = anchor.find_next("table") if anchor is not None else None
    current_date = None
    if table is not None:
        for kind, row in _rows_of(table):
            if kind == "date":
                current_date = _heading_date(row)
                continue
            if not row["href"]:
                skipped += 1            # courtesy listing for another home
                continue
            if not row["snum"]:
                logging.warning(f"[Benjamins newsletter] unreadable details link, row skipped: {row['href']!r}")
                continue
            when, where = _funeral_fields(current_date, row["info"])
            rows.append(_make_row(row["snum"], row["listed_name"], when, where,
                                  row["photo_url"], shiva.get(row["snum"]), shiva_note))
            seen.add(row["snum"])

    # Shiva rows whose funeral is no longer listed still belong to Benjamin's.
    for snum, sh in shiva.items():
        if snum in seen:
            continue
        rows.append(_make_row(snum, sh["listed_name"], None, None, sh["photo_url"], sh, shiva_note))

    return {"issue_label": label, "rows": rows, "skipped_courtesy": skipped, "shiva": shiva}


def _precedes(a, b):
    """True when tag a appears before tag b in document order."""
    for el in a.parents:
        pass
    return a.sourceline is None or b.sourceline is None or (a.sourceline, a.sourcepos) < (b.sourceline, b.sourcepos)


def _make_row(snum, listed_name, when, where, photo_url, shiva_entry, shiva_note):
    url = DETAILS_URL.format(snum=snum)
    row = {
        "source": SOURCE_NAME,
        "source_url": url,
        "condolence_url": url,          # required by the insert path; same page
        "deceased_name": display_name(listed_name),
        "funeral_datetime": when,
        "funeral_location": where,
        "photo_url": photo_url,
    }
    if shiva_entry and shiva_entry.get("address"):
        addr = shiva_entry["address"]
        row["shiva_address"] = addr
        row["shiva_info"] = f"Shiva at {addr}." + (f" {shiva_note}" if shiva_note else "")
    return row


# ── Merge + upsert ──────────────────────────────────────────────────────────

def merge_preserving(existing, new_row):
    """Return the dict to upsert: the existing row's columns, with only the
    fields the newsletter carries (and actually has a value for) overridden.
    With no existing row, the newsletter row is used as is."""
    if not existing:
        return dict(new_row)
    merged = {k: existing[k] for k in existing.keys()}
    merged["source"] = SOURCE_NAME
    for field in NEWSLETTER_FIELDS:
        value = new_row.get(field)
        if value not in (None, ""):
            merged[field] = value
    # A row that already has a shiva address from the details page keeps it;
    # the newsletter never removes a shiva line, only adds one.
    return merged


def ingest_rows(db, rows):
    """Upsert parsed rows through the shared path. Returns (new, updated)."""
    new = updated = 0
    for row in rows:
        key = compute_source_key(SOURCE_NAME, row["source_url"])
        db.connect()
        cur = db.cursor
        cur.execute("SELECT * FROM obituaries WHERE source_key = ? ORDER BY first_seen ASC LIMIT 1", (key,))
        hit = cur.fetchone()
        existing = None
        if hit is not None:
            cols = [d[0] for d in cur.description]
            existing = dict(zip(cols, hit))
        db.close()
        # upsert_obituary returns (row_id, action); action is 'inserted' for a
        # brand-new service and 'updated' (or similar) for an in-place update.
        result = db.upsert_obituary(merge_preserving(existing, row))
        action = result[1] if isinstance(result, (tuple, list)) and len(result) > 1 else str(result)
        if "insert" in str(action).lower():
            new += 1
        else:
            updated += 1
    return new, updated


def record_issue(db, issue_label, sent_at, found, new, updated):
    """scraper_log row whose run_time is the ISSUE's own send time, so the
    health report can measure the age of the newest issue directly."""
    when = (sent_at or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    db.connect()
    db.cursor.execute(
        """INSERT INTO scraper_log (source, run_time, status, obituaries_found,
                                    new_obituaries, updated_obituaries, error_message, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (SOURCE_NAME, when, LOG_STATUS, found, new, updated, f"issue={issue_label}", None),
    )
    db.conn.commit()
    db.close()


# ── IMAP ────────────────────────────────────────────────────────────────────

def fetch_unseen_issues(host, user, password, folder="INBOX", limit=5):
    """Return [(uid, raw_bytes)] for unseen listing e-mails, oldest first, and
    a callable that marks a uid seen. One connection, no retries."""
    conn = imaplib.IMAP4_SSL(host, 993, timeout=60)
    conn.login(user, password)
    conn.select(folder)
    typ, data = conn.uid("search", None, "UNSEEN", "SUBJECT", f'"{SUBJECT_MARK}"')
    uids = data[0].split() if typ == "OK" and data and data[0] else []
    uids = uids[-limit:]
    issues = []
    for uid in uids:
        typ, msgdata = conn.uid("fetch", uid, "(RFC822)")
        if typ == "OK" and msgdata and msgdata[0]:
            issues.append((uid, msgdata[0][1]))

    def mark_seen(uid):
        conn.uid("store", uid, "+FLAGS", "(\\Seen)")

    def close():
        try:
            conn.logout()
        except Exception:
            pass

    return issues, mark_seen, close


# ── Entry point ─────────────────────────────────────────────────────────────

def process_raw_issue(db, raw_bytes):
    """Parse and ingest one raw message. Returns the stats dict."""
    html, subject, sent_at = html_from_message(raw_bytes)
    if not html or SUBJECT_MARK not in subject:
        return {"skipped": True, "subject": subject}
    parsed = parse_issue(html)
    new, updated = ingest_rows(db, parsed["rows"])
    record_issue(db, parsed["issue_label"], sent_at, len(parsed["rows"]), new, updated)
    return {"issue_label": parsed["issue_label"], "found": len(parsed["rows"]),
            "new": new, "updated": updated, "skipped_courtesy": parsed["skipped_courtesy"]}


def run_from_env(db_path=None, limit=5):
    """One poll: read unseen issues, ingest, mark seen. Never retries."""
    host = os.environ.get(ENV_HOST, "imap.gmail.com")
    user = os.environ.get(ENV_USER)
    password = os.environ.get(ENV_PASSWORD)
    folder = os.environ.get(ENV_FOLDER, "INBOX")
    if not user or not password:
        logging.info(f"[Benjamins newsletter] {ENV_USER}/{ENV_PASSWORD} not set; poll skipped")
        return {"skipped": True, "reason": "no credentials"}

    started = time.time()
    db = NeshamaDatabase(db_path) if db_path else NeshamaDatabase()
    totals = {"issues": 0, "found": 0, "new": 0, "updated": 0, "skipped_courtesy": 0}
    try:
        issues, mark_seen, close = fetch_unseen_issues(host, user, password, folder, limit)
    except Exception as e:
        logging.error(f"[Benjamins newsletter] IMAP failed, cycle skipped: {e}")
        db.log_scraper_run(SOURCE_NAME, "error", None, error=f"newsletter imap: {e}", duration=time.time() - started)
        return {"error": str(e)}
    try:
        for uid, raw in issues:
            try:
                stats = process_raw_issue(db, raw)
            except Exception as e:
                logging.error(f"[Benjamins newsletter] issue uid={uid!r} failed, left unseen: {e}")
                continue
            if stats.get("skipped"):
                mark_seen(uid)
                continue
            totals["issues"] += 1
            for k in ("found", "new", "updated", "skipped_courtesy"):
                totals[k] += stats[k]
            mark_seen(uid)
            logging.info(f"[Benjamins newsletter] {stats['issue_label']}: {stats['found']} rows, "
                         f"{stats['new']} new, {stats['updated']} updated, {stats['skipped_courtesy']} courtesy skipped")
    finally:
        close()
    logging.info(f"[Benjamins newsletter] poll done in {time.time() - started:.1f}s: {totals}")
    return totals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print(run_from_env())
