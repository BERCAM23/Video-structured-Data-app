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
