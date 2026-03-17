#!/usr/bin/env python3
"""
Neshama Smoke Test — Run after every deploy
============================================
Tests all critical endpoints, flows, and subsystems.
Exits with code 0 if all pass, 1 if any fail.

Usage:
    python smoke_test.py                    # Test production (neshama.ca)
    python smoke_test.py --local            # Test local (localhost:8000)
    python smoke_test.py --url https://...  # Test custom URL
"""

import sys
import json
import time
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

# ── Config ──────────────────────────────────────────────────

PROD_URL = "https://neshama.ca"
LOCAL_URL = "http://localhost:8000"

# Pages that MUST return 200
CRITICAL_PAGES = [
    "/",
    "/feed",
    "/directory",
    "/gifts",
    "/about",
    "/faq",
    "/privacy",
    "/shiva/organize",
    "/shiva/caterers",
    "/shiva/caterers/apply",
    "/shiva-essentials",
    "/what-to-bring-to-a-shiva",
    "/how-to-sit-shiva",
    "/what-is-yahrzeit",
    "/kosher-shiva-food",
    "/jewish-funeral-etiquette",
    "/condolence-messages",
    "/shiva-preparation-checklist",
    "/yahrzeit",
    "/find-my-page",
    "/dashboard",
    "/sustain",
    "/premium",
    "/gifts/plant-a-tree",
    "/sitemap.xml",
    "/robots.txt",
]

# API endpoints that MUST return 200 with valid JSON
API_ENDPOINTS = [
    "/api/health",
    "/api/obituaries",
    "/api/status",
    "/api/vendors",
    "/api/gift-vendors",
    "/api/caterers",
    "/api/community-stats",
    "/api/directory-stats",
    "/api/referral-stats",
    "/api/subscribers/count",
    "/api/tributes/counts",
]

# ── Helpers ─────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


def fetch(url, timeout=15):
    """Fetch URL, return (status_code, body, error)."""
    try:
        req = Request(url, headers={"User-Agent": "NeshamaSmokeTest/1.0"})
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body, None
    except HTTPError as e:
        return e.code, None, str(e)
    except URLError as e:
        return 0, None, str(e)
    except Exception as e:
        return 0, None, str(e)


def post_json(url, data, timeout=15):
    """POST JSON to URL, return (status_code, body, error)."""
    try:
        payload = json.dumps(data).encode("utf-8")
        req = Request(url, data=payload, headers={
            "User-Agent": "NeshamaSmokeTest/1.0",
            "Content-Type": "application/json",
        })
        resp = urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body, None
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else None
        return e.code, body, str(e)
    except Exception as e:
        return 0, None, str(e)


# ── Test Functions ──────────────────────────────────────────

def test_pages(base_url):
    """Test all critical pages return 200."""
    results = []
    for page in CRITICAL_PAGES:
        status, body, err = fetch(f"{base_url}{page}")
        ok = status == 200
        results.append({
            "test": f"GET {page}",
            "ok": ok,
            "status": status,
            "detail": err if not ok else f"{len(body)} bytes",
        })
    return results


def test_apis(base_url):
    """Test all API endpoints return 200 with valid JSON."""
    results = []
    for endpoint in API_ENDPOINTS:
        status, body, err = fetch(f"{base_url}{endpoint}")
        ok = status == 200
        json_ok = False
        detail = err or ""

        if ok and body:
            try:
                data = json.loads(body)
                json_ok = True
                # Extra validation for health endpoint
                if endpoint == "/api/health":
                    checks = data.get("checks", {})
                    failed = [k for k, v in checks.items() if not v.get("ok", False)]
                    if failed:
                        detail = f"Degraded: {', '.join(failed)}"
                    else:
                        detail = f"All systems OK"
                else:
                    detail = "Valid JSON"
            except json.JSONDecodeError:
                detail = "Invalid JSON response"
                ok = False

        results.append({
            "test": f"API {endpoint}",
            "ok": ok and json_ok,
            "status": status,
            "detail": detail,
        })
    return results


def test_health_subsystems(base_url):
    """Deep check on /api/health subsystem statuses."""
    results = []
    status, body, err = fetch(f"{base_url}/api/health")

    if status != 200 or not body:
        results.append({
            "test": "Health subsystems",
            "ok": False,
            "status": status,
            "detail": err or "No response",
        })
        return results

    try:
        data = json.loads(body)
        checks = data.get("checks", {})

        for system, info in checks.items():
            is_ok = info.get("ok", False)
            detail_parts = []
            if "count" in info:
                detail_parts.append(f"count={info['count']}")
            if "warning" in info:
                detail_parts.append(info["warning"])
            if "error" in info:
                detail_parts.append(info["error"])
            if "sendgrid_connected" in info:
                detail_parts.append(f"sendgrid={'yes' if info['sendgrid_connected'] else 'NO'}")
            if "missing" in info:
                detail_parts.append(f"missing={info['missing']}")

            results.append({
                "test": f"  ↳ {system}",
                "ok": is_ok,
                "status": "OK" if is_ok else "FAIL",
                "detail": ", ".join(str(p) for p in detail_parts if p is not None) if detail_parts else "",
            })

    except json.JSONDecodeError:
        results.append({
            "test": "Health JSON parse",
            "ok": False,
            "status": status,
            "detail": "Invalid JSON",
        })

    return results


