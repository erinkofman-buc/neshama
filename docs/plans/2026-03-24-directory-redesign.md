# Vendor Directory Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the vendor directory page to feel warm, professional, and community-focused — not like a commercial marketplace. Every element should pass the test: "would this feel okay to browse the week your parent died?"

**Architecture:** Single-file redesign of `frontend/directory.html`. CSS + HTML structure + JS rendering changes. No backend changes needed — same `/api/vendors` data. The page must remain a single HTML file with embedded CSS/JS (matching the current Neshama architecture).

**Tech Stack:** Vanilla HTML/CSS/JS, Cormorant Garamond + Source Serif 4 fonts, Neshama design system colors.

**Brand constraints:**
- Warm earth tones (terracotta, cream, sage, dark brown)
- Never commercial — "community" not "marketplace"
- Accessible for 50-80+ users (20px+ body text, 44px+ tap targets, WCAG AA contrast)
- Grief-aware — no aggressive CTAs, no sales language

**Research basis:** Deep research report from Airbnb, Yelp, DoorDash, The Knot, Shiva.com, Empathy.com, Houzz, MealTrain. Key patterns: search-in-hero, single CTA per card, horizontal category pills, warm empty states, community trust badges.

---

### Task 1: Hero Section — Search Merged In, Warmer Headline

**Files:**
- Modify: `frontend/directory.html` (CSS lines 119-138, HTML lines 559-570)

**What changes:**
- Headline: "Find Trusted Partners" → "Local Vendors Ready to Help"
- Subtitle stays but tighten: "Caterers, bakeries, and food vendors — here when your community needs them most."
- Move search bar INTO the hero (merge filter-bar search into hero section)
- Vendor count stays as subtle social proof below subtitle
- Remove the breadcrumb (line 559-563) — it adds clutter and the nav already shows context
- Reduce hero vertical padding (currently 3rem top — too much dead space)

**Step 1: Update hero HTML**

Replace lines 559-570 with:
```html
<main id="main-content">
<header class="hero">
    <h1>Local Vendors Ready to Help</h1>
    <p class="subtitle">Caterers, bakeries, and food vendors &mdash; here when your community needs them most.</p>
    <p id="heroCount" class="hero-count"></p>
    <div class="hero-search">
        <svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="searchInput" placeholder="Search by name, cuisine, or neighborhood..." aria-label="Search vendors">
    </div>
</header>
```

**Step 2: Update hero CSS**

```css
.hero {
    text-align: center;
    padding: 2rem 1.5rem 1.25rem;
}
.hero h1 {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2.8rem;
    font-weight: 400;
    margin-bottom: 0.4rem;
}
.hero .subtitle {
    font-size: 1.1rem;
    color: var(--sage-dark);
    max-width: 520px;
    margin: 0 auto;
    line-height: 1.6;
}
.hero-count {
    font-size: 0.95rem;
    color: var(--sage-dark);
    margin-top: 0.4rem;
}
.hero-search {
    max-width: 480px;
    margin: 1.25rem auto 0;
    position: relative;
}
.hero-search input {
    width: 100%;
    padding: 0.85rem 1.25rem 0.85rem 3rem;
    border: 2px solid var(--light-taupe);
    border-radius: 2.5rem;
    font-family: 'Source Serif 4', serif;
    font-size: 1.05rem;
    color: var(--dark-brown);
    background: white;
    box-shadow: 0 2px 12px var(--soft-shadow);
    transition: border-color 0.2s, box-shadow 0.2s;
}
.hero-search input:focus {
    outline: none;
    border-color: var(--terracotta);
    box-shadow: 0 4px 20px rgba(210, 105, 30, 0.12);
}
.hero-search svg {
    position: absolute;
    left: 1.1rem;
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    stroke: var(--sage-dark);
    fill: none;
    stroke-width: 2;
}
```

**Step 3: Remove old search from filter-controls**

