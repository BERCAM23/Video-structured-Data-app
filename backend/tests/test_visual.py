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
    events = parse_events(text, offset_s=900)
    assert events == [{
        "t_start": 904.0, "t_end": 908.0,
        "description": "saque inicial", "on_screen_text": "0-0",
    }]


def test_parse_events_tolerates_missing_optional_keys():
    events = parse_events('[{"t_start": 1, "t_end": 2, "description": "gol"}]', 0)
    assert events[0]["on_screen_text"] is None


def test_parse_events_drops_malformed_items():
    events = parse_events('[{"description": "sin tiempo"}, {"t_start": 1, "t_end": 2, "description": "ok"}]', 0)
    assert len(events) == 1
