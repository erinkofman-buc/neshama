#!/usr/bin/env python3
"""
Apply Erin's Apr 21 vendor photo picks to seed_vendors.py.

Flow:
  1. Load review.html DATA (candidates per vendor from the Apr 20 pipeline run)
  2. Apply Erin's picks (option number → candidates[N-1]) as new image_url
  3. NULL out stock/AI/unpicked vendors (triggers cream placeholder)
  4. Remove Moishes dict entry (already in VENDORS_TO_REMOVE but dict was still being inserted-then-deleted)

Usage:
  python3 archive/apply_vendor_bundle_apr21.py          # dry run (prints what would change)
  python3 archive/apply_vendor_bundle_apr21.py --apply  # writes changes to seed_vendors.py
  python3 archive/apply_vendor_bundle_apr21.py --sql    # also write scripts/apply-directory-bundle-apr21.sql
"""
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED_PATH = REPO / "seed_vendors.py"
REVIEW_PATH = REPO / "outscraper_pipeline" / "review.html"
SQL_PATH = REPO / "archive" / "apply-directory-bundle-apr21.sql"


def slugify(name: str) -> str:
    """Mirror slugify() from seed_vendors.py so SQL updates hit the right rows."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def sql_escape(s: str) -> str:
    """Escape single quotes for SQL string literals."""
    return s.replace("'", "''")


def write_sql(picks_resolved: list, nulls: list, deletes: list) -> str:
    """Build the SQL migration script contents.

    picks_resolved: list of (vendor_name, slug, new_url)
    nulls:          list of (vendor_name, slug)
    deletes:        list of (vendor_name, slug)
    """
    lines = [
        "-- Neshama directory bundle migration — Apr 21, 2026",
        "-- Run on Render shell AFTER merging fix/directory-bundle-apr21 to main and Render redeploys.",
        "-- Before running: take a backup — see ROLLBACK section at bottom.",
        "--",
        "-- Scope:",
        f"--   {len(picks_resolved)} UPDATEs of image_url (Erin's Apr 21 photo picks)",
        f"--   {len(nulls)} UPDATEs to clear image_url (triggers cream placeholder fallback)",
        f"--   {len(deletes)} DELETEs (Option B drops + cleanup)",
        "",
        "BEGIN TRANSACTION;",
        "",
        "-- Pre-migration row counts (for your sanity check in Render shell output)",
        "SELECT 'vendors before' AS label, COUNT(*) AS n FROM vendors;",
        "",
        "-- === 1. Image URL updates (picked photos) ===",
    ]
    for name, slug, url in picks_resolved:
        lines.append(
            f"UPDATE vendors SET image_url = '{sql_escape(url)}' "
            f"WHERE slug = '{sql_escape(slug)}';  -- {sql_escape(name)}"
        )

    lines += ["", "-- === 2. Image URL NULLs (stock-photo / unpicked → cream placeholder) ==="]
    for name, slug in nulls:
        lines.append(
            f"UPDATE vendors SET image_url = '' "
            f"WHERE slug = '{sql_escape(slug)}';  -- {sql_escape(name)}"
        )

    lines += ["", "-- === 3. Vendor deletions (Option B drops) ==="]
    for name, slug in deletes:
        lines += [
            f"-- {sql_escape(name)}",
            f"DELETE FROM vendor_leads WHERE vendor_id IN (SELECT id FROM vendors WHERE slug = '{sql_escape(slug)}');",
            f"DELETE FROM vendor_clicks WHERE vendor_slug = '{sql_escape(slug)}';",
            f"DELETE FROM vendor_views WHERE vendor_slug = '{sql_escape(slug)}';",
            f"DELETE FROM vendors WHERE slug = '{sql_escape(slug)}';",
        ]

    lines += [
        "",
        "-- Post-migration row counts",
        "SELECT 'vendors after' AS label, COUNT(*) AS n FROM vendors;",
        "SELECT 'with image' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NOT NULL AND image_url <> '';",
        "SELECT 'placeholder' AS label, COUNT(*) AS n FROM vendors WHERE image_url IS NULL OR image_url = '';",
        "",
        "COMMIT;",
        "",
        "-- ROLLBACK INSTRUCTIONS",
        "-- If anything looks wrong AFTER COMMIT, restore from the pre-migration dump:",
        "--   sqlite3 neshama.db < pre-bundle-backup.sql",
        "-- Take the backup BEFORE running this script:",
        "--   sqlite3 neshama.db '.dump vendors' > /tmp/vendors-pre-apr21.sql",
        "--   sqlite3 neshama.db '.dump vendor_leads' > /tmp/vendor_leads-pre-apr21.sql",
        "",
    ]
    return "\n".join(lines)

# Erin's picks from DOM recovery (vendor_name -> option number, 1-indexed).
# Picks for vendors already in VENDORS_TO_REMOVE (Arthurs, Lemeac, Hof Kelsten,
# Jerusalem, Moishes) will be no-ops at prod level but we still apply to the
# seed file for consistency in case those vendors come back later.
PICKS = {
    # Montreal
    "Arthurs Nosh Bar": 2,
    # "Benny & Fils" — moved to NULL bucket after local review: option 1 = headless
    # torsos, option 2 = logo/tomato PNG, option 3 = menu scan. No usable option.
    "Blossom by La Plaza": 1,
    "Chenoy's Deli": 3,
    "Chiyoko": 2,
    "Deli 365": 1,
    "Deli 770": 1,
    "Deli Boyz": 1,  # Swapped from 2 (awkward face/shirt crop) to 1 (BBQ chicken combo) after local review
    "District Bagel": 1,
    "Fairmount Bagel": 1,
    "Gibby's": 3,
    "Gifting Kosher Canada": 1,
    "Hof Kelsten": 1,
    "Jerusalem Restaurant": 1,
    "La Marguerite Catering": 1,
    "Lemeac": 1,
    "Lester's Deli": 1,
    "Me Va Mi Kitchen Express": 2,
    "Nosherz": 1,
    "Oineg's Kosher": 1,
    "Olive et Gourmando": 2,
    "Paradise Kosher Catering": 1,
    "Schwartz's Deli": 1,
    "St-Viateur Bagel": 3,
    "Tabule": 1,
    # Toronto
    "Aba's Bagel Company": 2,
    "Apex Kosher Catering": 3,
    "Aroma Espresso Bar": 2,
    "Bistro Grande": 1,
    "Bubby's Bagels": 1,
    "Centre Street Deli": 2,
    "Chop Hop": 1,
    "Cumbrae's": 2,
    "Daiter's Kitchen": 1,
    "Harbord Bakery": 1,
    "Jem Salads": 2,
    "Kiva's Bagels": 3,
    "Kosher Gourmet": 1,
    "Linny's Luncheonette": 1,
    "Marron Bistro": 3,
    "Me-Va-Me": 2,
    "Menchens Glatt Kosher Catering": 1,
    "Milk 'N Honey": 1,
    "Mitzuyan Kosher Catering": 3,
    "Noah Kosher Sushi": 1,
    "Orly's Kitchen": 2,
    "Paese Ristorante": 3,
    "Pantry Foods": 1,
    "Pickle Barrel": 3,
    "Richmond Kosher Bakery": 3,
    "Royal Dairy Cafe & Catering": 3,
    "Slice n Bites": 2,
    "Sofram Restaurant": 1,
    "Summerhill Market": 1,
    "Terroni": 2,
    "The Chicken Nest": 3,
    "Tutto Pronto": 1,
    "United Bakers Dairy Restaurant": 3,
    "Wok & Bowl": 3,
    "Yummy Market": 1,
}

# Stock-photo or AI-generated picks Erin agreed to NULL instead (grief UX).
NULL_STOCK_OR_AI = {
    "Kosher Quality Bakery & Deli",  # iStock
    "Mehadrin Meats",                # Adobe Stock
    "Pizza Pita Prime",              # Adobe Stock
    "Cheese Boutique",               # Adobe Stock
    "Nortown Foods",                 # Adobe Stock
    "Paisanos",                      # Adobe Stock
    "Pancer's Original Deli",        # Shutterstock
    "Zelden's Deli and Desserts",    # iStock
    "Tov-Li Pizza & Falafel",        # ChatGPT-generated
}

# Vendors Erin didn't pick (ran out of steam / no usable candidates) -> placeholder.
NULL_UNPICKED = {
    "Benny & Fils",  # moved from picks after local review — no usable candidate
    "JoJo's Pizza",
    "Montreal Kosher Bakery",
    "Pizza Gourmetti",
    "Snowdon Deli",
    "Beyond Delish",
    "Dr. Laffa",
    "F + B Kosher Catering",
    "Golden Chopsticks",
    "Howie T's Burger Bar",
    "Pizza Cafe",
    "Pusateri's Fine Foods",
    "Sonny Langers Dairy & Vegetarian Caterers",
    "Sushi Inn",
    "Ba-Li Laffa",
    "Haymishe Bakery",
    "Parallel Brothers",
}

# Dicts to remove from seed entirely (already in VENDORS_TO_REMOVE list).
DELETE_DICTS = {"Moishes"}


def load_review_candidates():
    """Parse the review.html DATA array and return {vendor_name: [url1, url2, url3]}."""
    content = REVIEW_PATH.read_text()
    m = re.search(r"const DATA = (\[.*?\]);", content, re.DOTALL)
    if not m:
        raise RuntimeError("Could not find DATA array in review.html")
    data = json.loads(m.group(1))
    return {v["vendor_name"]: v.get("candidates", []) for v in data}


def decode_url(url: str) -> str:
    """HTML-decode URLs that came out of the DOM with entities like &amp;."""
    return html.unescape(url)


def escape_name_for_seed(name: str) -> str:
    """Build a regex pattern matching a vendor name as it appears in seed_vendors.py.

    Some names are in single-quoted Python strings where apostrophes are escaped
    as \\'. Others use double-quoted strings with a bare '. Match either form.
    """
    escaped = re.escape(name)
    # For any apostrophe, accept either ' or \' (optional preceding backslash).
    return escaped.replace("'", r"\\?'")


def update_image_url(src: str, vendor_name: str, new_url: str) -> tuple[str, str | None, str]:
    """Set image_url inside the dict whose name matches.

    If the field exists, replace it. If missing, insert before the dict's closing brace.
    Returns (new_source, old_url_or_None, action) where action is one of
    "updated" / "inserted" / "not_found".
    """
    name_escaped = escape_name_for_seed(vendor_name)

    # Case 1: image_url field already exists in this dict — replace value.
    pattern_existing = re.compile(
        rf"('name':\s*['\"]" + name_escaped + r"['\"],[^{}]*?'image_url':\s*)(['\"])([^'\"]*?)\2",
        re.DOTALL,
    )
    m = pattern_existing.search(src)
    if m:
        old_url = m.group(3)
        new_src = src[: m.start()] + m.group(1) + "'" + new_url + "'" + src[m.end() :]
        return new_src, old_url, "updated"

    # Case 2: no image_url field yet — insert it just before the dict's closing brace.
    # Match the full dict (no nested braces expected in vendor dicts).
    pattern_dict = re.compile(
        r"(\{[^{}]*?'name':\s*['\"]" + name_escaped + r"['\"][^{}]*?)(\n)([ \t]*)(\},?)",
        re.DOTALL,
    )
    m = pattern_dict.search(src)
    if m:
        body, newline, indent, close = m.group(1), m.group(2), m.group(3), m.group(4)
        # Use the same indent as the closing brace, one level deeper (+4 spaces).
        field_indent = indent + "    "
        # Ensure body ends with a comma before we add our line.
        if not body.rstrip().endswith(","):
            body = body.rstrip() + ","
        insertion = f"{newline}{field_indent}'image_url': '{new_url}',"
        new_src = src[: m.start()] + body + insertion + newline + indent + close + src[m.end() :]
        return new_src, None, "inserted"

    return src, None, "not_found"


def delete_dict(src: str, vendor_name: str) -> tuple[str, bool]:
    """Remove the entire dict whose name matches (including leading whitespace + trailing comma + newline)."""
    name_escaped = escape_name_for_seed(vendor_name)
    # Match: optional whitespace, {, ..., 'name': 'X', ..., }, optional comma, newline
    # Constrained to single dict (no nested braces expected).
    pattern = re.compile(
        r"[ \t]*\{[^{}]*?'name':\s*['\"]" + name_escaped + r"['\"][^{}]*?\},?\n",
        re.DOTALL,
    )
    m = pattern.search(src)
    if not m:
        return src, False
    return src[: m.start()] + src[m.end() :], True


def main():
    apply_changes = "--apply" in sys.argv
    write_sql_out = "--sql" in sys.argv

    candidates = load_review_candidates()
    src = SEED_PATH.read_text()

    # Collected records for SQL output (always built — emitted only if --sql).
    sql_picks: list = []
    sql_nulls: list = []
    sql_deletes: list = []

    results = {
        "picks_updated": [],
        "picks_inserted": [],
        "picks_missing_vendor": [],
        "picks_bad_option": [],
        "nulls_updated": [],
        "nulls_inserted": [],
        "nulls_missing_vendor": [],
        "dicts_deleted": [],
        "dicts_missing": [],
    }

    # 1. Apply picks (resolve option -> url from candidates)
    for name, opt in PICKS.items():
        cand = candidates.get(name)
        if not cand:
            results["picks_bad_option"].append((name, opt, "no candidates in review.html"))
            continue
        if opt < 1 or opt > len(cand):
            results["picks_bad_option"].append((name, opt, f"only {len(cand)} candidates"))
            continue
        new_url = decode_url(cand[opt - 1])
        new_src, old_url, action = update_image_url(src, name, new_url)
        if action == "updated":
            src = new_src
            results["picks_updated"].append((name, old_url, new_url))
            sql_picks.append((name, slugify(name), new_url))
        elif action == "inserted":
            src = new_src
            results["picks_inserted"].append((name, new_url))
            sql_picks.append((name, slugify(name), new_url))
        else:
            results["picks_missing_vendor"].append(name)

    # 2. NULL out stock/AI + unpicked
    for name in sorted(NULL_STOCK_OR_AI | NULL_UNPICKED):
        new_src, old_url, action = update_image_url(src, name, "")
        if action == "updated":
            src = new_src
            results["nulls_updated"].append((name, old_url))
            sql_nulls.append((name, slugify(name)))
        elif action == "inserted":
            src = new_src
            results["nulls_inserted"].append(name)
            sql_nulls.append((name, slugify(name)))
        else:
            results["nulls_missing_vendor"].append(name)

    # 3. Delete Moishes dict
    for name in DELETE_DICTS:
        new_src, ok = delete_dict(src, name)
        if ok:
            src = new_src
            results["dicts_deleted"].append(name)
            sql_deletes.append((name, slugify(name)))
        else:
            results["dicts_missing"].append(name)
            sql_deletes.append((name, slugify(name)))  # still emit DELETE — may exist on prod even if seed was already clean

    # Report
    print(f"Picks updated:        {len(results['picks_updated'])}")
    print(f"Picks inserted:       {len(results['picks_inserted'])}")
    print(f"Picks missing vendor: {len(results['picks_missing_vendor'])}")
    print(f"Picks bad option:     {len(results['picks_bad_option'])}")
    print(f"NULLs updated:        {len(results['nulls_updated'])}")
    print(f"NULLs inserted:       {len(results['nulls_inserted'])}")
    print(f"NULLs missing vendor: {len(results['nulls_missing_vendor'])}")
    print(f"Dicts deleted:        {len(results['dicts_deleted'])}")
    print(f"Dicts missing:        {len(results['dicts_missing'])}")

    if results["picks_missing_vendor"]:
        print("\nPicks where vendor name didn't match seed:")
        for n in results["picks_missing_vendor"]:
            print(f"  - {n}")
    if results["picks_bad_option"]:
        print("\nPicks with invalid option:")
        for n, o, why in results["picks_bad_option"]:
            print(f"  - {n}: option {o} — {why}")
    if results["nulls_missing_vendor"]:
        print("\nNULLs where vendor name didn't match seed:")
        for n in results["nulls_missing_vendor"]:
            print(f"  - {n}")
    if results["dicts_missing"]:
        print("\nDict deletions that didn't match:")
        for n in results["dicts_missing"]:
            print(f"  - {n}")

    if apply_changes:
        SEED_PATH.write_text(src)
        print(f"\n✅ Wrote {SEED_PATH}")
    else:
        print("\n(dry-run — re-run with --apply to write seed_vendors.py)")

    if write_sql_out:
        sql = write_sql(sql_picks, sql_nulls, sql_deletes)
        SQL_PATH.write_text(sql)
        print(f"\n✅ Wrote {SQL_PATH}  ({len(sql_picks)} updates + {len(sql_nulls)} NULLs + {len(sql_deletes)} deletes)")


if __name__ == "__main__":
    main()
