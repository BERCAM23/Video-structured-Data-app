import json
import re
import shutil
import subprocess
from pathlib import Path

from app import db
from app.timefmt import fmt_ts

MODEL = "claude-opus-4-8"

CITATION_RE = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")

SESSIONS_FILE = Path("data/chat_sessions.json")

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


def _load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_sessions(sessions: dict) -> None:
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(sessions), encoding="utf-8")


def _run_claude(args: list[str], stdin_text: str) -> dict:
    exe = shutil.which("claude")
    if exe is None:
        raise RuntimeError("claude CLI not found on PATH")
    proc = subprocess.run(
        [exe, "-p", "--model", "sonnet", "--output-format", "json", *args],
        input=stdin_text, capture_output=True, text=True, encoding="utf-8",
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {proc.stderr[-500:] or proc.stdout[-500:]}")
    return json.loads(proc.stdout)


def _first_turn_stdin(records: dict, question: str) -> str:
    return (
        RULES
        + "\n\nDATOS ESTRUCTURADOS DEL VIDEO:\n"
        + serialize_records(records)
        + "\n\nPREGUNTA DEL USUARIO: "
        + question
    )


def stream_chat(api_key: str | None, records: dict, messages: list[dict]):
    question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            question = m.get("content", "")
            break

    video_id = records["video"]["id"]
    sessions = _load_sessions()

    try:
        if video_id in sessions:
            try:
                result = _run_claude(["--resume", sessions[video_id]], question)
            except Exception:
                result = _run_claude([], _first_turn_stdin(records, question))
                sessions[video_id] = result["session_id"]
                _save_sessions(sessions)
        else:
            result = _run_claude([], _first_turn_stdin(records, question))
            sessions[video_id] = result["session_id"]
            _save_sessions(sessions)

        answer = result["result"]
        yield answer
    except Exception as e:
        yield "Error del chat: " + str(e)[:300]


GLOBAL_RULES = """Eres el asistente de busqueda de inteligencia de video de Fox Sports.
Respondes preguntas sobre TODOS los videos de la base usando UNICAMENTE los resumenes de video y los fragmentos recuperados que se te provean.

Reglas estrictas:
1. Responde solo con informacion presente en los datos provistos.
2. Cada afirmacion factual lleva su cita de fuente en formato exacto [<titulo del video> @ MM:SS], usando el separador @.
3. Si los datos recuperados no contienen la respuesta, dilo claramente.
4. Responde en el idioma de la pregunta (espanol o ingles).
5. Se concreto y breve. Nada de relleno."""


def build_global_context(conn, question: str) -> str:
    videos = [
        dict(r)
        for r in conn.execute(
            "SELECT id, title, sport, teams, summary FROM videos WHERE status = 'ready'"
        ).fetchall()
    ]
    parts = ["VIDEOS EN LA BASE:"]
    for v in videos:
        summary = (v.get("summary") or "")[:200]
        parts.append(f"- {v['title']} | {v.get('sport')} | {v.get('teams')} | {summary}")

    parts.append("FRAGMENTOS RECUPERADOS PARA ESTA PREGUNTA:")
    for hit in db.search(conn, question):
        content = (hit["content"] or "")[:300]
        parts.append(f"[{hit['title']} @ {fmt_ts(hit['t_start'])}] ({hit['kind']}) {content}")

    return "\n".join(parts)


GLOBAL_SESSION_KEY = "__global__"


def stream_global_chat(conn, messages: list[dict]):
    question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            question = m.get("content", "")
            break

    sessions = _load_sessions()

    try:
        context = build_global_context(conn, question)
        if GLOBAL_SESSION_KEY in sessions:
            try:
                stdin_text = context + "\n\nPREGUNTA: " + question
                result = _run_claude(["--resume", sessions[GLOBAL_SESSION_KEY]], stdin_text)
            except Exception:
                stdin_text = GLOBAL_RULES + "\n\n" + context + "\n\nPREGUNTA: " + question
                result = _run_claude([], stdin_text)
                sessions[GLOBAL_SESSION_KEY] = result["session_id"]
                _save_sessions(sessions)
        else:
            stdin_text = GLOBAL_RULES + "\n\n" + context + "\n\nPREGUNTA: " + question
            result = _run_claude([], stdin_text)
            sessions[GLOBAL_SESSION_KEY] = result["session_id"]
            _save_sessions(sessions)

        answer = result["result"]
        yield answer
    except Exception as e:
        yield "Error del chat: " + str(e)[:300]