Remove the `.search-box` div from the filter-controls section (it's now in the hero). Keep the category/area/kosher/delivery filters in the filter bar.

**Step 4: Verify**

- Page should show: warm heading → subtitle → count → search bar → filters → cards
- Search input still wired to `filterVendors()` function (same `id="searchInput"`)

**Step 5: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): merge search into hero, warmer headline"
```

---

### Task 2: Category Pills — Replace Dropdown with Horizontal Scroll Pills

**Files:**
- Modify: `frontend/directory.html` (CSS + HTML + JS)

**What changes:**
- Replace the `<select id="categoryFilter">` dropdown with horizontal scrolling pill buttons
- Each pill has a subtle category icon (emoji or Unicode)
- Active pill gets terracotta fill (same as city filter)
- Scrollable on mobile (overflow-x: auto, hide scrollbar)

**Step 1: Add category pills CSS**

```css
.category-pills {
    display: flex;
    gap: 0.5rem;
    overflow-x: auto;
    padding: 0.25rem 0;
    -ms-overflow-style: none;
    scrollbar-width: none;
}
.category-pills::-webkit-scrollbar { display: none; }

.cat-pill {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.5rem 1rem;
    border: 1.5px solid var(--light-taupe);
    border-radius: 2rem;
    background: white;
    cursor: pointer;
    font-family: 'Source Serif 4', serif;
    font-size: 0.9rem;
    color: var(--dark-brown);
    transition: all 0.2s;
    white-space: nowrap;
    min-height: 44px;
}
.cat-pill:hover { border-color: var(--terracotta); }
.cat-pill.active {
    background: var(--terracotta);
    color: white;
    border-color: var(--terracotta);
}
.cat-pill-icon { font-size: 1rem; }
```

**Step 2: Replace select with pill HTML**

```html
<div class="category-pills" id="categoryPills" role="radiogroup" aria-label="Filter by category">
    <button class="cat-pill active" data-cat="" onclick="setCat('',this)">
        <span class="cat-pill-icon">&#9776;</span> All
    </button>
    <button class="cat-pill" data-cat="Caterers" onclick="setCat('Caterers',this)">
        <span class="cat-pill-icon">&#127858;</span> Caterers
    </button>
    <button class="cat-pill" data-cat="Bagel Shops & Bakeries" onclick="setCat('Bagel Shops & Bakeries',this)">
        <span class="cat-pill-icon">&#127838;</span> Bakeries
    </button>
    <button class="cat-pill" data-cat="Kosher Restaurants & Caterers" onclick="setCat('Kosher Restaurants & Caterers',this)">
        <span class="cat-pill-icon">&#127860;</span> Kosher
    </button>
    <button class="cat-pill" data-cat="Restaurants & Delis" onclick="setCat('Restaurants & Delis',this)">
        <span class="cat-pill-icon">&#129386;</span> Delis
    </button>
    <button class="cat-pill" data-cat="Delis & Smoked Meat" onclick="setCat('Delis & Smoked Meat',this)">
        <span class="cat-pill-icon">&#129385;</span> Smoked Meat
    </button>
    <button class="cat-pill" data-cat="Middle Eastern & Israeli" onclick="setCat('Middle Eastern & Israeli',this)">
        <span class="cat-pill-icon">&#129474;</span> Middle Eastern
    </button>
    <button class="cat-pill" data-cat="Pizza & Dairy" onclick="setCat('Pizza & Dairy',this)">
        <span class="cat-pill-icon">&#127829;</span> Pizza
    </button>
    <button class="cat-pill" data-cat="Italian" onclick="setCat('Italian',this)">
        <span class="cat-pill-icon">&#127837;</span> Italian
    </button>
    <button class="cat-pill" data-cat="Japanese & Sushi" onclick="setCat('Japanese & Sushi',this)">
        <span class="cat-pill-icon">&#127843;</span> Sushi
    </button>
    <button class="cat-pill" data-cat="Mediterranean" onclick="setCat('Mediterranean',this)">
        <span class="cat-pill-icon">&#127813;</span> Mediterranean
    </button>
</div>
```

**Step 3: Add setCat() JS function**

```javascript
var activeCategory = '';
function setCat(cat, btn) {
    activeCategory = cat;
    var pills = document.querySelectorAll('.cat-pill');
    pills.forEach(function(p) { p.classList.remove('active'); });
    btn.classList.add('active');
    filterVendors();
}
```

**Step 4: Update filterVendors()** to use `activeCategory` instead of `categoryFilter.value`.

**Step 5: Remove the old `<select id="categoryFilter">` from HTML and its event listener from JS.

**Step 6: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): category pills with icons, horizontal scroll"
```

---

### Task 3: Simplified Filter Bar — Area + Toggles Only

**Files:**
- Modify: `frontend/directory.html`

**What changes:**
- The filter-controls box now only contains: area dropdown + kosher toggle + delivery toggle
- City pills move above category pills (both are now horizontal pill rows)
- The big white box with border goes away — filters are lightweight pills
- Filter area becomes: city pills → category pills → [area dropdown | kosher | delivers] on one compact line

