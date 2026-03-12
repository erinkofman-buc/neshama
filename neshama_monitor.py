#!/usr/bin/env python3
"""
Neshama Production Monitor
Run this to check the health of all production systems.
Usage: python3 neshama_monitor.py
Can be called from cron, /health-check skill, or manually.
"""

import json
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE_URL = "https://neshama.ca"
ISSUES = []
WARNINGS = []


def check(name, url, validator=None):
    """Check a URL and optionally validate the response."""
    try:
        req = Request(url, headers={'User-Agent': 'NeshamaMonitor/1.0'})
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        if validator:
            validator(data)
        return data
    except URLError as e:
        ISSUES.append(f"[{name}] Connection failed: {e}")
        return None
    except Exception as e:
        ISSUES.append(f"[{name}] Error: {e}")
        return None


def main():
    print(f"\n{'='*60}")
    print(f"  NESHAMA PRODUCTION MONITOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. Health endpoint
    print("1. Health Check...")
    health = check("Health", f"{BASE_URL}/api/health")
    if health:
        status = health.get('status', 'unknown')
        checks = health.get('checks', {})

        if status != 'ok':
            ISSUES.append(f"Overall status: {status}")

        # Check each subsystem
        for name, info in checks.items():
            if isinstance(info, dict):
                if not info.get('ok', True):
                    if name == 'scraper_freshness':
                        sources = info.get('sources', {})
                        for src, sdata in sources.items():
                            if not sdata.get('fresh'):
                                ISSUES.append(f"Scraper STALE: {src} — last: {sdata.get('latest', 'never')}")
                    else:
                        ISSUES.append(f"{name}: FAILED — {info.get('error', 'unknown')}")
                elif info.get('warning'):
                    WARNINGS.append(f"{name}: {info['warning']}")

        # DB writable
        db_w = checks.get('db_writable', {})
        if db_w.get('ok'):
            print("   DB writable: OK")
        else:
            print(f"   DB writable: FAILED — {db_w.get('error')}")

        # Scraper freshness
        sf = checks.get('scraper_freshness', {})
        if sf.get('sources'):
            for src, sdata in sf['sources'].items():
                status_icon = "OK" if sdata.get('fresh') else "STALE"
                print(f"   {src}: {status_icon} (last: {sdata.get('latest', 'unknown')[:19]})")

        # Counts
        for table in ['obituaries', 'vendors', 'subscribers']:
            info = checks.get(table, {})
            if info.get('count') is not None:
                print(f"   {table}: {info['count']}")
    else:
        print("   FAILED to reach health endpoint")

    # 2. Obituary feed
    print("\n2. Obituary Feed...")
    obits = check("Obituaries", f"{BASE_URL}/api/obituaries")
    if obits:
        obit_list = obits if isinstance(obits, list) else obits.get('obituaries', obits.get('data', []))
        print(f"   Total: {len(obit_list)}")

        # Check freshness per source
        from collections import Counter
        sources = Counter(o.get('source', 'unknown') for o in obit_list)
        for src, count in sources.most_common():
            print(f"   {src}: {count}")

        # Check most recent
        if obit_list:
            latest = max(obit_list, key=lambda x: x.get('scraped_at', '') or '')
            latest_time = latest.get('scraped_at', 'unknown')
            print(f"   Most recent scrape: {latest_time}")

            if latest_time and latest_time != 'unknown':
                try:
                    lt = datetime.fromisoformat(latest_time.replace('Z', '+00:00').split('+')[0])
                    hours_ago = (datetime.now() - lt).total_seconds() / 3600
                    if hours_ago > 3:
                        ISSUES.append(f"Scrapers stale: most recent data is {hours_ago:.1f}h old")
                except Exception:
                    pass

    # 3. Directory stats
    print("\n3. Directory Stats...")
    stats = check("Stats", f"{BASE_URL}/api/directory-stats")
    if stats and stats.get('data'):
        d = stats['data']
        print(f"   Obituaries: {d.get('obituary_count', 0)}")
        print(f"   Active shivas: {d.get('active_shiva_count', 0)}")
        print(f"   Caterers: {d.get('caterer_count', 0)}")

    # 4. Gift vendors
    print("\n4. Gift Vendors...")
    gifts = check("Gifts", f"{BASE_URL}/api/gift-vendors")
    if gifts and gifts.get('data') is not None:
        print(f"   Gift vendors from DB: {len(gifts['data'])}")

    # 5. Caterers
    print("\n5. Caterers...")
    caterers = check("Caterers", f"{BASE_URL}/api/caterers")
    if caterers and caterers.get('data') is not None:
        print(f"   Approved caterers: {len(caterers['data'])}")

    # 6. Compare Benjamin's website vs our data
    print("\n6. Benjamin's Coverage Check...")
    try:
        req = Request("https://benjaminsparkmemorialchapel.ca/Home.aspx",
                       headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='ignore')
        import re
        service_links = set(re.findall(r'ServiceDetails\.aspx\?snum=(\d+)', html))
        print(f"   Benjamin's website: {len(service_links)} current listings")

        if obits:
            obit_list = obits if isinstance(obits, list) else obits.get('obituaries', obits.get('data', []))
            benjamins = [o for o in obit_list if 'benjamin' in o.get('source', '').lower()]
            print(f"   Neshama has: {len(benjamins)} Benjamin's records")
            if len(service_links) > 0 and len(benjamins) == 0:
                ISSUES.append("Benjamin's scraper appears broken — 0 records but website has listings")
    except Exception as e:
        WARNINGS.append(f"Benjamin's check failed: {e}")

    # Summary
    print(f"\n{'='*60}")
    if ISSUES:
        print(f"  ISSUES FOUND: {len(ISSUES)}")
        for i in ISSUES:
            print(f"  [!] {i}")
    if WARNINGS:
        print(f"\n  WARNINGS: {len(WARNINGS)}")
        for w in WARNINGS:
            print(f"  [?] {w}")
    if not ISSUES and not WARNINGS:
        print("  ALL SYSTEMS HEALTHY")
    print(f"{'='*60}\n")

    return 1 if ISSUES else 0


if __name__ == '__main__':
    sys.exit(main())
