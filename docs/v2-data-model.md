# V2 Shiva Coordination — Data Model Design
> Approved design doc. PRD source: ~/Downloads/neshama-shiva-prd.docx
> Created: 2026-02-26 | Status: APPROVED — ready to implement

## Summary
- 2 modified tables (11 new columns total)
- 2 new tables (`shiva_co_organizers`, `email_log`)
- 0 deleted tables, 0 breaking changes
- All migrations are additive (ALTER TABLE ADD COLUMN pattern)

---

## 1. `shiva_support` — 7 New Columns

```sql
-- Drop-off instructions (P0) — "Leave food on the porch", "Buzzer #204"
-- Shown to confirmed volunteers only (same privacy level as address)
ALTER TABLE shiva_support ADD COLUMN drop_off_instructions TEXT;

-- Notification preferences (P0) — JSON toggles for organizer emails
-- {"instant": true, "daily_summary": true, "uncovered_alert": true}
ALTER TABLE shiva_support ADD COLUMN notification_prefs TEXT DEFAULT '{"instant":true,"daily_summary":true,"uncovered_alert":true}';

-- Email verification status (P0)
-- pending → verified (email link) or admin_approved (manual)
-- Default 'verified' so existing v1 pages don't break
ALTER TABLE shiva_support ADD COLUMN verification_status TEXT DEFAULT 'verified';

-- Email verification token (P0) — one-time, cleared after use
ALTER TABLE shiva_support ADD COLUMN verification_token TEXT;

-- When organizer verified their email (P0)
ALTER TABLE shiva_support ADD COLUMN verified_at TEXT;

-- How the page was created (P1/P2)
-- web_claim | web_standalone | funeral_home | auto_created
ALTER TABLE shiva_support ADD COLUMN source TEXT DEFAULT 'web_standalone';

-- Demo page flag for landing page (P1)
ALTER TABLE shiva_support ADD COLUMN is_demo INTEGER DEFAULT 0;
```

### Fields NOT added (and why)
- `welcome_note` — already exists as `family_notes`
- `family_photo_url` — inherited from `obituary.photo_url`
- `share_message` — generated client-side from family_name + page URL

---

## 2. `meal_signups` — 4 New Columns (+2 reminder flags)

```sql
-- Group multi-date signups from same form submission (P0)
-- UUID linking rows when volunteer signs up for Mon+Tue+Wed at once
ALTER TABLE meal_signups ADD COLUMN signup_group_id TEXT;

-- Signup status for cancel/swap (P2)
-- confirmed | cancelled
ALTER TABLE meal_signups ADD COLUMN status TEXT DEFAULT 'confirmed';

-- When cancelled (P2)
ALTER TABLE meal_signups ADD COLUMN cancelled_at TEXT;

-- Reminder tracking flags — prevents duplicate sends on cron re-run (P0)
ALTER TABLE meal_signups ADD COLUMN reminder_day_before INTEGER DEFAULT 0;
ALTER TABLE meal_signups ADD COLUMN reminder_morning_of INTEGER DEFAULT 0;
```

---

## 3. NEW TABLE: `shiva_co_organizers`

```sql
CREATE TABLE IF NOT EXISTS shiva_co_organizers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shiva_support_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    magic_token TEXT NOT NULL,         -- Their own organizer access token
    invited_by_email TEXT NOT NULL,    -- Audit trail: who invited them
    status TEXT DEFAULT 'pending',     -- pending → accepted → revoked
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id)
);

CREATE INDEX IF NOT EXISTS idx_coorg_shiva ON shiva_co_organizers(shiva_support_id);
CREATE INDEX IF NOT EXISTS idx_coorg_email ON shiva_co_organizers(email);
CREATE INDEX IF NOT EXISTS idx_coorg_token ON shiva_co_organizers(magic_token);
```

### Auth change
`get_support_for_organizer()` currently checks only `shiva_support.magic_token`.
V2 also checks `shiva_co_organizers.magic_token WHERE status='accepted'`.

---

## 4. NEW TABLE: `email_log`

```sql
CREATE TABLE IF NOT EXISTS email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shiva_support_id TEXT NOT NULL,
    email_type TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    related_signup_id INTEGER,        -- FK to meal_signups (for signup emails)
    scheduled_for TEXT,               -- When cron should send (ISO datetime)
    sent_at TEXT,                     -- When actually sent
    status TEXT DEFAULT 'pending',    -- pending | sent | failed | skipped
    error_message TEXT,
    sendgrid_message_id TEXT,         -- Delivery tracking
    created_at TEXT NOT NULL,
    FOREIGN KEY (shiva_support_id) REFERENCES shiva_support(id),
    FOREIGN KEY (related_signup_id) REFERENCES meal_signups(id)
);

CREATE INDEX IF NOT EXISTS idx_email_shiva ON email_log(shiva_support_id);
CREATE INDEX IF NOT EXISTS idx_email_status ON email_log(status);
CREATE INDEX IF NOT EXISTS idx_email_scheduled ON email_log(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_email_type ON email_log(email_type);
```

### Email types

