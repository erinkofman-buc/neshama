# Neshama System Reliability & Monitoring

## All Known Issues (as of March 12, 2026)

### CRITICAL — Fixed This Deploy
| # | Issue | Root Cause | Fix Applied | Prevention |
|---|-------|-----------|-------------|------------|
| 1 | **Database locked — scrapers dead for 3 days** | SQLite default journal mode blocks all writes during any write. No timeout = instant failure. | WAL mode + 30s busy_timeout on ALL connections (8 files). `_connect_db()` helper ensures consistency. | WAL mode persists on disk. Busy timeout retries for 30s before failing. Health watchdog alerts after 3 consecutive failures. |
| 2 | **Daily/weekly digest emails never sent** | `DailyDigestSender` created without `sendgrid_api_key` param. Falls back to `os.environ.get()` which SHOULD work, but if it doesn't, silently runs in TEST MODE with no alert. | Explicitly pass `sendgrid_api_key` in scheduler. Log ERROR (not INFO) when key missing. | Clear error logging. Watchdog checks for SendGrid key presence. |
| 3 | **Benjamin's missing 4 of 5 current funerals** | Scrapers couldn't write to locked DB for 58 hours. | DB lock fix. Scrapers will resume on deploy restart. | Scraper freshness check in `/api/health` — flags any source stale >3 hours. Alert email sent to contact@neshama.ca. |
| 4 | **Steeles missing today's funeral** | Same DB lock cause. | Same fix. | Same prevention. |

### MEDIUM — Known, Not Yet Fixed
| # | Issue | Impact | Fix Plan |
|---|-------|--------|----------|
| 5 | **No pagination on Benjamin's scraper** | Only scrapes Home.aspx (shows ~15 listings). If 20+ obituaries exist simultaneously, oldest are missed. | LOW RISK: Benjamin's rarely has >15 at once. Monitor via watchdog. If it becomes an issue, add archive page scraping. |
| 6 | **Steeles death dates all NULL** | 22 Steeles records have `name`/`date_of_death` as NULL — data stored in `deceased_name` only. | Audit Steeles scraper field mapping. May need to copy `deceased_name` → `name` in the API response. |
| 7 | **Benjamin's duplicate records** | David Kroft 3x, Sandra Halpern 2x — different name casing/formatting | Normalize name more aggressively in `generate_obituary_id()` — strip ALL-CAPS, handle "Big Daddy" nicknames. |
| 8 | **Welcome email is a stub** | After confirming subscription, user gets nothing. Only logs "Would send welcome email." | Implement actual welcome email in `subscription_manager.py` `send_welcome_email()`. |
| 9 | **Directory routing mismatch** | `directory.html` links to `/help/food/{slug}` but server routes `/directory/{slug}`. | Verify which path works in production. Add alias route if needed. |

### LOW — Cosmetic
| # | Issue | Notes |
|---|-------|-------|
| 10 | Caterer stats banner timing | `/api/directory-stats` returns correct data (18 caterers). Brief flash before data loads. |
| 11 | Gifts empty state | `/api/gift-vendors` returns 21 vendors. Possible brief empty flash on slow connections. |

---

## Monitoring Systems (Now Active)

### 1. Health Watchdog (NEW — runs in production)
- **Where**: Built into `api_server.py` as `_run_health_watchdog()`
- **When**: Every 6th scraper cycle (~2 hours) OR immediately after 3+ consecutive scraper failures
- **Checks**: DB writable, scraper freshness per source, subscriber counts, SendGrid key
- **Alert**: Sends email to contact@neshama.ca via SendGrid when issues found
- **No action needed**: Runs automatically

### 2. `/api/health` Endpoint (Enhanced)
- **URL**: https://neshama.ca/api/health
- **New check**: `scraper_freshness` — shows last scrape time per source, flags stale >3 hours
- **Returns**: 200 (all ok) or 503 (degraded) with detailed subsystem breakdown
- **Use**: Smoke tests, manual checks, external uptime monitors

