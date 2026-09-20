"""Video generation via Higgsfield.

Wraps the official ``higgsfield-client`` SDK (``pip install
higgsfield-client``), which authenticates via ``HF_KEY`` (or
``HF_API_KEY``/``HF_API_SECRET``) and exposes a submit-and-poll pattern:
``subscribe()`` blocks until the job finishes; ``submit()`` returns a
controller you can poll with ``poll_request_status()`` for
Queued/InProgress/Completed/Failed/NSFW/Cancelled states, with an
optional webhook_url for async notification instead of polling.

Higgsfield hosts 50+ models across text-to-video, image-to-video, and
"Soul" (identity-consistent) modes, each with its own parameter names —
check the model's page on cloud.higgsfield.ai before changing
``HIGGSFIELD_DEFAULT_MODEL``. This wrapper only assumes every model
accepts a ``prompt`` and, for image-to-video, an ``image_url``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class GeneratedAsset:
    topic: str
    model: str
    prompt: str
    status: str  # "completed" | "failed" | "dry_run"
    video_path: Path | None = None
    video_url: str | None = None
    job_id: str | None = None
    error: str | None = None


class VideoGenerator(Protocol):
    def generate(
        self, *, topic: str, prompt: str, model: str, image_url: str | None = None
    ) -> GeneratedAsset: ...


class HiggsfieldVideoClient:
    """Real client. Requires ``pip install higgsfield-client`` and a
    configured API key — both are checked lazily so importing this module
    never fails just because the SDK isn't installed."""

    def __init__(self, api_key: str, api_secret: str | None, output_dir: Path) -> None:
        os.environ.setdefault("HF_KEY", f"{api_key}:{api_secret}" if api_secret else api_key)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self, *, topic: str, prompt: str, model: str, image_url: str | None = None
    ) -> GeneratedAsset:
        try:
            import higgsfield_client  # type: ignore[import-not-found]
        except ImportError:
            return GeneratedAsset(
                topic=topic,
                model=model,
                prompt=prompt,
                status="failed",
                error=(
                    "higgsfield-client is not installed. Run "
                    "`pip install higgsfield-client` to enable real generation."
                ),
            )

        arguments: dict[str, object] = {"prompt": prompt}
        if image_url:
            arguments["image_url"] = image_url

        try:
            result = higgsfield_client.subscribe(model, arguments=arguments)
        except Exception as exc:  # noqa: BLE001 - surface any SDK/API failure as a failed asset
            return GeneratedAsset(
                topic=topic, model=model, prompt=prompt, status="failed", error=str(exc)
            )

        video_url = _extract_video_url(result)
        return GeneratedAsset(
            topic=topic,
            model=model,
            prompt=prompt,
            status="completed",
            video_url=video_url,
            job_id=getattr(result, "request_id", None) or (result.get("request_id") if isinstance(result, dict) else None),
        )


def _extract_video_url(result: object) -> str | None:
    """Higgsfield's result shape varies by model; check a few common spots
    rather than assuming one exact schema."""
    if isinstance(result, dict):
        for key in ("video_url", "url", "output_url"):
            if key in result:
                return str(result[key])
        video = result.get("video")
        if isinstance(video, dict):
            return video.get("url")
    return None


class DryRunVideoGenerator:
    """No API key, no network calls, no cost — writes a plan-of-record
    stub instead of an actual video so the rest of the pipeline (captions,
    publishing) can still be exercised and reviewed."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self, *, topic: str, prompt: str, model: str, image_url: str | None = None
    ) -> GeneratedAsset:
        stub_path = self.output_dir / f"{_slug(topic)}.DRY_RUN.txt"
        stub_path.write_text(
            "DRY RUN — no video was actually generated (no HIGGSFIELD_API_KEY configured).\n\n"
            f"Model: {model}\n"
            f"Prompt: {prompt}\n"
            f"Image reference: {image_url or 'none'}\n"
        )
        return GeneratedAsset(
            topic=topic,
            model=model,
            prompt=prompt,
            status="dry_run",
            video_path=stub_path,
        )


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")[:60]


def get_video_generator(
    *, api_key: str | None, api_secret: str | None, output_dir: Path
) -> VideoGenerator:
    if api_key:
        return HiggsfieldVideoClient(api_key, api_secret, output_dir)
    return DryRunVideoGenerator(output_dir)
