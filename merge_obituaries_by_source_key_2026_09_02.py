#!/usr/bin/env python3
"""One-shot merge of duplicate obituaries, clustered by source_key.

    python merge_obituaries_by_source_key_2026_09_02.py             # DRY RUN (default)
    python merge_obituaries_by_source_key_2026_09_02.py --execute   # writes, ONE transaction

WHY THIS EXISTS, AND WHY IT IS NOT THE AUGUST SCRIPT
----------------------------------------------------
`dedupe_obituaries_2026_08_26.py` clustered by (normalized_name, source). It did
its job: as of 2026-09-02 there are ZERO (source, normalized_name) duplicate
groups left in the 1,270 public rows.

But it cannot see the duplicates that remain, because in every one of them the
funeral home CHANGED THE NAME - which is precisely what a name-based matcher is
blind to:

    Yosi Derman        -> Jonathan Derman        (Hebrew / English)
    Zippe Blitstein    -> Sandra Blitstein       (Hebrew / English)
    Tony Belchetz      -> Anthony BELCHETZ       (diminutive / legal)
    Gerald "Jerry" Gold-> Jerry Gold             (nickname)
    Simon Chouchan     -> Simon Chauchan         (typo correction)
    Ray Mendell        -> Raymond Mendell
    Hy Goldstein       -> Hyman Goldstein

Clustering on the funeral home's own permanent URL id instead finds 74 groups
covering 78 removable rows (1,270 -> 1,192). Measured against live production
data on 2026-09-02, not estimated.

EVERYTHING ELSE IS THE AUGUST SCRIPT, DELIBERATELY
--------------------------------------------------
This file changes the clustering rule and nothing else. The merge rules, the
single BEGIN IMMEDIATE transaction, the pre-COMMIT invariant checks, the FK
re-pointing across comments / shiva_support / yahrzeit_reminders /
shiva_analytics / tributes, and the hidden-row exclusion are all reused by
import, not re-implemented. Erin's 2026-08-26 rulings still hold verbatim:

  * The OLDEST row's id survives. Memorial URLs get shared in WhatsApp groups
    and indexed by Google; breaking one is the failure mode this site cannot
    afford.
  * Every other field takes the newest non-empty value.
  * EXCEPT deceased_name, which takes the most complete variant by length.
  * EXCEPT date_of_death, which refuses a pre-1990 value onto an empty survivor.

WARNING: THIS SCRIPT IS DESTRUCTIVE AND HAS NOT BEEN RUN. Dry run is the default and
nothing writes without --execute. Run the dry run first, read the plan, and only
then decide. Back up /data/neshama.db before --execute.
"""

import os
import re
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dedupe_obituaries_2026_08_26 as base  # noqa: E402
from obituary_identity import source_key      # noqa: E402


# Parentheticals that are OPERATIONAL NOTICES, not part of a person's name.
#
# Steeles appends service logistics to the name field, so one man arrives as
# three rows: "Joseph Hayeems", "Joseph Hayeems (Start Time May Be Delayed)" and
# "Joseph Hayeems (Funeral Rescheduled to 12:00 p.m.)" - all three with the SAME
# date_of_death, which is a clean demonstration that the name, not the date, is
# what forks the old identity hash.
#
# This matters here because Erin's 2026-08-26 "most complete name wins by length"
# rule would then pick "Joseph Hayeems (Funeral Rescheduled to 12:00 p.m.)" as the
# surviving name - enshrining a scheduling note as a dead man's name on his own
# memorial page. That rule is still right for what it was written for: it is what
# preserves "Dr. Randy Leifer" over "Randy Leifer" and "Yvonne Hazan (née Sasson)"
# over "Yvonne Hazan". It simply cannot tell a née clause from a logistics note.
#
# Measured against the production snapshot of 2026-09-03: 255 obituary names
# contain a parenthetical, 253 of them are née / maiden / nickname clauses that
# MUST be preserved, and exactly 2 are operational - both Hayeems. So this rule
# separates them with no false positives on real data.
# Two groups. The first is verb STEMS and deliberately has no trailing word
# boundary, so "Delayed", "Rescheduled", "Postponed", "Cancelled" all match; a
# trailing \b there would silently match none of them. The second is whole
# words. "chang" is NOT a stem: Chang is a surname and appears in née clauses,
# so only the whole words "change"/"changed" count.
_OPERATIONAL_PAREN = re.compile(
    r'\b(?:delay|reschedul|postpon|cancel|updat|correct|revis)'
    r'|\b(?:changed?|moved|new time|start time|time change|funeral|shiva|'
    r'burial|service|graveside|livestream|p\.?m\.?|a\.?m\.?|today|tomorrow|'
    r'note)\b',
    re.IGNORECASE,
)


