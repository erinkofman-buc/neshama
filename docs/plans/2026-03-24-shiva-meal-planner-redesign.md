# Shiva Meal Planner UX Redesign Plan

**Date:** March 24, 2026
**Status:** Research & Planning (no code changes)
**Priority:** CORE PRODUCT -- this drives everything

---

## 1. Current UX Audit

### What Works
- **Privacy-first architecture** is solid: address only revealed after signup, private mode with access requests, consent checkboxes throughout
- **Shabbat awareness** built into the calendar -- pause toggle, visual distinction for Shabbat days
- **Coverage summary** with progress bar and colour-coded dots (green/yellow/red) gives at-a-glance status
- **Coverage strip** above the fold on mobile -- smart placement for the 80% iPhone audience
- **Meal blocking** lets organizers mark slots the family does not need, preventing unnecessary signups
- **Food chips** in the signup modal (Main dish, Soup, Salad, etc.) reduce typing friction
- **Caterer integration** in the organize wizard is contextual (browse during setup, not pushed as ads)
- **Print schedule** feature -- practical for the fridge at the shiva house
- **Organizer tools** are comprehensive: co-organizers, pass host, extend dates, post updates, thank-you notes, notification preferences, drop-off instructions
- **Share buttons** exist (WhatsApp, Email, Text) on the success screen
- **Duplicate/similar match detection** prevents creating duplicate pages

### What Doesn't Work

**Organizer Wizard (shiva-organize.html)**
1. **Title is generic and cold.** "Help Coordinate Support" reads like a form heading at a government office. Should feel like a caring friend saying "Let me help you set this up."
2. **Too much text before the form.** The explainer box, the caterer callout, the search section, the standalone callout -- a grieving person's friend is hit with 4 blocks of text before they can even start typing. They are already stressed.
3. **Step 1 asks for YOUR info first.** Wrong emotional order. The friend is thinking about the *family*, not about themselves. The first question should be "Who are we helping?" not "What's your email?"
4. **3-step stepper is misleading.** Step 2 (Shiva Details) contains 12+ fields including dates, address, city, neighbourhood, privacy toggle, meal blocking grid, guests per meal, dietary notes, special instructions, drop-off instructions, family notes, AND caterer browsing. That is not one step.
5. **Caterer browser in the wizard is premature.** At the moment of setup, the organizer is not thinking about vendors -- they are rushing to get the page live so they can share the link. Vendor discovery belongs AFTER the page is created, or on the shiva view page.
6. **No auto-fill of end date.** When you enter a start date, the end date should auto-populate 7 days later. Currently blank.
7. **No emotional warmth in the flow.** No reassurance copy, no "you're doing a beautiful thing," no acknowledgment that this is hard.
8. **Success state is functional, not emotional.** Green checkmark emoji + "Support Page Created" is transactional. This should be a moment of relief and purpose.
9. **Share flow is an afterthought.** Share buttons appear below the magic link box on the success screen. Should be the HERO of the success screen -- the entire point of creating the page is to share it.
10. **No guidance on what to put in the share message.** User has to compose their own WhatsApp/text message. The share should pre-compose a warm, ready-to-send message.

**Shiva View Page (shiva-view.html)**
1. **Hero section is informational, not emotional.** Family name, dates, organized by -- but no warmth. No "Here's how you can help" call to action above the fold.
2. **Color coding is INVERTED.** Green = "needs help" (empty), Red = "covered" (full). This is backwards from user intuition. Green means "good" universally. A friend landing on this page sees green and thinks "oh, they're fine." They should see red/urgency for uncovered days.
3. **"Needs help" vs "Help needed" inconsistency.** The badge text uses both phrases. Pick one.
4. **Info cards are below the calendar on mobile.** Dietary needs, address, donation link are pushed below the fold. A friend signing up needs to see dietary restrictions BEFORE they choose what to bring.
5. **Modal for signup is standard, not delightful.** The signup modal works but feels like a generic form. Could be warmer.
6. **Too many organizer sections visible.** On organizer view, there are 8+ management sections (edit, drop-off, notifications, co-org, pass host, extend dates, updates, thank you, donation prompt) all stacked vertically. Overwhelming -- needs tabs or accordion.
7. **"Can't cook?" section is positioned poorly.** It appears after the calendar, but a friend who can't cook will not scroll past 7 days of calendar to find alternatives. Should be visible alongside the calendar.
8. **Vendor integration is separated.** "Send Something Thoughtful" gift grid is far below the calendar. The "Can't cook? Send a meal from a local vendor" link is the right idea but it links away from the page.
9. **No emotional confirmation after signup.** After signing up, the confirmation shows the address and an "Add to Calendar" link. No warmth -- no "The [family] will be so grateful" moment.
10. **No real-time updates.** When someone signs up, the calendar does not update for other viewers without a refresh.

