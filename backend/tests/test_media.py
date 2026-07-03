import pytest

from app.media import MediaError, extract_audio, probe_duration


def test_probe_duration(tiny_clip):
    assert probe_duration(tiny_clip) == pytest.approx(2.0, abs=0.3)


def test_extract_audio(tiny_clip, tmp_path):
    out = extract_audio(tiny_clip, tmp_path / "audio.mp3")
    assert out.exists()
    assert out.stat().st_size > 1000


def test_probe_missing_file_raises(tmp_path):
    with pytest.raises(MediaError):
        probe_duration(tmp_path / "nope.mp4")
