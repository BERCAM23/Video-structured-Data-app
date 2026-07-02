# Video Intelligence MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-page web app that processes a Fox Sports LatAm video into structured records (diarized transcript, visual events, summaries, key moments) and answers questions grounded in those records with clickable timestamp citations.

**Architecture:** Python FastAPI backend runs a 6-stage resumable pipeline (ingest, ffmpeg audio extraction, ElevenLabs Scribe v2 transcription, Gemini 3.5 Flash chunked visual analysis, merge+summarize, SQLite persistence). Claude Opus 4.8 answers chat grounded in the records with prompt caching. Vite+React frontend: upload, live processing progress, then a workspace with video player, synced data scroller, and chat whose citations seek the player.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, google-genai SDK, anthropic SDK, sqlite3 (stdlib), pytest, ffmpeg CLI, Vite + React + TypeScript, vitest.

## Global Constraints

- Model IDs, verbatim: ElevenLabs `scribe_v2`, Google `gemini-3.5-flash`, Anthropic `claude-opus-4-8`.
- Transcription language: `es` (Spanish). Diarization and audio-event tagging ON.
- Visual analysis window: 900 seconds per Gemini call; visual description cadence ~4 seconds.
- Citations format everywhere: `[MM:SS]` or `[H:MM:SS]`. All stored timestamps are float seconds.
- No vector database. Chat gets full records in context with `cache_control: {"type": "ephemeral"}`.
- Claude call: streaming, `thinking={"type": "adaptive"}` set explicitly. Never `budget_tokens`, never `temperature`.
- Env keys in `backend/.env`: `ELEVENLABS_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`. Startup fails fast if any is missing. `.env` is gitignored.
- `data/` directory is gitignored (videos, audio, DB).
- Upload limits: extensions .mp4/.mov/.mkv, max 3 hours, max 2 GB.
- ffmpeg and ffprobe must be on PATH (`winget install --id Gyan.FFmpeg` on Windows).
- Backend tests run from `backend/` with `python -m pytest`. Never call paid APIs in tests; test pure logic, mock clients.
- Commit after every task. Conventional commits. No attribution lines.
- Writing style in all docs and comments: short sentences, no em dashes.

## Prerequisites (before Task 1)

- [ ] Python 3.11+ (`python --version`), Node 20+ (`node --version`), ffmpeg (`ffmpeg -version`).
- [ ] Accounts + API keys created for ElevenLabs, Google AI Studio, Anthropic.

---

### Task 1: Backend scaffold and fail-fast config

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `load_settings(env: dict | None = None) -> Settings` where `Settings` has `elevenlabs_api_key: str`, `google_api_key: str`, `anthropic_api_key: str`, `data_dir: Path`. Raises `RuntimeError` naming missing keys.

- [ ] **Step 1: Write requirements and env example**

`backend/requirements.txt`:
```
fastapi
uvicorn[standard]
python-multipart
httpx
python-dotenv
google-genai
anthropic
pytest
```

`backend/.env.example`:
```
ELEVENLABS_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
DATA_DIR=data
```

Install: `cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`backend/tests/test_config.py`:
```python
import pytest

from app.config import load_settings


def test_fails_fast_when_key_missing(tmp_path):
    env = {
        "ELEVENLABS_API_KEY": "x",
        "GOOGLE_API_KEY": "",
        "ANTHROPIC_API_KEY": "y",
        "DATA_DIR": str(tmp_path),
    }
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        load_settings(env)


def test_loads_and_creates_data_dir(tmp_path):
    env = {
        "ELEVENLABS_API_KEY": "a",
        "GOOGLE_API_KEY": "b",
        "ANTHROPIC_API_KEY": "c",
        "DATA_DIR": str(tmp_path / "d"),
    }
    s = load_settings(env)
    assert s.anthropic_api_key == "c"
    assert s.data_dir.exists()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/config.py`:
```python
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REQUIRED_KEYS = ["ELEVENLABS_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"]


@dataclass(frozen=True)
class Settings:
    elevenlabs_api_key: str
    google_api_key: str
    anthropic_api_key: str
    data_dir: Path