### Data Model Observations
- Schema is mature: shiva_support, meal_signups, shiva_co_organizers, shiva_updates, email_log, donation_prompts, shiva_host_transfers, shiva_access_requests, caterer_partners
- V1-V5 migrations show iterative growth; no structural issues
- Blocked meals, alternative contributions, additional contributors all supported
- Missing: no concept of "meal preferences" per day (e.g., family wants dairy Tuesday), no gift/order tracking from vendor directory

---

## 2. Competitor Analysis

### MealTrain (mealtrain.com)
**Strengths:**
- Dead simple setup: recipient name, address, dates, dietary needs, done
- Visual calendar with colour-coded days
- Shareable link is the centerpiece of the success screen
- Supports both meals AND gift cards (DoorDash, UberEats integration)
- Recipe database for inspiration
- One of the most recognized brands in this space

**Weaknesses:**
- Generic -- works for any occasion, so no grief-specific emotional design
- Calendar UI is functional but not warm
- No vendor directory or local caterer integration
- Takes a percentage of gift card purchases (monetization through friction)

**What to steal:**
- Setup simplicity -- get the page live in under 2 minutes
- Recipe/idea inspiration at point of signup
- Gift card integration as a "Can't cook?" path

### TakeThemAMeal (takethemameal.com)
**Strengths:**
- Even simpler than MealTrain -- one-page setup form
- Recipe database specifically for "meals that transport well"
- Searchable database of recipients (can find someone without having the link)
- Volunteer can see what others are bringing to avoid duplicates
- Works well on all devices

**Weaknesses:**
- Extremely bare-bones design -- looks like it was built in 2010
- No emotional design whatsoever
- No vendor integration
- No gift alternatives

**What to steal:**
- "Meals that transport well" recipe curation -- practical, thoughtful
- Searchable recipient database (Neshama already has this via obituary search)

### CareCalendar (carecalendar.org)
**Strengths:**
- Colour-coding: clearly distinguishes open needs, filled needs, and special dates
- Supports more than just meals: transportation, childcare, errands
- Automatic reminder emails to volunteers
- Birthday/occasion awareness in the calendar

**Weaknesses:**
- Interface is dated
- Setup is more complex than MealTrain
- No vendor/commercial integration

**What to steal:**
- Multi-need coordination (Neshama could expand to "rides to shiva," "help at the house")
- Colour-coding approach (but fix the green/red inversion)

### GiveInKind (giveinkind.com)
**Strengths:**
- All-in-one support page: meals, gift cards, GoFundMe, wishlists, errands
- "InKind Page" is a single hub for all help
- Integrates with DoorDash, Instacart, Amazon
- Beautiful, modern design
- Wishlists let the family specify exactly what they need

**Weaknesses:**
- Complexity can overwhelm users who just want to sign up for a meal
- Premium features behind paywall
- Not grief-specific

**What to steal:**
- Wishlist concept ("The family needs: paper plates, water bottles, tissues")
- Single hub approach -- the shiva page IS the support hub
- Commercial integration done tastefully (DoorDash, Instacart as "ways to help")

