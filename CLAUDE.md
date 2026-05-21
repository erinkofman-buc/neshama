# Neshama Project

---
## Brand enforcement (mandatory)

Before any edit, write, review, draft, or deploy of Neshama content, read `.claude/skills/neshama-brand-check/SKILL.md` and follow it in full. This applies to code, copy, HTML, Markdown, social, email, lead magnets, and demo assets.

The skill enforces BRAND.md (canonical, locked 2026-05-10). It catches em-dashes (literal and HTML-entity), emojis (literal and HTML-entity), font guard violations, and tagline drift.

Do not rely on skill auto-load. Load this skill on the first turn of every Neshama session.

---

## Architecture
- Python/SQLite backend (api_server.py + shiva_manager.py)
- Static HTML/CSS/JS frontend (no framework)
- Deployed on Render with auto-deploy from GitHub main branch
- Database: SQLite at local path (MUST persist across deploys)
- Email: SendGrid
- Payments: Stripe (test mode, not activated)

## Design System
- Fonts: Cormorant Garamond (headings), Crimson Pro (body)
- Colors: terracotta (#D2691E), cream (#FFF8F0), sage, dark brown (#3E2723)
- Tone: warm, empathetic, community-focused. Never clinical or corporate.
- All emails must feel warm, human, and dignified. White background, clean typography, no emoji bullets, no dark mode templates. This platform serves people who are grieving — every touchpoint should feel like it came from a caring person, not a bot.

## Current Features
- Obituary feed (scraped from funeral homes daily)
- Memorial pages with tributes
- Shiva meal coordination (organizer wizard + volunteer signup)
- Caterer directory with partner application system
- Shiva guide content page
- PWA support
- Analytics tracking

## Repository Structure (updated Mar 12, 2026)
```
~/Desktop/Neshama/
├── frontend/           ← ALL HTML pages, api_server.py, backend .py, static assets, sitemap.xml
├── marketing-kit/      ← Outreach kits, email drafts, contact lists, graphics
│   ├── jordana/        ← Jordana's share kit + WhatsApp card
│   ├── montreal/       ← Montreal share kit
│   ├── general/        ← One-pager, profile photo, synagogue outreach
│   ├── instagram-stories/ ← Story graphics (1080x1920)
│   ├── whatsapp/       ← WhatsApp share cards
│   ├── vendor-drafts/  ← Individual vendor email drafts
│   ├── synagogue-drafts/ ← Individual synagogue email drafts
│   ├── JORDANA-OUTREACH-KIT.md + .pdf  ← Master outreach kit
│   ├── synagogue-contacts.md  ← 17 synagogue contacts
│   └── vendor-emails-collected.md  ← 40 vendor emails
├── instagram-posts/    ← All IG feed graphics (1080x1080) + carousel subfolders
├── outscraper_pipeline/ ← Vendor data sourcing scripts + CSVs
├── docs/               ← Reference docs (UX review, deploy guide, ops manual, reliability)
├── archive/            ← Old/one-time scripts (generators, migrations, utilities)
├── fonts/              ← Brand fonts (gitignored)
├── tests/              ← Playwright e2e tests
├── *_scraper.py        ← Active scrapers (steeles, benjamins, paperman, misaskim)
├── master_scraper.py   ← Scraper orchestrator
├── database_setup.py   ← SQLite schema
├── seed_vendors.py     ← Vendor seed data (imported by api_server.py — do NOT move)
└── render.yaml         ← Render deploy config
```

**Where to find things:**
- Code & pages → `frontend/`
- Marketing anything → `marketing-kit/`
- Instagram graphics → `instagram-posts/`
- Old scripts → `archive/`
- Strategy & plans → Obsidian `01-Projects/Neshama/`
- Agent config → `~/agents/neshama/`

## Key Rules
- Always test before committing
- Always commit and push when done
- Mobile-first design (test at 375px)
- All user-facing text must be empathetic — this serves grieving families
- Caterer features must never feel like ads
- Address privacy: never expose shiva address publicly, only after meal signup

## Design Quality Checklist (every change)
- Mobile-first: test at 375px before committing
- Grief context: never place commercial elements (caterer links, pricing, upsells) on obituary or memorial pages — only in meal coordination flows
- Tone check: every user-facing string should pass "would this feel okay to read the week your parent died?"
- Caterer integration: always framed as "helpful resource" not "sponsored listing" — use language like "Browse caterers in your area" not "Our partners". Avoid defaulting to "kosher" in general caterer labels (not all vendors are kosher).
- Accessibility: sufficient color contrast, readable font sizes (min 16px body), tappable targets (min 44px)
- No orphaned pages: every page must have clear navigation back to home and feed
- Shabbat awareness: meal coordination UI should respect Friday sunset to Saturday sunset

---

## End-of-Session Discipline - verification before save

When updating _NOW.md, decisions-log.md, or any "where we left off" / status file at the end of a session:

1. For each claim that describes work completed during the session, verify the underlying file was actually edited in the session. Do not rely on the user's recollection or Claude's chat output as proof. File-level verification means: git diff or file read to confirm the change exists.

2. If a claim is aspirational or pending - i.e., discussed but not yet executed against the actual file - mark it explicitly: "PENDING:" or "NOT YET DONE:" prefix in the _NOW.md or decisions-log entry.

3. Before saving an end-of-session summary, output the diff AND explicitly state two lists:
   - "Verified completed: [list of work confirmed via file inspection]"
   - "Pending / not yet done: [list of work discussed but not yet executed]"
   The user must confirm both lists are accurate before save.

4. Push back on user dictation that asserts completed work without an underlying file change. Specifically: if user dictates a "Where we left off" bullet claiming X was done, Claude must verify X was actually done before saving. The user's tiredness at end of day is the highest-risk window for this failure mode.

5. This rule does not slow down sessions where work IS being executed in real time. It only adds friction at the summary/save step at end-of-session.

### Origin (added 2026-05-21)

This rule was created in response to a 2026-05-20 session failure where _NOW.md was saved with false claims that JORDANA-OUTREACH.md had been updated when it had not been. The discipline must activate automatically at end of every session going forward.