def load_settings(env: dict | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = dict(os.environ)
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    data_dir = Path(env.get("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        elevenlabs_api_key=env["ELEVENLABS_API_KEY"],
        google_api_key=env["GOOGLE_API_KEY"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        data_dir=data_dir,
    )
```

- [ ] **Step 5: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/app backend/tests
git commit -m "feat: backend scaffold with fail-fast config"
```

---

### Task 2: SQLite schema and record store

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces:
  - `connect(db_path: Path) -> sqlite3.Connection` (row_factory=Row, WAL, foreign keys on; parent dir auto-created)
  - `init_db(conn) -> None`
  - `create_video(conn, video_id: str, title: str, filename: str) -> None`
  - `set_status(conn, video_id: str, status: str, error: str | None = None) -> None`
  - `set_video_meta(conn, video_id, *, duration_s=None, sport=None, teams=None, event_type=None, summary=None) -> None`
  - `replace_records(conn, video_id, segments: list[dict], events: list[dict], minutes: list[dict], moments: list[dict]) -> None` (idempotent: deletes then inserts)
  - `get_video(conn, video_id) -> dict | None`
  - `get_records(conn, video_id) -> dict` with keys `video`, `transcript_segments`, `visual_events`, `minute_summaries`, `key_moments`
- Status values: `uploaded`, `extracting_audio`, `transcribing`, `analyzing_visuals`, `summarizing`, `ready`, `failed`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_db.py`:
```python
from app import db


def make(tmp_path):
    conn = db.connect(tmp_path / "vault.db")
    db.init_db(conn)
    return conn


def test_create_and_get_video(tmp_path):
    conn = make(tmp_path)
    db.create_video(conn, "v1", "Partido", "source.mp4")
    row = db.get_video(conn, "v1")
    assert row["status"] == "uploaded"
    assert row["title"] == "Partido"
    assert db.get_video(conn, "nope") is None


def test_status_and_meta(tmp_path):
    conn = make(tmp_path)
    db.create_video(conn, "v1", "t", "f.mp4")
    db.set_status(conn, "v1", "failed", error="boom")
    db.set_video_meta(conn, "v1", duration_s=120.5, sport="futbol")
    row = db.get_video(conn, "v1")
    assert row["status"] == "failed"
    assert row["error"] == "boom"
    assert row["duration_s"] == 120.5
    assert row["sport"] == "futbol"


def test_replace_records_is_idempotent(tmp_path):
    conn = make(tmp_path)
    db.create_video(conn, "v1", "t", "f.mp4")
    seg = [{"t_start": 0.0, "t_end": 2.0, "speaker": "speaker_0", "text": "hola"}]
    ev = [{"t_start": 0.0, "t_end": 4.0, "description": "kickoff", "on_screen_text": "0-0"}]
    mins = [{"minute_index": 0, "summary": "empieza"}]
    moms = [{"t": 1.0, "title": "inicio", "description": "arranca"}]
    db.replace_records(conn, "v1", seg, ev, mins, moms)
    db.replace_records(conn, "v1", seg, ev, mins, moms)
    rec = db.get_records(conn, "v1")
    assert len(rec["transcript_segments"]) == 1
    assert rec["visual_events"][0]["on_screen_text"] == "0-0"
    assert rec["minute_summaries"][0]["minute_index"] == 0
    assert rec["key_moments"][0]["title"] == "inicio"
    assert rec["video"]["id"] == "v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`

- [ ] **Step 3: Write minimal implementation**

`backend/app/db.py`:
```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: sqlite schema and record store"
```

---

### Task 3: ffmpeg helpers (probe + audio extraction)

**Files:**
- Create: `backend/app/media.py`
- Test: `backend/tests/test_media.py`
- Create: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `probe_duration(video_path: Path) -> float`, `extract_audio(video_path: Path, out_path: Path) -> Path` (mono 16kHz mp3). Both raise `MediaError` on failure.
- Test fixture `tiny_clip` (session-scoped): 2-second synthetic MP4 with tone audio, generated by ffmpeg. Reused by Task 7 and 9 tests.

- [ ] **Step 1: Write fixture and failing test**

`backend/tests/conftest.py`:
```python
import subprocess

import pytest


@pytest.fixture(scope="session")
def tiny_clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "tiny.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )
    return path
```

`backend/tests/test_media.py`:
```python
import pytest

from app.media import MediaError, extract_audio, probe_duration


def test_probe_duration(tiny_clip):
    assert probe_duration(tiny_clip) == pytest.approx(2.0, abs=0.3)


def test_extract_audio(tiny_clip, tmp_path):
    out = extract_audio(tiny_clip, tmp_path / "audio.mp3")
    assert out.exists()
    assert out.stat().st_size > 1000


def test_probe_missing_file_raises(tmp_path):
    with pytest.raises(MediaError):
        probe_duration(tmp_path / "nope.mp4")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_media.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.media'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/media.py`:
```python
import json
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise MediaError(f"{cmd[0]} not found on PATH") from e
    if proc.returncode != 0:
        raise MediaError(f"{cmd[0]} failed: {proc.stderr[-500:]}")
    return proc


def probe_duration(video_path: Path) -> float:
    if not Path(video_path).exists():
        raise MediaError(f"file not found: {video_path}")
    proc = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", str(video_path),
    ])
    return float(json.loads(proc.stdout)["format"]["duration"])


def extract_audio(video_path: Path, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
        str(out_path),
    ])
    return out_path
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_media.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/media.py backend/tests/test_media.py backend/tests/conftest.py
git commit -m "feat: ffmpeg probe and audio extraction"
```

---

### Task 4: ElevenLabs Scribe transcription + normalizer

**Files:**
- Create: `backend/app/stt.py`
- Test: `backend/tests/test_stt.py`
- Create: `backend/scripts/verify_stt.py`

**Interfaces:**
- Consumes: `Settings.elevenlabs_api_key`.
- Produces:
  - `transcribe(audio_path: Path, api_key: str) -> dict` (raw API response, retries 3x)
  - `normalize(raw: dict) -> list[dict]` returning `{"t_start": float, "t_end": float, "speaker": str, "text": str}`. Groups words by speaker, splits on speaker change, gaps > 1.5s, or segments > 30s. Audio events become segments with speaker `"EVENT"`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_stt.py`:
```python
from app.stt import normalize


def w(text, start, end, speaker="speaker_0", kind="word"):
    return {"text": text, "start": start, "end": end, "speaker_id": speaker, "type": kind}


def test_groups_consecutive_words_by_speaker():
    raw = {"words": [
        w("Hola", 0.0, 0.4), w(" ", 0.4, 0.5, kind="spacing"), w("amigos", 0.5, 1.0),
        w("Gol", 1.2, 1.6, speaker="speaker_1"),
    ]}
    segs = normalize(raw)
    assert len(segs) == 2
    assert segs[0]["text"] == "Hola amigos"
    assert segs[0]["speaker"] == "speaker_0"
    assert segs[0]["t_start"] == 0.0
    assert segs[0]["t_end"] == 1.0
    assert segs[1]["speaker"] == "speaker_1"


def test_splits_on_long_gap():
    raw = {"words": [w("uno", 0.0, 0.5), w("dos", 5.0, 5.5)]}
    segs = normalize(raw)
    assert len(segs) == 2


def test_audio_event_becomes_own_segment():
    raw = {"words": [
        w("Gol", 0.0, 0.5),
        w("(crowd cheering)", 0.5, 3.0, kind="audio_event"),
        w("increible", 3.1, 3.6),
    ]}
    segs = normalize(raw)
    assert [s["speaker"] for s in segs] == ["speaker_0", "EVENT", "speaker_0"]


def test_empty_response():
    assert normalize({"words": []}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_stt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stt'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/stt.py`:
```python
import time
from pathlib import Path

import httpx

API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MAX_GAP_S = 1.5
MAX_SEGMENT_S = 30.0


def transcribe(audio_path: Path, api_key: str) -> dict:
    data = {
        "model_id": "scribe_v2",
        "language_code": "es",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with open(audio_path, "rb") as f:
                resp = httpx.post(
                    API_URL,
                    headers={"xi-api-key": api_key},
                    data=data,
                    files={"file": (Path(audio_path).name, f, "audio/mpeg")},
                    timeout=httpx.Timeout(1800.0, connect=30.0),
                )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            last_err = e
            time.sleep(5 * 2**attempt)
    raise RuntimeError(f"ElevenLabs transcription failed after 3 attempts: {last_err}")


def _flush(segments: list[dict], cur: dict | None) -> None:
    if cur is not None:
        cur["text"] = " ".join(cur["text"].split())
        segments.append(cur)


def normalize(raw: dict) -> list[dict]:
    segments: list[dict] = []
    cur: dict | None = None
    for word in raw.get("words", []):
        kind = word.get("type", "word")
        if kind == "spacing":
            continue
        if kind == "audio_event":
            _flush(segments, cur)
            cur = None
            segments.append({
                "t_start": word["start"], "t_end": word["end"],
                "speaker": "EVENT", "text": word["text"].strip(),
            })
            continue
        speaker = word.get("speaker_id") or "speaker_0"
        if (
            cur is None
            or cur["speaker"] != speaker
            or word["start"] - cur["t_end"] > MAX_GAP_S
            or word["end"] - cur["t_start"] > MAX_SEGMENT_S
        ):
            _flush(segments, cur)
            cur = {
                "t_start": word["start"], "t_end": word["end"],
                "speaker": speaker, "text": word["text"],
            }
        else:
            cur["t_end"] = word["end"]
            cur["text"] += " " + word["text"]
    _flush(segments, cur)
    return segments
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_stt.py -v`
Expected: 4 passed

- [ ] **Step 5: Live verification against the real API (one cheap call)**

The request/response field names above follow the ElevenLabs docs. Verify them once with a real 30-second clip before the pipeline depends on them.

`backend/scripts/verify_stt.py`:
```python
"""Run once with a real key: .venv\\Scripts\\python scripts/verify_stt.py path\\to\\clip30s.mp3"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.stt import normalize, transcribe

settings = load_settings()
raw = transcribe(Path(sys.argv[1]), settings.elevenlabs_api_key)
Path("stt_raw_sample.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
for seg in normalize(raw)[:10]:
    print(f"[{seg['t_start']:6.1f}-{seg['t_end']:6.1f}] {seg['speaker']}: {seg['text']}")
```

Run it with a 30s Spanish audio clip (extract one from any sports video with `ffmpeg -i in.mp4 -t 30 -vn clip30s.mp3`). If field names differ from the docs (`words`, `start`, `end`, `speaker_id`, `type`), fix `normalize` and its tests to match the saved `stt_raw_sample.json`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/stt.py backend/tests/test_stt.py backend/scripts/verify_stt.py
git commit -m "feat: elevenlabs scribe transcription with diarized normalizer"
```

---

### Task 5: Gemini visual analysis (windows, prompt, parser, client)

**Files:**
- Create: `backend/app/visual.py`
- Test: `backend/tests/test_visual.py`

**Interfaces:**
- Consumes: `Settings.google_api_key`.
- Produces:
  - `compute_windows(duration_s: float, window_s: int = 900) -> list[tuple[int, int]]`
  - `parse_events(text: str, offset_s: float) -> list[dict]` returning `{"t_start", "t_end", "description", "on_screen_text"}` with offset added; tolerates markdown fences and missing keys
  - `analyze_video(video_path: Path, duration_s: float, api_key: str) -> list[dict]` (uploads via File API, waits ACTIVE, analyzes each window with 3 parallel workers, retries each window 3x)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_visual.py`:
```python
from app.visual import compute_windows, parse_events


def test_windows_exact_multiple():
    assert compute_windows(1800, window_s=900) == [(0, 900), (900, 1800)]


def test_windows_with_remainder():
    assert compute_windows(1000, window_s=900) == [(0, 900), (900, 1000)]


def test_windows_short_video():
    assert compute_windows(120.4, window_s=900) == [(0, 121)]


def test_parse_events_strips_fences_and_applies_offset():
    text = """```json
    [{"t_start": 4.0, "t_end": 8.0, "description": "saque inicial", "on_screen_text": "0-0"}]
    ```"""
    events = parse_events(text, offset_s=900)
    assert events == [{
        "t_start": 904.0, "t_end": 908.0,
        "description": "saque inicial", "on_screen_text": "0-0",
    }]


def test_parse_events_tolerates_missing_optional_keys():
    events = parse_events('[{"t_start": 1, "t_end": 2, "description": "gol"}]', 0)
    assert events[0]["on_screen_text"] is None


def test_parse_events_drops_malformed_items():
    events = parse_events('[{"description": "sin tiempo"}, {"t_start": 1, "t_end": 2, "description": "ok"}]', 0)
    assert len(events) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_visual.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.visual'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/visual.py`:
```python
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
WINDOW_S = 900

VISUAL_PROMPT = """Eres un analista de video de deportes en television.
Describe este clip de video segundo a segundo.

Reglas:
- Genera una entrada aproximadamente cada 4 segundos de video.
- Cada entrada describe que pasa en pantalla: jugadas, celebraciones, repeticiones, graficos, anuncios, estudio.
- Lee el texto en pantalla cuando exista (marcador, reloj, nombres, rotulos) y ponlo en on_screen_text.
- Los tiempos t_start y t_end son segundos relativos al inicio de ESTE clip.
- Responde SOLO con un arreglo JSON valido, sin texto adicional.

Formato de cada entrada:
{"t_start": <num>, "t_end": <num>, "description": "<que pasa>", "on_screen_text": "<texto en pantalla o null>"}
"""


def compute_windows(duration_s: float, window_s: int = WINDOW_S) -> list[tuple[int, int]]:
    total = math.ceil(duration_s)
    windows = []
    start = 0
    while start < total:
        end = min(start + window_s, total)
        windows.append((start, end))
        start = end
    return windows


def parse_events(text: str, offset_s: float) -> list[dict]:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    items = json.loads(cleaned)
    events = []
    for item in items:
        if "t_start" not in item or "t_end" not in item or "description" not in item:
            continue
        events.append({
            "t_start": float(item["t_start"]) + offset_s,
            "t_end": float(item["t_end"]) + offset_s,
            "description": str(item["description"]),
            "on_screen_text": item.get("on_screen_text") or None,
        })
    return events


def _upload_and_wait(client: genai.Client, video_path: Path):
    uploaded = client.files.upload(file=str(video_path))
    while uploaded.state.name == "PROCESSING":
        time.sleep(5)
        uploaded = client.files.get(name=uploaded.name)
    if uploaded.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file state: {uploaded.state.name}")
    return uploaded


def _analyze_window(client, uploaded, start: int, end: int) -> list[dict]:
    part = types.Part(
        file_data=types.FileData(file_uri=uploaded.uri, mime_type=uploaded.mime_type),
        video_metadata=types.VideoMetadata(
            start_offset=f"{start}s", end_offset=f"{end}s"
        ),
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=[types.Content(role="user", parts=[part, types.Part(text=VISUAL_PROMPT)])],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return parse_events(resp.text, offset_s=start)
        except Exception as e:
            last_err = e
            time.sleep(10 * 2**attempt)
    raise RuntimeError(f"Gemini window {start}-{end}s failed after 3 attempts: {last_err}")


def analyze_video(video_path: Path, duration_s: float, api_key: str) -> list[dict]:
    client = genai.Client(api_key=api_key)
    uploaded = _upload_and_wait(client, video_path)
    windows = compute_windows(duration_s)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda w: _analyze_window(client, uploaded, *w), windows))
    events = [e for window_events in results for e in window_events]
    events.sort(key=lambda e: e["t_start"])
    return events
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_visual.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/visual.py backend/tests/test_visual.py
git commit -m "feat: gemini chunked visual analysis with window math and json parser"
```

---

### Task 6: Timeline merge and Gemini summarization

**Files:**
- Create: `backend/app/summarize.py`
- Test: `backend/tests/test_summarize.py`

**Interfaces:**
- Consumes: transcript segments (Task 4 shape), visual events (Task 5 shape).
- Produces:
  - `merge_timeline(segments: list[dict], events: list[dict]) -> list[dict]` where each item gains `"kind": "speech" | "event" | "visual"` and list is sorted by `t_start`
  - `bucket_by_minute(merged: list[dict]) -> dict[int, list[dict]]`
  - `render_minute_block(minute: int, items: list[dict]) -> str` (text lines with `[MM:SS]` prefixes)
  - `summarize_minutes(merged: list[dict], duration_s: float, api_key: str) -> list[dict]` (`{"minute_index", "summary"}`; batches of 10 minutes per Gemini text call)
  - `summarize_video(minute_summaries: list[dict], segments: list[dict], api_key: str) -> dict` with keys `sport, teams, event_type, summary, key_moments` (each moment `{"t", "title", "description"}`); also maps anonymous speaker labels to real names when the transcript reveals them, returned as `speaker_names: dict[str, str]`
- Uses `fmt_ts` from Task 8 module `app.timefmt` (defined in this task to avoid forward dependency).
- Also create `backend/app/timefmt.py` here with `fmt_ts(seconds: float) -> str`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_summarize.py`:
```python
from app.summarize import bucket_by_minute, merge_timeline, render_minute_block
from app.timefmt import fmt_ts


def test_fmt_ts():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65.4) == "01:05"
    assert fmt_ts(3725) == "1:02:05"


def test_merge_orders_and_tags():
    segs = [{"t_start": 5.0, "t_end": 6.0, "speaker": "speaker_0", "text": "gol"}]
    evs = [{"t_start": 1.0, "t_end": 4.0, "description": "saque", "on_screen_text": None}]
    merged = merge_timeline(segs, evs)
    assert [m["kind"] for m in merged] == ["visual", "speech"]


def test_merge_tags_audio_events():
    segs = [{"t_start": 2.0, "t_end": 3.0, "speaker": "EVENT", "text": "(crowd)"}]
    merged = merge_timeline(segs, [])
    assert merged[0]["kind"] == "event"


def test_bucket_by_minute():
    merged = [
        {"t_start": 10.0, "kind": "speech", "t_end": 11, "speaker": "s", "text": "a"},
        {"t_start": 70.0, "kind": "speech", "t_end": 71, "speaker": "s", "text": "b"},
        {"t_start": 80.0, "kind": "speech", "t_end": 81, "speaker": "s", "text": "c"},
    ]
    buckets = bucket_by_minute(merged)
    assert sorted(buckets) == [0, 1]
    assert len(buckets[1]) == 2


def test_render_minute_block_contains_timestamps_and_text():
    items = [{"t_start": 70.0, "t_end": 72.0, "kind": "speech", "speaker": "speaker_1", "text": "que golazo"}]
    block = render_minute_block(1, items)
    assert "[01:10]" in block
    assert "speaker_1" in block
    assert "que golazo" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_summarize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`backend/app/timefmt.py`:
```python
def fmt_ts(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
```

`backend/app/summarize.py`:
```python
import json
import re
import time

from google import genai
from google.genai import types

from app.timefmt import fmt_ts

MODEL = "gemini-3.5-flash"
MINUTES_PER_CALL = 10

MINUTE_PROMPT = """Eres un documentalista de transmisiones deportivas.
Te doy la linea de tiempo (transcripcion diarizada + eventos visuales) de varios minutos de una transmision.
Escribe UN resumen por minuto, en espanol, 1 a 3 frases, concreto, con nombres cuando existan.
Responde SOLO JSON: [{"minute_index": <int>, "summary": "<resumen>"}]
"""

VIDEO_PROMPT = """Eres un documentalista de transmisiones deportivas.
Con los resumenes por minuto y el inicio de la transcripcion, devuelve SOLO este JSON:
{
 "sport": "<deporte>",
 "teams": "<equipos o participantes, o null>",
 "event_type": "<partido | programa de estudio | resumen | otro>",
 "summary": "<resumen global de 3 a 6 frases en espanol>",
 "key_moments": [{"t": <segundos>, "title": "<titulo corto>", "description": "<1 frase>"}],
 "speaker_names": {"<speaker_id>": "<nombre real si la transcripcion lo revela>"}
}
Incluye 5 a 15 key_moments (goles, jugadas claves, celebraciones, momentos emotivos del narrador).
En speaker_names incluye SOLO los speaker_id cuyo nombre real se deduce del propio dialogo.
"""


def merge_timeline(segments: list[dict], events: list[dict]) -> list[dict]:
    merged = []
    for s in segments:
        kind = "event" if s["speaker"] == "EVENT" else "speech"
        merged.append({**s, "kind": kind})
    for e in events:
        merged.append({**e, "kind": "visual"})
    merged.sort(key=lambda x: x["t_start"])
    return merged


def bucket_by_minute(merged: list[dict]) -> dict[int, list[dict]]:
    buckets: dict[int, list[dict]] = {}
    for item in merged:
        buckets.setdefault(int(item["t_start"] // 60), []).append(item)
    return buckets


def render_minute_block(minute: int, items: list[dict]) -> str:
    lines = [f"== Minuto {minute} =="]
    for it in items:
        ts = fmt_ts(it["t_start"])
        if it["kind"] == "speech":
            lines.append(f"[{ts}] {it['speaker']}: {it['text']}")
        elif it["kind"] == "event":
            lines.append(f"[{ts}] AUDIO: {it['text']}")
        else:
            screen = f" | pantalla: {it['on_screen_text']}" if it.get("on_screen_text") else ""
            lines.append(f"[{ts}] VISUAL: {it['description']}{screen}")
    return "\n".join(lines)


def _json_call(client: genai.Client, prompt: str, payload: str):
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt + "\n\n" + payload,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", resp.text.strip())
            return json.loads(cleaned)
        except Exception as e:
            last_err = e
            time.sleep(10 * 2**attempt)
    raise RuntimeError(f"Gemini summarize failed after 3 attempts: {last_err}")


def summarize_minutes(merged: list[dict], duration_s: float, api_key: str) -> list[dict]:
    client = genai.Client(api_key=api_key)
    buckets = bucket_by_minute(merged)
    all_minutes = sorted(buckets)
    results: list[dict] = []
    for i in range(0, len(all_minutes), MINUTES_PER_CALL):
        chunk = all_minutes[i : i + MINUTES_PER_CALL]
        payload = "\n\n".join(render_minute_block(m, buckets[m]) for m in chunk)
        items = _json_call(client, MINUTE_PROMPT, payload)
        results.extend(
            {"minute_index": int(it["minute_index"]), "summary": str(it["summary"])}
            for it in items
            if "minute_index" in it and "summary" in it
        )
    results.sort(key=lambda r: r["minute_index"])
    return results


def summarize_video(minute_summaries: list[dict], segments: list[dict], api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    minutes_text = "\n".join(f"Minuto {m['minute_index']}: {m['summary']}" for m in minute_summaries)
    head = "\n".join(
        f"[{fmt_ts(s['t_start'])}] {s['speaker']}: {s['text']}" for s in segments[:200]
    )
    payload = f"RESUMENES POR MINUTO:\n{minutes_text}\n\nINICIO DE TRANSCRIPCION:\n{head}"
    data = _json_call(client, VIDEO_PROMPT, payload)
    data.setdefault("key_moments", [])
    data.setdefault("speaker_names", {})
    data.setdefault("teams", None)
    return data
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_summarize.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/summarize.py backend/app/timefmt.py backend/tests/test_summarize.py
git commit -m "feat: timeline merge, minute summaries, video summary via gemini"
```

---

### Task 7: Pipeline orchestrator (resumable stages)

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 2-6.
- Produces: `run_pipeline(video_id: str, settings: Settings, db_path: Path) -> None`.
  - Artifacts under `settings.data_dir / "videos" / video_id`: `source.mp4` (already there from upload), `audio.mp3`, `transcript.json` (raw API), `segments.json` (normalized, speaker names applied), `visual.json`, `summary.json`, `records.json` (final export).
  - A stage runs only if its artifact is missing. Status updated per stage. On exception: status `failed` with error text, then re-raise.
  - Speaker rename: after `summarize_video`, apply `speaker_names` mapping to segments before persisting.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_pipeline.py`:
```python
import json

from app import db, pipeline
from app.config import Settings


def make_env(tmp_path, tiny_clip):
    settings = Settings("k1", "k2", "k3", tmp_path / "data")
    vdir = settings.data_dir / "videos" / "v1"
    vdir.mkdir(parents=True)
    (vdir / "source.mp4").write_bytes(tiny_clip.read_bytes())
    db_path = settings.data_dir / "vault.db"
    conn = db.connect(db_path)
    db.init_db(conn)
    db.create_video(conn, "v1", "test", "source.mp4")
    return settings, db_path, conn


FAKE_RAW = {"words": [
    {"text": "Hola", "start": 0.0, "end": 0.4, "speaker_id": "speaker_0", "type": "word"},
    {"text": "Martinoli", "start": 0.5, "end": 1.0, "speaker_id": "speaker_1", "type": "word"},
]}
FAKE_VISUAL = [{"t_start": 0.0, "t_end": 2.0, "description": "estudio", "on_screen_text": None}]
FAKE_MINUTES = [{"minute_index": 0, "summary": "saludos iniciales"}]
FAKE_SUMMARY = {
    "sport": "futbol", "teams": "A vs B", "event_type": "partido",
    "summary": "resumen global", "speaker_names": {"speaker_1": "Martinoli"},
    "key_moments": [{"t": 0.5, "title": "saludo", "description": "arranca"}],
}


def patch_apis(monkeypatch, calls):
    def fake_transcribe(path, key):
        calls.append("transcribe")
        return FAKE_RAW

    monkeypatch.setattr(pipeline.stt, "transcribe", fake_transcribe)
    monkeypatch.setattr(pipeline.visual, "analyze_video", lambda p, d, k: FAKE_VISUAL)
    monkeypatch.setattr(pipeline.summarize, "summarize_minutes", lambda m, d, k: FAKE_MINUTES)
    monkeypatch.setattr(pipeline.summarize, "summarize_video", lambda m, s, k: FAKE_SUMMARY)


def test_pipeline_end_to_end_and_resume(tmp_path, tiny_clip, monkeypatch):
    settings, db_path, conn = make_env(tmp_path, tiny_clip)
    calls: list[str] = []
    patch_apis(monkeypatch, calls)

    pipeline.run_pipeline("v1", settings, db_path)

    row = db.get_video(conn, "v1")
    assert row["status"] == "ready"
    assert row["sport"] == "futbol"
    rec = db.get_records(conn, "v1")
    speakers = {s["speaker"] for s in rec["transcript_segments"]}
    assert "Martinoli" in speakers  # rename applied
    assert rec["visual_events"] and rec["minute_summaries"] and rec["key_moments"]
    vdir = settings.data_dir / "videos" / "v1"
    assert (vdir / "records.json").exists()
    assert calls == ["transcribe"]

    # second run skips the transcription stage (artifact exists)
    pipeline.run_pipeline("v1", settings, db_path)
    assert calls == ["transcribe"]


def test_pipeline_failure_sets_status(tmp_path, tiny_clip, monkeypatch):
    settings, db_path, conn = make_env(tmp_path, tiny_clip)

    def boom(path, key):
        raise RuntimeError("stt down")

    monkeypatch.setattr(pipeline.stt, "transcribe", boom)
    try:
        pipeline.run_pipeline("v1", settings, db_path)
    except RuntimeError:
        pass
    row = db.get_video(conn, "v1")
    assert row["status"] == "failed"
    assert "stt down" in row["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/pipeline.py`:
```python
import json
from pathlib import Path

from app import db, media, stt, summarize, visual
from app.config import Settings


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def run_pipeline(video_id: str, settings: Settings, db_path: Path) -> None:
    conn = db.connect(db_path)
    vdir = settings.data_dir / "videos" / video_id
    source = vdir / "source.mp4"
    try:
        row = db.get_video(conn, video_id)
        if row is None:
            raise RuntimeError(f"unknown video: {video_id}")

        duration = row["duration_s"]
        if duration is None:
            duration = media.probe_duration(source)
            db.set_video_meta(conn, video_id, duration_s=duration)

        audio = vdir / "audio.mp3"
        if not audio.exists():
            db.set_status(conn, video_id, "extracting_audio")
            media.extract_audio(source, audio)

        raw_path = vdir / "transcript.json"
        if not raw_path.exists():
            db.set_status(conn, video_id, "transcribing")
            raw = stt.transcribe(audio, settings.elevenlabs_api_key)
            _write_json(raw_path, raw)
        segments = stt.normalize(_read_json(raw_path))

        visual_path = vdir / "visual.json"
        if not visual_path.exists():
            db.set_status(conn, video_id, "analyzing_visuals")
            events = visual.analyze_video(source, duration, settings.google_api_key)
            _write_json(visual_path, events)
        events = _read_json(visual_path)

        summary_path = vdir / "summary.json"
        if not summary_path.exists():
            db.set_status(conn, video_id, "summarizing")
            merged = summarize.merge_timeline(segments, events)
            minutes = summarize.summarize_minutes(merged, duration, settings.google_api_key)
            info = summarize.summarize_video(minutes, segments, settings.google_api_key)
            _write_json(summary_path, {"minutes": minutes, "info": info})
        summary = _read_json(summary_path)
        minutes, info = summary["minutes"], summary["info"]

        names = info.get("speaker_names") or {}
        for seg in segments:
            seg["speaker"] = names.get(seg["speaker"], seg["speaker"])
        _write_json(vdir / "segments.json", segments)

        db.replace_records(conn, video_id, segments, events, minutes, info.get("key_moments", []))
        db.set_video_meta(
            conn, video_id,
            sport=info.get("sport"), teams=info.get("teams"),
            event_type=info.get("event_type"), summary=info.get("summary"),
        )
        _write_json(vdir / "records.json", db.get_records(conn, video_id))
        db.set_status(conn, video_id, "ready")
    except Exception as e:
        db.set_status(conn, video_id, "failed", error=str(e)[:1000])
        raise
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py -v`
Expected: 2 passed. Also run the whole suite: `.venv\Scripts\python -m pytest -v` and expect all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: resumable six-stage pipeline orchestrator"
```

---

### Task 8: Grounded chat (context serialization + Claude streaming)

**Files:**
- Create: `backend/app/chat.py`
- Test: `backend/tests/test_chat.py`

**Interfaces:**
- Consumes: `db.get_records` dict shape (Task 2), `fmt_ts` (Task 6).
- Produces:
  - `serialize_records(records: dict) -> str` (compact Spanish-labeled sections with `[MM:SS]` prefixes)
  - `build_system(records: dict) -> list[dict]` (2 blocks; second block carries `cache_control: {"type": "ephemeral"}`)
  - `stream_chat(api_key: str, records: dict, messages: list[dict])` generator yielding text chunks
  - `CITATION_RE` regex matching `[MM:SS]` and `[H:MM:SS]`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chat.py`:
```python
from app.chat import CITATION_RE, build_system, serialize_records

RECORDS = {
    "video": {"id": "v1", "title": "Final", "duration_s": 130.0, "sport": "futbol",
              "teams": "A vs B", "event_type": "partido", "summary": "gran final"},
    "transcript_segments": [
        {"t_start": 65.0, "t_end": 68.0, "speaker": "Martinoli", "text": "Increible lo que hizo"},
    ],
    "visual_events": [
        {"t_start": 64.0, "t_end": 68.0, "description": "celebracion del gol", "on_screen_text": "1-0"},
    ],
    "minute_summaries": [{"minute_index": 1, "summary": "gol de A"}],
    "key_moments": [{"t": 65.0, "title": "Gol", "description": "gol de cabeza"}],
}


def test_serialize_contains_speakers_timestamps_and_screen_text():
    text = serialize_records(RECORDS)
    assert "[01:05] Martinoli: Increible lo que hizo" in text
    assert "celebracion del gol" in text
    assert "1-0" in text
    assert "Minuto 1: gol de A" in text
    assert "Gol" in text


def test_build_system_caches_the_data_block():
    blocks = build_system(RECORDS)
    assert len(blocks) == 2
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "Martinoli" in blocks[1]["text"]
    assert "[MM:SS]" in blocks[0]["text"]


def test_citation_regex():
    found = CITATION_RE.findall("El gol fue al [01:05] y el festejo al [1:02:05].")
    assert found == [("", "01", "05"), ("1", "02", "05")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_chat.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.chat'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/chat.py`:
```python
import re

import anthropic

from app.timefmt import fmt_ts

MODEL = "claude-opus-4-8"

CITATION_RE = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")

RULES = """Eres el asistente de inteligencia de video de Fox Sports.
Respondes preguntas sobre UNA transmision usando UNICAMENTE los datos estructurados provistos.

Reglas estrictas:
1. Responde solo con informacion presente en los datos. Si no esta, di claramente que no aparece en los datos del video.
2. Cada afirmacion factual lleva su cita de tiempo en formato [MM:SS] o [H:MM:SS], tomada de los datos.
3. Cuando cites lo que alguien dijo, nombra al hablante y cita el momento exacto.
4. Responde en el idioma de la pregunta (espanol o ingles).
5. Se concreto y breve. Nada de relleno."""


def serialize_records(records: dict) -> str:
    v = records["video"]
    parts = [
        f"VIDEO: {v['title']} | deporte: {v.get('sport')} | equipos: {v.get('teams')} | "
        f"tipo: {v.get('event_type')} | duracion: {fmt_ts(v.get('duration_s') or 0)}",
        f"RESUMEN GLOBAL: {v.get('summary')}",
        "MOMENTOS CLAVE:",
    ]
    parts += [f"[{fmt_ts(k['t'])}] {k['title']}: {k['description']}" for k in records["key_moments"]]
    parts.append("RESUMEN POR MINUTO:")
    parts += [f"Minuto {m['minute_index']}: {m['summary']}" for m in records["minute_summaries"]]
    parts.append("TRANSCRIPCION DIARIZADA:")
    parts += [
        f"[{fmt_ts(s['t_start'])}] {s['speaker']}: {s['text']}"
        for s in records["transcript_segments"]
    ]
    parts.append("EVENTOS VISUALES:")
    for e in records["visual_events"]:
        screen = f" | pantalla: {e['on_screen_text']}" if e.get("on_screen_text") else ""
        parts.append(f"[{fmt_ts(e['t_start'])}] {e['description']}{screen}")
    return "\n".join(parts)


def build_system(records: dict) -> list[dict]:
    return [
        {"type": "text", "text": RULES},
        {
            "type": "text",
            "text": "DATOS ESTRUCTURADOS DEL VIDEO:\n" + serialize_records(records),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def stream_chat(api_key: str, records: dict, messages: list[dict]):
    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=build_system(records),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_chat.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/chat.py backend/tests/test_chat.py
git commit -m "feat: grounded claude chat with cached context and citation rules"
```

---

### Task 9: FastAPI endpoints (upload, status, records, range stream, chat)

**Files:**
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces HTTP API:
  - `POST /api/videos` multipart field `file` -> `{"id": "<uuid>"}`, 400 on bad extension/duration; pipeline started via `BackgroundTasks`
  - `GET /api/videos/{id}/status` -> `{"id", "status", "error", "duration_s"}`
  - `GET /api/videos/{id}` -> full records dict
  - `GET /api/videos/{id}/stream` -> video bytes, supports `Range` (206)
  - `POST /api/videos/{id}/chat` body `{"messages": [{"role", "content"}]}` -> streamed plain text
- App state: `app.state.settings`, `app.state.db_path`. Test override via `create_app(settings, db_path, run_pipeline_fn)`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api.py`:
```python
from fastapi.testclient import TestClient

from app import db
from app.config import Settings
from app.main import create_app


def make_client(tmp_path, tiny_clip=None):
    settings = Settings("k1", "k2", "k3", tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = settings.data_dir / "vault.db"
    started: list[str] = []
    app = create_app(settings, db_path, run_pipeline_fn=lambda vid: started.append(vid))
    return TestClient(app), settings, db_path, started


def test_upload_starts_pipeline(tmp_path, tiny_clip):
    client, settings, db_path, started = make_client(tmp_path)
    with open(tiny_clip, "rb") as f:
        resp = client.post("/api/videos", files={"file": ("partido.mp4", f, "video/mp4")})
    assert resp.status_code == 200
    vid = resp.json()["id"]
    assert started == [vid]
    assert (settings.data_dir / "videos" / vid / "source.mp4").exists()
    status = client.get(f"/api/videos/{vid}/status").json()
    assert status["status"] == "uploaded"
    assert status["duration_s"] > 0


def test_upload_rejects_bad_extension(tmp_path):
    client, *_ = make_client(tmp_path)
    resp = client.post("/api/videos", files={"file": ("nota.txt", b"hola", "text/plain")})
    assert resp.status_code == 400


def test_records_and_404(tmp_path):
    client, settings, db_path, _ = make_client(tmp_path)
    assert client.get("/api/videos/nope").status_code == 404
    conn = db.connect(db_path)
    db.init_db(conn)
    db.create_video(conn, "v1", "t", "source.mp4")
    body = client.get("/api/videos/v1").json()
    assert body["video"]["id"] == "v1"
    assert body["transcript_segments"] == []


def test_stream_supports_range(tmp_path, tiny_clip):
    client, settings, db_path, _ = make_client(tmp_path)
    with open(tiny_clip, "rb") as f:
        vid = client.post("/api/videos", files={"file": ("a.mp4", f, "video/mp4")}).json()["id"]
    full = client.get(f"/api/videos/{vid}/stream")
    assert full.status_code == 200
    partial = client.get(f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206
    assert len(partial.content) == 100
    assert partial.headers["Content-Range"].startswith("bytes 0-99/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/main.py`:
```python
import shutil
import uuid
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app import chat, db, media, pipeline
from app.config import Settings, load_settings

ALLOWED_EXT = {".mp4", ".mov", ".mkv"}
MAX_DURATION_S = 3 * 3600
CHUNK = 1024 * 1024


def create_app(settings: Settings, db_path: Path,
               run_pipeline_fn: Callable[[str], None] | None = None) -> FastAPI:
    app = FastAPI(title="Fox Video Intelligence")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    conn = db.connect(db_path)
    db.init_db(conn)
    conn.close()

    if run_pipeline_fn is None:
        def run_pipeline_fn(video_id: str) -> None:
            pipeline.run_pipeline(video_id, settings, db_path)

    def get_conn():
        return db.connect(db_path)

    @app.post("/api/videos")
    async def upload_video(file: UploadFile, background_tasks: BackgroundTasks):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(400, f"unsupported file type: {ext or 'none'}")
        video_id = uuid.uuid4().hex[:12]
        vdir = settings.data_dir / "videos" / video_id
        vdir.mkdir(parents=True, exist_ok=True)
        dest = vdir / "source.mp4"
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out)
        try:
            duration = media.probe_duration(dest)
        except media.MediaError as e:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, f"not a readable video: {e}")
        if duration > MAX_DURATION_S:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "video longer than 3 hours")
        conn = get_conn()
        db.create_video(conn, video_id, Path(file.filename).stem, "source.mp4")
        db.set_video_meta(conn, video_id, duration_s=duration)
        conn.close()
        background_tasks.add_task(run_pipeline_fn, video_id)
        return {"id": video_id}

    @app.get("/api/videos/{video_id}/status")
    def status(video_id: str):
        conn = get_conn()
        row = db.get_video(conn, video_id)
        conn.close()
        if row is None:
            raise HTTPException(404, "video not found")
        return {"id": row["id"], "status": row["status"],
                "error": row["error"], "duration_s": row["duration_s"]}

    @app.get("/api/videos/{video_id}")
    def records(video_id: str):
        conn = get_conn()
        rec = db.get_records(conn, video_id)
        conn.close()
        if rec["video"] is None:
            raise HTTPException(404, "video not found")
        return rec

    @app.get("/api/videos/{video_id}/stream")
    def stream_video(video_id: str, request: Request):
        path = settings.data_dir / "videos" / video_id / "source.mp4"
        if not path.exists():
            raise HTTPException(404, "video file not found")
        file_size = path.stat().st_size
        range_header = request.headers.get("range")
        start, end = 0, file_size - 1
        status_code = 200
        if range_header and range_header.startswith("bytes="):
            spec = range_header.removeprefix("bytes=").split("-")
            if spec[0]:
                start = int(spec[0])
            if len(spec) > 1 and spec[1]:
                end = min(int(spec[1]), file_size - 1)
            status_code = 206

        def iterator():
            remaining = end - start + 1
            with open(path, "rb") as f:
                f.seek(start)
                while remaining > 0:
                    data = f.read(min(CHUNK, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return StreamingResponse(iterator(), status_code=status_code,
                                 media_type="video/mp4", headers=headers)

    @app.post("/api/videos/{video_id}/chat")
    async def chat_endpoint(video_id: str, body: dict):
        conn = get_conn()
        rec = db.get_records(conn, video_id)
        conn.close()
        if rec["video"] is None:
            raise HTTPException(404, "video not found")
        if rec["video"]["status"] != "ready":
            raise HTTPException(409, "video is still processing")
        messages = body.get("messages", [])
        if not messages:
            raise HTTPException(400, "messages required")
        gen = chat.stream_chat(settings.anthropic_api_key, rec, messages)
        return StreamingResponse(gen, media_type="text/plain; charset=utf-8")

    return app


def build() -> FastAPI:
    settings = load_settings()
    return create_app(settings, settings.data_dir / "vault.db")
```

Run server (manual): `cd backend && .venv\Scripts\uvicorn app.main:build --factory --reload --port 8000`

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv\Scripts\python -m pytest tests/test_api.py -v`
Expected: 4 passed. Full suite green: `.venv\Scripts\python -m pytest`

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: fastapi endpoints for upload, status, records, range stream, chat"
```

---

### Task 10: Frontend scaffold + time/citation utilities

**Files:**
- Create: `frontend/` via Vite scaffold
- Create: `frontend/src/lib/time.ts`
- Create: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/time.test.ts`

**Interfaces:**
- Produces:
  - `fmtTs(seconds: number): string` (`MM:SS` / `H:MM:SS`)
  - `splitCitations(text: string): Array<{kind: "text", value: string} | {kind: "cite", value: string, seconds: number}>`
  - `api.uploadVideo(file: File): Promise<{id: string}>`
  - `api.getStatus(id)`, `api.getRecords(id)`, `api.streamUrl(id)`, `api.chat(id, messages, onChunk)` (fetch streaming reader)
  - `API_BASE = "http://localhost:8000"`

- [ ] **Step 1: Scaffold**

```bash
cd "c:\Users\bcama\OneDrive\Desktop\Fox Sports Project"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D vitest
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing test**

`frontend/src/lib/time.test.ts`:
```typescript
import { describe, expect, it } from "vitest";
import { fmtTs, splitCitations } from "./time";

describe("fmtTs", () => {
  it("formats minutes and hours", () => {
    expect(fmtTs(0)).toBe("00:00");
    expect(fmtTs(65)).toBe("01:05");
    expect(fmtTs(3725)).toBe("1:02:05");
  });
});

describe("splitCitations", () => {
  it("splits text and citations with seconds", () => {
    const parts = splitCitations("Gol al [01:05] y festejo al [1:02:05].");
    expect(parts).toEqual([
      { kind: "text", value: "Gol al " },
      { kind: "cite", value: "[01:05]", seconds: 65 },
      { kind: "text", value: " y festejo al " },
      { kind: "cite", value: "[1:02:05]", seconds: 3725 },
      { kind: "text", value: "." },
    ]);
  });

  it("returns plain text when no citations", () => {
    expect(splitCitations("hola")).toEqual([{ kind: "text", value: "hola" }]);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL, cannot resolve `./time`

- [ ] **Step 4: Write implementation**

`frontend/src/lib/time.ts`:
```typescript
export function fmtTs(seconds: number): string {
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

const CITE_RE = /\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]/g;

export type Part =
  | { kind: "text"; value: string }
  | { kind: "cite"; value: string; seconds: number };

export function splitCitations(text: string): Part[] {
  const parts: Part[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) parts.push({ kind: "text", value: text.slice(last, idx) });
    const h = m[1] ? parseInt(m[1], 10) : 0;
    const seconds = h * 3600 + parseInt(m[2], 10) * 60 + parseInt(m[3], 10);
    parts.push({ kind: "cite", value: m[0], seconds });
    last = idx + m[0].length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}
```

`frontend/src/lib/api.ts`:
```typescript
export const API_BASE = "http://localhost:8000";

export type Status = {
  id: string;
  status: string;
  error: string | null;
  duration_s: number | null;
};

export type Records = {
  video: {
    id: string; title: string; duration_s: number; sport: string | null;
    teams: string | null; event_type: string | null; summary: string | null;
    status: string;
  };
  transcript_segments: { id: number; t_start: number; t_end: number; speaker: string; text: string }[];
  visual_events: { id: number; t_start: number; t_end: number; description: string; on_screen_text: string | null }[];
  minute_summaries: { id: number; minute_index: number; summary: string }[];
  key_moments: { id: number; t: number; title: string; description: string }[];
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

async function ok(resp: Response): Promise<Response> {
  if (!resp.ok) throw new Error((await resp.text()) || `HTTP ${resp.status}`);
  return resp;
}

export async function uploadVideo(file: File): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  const resp = await ok(await fetch(`${API_BASE}/api/videos`, { method: "POST", body: form }));
  return resp.json();
}

export async function getStatus(id: string): Promise<Status> {
  return (await ok(await fetch(`${API_BASE}/api/videos/${id}/status`))).json();
}

export async function getRecords(id: string): Promise<Records> {
  return (await ok(await fetch(`${API_BASE}/api/videos/${id}`))).json();
}

export function streamUrl(id: string): string {
  return `${API_BASE}/api/videos/${id}/stream`;
}

export async function chat(
  id: string,
  messages: ChatMessage[],
  onChunk: (text: string) => void,
): Promise<void> {
  const resp = await ok(
    await fetch(`${API_BASE}/api/videos/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    }),
  );
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
}
```

- [ ] **Step 5: Run tests, verify pass**

Run: `npm test`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: frontend scaffold with time and api utilities"
```

---

### Task 11: App state machine + Upload and Processing views

**Files:**
- Modify: `frontend/src/App.tsx` (replace scaffold content)
- Create: `frontend/src/components/UploadZone.tsx`
- Create: `frontend/src/components/ProcessingView.tsx`
- Modify: `frontend/src/index.css` (replace with app styles)
- Delete: `frontend/src/App.css`

**Interfaces:**
- Consumes: `uploadVideo`, `getStatus`, `getRecords` from Task 10.
- Produces: `App` renders `UploadZone` -> `ProcessingView` (poll status every 2s) -> `Workspace` (Task 12; until then render a placeholder `<div>ready</div>`).
- Stage labels map: `uploaded/extracting_audio -> "Preparando audio"`, `transcribing -> "Transcribiendo con hablantes"`, `analyzing_visuals -> "Analizando video"`, `summarizing -> "Generando resumenes"`, `ready -> done`, `failed -> show error`.

- [ ] **Step 1: Write the code**

`frontend/src/App.tsx`:
```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { getRecords, getStatus, uploadVideo, type Records } from "./lib/api";
import UploadZone from "./components/UploadZone";
import ProcessingView from "./components/ProcessingView";

type Phase =
  | { name: "upload" }
  | { name: "processing"; id: string; status: string; error: string | null }
  | { name: "workspace"; id: string; records: Records };

export default function App() {
  const [phase, setPhase] = useState<Phase>({ name: "upload" });
  const pollRef = useRef<number | null>(null);

  const startPolling = useCallback((id: string) => {
    const tick = async () => {
      try {
        const s = await getStatus(id);
        if (s.status === "ready") {
          if (pollRef.current) window.clearInterval(pollRef.current);
          const records = await getRecords(id);
          setPhase({ name: "workspace", id, records });
        } else {
          setPhase({ name: "processing", id, status: s.status, error: s.error });
          if (s.status === "failed" && pollRef.current) window.clearInterval(pollRef.current);
        }
      } catch {
        /* transient poll error: keep polling */
      }
    };
    tick();
    pollRef.current = window.setInterval(tick, 2000);
  }, []);

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  const onFile = async (file: File) => {
    const { id } = await uploadVideo(file);
    setPhase({ name: "processing", id, status: "uploaded", error: null });
    startPolling(id);
  };

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">FOX <b>VIDEO INTELLIGENCE</b></span>
      </header>
      {phase.name === "upload" && <UploadZone onFile={onFile} />}
      {phase.name === "processing" && (
        <ProcessingView status={phase.status} error={phase.error} />
      )}
      {phase.name === "workspace" && <div>ready</div>}
    </div>
  );
}
```

`frontend/src/components/UploadZone.tsx`:
```tsx
import { useRef, useState } from "react";

export default function UploadZone({ onFile }: { onFile: (f: File) => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handle = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
      setBusy(false);
    }
  };

  return (
    <main className="upload">
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); }}
        onClick={() => inputRef.current?.click()}
      >
        <h1>Sube una transmision</h1>
        <p>MP4, MOV o MKV. Maximo 3 horas.</p>
        <p className="hint">{busy ? "Subiendo..." : "Arrastra el archivo o haz clic"}</p>
        {error && <p className="error">{error}</p>}
        <input
          ref={inputRef} type="file" accept=".mp4,.mov,.mkv" hidden
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </div>
    </main>
  );
}
```

`frontend/src/components/ProcessingView.tsx`:
```tsx
const STAGES = [
  { keys: ["uploaded", "extracting_audio"], label: "Preparando audio" },
  { keys: ["transcribing"], label: "Transcribiendo con hablantes" },
  { keys: ["analyzing_visuals"], label: "Analizando video cuadro a cuadro" },
  { keys: ["summarizing"], label: "Generando resumenes" },
];

export default function ProcessingView({ status, error }: { status: string; error: string | null }) {
  const activeIdx = STAGES.findIndex((s) => s.keys.includes(status));
  return (
    <main className="processing">
      <h1>Procesando la transmision</h1>
      <ol>
        {STAGES.map((s, i) => (
          <li
            key={s.label}
            className={
              status === "failed" ? "" : i < activeIdx ? "done" : i === activeIdx ? "active" : ""
            }
          >
            {s.label}
          </li>
        ))}
      </ol>
      {status === "failed" && <p className="error">Fallo el procesamiento: {error}</p>}
    </main>
  );
}
```

`frontend/src/index.css` (replace file):
```css
:root {
  --bg: #0b0e14;
  --panel: #131826;
  --line: #232a3d;
  --text: #e8ecf4;
  --muted: #8b94ab;
  --accent: #f5c518;
  --accent2: #2f6fed;
  font-family: "Segoe UI", system-ui, sans-serif;
}
* { box-sizing: border-box; margin: 0; }
body { background: var(--bg); color: var(--text); }
.app { min-height: 100vh; display: flex; flex-direction: column; }
.topbar { padding: 14px 24px; border-bottom: 1px solid var(--line); letter-spacing: 2px; }
.brand b { color: var(--accent); }
.upload, .processing { flex: 1; display: grid; place-items: center; padding: 24px; }
.dropzone {
  border: 2px dashed var(--line); border-radius: 12px; padding: 64px 96px;
  text-align: center; cursor: pointer; background: var(--panel);
}
.dropzone:hover { border-color: var(--accent); }
.hint { color: var(--muted); margin-top: 12px; }
.error { color: #ff6b6b; margin-top: 12px; }
.processing ol { margin-top: 24px; display: grid; gap: 12px; list-style: none; }
.processing li { color: var(--muted); padding-left: 28px; position: relative; }
.processing li::before { content: "○"; position: absolute; left: 0; }
.processing li.done { color: var(--text); }
.processing li.done::before { content: "●"; color: var(--accent); }
.processing li.active { color: var(--accent); }
.processing li.active::before { content: "◐"; animation: spin 1.2s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }
```

Also delete `frontend/src/App.css` and remove its import from `App.tsx` (already absent above). In `frontend/src/main.tsx` keep the default `index.css` import.

- [ ] **Step 2: Manual verification**

Run backend (`uvicorn app.main:build --factory --port 8000`) and frontend (`npm run dev`). Open http://localhost:5173, upload the tiny test clip. Expect the processing checklist to animate; with real keys it reaches ready, without keys the backend fails and the error shows.

- [ ] **Step 3: Run frontend tests, verify pass**

Run: `npm test`
Expected: pass (time.test.ts unaffected)

- [ ] **Step 4: Commit**

```bash
git add frontend/src
git commit -m "feat: upload and processing views with status polling"
```

---

### Task 12: Workspace with video player and synced data scroller

**Files:**
- Create: `frontend/src/components/Workspace.tsx`
- Create: `frontend/src/components/DataScroller.tsx`
- Modify: `frontend/src/App.tsx` (replace the `ready` placeholder)
- Modify: `frontend/src/index.css` (append workspace styles)

**Interfaces:**
- Consumes: `Records`, `streamUrl`, `fmtTs`.
- Produces:
  - `Workspace({ id, records })` owns a `videoRef` and `currentTime` state; passes `seek(seconds)` down.
  - `DataScroller({ records, currentTime, onSeek })` with tabs Transcript | Visual | Momentos; auto-scrolls the item whose `t_start <= currentTime < t_end` (moments: nearest previous) into view; clicking an item seeks.
  - Chat panel slot rendered below (placeholder until Task 13: `<div className="chatpanel" />`).

- [ ] **Step 1: Write the code**

`frontend/src/components/Workspace.tsx`:
```tsx
import { useRef, useState } from "react";
import { streamUrl, type Records } from "../lib/api";
import DataScroller from "./DataScroller";

export default function Workspace({ id, records }: { id: string; records: Records }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);

  const seek = (seconds: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = seconds;
    v.play().catch(() => {});
  };

  return (
    <main className="workspace">
      <section className="stage">
        <video
          ref={videoRef}
          src={streamUrl(id)}
          controls
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        />
        <div className="videometa">
          <h2>{records.video.title}</h2>
          <p className="muted">
            {records.video.sport} {records.video.teams ? `| ${records.video.teams}` : ""}
          </p>
          <p>{records.video.summary}</p>
        </div>
      </section>
      <DataScroller records={records} currentTime={currentTime} onSeek={seek} />
      <div className="chatslot" data-seek-target id={`chat-${id}`} />
    </main>
  );
}
```

`frontend/src/components/DataScroller.tsx`:
```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import type { Records } from "../lib/api";
import { fmtTs } from "../lib/time";

type Tab = "transcript" | "visual" | "moments";

type Item = { key: string; t: number; end: number; head: string; body: string };

export default function DataScroller({
  records, currentTime, onSeek,
}: { records: Records; currentTime: number; onSeek: (s: number) => void }) {
  const [tab, setTab] = useState<Tab>("transcript");
  const listRef = useRef<HTMLDivElement>(null);

  const items: Item[] = useMemo(() => {
    if (tab === "transcript") {
      return records.transcript_segments.map((s) => ({
        key: `t${s.id}`, t: s.t_start, end: s.t_end, head: s.speaker, body: s.text,
      }));
    }
    if (tab === "visual") {
      return records.visual_events.map((e) => ({
        key: `v${e.id}`, t: e.t_start, end: e.t_end,
        head: e.on_screen_text ?? "", body: e.description,
      }));
    }
    return records.key_moments.map((k) => ({
      key: `m${k.id}`, t: k.t, end: k.t + 1, head: k.title, body: k.description,
    }));
  }, [tab, records]);

  const activeIdx = useMemo(() => {
    let idx = -1;
    for (let i = 0; i < items.length; i++) {
      if (items[i].t <= currentTime) idx = i;
      else break;
    }
    return idx;
  }, [items, currentTime]);

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-idx="${activeIdx}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIdx]);

  return (
    <aside className="scroller">
      <nav className="tabs">
        {(["transcript", "visual", "moments"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t === "transcript" ? "Transcripcion" : t === "visual" ? "Visual" : "Momentos"}
          </button>
        ))}
      </nav>
      <div className="list" ref={listRef}>
        {items.map((it, i) => (
          <button
            key={it.key}
            data-idx={i}
            className={`item ${i === activeIdx ? "active" : ""}`}
            onClick={() => onSeek(it.t)}
          >
            <span className="ts">{fmtTs(it.t)}</span>
            <span className="content">
              {it.head && <b>{it.head} </b>}
              {it.body}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
```

`frontend/src/App.tsx`, replace the placeholder line:
```tsx
{phase.name === "workspace" && <Workspace id={phase.id} records={phase.records} />}
```
and add `import Workspace from "./components/Workspace";`.

Append to `frontend/src/index.css`:
```css
.workspace {
  flex: 1; display: grid; gap: 16px; padding: 16px;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 1fr);
  grid-template-rows: minmax(0, 1fr) 320px;
  grid-template-areas: "stage scroller" "chat chat";
  height: calc(100vh - 49px);
}
.stage { grid-area: stage; min-width: 0; overflow-y: auto; }
.stage video { width: 100%; border-radius: 10px; background: #000; }
.videometa { padding: 12px 4px; }
.muted { color: var(--muted); }
.scroller {
  grid-area: scroller; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; display: flex; flex-direction: column; min-height: 0;
}
.tabs { display: flex; border-bottom: 1px solid var(--line); }
.tabs button {
  flex: 1; padding: 10px; background: none; border: none; color: var(--muted);
  cursor: pointer; font: inherit;
}
.tabs button.on { color: var(--accent); border-bottom: 2px solid var(--accent); }
.list { overflow-y: auto; flex: 1; padding: 8px; }
.item {
  display: flex; gap: 10px; width: 100%; text-align: left; padding: 8px;
  background: none; border: none; color: var(--text); cursor: pointer;
  border-radius: 6px; font: inherit;
}
.item:hover { background: #1a2133; }
.item.active { background: #1c2740; outline: 1px solid var(--accent2); }
.item .ts { color: var(--accent); font-variant-numeric: tabular-nums; flex-shrink: 0; }
.item b { color: var(--accent2); }
.chatslot, .chatpanel { grid-area: chat; }
```

- [ ] **Step 2: Manual verification**

With a processed video (or a hand-inserted DB row plus records), open the workspace. Play the video: the scroller highlights and follows. Click an item: the player seeks.

- [ ] **Step 3: Commit**

```bash
git add frontend/src
git commit -m "feat: workspace with video player and synced data scroller"
```

---

### Task 13: Chat panel with seeking citations

**Files:**
- Create: `frontend/src/components/ChatPanel.tsx`
- Modify: `frontend/src/components/Workspace.tsx` (replace `chatslot` div)
- Modify: `frontend/src/index.css` (append chat styles)

**Interfaces:**
- Consumes: `chat` from Task 10, `splitCitations`, `seek` from Workspace.
- Produces: `ChatPanel({ videoId, onSeek })`. Streams assistant text into the last message as chunks arrive. Renders citations as buttons calling `onSeek(seconds)`.

- [ ] **Step 1: Write the code**

`frontend/src/components/ChatPanel.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { chat, type ChatMessage } from "../lib/api";
import { splitCitations } from "../lib/time";

export default function ChatPanel({
  videoId, onSeek,
}: { videoId: string; onSeek: (s: number) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const history: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages([...history, { role: "assistant", content: "" }]);
    try {
      await chat(videoId, history, (chunk) => {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          next[next.length - 1] = { ...last, content: last.content + chunk };
          return next;
        });
      });
    } catch (e) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: `Error: ${e instanceof Error ? e.message : "chat failed"}`,
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="chatpanel">
      <div className="chatlog">
        {messages.length === 0 && (
          <p className="muted">
            Pregunta lo que quieras sobre esta transmision. Ejemplo: en que momento
            grito el narrador y que dijo exactamente?
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant"
              ? splitCitations(m.content).map((p, j) =>
                  p.kind === "cite" ? (
                    <button key={j} className="cite" onClick={() => onSeek(p.seconds)}>
                      {p.value}
                    </button>
                  ) : (
                    <span key={j}>{p.value}</span>
                  ),
                )
              : m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form
        className="chatinput"
        onSubmit={(e) => { e.preventDefault(); send(); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta sobre el video..."
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? "..." : "Enviar"}
        </button>
      </form>
    </section>
  );
}
```

In `Workspace.tsx`, replace `<div className="chatslot" ... />` with:
```tsx
<ChatPanel videoId={id} onSeek={seek} />
```
and add `import ChatPanel from "./ChatPanel";`.

Append to `frontend/src/index.css`:
```css
.chatpanel {
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  display: flex; flex-direction: column; min-height: 0;
}
.chatlog { flex: 1; overflow-y: auto; padding: 14px; display: grid; gap: 10px; align-content: start; }
.msg { max-width: 72ch; line-height: 1.5; white-space: pre-wrap; }
.msg.user { justify-self: end; background: #1c2740; padding: 8px 12px; border-radius: 10px; }
.msg.assistant { justify-self: start; }
.cite {
  background: var(--accent); color: #141002; border: none; border-radius: 5px;
  padding: 0 6px; margin: 0 2px; cursor: pointer; font: inherit; font-weight: 600;
}
.cite:hover { filter: brightness(1.1); }
.chatinput { display: flex; gap: 8px; padding: 10px; border-top: 1px solid var(--line); }
.chatinput input {
  flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: 10px 12px; font: inherit;
}
.chatinput button {
  background: var(--accent2); color: white; border: none; border-radius: 8px;
  padding: 0 18px; cursor: pointer; font: inherit;
}
.chatinput button:disabled { opacity: 0.5; cursor: default; }
```

- [ ] **Step 2: Manual verification**

Ask a question about the processed video. Expect streamed answer, yellow citation chips, and the player seeking when a chip is clicked.

- [ ] **Step 3: Commit**

```bash
git add frontend/src
git commit -m "feat: streaming chat panel with seeking timestamp citations"
```

---

### Task 14: Golden checks script

**Files:**
- Create: `backend/scripts/golden_check.py`

**Interfaces:**
- Consumes: DB records for a processed video.
- Produces: CLI `python scripts/golden_check.py <video_id>` printing PASS/FAIL per check, exit code 1 on any FAIL. Checks (from the spec): transcript non-empty; more than 1 distinct non-EVENT speaker; visual events cover >= 90% of duration; every full minute has a summary; all timestamps within duration.

- [ ] **Step 1: Write the script**

`backend/scripts/golden_check.py`:
```python
"""Usage: .venv\\Scripts\\python scripts/golden_check.py <video_id>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.config import load_settings


def main(video_id: str) -> int:
    settings = load_settings()
    conn = db.connect(settings.data_dir / "vault.db")
    rec = db.get_records(conn, video_id)
    video = rec["video"]
    if video is None:
        print(f"FAIL video {video_id} not found")
        return 1
    duration = video["duration_s"] or 0
    segs, evs = rec["transcript_segments"], rec["visual_events"]
    mins, moms = rec["minute_summaries"], rec["key_moments"]

    checks: list[tuple[str, bool]] = []
    checks.append(("transcript non-empty", len(segs) > 0))
    speakers = {s["speaker"] for s in segs if s["speaker"] != "EVENT"}
    checks.append((f"multiple speakers ({len(speakers)})", len(speakers) > 1))

    covered = sum(min(e["t_end"], duration) - e["t_start"] for e in evs)
    ratio = covered / duration if duration else 0
    checks.append((f"visual coverage {ratio:.0%}", ratio >= 0.9))

    expected_minutes = set(range(int(duration // 60)))
    have_minutes = {m["minute_index"] for m in mins}
    missing = expected_minutes - have_minutes
    checks.append((f"minute summaries complete (missing: {sorted(missing)[:5]})", not missing))

    all_ts = (
        [s["t_start"] for s in segs] + [s["t_end"] for s in segs]
        + [e["t_start"] for e in evs] + [e["t_end"] for e in evs]
        + [k["t"] for k in moms]
    )
    in_range = all(0 <= t <= duration + 2 for t in all_ts)
    checks.append(("all timestamps within duration", in_range))

    failed = 0
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        failed += 0 if passed else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 2: Verify against a processed video**

Run: `.venv\Scripts\python scripts/golden_check.py <id-of-processed-video>`
Expected: 5 lines, all PASS on the real video. Investigate any FAIL before the demo.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/golden_check.py
git commit -m "feat: golden checks script for processed videos"
```

---

### Task 15: README, end-to-end run, push

**Files:**
- Create: `README.md` (repo root)

- [ ] **Step 1: Write README**

`README.md`:
```markdown
# Fox Video Intelligence

Turns a sports broadcast into structured data (diarized transcript, visual
events, summaries, key moments) and answers questions about it with an AI
grounded in that data. Citations seek the video to the exact moment.

## Stack

ElevenLabs Scribe v2 (Spanish diarized transcription) + Gemini 3.5 Flash
(native video analysis) + Claude Opus 4.8 (grounded chat). FastAPI + SQLite
backend, Vite + React frontend. Design spec:
`docs/superpowers/specs/2026-07-02-video-intelligence-mvp-design.md`.

## Prerequisites

- Python 3.11+, Node 20+, ffmpeg on PATH
- API keys: ElevenLabs, Google AI Studio, Anthropic

## Run

Backend:

    cd backend
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
    copy .env.example .env   (fill in the three keys)
    .venv\Scripts\uvicorn app.main:build --factory --port 8000

Frontend:

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173, upload a video, wait for processing, ask
questions.

## Tests

    cd backend && .venv\Scripts\python -m pytest
    cd frontend && npm test

After processing a real video:

    cd backend && .venv\Scripts\python scripts/golden_check.py <video_id>

## Costs

Roughly $1.40 per hour of video processed. Chat questions cost cents.
```

- [ ] **Step 2: Full end-to-end run**

1. Backend test suite green, frontend tests green.
2. Process the real Fox video through the UI.
3. Run golden checks on it.
4. Ask the 10 prepared questions (8 answerable, 2 not). Verify grounding and citation seeking.

- [ ] **Step 3: Commit and push**

```bash
git add README.md
git commit -m "docs: readme with setup, run, and test instructions"
git push
```

---

## Day Mapping

- Day 1: Tasks 1-9 (backend complete, real video processing overnight).
- Day 2: Tasks 10-13 (frontend complete against processed data).
- Day 3: Tasks 14-15 plus polish, demo rehearsal, visual design pass on the frontend (use the frontend-design skill; keep the layout, upgrade the finish).

## Known Risks

- ElevenLabs response field names verified in Task 4 Step 5 before anything depends on them.
- Gemini window analysis quality: if 900s windows return sparse events, drop to 600s windows (change `WINDOW_S` only).
- If `speaker_names` mapping is wrong, segments keep anonymous labels. Acceptable for demo; manual rename is a stretch goal, not planned.
- The real video may exceed 2 GB (Gemini File API cap). If so, transcode down with `ffmpeg -i in.mp4 -vf scale=1280:-2 -c:v libx264 -crf 28 -c:a copy out.mp4` before upload.
```