### Lotsa Helping Hands (lotsahelpinghands.com)
**Strengths:**
- Community-based model with volunteer management
- Calendar integrations
- Supports large volunteer groups
- Task-based coordination beyond meals

**Weaknesses:**
- Account creation required
- More complex than needed for a 7-day shiva

**What to steal:**
- Volunteer management tools for organizers

### Empathy.com
**Strengths:**
- Purpose-built for bereavement
- Hybrid human + digital support
- Guides families through logistics AND grief
- Beautiful, calming design language
- Progressive disclosure -- shows only what's relevant right now

**Weaknesses:**
- Focuses on the bereaved, not the helpers
- No meal coordination
- B2B model (sold to insurance companies, employers)

**What to steal:**
- Progressive disclosure -- do not show everything at once
- Tone and emotional design -- every word matters
- The concept of a "guide" walking you through

### CaringBridge (caringbridge.org)
**Strengths:**
- Journal/update model keeps community informed
- Visitor guestbook for condolences
- Well-known, trusted brand
- Simple, clean interface

**Weaknesses:**
- Focused on health journeys, not specifically grief
- No meal coordination built in

**What to steal:**
- Community guestbook model (Neshama already has tributes on memorials)
- Trust signals -- "Trusted by X families"

---

## 3. Emotional Design Principles

These principles must guide every decision:

### P1: Acknowledge the weight
The person setting up this page is carrying something heavy for someone else. Every screen should say "We see you. This matters." Not through words on every screen, but through pace, whitespace, warmth.

### P2: Reduce decisions, not options
A grieving friend does not want to think. Auto-fill what you can. Suggest smart defaults. Make the most common path require zero thought. BUT keep options accessible for those who need them.

### P3: The goal is the share, not the form
The organizer's mission is to get a link into a WhatsApp group as fast as possible. Everything before that is friction. Everything after that is gravy.

### P4: Green means go, red means stop
Fix the colour inversion. Green = covered/good. Red/warm = needs attention. Empty/open = needs help (use a warm, inviting colour, not alarm red).

### P5: Commercial feels like caring
Vendor integration should feel like "Here are some wonderful local businesses that deliver to the shiva house" not "Sponsored listings." The transition from "Can't cook?" to "Browse caterers" should feel like a friend's recommendation, not a sales funnel.

### P6: Mobile is the product
80% of users are on iPhone, probably in a car, in an elevator, standing in their kitchen. Every tap target must be 48px+. Every flow must complete in one hand. The calendar must render beautifully at 375px.

### P7: Confirmation is celebration
Signing up to help should feel GOOD. The confirmation should make you feel like you did something meaningful. "Sarah, thank you. The Goldberg family will know you're bringing soup on Tuesday."

---

## 4. Redesign Specs

### 4A. Organizer Wizard Redesign

#### New Step Structure (5 micro-steps, feels like 3)

**Step 1: "Who are we helping?"**
- Single field: Family Name (large, centered, prominent)
- Obituary search below (optional): "Link to their memorial listing on Neshama" with inline search
- Reassurance copy: "You're setting up meal coordination so the community can show up for the [family]. Everything on this page can be changed later."
- Auto-detect if a shiva page already exists for this family (existing duplicate detection)
- [Continue] button

**Step 2: "When and where?"**
- Start date (date picker, default to today)
- End date (auto-fill 7 days from start, editable)
- Shiva address (with privacy notice inline: "Only shared with confirmed volunteers")
- City dropdown (Toronto/Montreal)
- Neighbourhood (conditional, appears after city selection)
- Shabbat pause toggle (default on, with one-line explanation)
- [Continue] button, [Back] link

**Step 3: "What should people know?"**
- Dietary needs (prominent, with suggestion chips: "Kosher", "Nut-free", "Vegetarian", "Gluten-free", "No restrictions")
- Number of people to feed (stepper widget, default 20)
- Drop-off instructions (collapsible, optional)
- Special instructions (collapsible, optional)
- Family notes (collapsible, optional, "Anything visitors should know?")
- [Continue] button, [Back] link

