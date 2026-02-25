"""
YouTube fetcher — subtitles first, Whisper fallback.
Requires: yt-dlp (brew install yt-dlp), whisper (brew install openai-whisper)
"""
import re, subprocess, json, tempfile, os
from pathlib import Path
from typing import Optional

YT_DLP = "/opt/homebrew/bin/yt-dlp"
WHISPER = "/opt/homebrew/bin/whisper"

def is_youtube_url(url: str) -> bool:
    return bool(re.match(
        r"https?://(www\.)?(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)",
        url
    ))

def fetch(url: str, whisper_model: str = "base") -> dict:
    """
    Fetch YouTube content. Strategy:
    1. Get metadata (title, channel, views, description)
    2. Try to get subtitles (auto-captions preferred)
    3. If no subtitles: download audio → Whisper transcription
    Returns normalized capture dict.
    """
    meta = _get_metadata(url)
    transcript, method = _get_transcript(url, meta, whisper_model)

    content = _build_content(meta, transcript)

    return {
        "url": url,
        "url_type": "youtube",
        "title": meta.get("title", ""),
        "author": meta.get("uploader", ""),
        "channel": meta.get("channel", ""),
        "content": content,
        "transcript": transcript,
        "transcript_method": method,   # "subtitles" | "whisper" | "description_only"
        "published_at": meta.get("upload_date", ""),   # YYYYMMDD
        "duration_secs": meta.get("duration", 0),
        "stats": {
            "views":    meta.get("view_count", 0),
            "likes":    meta.get("like_count", 0),
            "comments": meta.get("comment_count", 0),
        },
        "thumbnail": meta.get("thumbnail", ""),
        "tags": meta.get("tags", [])[:10],
        "chapters": meta.get("chapters", []),
    }

# ── internal helpers ──────────────────────────────────────────────────────────

def _get_metadata(url: str) -> dict:
    cmd = [YT_DLP, "--dump-json", "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {result.stderr[:200]}")
    return json.loads(result.stdout)

def _get_transcript(url: str, meta: dict, whisper_model: str) -> tuple[str, str]:
    """Returns (transcript_text, method_used)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: try to get subtitles
        transcript = _try_subtitles(url, tmpdir)
        if transcript:
            return transcript, "subtitles"

        # Step 2: Whisper transcription
        transcript = _try_whisper(url, tmpdir, whisper_model)
        if transcript:
            return transcript, "whisper"

    # Step 3: fallback to description
    desc = meta.get("description", "")
    return desc[:3000] if desc else "", "description_only"

def _try_subtitles(url: str, tmpdir: str) -> Optional[str]:
    """Download auto-generated or manual subtitles, return cleaned text."""
    cmd = [
        YT_DLP,
        "--write-auto-sub", "--write-sub",
        "--sub-lang", "en,zh-Hans,zh-Hant,zh",
        "--sub-format", "vtt",
        "--skip-download",
        "--no-playlist",
        "-o", os.path.join(tmpdir, "%(id)s"),
        url
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)

    # find any .vtt file
    vtt_files = list(Path(tmpdir).glob("*.vtt"))
    if not vtt_files:
        return None

    return _parse_vtt(vtt_files[0])

def _try_whisper(url: str, tmpdir: str, model: str) -> Optional[str]:
    """Download audio and run Whisper."""
    audio_path = os.path.join(tmpdir, "audio")
    # download audio only
    cmd = [
        YT_DLP, "-x", "--audio-format", "mp3",
        "--no-playlist",
        "-o", audio_path,
        url
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode != 0:
        return None

    # find the downloaded mp3
    mp3_files = list(Path(tmpdir).glob("*.mp3"))
    if not mp3_files:
        return None

    # run whisper
    cmd = [
        WHISPER, str(mp3_files[0]),
        "--model", model,
        "--output_format", "txt",
        "--output_dir", tmpdir,
        "--language", "auto",
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0:
        return None

    txt_files = list(Path(tmpdir).glob("*.txt"))
    if txt_files:
        return txt_files[0].read_text(encoding="utf-8").strip()
    return None

def _parse_vtt(vtt_path: Path) -> str:
    """Parse WebVTT subtitle file into clean plain text (deduped)."""
    text = vtt_path.read_text(encoding="utf-8", errors="replace")
    lines, seen = [], set()
    for line in text.splitlines():
        line = line.strip()
        # skip VTT headers, timestamps, empty lines
        if (not line or line.startswith("WEBVTT") or
                re.match(r"^\d{2}:\d{2}", line) or
                re.match(r"^NOTE", line) or
                re.match(r"^\d+$", line)):
            continue
        # strip HTML tags
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)
    return " ".join(lines)

def _build_content(meta: dict, transcript: str) -> str:
    """Combine metadata + transcript into a single content string."""
    parts = []
    title = meta.get("title", "")
    channel = meta.get("channel") or meta.get("uploader", "")
    duration = meta.get("duration", 0)
    mins = duration // 60

    if title:
        parts.append(f"Title: {title}")
    if channel:
        parts.append(f"Channel: {channel}")
    if mins:
        parts.append(f"Duration: {mins} min")

    chapters = meta.get("chapters", [])
    if chapters:
        parts.append("\nChapters:")
        for ch in chapters:
            start = int(ch.get("start_time", 0))
            parts.append(f"  {start//60}:{start%60:02d} {ch.get('title','')}")

    if transcript:
        parts.append(f"\nTranscript:\n{transcript[:8000]}")
    elif meta.get("description"):
        parts.append(f"\nDescription:\n{meta['description'][:2000]}")

    return "\n".join(parts)
