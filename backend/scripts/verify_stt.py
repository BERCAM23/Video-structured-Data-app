"""Run once with a real key: .venv\\Scripts\\python scripts/verify_stt.py path\\to\\clip30s.mp3"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.stt import normalize, transcribe

settings = load_settings()
raw = transcribe(Path(sys.argv[1]), settings.elevenlabs_api_key)
Path("stt_raw_sample.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
for seg in normalize(raw)[:10]:
    print(f"[{seg['t_start']:6.1f}-{seg['t_end']:6.1f}] {seg['speaker']}: {seg['text']}")