**Step 4: "About you"**
- Your name
- Your email
- Phone (optional)
- Relationship (Family / Friend)
- Privacy consent checkbox
- Privacy toggle: "Keep this page private" with explanation
- [Create Support Page] button, [Back] link

**Step 5: SUCCESS -- "You're all set. Now share it."**
(See section 4D for share flow redesign)

#### Removed from wizard:
- Meal blocking grid -- move to organizer view (post-creation)
- Caterer browser -- move to shiva view page as contextual recommendation
- "How it works" explainer -- replace with single reassurance line
- Donation URL field -- move to organizer view (post-creation)

#### Wireframe: Step 1

```
+------------------------------------------+
|  Neshama                        [menu]   |
+------------------------------------------+
|                                          |
|     Help Coordinate Meals                |
|     for a Family Sitting Shiva           |
|                                          |
|  You're doing something meaningful.      |
|  Let's get this set up.                  |
|                                          |
|  +------------------------------------+  |
|  |                                    |  |
|  |  Who are we helping?               |  |
|  |                                    |  |
|  |  Family Name                       |  |
|  |  [  The Goldberg Family         ]  |  |
|  |                                    |  |
|  |  Link to their memorial?          |  |
|  |  [Search listings...          ]    |  |
|  |  (optional)                        |  |
|  |                                    |  |
|  |         [ Continue  ]              |  |
|  |                                    |  |
|  +------------------------------------+  |
|                                          |
|  --- . --- . --- . ---                   |
|   *       o       o       o              |
|                                          |
+------------------------------------------+
```

#### Wireframe: Step 5 (Success/Share)

```
+------------------------------------------+
|  Neshama                        [menu]   |
+------------------------------------------+
|                                          |
|           The Goldberg Family            |
|        meal page is ready to share       |
|                                          |
|    You've set up 7 days of meal          |
|    coordination. Now let your            |
|    community know how they can help.     |
|                                          |
|  +------------------------------------+  |
|  |                                    |  |
|  |  [ Share on WhatsApp         ]     |  |
|  |                                    |  |
|  |  [ Share via Email           ]     |  |
|  |                                    |  |
|  |  [ Copy Link                 ]     |  |
|  |                                    |  |
|  |  [ Share via Text            ]     |  |
|  |                                    |  |
|  +------------------------------------+  |
|                                          |
|  View & manage your support page -->     |
|                                          |
|  +------------------------------------+  |
|  |  Your organizer link (save this):  |  |
|  |  neshama.ca/shiva/abc123?t=xyz     |  |
|  |  [ Copy Organizer Link ]           |  |
|  +------------------------------------+  |
|                                          |
|  Need help with meals?                   |
|  Browse local caterers -->               |
|                                          |
+------------------------------------------+
```

### 4B. Shiva View Page Redesign

#### Above the Fold (Mobile -- 667px viewport)

The first screen a friend sees must contain:
1. Family name (large, Cormorant Garamond)
2. Shiva dates
3. Coverage status ("4 of 10 meals covered -- 6 still needed")
4. Coverage progress bar
5. Primary CTA: "Sign Up to Bring a Meal" (large, terracotta button)
6. Secondary CTA: "Can't cook? Other ways to help" (text link)

#### Wireframe: Shiva View -- Above the Fold (Mobile)

```
+------------------------------------------+
|  Neshama                        [menu]   |
+------------------------------------------+
|                                          |
|       The Goldberg Family                |
|                                          |
|   Mar 24 - Mar 30, 2026                 |
|   Organized by Sarah Cohen              |
|                                          |
|   ---- --- --- --- --- --- ----          |
|                                          |
|   4 of 10 meals covered                 |
|   [======------] 40%                    |
|   6 meals still needed                  |
|                                          |
|   +----------------------------------+   |
|   |    Sign Up to Bring a Meal       |   |
|   +----------------------------------+   |
|                                          |
|   Can't cook? Other ways to help -->     |
|                                          |
|   +----------------------------------+   |
|   | Dietary: Strictly kosher,        |   |
|   | nut allergy. ~20 people/meal.    |   |
|   +----------------------------------+   |
|                                          |
+------------------------------------------+
```

