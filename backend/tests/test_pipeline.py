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
