# Neshama Daily Operations Runbook

## Daily (< 2 min)

1. Open `https://neshama.ca/api/health` — should say `"status": "ok"`
2. Check email for daily digest (should arrive by 7:30 AM ET)
3. Check email for health summary (arrives right after digest)
4. If anything red: use emergency commands below

## Emergency Commands

```bash
# Check scraper thread status
curl "https://neshama.ca/api/scraper-thread"

# Unlock stuck database
curl "https://neshama.ca/admin/unlock-db?key=ADMIN_SECRET"

# Force a scrape cycle
curl "https://neshama.ca/admin/scrape?key=ADMIN_SECRET"

# Manually send daily digest
curl "https://neshama.ca/admin/digest?key=ADMIN_SECRET"

# Download database backup
curl "https://neshama.ca/admin/backup?key=ADMIN_SECRET" -o backup.json
```

Replace `ADMIN_SECRET` with the actual admin key from Render env vars.

## Weekly

- Verify Sunday backup email arrived
- Check subscriber count: `curl "https://neshama.ca/api/subscribers/count"`
- Review scraper output for errors in Render logs

## Monthly

- Review Render billing ($7/mo Starter plan)
- Check SendGrid reputation dashboard
- Verify DNS records (Squarespace Domains) haven't changed
- Review ImprovMX forwarding (contact@neshama.ca -> Gmail)

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/health` | Full system health check |
| `/api/scraper-thread` | Scraper thread heartbeat + cycle count |
| `/api/status` | Basic API status |
| `/api/subscribers/count` | Active subscriber count |
| `/api/community-stats` | Obituary + community stats |

## Architecture Notes

- **Hosting**: Render.com (Starter, $7/mo) with 1GB persistent disk at `/data`
- **Database**: SQLite at `/data/neshama.db`
- **Email**: SendGrid (updates@neshama.ca)
- **Inbound email**: ImprovMX (contact@neshama.ca -> Gmail)
- **DNS**: Squarespace Domains
- **Deploys**: Auto from GitHub main branch
- **Scraper interval**: Every ~20 min, paused during Shabbat
- **Health watchdog**: Runs every 6th scraper cycle (~2 hours)
