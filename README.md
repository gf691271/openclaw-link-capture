# OpenClaw Link Capture

> Drop any URL into conversation → full text extracted → saved to knowledge base.

An [OpenClaw](https://openclaw.ai) skill that automatically captures web content into your personal knowledge graph. Supports Twitter/X, YouTube (subtitles + Whisper fallback), and any web article — zero API keys required.

Works standalone (`python3 capture.py --url "..."`) or as a live OpenClaw agent skill (auto-triggers on any URL in chat).

## What it does

1. **Auto-capture**: Drop a URL in chat → agent silently fetches full content, deduplicates, saves to knowledge graph
2. **Topic card**: `选题 [keyword]` → searches knowledge base + live web trends → outputs differentiated content angles

## Supported sources

| Source | Method | Notes |
|--------|--------|-------|
| Twitter/X | FxTwitter API | No auth required, full text incl. X Articles |
| YouTube | yt-dlp subtitles | Auto-captions or manual subs |
| YouTube (no subs) | yt-dlp + Whisper | Audio download → local transcription |
| Web articles | urllib (stdlib) | Title, author, date, text extraction |

## Setup

### Requirements

```bash
# macOS
brew install yt-dlp
brew install openai-whisper   # or: pip install openai-whisper

# No other pip packages needed
```

### OpenClaw installation

```bash
# Copy to your workspace skills directory
cp -r link-capture ~/.openclaw/workspace/skills/
```

The skill activates automatically when a URL appears in conversation.

## CLI usage

```bash
cd skills/link-capture

# Capture a tweet
python3 scripts/capture.py --url "https://x.com/user/status/123456"

# Capture a YouTube video (subtitles auto-detected, Whisper fallback)
python3 scripts/capture.py --url "https://youtube.com/watch?v=abc123"

# Use better Whisper model for longer videos
python3 scripts/capture.py --url "https://youtube.com/watch?v=abc123" --whisper-model small

# Capture a web article
python3 scripts/capture.py --url "https://example.com/article"

# JSON output (for programmatic use / AI agent integration)
python3 scripts/capture.py --url "..." --json

# Save to SQLite (default: ~/.link-capture/captures.db)
python3 scripts/capture.py --url "..." --backend sqlite

# Prepare for Nowledge Mem (OpenClaw) — AI agent calls nowledge_mem_save()
python3 scripts/capture.py --url "..." --backend nmem

# Save to both
python3 scripts/capture.py --url "..." --backend both
```

## Output format

```
🐦 [@MatthewBerman] OpenClaw作为公司OS：50亿token实战+OAuth漏洞
   URL:    https://x.com/i/status/2026450191759585776
   Type:   twitter
   Labels: #source-twitter #openclaw #ai-agents #signal-tool
   Imp:    ★★★ (0.8)
   Stats:  views=486,622 · likes=2,631 · bookmarks=6,799

   Summary:
   Tweet by @MatthewBerman: 5 BILLION tokens later, OpenClaw is now
   my company's operating system...

   ✅ Saved to SQLite [ea7656de]
   📋 nmem_payload ready (pass to nowledge_mem_save to index)
```

## Architecture

```
capture.py          ← main entry point + CLI
fetchers/
  twitter.py        ← FxTwitter API (zero auth)
  youtube.py        ← yt-dlp subtitles + Whisper fallback
  web.py            ← stdlib urllib, no dependencies
storage/
  sqlite.py         ← local SQLite (~/.link-capture/captures.db)
  nmem.py           ← Nowledge Mem payload formatter (OpenClaw)
SKILL.md            ← AI agent behavior definition
```

## Storage backends

| Backend | When to use |
|---------|-------------|
| `sqlite` | Standalone use, no OpenClaw needed |
| `nmem` | OpenClaw + Nowledge Mem plugin (full semantic search) |
| `both` | Best of both worlds |

## Deduplication

- SQLite: exact URL match check before save
- Nowledge Mem: AI agent runs `memory_search` (score > 0.85 = skip, 0.6–0.85 = save with link)

## OpenClaw agent integration

When running inside OpenClaw, the AI agent:
1. Calls `capture.py --url "..." --json` to get the capture result
2. Reads `result["nmem_payload"]` for pre-formatted Nowledge Mem fields
3. Calls `nowledge_mem_save(**nmem_payload)` to index into knowledge graph
4. Replies with one-line confirmation: `📌 已收入知识库 · **[title]** · #labels`

## Topic card (`选题` mode)

```
你: 选题 OpenClaw知识库
AI: 
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 选题卡：OpenClaw知识库
━━━━━━━━━━━━━━━━━━━━━━━━━━━
知识储备：8条相关记忆
  · [@MatthewBerman] OpenClaw公司OS — 2026-02-25 ★★★
  · OpenClaw升级记录 — 2026-02-25 ★★
  ...
本周热度：...
空白角度：「你家里的人形机器人档案馆」...
推荐选题：...
```

## License

MIT
