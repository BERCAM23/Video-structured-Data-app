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


def stream_chat(api_key: str | None, records: dict, messages: list[dict]):
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        system=build_system(records),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
