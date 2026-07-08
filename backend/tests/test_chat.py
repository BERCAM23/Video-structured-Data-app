import json

from app import chat, db
from app.chat import CITATION_RE, build_system, build_global_context, serialize_records

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


def test_stream_chat_yields_result_and_persists_session(tmp_path, monkeypatch):
    sessions_file = tmp_path / "chat_sessions.json"
    monkeypatch.setattr(chat, "SESSIONS_FILE", sessions_file)

    def fake_run_claude(args, stdin_text):
        return {"result": "el gol fue al [01:05]", "session_id": "sess-123"}

    monkeypatch.setattr(chat, "_run_claude", fake_run_claude)

    chunks = list(chat.stream_chat(None, RECORDS, [{"role": "user", "content": "cuando fue el gol?"}]))

    assert chunks == ["el gol fue al [01:05]"]
    saved = json.loads(sessions_file.read_text(encoding="utf-8"))
    assert saved == {"v1": "sess-123"}


def test_build_global_context(tmp_path):
    conn = db.connect(tmp_path / "vault.db")
    db.init_db(conn)
    db.create_video(conn, "v1", "Final", "f.mp4")
    db.set_status(conn, "v1", "ready")
    db.set_video_meta(conn, "v1", sport="futbol", teams="A vs B", summary="gran final entre A y B")
    seg = [{"t_start": 65.0, "t_end": 68.0, "speaker": "Martinoli", "text": "Increible lo que hizo Chicharito"}]
    db.replace_records(conn, "v1", seg, [], [], [])

    context = build_global_context(conn, "Chicharito")

    assert "VIDEOS EN LA BASE:" in context
    assert "- Final | futbol | A vs B | gran final entre A y B" in context
    assert "FRAGMENTOS RECUPERADOS PARA ESTA PREGUNTA:" in context
    assert "[Final @ 01:05]" in context
    assert "@" in context
