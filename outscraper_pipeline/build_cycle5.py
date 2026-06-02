#!/usr/bin/env python3
"""
Cycle 5 review builder — Apr 30, 2026

Replaces the bad Firecrawl candidates from Cycle 4 with fresh ones sourced
via WebSearch (see cycle5-fallback-urls.json). Output is review-cycle5.html
that Erin or Jordana opens in Chrome.

Pipeline:
  cycle5-fallback-urls.json  →  Firecrawl scrape per vendor
                              →  cycle5-candidates.json
                              →  review-cycle5.html (with isolated localStorage key)

Usage:
  python3 outscraper_pipeline/build_cycle5.py --dry-run
  python3 outscraper_pipeline/build_cycle5.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from extract_audit_images import (  # type: ignore[import]
    DELAY_SECONDS,
    extract_from_result,
    rank_candidates,
    scrape_one,
)

FALLBACK_PATH = os.path.join(SCRIPT_DIR, "data", "cycle5-fallback-urls.json")
CANDIDATES_OUT = os.path.join(SCRIPT_DIR, "cycle5-candidates.json")
REVIEW_HTML_OUT = os.path.join(SCRIPT_DIR, "review-cycle5.html")
STORAGE_KEY = "jordana-vendor-picks-cycle5"


def load_firecrawl_key() -> str:
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if api_key:
        return api_key
    env_path = os.path.join(SCRIPT_DIR, ".firecrawl.env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            return fh.read().strip()
    return ""


def scrape_vendors(rows: list[dict], dry_run: bool) -> list[dict]:
    """Scrape each row's fallback_url via Firecrawl. Return enriched rows."""
    if dry_run:
        for r in rows:
            r["candidates"] = []
            r["status"] = "dry-run"
        return rows

    api_key = load_firecrawl_key()
    if not api_key:
        print("ERROR: no FIRECRAWL_API_KEY found.")
        sys.exit(2)

    try:
        from firecrawl import FirecrawlApp  # type: ignore[import]
    except ImportError:
        print("ERROR: pip3 install firecrawl-py")
        sys.exit(2)

    app = FirecrawlApp(api_key=api_key)
    n = len(rows)
    for i, r in enumerate(rows, 1):
        url = r.get("fallback_url")
        if not url:
            r["candidates"] = []
            r["status"] = "no_url"
            print(f"[{i}/{n}] {r['vendor_name']:35} -> SKIP (no url)")
            continue
        print(f"[{i}/{n}] {r['vendor_name']:35} -> {url[:60]}")
        result, err = scrape_one(app, url)
        if err:
            r["candidates"] = []
            r["status"] = "scrape_error"
            r["error"] = err
            print(f"        FAIL: {err}")
        else:
            og_image, html_imgs = extract_from_result(result, url)
            ranked = rank_candidates(og_image, html_imgs)
            r["candidates"] = ranked
            r["status"] = "ok" if ranked else "no_candidates"
            print(f"        {len(ranked)} candidate(s)")
        if i < n:
            time.sleep(DELAY_SECONDS)
    return rows


def build_cycle5_candidates_json(rows: list[dict]) -> dict:
    """Output shape compatible with cycle4-candidates.json."""
    stats = {
        "processed": len(rows),
        "ok": sum(1 for r in rows if r.get("status") == "ok"),
        "no_candidates": sum(1 for r in rows if r.get("status") == "no_candidates"),
        "no_url": sum(1 for r in rows if r.get("status") == "no_url"),
        "scrape_error": sum(1 for r in rows if r.get("status") == "scrape_error"),
        "credits_used": sum(1 for r in rows if r.get("status") in ("ok", "no_candidates", "scrape_error")),
    }
    results = []
    for r in rows:
        results.append({
            "vendor_name": r["vendor_name"],
            "city": r.get("city", ""),
            "city_corrected": False,
            "city_original": None,
            "source_url": r.get("fallback_url") or "",
            "url_type": r.get("fallback_type") or "website",
            "candidates": r.get("candidates", []),
            "has_any": bool(r.get("candidates")),
            "fallback_reasoning": r.get("source_reasoning"),
        })
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "csv_source": "data/cycle5-fallback-urls.json",
        "cycle": 5,
        "stats": stats,
        "results": results,
    }


