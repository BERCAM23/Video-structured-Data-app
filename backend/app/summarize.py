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