**Step 1: Restructure filter HTML**

```html
<div class="filter-bar">
    <!-- City pills -->
    <div class="filter-pills-row">
        <button class="filter-toggle active" id="cityAll" onclick="setCity('all',this)">All</button>
        <button class="filter-toggle" id="cityToronto" onclick="setCity('toronto',this)">Toronto</button>
        <button class="filter-toggle" id="cityMontreal" onclick="setCity('montreal',this)">Montreal</button>
    </div>

    <!-- Category pills -->
    <div class="category-pills" id="categoryPills">
        <!-- ... pills from Task 2 ... -->
    </div>

    <!-- Secondary filters -->
    <div class="filter-secondary">
        <select class="filter-select" id="neighborhoodFilter" aria-label="Filter by area">
            <option value="">All Areas</option>
        </select>
        <button class="filter-toggle" id="kosherToggle" aria-pressed="false">Kosher Certified</button>
        <button class="filter-toggle" id="deliveryToggle" aria-pressed="false">Delivers</button>
    </div>
</div>
```

**Step 2: Update filter-bar CSS**

```css
.filter-bar {
    max-width: 960px;
    margin: 0 auto;
    padding: 0 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.filter-pills-row {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
}
.filter-secondary {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-items: center;
}
```

**Step 3: Remove the `.filter-controls` white box wrapper and its CSS.

**Step 4: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): streamlined filter layout, no white box"
```

---

### Task 4: Card Redesign — Single CTA, Badge Overlays, Warmer Feel

**Files:**
- Modify: `frontend/directory.html`

**What changes:**
- Single CTA per card: "View Details" (terracotta, full-width bottom). Remove "Reach Out" from cards — it lives on the detail page.
- Badges (COR, MK, Delivery) overlay on bottom-left of image with slight translucent background
- Category label as a small colored pill (not uppercase text)
- Description clamped to 2 lines (from 3)
- Neighborhood + phone as subtle footer text, not in a bordered meta row

**Step 1: Update card CSS**

```css
/* Badge overlays on image */
.vendor-card-badges {
    position: absolute;
    bottom: 0.5rem;
    left: 0.5rem;
    display: flex;
    gap: 0.25rem;
}
.vendor-card-badges .badge {
    font-size: 0.8rem;
    padding: 0.15rem 0.5rem;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(4px);
    border: none;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

/* Category as pill */
.vendor-category {
    display: inline-block;
    font-size: 0.8rem;
    color: var(--terracotta);
    font-weight: 500;
    padding: 0.15rem 0.6rem;
    border-radius: 1rem;
    background: rgba(210, 105, 30, 0.08);
    margin-bottom: 0.4rem;
    text-transform: none;
    letter-spacing: normal;
    width: fit-content;
}

/* Single full-width CTA */
.vendor-card-cta {
    display: block;
    text-align: center;
    padding: 0.75rem;
    color: var(--terracotta);
    font-weight: 600;
    font-size: 0.95rem;
    text-decoration: none;
    border-top: 1px solid rgba(210, 105, 30, 0.1);
    transition: background 0.2s;
}
.vendor-card-cta:hover {
    background: rgba(210, 105, 30, 0.04);
    text-decoration: none;
}

/* Vendor location line */
.vendor-location {
    font-size: 0.9rem;
    color: var(--sage-dark);
    margin-top: auto;
    padding-top: 0.5rem;
}
```

**Step 2: Update renderVendors() JS**

Move badges INSIDE the image div (overlaid). Render a single "View Details" CTA at the card bottom. Move neighborhood into the card body as subtle text. Remove phone from card (it's on the detail page).

**Step 3: Verify** — Cards should look: image (with badge overlay) → category pill → name → 2-line description → neighborhood → "View Details" link.

**Step 4: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): card redesign — single CTA, badge overlays, warmer category pills"
```

---

### Task 5: Partner Banner — Move Below Grid, Softer

**Files:**
- Modify: `frontend/directory.html`

**What changes:**
- Move the "Serve the community" vendor CTA from above the grid to below it
- Softer design — text-only, no box border, centered
- Feels like a gentle footnote, not an ad

**Step 1: Move banner HTML to after `</div><!-- vendor-grid -->`**

```html
<div class="vendor-apply-footer">
    <p>Are you a food vendor serving the Toronto or Montreal Jewish community?</p>
    <a href="/shiva/caterers/apply">Join our free directory &rarr;</a>
</div>
```

**Step 2: CSS**

```css
.vendor-apply-footer {
    text-align: center;
    padding: 2rem 1.5rem 1rem;
    max-width: 600px;
    margin: 0 auto;
}
.vendor-apply-footer p {
    font-size: 1rem;
    color: var(--sage-dark);
    margin-bottom: 0.5rem;
}
.vendor-apply-footer a {
    color: var(--terracotta);
    font-weight: 500;
    font-size: 1rem;
}
```

**Step 3: Remove the old inline-styled banner div (lines 606-614).

**Step 4: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): move vendor apply CTA below grid, softer tone"
```

---

### Task 6: Empty State — Warm Messaging

**Files:**
- Modify: `frontend/directory.html`

**What changes:**
- When no vendors match filters, show warm empty state instead of generic "No results"
- Include "Suggest a vendor" link

**Step 1: Update the no-results rendering in filterVendors()**

When `filtered.length === 0`, render:

```html
<div class="no-results">
    <h3>No vendors match those filters</h3>
    <p>Try broadening your search or <a href="/shiva/caterers/apply">suggest a vendor</a> you trust.</p>