#### Meal Calendar Redesign

**Colour fix (CRITICAL):**
- Covered (both meals signed up): Sage green background, green left border, "Covered" badge
- Partial (one meal signed up): Gold/amber background, gold left border, "1 meal needed" badge
- Open (no meals signed up): Warm rose/salmon background (#FFF0ED), terracotta left border, "Help needed" badge with subtle pulse animation
- Shabbat: Neutral taupe, "Shabbat" badge (unchanged)

**Layout change:**
- Each day card shows: Date header | Lunch slot | Dinner slot (side by side on desktop, stacked below 375px)
- Available slots show a tappable "Sign up" button with a + icon
- Taken slots show volunteer name, what they're bringing, servings
- On days that need help, the "Sign up" button is larger and more prominent

**"Can't Cook?" integration:**
- After the calendar (or floating at bottom on mobile), a persistent bar:
  "Not sure what to bring? Browse local caterers who deliver to shiva homes"
  [Browse Caterers] [Send a Gift]

#### Wireframe: Meal Calendar Day Card

```
+------------------------------------------+
| Tue, Mar 25                  Help needed  |
+--------------------+---------------------+
|  LUNCH             |  DINNER             |
|                    |                     |
|  Sarah C.          |  +  Sign up         |
|  Chicken soup      |                     |
|  (8 servings)      |  Tap to bring       |
|                    |  dinner for ~20     |
+--------------------+---------------------+

+------------------------------------------+
| Wed, Mar 26                    Covered    |
+--------------------+---------------------+
|  LUNCH             |  DINNER             |
|                    |                     |
|  David R.          |  Rachel M.          |
|  Deli platters     |  Pasta + salad      |
|  (20 servings)     |  (15 servings)      |
+--------------------+---------------------+

+------------------------------------------+
| Fri, Mar 28                    Shabbat    |
+------------------------------------------+
|  Paused for Shabbat -- Shabbat Shalom    |
+------------------------------------------+
```

### 4C. Signup Modal Redesign

**Current:** Generic form with name, food chips, servings, email, phone, consent, submit.

**Redesigned flow:**

1. **Header with context:** "Bring a meal for the Goldberg family" + "Tuesday, March 25 -- Dinner"
2. **Dietary reminder:** Prominent banner: "The family keeps strictly kosher and has a nut allergy" (pulled from shiva details)
3. **What are you bringing?** Food chips + custom text (keep existing, it works well)
4. **"Need ideas?" inline:** "Browse caterers who deliver to the Goldberg home" -- link to directory filtered by city/neighbourhood. NOT a modal-in-a-modal; opens in new tab or slides into view.
5. **Servings:** Stepper (keep existing)
6. **Your info:** Name, email, phone (keep existing, but prefill from localStorage if returning user)
7. **Consent + Submit**
8. **Confirmation screen (in-modal):**
   - "Thank you, Sarah. The Goldberg family will know you're bringing chicken soup on Tuesday."
   - Address reveal (existing feature, keep it)
   - "Add to your calendar" button (keep existing)
   - "Share this page with others who want to help" [WhatsApp] [Copy Link]
   - Dietary reminder: "Remember: the family keeps strictly kosher"

### 4D. Share Flow Redesign

**The share is the product.** Every share message must be pre-composed, warm, and ready to send.

**WhatsApp share message (pre-composed):**
```
Hi -- I've set up a meal coordination page for the [Family Name] family
who are sitting shiva [dates]. If you'd like to bring a meal, you can
sign up here:

[link]

[X] of [Y] meals still need to be covered. Every meal makes a
difference.
```

**Email share (pre-composed):**
- Subject: "Meal coordination for the [Family Name] family"
- Body: Similar to WhatsApp, but slightly more formal. Includes link, coverage status, dietary notes.

**Text/SMS share (pre-composed):**
```
Meal coordination for the [Family Name] shiva ([dates]).
[X] meals still needed. Sign up here: [link]
```

**Post-signup share (for volunteers who just signed up):**
```
I just signed up to bring [meal] to the [Family Name] shiva on [date].
[X] meals still need to be covered -- can you help?

[link]
```

### 4E. Vendor Integration Redesign

**Principle:** Vendors appear as a helpful resource at the moment of need, never as an interruption.

**Touchpoint 1: Signup modal**
When a friend is deciding what to bring, a subtle inline link:
"Need ideas? Browse caterers who deliver to [City]"
Links to /help/food filtered by the shiva's city.

**Touchpoint 2: "Can't cook?" section on shiva view**
Redesigned as a persistent section below the calendar:
```
+------------------------------------------+
|  Can't cook or too far away?             |
|                                          |
|  [Send a meal] via local caterer         |
|  [Send a gift basket]                    |
|  [Send a gift card] (DoorDash, etc.)     |
|  [Make a donation] in their honour       |
+------------------------------------------+
```

**Touchpoint 3: Post-creation (organizer wizard success)**
"Need help arranging meals? Browse local caterers and restaurants"
This is where the caterer browser currently lives in the wizard -- move it here.

**Touchpoint 4: Organizer email notifications**
When the organizer receives a "3 meals still uncovered" alert, the email includes:
"You can also order from a local caterer: [Browse caterers in City]"

**Touchpoint 5: Recommended caterers on shiva page**
If the organizer selected recommended vendors during setup (or later via organizer view), those appear as a subtle card:
"The organizer recommends these local options:"
[Vendor cards -- 1-3 max]

**Revenue path:**
- Caterer directory is free to browse
- Featured/promoted listings: vendors pay for priority placement
- Lead tracking: when someone clicks "Order from [Vendor]" from a shiva page, that's a trackable referral
- Future: in-app ordering with commission (Month 2-3 roadmap item)

### 4F. Organizer View Redesign

The organizer view currently shows 8+ management sections stacked vertically. Redesign into tabbed sections:

**Tab 1: Overview (default)**
- Coverage summary (progress bar + stats)
- Meal calendar with remove buttons
- Volunteer list with contact info

**Tab 2: Settings**
- Edit shiva details (address, dates, dietary)
- Privacy toggle
- Meal blocking grid
- Extend dates
- Recommended vendors

**Tab 3: Communication**
- Post an update
- Drop-off instructions
- Thank-you notes
- Notification preferences

**Tab 4: Team**
- Co-organizers (invite, manage)
- Pass host

On mobile, tabs become a horizontal scroll or accordion sections.

---

## 5. Mobile-First Specs

### Viewport Targets
- Primary: 390px (iPhone 14/15 -- most common)
- Secondary: 375px (iPhone SE, older models)
- Narrow: 360px (Android small)
- Tablet: 768px
- Desktop: 1024px+

### Touch Targets
- All buttons: minimum 48px height, 44px width
- Tap targets with at least 8px spacing between them
- Food chips: 48px minimum height
- Calendar day cards: full-width tappable area for available slots

### Performance
- First meaningful paint: under 1.5s on 4G
- Calendar render: under 500ms for 7-day shiva
- Signup modal: instant (pre-loaded, display:none until triggered)

### Gestures
- Swipe between wizard steps (optional, button navigation primary)
- Pull-to-refresh on shiva view page
- Bottom sheet modal on mobile (current implementation -- keep it, it works well)

### Offline Awareness
- If user is offline when they try to sign up, show: "You appear to be offline. Your signup will be saved when you reconnect." (Future enhancement, not Phase 1)

---

## 6. Phased Implementation Plan

### Phase 1: Emotional Polish (1-2 days)
*Low-risk, high-impact changes to existing pages*

- [ ] Fix colour inversion on meal calendar (green = covered, warm/rose = needs help)
- [ ] Rewrite page titles and subtitles with warm, empathetic copy
- [ ] Pre-compose share messages for WhatsApp, Email, Text
- [ ] Auto-fill end date (start + 7 days) in organizer wizard
- [ ] Add dietary suggestion chips to the wizard
- [ ] Make share buttons the HERO of the success screen
- [ ] Add emotional confirmation copy after volunteer signup ("Thank you, [name]. The [family] will know you're coming.")
- [ ] Add dietary reminder banner in signup modal
- [ ] Fix "Needs help" / "Help needed" inconsistency

### Phase 2: Wizard Restructure (2-3 days)
*Reorder and simplify the organizer wizard*

- [ ] Reorder steps: Family first, then dates/location, then details, then your info
- [ ] Split Step 2 into 2-3 micro-steps (dates/location, dietary/instructions)
- [ ] Move meal blocking grid to organizer view (post-creation)
- [ ] Move caterer browser to success screen and shiva view page
- [ ] Add progress stepper with 4-5 dots instead of 3
- [ ] Reduce total wizard to 4 steps + success screen

### Phase 3: Shiva View Overhaul (3-4 days)
*Redesign the friend-facing page*

- [ ] New above-the-fold layout: family name, dates, coverage, CTA
- [ ] Redesigned meal calendar cards with fixed colours
- [ ] Persistent "Can't cook?" section alongside calendar
- [ ] Improved signup modal with dietary context and vendor link
- [ ] Post-signup share prompt ("Share this page with others")
- [ ] Organizer view tabbed layout (Overview / Settings / Communication / Team)
- [ ] Dietary info card visible before calendar on mobile

### Phase 4: Vendor Integration Polish (1-2 days)
*Make vendor touchpoints feel natural*

- [ ] "Need ideas?" link in signup modal filtered by shiva city
- [ ] "Can't cook?" section links to directory with city pre-filtered
- [ ] Recommended caterers card on shiva view (if organizer selected vendors)
- [ ] Caterer link in organizer notification emails
- [ ] Track referral clicks from shiva pages to vendor directory

### Phase 5: Advanced Features (backlog, post-launch)
*From the Hardening Sprint backlog*

- [ ] Role-based views (organizer vs volunteer vs public) -- Priority 1 from backlog
- [ ] Real-time calendar updates (polling or SSE)
- [ ] Returning user detection (prefill name/email from localStorage)
- [ ] "Family needs" wishlist (paper plates, water, tissues)
- [ ] Multi-need coordination (rides, childcare, errands)
- [ ] In-app vendor ordering with commission tracking

---

## 7. Vendor Monetization Connection

The meal planner drives vendor revenue through a natural funnel:

```
Friend receives WhatsApp link
        |
        v
Lands on shiva view page
        |
    +---+---+
    |       |
    v       v
Signs up   Can't cook
to cook    / too far
    |       |
    |       v
    |   "Browse local caterers"
    |       |
    |       v
    |   Vendor directory
    |   (filtered by city)
    |       |
    |       v
    |   Clicks vendor
    |   (trackable referral)
    |       |
    v       v
Confirmation  Order placed
    |       (commission)
    v
"Share with others"
(more visitors)
```

**Key insight:** The meal planner is not a feature. It is the acquisition engine. Every shiva page generates 10-50 visitors (family, friends, community). Each visitor is a potential vendor directory user. The meal planner must be world-class so that people *want* to share the link, which brings more visitors, which drives vendor traffic.

**Monetization touchpoints (never feel like ads):**
1. "Need ideas?" in signup modal -- helpful, contextual
2. "Can't cook?" section -- solves a real problem
3. Recommended caterers -- organizer-curated, trustworthy
4. Organizer notification emails -- "Fill uncovered days with a local caterer"
5. Post-shiva follow-up email -- "Thank you for using Neshama. Browse our directory for future needs."

**Revenue tracking needed:**
- `referral_source: 'shiva_page'` on vendor directory clicks
- `shiva_id` param passed to vendor directory for attribution
- Conversion tracking: click-through from shiva page to vendor page to vendor website/order

---

## 8. Copy & Tone Guide for Meal Planner

Every word on these pages must pass the test: "Would this feel okay to read the week your parent died?"

### Organizer Wizard
- Title: "Help Coordinate Meals" --> "Set Up Meal Support"
- Subtitle: "Set up meal coordination for a family during their shiva" --> "Organize meals so the community can show up for the [family]"
- Step 1 heading: "Your Information" --> "Who are we helping?"
- Step 2 heading: "Shiva Details" --> "When and where?"
- Success heading: "Support Page Created" --> "The [family] meal page is ready to share"
- Success body: "The community can now sign up to help coordinate meals." --> "You've set up [X] days of meal coordination. Now let your community know how they can help."

### Shiva View Page
- Section heading: "Meal Schedule" --> "Meal Calendar"
- Empty calendar prompt: (currently none) --> "This family could really use your help. Tap any available slot to sign up."
- Coverage: "4/10 meals" --> "4 of 10 meals covered -- 6 still needed"
- Signup CTA: (currently just tapping a slot) --> Add persistent button: "Sign Up to Bring a Meal"

### Signup Modal
- Heading: "Sign Up to Bring a Meal" --> "Bring a meal for the [Family] family"
- Subtitle: (date/time) --> "Tuesday, March 25 -- Dinner for approximately 20 people"
- Confirmation: "Thank you for signing up!" --> "Thank you, [Name]. The [Family] family will know you're bringing [meal] on [date]."

### Share Messages
- Never clinical. Never transactional.
- Always mention the family by name.
- Always include coverage status (creates urgency without pressure).
- Always end with the link.

---

## 9. Backlog Integration

Items from the "Shiva Organizer Hardening Sprint" that this redesign addresses or enables:

| Backlog Item | Status in This Plan |
|---|---|
| Redesign shiva page views (role-based) | Phase 3 + Phase 5 |
| Privacy modes (public vs private) | Already built; Phase 3 improves the private page UX |
| Token-based access | Already built; no changes needed |
| Organizer view redesign | Phase 3 (tabbed layout) |
| Volunteer/public view separation | Phase 3 (above-the-fold redesign) |
| Pass Host | Already built; moved to Team tab in Phase 3 |
| $18 donation prompt | Already built; Phase 3 positions it better |
| Above-the-fold mobile optimization | Phase 3 (new hero layout) |
| Below-the-fold content ordering | Phase 3 (dietary before calendar, vendor after) |
| Extend shiva days UI | Already built; moved to Settings tab in Phase 3 |

---

## Appendix: Competitor Feature Matrix

| Feature | Neshama | MealTrain | TakeThemAMeal | CareCalendar | GiveInKind |
|---|---|---|---|---|---|
| Free | Yes | Freemium | Yes | Freemium | Freemium |
| Grief-specific | Yes | No | No | No | No |
| Visual calendar | Yes | Yes | Yes | Yes | No |
| Colour-coded coverage | Yes* | Yes | No | Yes | No |
| Dietary notes | Yes | Yes | Yes | Yes | Yes |
| Share buttons | Yes | Yes | Limited | No | Yes |
| Vendor directory | Yes | No | No | No | DoorDash etc. |
| Gift alternatives | Yes | Gift cards | No | No | Wishlists |
| Co-organizers | Yes | No | No | No | No |
| Privacy controls | Yes | No | No | No | No |
| Shabbat awareness | Yes | No | No | No | No |
| Print schedule | Yes | No | No | Yes | No |
| Mobile-optimized | Yes | Yes | Yes | No | Yes |
| Meal blocking | Yes | No | No | No | No |
| Thank-you notes | Yes | No | No | No | No |
| Donation prompt | Yes | No | No | No | GoFundMe |

*Colour coding exists but is inverted (green = empty, red = full). Fix in Phase 1.

**Neshama's advantages:** Shabbat awareness, privacy controls, co-organizers, vendor directory, grief-specific design, meal blocking, thank-you notes. These are significant differentiators. The redesign should amplify them, not replace them.

---

*This plan is research and specs only. No code has been changed. Implementation requires Erin's review and approval before any work begins.*