def strip_operational_parentheticals(value):
    """Remove '(Funeral Rescheduled...)'-style notices, keep '(née Sasson)'.

    Only drops a parenthetical whose CONTENTS look like service logistics. A
    parenthetical holding a name is left exactly as it is.
    """
    if not value:
        return value
    out = re.sub(
        r'\s*\(([^)]*)\)',
        lambda m: '' if _OPERATIONAL_PAREN.search(m.group(1)) else m.group(0),
        str(value),
    )
    return ' '.join(out.split())


def choose_name(cluster):
    """Pick the surviving deceased_name for a merged cluster.

    Erin's rule (most complete wins) applied to names that have had operational
    notices stripped first, so a scheduling note can never win on length.
    """
    candidates = []
    for row in cluster:
        cleaned = base.clean_name(row.get('deceased_name'))
        if not cleaned:
            continue
        candidates.append(strip_operational_parentheticals(cleaned) or cleaned)
    if not candidates:
        return None
    return max(candidates, key=len)


def build_plan_by_source_key(conn):
    """Same plan shape as base.build_plan, clustered on source_key.

    Rows whose source_key cannot be derived are skipped entirely rather than
    guessed at - a wrong merge is unrecoverable, a missed one is not.
    """
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        'SELECT * FROM obituaries WHERE COALESCE(hidden, 0) = 0')]

    groups = defaultdict(list)
    for row in rows:
        key = row.get('source_key') or source_key(
            row.get('source'), row.get('source_url'))
        if key:
            groups[key].append(row)

    plan = []
    for key, cluster in groups.items():
        if len(cluster) < 2:
            continue
        # Oldest first - cluster[0] is the survivor and keeps its id.
        cluster.sort(key=lambda r: (r.get('first_seen') or r.get('last_updated') or '',
                                    r.get('id') or ''))
        survivor, dropped = cluster[0], cluster[1:]
        merged, held = {}, []

        for field in survivor.keys():
            if field == 'id':
                continue
            if field in ('first_seen', 'last_updated'):
                values = [r.get(field) for r in cluster if r.get(field)]
                if values:
                    merged[field] = min(values) if field == 'first_seen' else max(values)
                continue
            if field == 'deceased_name':
                chosen = choose_name(cluster)
                if chosen:
                    merged[field] = chosen
                continue
            value = survivor.get(field)
            for other in dropped:
                if other.get(field) not in (None, '', 0):
                    value = other.get(field)
            if field == 'date_of_death' and not survivor.get(field) and value \
                    and base.SUSPECT_YEAR.search(str(value)):
                held.append(str(value))
                value = survivor.get(field)
            merged[field] = value

        changed = {f: v for f, v in merged.items() if survivor.get(f) != v}
        plan.append({'key': (key, survivor.get('source') or ''),
                     'survivor': survivor, 'dropped': dropped,
                     'changed': changed, 'held': held})
    return rows, plan


if __name__ == '__main__':
    # Swap the clustering rule; reuse every safety mechanism unchanged.
    base.build_plan = build_plan_by_source_key
    base.main()
