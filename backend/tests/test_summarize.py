from app.summarize import bucket_by_minute, merge_timeline, render_minute_block
from app.timefmt import fmt_ts


def test_fmt_ts():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65.4) == "01:05"
    assert fmt_ts(3725) == "1:02:05"


def test_merge_orders_and_tags():
    segs = [{"t_start": 5.0, "t_end": 6.0, "speaker": "speaker_0", "text": "gol"}]
    evs = [{"t_start": 1.0, "t_end": 4.0, "description": "saque", "on_screen_text": None}]
    merged = merge_timeline(segs, evs)
    assert [m["kind"] for m in merged] == ["visual", "speech"]


def test_merge_tags_audio_events():
    segs = [{"t_start": 2.0, "t_end": 3.0, "speaker": "EVENT", "text": "(crowd)"}]
    merged = merge_timeline(segs, [])
    assert merged[0]["kind"] == "event"


def test_bucket_by_minute():
    merged = [
        {"t_start": 10.0, "kind": "speech", "t_end": 11, "speaker": "s", "text": "a"},
        {"t_start": 70.0, "kind": "speech", "t_end": 71, "speaker": "s", "text": "b"},
        {"t_start": 80.0, "kind": "speech", "t_end": 81, "speaker": "s", "text": "c"},
    ]
    buckets = bucket_by_minute(merged)
    assert sorted(buckets) == [0, 1]
    assert len(buckets[1]) == 2


def test_render_minute_block_contains_timestamps_and_text():
    items = [{"t_start": 70.0, "t_end": 72.0, "kind": "speech", "speaker": "speaker_1", "text": "que golazo"}]
    block = render_minute_block(1, items)
    assert "[01:10]" in block
    assert "speaker_1" in block
    assert "que golazo" in block
