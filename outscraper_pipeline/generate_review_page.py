#!/usr/bin/env python3
"""
Review Page Generator
=====================
Reads audit_image_candidates.json and emits a standalone review.html
that Jordana opens in a browser. No server, no internet API needed
(except for loading the vendor photos themselves).

For each vendor, picks best candidate set:
  - fallback_candidates if fallback_status == "ok"
  - else primary candidates

Output: outscraper_pipeline/review.html

Usage:
  python3 outscraper_pipeline/generate_review_page.py
  open outscraper_pipeline/review.html
"""

import json
import os
import html as html_lib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "audit_image_candidates.json")
OUT_PATH = os.path.join(SCRIPT_DIR, "review.html")


def pick_candidates(r: dict) -> tuple[list, str]:
    """Return (candidates, source_url_used)."""
    fb = r.get("fallback_candidates") or []
    if fb and r.get("fallback_status") == "ok":
        return fb, r.get("fallback_url", "")
    return r.get("candidates", []), r.get("source_url", "")


def main():
    with open(JSON_PATH) as f:
        data = json.load(f)

    review_rows = []
    for r in data["results"]:
        candidates, used_url = pick_candidates(r)
        review_rows.append({
            "vendor_name": r["vendor_name"],
            "city": r.get("city", ""),
            "city_corrected": r.get("city_corrected", False),
            "city_original": r.get("city_original"),
            "source_url": used_url,
            "candidates": [c["url"] for c in candidates],
            "has_any": len(candidates) > 0,
        })

    review_rows.sort(key=lambda r: (not r["has_any"], r["city"], r["vendor_name"]))

    total = len(review_rows)
    with_cand = sum(1 for r in review_rows if r["has_any"])
    without = total - with_cand

    data_json = json.dumps(review_rows, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Neshama Vendor Photo Review — Jordana</title>
<style>
  :root {{
    --cream: #FFF8F0;
    --terracotta: #D2691E;
    --brown: #3E2723;
    --sage: #8A9A5B;
    --border: #E8DDD0;
    --pick: #2E7D32;
    --reject: #C62828;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--cream);
    color: var(--brown);
    margin: 0;
    padding: 0 16px 120px;
    line-height: 1.5;
  }}
  header {{
    position: sticky;
    top: 0;
    background: var(--cream);
    padding: 16px 0 12px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 16px;
    z-index: 100;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px; color: var(--terracotta); }}
  .sub {{ font-size: 14px; color: var(--brown); opacity: 0.7; }}
  .progress {{
    font-size: 14px;
    margin-top: 8px;
    font-weight: 600;
  }}
  .progress-bar {{
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
    margin-top: 4px;
  }}
  .progress-fill {{
    height: 100%;
    background: var(--sage);
    transition: width 0.3s;
  }}
  button.primary {{
    background: var(--terracotta);
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 8px;
  }}
  button.primary:hover {{ opacity: 0.9; }}

  .vendor {{
    background: white;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 14px;
  }}
  .vendor h2 {{
    font-size: 17px;
    margin: 0 0 2px;
    color: var(--brown);
  }}
  .meta {{
    font-size: 13px;
    color: #666;
    margin-bottom: 10px;
  }}
  .meta a {{ color: var(--terracotta); text-decoration: none; }}
  .meta a:hover {{ text-decoration: underline; }}
  .city-fix {{
    display: inline-block;
    background: #FFF3E0;
    color: #E65100;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 6px;
    font-weight: 600;
  }}

  .candidates {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 10px;
  }}
  .candidate {{
    border: 2px solid var(--border);
    border-radius: 8px;
    padding: 6px;
    cursor: pointer;
    transition: all 0.15s;
    background: var(--cream);
  }}
  .candidate:hover {{ border-color: var(--sage); }}
  .candidate.picked {{
    border-color: var(--pick);
    background: #E8F5E9;
    box-shadow: 0 0 0 2px var(--pick);
  }}
  .candidate img {{
    width: 100%;
    height: 140px;
    object-fit: cover;
    border-radius: 4px;
    background: #f0f0f0;
    display: block;
  }}
  .candidate .lbl {{
    font-size: 11px;
    color: #666;
    margin-top: 4px;
    text-align: center;
  }}
  .none-option {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    font-size: 14px;
    padding: 8px 10px;
    border: 1px dashed var(--border);
    border-radius: 6px;
    cursor: pointer;
  }}
  .none-option.picked {{
    background: #FFEBEE;
    border-color: var(--reject);
    border-style: solid;
  }}
  .none-option input {{ margin: 0; }}
  .no-cand {{
    background: #FFF3E0;
    border-left: 4px solid #E65100;
    padding: 10px 12px;
    border-radius: 4px;
    font-size: 14px;
    margin: 8px 0;
  }}
  textarea.notes {{
    width: 100%;
    margin-top: 10px;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
    min-height: 40px;
  }}

  footer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    border-top: 2px solid var(--border);
    padding: 12px 16px;
    display: flex;
    gap: 10px;
    align-items: center;
    justify-content: space-between;
    z-index: 100;
  }}
  .status {{
    font-size: 13px;
    color: #666;
  }}
</style>
</head>
<body>

<header>
  <h1>Vendor Photo Review</h1>
  <div class="sub">
    {total} vendors · {with_cand} with photo options · {without} need new source
  </div>
  <div class="progress">
    <span id="progress-text">0 / {total} reviewed</span>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width:0%"></div></div>
  </div>