def build_review_html(payload: dict) -> str:
    """Generate the standalone review HTML, modeled on review-cycle4.html."""
    review_rows = []
    for r in payload["results"]:
        review_rows.append({
            "vendor_name": r["vendor_name"],
            "city": r.get("city", ""),
            "source_url": r.get("source_url", ""),
            "candidates": [c["url"] if isinstance(c, dict) else c for c in r.get("candidates", [])],
            "has_any": r["has_any"],
            "reasoning": r.get("fallback_reasoning") or "",
        })
    review_rows.sort(key=lambda r: (not r["has_any"], r["city"], r["vendor_name"]))
    total = len(review_rows)
    with_cand = sum(1 for r in review_rows if r["has_any"])
    without = total - with_cand
    data_json = json.dumps(review_rows, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Neshama Vendor Photo Review — Cycle 5</title>
<style>
  :root {{
    --cream: #FFF8F0;
    --terracotta: #D2691E;
    --brown: #3E2723;
    --sage: #8A9A5B;
    --border: #E8DDD0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--cream);
    color: var(--brown);
    margin: 0;
    padding: 24px;
    font-size: 16px;
  }}
  header {{
    background: white;
    padding: 20px 24px;
    border-radius: 12px;
    border: 1px solid var(--border);
    position: sticky;
    top: 8px;
    z-index: 50;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    margin-bottom: 24px;
  }}
  header h1 {{ margin: 0 0 6px 0; font-size: 22px; color: var(--terracotta); }}
  header .stats {{ font-size: 14px; color: #6b5d4f; }}
  header button {{
    background: var(--terracotta);
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 8px;
    font-size: 15px;
    cursor: pointer;
    margin-top: 8px;
  }}
  header button:hover {{ background: #B85A18; }}
  .vendor {{
    background: white;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 16px;
  }}
  .vendor h2 {{ margin: 0 0 4px 0; font-size: 18px; color: var(--brown); }}
  .vendor .meta {{ font-size: 13px; color: #6b5d4f; margin-bottom: 10px; }}
  .vendor .meta a {{ color: var(--terracotta); text-decoration: none; }}
  .vendor .reasoning {{ font-size: 13px; font-style: italic; color: #6b5d4f; margin-bottom: 12px; }}
  .candidates {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 10px; }}
  .candidate {{
    border: 2px solid transparent;
    border-radius: 8px;
    cursor: pointer;
    overflow: hidden;
    background: #f4ede0;
    aspect-ratio: 1;
    position: relative;
  }}
  .candidate img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .candidate .label {{
    position: absolute; top: 6px; left: 6px;
    background: rgba(255,255,255,0.9);
    padding: 2px 8px; border-radius: 4px;
    font-size: 12px; font-weight: 600;
  }}
  .candidate.picked {{ border-color: #2E7D32; }}
  .candidate.picked::after {{
    content: '✓'; position: absolute; bottom: 6px; right: 6px;
    background: #2E7D32; color: white;
    width: 26px; height: 26px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: bold;
  }}
  .empty {{ font-size: 14px; color: #999; padding: 16px; text-align: center; background: #faf6ed; border-radius: 8px; }}
  textarea {{
    width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
    font-family: inherit; font-size: 14px; resize: vertical; min-height: 40px;
  }}
  .vendor.has-pick {{ border: 2px solid #2E7D32; background: #f4faf3; }}
  .custom-url-row {{ margin: 12px 0 8px 0; padding: 10px; background: #faf6ed; border-radius: 8px; }}
  .custom-url-row label {{ display: block; font-size: 13px; color: #6b5d4f; margin-bottom: 6px; }}
  input.custom-url {{
    width: 100%; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
    font-family: inherit; font-size: 14px;
  }}
  .custom-preview {{ margin-top: 8px; }}
  .custom-preview img {{ max-width: 200px; max-height: 200px; border-radius: 8px; border: 2px solid #2E7D32; }}
</style>
</head>
<body>
<header>
  <h1>Vendor Photo Review — Cycle 5</h1>
  <div class="stats">
    {total} vendors · {with_cand} with candidates · {without} need manual research<br>
    Click an image to pick it. Picks save to your browser. When done, click Export.
  </div>
  <button onclick="exportPicks()">Export Picks (CSV)</button>
</header>
<main id="content"></main>
<script>
const DATA = {data_json};
const STORAGE_KEY = '{STORAGE_KEY}';
const picks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');

function escapeHTML(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"}})[c]);
}}

function render() {{
  const main = document.getElementById('content');
  main.innerHTML = DATA.map((v, idx) => {{
    const candidatesHTML = v.candidates.length
      ? '<div class="candidates">' + v.candidates.map((url, i) => {{
          const id = 'cand-' + idx + '-' + i;
          const isPicked = picks[v.vendor_name] === url;
          return `
            <div class="candidate ${{isPicked ? 'picked' : ''}}" data-vendor="${{escapeHTML(v.vendor_name)}}" data-url="${{escapeHTML(url)}}">
              <span class="label">Option ${{i+1}}</span>
              <img src="${{escapeHTML(url)}}" alt="candidate ${{i+1}}" loading="lazy" onerror="this.style.background='#fde';this.alt='(image failed to load)'">
            </div>`;
        }}).join('') + '</div>'
      : '<div class="empty">No candidates from Firecrawl. Add a note below.</div>';
    const reasoning = v.reasoning ? `<div class="reasoning">${{escapeHTML(v.reasoning)}}</div>` : '';
    const note = (picks[v.vendor_name + '__note'] || '');
    const custom = (picks[v.vendor_name + '__custom'] || '');
    const hasPick = !!picks[v.vendor_name] || !!custom;
    return `
      <article class="vendor ${{hasPick ? 'has-pick' : ''}}">
        <h2>${{escapeHTML(v.vendor_name)}}</h2>
        <div class="meta">${{escapeHTML(v.city)}} · <a href="${{escapeHTML(v.source_url)}}" target="_blank">source</a></div>
        ${{reasoning}}
        ${{candidatesHTML}}
        <div class="custom-url-row">
          <label>Or paste your own image URL (overrides any clicked option above):</label>
          <input type="url" class="custom-url" data-vendor="${{escapeHTML(v.vendor_name)}}" placeholder="https://..." value="${{escapeHTML(custom)}}">
          ${{custom ? `<div class="custom-preview"><img src="${{escapeHTML(custom)}}" alt="custom preview" onerror="this.style.display='none'"></div>` : ''}}
        </div>
        <textarea data-vendor="${{escapeHTML(v.vendor_name)}}" placeholder="Notes (optional)">${{escapeHTML(note)}}</textarea>
      </article>`;
  }}).join('');
  document.querySelectorAll('.candidate').forEach(el => {{
    el.addEventListener('click', () => {{
      const v = el.dataset.vendor; const u = el.dataset.url;
      picks[v] = u;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(picks));
      render();
    }});
  }});
  document.querySelectorAll('textarea[data-vendor]').forEach(el => {{
    el.addEventListener('input', () => {{
      picks[el.dataset.vendor + '__note'] = el.value;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(picks));
    }});
  }});
  document.querySelectorAll('input.custom-url').forEach(el => {{
    el.addEventListener('input', () => {{
      const v = el.dataset.vendor;
      const url = el.value.trim();
      if (url) {{
        picks[v + '__custom'] = url;
      }} else {{
        delete picks[v + '__custom'];
      }}
      localStorage.setItem(STORAGE_KEY, JSON.stringify(picks));
    }});
    el.addEventListener('blur', () => {{ render(); }});
  }});
}}

function exportPicks() {{
  let csv = 'Vendor Name,City,Choice,Picked URL,Source Page,Note\\n';
  DATA.forEach(v => {{
    const custom = (picks[v.vendor_name + '__custom'] || '').trim();
    const candidatePick = picks[v.vendor_name] || '';
    const finalPick = custom || candidatePick;
    const note = (picks[v.vendor_name + '__note'] || '');
    let choice = 'NEEDS NEW SOURCE';
    if (custom) {{
      choice = 'Custom (pasted URL)';
    }} else if (candidatePick) {{
      const idx = v.candidates.indexOf(candidatePick);
      choice = idx >= 0 ? `Option ${{idx + 1}}` : 'Custom';
    }}
    const safe = s => `"${{String(s || '').replace(/"/g, '""')}}"`;
    csv += [safe(v.vendor_name), safe(v.city), safe(choice), safe(finalPick), safe(v.source_url), safe(note)].join(',') + '\\n';
  }});
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'vendor-photo-picks-cycle5-' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}}

render();
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip Firecrawl, just verify pipeline shape")
    args = parser.parse_args()

    if not os.path.exists(FALLBACK_PATH):
        print(f"ERROR: fallback URLs JSON not found: {FALLBACK_PATH}")
        sys.exit(2)

    with open(FALLBACK_PATH) as fh:
        fallback_data = json.load(fh)

    rows = fallback_data["results"]
    print(f"Loaded {len(rows)} vendors from cycle5-fallback-urls.json")
    print(f"  with fallback URL: {sum(1 for r in rows if r.get('fallback_url'))}")
    print(f"  null (need manual): {sum(1 for r in rows if not r.get('fallback_url'))}")

    rows = scrape_vendors(rows, dry_run=args.dry_run)
    payload = build_cycle5_candidates_json(rows)

    with open(CANDIDATES_OUT, "w") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {CANDIDATES_OUT}")
    print(f"  stats: {payload['stats']}")

    html = build_review_html(payload)
    with open(REVIEW_HTML_OUT, "w") as fh:
        fh.write(html)
    print(f"Wrote {REVIEW_HTML_OUT}")
    print(f"\nReview by running: open {REVIEW_HTML_OUT}")


if __name__ == "__main__":
    sys.exit(main() or 0)
