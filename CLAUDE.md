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
- Caterer integration: always framed as "helpful resource" not "sponsored listing" — use language like "Browse kosher caterers in your area" not "Our partners"
- Accessibility: sufficient color contrast, readable font sizes (min 16px body), tappable targets (min 44px)
- No orphaned pages: every page must have clear navigation back to home and feed
- Shabbat awareness: meal coordination UI should respect Friday sunset to Saturday sunset
