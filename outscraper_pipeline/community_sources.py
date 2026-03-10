#!/usr/bin/env python3
"""
Neshama Vendor Pipeline — Community Verification Sources
Cross-references scraped vendors against trusted community sources.

Vendors found in community sources get auto-promoted.
Vendors found ONLY in Outscraper get flagged for manual review.

Usage:
    python community_sources.py --input data/step2_cleaned_20260309.csv
    python community_sources.py --update-sources
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime


# ── Community source data ──
# These are populated manually from trusted sources.
# Each source has a trust level: HIGH (direct recommendation),
# MEDIUM (published list), LOW (mentioned online).

SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'data', 'community_sources.json')

DEFAULT_SOURCES = {
    "meta": {
        "last_updated": "2026-03-09",
        "description": "Trusted community sources for vendor verification. "
                       "Vendors found here get auto-promoted in the pipeline."
    },

    # ── Source 1: Misaskim (Eli Warner) ──
    # 500 funerals/year, Orthodox community, direct relationship via Jordana
    "misaskim": {
        "source_name": "Misaskim / Eli Warner",
        "trust_level": "HIGH",
        "contact": "Eli Warner (via Jordana)",
        "website": "missaskim.ca",
        "notes": "Plans 500 funerals/year. Orthodox community. Loved yahrzeit feature. "
                 "Said we can pull from his listings. Will recommend Neshama.",
        "vendors": [
            # Populate after scraping missaskim.ca or getting list from Eli
        ]
    },

    # ── Source 2: Jordana's personal network ──
    # Co-founder, Orthodox circles, Forest Hill / North York
    "jordana_network": {
        "source_name": "Jordana Mednick (co-founder)",
        "trust_level": "HIGH",
        "notes": "Personal knowledge of caterers and vendors in the Orthodox community. "
                 "Her recommendations carry the most weight.",
        "vendors": [
            # These are vendors Jordana has personally recommended or corrected
            {"name": "Bubby's Bagels", "category": "bakery", "endorsed": True},
            {"name": "Cafe Sheli", "category": "restaurant", "endorsed": True},
            {"name": "Daiter's Kitchen", "category": "deli", "endorsed": True},
            {"name": "Gryfe's Bagel Bakery", "category": "bakery", "endorsed": True},
            {"name": "Kiva's Bagels", "category": "bakery", "endorsed": True},
            {"name": "Main Event Catering", "category": "caterer", "endorsed": True},
            {"name": "Paisanos", "category": "restaurant", "endorsed": True},
            {"name": "Pizza Cafe", "category": "restaurant", "endorsed": True},
            {"name": "Aroma Espresso Bar", "category": "restaurant", "endorsed": True},
            {"name": "Chop Hop", "category": "restaurant", "endorsed": True},
            {"name": "Golden Chopsticks", "category": "restaurant", "endorsed": True},
            {"name": "Shalom India", "category": "restaurant", "endorsed": True},
            {"name": "AB Cookies", "category": "bakery", "endorsed": True},
            {"name": "Good Person Biscotti", "category": "bakery", "endorsed": True},
            # Vendors Jordana flagged for REMOVAL (no longer exist / bad quality)
            {"name": "Miami Grill", "category": "restaurant", "endorsed": False, "reason": "closed"},
            {"name": "Village Pizza Kosher", "category": "restaurant", "endorsed": False, "reason": "closed"},
            {"name": "Citrus Traiteur", "category": "caterer", "endorsed": False, "reason": "removed by Jordana"},
        ]
    },

    # ── Source 3: COR (Kashruth Council of Canada) ──
    # Official Toronto kosher certification body
    "cor": {
        "source_name": "COR (Kashruth Council of Canada)",
        "trust_level": "MEDIUM",
        "website": "https://cor.ca",
        "notes": "Official kosher certification for Toronto. Published directory at cor.ca. "
                 "Being COR-certified means the business meets halachic standards.",
        "vendors": [
            # Populate by scraping cor.ca/establishments or their directory
            # These are known COR vendors already in our database
        ]
    },

    # ── Source 4: MK (Montreal Kosher) ──
    "mk": {
        "source_name": "MK (Montreal Kosher / Vaad Ha'ir)",
        "trust_level": "MEDIUM",
        "website": "https://mk.ca",
        "notes": "Official kosher certification for Montreal.",
        "vendors": []
    },

    # ── Source 5: Funeral home vendor lists ──
    "funeral_homes": {
        "source_name": "Funeral Home Referral Lists",
        "trust_level": "HIGH",
        "notes": "Benjamin's, Steeles, and Paperman's give families vendor lists. "
                 "Being on a funeral home list = highest community endorsement. "
                 "Jordana to request lists when calling funeral homes.",
        "vendors": []
    },

    # ── Source 6: Synagogue chesed committees ──
    "chesed_committees": {
        "source_name": "Synagogue Chesed Committees",
        "trust_level": "HIGH",
        "notes": "Every shul has a chesed committee that coordinates meals for mourners. "
                 "They maintain internal lists of reliable caterers. "
                 "Target: Beth Emeth, Beth Torah, Shaarei Shomayim, Adath Israel, "
                 "BAYT, Aish, Shaarei Tefillah.",
        "vendors": []
    },

    # ── Source 7: Toronto Jewish Facebook groups ──
    "facebook_groups": {
        "source_name": "Toronto Jewish Facebook Groups",
        "trust_level": "LOW",
        "notes": "Groups like 'Jewish Toronto', 'Kosher Food Toronto', etc. "
                 "Search for vendor recommendations in posts. Low trust individually "
                 "but high signal when multiple people recommend the same vendor.",
        "vendors": []
    },
}


def load_sources():
    """Load community sources from JSON file."""
    if os.path.exists(SOURCES_FILE):
        with open(SOURCES_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_SOURCES


def save_sources(sources):
    """Save community sources to JSON file."""
    os.makedirs(os.path.dirname(SOURCES_FILE), exist_ok=True)
    with open(SOURCES_FILE, 'w') as f:
        json.dump(sources, f, indent=2)
    print(f"Saved community sources to {SOURCES_FILE}")


def normalize(name):
    """Normalize name for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    # Remove common suffixes
    for suffix in ['inc', 'ltd', 'llc', 'corp', 'restaurant', 'bakery', 'catering']:
        name = re.sub(rf'\b{suffix}\b', '', name)
    return name.strip()


