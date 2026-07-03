import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  filename TEXT NOT NULL,
  duration_s REAL,
  sport TEXT,
  teams TEXT,
  event_type TEXT,
  summary TEXT,
  status TEXT NOT NULL DEFAULT 'uploaded',
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS transcript_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL REFERENCES videos(id),
  t_start REAL NOT NULL,
  t_end REAL NOT NULL,
  speaker TEXT NOT NULL,
  text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS visual_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL REFERENCES videos(id),
  t_start REAL NOT NULL,
  t_end REAL NOT NULL,
  description TEXT NOT NULL,
  on_screen_text TEXT
);
CREATE TABLE IF NOT EXISTS minute_summaries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL REFERENCES videos(id),
  minute_index INTEGER NOT NULL,
  summary TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS key_moments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT NOT NULL REFERENCES videos(id),
  t REAL NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def create_video(conn, video_id: str, title: str, filename: str) -> None:
    conn.execute(
        "INSERT INTO videos (id, title, filename) VALUES (?, ?, ?)",
        (video_id, title, filename),
    )
    conn.commit()


def set_status(conn, video_id: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE videos SET status = ?, error = ? WHERE id = ?",
        (status, error, video_id),
    )
    conn.commit()


def set_video_meta(conn, video_id, *, duration_s=None, sport=None, teams=None,
                   event_type=None, summary=None) -> None:
    fields = {
        "duration_s": duration_s, "sport": sport, "teams": teams,
        "event_type": event_type, "summary": summary,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE videos SET {cols} WHERE id = ?", (*updates.values(), video_id))
    conn.commit()


def get_video(conn, video_id) -> dict | None:
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


def replace_records(conn, video_id, segments, events, minutes, moments) -> None:
    with conn:
        for table in ("transcript_segments", "visual_events", "minute_summaries", "key_moments"):
            conn.execute(f"DELETE FROM {table} WHERE video_id = ?", (video_id,))
        conn.executemany(
            "INSERT INTO transcript_segments (video_id, t_start, t_end, speaker, text) VALUES (?, ?, ?, ?, ?)",
            [(video_id, s["t_start"], s["t_end"], s["speaker"], s["text"]) for s in segments],
        )
        conn.executemany(
            "INSERT INTO visual_events (video_id, t_start, t_end, description, on_screen_text) VALUES (?, ?, ?, ?, ?)",
            [(video_id, e["t_start"], e["t_end"], e["description"], e.get("on_screen_text")) for e in events],
        )
        conn.executemany(
            "INSERT INTO minute_summaries (video_id, minute_index, summary) VALUES (?, ?, ?)",
            [(video_id, m["minute_index"], m["summary"]) for m in minutes],
        )
        conn.executemany(
            "INSERT INTO key_moments (video_id, t, title, description) VALUES (?, ?, ?, ?)",
            [(video_id, k["t"], k["title"], k["description"]) for k in moments],
        )


def _rows(conn, sql, video_id):
    return [dict(r) for r in conn.execute(sql, (video_id,)).fetchall()]


def get_records(conn, video_id) -> dict:
    return {
        "video": get_video(conn, video_id),
        "transcript_segments": _rows(
            conn, "SELECT * FROM transcript_segments WHERE video_id = ? ORDER BY t_start", video_id),
        "visual_events": _rows(
            conn, "SELECT * FROM visual_events WHERE video_id = ? ORDER BY t_start", video_id),
        "minute_summaries": _rows(
            conn, "SELECT * FROM minute_summaries WHERE video_id = ? ORDER BY minute_index", video_id),
        "key_moments": _rows(
            conn, "SELECT * FROM key_moments WHERE video_id = ? ORDER BY t", video_id),
    }
