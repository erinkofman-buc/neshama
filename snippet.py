"""
Obituary snippet extraction via Anthropic Haiku.

Per HANDOFF-obituaries.md: extracts a 1-2 line "emotional pull" snippet from each
obituary text — family role, profession, community ties, passions, origin story.
The snippet appears on the obituary feed cards. It's what makes the feed feel alive
vs generic — scroll past a name+date and you keep scrolling; scroll past
"Holocaust survivor, matriarch of four generations, lover of klezmer music" and you stop.

Hard guardrails against invention. Never embellishes. Returns NULL for boilerplate obits.

Cost: ~$1 to backfill ~500 existing obits, well under $1/month for new obits at
~10-30/day scrape volume.

Setup: requires ANTHROPIC_API_KEY in env (or .env file at project root).
"""

import os
import logging

# Load .env if present (project-local secrets, NOT committed to git per .gitignore)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed — fall back to plain os.environ
    pass

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None  # Allow module import without anthropic installed (for tests/CI)

logger = logging.getLogger(__name__)

# Haiku 4.5 — best speed/cost for single-shot extraction.
# Per the claude-api skill: use the alias form, not the date-suffixed full ID.
MODEL = "claude-haiku-4-5"

# Single-shot extraction — no prompt caching. Each obit is a unique input,
# the static prompt template is ~80 tokens (well under Haiku's 4096-token cache
# minimum), so cache_control would write a per-obit entry that's never read.
PROMPT = """From the obituary below, extract 1-2 short phrases (max 120 characters total) that capture who this person was — family role, profession, community ties, passions, or origin story.

Rules:
- Extract only. Do NOT invent, embellish, or infer.
- Do NOT include the person's name, age, dates, or funeral details.
- Do NOT add "beloved" or "loving" unless the original obituary uses them.
- Keep it plain and specific. "Retired teacher at Bialik Hebrew Day School" beats "educator."
- If the obituary contains nothing compelling beyond boilerplate, return exactly: NULL

Return the snippet alone. No quotes, no preamble, no trailing punctuation beyond a period.

Obituary:
---
{obituary_text}
---"""

# Trim long obits to keep token cost trivial. Real obits rarely have meaningful new
# content past 4000 chars — by then it's funeral logistics, donation requests, etc.
# (Haiku 4.5's 200K context window can handle far more, this is purely cost discipline.)
MAX_INPUT_CHARS = 4000

# Defensive: if extracted output exceeds this, treat it as a runaway response and discard.
# The prompt asks for max 120 chars; 160 leaves a margin for valid edge cases.
MAX_OUTPUT_CHARS = 160

# Minimum obit text length worth extracting from. Anything shorter is likely a stub
# (just "passed away peacefully") with no compelling content to surface.
MIN_INPUT_CHARS = 80


_client = None


def _get_client():
    """Lazy-init the Anthropic client so module import doesn't fail when key is unset."""
    global _client
    if _client is None:
        if Anthropic is None:
            raise RuntimeError(
                "anthropic SDK not installed. Run: pip install anthropic python-dotenv"
            )
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Either:\n"
                "  - export ANTHROPIC_API_KEY=sk-ant-...\n"
                "  - add ANTHROPIC_API_KEY=sk-ant-... to ~/Desktop/Neshama/.env (preferred — gitignored)"
            )
        _client = Anthropic()  # SDK reads ANTHROPIC_API_KEY from env automatically
    return _client


def extract_snippet(obituary_text):
    """
    Extract a 1-2 line life-context snippet from an obituary.

    Returns:
        str: The extracted snippet (no trailing whitespace, no quotes), or
        None: If the obituary is too short, contains no extractable content,
              or if any error occurs (network, API, etc.). Snippets are
              nice-to-have, not blocking — failing quietly is the right
              behaviour for a scraper that runs continuously.
    """
    if not obituary_text or len(obituary_text.strip()) < MIN_INPUT_CHARS:
        return None

    text = obituary_text.strip()[:MAX_INPUT_CHARS]

    try:
        client = _get_client()
        # SDK auto-retries 429 + 5xx with exponential backoff (default max_retries=2).
        # No need to wrap in our own retry loop.
        resp = client.messages.create(
            model=MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": PROMPT.format(obituary_text=text)}],
        )
        # Response.content is a list of content blocks — extract the first text block.
        out = next(
            (block.text for block in resp.content if block.type == "text"),
            "",
        ).strip().strip('"').strip("'")

        if not out or out == "NULL":
            return None
        if len(out) > MAX_OUTPUT_CHARS:
            logger.warning(
                "[snippet] runaway response (%d chars), discarding: %r",
                len(out), out[:80]
            )
            return None
        return out

    except Exception as e:
        # Catch-all is intentional — snippet is nice-to-have, not blocking.
        # Scrapers should NOT fail because the API was briefly unavailable.
        logger.warning("[snippet] extraction failed for obit: %s", e)
        return None


def _self_test():
    """
    Smoke test: pull 2 random obits from the local DB and run extraction on them.
    Prints inputs + outputs so you can eyeball quality before running the full backfill.

    Usage:
        python3 snippet.py --self-test
    """
    import sqlite3
    import sys

    db_path = os.environ.get(
        "DATABASE_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "neshama.db"),
    )
    if not os.path.exists(db_path):
        print(f"❌ DB not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, deceased_name, obituary_text
        FROM obituaries
        WHERE obituary_text IS NOT NULL
          AND length(obituary_text) > 200
        ORDER BY RANDOM()
        LIMIT 2
        """
    ).fetchall()

    if not rows:
        print("❌ No obituaries with text in DB. Run scrapers first.")
        sys.exit(1)

    print(f"\n=== Snippet self-test ({MODEL}) ===\n")
    for row in rows:
        print(f"--- obit id={row['id']} | {row['deceased_name']} ---")
        text = row["obituary_text"]
        print(f"INPUT  ({len(text)} chars): {text[:200]}{'...' if len(text) > 200 else ''}")
        snippet = extract_snippet(text)
        print(f"OUTPUT: {snippet!r}\n")

    print("Self-test complete. Eyeball the OUTPUT lines.")
    print("If quality is good → safe to run backfill_snippets.py against the full DB.")
    print("If quality is off → tune the PROMPT in snippet.py and re-test.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        _self_test()
    else:
        print("Usage: python3 snippet.py --self-test")
        print("       (extract_snippet() is meant to be imported from scrapers)")
