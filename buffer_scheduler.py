#!/usr/bin/env python3
"""
Neshama Buffer Scheduler — Batch-schedule Instagram posts
==========================================================
Reads posts from a JSON file and schedules them via Buffer's API.

Requirements:
    pip install requests

Setup:
    1. Get your Buffer access token: https://bufferapp.com/developers/apps
    2. Set: export BUFFER_ACCESS_TOKEN=your_token_here
    3. Find your profile ID: python buffer_scheduler.py --list-profiles

Usage:
    python buffer_scheduler.py                          # Schedule all posts from posts_to_schedule.json
    python buffer_scheduler.py --file my_posts.json     # Schedule from a custom file
    python buffer_scheduler.py --dry-run                # Preview without scheduling
    python buffer_scheduler.py --list-profiles          # Show your Buffer profile IDs
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────

BUFFER_API_BASE = "https://api.bufferapp.com/1"
DEFAULT_POSTS_FILE = "posts_to_schedule.json"
LOG_FILE = "buffer_schedule_log.json"
RATE_LIMIT_DELAY = 1.1  # seconds between API calls (Buffer: 10 req/10 sec)
MAX_POSTS = 40

# ── API Helpers ──────────────────────────────────────────────

def get_token():
    """Get Buffer access token from environment."""
    token = os.environ.get("BUFFER_ACCESS_TOKEN", "").strip()
    if not token:
        print("Error: BUFFER_ACCESS_TOKEN environment variable not set.")
        print("Get your token at: https://bufferapp.com/developers/apps")
        print("Then run: export BUFFER_ACCESS_TOKEN=your_token_here")
        sys.exit(1)
    return token


def api_get(endpoint, token):
    """Make authenticated GET request to Buffer API."""
    url = f"{BUFFER_API_BASE}{endpoint}"
    resp = requests.get(url, params={"access_token": token}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_post(endpoint, token, data):
    """Make authenticated POST request to Buffer API."""
    url = f"{BUFFER_API_BASE}{endpoint}"
    data["access_token"] = token
    resp = requests.post(url, data=data, timeout=30)
    return resp.status_code, resp.json()


# ── Profile Management ──────────────────────────────────────

def list_profiles(token):
    """List all Buffer profiles (social accounts)."""
    profiles = api_get("/profiles.json", token)
    print(f"\n{'='*50}")
    print("  Your Buffer Profiles")
    print(f"{'='*50}\n")
    for p in profiles:
        status = "✅ active" if not p.get("paused") else "⏸ paused"
        print(f"  {p['service']:12} | {p.get('formatted_username', p.get('service_username', 'N/A'))}")
        print(f"  {'':12} | ID: {p['id']}")
        print(f"  {'':12} | Status: {status}")
        print()
    return profiles


# ── Post Validation ──────────────────────────────────────────

def validate_posts(posts):
    """Validate all posts before scheduling any."""
    errors = []
    warnings = []

    if not posts:
        errors.append("No posts found in file")
        return errors, warnings

    if len(posts) > MAX_POSTS:
        errors.append(f"Too many posts: {len(posts)} (max {MAX_POSTS})")

    for i, post in enumerate(posts, 1):
        label = f"Post {i}"

        # Required: text
        if not post.get("text", "").strip():
            errors.append(f"{label}: missing 'text' (caption)")

        # Required: profile_ids
        pids = post.get("profile_ids", [])
        if not pids:
            errors.append(f"{label}: missing 'profile_ids' (Buffer profile ID)")

        # Optional: scheduled_at
        sched = post.get("scheduled_at", "")
        if sched and sched != "next_slot":
            try:
                dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
                if dt < datetime.now(timezone.utc):
                    warnings.append(f"{label}: scheduled_at is in the past ({sched})")
            except ValueError:
                errors.append(f"{label}: invalid scheduled_at format '{sched}' (use ISO 8601)")

        # Optional: media
        media = post.get("media", [])
        if media:
            for j, m in enumerate(media):
                if isinstance(m, str):
                    # URL or file path
                    if not m.startswith("http") and not os.path.exists(m):
                        warnings.append(f"{label}: media[{j}] file not found: {m}")
                elif isinstance(m, dict):
                    if "link" not in m and "photo" not in m:
                        warnings.append(f"{label}: media[{j}] needs 'link' or 'photo' key")

        # Caption length check (Instagram: 2200 chars)
        text = post.get("text", "")
        if len(text) > 2200:
            warnings.append(f"{label}: caption is {len(text)} chars (Instagram max: 2200)")

    return errors, warnings


# ── Scheduling ───────────────────────────────────────────────

def schedule_post(token, post, dry_run=False):
    """Schedule a single post via Buffer API."""
    text = post["text"]
    profile_ids = post.get("profile_ids", [])
    scheduled_at = post.get("scheduled_at", "")
    media = post.get("media", [])

    # Build request data
    data = {"text": text, "now": False}

    # Profile IDs
    for pid in profile_ids:
        data.setdefault("profile_ids[]", []).append(pid)

    # Schedule time
    if scheduled_at == "next_slot":
        data["now"] = False  # Buffer auto-assigns next slot
    elif scheduled_at:
        data["scheduled_at"] = scheduled_at

    # Media (photos/links)
    for m in media:
        if isinstance(m, str):
            if m.startswith("http"):
                data["media[photo]"] = m
            # Local files would need uploading — Buffer API supports URLs
        elif isinstance(m, dict):
            if "photo" in m:
                data["media[photo]"] = m["photo"]
            if "link" in m:
                data["media[link]"] = m["link"]
            if "description" in m:
                data["media[description]"] = m["description"]

    if dry_run:
        return 200, {
            "success": True,
            "dry_run": True,
            "message": f"Would schedule: {text[:60]}..."
        }

    status_code, resp = api_post("/updates/create.json", token, data)
    return status_code, resp


def run_scheduler(posts_file, dry_run=False):
    """Main scheduling loop."""
    token = get_token()

    # Load posts
    if not os.path.exists(posts_file):
        print(f"Error: Posts file not found: {posts_file}")
        print(f"Create it from the sample: cp posts_to_schedule_sample.json {posts_file}")
        sys.exit(1)

    with open(posts_file, "r") as f:
        posts = json.load(f)

    if isinstance(posts, dict) and "posts" in posts:
        posts = posts["posts"]

    print(f"\n{'='*60}")
    print(f"  NESHAMA BUFFER SCHEDULER")
    print(f"  Posts file: {posts_file}")
    print(f"  Posts found: {len(posts)}")
    print(f"  Mode: {'DRY RUN (no posts will be sent)' if dry_run else 'LIVE'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Validate
    errors, warnings = validate_posts(posts)

    if warnings:
        print("⚠️  Warnings:")
        for w in warnings:
            print(f"   {w}")
        print()

    if errors:
        print("❌ Validation errors (must fix before scheduling):")
        for e in errors:
            print(f"   {e}")
        print("\nAborted. Fix errors and try again.")
        sys.exit(1)

    # Preview
    print("📋 Schedule Preview:")
    print(f"{'─'*50}")
    for i, post in enumerate(posts, 1):
        text_preview = post["text"][:65].replace("\n", " ")
        sched = post.get("scheduled_at", "next slot")
        print(f"  {i:2}. {text_preview}...")
        print(f"      → {sched}")
    print(f"{'─'*50}\n")

    if not dry_run:
        print("Starting in 3 seconds... (Ctrl+C to cancel)")
        time.sleep(3)

    # Schedule each post
    results = []
    scheduled = 0
    failed = 0
    skipped = 0

    for i, post in enumerate(posts, 1):
        text_preview = post["text"][:50].replace("\n", " ")
        print(f"  [{i}/{len(posts)}] {text_preview}...", end=" ")

        try:
            status_code, resp = schedule_post(token, post, dry_run=dry_run)

            if dry_run:
                print("✅ (dry run)")
                scheduled += 1
                results.append({
                    "index": i,
                    "status": "dry_run",
                    "text_preview": text_preview,
                    "scheduled_at": post.get("scheduled_at", "next_slot")
                })
            elif resp.get("success"):
                update = resp.get("updates", [{}])[0] if resp.get("updates") else resp.get("update", {})
                due = update.get("due_at", "queued")
                print(f"✅ scheduled → {due}")
                scheduled += 1
                results.append({
                    "index": i,
                    "status": "scheduled",
                    "buffer_id": update.get("id"),
                    "due_at": due,
                    "text_preview": text_preview
                })
            else:
                msg = resp.get("message", "Unknown error")
                print(f"❌ {msg}")
                failed += 1
                results.append({
                    "index": i,
                    "status": "failed",
                    "error": msg,
                    "text_preview": text_preview
                })

        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            failed += 1
            results.append({
                "index": i,
                "status": "error",
                "error": str(e),
                "text_preview": text_preview
            })

        except Exception as e:
            print(f"❌ Error: {e}")
            failed += 1
            results.append({
                "index": i,
                "status": "error",
                "error": str(e),
                "text_preview": text_preview
            })

        # Rate limiting
        if i < len(posts):
            time.sleep(RATE_LIMIT_DELAY)

    # Summary
    print(f"\n{'='*60}")
    if failed == 0:
        print(f"  ✅ ALL {scheduled} POSTS {'PREVIEWED' if dry_run else 'SCHEDULED'}")
    else:
        print(f"  📊 {scheduled} scheduled, {failed} failed, {skipped} skipped")
    print(f"{'='*60}\n")

    # Save log
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "posts_file": posts_file,
        "dry_run": dry_run,
        "total": len(posts),
        "scheduled": scheduled,
        "failed": failed,
        "results": results
    }

    log_data = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                log_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            log_data = []

    log_data.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)

    print(f"📝 Log saved to {LOG_FILE}")

    return 0 if failed == 0 else 1


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Neshama Buffer Scheduler — batch-schedule Instagram posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python buffer_scheduler.py --dry-run              Preview what would be posted
    python buffer_scheduler.py                        Schedule all posts (live)
    python buffer_scheduler.py --file week2.json      Use a custom posts file
    python buffer_scheduler.py --list-profiles        Show your Buffer profile IDs

Environment:
    BUFFER_ACCESS_TOKEN    Your Buffer API access token (required)
        """
    )
    parser.add_argument("--file", type=str, default=DEFAULT_POSTS_FILE,
                        help=f"Posts JSON file (default: {DEFAULT_POSTS_FILE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without actually scheduling")
    parser.add_argument("--list-profiles", action="store_true",
                        help="List your Buffer profiles and IDs")

    args = parser.parse_args()

    if args.list_profiles:
        token = get_token()
        list_profiles(token)
        sys.exit(0)

    exit_code = run_scheduler(args.file, dry_run=args.dry_run)
    sys.exit(exit_code)
