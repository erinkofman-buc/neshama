#!/usr/bin/env python3
"""
check_next_cycle.py — Photo-audit auto-queuer detector.

Captured Apr 30, 2026 to replace the manual "scan prod for placeholders, build a CSV,
queue Jordana" orchestration that ran in Cycles 3 + 4. Intended as the foundation
for a scheduled job that surfaces "next cycle is ready" automatically.

What it does:
  1. Hits https://neshama.ca/api/vendors and counts vendors with no image_url
  2. Reads every existing data/cycle*-placeholders.csv to see who's already been queued
  3. Diffs: NEW placeholders = current placeholders MINUS vendors already queued in any prior cycle
  4. If --write-draft and new count >= --threshold (default 8), emits data/cycle{N+1}-placeholders.csv
  5. Prints a status report (suitable for cron output / Telegram piping)

Usage:
  python3 check_next_cycle.py                    # status only
  python3 check_next_cycle.py --write-draft      # also write next cycle CSV if threshold met
  python3 check_next_cycle.py --threshold 5      # lower threshold (default: 8)

Why threshold 8: Cycle 3 = 65/72 vendors. Cycle 4 = 38 placeholders. Both substantial.
Below 8 new placeholders, cost of a cycle (Jordana's 30 min + Firecrawl credits) outweighs benefit.
Above 8, a fresh cycle is worth queuing.

Idempotent: running this twice in a row produces the same output. Writing a draft is the only
side effect, and only when explicitly asked AND threshold met.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import urllib.request
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
DATA_DIR = PIPELINE_DIR / "data"
PROD_VENDORS_URL = "https://neshama.ca/api/vendors"
DEFAULT_THRESHOLD = 8


def fetch_prod_vendors() -> list[dict]:
    req = urllib.request.Request(PROD_VENDORS_URL, headers={"User-Agent": "neshama-cycle-checker/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("vendors", "data", "results"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    raise RuntimeError(f"Unrecognised /api/vendors payload shape: {type(payload).__name__}")


def find_placeholders(vendors: list[dict]) -> list[dict]:
    """Vendor needs a fresh image when image_url is missing or empty."""
    placeholders = []
    for v in vendors:
        img = (v.get("image_url") or "").strip()
        if not img:
            placeholders.append(v)
    return placeholders


def previously_queued_names() -> tuple[set[str], int]:
    """Return (set of vendor names already queued, highest cycle number seen)."""
    queued: set[str] = set()
    cycles_seen: list[int] = []
    pattern = str(DATA_DIR / "cycle*-placeholders.csv")
    for path in sorted(glob.glob(pattern)):
        cycle_num = _parse_cycle_number(path)
        if cycle_num is not None:
            cycles_seen.append(cycle_num)
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        # Header may be on line 3 (CSVs include a 2-line metadata preamble). Probe both.
        header_idx = None
        for idx, line in enumerate(lines[:5]):
            if "Vendor Name" in line and "City" in line:
                header_idx = idx
                break
        if header_idx is None:
            continue
        reader = csv.DictReader(lines[header_idx:])
        for row in reader:
            name = (row.get("Vendor Name") or "").strip()
            if name:
                queued.add(name)
    highest = max(cycles_seen) if cycles_seen else 0
    return queued, highest


def _parse_cycle_number(path: str) -> int | None:
    name = os.path.basename(path)
    if not name.startswith("cycle"):
        return None
    num = name[len("cycle"):].split("-", 1)[0]
    try:
        return int(num)
    except ValueError:
        return None


def write_draft_csv(new_vendors: list[dict], next_cycle: int) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"cycle{next_cycle}-placeholders.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([f"Cycle {next_cycle} — auto-queued placeholder backfill", "", "", ""])
        writer.writerow([f"{len(new_vendors)} new placeholders since prior cycles", "", "", ""])
        writer.writerow(["Vendor Name", "City", "Image Status", "New Image URL"])
        for v in sorted(new_vendors, key=lambda r: (r.get("name") or "").lower()):
            name = v.get("name") or ""
            address = v.get("address") or ""
            city = _guess_city(address)
            website = (v.get("website") or "").strip()
            writer.writerow([name, city, "Replace", website])
    return out_path


def _guess_city(address: str) -> str:
    """Fallback city guess from address. Jordana edits if wrong."""
    addr_lower = address.lower()
    if "montreal" in addr_lower or "côte" in addr_lower or "qc" in addr_lower:
        return "Montreal"
    if "thornhill" in addr_lower or "vaughan" in addr_lower or "richmond hill" in addr_lower:
        return "Toronto"
    if "toronto" in addr_lower or ", on" in addr_lower:
        return "Toronto"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Min new placeholders to suggest a new cycle (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--write-draft", action="store_true",
                        help="Write data/cycle{N+1}-placeholders.csv if threshold met")
    parser.add_argument("--quiet", action="store_true",
                        help="Single-line summary only (cron-friendly)")
    args = parser.parse_args()

    try:
        vendors = fetch_prod_vendors()
    except Exception as e:
        print(f"FAIL: could not fetch prod vendors: {e}", file=sys.stderr)
        return 2

    placeholders = find_placeholders(vendors)
    queued, highest_cycle = previously_queued_names()
    placeholder_names = {(v.get("name") or "").strip() for v in placeholders}
    new_names = placeholder_names - queued
    new_vendors = [v for v in placeholders if (v.get("name") or "").strip() in new_names]

    next_cycle = highest_cycle + 1
    threshold_met = len(new_vendors) >= args.threshold

    if args.quiet:
        print(f"vendors={len(vendors)} placeholders={len(placeholders)} "
              f"queued_in_prior_cycles={len(queued)} new={len(new_vendors)} "
              f"threshold={args.threshold} ready={'yes' if threshold_met else 'no'} "
              f"next_cycle={next_cycle}")
        return 0

    print("=" * 60)
    print("Photo-audit cycle status")
    print("=" * 60)
    print(f"Vendors on prod          : {len(vendors)}")
    print(f"Vendors with image_url   : {len(vendors) - len(placeholders)}")
    print(f"Placeholders             : {len(placeholders)}")
    print(f"Queued in prior cycles   : {len(queued)}  (highest cycle seen: {highest_cycle})")
    print(f"NEW placeholders         : {len(new_vendors)}")
    print(f"Threshold for new cycle  : {args.threshold}")
    print()

    if threshold_met:
        print(f"NEXT CYCLE READY: {len(new_vendors)} new placeholders >= threshold {args.threshold}")
        print(f"Suggested cycle number   : {next_cycle}")
        if args.write_draft:
            out_path = write_draft_csv(new_vendors, next_cycle)
            print(f"Wrote draft CSV          : {out_path}")
            print()
            print("Next steps:")
            print(f"  1. Jordana fills 'New Image URL' column where the auto-guessed website is wrong/missing")
            print(f"  2. Run: python3 outscraper_pipeline/extract_audit_images.py --csv {out_path}")
            print(f"  3. Run: python3 outscraper_pipeline/extract_fallback_images.py")
            print(f"  4. Run: python3 outscraper_pipeline/generate_review_page.py --cycle {next_cycle}")
        else:
            print()
            print("To generate the draft CSV, re-run with --write-draft")
        if new_vendors[:10]:
            print()
            print("Sample new placeholders (first 10 alphabetical):")
            for v in sorted(new_vendors, key=lambda r: (r.get("name") or "").lower())[:10]:
                addr = (v.get("address") or "").split(",")[0]
                print(f"  - {v.get('name', '?')}  ({_guess_city(v.get('address') or '')}, {addr})")
    else:
        gap = args.threshold - len(new_vendors)
        if gap > 0:
            print(f"NOT YET: {len(new_vendors)} new placeholders, need {gap} more to hit threshold {args.threshold}")
        else:
            print("NOT YET: no new placeholders since prior cycles")

    return 0 if threshold_met else 1


if __name__ == "__main__":
    sys.exit(main())
