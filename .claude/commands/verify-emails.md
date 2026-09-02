---
description: Self-check the digest email path before merging anything that touches it
---

# /verify-emails

Self-check everything that reaches a subscriber's inbox. Run this **before
merging any change that touches the digest path** - the scrapers, the obituary
identity, `field_hygiene`, `daily_digest.py`, `weekly_digest.py`, or the health
report.

## Run it

```bash
cd ~/Desktop/Neshama && python3 tools/verify_emails.py
```

Add `--open` to open the rendered sample digest in a browser, or `--quiet` for
the verdict only.

## What it does

1. Runs the digest test suite (`test_dedup_key`, `test_digest_placeholders`,
   `test_digest_subscriber_guard`, `test_scraper_freshness`, `test_email_queue`).
   Test files that are not on the current branch are skipped, not failed, so
   this works before all four sprint branches have landed.
2. Renders a real digest from fixtures, one per defect that has actually shipped
   to Erin's inbox, plus a clean control.
3. Scans the rendered HTML **and** the plain-text alternative for known junk, and
   checks that real content still survives.

Everything runs offline. It never touches production, never sends mail, and
needs no SendGrid key.

## Reading the result

- `VERIFY-EMAILS: PASS` - safe to merge as far as email output is concerned.
- `VERIFY-EMAILS: FAIL - do not merge` - the failing line names either a
  placeholder that leaked or a real value that was suppressed. Both are bugs.
  Suppressing real detail is as bad as printing junk.

## After it passes

`/verify-emails` only checks what the code *renders*. It does not check what
production actually *sent*. After a deploy that touches the digest, confirm the
next real send:

```bash
curl -s https://neshama.ca/api/digest-status | python3 -m json.tool
```

Expect one `ran_at` per day, with `subscribers_sent` matching the active
subscriber count in `/api/health`. Two runs in one day, or a run reporting
`subscribers_sent: 0` while `/api/health` shows active subscribers, means a
second deployment is running the digest - check the `[Neshama Health]` INSTANCE
line to see which.

## When to extend it

Whenever a new junk pattern reaches a real inbox, add the exact string a reader
saw to `FORBIDDEN` in `tools/verify_emails.py`, and add a fixture that produces
it. That list is a record of defects that have actually shipped; keep it that way
rather than filling it with hypotheticals.

## Background

Four defects reached real inboxes in August 2026 and none were caught before
Erin read them: a person announced as new in two consecutive digests, section
labels rendered as data ("Shiva: Shiva Location", "Burial: Dawes Road Cemetery"),
a doubled non-answer ("Shiva: Address: Shiva details to follow; Shiva details to
follow"), and two health reports five seconds apart with one reading all zeros.
Full write-ups are in `HQ/01-Projects/Neshama/decisions-log.md` under 2026-09-02.
