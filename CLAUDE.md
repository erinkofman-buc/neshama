# Neshama Project

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
- Address privacy (V2): shiva address is visible to anyone with the volunteer link. The link itself is the access control — only people the organizer shares it with can see it.

## Design Quality Checklist (every change)
- Mobile-first: test at 375px before committing
- Grief context: never place commercial elements (caterer links, pricing, upsells) on obituary or memorial pages — only in meal coordination flows
- Tone check: every user-facing string should pass "would this feel okay to read the week your parent died?"
- Caterer integration: always framed as "helpful resource" not "sponsored listing" — use language like "Browse caterers in your area" not "Our partners". Avoid defaulting to "kosher" in general caterer labels (not all vendors are kosher).
- Accessibility: sufficient color contrast, readable font sizes (min 16px body), tappable targets (min 44px)
- No orphaned pages: every page must have clear navigation back to home and feed
- Shabbat awareness: meal coordination UI should respect Friday sunset to Saturday sunset
