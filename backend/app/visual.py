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
