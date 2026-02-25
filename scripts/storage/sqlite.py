"""
SQLite storage backend — zero external dependencies.
Default DB: ~/.link-capture/captures.db
"""
import sqlite3, json, hashlib, os
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path.home() / ".link-capture" / "captures.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    id           TEXT PRIMARY KEY,
    url          TEXT UNIQUE NOT NULL,
    url_type     TEXT,
    title        TEXT,
    author       TEXT,
    content      TEXT,
    summary      TEXT,
    labels       TEXT,          -- JSON array
    importance   REAL DEFAULT 0.5,
    published_at TEXT,
    captured_at  TEXT,
    stats_json   TEXT,          -- views/likes/etc
    extra_json   TEXT           -- any extra metadata
);
CREATE INDEX IF NOT EXISTS idx_captured_at ON captures(captured_at);
CREATE INDEX IF NOT EXISTS idx_url_type    ON captures(url_type);
"""

def _url_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]

class SQLiteBackend:
    def __init__(self, db_path: Optional[str] = None):
        path = Path(db_path) if db_path else DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def exists(self, url: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM captures WHERE url=?", (url,))
        return cur.fetchone() is not None

    def save(self, capture: dict) -> str:
        uid = _url_id(capture["url"])
        now = datetime.utcnow().isoformat()
        self.conn.execute("""
            INSERT OR REPLACE INTO captures
            (id, url, url_type, title, author, content, summary, labels,
             importance, published_at, captured_at, stats_json, extra_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            uid,
            capture.get("url", ""),
            capture.get("url_type", "web"),
            capture.get("title", ""),
            capture.get("author", ""),
            capture.get("content", "")[:20000],   # cap at 20K chars
            capture.get("summary", ""),
            json.dumps(capture.get("labels", [])),
            capture.get("importance", 0.5),
            capture.get("published_at", ""),
            now,
            json.dumps(capture.get("stats", {})),
            json.dumps({k: v for k, v in capture.items()
                        if k not in ("url","url_type","title","author",
                                     "content","summary","labels","importance",
                                     "published_at","stats")}),
        ))
        self.conn.commit()
        return uid

    def search(self, query: str, limit: int = 8) -> list[dict]:
        """Simple full-text search (LIKE). For production use FTS5."""
        q = f"%{query}%"
        cur = self.conn.execute("""
            SELECT url, url_type, title, author, summary, labels, importance, captured_at
            FROM captures
            WHERE title LIKE ? OR content LIKE ? OR summary LIKE ?
            ORDER BY importance DESC, captured_at DESC
            LIMIT ?
        """, (q, q, q, limit))
        rows = cur.fetchall()
        cols = ["url","url_type","title","author","summary","labels","importance","captured_at"]
        return [dict(zip(cols, r)) for r in rows]

    def close(self):
        self.conn.close()