</div>
```

**Step 2: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): warm empty state with suggest-a-vendor link"
```

---

### Task 7: Mobile Responsive Polish

**Files:**
- Modify: `frontend/directory.html`

**What changes:**
- Category pills scroll horizontally on mobile (already handled by overflow-x: auto)
- Filter toggles stack properly
- Cards go full-width single column at 768px (already works)
- Hero search stays full-width on mobile
- Image height 150px on mobile

**Step 1: Update mobile CSS**

```css
@media (max-width: 768px) {
    .vendor-grid { grid-template-columns: 1fr; max-width: 520px; }
    .filter-secondary { flex-direction: column; }
    .filter-secondary > * { width: 100%; justify-content: center; }
}

@media (max-width: 600px) {
    .hero h1 { font-size: 2.2rem; }
    .hero { padding: 1.5rem 1.5rem 1rem; }
    .hero-search input { font-size: 1rem; padding: 0.75rem 1rem 0.75rem 2.75rem; }
    .vendor-card-img { height: 150px; }
    .vendor-card h3 { font-size: 1.25rem; }
}
```

**Step 2: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): mobile responsive polish"
```

---

### Task 8: Red Team + QA

**Step 1: Brand voice check**
- Grep for commercial language: "buy", "sale", "discount", "order now", "shop"
- Verify all copy passes: "would this feel okay the week your parent died?"
- Check "View Details" CTA tone (not "Request a Quote" or "Buy Now")

**Step 2: Accessibility audit**
- All font sizes >= 16px
- All tap targets >= 44px
- Color contrast WCAG AA on all text
- All interactive elements have aria labels
- Category pills have `role="radiogroup"`

**Step 3: Security check**
- `escapeHtml()` still used on all vendor data
- `referrerpolicy="no-referrer"` still on images
- No new innerHTML without escaping

**Step 4: Run smoke tests**

```
python3 smoke_test.py
```

Expected: 54 pass, 1 pre-existing fail (daily_digest)

**Step 5: Run /qa pre**

**Step 6: Commit + push**

```
git push
```

**Step 7: Run /qa post after deploy**

---

### Task 9: SEO Updates

**Step 1: Update page title and meta**
- Title: "Local Food Vendors for Shiva Meals - Neshama" (more specific)
- Meta description: "Browse 100+ caterers, bakeries, and food vendors across Toronto and Montreal. Free directory for shiva meals and community gatherings."
- OG title to match

**Step 2: Commit**

```
git add frontend/directory.html
git commit -m "feat(directory): update SEO title and meta for better search ranking"
```

---

## Summary of Visual Changes

| Element | Before | After |
|---------|--------|-------|
| Headline | "Find Trusted Partners" | "Local Vendors Ready to Help" |
| Search | Inside white filter box | Prominent in hero |
| Categories | Dropdown select | Horizontal scroll pills with icons |
| Filter bar | White bordered box | Lightweight pill rows |
| Card badges | In body text | Overlaid on image |
| Card category | ALL CAPS text | Colored pill |
| Card CTAs | "Reach Out" + "Visit →" | "View Details" only |
| Card meta | Cramped one-line | Subtle location text |
| Partner banner | Above grid, boxed | Below grid, text-only |
| Empty state | Generic text | Warm message + suggest link |
