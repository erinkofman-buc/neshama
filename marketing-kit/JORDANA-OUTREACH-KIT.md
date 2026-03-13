# Neshama — Cofounder Briefing for Jordana
**Updated: March 2, 2026**

Jordana — this is everything. How the product works, how it makes money, what we're tracking, what's next, and why your outreach right now is the single most important thing for Neshama.

---

## Why Your Outreach Matters — Read This First

The product is built. 24 pages, 200+ obituaries, 129 vendors, 18 caterers, meal coordination, yahrzeit reminders, guestbooks — all live, all working. The tech is done.

But none of it matters without people.

Right now, Neshama is a fully stocked store with no customers walking in. The obituaries update daily. The "How Can I Help?" hub is ready. The meal coordination tool works. But families don't know it exists yet. Vendors don't know they're being tracked. Synagogues haven't heard of us.

**Your outreach is the ignition.** Every WhatsApp message you send, every chesed committee you tell, every caterer friend you loop in — that's what turns a built product into a living community. We can't buy this kind of trust. It has to come from you, person to person, community to community.

Here's why timing matters:
- **Vendor revenue depends on traffic data.** We can't sell featured listings until we show vendors they're getting clicks. Your outreach drives the traffic that creates the data that generates the revenue.
- **Community trust compounds.** The earlier real people start using it, the more organic word-of-mouth builds.
- **We're spending $8.25/month.** We don't need millions of users. We need the right 500 people — and you know them.

---

## Our Story — When People Ask "Why Did You Build This?"

Your mom was a therapist who read obituaries to identify former patients and pay her respects. She was also the person who made the big salads, who cooked, who brought everyone together around a table. When you lost her to MSA nearly eight years ago, you started doing both — reading every obituary, and feeding people. Jem Salads grew out of that. Carrying on what she did.

And through catering shivas every single week, you saw how broken the process was. Three different funeral home websites. Meals overlapping on Monday, nothing on Wednesday. Families drowning in logistics during the worst week of their lives. You came to me and said: there should be one place for all of this.

My reasons are different but they point in the same direction. My dad is from Montreal. My grandmother was American. My husband's family is in Germany. I know what it's like to hear about a loss too late, or not at all — to feel disconnected from community across countries and time zones.

Thirty years of friendship and one shared conviction: a lost soul should never be lost. That's Neshama.

**When someone asks you about it, you don't need a pitch. You just tell the truth.** Your mom read obituaries. You do the same. You started feeding people the way she did. Through catering you saw the gap. We built the thing. That's the whole story.

---

## What Neshama Is

Neshama (neshama.ca) is a free community platform for Jewish families in Toronto and Montreal. When someone passes away, the people around them want to help — but the logistics are a mess. We bring everything together in one place.

**What's live right now:**
- **Obituary feed** — Aggregated automatically from 4 funeral homes (Steeles, Benjamin's, Paperman's, Misaskim). 200+ real listings. Updated daily.
- **Shiva meal coordination** — A friend or family member creates a shiva page. Community members sign up for specific meal slots (breakfast/lunch/dinner) on each day. Everyone sees what's covered and what's still needed. Supports co-organizers.
- **"How Can I Help?" hub** — 110 verified vendors: 86 local food partners (caterers, bakeries, delis) + 24 gift options (baskets, comfort items, memorial trees). Browsable by category.
- **Caterer directory** — 18 caterers with detailed profiles (kosher level, delivery area, price range, descriptions).
- **Digital condolence guestbook** — Friends leave tributes, light a memorial candle, share memories. Exportable as a PDF keepsake the family keeps forever.
- **Yahrzeit reminders** — This is a big one. Annual reminders on the exact Hebrew calendar anniversary of a loved one's passing. Users enter the info once, and every year on the yahrzeit date they get an email reminder. Fully automated — runs every morning at 9 AM. Handles leap years, Adar edge cases, everything. Double opt-in so no one gets surprised. This feature alone is something no other site does properly.
- **Plant a Memorial Tree** — JNF partnership for tree planting in Israel ($18/tree).
- **"What to Bring to a Shiva" guide** — Educational content that ranks in search.
- **Prepare the Home page** — Products and guidance for setting up the shiva home.

