"""Usage: .venv\\Scripts\\python scripts/golden_check.py <video_id>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db
from app.config import load_settings


def main(video_id: str) -> int:
    settings = load_settings()
    conn = db.connect(settings.data_dir / "vault.db")
    rec = db.get_records(conn, video_id)
    video = rec["video"]
    if video is None:
        print(f"FAIL video {video_id} not found")
        return 1
    duration = video["duration_s"] or 0
    segs, evs = rec["transcript_segments"], rec["visual_events"]
    mins, moms = rec["minute_summaries"], rec["key_moments"]

    checks: list[tuple[str, bool]] = []
    checks.append(("transcript non-empty", len(segs) > 0))
    speakers = {s["speaker"] for s in segs if s["speaker"] != "EVENT"}
    checks.append((f"multiple speakers ({len(speakers)})", len(speakers) > 1))

    covered = sum(max(0.0, min(e["t_end"], duration) - max(e["t_start"], 0.0)) for e in evs)
    ratio = covered / duration if duration else 0
    checks.append((f"visual coverage {ratio:.0%}", ratio >= 0.9))

    expected_minutes = set(range(int(duration // 60)))
    have_minutes = {m["minute_index"] for m in mins}
    missing = expected_minutes - have_minutes
    checks.append((f"minute summaries complete (missing: {sorted(missing)[:5]})", not missing))

    all_ts = (
        [s["t_start"] for s in segs] + [s["t_end"] for s in segs]
        + [e["t_start"] for e in evs] + [e["t_end"] for e in evs]
        + [k["t"] for k in moms]
    )
    in_range = all(0 <= t <= duration + 2 for t in all_ts)
    checks.append(("all timestamps within duration", in_range))

    failed = 0
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
        failed += 0 if passed else 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
