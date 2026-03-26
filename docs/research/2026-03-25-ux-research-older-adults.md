# UX Research: Designing Neshama for Users Aged 40-80

**Date:** March 25, 2026
**Scope:** Deep research on UX for older adults on a grief/community platform, applied to Neshama's current flows
**Primary audience:** Jewish community members aged 40-80, many arriving via WhatsApp link while grieving

---

## Table of Contents

1. [Research Findings](#1-research-findings)
   - [Font Size & Typography](#11-font-size--typography)
   - [Navigation & Information Architecture](#12-navigation--information-architecture)
   - [Form Design for Older Adults](#13-form-design-for-older-adults)
   - [Emotional & Grief-Aware Design](#14-emotional--grief-aware-design)
   - [Trust Signals for Non-Digital-Natives](#15-trust-signals-for-non-digital-natives)
   - [Error Messaging](#16-error-messaging-that-reduces-anxiety)
   - [Buttons, Links & Touch Targets](#17-buttons-links--touch-targets)
   - [WhatsApp Share Flows](#18-whatsapp-share-flows)
   - [Mobile UX for 50+ Users](#19-mobile-ux-for-50-users)
2. [Page-by-Page Audit](#2-page-by-page-audit)
   - [Landing Page (landing.html)](#21-landing-page)
   - [Shiva Organize Wizard (shiva-organize.html)](#22-shiva-organize-wizard)
   - [Shiva View Page (shiva-view.html)](#23-shiva-view-page)
   - [Vendor Directory (directory.html)](#24-vendor-directory)
3. [Priority Action Items](#3-priority-action-items)
4. [Sources](#4-sources)

---

## 1. Research Findings

### 1.1 Font Size & Typography

**What the research says:**

- WCAG minimum of 16px is insufficient for users 60+. Research from Frontiers in Psychology (2022) found that **19px / 14pt is the minimum recommended for older adults**, with many studies recommending even larger.
- Reading speed declines sharply below a "critical print size" that increases with age. For users 60-79, performance deteriorated significantly as character size decreased.
- Serif fonts like Source Serif 4 are acceptable for body text but **sans-serif fonts with simple shapes are preferred for mobile interfaces** per systematic reviews of age-friendly app design.
- Line spacing of at least 1.5x the font size significantly improves readability. Neshama's `line-height: 1.7` is good.
- **Contrast ratio must exceed 7:1** (WCAG AAA) for this demographic, not just the 4.5:1 AA minimum.

**What this means for Neshama:**

The current body font of `17px` on landing.html is acceptable but borderline. The `0.85rem` (approximately 13.6px) used for hints, privacy notices, and form helper text throughout the site is **too small for this audience**. The `0.7rem` (11.2px) used for meal slot labels in shiva-view.html is critically undersized.

| Element | Current Size | Recommended Minimum |
|---------|-------------|-------------------|
| Body text | 17px (landing), 16px (other pages) | 18px across all pages |
| Form labels | 0.95rem (~15.2px) | 18px minimum |
| Helper/hint text | 0.85rem (~13.6px) | 16px minimum |
| Meal slot labels | 0.7rem (~11.2px) | 14px absolute minimum, 16px preferred |
| Nav links | 1rem (16px) | 18px |
| Footer links | 1rem (16px) | 16px (acceptable, but increase gap) |
| Privacy/consent text | 0.85-0.9rem | 16px minimum |

### 1.2 Navigation & Information Architecture

**What the research says:**

- Older adults need **flat, simple navigation** with minimal sublevels. Each menu should serve a single, clear function.
- Progressive disclosure (showing more detail on demand) works well -- but only when the trigger is obvious and labeled with text, not just an icon.
- **Hamburger menus are problematic** for older users. Research from NN/g shows they hide critical navigation and older users frequently do not discover them. A visible, always-expanded navigation is preferable.
- Sticky navs are helpful for orientation but must not cover content or create confusion about scroll position.
- Breadcrumbs and "you are here" indicators significantly reduce disorientation.

**What this means for Neshama:**

The hamburger menu on mobile hides all navigation behind an icon that many 65-year-olds will not recognize or tap. The jump-nav on the landing page is good but uses small text (0.95rem). The nav labels "Listings," "Shiva Essentials," and "How Can I Help?" are clear. However, "Listings" may not immediately communicate "obituaries" to a first-time visitor.

### 1.3 Form Design for Older Adults

**What the research says:**

- **Single-column layout is mandatory.** Users complete single-column forms 15.4 seconds faster on average, and multi-column layouts cause confusing z-shaped eye movement.
- **Labels must be outside the input field**, not as placeholder text. Placeholder text disappears on focus, causing short-term memory strain. Floating labels are easily mistaken for auto-filled content.
- **Multi-step wizards work well** for older adults -- but only with clear step indicators, large "Back" buttons, and progress saved between steps so they can return without losing data.
- **Date pickers are problematic.** Native `<input type="date">` forces scrolling through calendars. For shiva dates (typically within the next 7 days), a simpler approach would be dropdown or text input. For date ranges, showing specific day names ("Monday March 25 - Sunday March 31") reduces cognitive load.
- **Dropdowns should be short** (under 7 options). The relationship dropdown in step 1 (Family/Friend) is good -- only 2 options.
- **Confirmation before submission** reduces anxiety. A review step (like step 3) is excellent practice.
- **Inline validation** immediately after field completion is preferred over validation only on submit.

**What this means for Neshama:**

The shiva-organize wizard is well-structured as a 3-step process. However:
- Labels use placeholder text inside inputs (e.g., "Your full name", "you@example.com") which disappears on focus
- The date picker `<input type="date">` may confuse older users on some devices
- Step 2 has too many fields visible at once (family name, address, city, neighbourhood, privacy toggle, start date, end date, shabbat toggle, meal blocking, guests per meal, dietary notes, special instructions, drop-off instructions, family notes, caterer selection) -- **this is cognitive overload**

### 1.4 Emotional & Grief-Aware Design

**What the research says:**

- **Use direct language.** UK Government Digital Service research found that euphemisms ("passed away," "lost") are harder to process, especially for non-native English speakers. Use "died" and "death" in functional contexts.
- **Do not assume all visitors are grieving deeply.** Some are friends helping coordinate; others may feel relief or be processing complex emotions. Avoid blanket sympathy like "Sorry for your loss."
- **Use "When you're ready..." language** instead of directive instructions. This resonates far more with bereaved users than commands.
- **Minimize text.** When grieving, cognitive capacity drops dramatically. Lengthy explanations become noise. Keep instructions to one sentence per step.
- **Explain why you are asking** for each piece of information. People in grief are hyper-vigilant about being exploited.
- **Provide clarity on what happens next** after each action. Uncertainty amplifies anxiety in bereavement.
- **Remove all unnecessary interface elements.** Grief-aware design follows the principle: if removing something would not harm the user experience, remove it.
- **Maintain consistent terminology.** Do not mix "support page," "shiva page," "meal coordination page," and "shiva support page" -- pick one and use it everywhere.

**What this means for Neshama:**

Neshama uses warm, respectful language overall -- this is a strength. However, there are terminology inconsistencies:
- "Support Page" vs "Shiva Page" vs "Shiva Support Page" -- used interchangeably
- The explainer box on shiva-organize.html is 150+ words before the user reaches any form field -- too long for a grieving visitor
- "Set Up Shiva Support" (page title) vs "Help Coordinate Support" (h1) vs "Organize Shiva Meals" (nav button) -- three different labels for the same action

### 1.5 Trust Signals for Non-Digital-Natives

**What the research says:**

- Older adults ("Digital Immigrants") value **brand reputation and offline presence** more than social proof or user reviews.
- Seeing a **phone number, physical address, or email address** prominently displayed builds trust more than badges or logos.
- **Privacy explanations** must be visible and plain-language, not buried in links to legal documents.
- Trust is **experience-based** -- it builds through cumulative positive interactions. First impressions matter enormously.
- **Family support and community endorsement** reduce digital anxiety more than any design element.
- **Familiar design patterns** (looking like websites they already know) build trust faster than novel designs.
- The most effective trust signal for this demographic: **"This was recommended by someone I know."**

**What this means for Neshama:**

The landing page trust bar ("Toronto & Montreal," "Updated daily," "Always free," "Community-supported") is good but generic. Adding specific trust signals would help:
- "contact@neshama.ca" visible in the footer (currently only as mailto link -- good)
- Naming specific funeral homes explicitly ("Steeles, Benjamin's, Paperman's") on the landing page builds credibility (currently done in the subscribe section -- should be more prominent)
- The privacy notice on shiva-organize.html is excellent: "My information will only be shared with the family and will be deleted 30 days after the shiva period ends" -- this should be more prominent

### 1.6 Error Messaging That Reduces Anxiety

**What the research says:**

- Many older users approach technology with trepidation, **fearing irreversible mistakes**.
- Error messages must: (1) explain what went wrong in plain language, (2) tell the user exactly how to fix it, (3) never use technical jargon, (4) never blame the user.
- **Inline validation** (showing errors next to the field immediately) is preferred over top-of-page error summaries.
- **Confirmation messages** ("Your information has been saved") build trust and reduce anxiety.
- Providing **"undo" options** wherever possible reduces fear of commitment.
- Use warm, encouraging tone: "Let's try that again" not "Invalid input."

**Recommended error message patterns:**

| Instead of... | Use... |
|--------------|--------|
| "Invalid email" | "Please check your email address -- it should look like name@email.com" |
| "Required field" | "We need your name so the family knows who organized this" |
| "Invalid date" | "The end date should be after the start date" |
| "Error 500" | "Something went wrong on our end. Your information is safe. Please try again, or email us at contact@neshama.ca" |
| "Form submission failed" | "We could not save your page right now. Nothing was lost -- please try the button again in a moment." |

### 1.7 Buttons, Links & Touch Targets

**What the research says:**

- **72px buttons produced the highest accuracy** for older users in research studies. The minimum recommended is 60px.
- WCAG 2.5.5 recommends **44x44px minimum** touch targets, but this is insufficient for older adults -- **60px minimum height** is recommended.
- **Buttons are more reliably tapped than links.** Older users often miss text links because they do not recognize them as interactive, especially if the link text is small or the color contrast with surrounding text is subtle.
- **Text labels on buttons are essential.** Icon-only buttons (like a bare "X" to close a modal) are frequently missed.
- **Spacing between interactive elements** must be at least 8px to prevent accidental taps.
- The **Back button** must be as visually prominent as the forward/submit button -- older users rely on it heavily.

**What this means for Neshama:**

Current button heights:
- `.btn-primary` padding: `0.85rem 2rem` (~48px total height with font) -- borderline, increase to 56-60px
- `.btn-secondary` (Back button) has the same padding but thinner visual weight due to transparent background -- **older users may not recognize it as a button**
- Meal slot buttons in shiva-view.html: `min-height: 76px` -- good
- Food chips: `padding: 0.5rem 0.9rem` (~38px) -- too small, increase to 44px minimum
- Category pills in directory: `min-height: 44px` -- acceptable
- On mobile (< 600px), food chips shrink to `padding: 0.45rem 0.75rem` (~35px) -- **too small**

### 1.8 WhatsApp Share Flows

**What the research says:**

- WhatsApp is the **primary digital communication channel** for many adults 50+, especially in tight-knit communities like Jewish populations.
- Older users on WhatsApp primarily check messages, share media, and read -- they rarely use advanced features.
- The share flow must be **one tap to share.** Any additional steps (copy link, open WhatsApp, paste) create friction that causes abandonment.
- **Pre-composed messages** with the link embedded perform dramatically better than "copy this link and send it."
- The share message should be **short, warm, and explain what will happen when the recipient taps the link.**

**Recommended WhatsApp share message template:**
```
A shiva meal page has been set up for the [Family Name] family.

You can sign up to bring a meal here:
[link]

Organized through Neshama.
```

**What this means for Neshama:**

The current share buttons on shiva-organize.html success state are good -- WhatsApp, Email, and Text are all present. However:
- The share buttons are small (padding `0.6rem 1.25rem`, approximately 40px height) -- increase to 56px
- The WhatsApp button should be **visually dominant** (larger, in WhatsApp green) since it is the primary channel
- The "Copy Link" button requires a 3-step process (tap copy, open WhatsApp, paste) -- most older users will not complete this
- The share prompt text "Share this page with family and friends:" is good but should be more specific: "Send this link to friends who may want to bring a meal"

### 1.9 Mobile UX for 50+ Users

**What the research says:**

- Tap accuracy is best **toward the center, right edge, and bottom-right corner** of the screen.
- Horizontal swipe gestures are more accurate toward the bottom half; vertical swipe toward the right half.
- **Tap interactions are strongly preferred over swipe gestures.** Swipe requires motor skills that deteriorate with age.
- Cognitive barriers include: feeling overwhelmed by complex information, difficulty forming a mental model, and forgetfulness mid-task.
- Physical barriers include: hand tremors, poor near vision, slow reading speed, and inaccurate touch.
- **Bottom navigation bars** work better than top hamburger menus on mobile.
- **Scroll indicators** ("scroll down for more") are needed -- older users often do not discover content below the fold.

**What this means for Neshama:**

The sticky mobile CTA bar ("Coordinate a Meal") at the bottom of landing.html is excellent positioning for older users. However:
- The meal calendar grid in shiva-view.html requires understanding a visual system (color coding, slot labels) without explicit instruction
- The modal that appears when signing up for a meal slot slides up from the bottom on mobile -- good pattern
- The hamburger menu at 768px breakpoint hides critical navigation

---

## 2. Page-by-Page Audit

### 2.1 Landing Page

**File:** `/Users/erinkofman/Desktop/Neshama/frontend/landing.html`

#### Where a 65-year-old would get confused:

1. **Hero section is too abstract.** "Neshama" in large letters with Hebrew text below and "Comforting our community" in italic. A first-time visitor does not immediately understand what this site does. The actual explanation ("Obituaries and memorials from Toronto and Montreal's Jewish funeral homes, in one place") is in small text below.

2. **"Listings" nav label is unclear.** Most older adults would expect "Obituaries" -- "Listings" sounds like classifieds or real estate.

3. **Jump nav terminology mismatch.** "Meals" in the jump nav links to a section about "Coordinate meals for families in mourning" -- the word "Meals" alone does not convey the shiva context.

4. **Trust bar is too subtle.** The trust signals ("Toronto & Montreal," "Updated daily," "Always free") are in 0.9rem light gray text. Many older users will scroll past without reading them.

5. **"Three things, done well" heading is vague.** A 65-year-old wants to know "What can I do here?" not a marketing tagline.

#### Where they would abandon:

1. **The hero section has two buttons with no visual hierarchy difference on mobile.** "View Obituaries" and "Organize Shiva Meals" stack vertically at 640px. An older user may not know which to tap.

2. **The email subscribe section** has dark background with light text input -- low contrast for aging eyes. The placeholder text in the email field is very faint on dark background.

#### What is too small:

- Trust bar text: `0.9rem` (14.4px)
- Jump nav links: `0.95rem` (15.2px)
- Shiva steps list items: `0.98rem` (15.7px)
- Feature descriptions: `0.98rem` (15.7px)
- "Why coordinate?" list items: `0.95rem` (15.2px)
- Subscribe consent text: `0.9rem` (14.4px)

#### Language they would not understand:

- "PWA" (if exposed anywhere)
- "Community-supported" (vague -- supported how? by whom?)
- The Hebrew text without transliteration may confuse less-religious Jewish community members or non-Jewish family friends

#### Recommendations:

**Before:**
```html
<h1 class="hero-title reveal">Neshama</h1>
<span class="hero-hebrew">...</span>
<p class="hero-tagline">Comforting our community</p>
<p class="hero-desc">Obituaries and memorials from Toronto and Montreal's
Jewish funeral homes, in one place.</p>
```

**After:**
```html
<h1 class="hero-title reveal">Neshama</h1>
<p class="hero-tagline">Jewish obituaries from Toronto and Montreal,
in one place</p>
<p class="hero-desc">Search obituaries from Steeles, Benjamin's,
Paperman's, and Misaskim. Coordinate shiva meals for families.
Always free.</p>
```

**Before (nav):**
```html
<a href="/feed" class="nav-link">Listings</a>
```

**After (nav):**
```html
<a href="/feed" class="nav-link">Obituaries</a>
```

---

### 2.2 Shiva Organize Wizard

**File:** `/Users/erinkofman/Desktop/Neshama/frontend/shiva-organize.html`

#### Where a 65-year-old would get confused:

1. **The "How It Works" explainer is too long.** 150+ words before the first form field. Contains a `<details>` expandable section ("Why coordinate instead of just calling a caterer?") that uses a pattern many older users do not recognize as interactive.

2. **Stepper dots (12px) have no text labels.** The three dots at the top give no indication of what each step contains. A user does not know they are on "Step 1 of 3: Your Information" unless they read the card title.

3. **"Your Relationship to the Family" dropdown** has only "Family" and "Friend" -- what about "Neighbour," "Colleague," "Synagogue member"? An older user organizing from the synagogue sisterhood may feel excluded.

4. **Step 2 is overwhelmingly long.** It contains 12+ form fields including conditional sections (neighbourhood, meal blocking grid). A 65-year-old will see this wall of fields and feel anxious about making mistakes.

5. **Toggle switches** (for "Keep this shiva page private" and "Pause for Shabbat") use a slider pattern that some older users do not recognize as interactive. The toggle is 48x26px -- adequate but could be larger.

6. **Date inputs** use native `<input type="date">` which renders differently on every browser/device. On iPhone, it opens a spinner; on Android, a calendar. Neither clearly communicates "pick a date within the next 2 weeks."

7. **"Number of People to Feed per Meal" defaults to 20** with a plain number input. A 65-year-old may not realize they can (or should) change this.

8. **The caterer browser** ("Browse Local Options") opens an inline scrollable grid limited to 320px height -- this nested scrolling is confusing on mobile.

9. **Consent checkbox text** is 0.9rem (14.4px) and contains a link to the Privacy Policy -- the text is too small and the link target is too small for older fingers.

#### Where they would abandon:

1. **Step 2 field overload.** Seeing 12+ fields with optional/required mixed together causes paralysis.
2. **If they make an error and do not understand the error message.**
3. **After the "Search Section" if they cannot find the family** -- the "Set up without a listing" button uses an arrow entity (`&rarr;`) that may not render on all devices and the language is unclear.
4. **The success page "magic link" concept.** "Save this link to edit your support page later" requires understanding that a URL is a key. Many 65-year-olds will not save this link and will lose access to their page.

#### What is too small:

- Form labels: `0.95rem` (15.2px)
- Form hints: `0.85rem` (13.6px)
- Privacy notice text: `0.85rem` (13.6px)
- Toggle labels: `0.95rem` (15.2px)
- Toggle hints: `0.85rem` (13.6px)
- Caterer card details: `0.82rem` (13.1px)
- Consent label: `0.9rem` (14.4px)
- Review item labels: `0.95rem` (15.2px)
- Meal block day labels: `0.85rem` (13.6px)
- Meal block buttons: `font-size: 0.8rem; padding: 0.35rem 0.75rem` (~30px height -- too small)
- Stepper dots: 12px diameter with no text

#### Language they would not understand:

- "Magic link" (success state) -- sounds like spam
- "Meal blocking grid" -- technical term
- "Toggle" -- never use this word in UI
- "utm_source=nav&utm_medium=header" visible in help link href (not user-facing but sloppy)

#### Recommendations:

**Break Step 2 into two steps (making it a 4-step wizard):**

- Step 1: Your Information (as-is)
- Step 2: The Family (family name, address, city, privacy toggle)
- Step 3: Shiva Schedule (dates, shabbat pause, meals per day, dietary notes)
- Step 4: Review & Submit

**Replace stepper dots with labeled steps:**

**Before:**
```html
<div class="stepper">
    <div class="stepper-dot active"></div>
    <div class="stepper-line"></div>
    <div class="stepper-dot"></div>
    <div class="stepper-line"></div>
    <div class="stepper-dot"></div>
</div>
```

**After:**
```html
<div class="stepper">
    <div class="stepper-step active">
        <span class="stepper-number">1</span>
        <span class="stepper-label">You</span>
    </div>
    <div class="stepper-line"></div>
    <div class="stepper-step">
        <span class="stepper-number">2</span>
        <span class="stepper-label">Family</span>
    </div>
    <div class="stepper-line"></div>
    <div class="stepper-step">
        <span class="stepper-number">3</span>
        <span class="stepper-label">Schedule</span>
    </div>
    <div class="stepper-line"></div>
    <div class="stepper-step">
        <span class="stepper-number">4</span>
        <span class="stepper-label">Review</span>
    </div>
</div>
```

**Replace "magic link" language:**

**Before:**
```
Save this link to edit your support page later:
```

**After:**
```
Bookmark this page or save this link -- you will need it to make
changes later. We also sent it to your email.
```

**Add persistent labels above inputs:**

**Before:**
```html
<label for="organizerName">Your Name</label>
<input type="text" id="organizerName" placeholder="Your full name">
```

**After:**
```html
<label for="organizerName">Your Name</label>
<input type="text" id="organizerName" placeholder="e.g. Sarah Cohen">
```
(Keep label always visible; use placeholder as example, not instruction)

---

### 2.3 Shiva View Page

**File:** `/Users/erinkofman/Desktop/Neshama/frontend/shiva-view.html`

#### Where a 65-year-old would get confused:

1. **The meal calendar color system is unexplained.** Green-left-border = covered, amber = needs help, grey = taken. There is no legend visible before the calendar. A new visitor sees colored cards with no context.

2. **Meal slot interaction model is unclear.** Available slots show "+ Sign up to bring lunch" with a subtle pulse animation, but nothing says "tap here to volunteer." The slot looks like a status indicator, not a button.

3. **The volunteer signup modal** opens and asks for name, email, phone (optional), what food they will bring (food chips), servings counter, optional notes, and consent. This is 6-7 fields in a modal -- a lot for someone who just wants to say "I will bring dinner Tuesday."

4. **Food chips** ("Salad," "Main dish," "Soup," etc.) require understanding a chip-selection pattern. Some older users will not realize they can tap multiple chips.

5. **The servings counter** uses +/- buttons (44px circular) -- good size, but "4 servings" may confuse someone who is bringing a casserole. "How many people will your food serve?" is clearer.

6. **After signing up,** the address reveal shows the shiva address. But the flow is: tap slot > fill modal > submit > see address in modal > modal closes > address appears on page. This multi-step reveal may confuse someone who expected to just see the address.

7. **Coverage summary dots** at the top use 10px colored dots with 0.85rem labels -- both too small.

8. **The "Report this page" link** at the bottom is 1rem in sage-dark color -- it looks like it might be for reporting a problem, which could worry someone ("Did I do something wrong?").

#### Where they would abandon:

1. **If they do not realize the amber slots are tappable.** The lack of a visible "Sign Up" button on the page (outside the calendar) means the entire interaction model depends on understanding color-coded tappable slots.
2. **If the modal form feels too demanding** for what should be a simple "I will bring food" action.
3. **If they are confused by the coverage bar** and do not understand what percentage means in this context.

#### What is too small:

- Meal slot labels: `0.7rem` (11.2px) -- **critically small, 0.65rem on mobile (10.4px)**
- Coverage stat dots: 10px
- Coverage stat text: `0.85rem` (13.6px), `0.82rem` on narrow phones
- Shabbat badge: `0.7rem` (11.2px)
- Remove button: `0.7rem` (11.2px) with tiny padding
- Food chip text: `0.9rem` (14.4px), `0.85rem` on mobile
- Consent text: `1rem` (fine) but small checkbox (20px -- increase to 24px)
- Modal subtitle: `0.95rem` (15.2px)
- Organized by text: `1.05rem` -- acceptable but could be 1.1rem

#### Language they would not understand:

- "Coverage" as a concept (coverage summary, coverage bar, coverage strip)
- "Slot" (meal slot)
- "Servings" in the context of home-cooked food
- "Drop-off instructions" could be clearer as "Where and when to deliver food"

#### Recommendations:

**Add a visible call-to-action above the calendar:**

**Before:** Calendar appears with colored slots and no instruction.

**After:**
```html
<div class="calendar-instruction">
    <p>See what meals are still needed below.
    Tap any orange slot to sign up to bring food.</p>
</div>
```

**Add a color legend:**
```html
<div class="calendar-legend">
    <span class="legend-item">
        <span class="legend-swatch" style="background: #D2691E;"></span>
        Needs a volunteer
    </span>
    <span class="legend-item">
        <span class="legend-swatch" style="background: #a5d6a7;"></span>
        Covered -- thank you!
    </span>
</div>
```

**Simplify the volunteer modal:**

Reduce to 3 fields minimum:
1. Your name (required)
2. Your email (required)
3. What will you bring? (free text, one field, optional)

Move phone, servings counter, and food chips to optional expandable section: "Want to add more details? (optional)"

**Increase meal slot label size:**

**Before:**
```css
.meal-slot-label { font-size: 0.7rem; }
```

**After:**
```css
.meal-slot-label { font-size: 0.875rem; }
/* Mobile: */
.meal-slot-label { font-size: 0.8rem; } /* not 0.65rem */
```

---

### 2.4 Vendor Directory

**File:** `/Users/erinkofman/Desktop/Neshama/frontend/directory.html`

#### Where a 65-year-old would get confused:

1. **Filter pills and category pills** require understanding a pill-selection paradigm. Active pills change color (terracotta background, white text) but there is no explicit "Filter by:" label.

2. **The two-column grid on desktop** works well. On mobile (< 600px, implied by patterns), cards likely stack to one column -- good.

3. **Vendor card CTA** says "View Details" or similar -- but it is styled as a text link at the bottom of the card, not a button. Older users may not recognize it as tappable.

4. **Badge text** ("Kosher," "Delivery") at `0.8rem` (12.8px) with small padding is hard to read.

5. **The search input** uses a magnifying glass icon without a "Search" label. Some older users will not recognize the icon.

#### Where they would abandon:

1. **If they do not understand the filter system** and see all 100+ vendors at once -- scroll fatigue.
2. **If vendor cards do not clearly indicate** what the vendor offers (the description is clamped to 2 lines).

#### What is too small:

- Badge text: `0.8rem` (12.8px)
- Category pill text: `0.9rem` (14.4px)
- Vendor category label: `0.8rem` (12.8px)
- Filter select text: `0.95rem` (15.2px)
- Vendor location text: `0.9rem` (14.4px)
- Result count: `0.95rem` (15.2px)

#### Language they would not understand:

- "Filter" (use "Show me:" or "I am looking for:")
- Category names are generally clear, but ensure they match what older users would search for

#### Recommendations:

**Add explicit filter labels:**

**Before:**
```html
<div class="filter-pills-row">
    <!-- pills without context -->
</div>
```

**After:**
```html
<div class="filter-pills-row">
    <span class="filter-label">Show me:</span>
    <!-- pills -->
</div>
```

**Add "Search" label to search input:**

**Before:**
```html
<input type="text" placeholder="Search vendors...">
```

**After:**
```html
<label for="vendorSearch" class="sr-only">Search vendors by name</label>
<input type="text" id="vendorSearch" placeholder="Search by name...">
<!-- Add visible label or "Search" button next to input -->
```

**Increase badge text size to 0.875rem and padding.**

---

## 3. Priority Action Items

### Critical (Fix before launch or immediately after)

| # | Issue | Pages | Impact |
|---|-------|-------|--------|
| 1 | **Increase minimum font size to 16px across all elements.** No text on the site should be below 16px. Meal slot labels, hints, badges, and consent text are all currently below this. | All | Readability for entire target audience |
| 2 | **Add text labels to stepper dots** in the organize wizard. Users need to know "Step 1 of 3: Your Information." | shiva-organize | Reduces confusion and abandonment |
| 3 | **Add calendar legend and instruction text** to shiva-view. Users must understand the color system before encountering it. | shiva-view | Critical for the core signup flow |
| 4 | **Make meal slots obviously tappable.** Add a visible "Sign Up" button or "Tap to volunteer" label inside available slots. | shiva-view | Users cannot complete the primary action without this |
| 5 | **Rename "Listings" to "Obituaries"** in navigation across all pages. | All | Users cannot find the core feature |
| 6 | **Replace "magic link" language** on success page with plain explanation and email backup. | shiva-organize | Users will lose access to their page |

### High Priority (First improvement sprint)

| # | Issue | Pages | Impact |
|---|-------|-------|--------|
| 7 | **Split Step 2 into two steps** (Family Info + Schedule). The current step has 12+ fields. | shiva-organize | Reduces form abandonment |
| 8 | **Increase all button heights to 56px minimum.** Back buttons should have visible borders and fill. | All | Tap accuracy for older users |
| 9 | **Make WhatsApp share button visually dominant** (larger, green, top position in share section). Pre-compose the share message. | shiva-organize, shiva-view | WhatsApp is the primary distribution channel |
| 10 | **Add persistent labels above all form inputs.** Placeholder text must supplement, not replace, labels. | shiva-organize, shiva-view | Form comprehension for aging users |
| 11 | **Use consistent terminology.** Pick one term: "shiva meal page" and use it everywhere. Not "support page," "shiva page," "shiva support page," "meal coordination page." | All | Reduces confusion |
| 12 | **Add inline validation with friendly messages.** Show errors next to the field, not in a general error box at the bottom. | shiva-organize, shiva-view | Reduces anxiety and form abandonment |

### Medium Priority (Ongoing improvement)

| # | Issue | Pages | Impact |
|---|-------|-------|--------|
| 13 | **Simplify volunteer signup modal** to 3 core fields. Move food chips and servings to expandable optional section. | shiva-view | Reduces signup friction |
| 14 | **Shorten the "How It Works" explainer** to 3 bullet points maximum. Move the `<details>` expandable below the form. | shiva-organize | Reduces cognitive overload at page entry |
| 15 | **Add visible "Search" label** to directory search input. Add "Show me:" label before filter pills. | directory | Discoverability for older users |
| 16 | **Increase badge sizes** on vendor cards. Minimum 14px text with more padding. | directory | Readability |
| 17 | **Add a phone/email contact option** visibly on every page, not just in the footer. "Need help? Email contact@neshama.ca" | All | Trust building for non-digital-natives |
| 18 | **Improve hero section clarity** on landing page. Lead with what the site does, not the brand name. | landing | First-time visitor comprehension |
| 19 | **Replace toggle switches with checkboxes** where feasible. Checkboxes are a more universally understood pattern. | shiva-organize | Reduces interaction confusion |
| 20 | **Add "Back to top" button** on long pages (directory, shiva-view). | directory, shiva-view | Navigation aid for older users |

### Low Priority (Polish)

| # | Issue | Pages | Impact |
|---|-------|-------|--------|
| 21 | Consider bottom navigation bar on mobile instead of hamburger menu | All | Better mobile navigation for 50+ users |
| 22 | Add scroll indicators on long pages ("scroll down for more") | landing, directory | Content discovery |
| 23 | Add breadcrumbs to interior pages | All except landing | Orientation and wayfinding |
| 24 | Test contrast ratios at AAA level (7:1) for all text elements | All | Visual accessibility |
| 25 | Consider offering a "large text" toggle in the nav | All | User control over readability |

---

## 4. Sources

### UX for Older Adults
- [UX for Elderly Users: How to Design Patient-Friendly Interfaces](https://cadabra.studio/blog/ux-for-elderly/)
- [A Guide to Interface Design for Older Adults - Toptal](https://www.toptal.com/designers/ui/ui-design-for-older-adults)
- [Senior-Friendly Digital Design - GovWebworks](https://www.govwebworks.com/2025/09/03/senior-friendly-digital-design/)
- [UX Design for Older Adults | Building Digital Confidence](https://www.aufaitux.com/blog/ux-design-older-adults-digital-confidence/)
- [Optimizing mobile app design for older adults: systematic review - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12350549/)
- [4 Things to Do When Designing for Older Users - NN/g](https://www.nngroup.com/videos/designing-seniors/)
- [Usability for Older Adults: Challenges and Changes - NN/g](https://www.nngroup.com/articles/usability-for-senior-citizens/)

### Font Size & Typography
- [How to design font size for older adults: systematic literature review - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9376262/)
- [Frontiers in Psychology: Font size for older adults with mobile devices](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.931646/full)
- [Health Literacy Online: Use a readable font at least 16 pixels](https://odphp.health.gov/healthliteracyonline/design-easy-scanning/use-readable-font-thats-least-16-pixels)
- [Vision Changes: Typography for Aging Audiences](https://www.marketing-partners.com/conversations2/vision-changes-typography-for-aging-audiences)

### Grief & Bereavement UX
- [Finding a digital solution for grief - the UX part](https://medium.com/@uxalarcon/finding-a-digital-solution-for-grief-the-ux-part-4d4144aa13a9)
- [Grief-inspired design - UX Collective](https://uxdesign.cc/grief-inspired-design-b9710b04eda8)
- [Designing For Death & Grief Online - Funeral Guide](https://www.funeralguide.co.uk/blog/designing-for-death-online)
- [Designing content for people dealing with a death - DWP Digital](https://dwpdigital.blog.gov.uk/2020/02/06/designing-content-for-people-dealing-with-a-death/)
- [Modern Bereavement: A Model for Complicated Grief in the Digital Age](https://dl.acm.org/doi/10.1145/3173574.3173990)

### Accessibility & WCAG
- [W3C: Older Users and Web Accessibility](https://www.w3.org/WAI/older-users/)
- [Web Accessibility for Older Users - HubSpot](https://blog.hubspot.com/website/web-accessibility-for-older-users)
- [Web Accessibility for Older Adults - Level Access](https://www.levelaccess.com/blog/ensuring-web-accessibility-for-older-adults/)

### Form Design
- [Four considerations when designing forms for older adults - TechGuilds](https://www.techguilds.com/blog/accessible-web-forms-for-older-adults)
- [Designing Birthday Picker UX - Smashing Magazine](https://www.smashingmagazine.com/2021/05/frustrating-design-patterns-birthday-picker/)
- [Date-Input Form Fields: UX Design Guidelines - NN/g](https://www.nngroup.com/articles/date-input/)
- [Drop-Down Usability - Baymard Institute](https://baymard.com/blog/drop-down-usability)

### Touch Targets & Buttons
- [Optimal Size and Spacing for Mobile Buttons - UX Movement](https://uxmovement.com/mobile/optimal-size-and-spacing-for-mobile-buttons/)
- [Accessible Target Sizes Cheatsheet - Smashing Magazine](https://www.smashingmagazine.com/2023/04/accessible-tap-target-sizes-rage-taps-clicks/)
- [Touch Screen Interfaces for Older Adults: Button Size and Spacing - ResearchGate](https://www.researchgate.net/publication/225367546_Touch_Screen_User_Interfaces_for_Older_Adults_Button_Size_and_Spacing)
- [Touch Targets on Touchscreens - NN/g](https://www.nngroup.com/articles/touch-target-size/)

### Trust & Digital Immigrants
- [Digital Natives or Digital Immigrants: Impact on Online Trust - JMIS](https://www.jmis-web.org/articles/1214)
- [To trust or not to trust: older adults' online communication - Springer](https://link.springer.com/article/10.1007/s10660-023-09679-4)

### Error Messaging
- [Bridging the Generation Gap: UX Design for Elderly Users - Medium](https://medium.com/design-bootcamp/bridging-the-generation-gap-ux-design-for-elderly-users-made-simple-2eb4d6dc4ac9)
- [Error Message Guidelines - NN/g](https://www.nngroup.com/articles/error-message-guidelines/)
- [Age-Friendly Communication - Canada.ca](https://www.canada.ca/en/public-health/services/publications/healthy-living/friendly-communication-facts-tips-ideas.html)

### Mobile UX for 50+
- [Designing Mobile Experiences with Seniors in Mind - Bentley University](https://www.bentley.edu/centers/user-experience-center/designing-mobile-experiences-seniors-mind)
- [Design Guidelines of Mobile Apps for Older Adults - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10557006/)
- [JMIR: Design Guidelines of Mobile Apps for Older Adults](https://mhealth.jmir.org/2023/1/e43186)

### Food Delivery Apps
- [A Guide to Food Delivery Apps for Older Adults](https://www.bethesdagardensaz.com/blog/a-guide-to-food-delivery-apps-for-older-adults)
- [The Hunger Pains: Review of Food Delivery Apps - AFB](https://afb.org/aw/20/4/16411)
- [Ordering Food Online: What It Means for Older Adults - Peacefully](https://peacefully.com/ordering-food-online-what-it-means-for-older-adults/)
