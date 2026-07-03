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
