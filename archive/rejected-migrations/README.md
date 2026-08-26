# Rejected migrations — do not run

Archived 2026-08-26. These files are kept as a record of a decision, not as work
to be picked up. Nothing in this directory should be executed against any
database, local or production.

## 2026-05-02 binary kosher_status

`2026-05-02-kosher-status-binary.sql` and its companion sweep
`2026-05-02-kosher-status-binary-COMPANION-CHANGES.md` would have collapsed
`vendors.kosher_status` from named certifications (`COR`, `MK`) to a binary
`Kosher` / `not_kosher`.

**Status: REJECTED, 2026-06-02.** From `decisions-log.md`:

> The binary-Kosher migration (the "Saturday migration" referenced in several
> code comments) is REJECTED: we do not claim a certification we cannot name.

The rejection is enforced in live code by `is_kosher_certified()` in
`frontend/api_server.py`, which grants a kosher badge only for a named hechsher
(`COR` or `MK`), case-insensitively. A bare `Kosher`, `not_certified`, or blank
earns no badge.

The migration never ran. Production still shows the pre-migration distribution
(verified 2026-08-25 via `/api/vendors`): COR 39, MK 22, not_certified 70,
bare `Kosher` 1, empty 13 — which matches the Apr 29 audit recorded in the SQL
file's own header.

It was drafted 2026-04-29 for a Saturday 2026-05-02 deploy window, that window
passed, and the approach was overturned on 2026-06-02 before it ever shipped.

## If you are here because a code comment pointed you here

Several comments in `seed_vendors.py`, `directory.html` and `shiva-caterers.html`
still refer to "the Saturday SQL migration" as if it were pending. Those comments
are stale. Removing them is tracked as follow-up in `decisions-log.md`
(2026-06-02, "remove the Saturday-migration comments").
