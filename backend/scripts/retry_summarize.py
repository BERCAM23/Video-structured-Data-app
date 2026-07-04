"""Retry the pipeline until the rate limit clears. Usage: python scripts/retry_summarize.py [video_id]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings
from app.pipeline import run_pipeline

settings = load_settings()
db_path = settings.data_dir / "vault.db"
video_id = sys.argv[1] if len(sys.argv) > 1 else "e3b0e908d2d3"

for attempt in range(1, 13):
    try:
        run_pipeline(video_id, settings, db_path)
        print(f"attempt {attempt}: READY", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"attempt {attempt}: {str(e)[:200]}", flush=True)
        time.sleep(600)

print("gave up after 12 attempts", flush=True)
sys.exit(1)
