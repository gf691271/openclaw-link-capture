#!/usr/bin/env python3
"""
link-capture — URL knowledge capture pipeline
Supports: Twitter/X, YouTube (subtitles + Whisper), web articles

Usage:
  python3 capture.py --url "https://x.com/user/status/123"
  python3 capture.py --url "https://youtube.com/watch?v=abc" --whisper-model small
  python3 capture.py --url "https://example.com/article"
  python3 capture.py --url "..." --backend sqlite --db ~/my-captures.db
  python3 capture.py --url "..." --backend nmem         # for OpenClaw Nowledge Mem
  python3 capture.py --url "..." --backend both         # save to both
  python3 capture.py --json                             # output JSON only (for AI agents)
"""
import argparse, json, sys, re, os
from pathlib import Path

# add scripts/ to path so we can import siblings
sys.path.insert(0, str(Path(__file__).parent))

from fetchers import twitter, youtube, web
from storage  import sqlite as sqlite_backend, nmem as nmem_backend

# ── URL router ────────────────────────────────────────────────────────────────

def fetch(url: str, whisper_model: str = "base") -> dict:
    """Route URL to the right fetcher and return a normalized capture dict."""
    if twitter.is_twitter_url(url):
        return twitter.fetch(url)
    if youtube.is_youtube_url(url):
        return youtube.fetch(url, whisper_model=whisper_model)
    if web.is_web_url(url):
        return web.fetch(url)
    raise ValueError(f"Unsupported URL: {url}")

# ── summary generator (standalone, no LLM required) ──────────────────────────

def auto_summary(capture: dict, max_len: int = 400) -> str:
    """
    Generate a summary without an LLM.
    Good enough for indexing; AI agents can enrich this when calling from OpenClaw.
    """
    url_type = capture.get("url_type", "web")
    content  = capture.get("content", "")
    stats    = capture.get("stats", {})

    parts = []

    if url_type == "twitter":
        sn = capture.get("screen_name", "")
        parts.append(f"Tweet by @{sn}:" if sn else "Tweet:")
        # first 200 chars of content
        parts.append(content[:200])
        if stats:
            parts.append(
                f"[{stats.get('views',0):,} views · "
                f"{stats.get('likes',0):,} likes · "
                f"{stats.get('bookmarks',0):,} bookmarks]"
            )
        qt = capture.get("quote_tweet")
        if qt:
            parts.append(f"Quoting @{qt['screen_name']}: {qt['text'][:100]}")

    elif url_type == "youtube":
        ch = capture.get("channel") or capture.get("author","")
        dur = capture.get("duration_secs", 0)
        method = capture.get("transcript_method","")
        parts.append(f"YouTube video by {ch} ({dur//60} min) [{method}]")
        transcript = capture.get("transcript", "")
        if transcript:
            parts.append(transcript[:300])
        else:
            parts.append(content[:300])

    else:  # web
        domain = capture.get("domain", "")
        author = capture.get("author", "")
        if author and author != domain:
            parts.append(f"Article by {author} ({domain}):")
        parts.append(content[:300])

    return "\n".join(parts)[:max_len]

# ── dedup check (sqlite only; nmem dedup handled by the AI agent) ─────────────

def check_dedup_sqlite(url: str, db: sqlite_backend.SQLiteBackend) -> dict:
    """Returns {"exists": bool, "similar": [...]}"""
    return {"exists": db.exists(url), "similar": []}

# ── main pipeline ─────────────────────────────────────────────────────────────

def run(
    url: str,
    backend: str = "sqlite",
    db_path: str = None,
    whisper_model: str = "base",
    json_output: bool = False,
) -> dict:
    """
    Full capture pipeline.
    Returns result dict suitable for AI agent consumption.
    """
    result = {
        "url":        url,
        "status":     "ok",
        "url_type":   None,
        "title":      None,
        "summary":    None,
        "labels":     [],
        "importance": 0.5,
        "nmem_payload": None,   # filled when backend includes nmem
        "dedup":      {"exists": False, "similar": []},
        "error":      None,
    }

    # 1. fetch
    try:
        capture = fetch(url, whisper_model=whisper_model)
        result["url_type"] = capture.get("url_type")
        result["title"]    = capture.get("title")
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
        if json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    # 2. auto-summary
    summary = auto_summary(capture)
    result["summary"] = summary

    # 3. nmem formatting (always computed; AI agent decides whether to actually save)
    nmem_payload = nmem_backend.format_for_nmem(capture, summary)
    result["nmem_payload"] = nmem_payload
    result["labels"]       = nmem_payload["labels"]
    result["importance"]   = nmem_payload["importance"]

    # 4. sqlite save (if requested)
    if backend in ("sqlite", "both"):
        db = sqlite_backend.SQLiteBackend(db_path)
        dedup = check_dedup_sqlite(url, db)
        result["dedup"] = dedup
        if not dedup["exists"]:
            save_capture = {**capture, **nmem_payload}
            uid = db.save(save_capture)
            result["sqlite_id"] = uid
        db.close()

    # 5. output
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result, capture)

    return result


def _print_human(result: dict, capture: dict):
    """Print a concise human-readable capture card."""
    icon = {"twitter": "🐦", "youtube": "🎬", "web": "🌐"}.get(result["url_type"], "🔗")
    title = result["title"] or result["url"]
    labels = " ".join(f"#{l}" for l in result["labels"])
    imp = result["importance"]
    imp_star = "★★★" if imp >= 0.8 else "★★" if imp >= 0.65 else "★"

    print(f"\n{icon} {title}")
    print(f"   URL:    {result['url']}")
    print(f"   Type:   {result['url_type']}")
    print(f"   Labels: {labels}")
    print(f"   Imp:    {imp_star} ({imp:.1f})")

    stats = capture.get("stats", {})
    if stats and any(stats.values()):
        stat_str = " · ".join(
            f"{k}={v:,}" for k, v in stats.items() if v
        )
        print(f"   Stats:  {stat_str}")

    if result["url_type"] == "youtube":
        method = capture.get("transcript_method", "")
        dur    = capture.get("duration_secs", 0)
        print(f"   Audio:  {dur//60} min · transcript via {method}")

    print(f"\n   Summary:\n   {result['summary'][:300]}")

    if result["dedup"].get("exists"):
        print("\n   ⚠️  Already in local DB — skipped")
    elif "sqlite_id" in result:
        print(f"\n   ✅ Saved to SQLite [{result['sqlite_id']}]")

    if result["nmem_payload"]:
        print("\n   📋 nmem_payload ready (pass to nowledge_mem_save to index)")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="link-capture: URL → knowledge")
    p.add_argument("--url",           required=True, help="URL to capture")
    p.add_argument("--backend",       default="sqlite",
                   choices=["sqlite","nmem","both","none"],
                   help="Storage backend (default: sqlite)")
    p.add_argument("--db",            default=None,
                   help="SQLite DB path (default: ~/.link-capture/captures.db)")
    p.add_argument("--whisper-model", default="base",
                   choices=["tiny","base","small","medium","large"],
                   help="Whisper model for YouTube (default: base)")
    p.add_argument("--json",          action="store_true",
                   help="Output JSON (for AI agent consumption)")
    args = p.parse_args()

    run(
        url           = args.url,
        backend       = args.backend,
        db_path       = args.db,
        whisper_model = args.whisper_model,
        json_output   = args.json,
    )

if __name__ == "__main__":
    main()