### 3. `neshama_monitor.py` (NEW — manual/cron)
- **Where**: `~/Desktop/Neshama/neshama_monitor.py`
- **Run**: `python3 neshama_monitor.py`
- **Checks**: Health endpoint, obituary feed, directory stats, gift vendors, caterers, Benjamin's website comparison
- **Output**: Console report with issues/warnings
- **Use**: Run before and after deploys, or add to cron for daily check

### 4. `smoke_test.py` (Existing)
- **Where**: `~/Desktop/Neshama/smoke_test.py`
- **Run**: `python3 smoke_test.py`
- **Checks**: 42 tests covering all pages, APIs, email flows, obituary data
- **Use**: After every deploy

---

## Prevention Strategy

### Database
- **WAL mode**: Enabled permanently. Allows concurrent reads while writing. Prevents "database is locked" for read operations.
- **Busy timeout**: 30 seconds on every connection. If a write lock exists, SQLite retries for 30s before failing (was 0s = instant fail).
- **Single writer discipline**: Scrapers run sequentially via `master_scraper.py` (not parallel). API writes are short-lived.

### Scrapers
- **Freshness monitoring**: Health endpoint flags any source stale >3 hours
- **Failure tracking**: Consecutive failure counter triggers watchdog immediately at 3+ fails
- **Alert email**: contact@neshama.ca gets notified of persistent scraper failures
- **Shabbat pause**: Friday 6 PM – Saturday 9 PM (intentional, not a bug)

### Email System
- **Explicit API key passing**: Daily/weekly digest now receives SendGrid key explicitly, not via env var fallback
- **Clear error logging**: "TEST MODE" logged as ERROR level (visible in Render logs)
- **Auto-confirm safety net**: Subscribers unconfirmed after 48h are auto-confirmed (catches spam-filtered confirmation emails)

### Deploys
- **Pre-deploy**: Run `python3 smoke_test.py` (tests against production)
- **Post-deploy**: Run `python3 neshama_monitor.py` (comprehensive health check)
- **Render auto-deploy**: Pushes to `main` trigger automatic deployment
- **Persistent disk**: DB at `/data/neshama.db` survives restarts

---

## Recommended Additions (Future)

### Short Term (Before Launch Mar 24)
1. **External uptime monitor**: Set up free UptimeRobot or Better Uptime to ping `/api/health` every 5 minutes. Alerts via SMS/email if site goes down.
2. **Daily monitor cron**: Add `neshama_monitor.py` to launchd (like daily briefing) — run at 8 AM, email results.
3. **Fix Steeles field mapping**: Ensure `name` and `date_of_death` are populated, not just `deceased_name`.

### Medium Term (Month 1-2)
4. **SendGrid bounce webhook**: Process bounced/spam emails to maintain sender reputation.
5. **Scraper dashboard page**: `/admin/scrapers` showing last run time, success/fail, obituary counts per source.
6. **Database backup verification**: Weekly check that Sunday 3 AM backup email actually arrives.
7. **Render auto-restart on unhealthy**: Configure Render health check to restart service if `/api/health` returns 503 for 5+ minutes.

### Long Term
8. **Move from SQLite to PostgreSQL**: Eliminates all locking issues. Render offers managed Postgres. Migration path: export → import, update connection strings.
9. **Structured logging**: Ship logs to a service (Logtail, Papertrail) for searchable history and alerting rules.
10. **Error tracking**: Sentry or similar — automatic alerts for unhandled exceptions.

---

## Quick Reference

| What | Command |
|------|---------|
| Check production health | `python3 ~/Desktop/Neshama/neshama_monitor.py` |
| Run smoke tests | `python3 ~/Desktop/Neshama/smoke_test.py` |
| Check health API | `curl https://neshama.ca/api/health \| python3 -m json.tool` |
| Check scraper freshness | `curl https://neshama.ca/api/health \| python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'{k}: {v}') for k,v in d.get('checks',{}).get('scraper_freshness',{}).get('sources',{}).items()]"` |
| Trigger manual scrape | `curl "https://neshama.ca/admin/scrape?key=$ADMIN_SECRET"` |
| Check subscriber count | `curl https://neshama.ca/api/subscribers/count` |
| View Render logs | Render Dashboard > neshama service > Logs |
