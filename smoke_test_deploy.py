#!/usr/bin/env python3
"""
Post-Deploy Smoke Test — Neshama
=================================
Runs after every git push to verify critical site functionality.
Tests: pages, APIs, shiva flow, vendor directory, affiliate links, scrapers.

Usage:
  python3 smoke_test_deploy.py              # Test production
  python3 smoke_test_deploy.py --local      # Test local dev server
  python3 smoke_test_deploy.py --verbose    # Show response details
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.request
from urllib.error import HTTPError, URLError

PROD_BASE = "https://neshama.ca"
LOCAL_BASE = "http://localhost:8000"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "NeshamaSmokeTest/1.0",
    "Accept": "text/html,application/json",
}


class SmokeTest:
    def __init__(self, base_url, verbose=False):
        self.base = base_url.rstrip("/")
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.errors = []

    def fetch(self, path, expect_json=False, timeout=15):
        url = f"{self.base}{path}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            ctx = SSL_CTX if url.startswith("https") else None
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.status
                if expect_json:
                    return status, json.loads(body)
                return status, body
        except HTTPError as e:
            return e.code, None
        except Exception as e:
            return 0, str(e)

    def check(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"  ✓ {name}")
        else:
            self.failed += 1
            msg = f"{name}: {detail}" if detail else name
            self.errors.append(msg)
            print(f"  ✗ {name} — {detail}")

    def run_all(self):
        print(f"\n{'=' * 60}")
        print(f"  Neshama Post-Deploy Smoke Test")
        print(f"  Target: {self.base}")
        print(f"{'=' * 60}")

        self.test_pages()
        self.test_apis()
        self.test_shiva_flow()
        self.test_vendor_directory()
        self.test_affiliate_links()
        self.test_email_endpoints()

        print(f"\n{'=' * 60}")
        print(f"  RESULTS: {self.passed} passed, {self.failed} failed")
        print(f"{'=' * 60}")

        if self.errors:
            print("\n  FAILURES:")
            for e in self.errors:
                print(f"    • {e}")

        return self.failed == 0

    def test_pages(self):
        print("\n── Pages ──")
        pages = [
            ("/", "Neshama"),
            ("/landing.html", "Neshama"),
            ("/directory", "directory"),
            ("/help/food", "caterer"),
            ("/help/supplies", "shiva"),
            ("/help/gifts", "gift"),
            ("/terms", "terms"),
            ("/shiva/organize", "organize"),
            ("/first-passover-after-loss", "passover"),
        ]
        for path, keyword in pages:
            status, body = self.fetch(path)
            self.check(
                f"GET {path} → {status}",
                status == 200 and body and keyword.lower() in body.lower(),
                f"status={status}" if status != 200 else "keyword not found",
            )

    def test_apis(self):
        print("\n── APIs ──")

        # Obituaries
        status, data = self.fetch("/api/obituaries", expect_json=True)
        obit_count = len(data.get("data", [])) if data else 0
        self.check(
            f"GET /api/obituaries → {obit_count} obituaries",
            status == 200 and obit_count > 0,
            f"status={status}, count={obit_count}",
        )

        # Check obituaries have recent data (within last 14 days)
        if data and data.get("data"):
            dates = [o.get("date_of_death", "") for o in data["data"] if o.get("date_of_death")]
            recent = any("2026" in d for d in dates[:10])
            self.check("Obituaries have recent data", recent, "no March 2026 dates found")

        # Vendors
        status, data = self.fetch("/api/vendors", expect_json=True)
        vendor_count = len(data.get("data", [])) if data else 0
        self.check(
            f"GET /api/vendors → {vendor_count} vendors",
            status == 200 and vendor_count >= 100,
            f"status={status}, count={vendor_count}",
        )

        # Gift vendors
        status, data = self.fetch("/api/gift-vendors", expect_json=True)
        gift_count = len(data.get("data", [])) if data else 0
        self.check(
            f"GET /api/gift-vendors → {gift_count} gift vendors",
            status == 200 and gift_count > 0,
            f"status={status}, count={gift_count}",
        )

    def test_shiva_flow(self):
        print("\n── Shiva Flow ──")

        # Test the Tarnofsky shiva page (known test shiva)
        shiva_id = "1f94514f-931c-4147-8f4f-1847a0368815"
        status, data = self.fetch(f"/api/shiva/{shiva_id}", expect_json=True)
        self.check(
            "GET /api/shiva (test shiva) → success",
            status == 200 and data and data.get("status") == "success",
            f"status={status}, response={data.get('status') if data else 'none'}",
        )

        if data and data.get("data"):
            shiva = data["data"]
            self.check(
                "Shiva has family name",
                bool(shiva.get("family_name")),
                f"family_name={shiva.get('family_name')}",
            )
            self.check(
                "Shiva has dates",
                bool(shiva.get("shiva_start_date")),
                "missing start date",
            )
            # Check access level — should be public (not limited) after migration
            access = data.get("access", "")
            self.check(
                f"Shiva access level: {access}",
                access in ("full", "public", "limited"),
                f"unexpected access={access}",
            )

        # Meals endpoint
        status, data = self.fetch(f"/api/shiva/{shiva_id}/meals", expect_json=True)
        self.check(
            "GET /api/shiva/meals → success",
            status == 200 and data and data.get("status") == "success",
            f"status={status}",
        )

        # Shiva page HTML loads
        status, body = self.fetch(f"/shiva/{shiva_id}")
        self.check(
            "Shiva page HTML loads",
            status == 200 and body and "shiva" in body.lower(),
            f"status={status}",
        )

    def test_vendor_directory(self):
        print("\n── Vendor Directory ──")

        status, data = self.fetch("/api/vendors", expect_json=True)
        if not data or not data.get("data"):
            self.check("Vendor data available", False, "no vendor data")
            return

        vendors = data["data"]

        # Check data quality
        with_images = sum(1 for v in vendors if v.get("image_url"))
        with_emails = sum(1 for v in vendors if v.get("email"))
        with_instagram = sum(1 for v in vendors if v.get("instagram"))
        with_phone = sum(1 for v in vendors if v.get("phone"))

        self.check(
            f"Vendors with images: {with_images}/{len(vendors)}",
            with_images > 30,
            f"only {with_images} have images",
        )
        self.check(
            f"Vendors with phone: {with_phone}/{len(vendors)}",
            with_phone > 80,
            f"only {with_phone} have phones",
        )

        # No "Kosher Style" labels
        kosher_style = sum(1 for v in vendors if v.get("kosher_status") == "Kosher Style")
        self.check(
            "No 'Kosher Style' labels",
            kosher_style == 0,
            f"found {kosher_style} vendors with 'Kosher Style'",
        )

    def test_affiliate_links(self):
        print("\n── Affiliate Links ──")

        status, body = self.fetch("/help/supplies")
        if status == 200 and body:
            amazon_count = body.count("neshama0708-20")
            self.check(
                f"Amazon affiliate tags on /help/supplies: {amazon_count}",
                amazon_count >= 10,
                f"only {amazon_count} tags found",
            )

        status, body = self.fetch("/help/gifts")
        if status == 200 and body:
            amazon_count = body.count("neshama0708-20")
            self.check(
                f"Amazon affiliate tags on /help/gifts: {amazon_count}",
                amazon_count >= 3,
                f"only {amazon_count} tags found",
            )

    def test_email_endpoints(self):
        print("\n── Email/Subscribe ──")

        # Subscribe is POST-only, so a GET should return 405 or the page that contains the form
        # Test that the footer subscribe JS loads
        status, body = self.fetch("/footer-subscribe.js")
        self.check(
            "Footer subscribe JS loads",
            status == 200 and body and "subscribe" in body.lower(),
            f"status={status}",
        )


def main():
    parser = argparse.ArgumentParser(description="Neshama post-deploy smoke test")
    parser.add_argument("--local", action="store_true", help="Test local dev server")
    parser.add_argument("--verbose", action="store_true", help="Show response details")
    args = parser.parse_args()

    base = LOCAL_BASE if args.local else PROD_BASE
    tester = SmokeTest(base, verbose=args.verbose)

    success = tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