def test_email_subscribe_flow(base_url):
    """Test email subscription API accepts a request (won't send real email in test)."""
    results = []

    # Test subscribe endpoint (consent required by CASL)
    status, body, err = post_json(f"{base_url}/api/subscribe", {
        "email": f"smoketest+{int(time.time())}@neshama.ca",
        "frequency": "daily",
        "locations": "toronto",
        "consent": True
    })

    ok = status == 200
    detail = err or ""
    if ok and body:
        try:
            data = json.loads(body)
            detail = data.get("message", "OK")
        except json.JSONDecodeError:
            detail = "Invalid JSON"
            ok = False

    results.append({
        "test": "POST /api/subscribe",
        "ok": ok,
        "status": status,
        "detail": detail,
    })

    return results


def test_confirm_route(base_url):
    """Test /confirm/ route returns a page (even if token is invalid)."""
    results = []
    status, body, err = fetch(f"{base_url}/confirm/test-invalid-token-smoke-test")

    # Should return 200 with an error page (not a 404 or 500)
    ok = status == 200 and body and "Confirmation" in body
    results.append({
        "test": "GET /confirm/{token} (invalid token)",
        "ok": ok,
        "status": status,
        "detail": "Returns confirmation page" if ok else (err or "Unexpected response"),
    })
    return results


def test_shiva_flow(base_url):
    """Test shiva page serving works."""
    results = []

    # The feed should have at least some obituaries
    status, body, err = fetch(f"{base_url}/api/obituaries")
    if status == 200 and body:
        try:
            data = json.loads(body)
            # API returns {status, data: [...], meta: {total: N}}
            if isinstance(data, dict) and "data" in data:
                obit_count = len(data["data"])
            elif isinstance(data, list):
                obit_count = len(data)
            else:
                obit_count = data.get("meta", {}).get("total", 0)
            results.append({
                "test": "Obituary feed data",
                "ok": obit_count > 0,
                "status": status,
                "detail": f"{obit_count} obituaries",
            })
        except json.JSONDecodeError:
            results.append({
                "test": "Obituary feed data",
                "ok": False,
                "status": status,
                "detail": "Invalid JSON",
            })

    return results


def test_referral_tracking(base_url):
    """Test referral tracking endpoint."""
    results = []

    # POST a test referral
    status, body, err = post_json(f"{base_url}/api/track-referral", {
        "ref": "smoke-test",
        "page": "/smoke-test"
    })

    ok = status == 200
    results.append({
        "test": "POST /api/track-referral",
        "ok": ok,
        "status": status,
        "detail": "Tracked" if ok else (err or "Failed"),
    })

    return results


# ── Main ────────────────────────────────────────────────────

def run_all_tests(base_url):
    """Run all test suites and print results."""
    print(f"\n{'='*60}")
    print(f"  NESHAMA SMOKE TEST")
    print(f"  Target: {base_url}")
    print(f"  Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    all_results = []

    suites = [
        ("📄 Critical Pages", test_pages),
        ("🔌 API Endpoints", test_apis),
        ("🏥 Health Subsystems", test_health_subsystems),
        ("📧 Email Subscribe Flow", test_email_subscribe_flow),
        ("🔗 Confirm Route", test_confirm_route),
        ("📰 Obituary Data", test_shiva_flow),
        ("📊 Referral Tracking", test_referral_tracking),
    ]

    for suite_name, test_fn in suites:
        print(f"\n{suite_name}")
        print(f"{'-'*40}")
        results = test_fn(base_url)
        all_results.extend(results)

        for r in results:
            icon = PASS if r["ok"] else FAIL
            detail = f" — {r['detail']}" if r.get("detail") else ""
            status_str = f"[{r['status']}]" if isinstance(r["status"], int) else ""
            print(f"  {icon} {r['test']} {status_str}{detail}")

    # Summary
    passed = sum(1 for r in all_results if r["ok"])
    failed = sum(1 for r in all_results if not r["ok"])
    total = len(all_results)

    print(f"\n{'='*60}")
    if failed == 0:
        print(f"  {PASS} ALL {total} TESTS PASSED")
    else:
        print(f"  {FAIL} {failed} FAILED / {passed} passed / {total} total")
        print(f"\n  Failed tests:")
        for r in all_results:
            if not r["ok"]:
                print(f"    {FAIL} {r['test']} [{r['status']}] {r.get('detail', '')}")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Neshama smoke test")
    parser.add_argument("--local", action="store_true", help="Test localhost:8000")
    parser.add_argument("--url", type=str, help="Custom base URL")
    args = parser.parse_args()

    if args.url:
        base = args.url.rstrip("/")
    elif args.local:
        base = LOCAL_URL
    else:
        base = PROD_URL

    exit_code = run_all_tests(base)
    sys.exit(exit_code)
