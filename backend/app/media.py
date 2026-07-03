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
