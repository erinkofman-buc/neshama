# Kosher Migration Companion Code Changes

**Sibling to:** `2026-05-02-kosher-status-binary.sql`
**Sweep done:** May 1, 2026 by autonomous agent
**Status:** REQUIRED before migration ships — UI will break otherwise

## Scope summary
- **11 files** need changes
- **~250 total locations**
- **Estimated effort:** 60-90 min
- **Most volume:** seed_vendors.py (~145 of the 250)

## Files needing changes

### `seed_vendors.py` — SEED DATA
- Line 71: `kosher_status TEXT DEFAULT 'not_certified'` → DEFAULT `'not_kosher'` (or NULL)
- ~75 lines: `'kosher_status': 'not_certified'` → `'not_kosher'`
- ~42 lines: `'kosher_status': 'COR'` → `'Kosher'`
- ~22 lines: `'kosher_status': 'MK'` → `'Kosher'`
- Lines 2337, 2375: `v.get('kosher_status', 'not_certified')` defaults → `'not_kosher'`
- Empty string `''` entries (~15 lines: 727, 846, 991, 2061, 2076, 2091, 2106, 2181, 2196, 2211, 2226, 2241, 2256, 2271, 2286): confirm migration handles empty as NULL

### `frontend/api_server.py` — DATA + DISPLAY
- Lines 6700-6703: UPDATE using `'not_certified'` → `'not_kosher'`
- Lines 6721-6725: `WHERE ... kosher_status = 'COR'` → `'Kosher'`
- Lines 6798, 6816, 6819, 6822, 6825, 6828, 6831, 6834, 6843: hardcoded INSERT `"COR"` → `"Kosher"`
- Lines 6799, 6837, 6840, 6846: hardcoded INSERT `"not_certified"` → `"not_kosher"`
- Line 6864: `UPDATE ... SET 'not_certified' WHERE 'Kosher Style'` — both literals
- Line 6974: `... AND kosher_status = 'COR'` → `'Kosher'`
- Line 7054: `WHERE kosher_status = 'COR'` + SET `'not_certified'` — both
- Line 7056: SET `''` WHERE `'not_certified'` — WHERE → `'not_kosher'`
- Line 7114: same `Kosher Style` → `not_certified` migration as 6864
- Line 7279: SET `'not_certified'` WHERE `'Kosher'` — SET → `'not_kosher'`

### `frontend/directory.html` — DISPLAY/FILTER
- Line 995: `=== 'Kosher' || === 'COR' || === 'MK'` → `=== 'Kosher'`
- Line 1000: same pattern → `=== 'Kosher'`
- Line 1056: `!== 'COR' && !== 'MK'` → `!== 'Kosher'`

### `frontend/gifts.html` — DISPLAY/FILTER
- Lines 458, 468: mock data `'Kosher certified'` → `'Kosher'`
- Line 541: `!== 'not_certified'` → `!== 'not_kosher'`
- Line 591: compound `=== 'Kosher' || === 'COR' || === 'MK' || === 'Kosher certified'` → `=== 'Kosher'`

### `frontend/vendor-detail.html` — DISPLAY
- Lines 582, 585: COR/MK badge branches → collapse to `=== 'Kosher'`
- Lines 631, 633: same in second render block
- Lines 666-667: schema.org JSON-LD `if COR or MK` then `additionalProperty.value = v.kosher_status` — change to `=== 'Kosher'` and value `'Kosher'`. **Loses COR/MK schema granularity — talk to Erin if SEO impact matters.**

### `frontend/shiva-organize.html` — DISPLAY
- Line 1974: `if COR || MK` shows "Kosher (' + v.kosher_status + ')" → `if === 'Kosher'`, just show `'Kosher'`

### `frontend/shiva-view.html` — DISPLAY
- Lines 2868-2869: same pattern → collapse
- Lines 3271-3272: same pattern → collapse