| email_type              | Trigger                          | Recipient  | Priority |
|------------------------|----------------------------------|------------|----------|
| signup_confirmation     | Immediate on signup              | Volunteer  | P0       |
| day_before_reminder     | Cron: 7pm night before           | Volunteer  | P0       |
| morning_of_reminder     | Cron: 8am day of                 | Volunteer  | P0       |
| instant_notification    | Immediate on signup              | Organizer  | P0       |
| thank_you               | Cron: day after shiva_end        | All participants | P0  |
| uncovered_alert         | Cron: 7pm for tomorrow gaps      | Organizer  | P1       |
| daily_summary           | Cron: 8pm daily during shiva     | Organizer  | P1       |
| co_organizer_invite     | Immediate on invite              | Invitee    | P1       |

---

## 5. Cron Job: `process_email_queue()`

Runs every 15 minutes. Logic:

1. **Day-before reminders:** `meal_signups WHERE meal_date = tomorrow AND status='confirmed' AND reminder_day_before=0`
2. **Morning-of reminders:** `meal_signups WHERE meal_date = today AND status='confirmed' AND reminder_morning_of=0`
3. **Uncovered alerts:** Active shiva pages with tomorrow having 0 confirmed signups (check email_log for dedup)
4. **Daily summary:** Active shiva pages within date range, no summary sent today
5. **Thank-you:** `shiva_end_date = yesterday AND status='active'` → email all volunteers → archive
6. **Retry failed:** `email_log WHERE status='failed' AND created_at > 24h ago` (max 3 retries)

---

## 6. Entity Relationships

```
obituaries (1) ──────── (0..1) shiva_support
                                    │
                    ┌───────────────┼───────────────────┐
                    │               │                   │
              meal_signups    shiva_co_organizers    email_log
             (many per shiva)  (0..N per shiva)    (many per shiva)
                    │
              email_log.related_signup_id
              (1..N emails per signup)
```

---

## 7. Migration Strategy

All migrations in `setup_database()` using existing try/except pattern:

```python
# V2 Migrations — shiva_support
for col, defn in [
    ('drop_off_instructions', 'TEXT'),
    ('notification_prefs', "TEXT DEFAULT '{\"instant\":true,\"daily_summary\":true,\"uncovered_alert\":true}'"),
    ('verification_status', "TEXT DEFAULT 'verified'"),
    ('verification_token', 'TEXT'),
    ('verified_at', 'TEXT'),
    ('source', "TEXT DEFAULT 'web_standalone'"),
    ('is_demo', 'INTEGER DEFAULT 0'),
]:
    try:
        cursor.execute(f'SELECT {col} FROM shiva_support LIMIT 1')
    except Exception:
        cursor.execute(f'ALTER TABLE shiva_support ADD COLUMN {col} {defn}')

# V2 Migrations — meal_signups
for col, defn in [
    ('signup_group_id', 'TEXT'),
    ('status', "TEXT DEFAULT 'confirmed'"),
    ('cancelled_at', 'TEXT'),
    ('reminder_day_before', 'INTEGER DEFAULT 0'),
    ('reminder_morning_of', 'INTEGER DEFAULT 0'),
]:
    try:
        cursor.execute(f'SELECT {col} FROM meal_signups LIMIT 1')
    except Exception:
        cursor.execute(f'ALTER TABLE meal_signups ADD COLUMN {col} {defn}')
```

New tables use `CREATE TABLE IF NOT EXISTS` (idempotent).

---

## 8. PRD Feature Coverage

| PRD Feature                     | Priority | Data Model Support |
|--------------------------------|----------|-------------------|
| Auto-populate from obituary     | P0       | Existing (obituary_id FK) |
| Drop-off instructions           | P0       | `drop_off_instructions` column |
| Multi-date signup               | P0       | `signup_group_id` links rows |
| Visual calendar (colors)        | P0       | Computed from meal_signups |
| Signup confirmation email       | P0       | `email_log` + immediate trigger |
| Day-before + morning reminders  | P0       | `email_log` + reminder flags + cron |
| Organizer dashboard             | P0       | Existing (magic_token auth) |
| Instant notification toggle     | P0       | `notification_prefs` JSON |
| Thank-you email                 | P0       | `email_log` + cron on shiva_end |
| Email verification              | P0       | `verification_status/token/verified_at` |
| WhatsApp/SMS share text         | P0       | Generated client-side |
| Uncovered date alerts           | P1       | `email_log` + `notification_prefs` + cron |
| Daily organizer summary         | P1       | `email_log` + `notification_prefs` + cron |
| Co-admin invite                 | P1       | `shiva_co_organizers` table |
| Standalone shiva                | P1       | Existing (obituary_id NULL) |
| Demo shiva page                 | P1       | `is_demo` flag |
| Funeral home creation           | P1       | `source` column |
| Cancel/swap from reminder       | P2       | `status` + `cancelled_at` on meal_signups |
| Funeral home auto-creation      | P2       | `source = 'auto_created'` |

---

## Implementation Order (suggested)

1. **Migrations** — Add all columns + new tables to `setup_database()`
2. **Co-organizer system** — Table, invite flow, auth check update
3. **Email log** — Replace fire-and-forget threads with logged sends
4. **Cron job** — `process_email_queue()` with all 6 email types
5. **Multi-date signup** — `signup_group_id` in signup flow + grouped confirmation email
6. **Verification flow** — Token generation, verification endpoint, status checks
7. **Frontend updates** — Drop-off instructions field, notification toggles, co-admin UI
