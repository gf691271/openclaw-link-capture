#!/usr/bin/env python3
"""
OpenClaw Link Capture — simplified v2
Uses x-reader for fetching, Nowledge Mem for storage.

Usage:
  python3 capture.py --url "https://x.com/user/status/123"
  python3 capture.py --url "https://youtube.com/watch?v=abc"
  python3 capture.py --url "https://example.com/article"
  python3 capture.py --url "..." --json    # machine-readable output for AI agents
"""
import argparse, json, os, subprocess, sys, tempfile, re, hashlib
from pathlib import Path

X_READER = "/Users/frank/.local/bin/x-reader"

# ── URL normalisation ─────────────────────────────────────────────────────────

def normalise_url(url: str) -> str:
    """Canonicalise Twitter /i/status/ → standard form."""
    url = url.strip()
    # x.com/i/status/ID → x.com/i/status/ID (keep as-is; dedup uses semantics)
    # t.co short links are resolved by x-reader automatically
    return url

def detect_type(url: str) -> str:
    if re.search(r"(twitter\.com|x\.com)", url): return "twitter"
    if re.search(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts)", url): return "youtube"
    return "web"

# ── fetch via x-reader ────────────────────────────────────────────────────────

def fetch(url: str) -> dict:
    """
    Run x-reader and return the structured UnifiedContent dict.
    Uses a temp file as inbox to avoid polluting the shared inbox.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        env = {**os.environ, "INBOX_FILE": tmp_path}
        result = subprocess.run(
            [X_READER, url],
            capture_output=True, text=True,
            timeout=90, env=env
        )
        if result.returncode != 0:
            raise RuntimeError(f"x-reader failed: {result.stderr[:200]}")

        raw = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
        if not raw:
            raise RuntimeError("x-reader returned empty result")

        item = raw[-1]  # most recent entry
        return item

    finally:
        try: os.unlink(tmp_path)
        except: pass

# ── importance scoring ────────────────────────────────────────────────────────

def score_importance(item: dict) -> float:
    meta = item.get("metadata", {}) or {}
    url_type = item.get("source_type", "web")

    views     = meta.get("views", 0) or 0
    bookmarks = meta.get("bookmarks", 0) or 0
    likes     = meta.get("likes", 0) or 0

    if url_type == "twitter":
        if views > 500_000 or bookmarks > 5000: return 0.9
        if views > 100_000 or bookmarks > 2000 or likes > 5000: return 0.8
        if views > 10_000  or likes > 500: return 0.65
        return 0.5
    if url_type == "youtube":
        if views > 1_000_000: return 0.8
        if views > 100_000:   return 0.65
        return 0.5
    return 0.5

# ── auto-labelling ────────────────────────────────────────────────────────────

TOPIC_MAP = {
    "openclaw":          ["openclaw","claude","anthropic","claw"],
    "ai-agents":         ["agent","agentic","llm","gpt","mcp","multi-agent"],
    "robotics":          ["robot","humanoid","unitree","embodied"],
    "real-estate":       ["real estate","property","zealty","mls","housing","mortgage"],
    "school-district":   ["school","district","iusd","irvine","university high"],
    "immigration":       ["visa","green card","eb-5","immigration","i-526"],
    "content-strategy":  ["content","strategy","growth","audience","viral","hook"],
    "engineering":       ["scraper","python","api","pipeline","etl","github"],
    "north-shore-crossing": ["lions gate","ironworkers","bridge","north shore"],
    "twitter":           ["twitter","tweet","x.com"],
}

def auto_labels(item: dict) -> list:
    text = (
        (item.get("title") or "") + " " +
        (item.get("content") or "")[:500]
    ).lower()

    labels = [f"source-{item.get('source_type','web')}"]
    for label, keywords in TOPIC_MAP.items():
        if any(kw in text for kw in keywords):
            labels.append(label)
    return labels[:6]

# ── nmem payload ──────────────────────────────────────────────────────────────

def build_nmem_payload(item: dict) -> dict:
    url_type   = item.get("source_type", "web")
    meta       = item.get("metadata", {}) or {}
    title      = item.get("title", "") or item.get("url", "")
    url        = item.get("url", "")
    content    = item.get("content", "") or ""
    # x-reader uses "@i" for /i/status/ URLs — extract real author from content footer
    author     = item.get("source_name", "")
    content_footer = re.search(r"@(\w+)\)\s*\w+ \d+, \d{4}$", content)
    if author in ("@i", "i", "") and content_footer:
        author = "@" + content_footer.group(1)
    fetched_at = item.get("fetched_at", "")[:10]

    # title formatting
    if url_type == "twitter" and author:
        clean_author = author.lstrip("@")
        display_title = f"[@{clean_author}] {title[:55]}"
    elif url_type == "youtube":
        display_title = f"[YouTube] {title[:50]}"
    else:
        display_title = title[:60]

    # stats line
    stats_parts = []
    for k, label in [("views","播放"), ("likes","赞"), ("bookmarks","收藏")]:
        v = meta.get(k, 0) or 0
        if v: stats_parts.append(f"{v:,}{label}")
    stats_line = "数据：" + "，".join(stats_parts) + "\n" if stats_parts else ""

    text = (
        f"来源：{url} / {author} / {fetched_at}\n"
        f"{stats_line}"
        f"\n{content[:600]}"
    )

    pub_date = (meta.get("published_at") or fetched_at or "")[:10]

    return {
        "title":       display_title,
        "text":        text,
        "unit_type":   "event" if url_type in ("twitter","youtube") else "fact",
        "labels":      auto_labels(item),
        "importance":  score_importance(item),
        "event_start": pub_date or None,
    }

# ── main pipeline ─────────────────────────────────────────────────────────────

def run(url: str, json_output: bool = False) -> dict:
    url = normalise_url(url)
    result = {
        "url": url, "status": "ok",
        "title": None, "url_type": detect_type(url),
        "nmem_payload": None, "error": None,
    }

    try:
        item = fetch(url)
        result["url_type"]     = item.get("source_type", detect_type(url))
        result["title"]        = item.get("title", url)
        result["nmem_payload"] = build_nmem_payload(item)
        result["raw"]          = item
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)

    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    return result

def _print_human(r: dict):
    icon = {"twitter":"🐦","youtube":"🎬","web":"🌐"}.get(r["url_type"],"🔗")
    print(f"\n{icon} {r['title'] or r['url']}")
    print(f"   {r['url']}")
    if r.get("error"):
        print(f"   ❌ {r['error']}")
        return
    p = r.get("nmem_payload", {})
    if p:
        labels = " ".join(f"#{l}" for l in p.get("labels",[]))
        imp = p.get("importance", 0.5)
        star = "★★★" if imp>=0.8 else "★★" if imp>=0.65 else "★"
        print(f"   {labels}  {star}")
        print(f"   {p.get('text','')[:200]}")
    print(f"\n   📋 nmem_payload ready → nowledge_mem_save()")

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="OpenClaw Link Capture")
    p.add_argument("--url",  required=True)
    p.add_argument("--json", action="store_true", help="JSON output for AI agents")
    args = p.parse_args()
    run(args.url, json_output=args.json)