### `sync_vendors_to_caterers.py` — MAPPING TABLE
- Lines 13-18: dict map old→new. Add `'Kosher': 'certified_kosher'`. Drop COR/MK rows or keep for backward read safety
- Line 43: default fallback `'not_certified'` → `'not_kosher'`

### `outscraper_pipeline/import_vendors.py` — SCRAPER MAPPING
- Lines 64-70: `map_kosher_status()` returns COR/MK/not_certified → return `'Kosher'`/`'not_kosher'`

### `outscraper_pipeline/enrich_vendors_firecrawl.py` — SCRAPER MAPPING
- Lines 163-170: same `map_kosher_status` pattern → `'Kosher'`/`'not_kosher'`
- Line 170: `current_status != 'not_certified'` → `!= 'not_kosher'`

### `outscraper_pipeline/audit_vendor_data.py` — TEST/QA
- Line 73: `LEGACY_KOSHER_STATUS = {"COR", "MK", "not_certified"}` → `{"Kosher", "not_kosher"}` (or rename + keep legacy as WARN tier)
- Line 178: error message text mentions "use COR/MK/not_certified" → update text
- Lines 19, 24, 69, 74: comment updates (optional)

## Files NOT needing changes (verified)
- `migrations/2026-05-02-kosher-status-binary.sql` — the migration itself
- `archive/**` — historical (excluded)
- `outscraper_pipeline/data/**` — data dumps (excluded)
- `smoke_test_deploy.py` lines 226-231 — `Kosher Style` regression check still valid (asserts post-migration there are zero rows)
- `frontend/shiva_manager.py` — uses `caterers.kosher_level` (separate field), already binary-aware
- `frontend/shiva-caterers.html` — uses `kosher_level` (caterers), not affected

## Risk areas to flag
1. **`vendor-detail.html:666-667`** — JSON-LD schema loses COR/MK granularity. Decide if SEO impact matters before collapsing.
2. **`api_server.py` startup migrations (lines 6864, 7114)** — these run on every boot. They're idempotent re-applications of an old fix. Safe to update RHS to `'not_kosher'`, but verify migration ran first.
3. **`sync_vendors_to_caterers.py`** writes to `caterers.kosher_level` (separate field, NOT migrating). Only the lookup keys change.
4. **`seed_vendors.py` empty strings** (`''`) — confirm migration treats `''` correctly. Suggest normalizing to NULL in migration or here.

## Ready-to-run mechanical replacements (seed_vendors.py only — safe)

```bash
cd ~/Desktop/Neshama
sed -i '' "s/'kosher_status': 'COR'/'kosher_status': 'Kosher'/g" seed_vendors.py
sed -i '' "s/'kosher_status': 'MK'/'kosher_status': 'Kosher'/g" seed_vendors.py
sed -i '' "s/'kosher_status': 'not_certified'/'kosher_status': 'not_kosher'/g" seed_vendors.py
sed -i '' "s/'not_certified'/'not_kosher'/g" seed_vendors.py
```

Verify diff:
```bash
git diff seed_vendors.py | head -60
```

## NOT safe for sed
- HTML compound conditional chains (`|| === 'COR' || === 'MK'`) — manual collapse
- `api_server.py` UPDATE strings — `'COR'` appears inside SQL literals next to vendor names

## Suggested branch
**Don't add to `chore/post-apr30-cleanup` or `fix/health-check-write-storm`** — those have tight scope.

Create `feat/kosher-binary-migration`:
```bash
cd ~/Desktop/Neshama
git checkout main
git checkout -b feat/kosher-binary-migration
mv migrations/2026-05-02-kosher-status-binary.sql migrations/   # already there
git add migrations/2026-05-02-kosher-status-binary.sql migrations/2026-05-02-kosher-status-binary-COMPANION-CHANGES.md
git commit -m "Migration: collapse kosher_status to binary"
# Then apply seed sed + manual HTML/api_server edits in subsequent commits
```
