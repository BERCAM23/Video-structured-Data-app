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
            minutes = summarize.summarize_minutes(merged, duration, settings.anthropic_api_key)
            info = summarize.summarize_video(minutes, segments, settings.anthropic_api_key)
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