**Scale:** 27 pages, 200+ obituaries, 129 local food partners and gift vendors, 18 caterers. This is not a prototype.

---

## How Users Find Us & What They Experience

### The First Visit
Someone finds neshama.ca — through a Google search ("Toronto Jewish obituaries"), a WhatsApp share, or word of mouth. They land on the homepage.

**Above the fold:** They see the obituary search bar, a clear explanation of what the site does, and jump-navigation to all features. No sign-up required. No paywall. Everything is immediately accessible.

### The Email Popup
**When:** After 45 seconds of idle time on any page.
**What:** A non-intrusive overlay: "Stay connected to our community. When someone in our community passes away, you'll know — so you can show up when it matters."
**Fields:** Email, frequency preference (daily or weekly digest), location (Toronto and/or Montreal).
**CTA:** "Keep Me Informed"
**Rules:** Only shows once per session. If dismissed, waits 24 hours before showing again. Once subscribed, never shows again. This is tracked via localStorage on their device.

**What happens with those emails:** They go into our subscriber database. We send daily or weekly digest emails with new obituaries. Powered by SendGrid.

### The Sustain Page
**Where:** neshama.ca/sustain (linked in nav + footer on every page)
**When shown:** Only when someone clicks it. We never push this during grief. No pop-ups for payment. Ever.
**What it is:** A voluntary annual contribution of $18 CAD (one chai). Not a donation — we're a for-profit. Not tax-deductible. We're transparent about this.
**Payment:** Stripe Checkout → annual recurring subscription → success page.
**Amounts:** Default $18/year. Custom amounts available.
**Key line on the page:** "Voluntary contribution, not a charitable donation. Not tax-deductible."

---

## How We Make Money

Three revenue streams. The first is the main one.

### 1. Featured Vendor Listings (Primary Revenue)

This is B2B, not family-facing.

**How it works:**
- All 129 vendors have a free listing. That never changes. Nobody gets removed.
- Behind the scenes, we track every click and view on every vendor listing (more on this below).
- **Month 1-2:** We email each vendor: "Hey, you're listed on Neshama. Families are finding you. Here's your free listing."
- **Month 2-3:** We start sending automated monthly performance reports: "Your listing got X views and Y clicks this month."
- **Month 3+:** Now we have real data. We reach out: "You got 47 clicks last month. Featured vendors get ~3x more visibility. Want to try it?"

**Featured listing ($49/mo founding rate):**
- Priority placement in directory (appears first)
- "Featured" badge on listing
- Photo gallery on profile
- Access to detailed analytics dashboard
- Monthly performance reports

**The math for vendors:** One shiva catering order = $200-$1,500. One order covers months of listing fees. Sells itself once we have the data.

**Year 1 target:** 5-15 paying vendors at $49/month.

### 2. Community Sustainers (Voluntary)

- $18 CAD/year (chai)
- Voluntary, not a paywall. Nothing gets locked.
- 10% goes to Jewish community organizations (JFCS Toronto, Federation CJA Montreal)
- **Year 1 target:** 100-500 people × $18 = $1,800-$9,000/year

### 3. Affiliate & Partnerships

- **Amazon affiliate links** on all product pages — tag `neshama07-20`. When someone clicks through and buys, we get 1-5% commission depending on category.
- **JNF memorial tree planting** — $18/tree partnership
- **UTM-tracked vendor links** — all outbound vendor links tagged with `utm_source=neshama` for attribution
- **Year 1 target:** $870-$4,680/year

### Total Year 1 Projections
| Scenario | Revenue | What It Takes |
|----------|---------|---------------|
| Slow start | $2,000-$4,000 | 2-3 paying vendors, 50 sustainers, minimal affiliate |
| Moderate | $8,000-$15,000 | 5-8 paying vendors, 150 sustainers, steady traffic |
| Strong | $20,000-$30,000 | 10-15 paying vendors, 300+ sustainers, organic growth |
| **Monthly costs** | **$8.25** | Render hosting + domain |

Break-even: Month 3-4 at the slow start level. The math works because costs are nearly zero.

---

## What We're Tracking (Metrics)

### Vendor Performance (This Is How We Sell Featured Listings)

