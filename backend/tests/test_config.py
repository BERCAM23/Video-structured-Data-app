import pytest

from app.config import load_settings


def test_fails_fast_when_key_missing(tmp_path):
    env = {
        "ELEVENLABS_API_KEY": "x",
        "GOOGLE_API_KEY": "",
        "ANTHROPIC_API_KEY": "y",
        "DATA_DIR": str(tmp_path),
    }
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        load_settings(env)


def test_loads_and_creates_data_dir(tmp_path):
    env = {
        "ELEVENLABS_API_KEY": "a",
        "GOOGLE_API_KEY": "b",
        "ANTHROPIC_API_KEY": "c",
        "DATA_DIR": str(tmp_path / "d"),
    }
    s = load_settings(env)
    assert s.anthropic_api_key == "c"
    assert s.data_dir.exists()


def test_anthropic_key_is_optional(tmp_path):
    env = {
        "ELEVENLABS_API_KEY": "a",
        "GOOGLE_API_KEY": "b",
        "DATA_DIR": str(tmp_path / "d"),
    }
    s = load_settings(env)
    assert s.anthropic_api_key is None
