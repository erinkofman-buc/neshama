# V2 Shiva Coordination — Handoff Notes
> For the next Claude session to pick up where we left off
> Date: 2026-02-26

## Current State
- **Branch:** `main` at commit `2bf7b7a` (clean, pushed)
- **Sprint 5:** Fully shipped and deployed on Render
- **Codebase audit:** Complete. 5 of 10 issues fixed (commits a62dfa0, 2bf7b7a)
- **Data model:** DESIGNED and APPROVED — saved in `docs/v2-data-model.md`
- **No v2 code written yet** — data model is the starting point

## What's Been Done This Session
1. Seeded 11 gift basket vendors (commit a48acf0)
2. Created robots.txt, fixed sitemap.xml for SEO/Google Search Console
3. Full production codebase audit (Python + HTML/JS)
4. Fixed 5 bugs: shiva_address crash, bare except, console.error leaks, alert text
5. Added caterer location filtering by city on /shiva/organize (commit 2bf7b7a)
6. Read PRD (~/Downloads/neshama-shiva-prd.docx) and designed v2 data model

## Next Steps (in order)
1. **Implement v2 migrations** in `shiva_manager.py` setup_database()
   - 7 new columns on shiva_support
   - 5 new columns on meal_signups
   - New table: shiva_co_organizers
   - New table: email_log
2. **Build email scheduling system** — replace fire-and-forget threads with email_log + cron
3. **Co-organizer invite flow** — endpoints + email + auth check update
4. **Multi-date signup** — signup_group_id + grouped confirmation email
5. **Verification flow** — token generation + verification endpoint
6. **Frontend updates** — drop-off instructions, notification toggles, co-admin UI

## Key Files
- `frontend/shiva_manager.py` — Core backend (1,423 lines), all DB logic
- `frontend/api_server.py` — HTTP server + all API endpoints (2,515+ lines)
- `frontend/shiva-organize.html` — 3-step wizard form (~68KB)
- `docs/v2-data-model.md` — The approved data model design
- `~/Downloads/neshama-shiva-prd.docx` — Original PRD

## Remaining Audit Issues (not yet fixed)
- #2 MEDIUM: cloudscraper pip package missing for uhmc_scraper.py
- #3 MEDIUM: fire-and-forget daemon threads for emails (will be fixed by v2 email_log)
- #6 LOW: print statements should use logging module
- #7 LOW: DB migration except clauses too broad

## Google Search Console
- robots.txt and sitemap.xml are ready
- DNS TXT record verification instructions were provided to Erin
- Manual step: Erin needs to add TXT record in Squarespace DNS