Every vendor interaction is tracked:

1. **Profile views** — When someone views a vendor's listing page. Logged with timestamp and referrer (which page they came from).
2. **Website clicks** — When someone clicks through to a vendor's actual website. Routed through `/api/track-click` which logs the click then redirects. We capture: vendor slug, destination URL, referrer page, timestamp.
3. **Lead submissions** — When someone fills out the inquiry form on a vendor page. We capture: vendor name, contact info, event type, date, guest count, message.

**Monthly vendor reports** go out automatically on the 1st of each month. Each vendor gets: profile views, website clicks, and inquiry count for the past 30 days.

### Email Subscriber Metrics
- Total confirmed subscribers
- Frequency breakdown (daily vs. weekly)
- Location breakdown (Toronto vs. Montreal)
- Bounce count per subscriber
- Unsubscribe rate + reasons (we ask why)
- Last email sent date per subscriber

### Shiva Adoption Metrics
- Shiva pages created
- Meal signups per shiva
- Co-organizer invites
- Community updates posted

### Site-Wide Analytics (Plausible)
Plausible analytics is on every single page. It tracks:
- Page views, unique visitors, sessions
- Referral sources (where traffic comes from)
- Device/browser breakdown
- User journey through the site
- **Dashboard:** plausible.io (we'll share access)

### Amazon Affiliate
Amazon Associates dashboard shows clicks and commissions. Tag: `neshama07-20`.

---

## Your Dashboard

**URL:** neshama.ca/dashboard (or neshama.ca/cofounder)

This is a live dashboard — not linked from the public site. Only accessible if you know the URL. Shows:

- **Overview cards** — Obituaries, vendors, caterers, subscribers, tributes, active shiva pages. Real-time from the database.
- **Vendor click tracking** — Table of every vendor with their total clicks, views, and last activity.
- **Recent activity** — Latest obituaries and guestbook entries.
- **Revenue tracking** — Affiliate clicks, sustainer count (Stripe integration coming).
- **Outreach progress** — Checkboxes for your channels (synagogues, WhatsApp groups, funeral homes, vendors contacted, media). Your check marks persist between sessions.

Auto-refreshes every 60 seconds. Works on mobile.

---

## What's Built, What's Next

### Done ✅
- Full product live on neshama.ca (24 pages, all features working)
- 200+ obituaries from 4 funeral homes (auto-scraped daily)
- 129 vendors, 18 caterers in directory
- Stripe payments live (tested with real payment + refund)
- Email subscription with daily/weekly digests via SendGrid
- Yahrzeit reminder system (Hebrew calendar, daily 9AM cron)
- All tracking infrastructure (vendor clicks, views, leads, analytics)
- Monthly vendor performance reports (automated)
- Amazon affiliate links on all product pages
- UTM tracking on all outbound vendor links
- 7 beta fixes deployed from tester feedback
- About page focused on mission & values (no personal bios — intentional; we keep the human story for outreach conversations, not the public site)
- Cofounder dashboard at /dashboard
- Deploy pipeline fixed — database now initializes at runtime, builds are clean
- All Instagram posts created + scheduled (Mar 2-8)

### Next — Timeline

**NOW (Mar 2-7) — You Start Outreach:**
- [ ] Send your first WhatsApp messages (personal contacts, community groups)
- [ ] Reach out to Orthodox circles and chesed committee contacts
- [ ] Instagram posts are already scheduled (Mon-Sun)
- [ ] Set up Instagram Highlights on phone (About, Resources, Community)
- [ ] Test a referral link yourself — visit `neshama.ca/?ref=jordana-whatsapp` and check the dashboard to see it tracked

**Week 2 (Mar 8-14) — Vendor + Synagogue Push:**
- [ ] Vendor outreach emails sent — "You're listed on Neshama" (129 vendors)
- [ ] Call 5 kosher caterers — pitch Featured Vendor ($49/mo founding rate)
- [ ] Synagogue outreach emails (12+ synagogues)
- [ ] Press pitch: Canadian Jewish News

**Month 1 (March) — Data Builds, Revenue Starts:**
- [ ] First monthly vendor performance reports sent automatically
- [ ] Pitch featured listings to vendors who have real click data
- [ ] Formalize funeral home partnerships (Steeles, Benjamin's, Paperman's)

**Month 2-3 — Revenue Activation:**
- [ ] Convert 5-20 vendors to Featured ($49/mo founding rate)
- [ ] Memorial donation integration
- [ ] Expand to more funeral homes
- [ ] US expansion research (South Florida first — 620K Jews, snowbird overlap)

---

## Outreach Materials Ready for You

All copy-paste ready. Organized by channel.

### WhatsApp Groups — Casual Drop

Hey everyone, wanted to share something. My friend Erin built neshama.ca — it pulls together all the Jewish obituaries from the funeral home sites (Steeles, Benjamin's, Paperman's) so you're not checking three different places. There's also a tool to sign up to bring meals during shiva so you don't end up with 6 people on Monday and nobody on Thursday. Free, no sign-up. Worth bookmarking before you need it. neshama.ca

### WhatsApp — The Personal One (for groups where people know the story)

You guys know my mom used to read every obituary. After we lost her I started doing the same thing. Between that and catering shivas every week with Jem, I kept seeing the same problem — everyone wants to help but nobody knows what's covered.

Erin and I built neshama.ca. All the local obituaries in one place, a way to coordinate who's bringing what, and a directory of food and gift options if you want to send something. Free, no accounts, nothing to sign up for.

Take a look when you get a sec. neshama.ca

### Orthodox Community / Chesed Circles

Hey [Name] — I wanted to tell you about something Erin Kofman and I have been working on. It's called Neshama — neshama.ca.

You know what it's like. Three people bring chicken on Monday, nobody shows up Wednesday. Families are checking three funeral home websites trying to find a listing. People want to help and don't know where to start.

Neshama puts it all in one place. Obituaries from the local funeral homes, a meal coordination tool for shiva, and a directory of food and gift vendors. Free, no sign-up.

If you know anyone on a chesed committee or shul board, I'd love for them to see it. It's the kind of thing that works best when people know about it before they need it.

### Synagogue Contacts / Chesed Committees

Hi [Name],

I've been working with Erin Kofman on something I wanted to share with you — a free community resource called Neshama (neshama.ca).

Through catering shivas every week, I see how stressful the logistics are for families. Who's bringing food when. Which funeral home has the listing. Where to find a caterer. It's all scattered.

Neshama pulls obituaries from the local funeral home websites into one search, has a meal coordination tool so volunteers can sign up for specific days, and a directory of food and gift vendors. Free for families, no sign-up.

I think [Synagogue Name]'s congregation would find it really useful. Would you be open to sharing it in your newsletter or passing it to your chesed committee? Here's a blurb ready to go:

> **Neshama** — When a family in our community experiences a loss, neshama.ca brings together obituaries from local funeral homes, a meal coordination tool for shiva, and a directory of food and gift vendors. Free, no sign-up required. neshama.ca

Warmly,
Jordana Mednick

### Vendor Peers (Caterer-to-Caterer)

Hey [Name] — hope things are good. Wanted to tell you about something Erin and I built. It's called Neshama — neshama.ca. Basically a community hub for families dealing with a loss. Obituaries from the funeral homes, meal coordination for shiva, and a directory of caterers and vendors.

You're actually already listed on it. Erin put together a directory of everyone in Toronto and Montreal who serves shiva families. Your listing: [listing URL]

If anything needs updating — phone, website, whatever — just let me know. There's also a featured listing option if you want more visibility, but your current one stays free no matter what.

Check it out: neshama.ca/shiva/caterers

### Funeral Home Contacts

Hi [Name] — I wanted to make you aware of something my friend Erin Kofman and I have been working on. It's called Neshama — neshama.ca.

It pulls obituaries from Jewish funeral homes across Toronto and Montreal, including [Funeral Home Name], and puts them in one searchable feed alongside meal coordination tools and a vendor directory.

All the listings link back to your site. We'd genuinely appreciate your feedback — is this useful from your perspective? Anything about how your listings appear that you'd want changed?

Happy to chat anytime.

Jordana Mednick

### Dana Cohen Ezer / Hartsman Institute

Hey Dana — I've been meaning to tell you about this. You know what losing my mom did to me. One of the things that came out of it — you'll understand this — is that I started reading obituaries the way she used to. She did it to find former patients. I do it because it makes me feel connected to her.

And the whole time I kept thinking: why is this so hard for families? The information is all over the place, nobody coordinates meals, people want to help but don't know how.

So Erin Kofman and I built something. It's called Neshama (www.neshama.ca). It brings together obituaries from Toronto and Montreal funeral homes, has a meal coordination tool for shiva, and a "How Can I Help?" hub with local food partners and gifts. Free for families, no sign-up.

I know through your work with the Hartsman Institute you see the community side of grief and support every day. I think Neshama could be a natural fit to share with chesed committees, community organizations, anyone working with families during difficult times.

Would love for you to take a look. And if you see the right people to share it with, that would mean a lot.

---

## FAQ — When People Ask Questions

**"What is this exactly?"**
> A free website for Jewish families when someone passes away. Pulls together obituaries from funeral homes, has a meal coordination tool so friends don't overlap, and a "How Can I Help?" hub with 129+ local food partners and gift vendors. Everything the community needs during shiva, in one place.

**"Why not just call a caterer?"**
> You absolutely should — the site even has a directory to help you find one. But the coordination piece is different. When 12 people want to bring food, you end up with three kugels Monday and nothing Wednesday. The meal tool lets everyone sign up for specific days. It works alongside caterers, not instead of them.

**"Does it cost anything?"**
> No. Free for families. No accounts, no fees. We sustain the site through optional vendor listings — the family side will always be free.

**"How do you make money?"**
> Vendors can pay for featured listings to get more visibility. We also have Amazon affiliate links and a voluntary sustainer program ($18/year). But the family-facing side is free. Always.

**"Is this only for Jewish families?"**
> It was built for the Jewish community — shiva, yahrzeit, kosher considerations. But anyone is welcome to use it.

---

## Key Pages

| Page | Link |
|------|------|
| Homepage | www.neshama.ca |
| Obituary Feed | www.neshama.ca/feed |
| Meal Coordination | www.neshama.ca/shiva-organize |
| Caterer Directory | www.neshama.ca/shiva/caterers |
| How Can I Help? (Food) | www.neshama.ca/help/food |
| What to Bring | www.neshama.ca/what-to-bring-to-a-shiva |
| Prepare the Home | www.neshama.ca/help/supplies |
| How to Sit Shiva | www.neshama.ca/how-to-sit-shiva |
| What Is Yahrzeit | www.neshama.ca/what-is-yahrzeit |
| Kosher Shiva Food | www.neshama.ca/kosher-shiva-food |
| Yahrzeit Reminders | www.neshama.ca/yahrzeit |
| Send Something Thoughtful | www.neshama.ca/help/gifts |
| About | www.neshama.ca/about |
| **Cofounder Dashboard** | **www.neshama.ca/dashboard** |

---

## Referral Tracking URLs

Use these links when sharing Neshama so we can see which channels drive traffic. Results appear on the dashboard in real time.

| Channel | Tracking Link |
|---------|---------------|
| Jordana WhatsApp (personal) | `neshama.ca/?ref=jordana-whatsapp` |
| Jordana WhatsApp (community groups) | `neshama.ca/?ref=jordana-whatsapp-groups` |
| Dana's network | `neshama.ca/?ref=dana` |
| Synagogue emails | `neshama.ca/?ref=synagogue-email` |
| Facebook Jewish groups | `neshama.ca/?ref=facebook-jewish` |
| Instagram bio | `neshama.ca/?ref=instagram` |
| Funeral home partnerships | `neshama.ca/?ref=funeral-home` |
| Canadian Jewish News | `neshama.ca/?ref=cjn-press` |
| Friend/family word of mouth | `neshama.ca/?ref=word-of-mouth` |
| Vendor outreach | `neshama.ca/?ref=vendor-email` |

**How it works:** When someone clicks a tracking link, the `?ref=` tag is logged automatically. The dashboard shows total visits per channel, first/last visit dates, and a 7-day trend. One visit per session per link is counted (no duplicate inflation).

---

*This is your thing, Jordana. You had the idea. Let's make it matter.*
