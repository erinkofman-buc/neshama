-- Migration: Collapse kosher_status to binary (Kosher / not_kosher)
-- Date: scheduled for Sat May 2, 2026 (deep code day per feedback_saturday_deep_code_day.md)
-- Author: drafted Apr 29, 2026
-- Reference: feedback_no_kosher_style.md (UPDATED Apr 29 — binary, not multi-cert)
--
-- Production state Apr 29 2026 (147 vendors):
--   COR            40 vendors → 'Kosher'
--   MK             23 vendors → 'Kosher'
--   Kosher          1 vendor (Candy Catchers) → stays 'Kosher'
--   not_certified  69 vendors → 'not_kosher'
--   (empty)        14 vendors → leave NULL/empty for Jordana to verify
--
-- This migration is REVERSIBLE via the rollback section below.
-- Run during Saturday deep-code window (10 PM-6 AM ET).
-- Pre-flight: ensure /admin/backup endpoint just wrote a fresh backup.

-- =============================================================================
-- BACKUP CHECK (manual — verify before running)
-- =============================================================================
-- 1. Hit /admin/backup to write fresh backup of vendors table to disk
-- 2. Confirm backup file exists and is non-empty
-- 3. Note the timestamp of pre-migration state for rollback reference

-- =============================================================================
-- MIGRATION (forward)
-- =============================================================================

BEGIN TRANSACTION;

-- Step 1: Snapshot pre-migration state for verification
CREATE TABLE IF NOT EXISTS _kosher_migration_2026_05_02_snapshot AS
SELECT id, slug, name, kosher_status, datetime('now') as snapshotted_at
FROM vendors;

-- Step 2: Verify expected counts BEFORE migration (should match Apr 29 audit)
-- Run these as SELECT queries first; abort if counts don't roughly match:
--   SELECT kosher_status, COUNT(*) FROM vendors GROUP BY kosher_status;
-- Expected approximate counts (will drift slightly Apr 29 → May 2):
--   COR ~40, MK ~23, Kosher ~1, not_certified ~69, NULL/empty ~14

-- Step 3: Update COR + MK + Kosher → 'Kosher'
UPDATE vendors
SET kosher_status = 'Kosher'
WHERE kosher_status IN ('COR', 'MK', 'Kosher');

-- Step 4: Update not_certified → 'not_kosher'
UPDATE vendors
SET kosher_status = 'not_kosher'
WHERE kosher_status = 'not_certified';

-- Step 5: Verify post-migration state. Expected:
--   Kosher       ~64 (40 + 23 + 1)
--   not_kosher   ~69
--   NULL/empty   ~14
-- Run: SELECT kosher_status, COUNT(*) FROM vendors GROUP BY kosher_status;

-- Step 6: Sanity-check no unexpected values appeared
-- Run: SELECT DISTINCT kosher_status FROM vendors;
-- Expected: 'Kosher', 'not_kosher', NULL, '' (no other values)

COMMIT;

-- =============================================================================
-- ROLLBACK (if needed within 7 days while snapshot table still exists)
-- =============================================================================
-- BEGIN TRANSACTION;
--
-- UPDATE vendors
-- SET kosher_status = (
--     SELECT kosher_status
--     FROM _kosher_migration_2026_05_02_snapshot s
--     WHERE s.id = vendors.id
-- )
-- WHERE EXISTS (
--     SELECT 1 FROM _kosher_migration_2026_05_02_snapshot s WHERE s.id = vendors.id
-- );
--
-- COMMIT;

-- =============================================================================
-- POST-MIGRATION CLEANUP (only after 7 days of confirmed stability)
-- =============================================================================
-- DROP TABLE _kosher_migration_2026_05_02_snapshot;

-- =============================================================================
-- COMPANION CODE CHANGES (must ship in same deploy)
-- =============================================================================
-- 1. seed_vendors.py: update all entries to use 'Kosher' or 'not_kosher' (binary)
-- 2. api_server.py: any explicit COR/MK references in vendor display/filtering need binary update
-- 3. Frontend HTML: search for "COR", "MK", "Kosher Style" in *.html — update display logic
-- 4. /qa post regression checklist references (memory feedback_coding_lessons.md):
--    - "Aroma Espresso Bar kosher_status = 'not_certified'" → update to 'not_kosher'
--    - "Aba's Bagel Company kosher_status = 'Kosher Style'" → that label was already forbidden;
--      verify production value is 'not_kosher' post-migration
-- 5. NESHAMA-SKILL.md or brand voice docs that reference kosher labels

-- =============================================================================
-- WHAT'S LEFT: 14 empty kosher_status vendors
-- =============================================================================
-- After migration, ~14 vendors will still have NULL/empty kosher_status.
-- These need Jordana verification (caterer-by-caterer review).
-- Until then, the directory should display these as "Status not verified" (not Kosher).
-- See vendor-data-audit-2026-04-29.csv for the list.
