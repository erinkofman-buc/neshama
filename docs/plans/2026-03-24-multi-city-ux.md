# Multi-City UX Expansion Plan

**Date**: 2026-03-24
**Status**: Planning (no code changes)
**Scope**: UX for scaling from 2 cities (Toronto, Montreal) to 6+ (adding South Florida, Chicago, NYC, LA)

---

## Table of Contents

1. [City Selector Component](#1-city-selector-component)
2. [SEO Landing Pages Per City](#2-seo-landing-pages-per-city)
3. [Homepage Adaptation](#3-homepage-adaptation)
4. [Vendor Directory Per City](#4-vendor-directory-per-city)
5. [Email Digest Per City](#5-email-digest-per-city)
6. [How city_config.py Feeds Everything](#6-how-city_configpy-feeds-everything)
7. [File Change Map](#7-file-change-map)
8. [Phased Implementation](#8-phased-implementation)

---

## 1. City Selector Component

### Problem

Currently: 3 buttons in a `.city-filter` div — "All", "Toronto", "Montreal". At 6 cities + "All" = 7 buttons. At 10+ cities, buttons overflow on mobile.

### Solution: Dropdown + Saved Preference

Replace the button row with a **single dropdown selector** that:
- Shows the user's saved city by default
- Groups cities by country (Canada / United States)
- Includes an "All Cities" option at top
- Saves selection to `localStorage` under `neshama_city`
- Renders as a warm, styled `<select>` that matches the design system
- Works identically on the feed page AND the vendor directory

**Why a dropdown, not pills**: Pills work for 2-3 options. At 6+, they break on mobile (375px) and force horizontal scrolling that 50-80 year old iPhone users will miss. A dropdown is one tap, immediately clear, universally understood.

### Wireframe Description

```
┌──────────────────────────────────────────┐
│  Location ▾  [South Florida         ▾]   │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ All Cities                         │  │
│  │ ─── Canada ───                     │  │
│  │ Toronto                            │  │
│  │ Montreal                           │  │
│  │ ─── United States ───              │  │
│  │ South Florida                      │  │
│  │ Chicago                            │  │
│  │ New York                           │  │
│  │ Los Angeles                        │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Sub-Region Filtering (Within City)

For large metro areas, a **second dropdown** appears ONLY when a multi-region city is selected:

- **South Florida**: Palm Beach County, Broward County, Miami-Dade County
- **NYC**: Manhattan, Brooklyn, Queens, Long Island, Westchester/NJ
- **LA**: Westside, Pico-Robertson/Mid-City, The Valley, Orange County
- **Chicago**: North Shore, Skokie/West Rogers Park, Lakeview/Lincoln Park
- **Toronto**: No sub-regions needed (neighborhoods handled by funeral home)
- **Montreal**: No sub-regions needed

Sub-regions are defined in `city_config.py` as a new `sub_regions` key (see Section 6).

```
┌──────────────────────────────────────────┐
│  Location: [South Florida ▾]             │
│  Area:     [Broward County ▾]            │
└──────────────────────────────────────────┘
```

The sub-region dropdown defaults to "All Areas" and is hidden when the selected city has no sub_regions.

### CSS Spec for City Selector

```css
/* Shared city selector — used on feed, directory, landing pages */
.city-selector {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.city-selector label {
    font-family: 'Source Serif 4', serif;
    font-size: 0.875rem;
    color: var(--sage-dark);
    font-weight: 500;
}

.city-selector select {
    font-family: 'Source Serif 4', serif;
    font-size: 1rem;
    padding: 0.55rem 2rem 0.55rem 0.85rem;
    border: 1.5px solid var(--light-taupe);
    border-radius: 0.5rem;
    background: white;
    color: var(--dark-brown);
    cursor: pointer;
    min-height: 44px; /* accessibility tap target */
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,...chevron-svg...");
    background-repeat: no-repeat;
    background-position: right 0.75rem center;
    background-size: 12px;
    transition: border-color 0.2s;
}

.city-selector select:focus {
    outline: none;
    border-color: var(--terracotta);
    box-shadow: 0 0 0 3px rgba(210, 105, 30, 0.1);
}

/* Sub-region dropdown — hidden when not applicable */
.city-selector .sub-region-select {
    display: none;
}

.city-selector .sub-region-select.visible {
    display: inline-flex;
}

@media (max-width: 600px) {
    .city-selector {
        flex-direction: column;
        align-items: stretch;
    }
    .city-selector select {
        width: 100%;
        font-size: 1.05rem;
    }
}
```

### HTML Spec

```html
<div class="city-selector" id="citySelector">
    <label for="citySelect">Location</label>
    <select id="citySelect" aria-label="Select city">
        <option value="all">All Cities</option>
        <optgroup label="Canada">
            <option value="toronto">Toronto</option>
            <option value="montreal">Montreal</option>
        </optgroup>
        <optgroup label="United States">
            <option value="south-florida">South Florida</option>
            <option value="chicago">Chicago</option>
            <option value="nyc">New York</option>
            <option value="la">Los Angeles</option>
        </optgroup>
    </select>
    <select id="subRegionSelect" class="sub-region-select" aria-label="Select area within city">
        <option value="all">All Areas</option>
        <!-- Populated dynamically from city_config sub_regions -->
    </select>
</div>
```

### JS Behavior

```javascript
// On page load:
// 1. Fetch /api/cities to get city list + sub_regions
// 2. Read localStorage('neshama_city') and localStorage('neshama_sub_region')
// 3. Set dropdown values
// 4. If city has sub_regions, show sub-region dropdown

// On city change:
// 1. Save to localStorage('neshama_city')
// 2. Clear sub-region selection
// 3. If new city has sub_regions, populate + show sub-region dropdown
// 4. If no sub_regions, hide sub-region dropdown
// 5. Re-filter feed/directory
// 6. Update URL hash: #city=south-florida&area=broward (shareable)

// On sub-region change:
// 1. Save to localStorage('neshama_sub_region')
// 2. Re-filter feed/directory
```

### Auto-Detect City (Optional, Phase 2)

On first visit (no localStorage preference), attempt IP-based city detection:

1. Call a free IP geolocation API (ipapi.co or similar — no API key needed for basic)
2. Match returned city/state against `detection_keywords` in city_config
3. If match found, pre-select that city and show a subtle banner: "Showing results near South Florida. [Change]"
4. If no match, default to "All Cities"
5. Never override a saved localStorage preference

This is low priority. The dropdown with localStorage memory handles 95% of the UX need.

---

## 2. SEO Landing Pages Per City

### URL Structure

```
/toronto           — Toronto Jewish Obituaries & Shiva Support
/montreal          — Montreal Jewish Obituaries & Shiva Support
/south-florida     — South Florida Jewish Obituaries & Shiva Support
/chicago           — Chicago Jewish Obituaries & Shiva Support
/nyc               — New York Jewish Obituaries & Shiva Support
/la                — Los Angeles Jewish Obituaries & Shiva Support
```

These URLs serve **server-rendered HTML** pages — NOT JavaScript-rendered SPAs. This is critical for SEO.

### How They Work (Server Architecture)

**Option A (recommended): Template rendering in api_server.py**

Add a city landing page handler in `api_server.py` that:

1. Matches request path against `city_config.get_city_slugs()`
2. Reads a single HTML template file (`city-landing-template.html`)
3. Injects city-specific data from `city_config.py`:
   - Page title, meta description, OG tags from `seo` dict
   - City name, neighborhoods list
   - Funeral home names from `funeral_homes` dict
   - Recent obituaries (top 10) from database, filtered by city
   - Local vendor count from database, filtered by city
4. Returns fully rendered HTML

This means one template file serves all 6 city pages. Adding a new city = adding to `city_config.py` and the page auto-generates.

**Route registration in api_server.py:**

```python
# In the do_GET handler, before static file routing:
city_slugs = get_city_slugs()
if path.strip('/') in city_slugs:
    self.serve_city_landing(path.strip('/'))
    return
```

### Landing Page Template Wireframe

```
┌─────────────────────────────────────────────────┐
│  [Nav bar — same as all pages]                   │
├─────────────────────────────────────────────────┤
│                                                  │
│        South Florida Jewish Obituaries           │
│             & Shiva Support                      │
│                                                  │
│  Obituaries from Star of David, Riverside        │
│  Gordon, Menorah Gardens, Levitt-Weinstein,      │
│  and more — updated daily.                       │
│                                                  │
│  [View Obituaries]  [Find Local Vendors]         │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  RECENT OBITUARIES                               │
│  ┌──────┐ ┌──────┐ ┌──────┐                     │
│  │ Card │ │ Card │ │ Card │   (3-6 recent)      │
│  └──────┘ └──────┘ └──────┘                     │
│           [View all South Florida obituaries →]  │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  LOCAL FUNERAL HOMES                             │
│  • Star of David Memorial Gardens                │
│  • Riverside Gordon Memorial Chapels             │
│  • Menorah Gardens Funeral Chapels               │
│  • Levitt-Weinstein Memorial Chapel              │
│  • Kronish Funeral Services                      │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  LOCAL VENDORS                                   │
│  Catering • Bakeries • Gift Baskets              │
│  [Browse 45 South Florida vendors →]             │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  NEIGHBORHOODS WE SERVE                          │
│  Aventura • Bal Harbour • Boca Raton •           │
│  Boynton Beach • Coconut Creek • ...             │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  GET SOUTH FLORIDA UPDATES                       │
│  [email input] [Subscribe]                       │
│  Weekly digest of new obituaries                 │
│                                                  │
├─────────────────────────────────────────────────┤
│  [Footer — same as all pages]                    │
└─────────────────────────────────────────────────┘
```

### Schema Markup Per City

Each city landing page includes structured data:

```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "{{city.seo.title}}",
  "description": "{{city.seo.description}}",
  "url": "https://neshama.ca/{{city_slug}}",
  "isPartOf": {
    "@type": "WebSite",
    "name": "Neshama",
    "url": "https://neshama.ca"
  },
  "about": {
    "@type": "Service",
    "name": "{{city.display_name}} Jewish Obituary & Shiva Support",
    "areaServed": {
      "@type": "City",
      "name": "{{city.display_name}}"
    },
    "provider": {
      "@type": "Organization",
      "name": "Neshama",
      "url": "https://neshama.ca"
    }
  }
}
```

Plus `ItemList` schema for the recent obituaries shown on the page.

### SEO Signals

Each city page should include:
- `<title>` from `city_config[slug]['seo']['title']`
- `<meta name="description">` from `city_config[slug]['seo']['description']`
- `<link rel="canonical" href="https://neshama.ca/{{slug}}">`
- `<meta property="og:*">` tags matching the city
- H1 with city name + "Jewish Obituaries"
- Natural neighborhood mentions (the "Neighborhoods We Serve" section)
- Internal links to feed page (pre-filtered by city) and directory page
- Cross-links to other city pages ("Also serving Toronto, Montreal, Chicago...")

### Sitemap Update

Add city landing pages to `frontend/sitemap.xml`:

```xml
<url>
    <loc>https://neshama.ca/south-florida</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
</url>
```

Generate sitemap entries from `city_config.get_city_slugs()` — either at build time or dynamically.

---

## 3. Homepage Adaptation

### Current State

`frontend/landing.html` has "Toronto & Montreal" hardcoded in:
- `<title>` tag (line 7)
- Meta description (line 8)
- OG description (line 15)
- Twitter description (line 24)
- Schema.org `areaServed` (line 33)
- Hero description text (line 275)
- Trust bar (line 300)
- Vendor count text (line 360)
- Email subscription location checkboxes (lines 442-446)
- Footer location text (line 604)

### Changes Needed

**A. Title and Meta — Dynamic but server-rendered**

```html
<title>Neshama — Jewish Obituaries & Shiva Support</title>
<meta name="description" content="Neshama brings together obituaries from Jewish funeral homes across North America — comforting families and connecting community.">
```

Drop city names from the homepage title. City-specific SEO happens on the city landing pages.

**B. Hero Section**

Current: "Obituaries and memorials from Toronto and Montreal's Jewish funeral homes, in one place."

New: "Obituaries and memorials from Jewish funeral homes across North America, in one place."

**C. City Cards Section (NEW)**

Add a new section between the hero and the features section — a grid of city cards linking to each city's landing page:

```
┌──────────────────────────────────────────────────┐
│                                                   │
│         Serving Jewish Communities Across          │
│               North America                       │
│                                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │ Toronto │ │Montreal │ │ S. FL   │            │
│  │  188K   │ │  90K    │ │  620K   │            │
│  │  Jews   │ │  Jews   │ │  Jews   │            │
│  └─────────┘ └─────────┘ └─────────┘            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │Chicago  │ │New York │ │  L.A.   │            │
│  │  320K   │ │  2.2M   │ │  743K   │            │
│  │  Jews   │ │  Jews   │ │  Jews   │            │
│  └─────────┘ └─────────┘ └─────────┘            │
│                                                   │
└──────────────────────────────────────────────────┘
```

Each card:
- Links to `/{city-slug}`
- Shows city display name
- Shows a warm icon or subtle illustration
- Has a brief tagline: "3 funeral homes" or "Updated daily"
- Hover: gentle lift + terracotta border glow

### CSS for City Cards

```css
.city-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    max-width: 720px;
    margin: 0 auto;
}

.city-card {
    background: white;
    border: 1px solid var(--light-border);
    border-radius: 12px;
    padding: 1.5rem 1rem;
    text-align: center;
    text-decoration: none;
    color: var(--dark);
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.city-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    border-color: var(--terracotta);
    color: var(--dark);
}

.city-card-name {
    font-family: var(--font-heading);
    font-size: 1.3rem;
    font-weight: 400;
    margin-bottom: 0.3rem;
}

.city-card-detail {
    font-size: 0.9rem;
    color: var(--warm-gray);
}

@media (max-width: 600px) {
    .city-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

**D. Trust Bar**

Current: "Toronto & Montreal"

New: "6 cities" or dynamically: "{{count}} cities across North America"

**E. Vendor Section**

Current: "128+ vendors across Toronto & Montreal"

New: "{{total_count}} vendors across {{city_count}} cities"

**F. Email Subscription Section**

See Section 5 below. The homepage subscription form needs city checkboxes.

**G. Schema.org**

```json
"areaServed": ["Toronto", "Montreal", "South Florida", "Chicago", "New York", "Los Angeles"]
```

Generated from `city_config.py` keys.

---

## 4. Vendor Directory Per City

### Current State

`frontend/directory.html` uses the same `.city-btn` pattern as the feed page — "All", "Toronto", "Montreal" buttons. Vendors are fetched from `/api/vendors?city=...`.

### Changes

**A. Replace city buttons with the shared city selector dropdown** (same component as Section 1). The `#citySelector` component is identical on feed and directory.

**B. City-Specific Vendor SEO Pages**

URL structure:
```
/toronto/catering           — Toronto Kosher Caterers
/south-florida/catering     — South Florida Kosher Caterers
/nyc/bakeries               — New York Jewish Bakeries
/chicago/catering            — Chicago Kosher Caterers
```

These are generated the same way as city landing pages — a template rendered server-side with city + category data injected. They target long-tail searches like "kosher catering boca raton" or "shiva caterer brooklyn."

Route pattern in `api_server.py`:

```python
# Match /{city_slug}/{vendor_category}
match = re.match(r'^/([a-z-]+)/(catering|bakeries|gifts|restaurants|delis)$', path)
if match:
    city_slug, category = match.groups()
    if city_slug in city_slugs:
        self.serve_city_vendor_page(city_slug, category)
        return
```

**C. Cross-City Browsing**

When viewing a city's directory, include a subtle link at the bottom:
"Also browse vendors in: [Toronto] [Montreal] [Chicago] [NYC] [LA]"

These link to the directory page with the city pre-selected (using the hash: `/directory#city=toronto`).

**D. Vendor Cards — City Badge**

Each vendor card should show a small city badge (e.g., "Toronto" or "S. Florida") so users browsing "All Cities" can see where each vendor is located.

---

## 5. Email Digest Per City

### Current State

Subscribers table has a `locations` column storing comma-separated city slugs (e.g., "toronto,montreal"). The subscription form has hardcoded Toronto/Montreal checkboxes.

### Changes

**A. Subscription Form — City Selector**

Replace hardcoded checkboxes with dynamic checkboxes generated from `city_config.py`:

```html
<fieldset class="subscribe-cities">
    <legend>Which cities do you want updates from?</legend>
    <label><input type="checkbox" value="toronto" checked> Toronto</label>
    <label><input type="checkbox" value="montreal" checked> Montreal</label>
    <label><input type="checkbox" value="south-florida"> South Florida</label>
    <label><input type="checkbox" value="chicago"> Chicago</label>
    <label><input type="checkbox" value="nyc"> New York</label>
    <label><input type="checkbox" value="la"> Los Angeles</label>
</fieldset>
```

If the user arrived from a city landing page (e.g., `/south-florida`), pre-check that city.

If the user has a saved city in localStorage, pre-check that city.

**B. CSS for City Checkboxes**

```css
.subscribe-cities {
    border: none;
    padding: 0;
    margin-bottom: 1rem;
}

.subscribe-cities legend {
    font-family: 'Source Serif 4', serif;
    font-size: 0.95rem;
    color: var(--sage-dark);
    margin-bottom: 0.5rem;
}

.subscribe-cities label {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin-right: 1rem;
    margin-bottom: 0.4rem;
    font-size: 0.95rem;
    cursor: pointer;
    min-height: 44px; /* tap target */
}

.subscribe-cities input[type="checkbox"] {
    width: 20px;
    height: 20px;
    accent-color: var(--terracotta);
}
```

**C. Digest Generation (Backend)**

The digest sending logic in `api_server.py` already filters by `locations`. The change is:
1. When sending daily/weekly digests, filter obituaries by the subscriber's `locations` list
2. Subject line includes city: "This Week: 12 New Obituaries in South Florida"
3. If subscriber follows multiple cities, group by city with headers

**D. Subscription Management Page**

The `/manage-subscription` page needs the same city checkboxes so subscribers can add/remove cities.

**E. Landing Page Subscription Forms**

Each city landing page (`/south-florida`, etc.) has its own inline subscription form that pre-checks that city:

```html
<input type="hidden" name="locations" value="south-florida">
```

Or show the city pre-checked with option to add others.

---

## 6. How city_config.py Feeds Everything

### Current city_config.py

Already has: `display_name`, `country`, `region`, `timezone`, `neighborhoods`, `detection_keywords`, `scrapers`, `funeral_homes`, `outscraper_keywords`, `seo`.

### Additions Needed

```python
'south-florida': {
    # ... existing fields ...
    'sub_regions': {
        'palm-beach': {
            'display_name': 'Palm Beach County',
            'neighborhoods': ['Boca Raton', 'Delray Beach', 'Boynton Beach',
                            'West Palm Beach', 'Palm Beach Gardens'],
        },
        'broward': {
            'display_name': 'Broward County',
            'neighborhoods': ['Fort Lauderdale', 'Hollywood', 'Parkland',
                            'Weston', 'Coral Springs', 'Tamarac', 'Davie',
                            'Deerfield Beach', 'Coconut Creek', 'Pompano Beach'],
        },
        'miami-dade': {
            'display_name': 'Miami-Dade County',
            'neighborhoods': ['Miami Beach', 'Aventura', 'Sunny Isles',
                            'Surfside', 'Bal Harbour', 'North Miami Beach'],
        },
    },
    'population': '620,000',  # for city cards on homepage
    'tagline': 'Boca Raton, Aventura, Fort Lauderdale, and beyond',
}
```

Similarly for NYC:
```python
'sub_regions': {
    'manhattan': {'display_name': 'Manhattan', 'neighborhoods': [...]},
    'brooklyn': {'display_name': 'Brooklyn', 'neighborhoods': [...]},
    'queens': {'display_name': 'Queens', 'neighborhoods': [...]},
    'long-island': {'display_name': 'Long Island', 'neighborhoods': [...]},
    'westchester-nj': {'display_name': 'Westchester & NJ', 'neighborhoods': [...]},
}
```

### New Helper Functions

```python
def get_sub_regions(city_slug):
    """Return sub_regions dict for a city, or empty dict."""
    city = CITIES.get(city_slug, {})
    return city.get('sub_regions', {})

def get_cities_for_api():
    """Updated to include sub_regions."""
    return {
        slug: {
            'display_name': cfg['display_name'],
            'country': cfg['country'],
            'region': cfg['region'],
            'neighborhoods': cfg['neighborhoods'],
            'sub_regions': {
                sr_slug: sr_data['display_name']
                for sr_slug, sr_data in cfg.get('sub_regions', {}).items()
            },
            'funeral_homes': cfg['funeral_homes'],
            'seo': cfg['seo'],
            'population': cfg.get('population', ''),
            'tagline': cfg.get('tagline', ''),
        }
        for slug, cfg in CITIES.items()
    }
```

### Data Flow

```
city_config.py
    │
    ├──→ /api/cities endpoint → Frontend JS (populates dropdowns, city cards)
    │
    ├──→ City landing page renderer (SEO pages)
    │      Uses: display_name, seo, funeral_homes, neighborhoods
    │
    ├──→ Feed page filtering (app.js)
    │      Uses: city slug for /api/obituaries?city=X
    │
    ├──→ Directory page filtering
    │      Uses: city slug for /api/vendors?city=X
    │
    ├──→ Email digest sender
    │      Uses: city slugs to filter obituaries per subscriber
    │
    ├──→ Sitemap generator
    │      Uses: get_city_slugs() for city landing page URLs
    │
    └──→ Scraper orchestrator (master_scraper.py)
           Uses: scrapers list per city
```

**Single source of truth**: Adding a new city means:
1. Add entry to CITIES dict in `city_config.py`
2. Uncomment it
3. Everything else (dropdowns, landing page, SEO, filters, digest) auto-generates

---

## 7. File Change Map

### Files to Modify

| File | Changes |
|------|---------|
| `city_config.py` | Add `sub_regions`, `population`, `tagline` to each city. Uncomment expansion cities. Update `get_cities_for_api()`. |
| `frontend/api_server.py` | Add city landing page route handler. Add city+category vendor page route. Add template rendering function. Update sitemap generation. |
| `frontend/index.html` (feed) | Replace `.city-btn` buttons with `#citySelector` dropdown. Add sub-region dropdown. Update `NeshamaApp` JS to use dropdown instead of buttons. |
| `frontend/app.js` | Replace `handleCityChange` button logic with dropdown `change` event. Add sub-region filtering. Update `getFiltered()` for sub-region. |
| `frontend/landing.html` (homepage) | Replace "Toronto & Montreal" in title, meta, hero, trust bar, vendor text, schema. Add city cards section. Update subscription form. |
| `frontend/directory.html` | Replace city buttons with shared `#citySelector` dropdown. Add city badge to vendor cards. |
| `frontend/sitemap.xml` | Add city landing page URLs. Add city+category vendor page URLs. |

### New Files to Create

| File | Purpose |
|------|---------|
| `frontend/city-landing-template.html` | Server-rendered template for `/toronto`, `/south-florida`, etc. |
| `frontend/city-vendor-template.html` | Server-rendered template for `/toronto/catering`, etc. |
| `frontend/city-selector.js` | Shared JS module for the city dropdown (imported by feed, directory, landing pages). Or inline in each page if keeping single-file architecture. |

### Files to Update for "Toronto & Montreal" Hardcoding

Every file that mentions "Toronto & Montreal" or "Toronto and Montreal" needs updating:

| File | What to Change |
|------|---------------|
| `frontend/landing.html` | Title, meta, OG, hero text, trust bar, vendor text, email form, footer |
| `frontend/index.html` | Title, meta, OG, schema markup |
| `frontend/faq.html` | FAQ answers mentioning Toronto/Montreal |
| `frontend/directory.html` | Vendor count text, partner banner text |
| `frontend/manifest.json` | App description |

---

## 8. Phased Implementation

### This Week (Mar 24-28): Foundation

**Goal**: City selector dropdown replaces buttons. No new cities yet — same 2 cities, new UI.

1. **Build city selector dropdown component** in `frontend/index.html`
   - Replace `.city-btn` buttons with `<select>` dropdown
   - Keep "All", "Toronto", "Montreal" as options
   - Wire up localStorage save/restore (already exists — just change from button to select)
   - Test on mobile (375px)

2. **Copy city selector to `frontend/directory.html`**
   - Same dropdown component
   - Same localStorage key so preference syncs between pages

3. **Update `get_cities_for_api()`** to include `sub_regions` (empty for Toronto/Montreal)

4. **Test and deploy**

**No content changes, no new pages. Just the UI component swap.**

### Month 1 (April): South Florida Launch Prep

**Goal**: South Florida city config live, city landing pages working, homepage updated.

**Week 1-2**:
1. Uncomment `south-florida` in `city_config.py` with `sub_regions` added
2. Build `city-landing-template.html` — the server-rendered template
3. Add route handler in `api_server.py` for `/{city_slug}` paths
4. Landing pages working for `/toronto`, `/montreal`, `/south-florida`
5. Update homepage: remove "Toronto & Montreal" hardcoding, add city cards section

**Week 3-4**:
6. Update email subscription form with city checkboxes
7. Update digest sender to use city-filtered obituaries
8. Add city landing page URLs to sitemap
9. Submit new pages to Google Search Console
10. Update all pages that say "Toronto & Montreal" (faq, directory, etc.)
11. Deploy and verify SEO pages are indexing

### Month 2 (May): Chicago + NYC + LA Launch Prep

**Goal**: All 6 cities in city_config, all landing pages live, sub-region filtering working.

**Week 1-2**:
1. Uncomment Chicago, NYC, LA in `city_config.py` with `sub_regions`
2. Landing pages auto-generate for all 6 cities (template already built)
3. Build sub-region dropdown logic
4. Add sub-region filtering to feed and directory
5. Build city+category vendor pages (`/toronto/catering`, etc.)

**Week 3-4**:
6. Add auto-detect city from IP (optional — nice-to-have)
7. Cross-city vendor browsing links
8. City badge on vendor cards
9. Full QA pass across all 6 cities, all pages
10. Performance testing — landing pages must load in <2s
11. Deploy and submit all new pages to GSC

### Month 3+ (June onward): Polish + Scale

- Monitor GSC for city page indexing and ranking
- A/B test city card layout on homepage
- Add city-specific OG images for social sharing
- Build city-specific email digest headers/branding
- Evaluate need for 10+ city scaling (at that point, city selector may need search/typeahead)
- Consider `.com` domain for US market SEO

---

## Design Principles Throughout

1. **Warm, not corporate**: City selection should feel like choosing "my community" not "my market." Use language like "Your community" not "Select region."

2. **Mobile-first**: Every component designed for 375px iPhone first. The dropdown is inherently mobile-friendly — native `<select>` gives iOS users the familiar scroll picker.

3. **Grief-aware**: City landing pages lead with obituaries, not vendor upsells. The tone is "your community is here" not "browse our listings."

4. **Progressive disclosure**: Show city dropdown, then sub-region only if needed. Don't overwhelm with 6 cities + 20 sub-regions on first load.

5. **Respect saved preferences**: If someone picked "South Florida" yesterday, show South Florida today. Don't make them re-select every visit.

6. **Accessible**: 44px tap targets, 20px+ text on landing pages, high contrast, proper ARIA labels on all dropdowns and form controls. The 50-80 year old iPhone user with reading glasses is the primary persona.

---

## Open Questions

1. **Domain strategy**: Should US city pages live on neshama.ca or a separate neshama.com? The `.ca` signals Canada. Could use neshama.ca for Canadian cities and redirect US visitors to neshama.com. Or keep everything on `.ca` and rely on landing page SEO. Decision needed before Month 2.

2. **Obituary city assignment**: How are obituaries tagged with a city? Currently inferred from funeral home source. With multi-city, the `city` column in the obituaries table must be populated reliably. The `detect_city_from_text()` function in city_config handles this, but needs to be called during scraping.

3. **Vendor city assignment**: Same question. The `backfill_vendor_cities` function exists but needs to run for new cities. Outscraper pipeline needs city-specific keyword lists (already in city_config).

4. **Cross-city obituaries**: Snowbirds who die in Florida but have families in Toronto. The South Florida expansion plan mentions a `cross_community_links` table. When/how to implement this? Phase 2 at earliest.

5. **Hebrew/Yiddish/Farsi rendering**: NYC and LA have significant non-English obituary content. Need to verify font stack handles Hebrew, Yiddish, and Farsi characters. Current fonts (Cormorant Garamond, Source Serif 4) support Hebrew but not Farsi — may need a fallback.
