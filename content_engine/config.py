"""Configuration loading for the content engine.

Reads from real environment variables first, then falls back to a local
``.env`` file (simple ``KEY=VALUE`` lines, no external dependency needed).
Nothing in here requires credentials to be present — every field is
optional so the pipeline can run end-to-end in dry-run mode with no keys
configured at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ENV_LOADED = False


def _load_dotenv(path: Path = Path(".env")) -> None:
    global _ENV_LOADED
    if _ENV_LOADED or not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ENV_LOADED = True


@dataclass(frozen=True)
class Config:
    # Higgsfield (video generation)
    higgsfield_api_key: str | None
    higgsfield_api_secret: str | None
    higgsfield_default_model: str

    # TikTok (Direct Post / Content Posting API)
    tiktok_client_key: str | None
    tiktok_client_secret: str | None
    tiktok_access_token: str | None
    tiktok_app_audited: bool
    """TikTok forces every unaudited app's posts to private (SELF_ONLY),
    regardless of what privacy_level is requested. Set this to true only
    once your app has passed TikTok's content-posting audit."""

    # Ideation (Claude, optional — falls back to templates without it)
    anthropic_api_key: str | None

    output_dir: Path

    @property
    def higgsfield_ready(self) -> bool:
        return bool(self.higgsfield_api_key)

    @property
    def tiktok_ready(self) -> bool:
        return bool(self.tiktok_client_key and self.tiktok_access_token)


def load_config() -> Config:
    _load_dotenv()
    return Config(
        higgsfield_api_key=os.environ.get("HIGGSFIELD_API_KEY") or None,
        higgsfield_api_secret=os.environ.get("HIGGSFIELD_API_SECRET") or None,
        higgsfield_default_model=os.environ.get(
            "HIGGSFIELD_DEFAULT_MODEL", "higgsfield/soul/image-to-video"
        ),
        tiktok_client_key=os.environ.get("TIKTOK_CLIENT_KEY") or None,
        tiktok_client_secret=os.environ.get("TIKTOK_CLIENT_SECRET") or None,
        tiktok_access_token=os.environ.get("TIKTOK_ACCESS_TOKEN") or None,
        tiktok_app_audited=os.environ.get("TIKTOK_APP_AUDITED", "false").lower()
        in ("1", "true", "yes"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        output_dir=Path(os.environ.get("CONTENT_ENGINE_OUTPUT_DIR", "output")),
    )
