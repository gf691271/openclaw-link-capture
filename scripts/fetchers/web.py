"""
Generic web fetcher — extracts readable content from any URL.
Uses urllib (stdlib only) with readability-style extraction.
Falls back to raw text extraction.
"""
import re, urllib.request, html
from urllib.parse import urlparse
from typing import Optional

def is_web_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")

def fetch(url: str, max_chars: int = 6000) -> dict:
    """Fetch a web page and return normalized capture dict."""
    raw_html, final_url = _download(url)
    title = _extract_title(raw_html)
    author = _extract_author(raw_html)
    published = _extract_date(raw_html)
    content = _extract_text(raw_html, max_chars)
    domain = urlparse(final_url).netloc.replace("www.", "")

    return {
        "url": final_url,
        "url_type": "web",
        "title": title or final_url,
        "author": author or domain,
        "domain": domain,
        "content": content,
        "published_at": published or "",
        "stats": {},
    }

# ── internal helpers ──────────────────────────────────────────────────────────

def _download(url: str) -> tuple[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = _detect_charset(resp.headers.get("Content-Type", ""))
        raw = resp.read()
        return raw.decode(charset, errors="replace"), resp.url

def _detect_charset(content_type: str) -> str:
    m = re.search(r"charset=([^\s;]+)", content_type, re.I)
    return m.group(1).lower() if m else "utf-8"

def _extract_title(html_text: str) -> Optional[str]:
    # OG title first, then <title>
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html_text, re.I)
    if m:
        return html.unescape(m.group(1).strip())
    m = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.I)
    if m:
        return html.unescape(m.group(1).strip())
    return None

def _extract_author(html_text: str) -> Optional[str]:
    patterns = [
        r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)',
        r'"author"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
        r'<a[^>]+rel=["\']author["\'][^>]*>([^<]+)<',
    ]
    for p in patterns:
        m = re.search(p, html_text, re.I)
        if m:
            return html.unescape(m.group(1).strip())
    return None

def _extract_date(html_text: str) -> Optional[str]:
    patterns = [
        r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'<time[^>]+datetime=["\']([^"\']+)',
    ]
    for p in patterns:
        m = re.search(p, html_text, re.I)
        if m:
            val = m.group(1).strip()
            return val[:10]  # YYYY-MM-DD
    return None

def _extract_text(html_text: str, max_chars: int) -> str:
    """Strip HTML tags and return readable text."""
    # Remove script, style, nav, header, footer blocks
    for tag in ["script", "style", "nav", "header", "footer", "aside", "iframe"]:
        html_text = re.sub(
            rf"<{tag}[\s>].*?</{tag}>", "", html_text,
            flags=re.DOTALL | re.I
        )
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html_text)
    # Decode entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]
