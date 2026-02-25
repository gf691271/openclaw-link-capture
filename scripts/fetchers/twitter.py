"""
Twitter/X fetcher — wraps FxTwitter API (zero auth required)
"""
import json, urllib.request, re
from typing import Optional

FXTWITTER_API = "https://api.fxtwitter.com"

def is_twitter_url(url: str) -> bool:
    return bool(re.match(r"https?://(www\.)?(twitter\.com|x\.com|t\.co)/", url))

def fetch(url: str) -> dict:
    """Fetch a tweet and return normalized capture dict."""
    tweet_id = _extract_id(url)
    if not tweet_id:
        raise ValueError(f"Cannot extract tweet ID from: {url}")

    api_url = f"{FXTWITTER_API}/status/{tweet_id}"
    req = urllib.request.Request(api_url, headers={"User-Agent": "link-capture/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    tweet = data.get("tweet", {})
    author = tweet.get("author", {})

    # handle X Articles (long-form)
    # raw_text is a dict {"text": "...", "facets": []} for media-only tweets
    raw = tweet.get("raw_text", "")
    raw_str = raw.get("text", "") if isinstance(raw, dict) else str(raw)
    content = tweet.get("text", "") or raw_str
    if tweet.get("note_tweet"):
        content = tweet.get("note_tweet", {}).get("text", content)

    article = tweet.get("card", {})
    article_text = ""
    if tweet.get("is_article") or "article" in tweet:
        a = tweet.get("article", {})
        article_text = a.get("full_text", "")
        content = f"{a.get('title','')}\n\n{article_text}" if article_text else content

    media_urls = []
    for m in tweet.get("media", {}).get("photos", []):
        media_urls.append(m.get("url", ""))
    for m in tweet.get("media", {}).get("videos", []):
        media_urls.append(m.get("url", ""))

    # media-only tweet: flag it clearly
    is_media_only = bool(media_urls) and not content.strip()

    return {
        "url": url,
        "url_type": "twitter",
        "title": f"@{author.get('screen_name','')}: {content[:80]}...",
        "author": author.get("name", ""),
        "screen_name": author.get("screen_name", ""),
        "content": content,
        "article_text": article_text,
        "published_at": tweet.get("created_at", ""),
        "stats": {
            "views":     tweet.get("views", 0),
            "likes":     tweet.get("likes", 0),
            "retweets":  tweet.get("retweets", 0),
            "bookmarks": tweet.get("bookmarks", 0),
            "replies":   tweet.get("replies", 0),
        },
        "media_urls": media_urls,
        "is_article": bool(article_text),
        "quote_tweet": _extract_quote(tweet),
    }

def _extract_id(url: str) -> Optional[str]:
    m = re.search(r"/status(?:es)?/(\d+)", url)
    return m.group(1) if m else None

def _extract_quote(tweet: dict) -> Optional[dict]:
    qt = tweet.get("quote", {})
    if not qt:
        return None
    qa = qt.get("author", {})
    return {
        "screen_name": qa.get("screen_name", ""),
        "text": qt.get("text", ""),
    }
