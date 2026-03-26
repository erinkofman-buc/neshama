# Brand Voice Audit — 2026-03-25

Audited all 39 public-facing HTML files in `/frontend/` against Neshama brand voice guidelines.

**Brand rules applied:**
- Warm, empathetic, community-focused — never clinical, corporate, or transactional
- No aggressive CTAs
- Grief-aware: every element passes "would this feel okay the week your parent died?"
- Language: "community" not "marketplace", "support" not "service"
- No emoji in user-facing text
- Canadian spelling (colour, honour, centre, organise)

---

## Violations Found

| Page | Line | Current Text | Issue | Suggested Fix |
|------|------|-------------|-------|---------------|
| about.html | 8 | `content="Learn about Neshama, an independent service aggregating..."` | Meta description uses "service" — brand prefers "community resource" | `content="Learn about Neshama, an independent community resource aggregating..."` |
| about.html | 432 | `"contactType": "customer service"` | Schema.org uses "customer service" — corporate language | `"contactType": "customer support"` (schema.org requires this exact value, so acceptable as-is) |
| about.html | 543 | `We offer memorial pages with tributes` | "Offer" has a transactional undertone | `We provide memorial pages with tributes` or `Memorial pages with tributes give the community a space to...` |
| about.html | 572 | `Our service is free because supporting the community shouldn't have a price.` | "Service" — prefer "community resource" or omit | `Neshama is free because supporting the community shouldn't have a price.` |
| about.html | 606 | `Neshama is an independent community service built to strengthen...` | "Service" again | `Neshama is an independent community resource built to strengthen...` |
| faq.html | 482 | `Neshama is a free service that aggregates obituary listings...` | "Service" | `Neshama is a free community resource that aggregates obituary listings...` |
| faq.html | 510 | `Neshama is an independent community service.` | "Service" | `Neshama is an independent community resource.` |
| faq.html | 559 | `We're building some optional premium features` | "Premium features" sounds like SaaS/startup jargon | `We're building some optional extras` or `We're adding a few optional tools` |
| demo.html | 8 | `content="...See the real product in action."` | "Product" — startup jargon, brand says never use | `content="...See how Neshama brings communities together."` |
| partner.html | 7 | `content="Partner with Neshama to serve the Jewish community."` | "Serve" can feel transactional in meta context | Acceptable — "serve" in context of community service is warm enough. No change needed. |
| partner.html | 744 | `Verified vendors` | "Verified" implies a formal certification process that may not exist; feels corporate | `Trusted partners` or `Community-trusted vendors` |
| partner.html | 752 | `15+ Subscribers` | "Subscribers" is a metrics/startup term; also inflated from actual count of 3 | `15+ Community members` — and verify the actual number |
| partner.html | 975 | `...a free platform that aggregates Jewish obituaries...` (WhatsApp share text) | "Platform" — startup jargon | `...a free community resource for Jewish obituaries...` |
| partner.html | 979 | `...a free platform that aggregates Jewish obituaries...` (email share text) | Same "platform" issue | Same fix as above |
| partner.html | 983 | `...a free platform that aggregates Jewish obituaries...` (SMS share text) | Same "platform" issue | Same fix as above |
| premium.html | 514 | `But keeping this service running takes real resources.` | "Service" | `But keeping Neshama running takes real resources.` |
| premium.html | 559 | `A platform built to comfort families and bring community together` | "Platform" — startup jargon | `A space built to comfort families and bring community together` |
| premium.html | 560 | `A service that remains free for every family, always` | "Service" | `Free for every family, always` |
| premium_modal.html | 259 | `A service that stays free for everyone` | "Service" | `Free for every family, always` |
| terms.html | 8 | `content="...our Jewish obituary aggregation and shiva coordination platform."` | "Platform" — startup jargon in meta description (shows in Google) | `content="...our Jewish obituary and shiva coordination community resource."` |
| shiva-caterer-apply.html | 8 | `content="...Help families sitting shiva in Toronto and Montreal with quality kosher meal options."` | Implies all vendors are kosher — brand rule says never default to kosher-only | `content="...Help families sitting shiva in Toronto and Montreal with quality meal options."` |
| shiva-caterer-apply.html | 600 | `...quality and safety of your products and services.` | "Products and services" — corporate/legal boilerplate | Acceptable in legal terms context. No change needed. |
| shiva-caterer-apply.html | 602 | `Neshama acts only as a listing platform` | "Listing platform" — corporate/startup | `Neshama acts only as a directory listing` |
| unsubscribe.html | 283 | `You've been removed from our list` | "Removed from our list" feels cold and clinical | `You've been unsubscribed` or `We've stopped your email updates` |
| unsubscribe.html | 373 | `alert('Please select at least one reason so we can do better.')` | Alert box feels corporate and demanding | `alert('If you have a moment, selecting a reason helps us improve.')` |
| vendor-analytics.html | 7 | `content="View your vendor performance metrics..."` | "Performance metrics" — corporate language | `content="See how your listing is doing on Neshama..."` |
| vendor-analytics.html | 463 | `Want More Visibility?` | Marketing/sales language | `Reach More Families` or `Help More Families Find You` |
| directory.html | 700 | `Join Our Directory` (footer link) | "Directory" is fine but "Join" + "Our" feels slightly corporate | `List Your Business` or keep as-is — borderline acceptable |
| landing.html | 458 | `&#x2709;&#xFE0F;` (envelope emoji in subscribe success) | Emoji in user-facing text — brand rule says no emoji | Replace with a simple SVG icon or remove |
| landing.html | 648 | `&#x1F56F;&#xFE0F;` (candle emoji as placeholder) | Emoji as fallback image — acceptable as decorative/aria-hidden | Borderline acceptable since it's a placeholder for missing photos, not text content |
| memorial.html | 1229 | `&#x1F54A;&#xFE0F; Condolences` (dove emoji on tab) | Emoji in user-facing button text | Remove emoji: `Condolences` |
| memorial.html | 1243 | `&#x1F54A;&#xFE0F; Send Condolences` (dove emoji on button) | Emoji in user-facing button text | Remove emoji: `Send Condolences` |
| memorial.html | 1305 | `&#x2709;&#xFE0F;` (envelope emoji on share button) | Emoji in share button | Replace with SVG envelope icon |
| memorial.html | 1694 | `alert('We weren\'t able to create the keepsake PDF right now...')` | Alert box — functional, but tone is good | No change needed — the language is warm |
| gifts.html | 577 | `&#128222;` (phone emoji next to phone number) | Emoji in user-facing text | Replace with SVG phone icon |
| help.html | 325 | `&#x1F56F;&#xFE0F;` (candle emoji as card icon) | Emoji as decorative icon | Replace with SVG candle icon (brand consistency) |
| email_popup.html | 350 | `<div class="success-icon">✉️</div>` | Emoji in user-facing success state | Replace with SVG envelope icon |
| index.html | 2309 | `&#x2709;&#xFE0F;` (envelope emoji in success popup) | Emoji in user-facing text | Replace with SVG envelope icon |
| shiva-organize.html | 1055 | `&#x2705;` (green checkmark emoji in success state) | Emoji in user-facing text | Replace with SVG checkmark icon |