</header>

<main id="vendors"></main>

<footer>
  <span class="status" id="status">Picks auto-save to your browser. Safe to close and come back.</span>
  <button class="primary" onclick="exportCSV()">Export picks as CSV</button>
</footer>

<script>
const DATA = {data_json};
const STORAGE_KEY = 'jordana-vendor-picks-v1';
const picks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');

function savePicks() {{
  localStorage.setItem(STORAGE_KEY, JSON.stringify(picks));
  updateProgress();
}}

function updateProgress() {{
  const total = DATA.length;
  const done = Object.keys(picks).filter(k => picks[k] && picks[k].choice !== undefined).length;
  document.getElementById('progress-text').textContent = done + ' / ' + total + ' reviewed';
  document.getElementById('progress-fill').style.width = (done / total * 100) + '%';
}}

function pickImage(vendorName, index) {{
  picks[vendorName] = picks[vendorName] || {{}};
  picks[vendorName].choice = index;
  picks[vendorName].picked_url = DATA.find(v => v.vendor_name === vendorName).candidates[index] || '';
  savePicks();
  render();
}}

function pickNone(vendorName) {{
  picks[vendorName] = picks[vendorName] || {{}};
  picks[vendorName].choice = 'none';
  picks[vendorName].picked_url = '';
  savePicks();
  render();
}}

function updateNote(vendorName, note) {{
  picks[vendorName] = picks[vendorName] || {{}};
  picks[vendorName].note = note;
  savePicks();
}}

function escapeHTML(s) {{
  return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

function render() {{
  const container = document.getElementById('vendors');
  container.innerHTML = DATA.map(v => {{
    const p = picks[v.vendor_name] || {{}};
    const cityFix = v.city_corrected
      ? `<span class="city-fix">CITY FIX: ${{escapeHTML(v.city_original)}} → ${{escapeHTML(v.city)}}</span>`
      : '';

    let body;
    if (!v.has_any) {{
      body = `<div class="no-cand">⚠️ No usable candidates found. You'll need to source a new photo manually.</div>`;
    }} else {{
      const cards = v.candidates.map((url, i) => {{
        const picked = p.choice === i ? ' picked' : '';
        return `<div class="candidate${{picked}}" onclick="pickImage(${{escapeHTML(JSON.stringify(v.vendor_name))}}, ${{i}})">
          <img src="${{escapeHTML(url)}}" alt="candidate ${{i+1}}" loading="lazy" onerror="this.style.background='#fde';this.alt='(image failed to load)'">
          <div class="lbl">Option ${{i+1}}</div>
        </div>`;
      }}).join('');
      body = `<div class="candidates">${{cards}}</div>`;
    }}

    const nonePicked = p.choice === 'none' ? ' picked' : '';
    const noneLabel = v.has_any
      ? 'None of these work — need a new photo'
      : 'Confirmed — need to source manually';

    return `<div class="vendor">
      <h2>${{escapeHTML(v.vendor_name)}}${{cityFix}}</h2>
      <div class="meta">
        ${{escapeHTML(v.city)}}
        ${{v.source_url ? ` · <a href="${{escapeHTML(v.source_url)}}" target="_blank" rel="noopener">source page ↗</a>` : ''}}
      </div>
      ${{body}}
      <label class="none-option${{nonePicked}}">
        <input type="checkbox" ${{p.choice === 'none' ? 'checked' : ''}} onchange="pickNone(${{escapeHTML(JSON.stringify(v.vendor_name))}})">
        <span>${{noneLabel}}</span>
      </label>
      <textarea class="notes" placeholder="Optional note (e.g. 'logo only', 'wrong vendor')..." onchange="updateNote(${{escapeHTML(JSON.stringify(v.vendor_name))}}, this.value)">${{escapeHTML(p.note || '')}}</textarea>
    </div>`;
  }}).join('');
  updateProgress();
}}

function exportCSV() {{
  const rows = [['Vendor Name', 'City', 'City Corrected', 'Choice', 'Picked URL', 'Source Page', 'Note']];
  DATA.forEach(v => {{
    const p = picks[v.vendor_name] || {{}};
    let choiceLabel = '';
    if (p.choice === 'none') choiceLabel = 'NEEDS NEW SOURCE';
    else if (typeof p.choice === 'number') choiceLabel = 'Option ' + (p.choice + 1);
    rows.push([
      v.vendor_name,
      v.city,
      v.city_corrected ? 'YES (was ' + v.city_original + ')' : '',
      choiceLabel,
      p.picked_url || '',
      v.source_url || '',
      p.note || '',
    ]);
  }});
  const csv = rows.map(r => r.map(c => {{
    const s = String(c ?? '');
    return /[",\\n]/.test(s) ? `"${{s.replace(/"/g, '""')}}"` : s;
  }}).join(',')).join('\\n');
  const blob = new Blob([csv], {{type: 'text/csv;charset=utf-8;'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const ts = new Date().toISOString().slice(0,10);
  a.download = `vendor-photo-picks-${{ts}}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}}

render();
</script>

</body>
</html>
"""

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated: {OUT_PATH}")
    print(f"  Total vendors:      {total}")
    print(f"  With candidates:    {with_cand}")
    print(f"  Need new source:    {without}")
    print(f"\nOpen with: open {OUT_PATH}")


if __name__ == "__main__":
    main()
