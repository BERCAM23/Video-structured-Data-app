import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REQUIRED_KEYS = ["ELEVENLABS_API_KEY", "GOOGLE_API_KEY"]


@dataclass(frozen=True)
class Settings:
    elevenlabs_api_key: str
    google_api_key: str
    anthropic_api_key: str | None
    data_dir: Path


def load_settings(env: dict | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = dict(os.environ)
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    data_dir = Path(env.get("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        elevenlabs_api_key=env["ELEVENLABS_API_KEY"],
        google_api_key=env["GOOGLE_API_KEY"],
        anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
        data_dir=data_dir,
    )
