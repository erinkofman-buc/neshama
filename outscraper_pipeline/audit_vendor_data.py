#!/usr/bin/env python3
"""
Vendor Data Audit — flags integrity issues across all vendors in the Neshama directory.

Reads from production /api/vendors + /api/gift-vendors (local DB is empty per
feedback_local_db_empty). Runs checks. Outputs CSV + JSON for Jordana to review and
Erin to action.

Usage:
    python3 outscraper_pipeline/audit_vendor_data.py
    python3 outscraper_pipeline/audit_vendor_data.py --check-urls    # also test URL liveness (slow)
    python3 outscraper_pipeline/audit_vendor_data.py --output ~/Desktop/foo.csv

Output:
    CSV at ~/Desktop/Neshama_Vendor_Photo_Audit/vendor-data-audit-YYYY-MM-DD.csv
    JSON sibling for programmatic use

Issue levels:
    CRITICAL — blocks customer experience (broken URL, fake address, "Kosher Style" label)
    WARN     — notable but non-blocking (placeholder image, missing phone, no description)
    INFO     — improvement opportunity (missing Instagram, missing hours, generic description)

Rules referenced:
    feedback_no_kosher_style.md         — "Kosher Style" label is forbidden
    feedback_kosher_inclusivity.md      — non-kosher options must be clearly labeled
    feedback_neshama_data_safety.md     — never break URLs, never drop tables
    feedback_obituary_quality.md        — never highlight count, focus on freshness/accuracy

Per Rule #1: This script READS only. Never writes to vendors table. Output is
human-reviewed before any seed_vendors.py update.
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_API_BASE = "https://neshama.ca"
DEFAULT_OUTPUT_DIR = Path.home() / "Desktop/Neshama_Vendor_Photo_Audit"

# Image URL patterns that indicate placeholder/missing image
PLACEHOLDER_PATTERNS = [
    "placeholder",
    "/static/cream",
    "no-image",
    "default.png",
    "logo-only",
    "/static/default",
]

# Address patterns that indicate test/fake data
SUSPICIOUS_ADDRESS_PATTERNS = [
    "123 main",
    "1 main st",
    "test address",
    "tbd",
    "n/a",
    "various locations",
    "unknown",
    "address tbd",
]

# Valid kosher_status values per UPDATED feedback_no_kosher_style.md (Apr 29 2026):
# Binary: Kosher / not_kosher. Old COR/MK/not_certified taxonomy is being migrated.
VALID_KOSHER_STATUS_NEW = {"Kosher", "not_kosher", "", None}
# Legacy values still in production (147 vendors as of Apr 29) — flagged as MIGRATION-NEEDED until SQL migration ships:
LEGACY_KOSHER_STATUS = {"COR", "MK", "not_certified"}
# "Kosher Style" is still forbidden — implies cert when there is none.


def fetch_vendors(api_base):
    """Fetch all vendors from production API (food + gift), deduped by slug.
    Both endpoints return gift vendors (per api_server.py line 2958: /api/vendors filter
    is `vendor_type IN ('food', 'services', 'gift')`). Dedupe by slug, prefer the entry
    from /api/vendors when conflicting (richer data)."""
    by_slug = {}
    counts = {}
    for endpoint in ["/api/vendors", "/api/gift-vendors"]:
        url = f"{api_base.rstrip('/')}{endpoint}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Neshama-Audit/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                if data.get("status") == "success":
                    vs = data.get("vendors", []) or data.get("data", [])
                    counts[endpoint] = len(vs)
                    for v in vs:
                        slug = (v.get("slug") or "").strip()
                        if slug and slug not in by_slug:
                            by_slug[slug] = v
                else:
                    print(f"  {endpoint}: ERROR — {data.get('message', 'unknown')}", file=sys.stderr)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            print(f"  {endpoint}: FETCH FAILED — {e}", file=sys.stderr)

    for endpoint, n in counts.items():
        print(f"  {endpoint}: {n} vendors")
    print(f"  After dedupe by slug: {len(by_slug)} unique vendors")
    return list(by_slug.values())


def url_format_issue(url):
    if not url or not url.strip():
        return "missing"
    if not (url.startswith("http://") or url.startswith("https://")):
        return f"missing scheme (current: {url[:50]})"
    return None


def check_url_live(url, timeout=8):
    """Check if URL responds 200. Returns (status_code, error)."""
    if not url:
        return None, "no url"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 Neshama-Audit"}, method="HEAD"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)[:80]


def is_placeholder_image(url):
    if not url:
        return True
    return any(p in url.lower() for p in PLACEHOLDER_PATTERNS)


def is_suspicious_address(addr):
    if not addr or not addr.strip():
        return False  # missing != fake (separate flag)
    addr_lower = addr.strip().lower()
    if any(p in addr_lower for p in SUSPICIOUS_ADDRESS_PATTERNS):
        return True
    if len(addr.strip()) < 8:
        return True
    return False


def phone_format_issue(phone):
    if not phone or not phone.strip():
        return None  # missing handled separately
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10 or len(digits) > 11:
        return f"unusual digit count ({len(digits)})"
    return None


def audit_vendor(v, check_urls=False):
    """Return list of (level, field, message, current_value) for this vendor."""
    issues = []

    name = v.get("name", "").strip()
    slug = v.get("slug", "").strip()

    # Required fields
    if not name:
        issues.append(("CRITICAL", "name", "Missing vendor name", ""))
    if not slug:
        issues.append(("CRITICAL", "slug", "Missing vendor slug", ""))
    if not v.get("vendor_type") and not v.get("category"):
        issues.append(("WARN", "vendor_type", "Missing vendor_type and category", ""))

    # Kosher status (per feedback_no_kosher_style.md)
    ks = (v.get("kosher_status") or "").strip()
    if ks.lower() == "kosher style":
        issues.append((
            "CRITICAL", "kosher_status",
            "'Kosher Style' label is forbidden — use COR/MK/not_certified",
            ks,
        ))
    elif ks and ks not in VALID_KOSHER_STATUS:
        issues.append(("WARN", "kosher_status", f"Non-standard value: {ks}", ks))

    # Website URL
    web = v.get("website") or ""
    web_issue = url_format_issue(web)
    if web_issue == "missing":
        issues.append(("INFO", "website", "Missing website", ""))
    elif web_issue:
        issues.append(("CRITICAL", "website", web_issue, web))
    elif check_urls:
        status, err = check_url_live(web)
        if err:
            issues.append(("WARN", "website", f"URL check failed: {err}", web))
        elif status and status >= 400:
            issues.append(("CRITICAL", "website", f"URL returns HTTP {status}", web))

    # Image URL
    img = v.get("image_url") or v.get("image") or ""
    if not img:
        issues.append(("WARN", "image_url", "No image (placeholder displayed)", ""))
    elif is_placeholder_image(img):
        issues.append(("WARN", "image_url", "Using placeholder image", img))
    elif check_urls:
        status, err = check_url_live(img)
        if err:
            issues.append(("WARN", "image_url", f"Image URL check failed: {err}", img))
        elif status and status >= 400:
            issues.append(("CRITICAL", "image_url", f"Image returns HTTP {status}", img))

    # Phone
    phone = v.get("phone") or ""
    p_issue = phone_format_issue(phone)
    if p_issue:
        issues.append(("WARN", "phone", p_issue, phone))
    elif not phone.strip():
        issues.append(("INFO", "phone", "Missing phone", ""))

    # Address
    addr = v.get("address") or ""
    if is_suspicious_address(addr):
        issues.append(("CRITICAL", "address", f"Suspicious address: '{addr}'", addr))
    elif not addr.strip():
        issues.append(("INFO", "address", "Missing address", ""))

    # Description
    desc = (v.get("description") or "").strip()
    if not desc:
        issues.append(("INFO", "description", "Missing description", ""))
    elif len(desc) < 30:
        issues.append(("INFO", "description", f"Description too short ({len(desc)} chars)", desc))

    return issues


def find_duplicates(vendors):
    """Find vendors with duplicate slugs or name-normalized duplicates."""
    by_slug = defaultdict(list)
    by_name_norm = defaultdict(list)

    for v in vendors:
        slug = (v.get("slug") or "").strip()
        if slug:
            by_slug[slug].append(v)
        name_norm = re.sub(r"[^a-z0-9]", "", (v.get("name") or "").lower())
        if name_norm:
            by_name_norm[name_norm].append(v)

    issues = []
    for slug, vs in by_slug.items():
        if len(vs) > 1:
            ids = [str(v.get("id", "?")) for v in vs]
            issues.append({
                "level": "CRITICAL",
                "type": "duplicate_slug",
                "slug": slug,
                "vendor_ids": ids,
                "names": [v.get("name") for v in vs],
                "message": f"Duplicate slug '{slug}' shared by {len(vs)} vendors",
            })
    for name_norm, vs in by_name_norm.items():
        if len(vs) > 1:
            slugs = [v.get("slug", "?") for v in vs]
            if len(set(slugs)) > 1:
                issues.append({
                    "level": "WARN",
                    "type": "near_duplicate_name",
                    "vendor_names": [v.get("name") for v in vs],
                    "vendor_slugs": slugs,
                    "message": f"Near-duplicate names: {', '.join(v.get('name','') for v in vs)}",
                })
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("--api-base", default=DEFAULT_API_BASE,
                        help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--check-urls", action="store_true",
                        help="Also HEAD-check website + image URLs (slow)")
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    print("=" * 70)
    print("  Vendor Data Audit")
    print("=" * 70)
    print(f"  API base: {args.api_base}")
    print(f"  URL liveness check: {'YES' if args.check_urls else 'no (use --check-urls to enable)'}")
    print()

    print("Fetching vendors from production API:")
    vendors = fetch_vendors(args.api_base)
    print(f"  Total: {len(vendors)} vendors")
    print()

    if not vendors:
        print("ERROR: no vendors fetched. Aborting.", file=sys.stderr)
        sys.exit(1)

    print("Auditing per-vendor issues...")
    audit_rows = []
    by_level = defaultdict(int)
    for v in vendors:
        issues = audit_vendor(v, check_urls=args.check_urls)
        for level, field, message, current_value in issues:
            audit_rows.append({
                "level": level,
                "vendor_id": v.get("id", ""),
                "vendor_slug": v.get("slug", ""),
                "vendor_name": v.get("name", ""),
                "vendor_type": v.get("vendor_type") or v.get("category", ""),
                "city": v.get("city", ""),
                "field": field,
                "issue": message,
                "current_value": str(current_value)[:200] if current_value else "",
            })
            by_level[level] += 1

    print(f"  Per-vendor issues: {len(audit_rows)}")
    print()

    print("Checking cross-vendor issues (duplicate slugs, near-duplicate names)...")
    dup_issues = find_duplicates(vendors)
    print(f"  Cross-vendor issues: {len(dup_issues)}")
    print()

    timestamp = datetime.now().strftime("%Y-%m-%d")
    csv_path = Path(args.output_csv).expanduser() if args.output_csv \
        else DEFAULT_OUTPUT_DIR / f"vendor-data-audit-{timestamp}.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    level_order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    audit_rows.sort(key=lambda r: (level_order.get(r["level"], 99), r["vendor_name"], r["field"]))

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["level", "vendor_id", "vendor_slug", "vendor_name",
                      "vendor_type", "city", "field", "issue", "current_value"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    json_path = Path(args.output_json).expanduser() if args.output_json \
        else csv_path.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "api_base": args.api_base,
            "url_liveness_checked": args.check_urls,
            "vendor_count": len(vendors),
            "summary": dict(by_level),
            "rows": audit_rows,
            "cross_vendor_issues": dup_issues,
        }, f, indent=2, default=str)

    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Vendors checked: {len(vendors)}")
    print(f"  CRITICAL issues: {by_level.get('CRITICAL', 0)}")
    print(f"  WARN issues:     {by_level.get('WARN', 0)}")
    print(f"  INFO issues:     {by_level.get('INFO', 0)}")
    print(f"  Duplicate flags: {len(dup_issues)}")
    print()
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    print("=" * 70)
    print()

    critical = [r for r in audit_rows if r["level"] == "CRITICAL"]
    if critical:
        print(f"  Top CRITICAL issues (first 15):")
        for r in critical[:15]:
            print(f"    - {r['vendor_name']} ({r['vendor_slug']}): "
                  f"{r['issue']}{' — ' + r['current_value'][:60] if r['current_value'] else ''}")
        if len(critical) > 15:
            print(f"    ... and {len(critical) - 15} more in CSV")

    if dup_issues:
        print()
        print(f"  Cross-vendor issues:")
        for dup in dup_issues:
            print(f"    - [{dup['level']}] {dup['message']}")


if __name__ == "__main__":
    main()
