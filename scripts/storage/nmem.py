"""
Nowledge Mem backend — saves to OpenClaw knowledge graph via CLI.
Requires: openclaw-nowledge-mem plugin running.
This backend is a thin wrapper; actual save happens when the AI calls
nowledge_mem_save() tool. This module handles formatting only.
"""
from typing import Optional

# Importance heuristics for Twitter content
def compute_importance(capture: dict) -> float:
    stats = capture.get("stats", {})
    views     = stats.get("views", 0)
    bookmarks = stats.get("bookmarks", 0)
    likes     = stats.get("likes", 0)

    url_type = capture.get("url_type", "web")

    if url_type == "twitter":
        if views > 500_000 or bookmarks > 5000:
            return 0.9
        if views > 100_000 or bookmarks > 2000 or likes > 5000:
            return 0.8
        if views > 10_000 or likes > 500:
            return 0.65
        return 0.5

    if url_type == "youtube":
        if views > 1_000_000:
            return 0.8
        if views > 100_000:
            return 0.65
        return 0.5

    return 0.5  # web articles default

def format_for_nmem(capture: dict, summary: str) -> dict:
    """
    Returns a dict with all fields needed for nowledge_mem_save().
    The AI agent calls nowledge_mem_save(**format_for_nmem(capture, summary)).
    """
    url_type = capture.get("url_type", "web")
    stats    = capture.get("stats", {})

    # build title
    title = capture.get("title", "")
    if url_type == "twitter":
        screen_name = capture.get("screen_name", "")
        title = f"[@{screen_name}] {title[:55]}" if screen_name else title[:60]
    elif url_type == "youtube":
        channel = capture.get("channel") or capture.get("author", "")
        title = f"[YouTube] {title[:45]} — {channel}"[:60]

    # build text
    stats_line = ""
    if url_type == "twitter" and stats:
        stats_line = (
            f"数据：{stats.get('views',0):,}播放，"
            f"{stats.get('bookmarks',0):,}收藏，"
            f"{stats.get('likes',0):,}赞\n"
        )
    elif url_type == "youtube" and stats:
        stats_line = (
            f"数据：{stats.get('views',0):,}播放，"
            f"{stats.get('likes',0):,}赞\n"
        )

    transcript_note = ""
    if url_type == "youtube":
        method = capture.get("transcript_method", "")
        transcript_note = f"字幕来源：{method}\n"

    text = (
        f"来源：{capture['url']}"
        f" / {capture.get('author','')}"
        f" / {capture.get('published_at','')}\n"
        f"{stats_line}"
        f"{transcript_note}"
        f"\n{summary}"
    )

    # auto-labels
    labels = _auto_labels(capture, summary)

    # published date → event_start
    pub = capture.get("published_at", "")
    event_start = pub[:10] if pub and len(pub) >= 10 else None

    return {
        "title":       title,
        "text":        text,
        "unit_type":   "event" if url_type in ("twitter","youtube") else "fact",
        "labels":      labels,
        "importance":  compute_importance(capture),
        "event_start": event_start,
    }

def _auto_labels(capture: dict, summary: str) -> list[str]:
    """Heuristic label assignment based on content keywords."""
    text = (capture.get("title","") + " " + summary).lower()
    labels = []

    # source label
    labels.append(f"source-{capture.get('url_type','web')}")

    # topic labels
    topic_map = {
        "openclaw":        ["openclaw","claude","anthropic"],
        "ai-agents":       ["agent","agentic","multi-agent","llm","gpt"],
        "robotics":        ["robot","humanoid","unitree","embodied"],
        "twitter":         ["twitter","tweet","x.com","@"],
        "real-estate":     ["real estate","property","zealty","mls","housing"],
        "school-district": ["school","district","iusd","university high","irvine"],
        "immigration":     ["visa","green card","eb-5","immigration"],
        "content-strategy":["content","strategy","growth","audience","viral"],
        "engineering":     ["code","scraper","python","api","pipeline","etl"],
        "north-shore-crossing": ["lions gate","ironworkers","bridge","north shore"],
    }
    for label, keywords in topic_map.items():
        if any(kw in text for kw in keywords):
            labels.append(label)

    return labels[:6]  # cap at 6 labels
