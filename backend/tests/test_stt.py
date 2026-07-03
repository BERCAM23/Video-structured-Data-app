from app.stt import normalize


def w(text, start, end, speaker="speaker_0", kind="word"):
    return {"text": text, "start": start, "end": end, "speaker_id": speaker, "type": kind}


def test_groups_consecutive_words_by_speaker():
    raw = {"words": [
        w("Hola", 0.0, 0.4), w(" ", 0.4, 0.5, kind="spacing"), w("amigos", 0.5, 1.0),
        w("Gol", 1.2, 1.6, speaker="speaker_1"),
    ]}
    segs = normalize(raw)
    assert len(segs) == 2
    assert segs[0]["text"] == "Hola amigos"
    assert segs[0]["speaker"] == "speaker_0"
    assert segs[0]["t_start"] == 0.0
    assert segs[0]["t_end"] == 1.0
    assert segs[1]["speaker"] == "speaker_1"


def test_splits_on_long_gap():
    raw = {"words": [w("uno", 0.0, 0.5), w("dos", 5.0, 5.5)]}
    segs = normalize(raw)
    assert len(segs) == 2


def test_audio_event_becomes_own_segment():
    raw = {"words": [
        w("Gol", 0.0, 0.5),
        w("(crowd cheering)", 0.5, 3.0, kind="audio_event"),
        w("increible", 3.1, 3.6),
    ]}
    segs = normalize(raw)
    assert [s["speaker"] for s in segs] == ["speaker_0", "EVENT", "speaker_0"]


def test_empty_response():
    assert normalize({"words": []}) == []
