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
