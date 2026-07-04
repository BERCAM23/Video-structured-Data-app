from app.visual import compute_windows, parse_events


def test_windows_exact_multiple():
    assert compute_windows(1800, window_s=900) == [(0, 900), (900, 1800)]


def test_windows_with_remainder():
    assert compute_windows(1000, window_s=900) == [(0, 900), (900, 1000)]


def test_windows_short_video():
    assert compute_windows(120.4, window_s=900) == [(0, 121)]


def test_parse_events_strips_fences_and_applies_offset():
    text = """```json
    [{"t_start": 4.0, "t_end": 8.0, "description": "saque inicial", "on_screen_text": "0-0"}]
    ```"""
    events = parse_events(text, offset_s=900, window_s=900)
    assert events == [{
        "t_start": 904.0, "t_end": 908.0,
        "description": "saque inicial", "on_screen_text": "0-0",
    }]


def test_parse_events_tolerates_missing_optional_keys():
    events = parse_events('[{"t_start": 1, "t_end": 2, "description": "gol"}]', 0, window_s=900)
    assert events[0]["on_screen_text"] is None


def test_parse_events_drops_malformed_items():
    events = parse_events(
        '[{"description": "sin tiempo"}, {"t_start": 1, "t_end": 2, "description": "ok"}]', 0, window_s=900
    )
    assert len(events) == 1


def test_parse_events_absolute_timestamp_not_double_offset():
    # Item timestamp >= window_s means Gemini returned an absolute timestamp;
    # it must NOT be added to offset_s again.
    events = parse_events(
        '[{"t_start": 950, "t_end": 954, "description": "gol"}]',
        offset_s=900,
        window_s=900,
    )
    assert events == [{
        "t_start": 950.0, "t_end": 954.0,
        "description": "gol", "on_screen_text": None,
    }]


def test_parse_events_relative_timestamp_gets_offset():
    events = parse_events(
        '[{"t_start": 4, "t_end": 8, "description": "gol"}]',
        offset_s=900,
        window_s=900,
    )
    assert events[0]["t_start"] == 904.0
    assert events[0]["t_end"] == 908.0


def test_parse_events_drops_events_beyond_duration():
    events = parse_events(
        '[{"t_start": 2710, "t_end": 2715, "description": "gol"}]',
        offset_s=1800,
        window_s=900,
        duration_s=2700,
    )
    assert events == []


def test_parse_events_clamps_t_end_to_duration():
    events = parse_events(
        '[{"t_start": 95, "t_end": 130, "description": "gol"}]',
        offset_s=0,
        window_s=900,
        duration_s=100,
    )
    assert events[0]["t_start"] == 95.0
    assert events[0]["t_end"] == 100.0


def test_compute_windows_300s():
    assert len(compute_windows(2700, window_s=300)) == 9