---

## Spelling Check (Canadian vs. American)

All user-facing text uses Canadian spelling correctly:
- "honour" used throughout (not "honor")
- "colour" not found in user-facing text (colours are CSS values only)
- "neighbourhood" used correctly in shiva-organize.html line 941
- "organise" used in jewish-funeral-etiquette.html line 249 (correct)
- **Exception:** "Organize" used consistently in nav buttons across all pages (`Organize Shiva Meals`). This is the one American spelling used site-wide. Canadian would be "Organise Shiva Meals". However, since this is a proper feature name used as a navigation element, consistency matters more than correctness here — changing it would require updating 30+ files. **Recommendation:** Keep "Organize" as the established feature name, or do a single coordinated change across all files.

---

## Tone Patterns — What's Working Well

The vast majority of the site is excellent. Specific praise:

- **premium.html** — The sustain page is beautifully written. "Your support is not a transaction. It is an act of communal care." Perfect.
- **landing.html** — "Comforting our community" tagline is exactly right.
- **shiva-view.html** — "Sign up to bring a meal or offer support for a family sitting shiva. Community care, coordinated with warmth through Neshama." Excellent.
- **shiva-organize.html** — The explainer ("This page is for the friend, neighbour, or family member...") is warm and clear.
- **about.html** — Values section using Hebrew terms (Kavod, Chesed, Emet, Tzniut) with explanations is beautiful.
- **Footer copy** — "Built with care for the Jewish community" is consistent across all 39 pages. Well done.
- **Error messages** — "We couldn't load the listings right now" and "We weren't able to connect..." are warm and human throughout.
- **FAQ answers** — Written in accessible, conversational language. No jargon.
- **All content pages** (how-to-sit-shiva, what-to-bring, kosher-shiva-food, condolence-messages, etc.) — Beautifully grief-aware, educational without being clinical.

---

## Priority Fixes

### High Priority (visible in Google/social shares)
1. **demo.html** meta description — remove "product"
2. **terms.html** meta description — remove "platform"
3. **shiva-caterer-apply.html** meta description — remove assumption that all vendors are kosher

### Medium Priority (user-facing text)
4. **unsubscribe.html** — soften "removed from our list" heading
5. **partner.html** — change "Verified vendors" to "Trusted partners", fix subscriber count
6. **faq.html** — replace "service" with "community resource" (2 instances)
7. **about.html** — replace "service" with "community resource" (2 instances)
8. **premium.html** / **premium_modal.html** — replace "service" and "platform" (4 instances)
9. **vendor-analytics.html** — soften "Want More Visibility?" heading

### Low Priority (emoji cleanup)
10. Replace emoji characters with SVG icons on memorial.html, gifts.html, help.html, email_popup.html, index.html, shiva-organize.html, landing.html

---

## Summary

- **39 pages audited**
- **~30 violations found** (most are minor — repeated use of "service" and "platform")
- **0 aggressive CTAs** found anywhere
- **0 instances** of "marketplace", "users", "content" (for obituaries), or "death feed"
- **Canadian spelling** is consistent except "Organize" (established feature name)
- **Grief-awareness** is excellent throughout — no commercial elements on memorial pages
- **Footer consistency** is perfect across all pages
- The site's brand voice is strong. The fixes above are refinements, not corrections.