def check_community_sources(vendor_name, sources):
    """Check if a vendor appears in any community source.
    Returns: list of (source_name, trust_level, endorsed) tuples.
    """
    matches = []
    normalized = normalize(vendor_name)

    for source_key, source in sources.items():
        if source_key == 'meta':
            continue
        for vendor in source.get('vendors', []):
            v_name = vendor if isinstance(vendor, str) else vendor.get('name', '')
            if normalize(v_name) == normalized or normalized in normalize(v_name) or normalize(v_name) in normalized:
                endorsed = vendor.get('endorsed', True) if isinstance(vendor, dict) else True
                reason = vendor.get('reason', '') if isinstance(vendor, dict) else ''
                matches.append({
                    'source': source.get('source_name', source_key),
                    'trust_level': source.get('trust_level', 'LOW'),
                    'endorsed': endorsed,
                    'reason': reason,
                })

    return matches


def verify_against_community(input_csv, output_dir=None):
    """Cross-reference a cleaned vendor CSV against community sources."""
    sources = load_sources()

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Checking {len(rows)} vendors against community sources...")

    community_verified = []  # Found in community sources, endorsed
    community_rejected = []  # Found in community sources, NOT endorsed
    outscraper_only = []     # Not found in any community source
    stats = {'high': 0, 'medium': 0, 'low': 0}

    for row in rows:
        name = row.get('name', row.get('business_name', '')).strip()
        matches = check_community_sources(name, sources)

        if matches:
            # Check if any source says NOT endorsed
            rejected = [m for m in matches if not m['endorsed']]
            if rejected:
                row['community_status'] = 'REJECTED'
                row['community_sources'] = '; '.join(
                    f"{m['source']} ({m['reason']})" for m in rejected)
                community_rejected.append(row)
            else:
                row['community_status'] = 'VERIFIED'
                row['community_sources'] = '; '.join(
                    f"{m['source']} [{m['trust_level']}]" for m in matches)
                # Track highest trust level
                trust_levels = [m['trust_level'] for m in matches]
                if 'HIGH' in trust_levels:
                    row['community_trust'] = 'HIGH'
                    stats['high'] += 1
                elif 'MEDIUM' in trust_levels:
                    row['community_trust'] = 'MEDIUM'
                    stats['medium'] += 1
                else:
                    row['community_trust'] = 'LOW'
                    stats['low'] += 1
                community_verified.append(row)
        else:
            row['community_status'] = 'OUTSCRAPER_ONLY'
            row['community_sources'] = ''
            row['community_trust'] = 'UNVERIFIED'
            outscraper_only.append(row)

    # Save results
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    date_str = datetime.now().strftime('%Y%m%d')
    columns = list(rows[0].keys()) if rows else []
    extra_cols = ['community_status', 'community_sources', 'community_trust']
    all_cols = columns + [c for c in extra_cols if c not in columns]

    # Community verified
    path = os.path.join(output_dir, f'community_verified_{date_str}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(community_verified)

    # Community rejected
    path = os.path.join(output_dir, f'community_rejected_{date_str}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols + ['community_status'],
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(community_rejected)

    # Outscraper only (needs manual review)
    path = os.path.join(output_dir, f'outscraper_only_{date_str}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(outscraper_only)

    # Report
    print(f"\n{'='*60}")
    print(f"COMMUNITY VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"Total vendors checked: {len(rows)}")
    print(f"")
    print(f"Community VERIFIED: {len(community_verified)}")
    print(f"  HIGH trust (Jordana/Misaskim/funeral homes): {stats['high']}")
    print(f"  MEDIUM trust (COR/MK certified lists): {stats['medium']}")
    print(f"  LOW trust (Facebook/online mentions): {stats['low']}")
    print(f"")
    print(f"Community REJECTED: {len(community_rejected)}")
    for r in community_rejected:
        print(f"  {r.get('name', '?')} — {r.get('community_sources', '')}")
    print(f"")
    print(f"Outscraper ONLY (needs review): {len(outscraper_only)}")
    print(f"")
    print(f"RECOMMENDATION:")
    print(f"  - Community verified vendors → auto-promote to Tier 1")
    print(f"  - Community rejected → remove from pipeline")
    print(f"  - Outscraper only → send to Jordana for review before importing")
    print(f"{'='*60}")

    return community_verified, community_rejected, outscraper_only


def main():
    parser = argparse.ArgumentParser(
        description='Neshama Pipeline — Community Verification')
    parser.add_argument('--input', type=str,
                        help='Cleaned vendor CSV to verify')
    parser.add_argument('--update-sources', action='store_true',
                        help='Initialize/update the community sources JSON file')
    parser.add_argument('--add-vendor', type=str,
                        help='Add a vendor to a source (format: source:vendor_name)')
    parser.add_argument('--list-sources', action='store_true',
                        help='Show all community sources and vendor counts')

    args = parser.parse_args()

    if args.update_sources:
        sources = load_sources()
        # Merge with defaults (add any new sources)
        for key, value in DEFAULT_SOURCES.items():
            if key not in sources:
                sources[key] = value
        save_sources(sources)
        print("Community sources file updated.")
        return

    if args.list_sources:
        sources = load_sources()
        print(f"\n{'='*60}")
        print(f"COMMUNITY SOURCES")
        print(f"{'='*60}")
        for key, source in sources.items():
            if key == 'meta':
                continue
            vendors = source.get('vendors', [])
            endorsed = sum(1 for v in vendors
                           if (isinstance(v, dict) and v.get('endorsed', True)) or isinstance(v, str))
            rejected = sum(1 for v in vendors
                           if isinstance(v, dict) and not v.get('endorsed', True))
            print(f"\n{source.get('source_name', key)} [{source.get('trust_level', '?')}]")
            print(f"  Endorsed: {endorsed} | Rejected: {rejected}")
            if source.get('notes'):
                print(f"  {source['notes'][:100]}")
        return

    if args.add_vendor:
        parts = args.add_vendor.split(':', 1)
        if len(parts) != 2:
            print("Format: --add-vendor source_key:Vendor Name")
            sys.exit(1)
        source_key, vendor_name = parts
        sources = load_sources()
        if source_key not in sources:
            print(f"Source '{source_key}' not found. Available: {list(sources.keys())}")
            sys.exit(1)
        sources[source_key]['vendors'].append(
            {"name": vendor_name, "endorsed": True})
        save_sources(sources)
        print(f"Added '{vendor_name}' to {source_key}")
        return

    if args.input:
        if not os.path.exists(args.input):
            print(f"File not found: {args.input}")
            sys.exit(1)
        # Initialize sources file if it doesn't exist
        if not os.path.exists(SOURCES_FILE):
            save_sources(DEFAULT_SOURCES)
        verify_against_community(args.input)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
