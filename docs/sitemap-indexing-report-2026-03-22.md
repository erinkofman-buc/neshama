# Neshama Sitemap & Indexing Report — March 22, 2026

## Sitemap Status

**Live sitemap**: https://neshama.ca/sitemap.xml — confirmed accessible
**robots.txt**: https://neshama.ca/robots.txt — confirmed accessible, references sitemap, allows all crawlers

### Previous state (Mar 13)
- 27 URLs, all with lastmod 2026-03-13

### Updated state (Mar 22)
- 29 URLs, all lastmod updated to 2026-03-22
- 2 new pages added (see below)
- Pages reordered by priority for clarity

## Pages Added to Sitemap

| URL | Why |
|-----|-----|
| `/shiva/caterers/apply` | Caterer application page — existed but was missing from sitemap |
| `/terms` | Terms of service — public legal page, was missing from sitemap |

## Pages Already Present (confirmed)

- `/partner` (partner.html) -- already in sitemap
- `/gifts/plant-a-tree` (plant-a-tree.html) -- already in sitemap

## Pages Intentionally Excluded from Sitemap

These are internal, dynamic, or utility pages that should NOT be indexed:

| File | Reason |
|------|--------|
| dashboard.html | Admin/internal |
| email_popup.html | UI component (modal) |
| premium_modal.html | UI component (modal) |
| premium.html | Mapped via /sustain (already in sitemap) |
| premium_success.html | Post-payment confirmation |
| premium_cancelled.html | Post-payment cancellation |
| vendor-analytics.html | Vendor admin dashboard |
| unsubscribe.html | Email unsubscribe utility |
| shiva-view.html | Dynamic (per-shiva pages) |
| memorial.html | Dynamic (per-memorial pages) |
| vendor-detail.html | Dynamic (per-vendor pages at /directory/slug) |
| index.html | Internal redirect to landing |
| landing.html | Served at / (already in sitemap as /) |
| directory.html | Served at /help/food (already in sitemap) |
| gifts.html | Served at /help/gifts (already in sitemap) |

## Priority Index Request List for Google Search Console

Submit these URLs for indexing via GSC "URL Inspection" tool, in this priority order:

### Tier 1 — Core pages (submit first)
1. `https://neshama.ca/` — Landing page
2. `https://neshama.ca/feed` — Obituary feed (main product)
3. `https://neshama.ca/about` — About page
4. `https://neshama.ca/shiva/organize` — Shiva meal organizer

### Tier 2 — High-value content pages
5. `https://neshama.ca/help` — Help hub
6. `https://neshama.ca/help/food` — Food vendor directory
7. `https://neshama.ca/help/gifts` — Gift directory
8. `https://neshama.ca/shiva-essentials` — Shiva essentials shopping
9. `https://neshama.ca/shiva/guide` — Complete shiva guide
10. `https://neshama.ca/shiva/caterers` — Caterer directory
11. `https://neshama.ca/faq` — Frequently asked questions

### Tier 3 — SEO content (long-tail search traffic)
12. `https://neshama.ca/what-to-bring-to-a-shiva`
13. `https://neshama.ca/how-to-sit-shiva`
14. `https://neshama.ca/kosher-shiva-food`
15. `https://neshama.ca/jewish-funeral-etiquette`
16. `https://neshama.ca/condolence-messages`
17. `https://neshama.ca/shiva-preparation-checklist`
18. `https://neshama.ca/what-is-yahrzeit`
19. `https://neshama.ca/first-passover-after-loss`

### Tier 4 — Supporting pages
20. `https://neshama.ca/help/supplies`
21. `https://neshama.ca/gifts/plant-a-tree`
22. `https://neshama.ca/yahrzeit`
23. `https://neshama.ca/sustain`
24. `https://neshama.ca/demo`
25. `https://neshama.ca/partner`
26. `https://neshama.ca/find-my-page`
27. `https://neshama.ca/shiva/caterers/apply`
28. `https://neshama.ca/terms`
29. `https://neshama.ca/privacy`

## Actions for Erin in Google Search Console

1. **Push the updated sitemap**: Commit and push the updated `frontend/sitemap.xml` to GitHub so Render deploys it.

2. **Resubmit sitemap in GSC**: Go to GSC > Sitemaps > enter `sitemap.xml` > Submit. This tells Google the sitemap has changed (29 URLs, updated dates).

3. **Request indexing for Tier 1-2 pages**: In GSC > URL Inspection, paste each Tier 1 and Tier 2 URL (11 total) and click "Request Indexing." Do Tier 1 first. Google limits ~10-12 requests per day, so do Tier 1-2 today and Tier 3 tomorrow.

4. **Check current index status**: While in URL Inspection, note which pages are already indexed vs. "Discovered - currently not indexed" vs. "Crawled - currently not indexed." Last check (Mar 12) showed 4 indexed / 19 not indexed.

5. **Check back in 3-5 days**: Google typically processes indexing requests within a few days. Check the Coverage/Pages report to see progress.

## GSC History (from memory)
- Mar 12: 4 pages indexed, 19 not indexed, 12 total clicks, ~1-3 clicks/day
- Sitemap was 24 URLs on Mar 12, now 29
- Launch date: Mar 24 — getting pages indexed before launch is ideal
