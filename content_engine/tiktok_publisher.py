"""Publishing to TikTok via the official Content Posting API (Direct Post).

Flow (per developers.tiktok.com/docs/en/content-posting-api-get-started):
1. POST /v2/post/publish/video/init/ with post_info (caption, privacy,
   interaction toggles) and source_info (FILE_UPLOAD or PULL_FROM_URL) ->
   returns ``publish_id`` and, for FILE_UPLOAD, an ``upload_url``.
2. For FILE_UPLOAD: PUT the video to ``upload_url`` in 5-64MB chunks
   (final chunk may run up to 128MB), each declared with a Content-Range
   header.
3. Poll /v2/post/publish/status/fetch/ with the ``publish_id`` until the
   post is processed.

**Critical constraint, enforced here rather than left to the caller to
remember:** TikTok forces every unaudited app's posts to private
(SELF_ONLY) regardless of the privacy_level requested, until the app
passes TikTok's content-posting audit. This client will not even attempt
to request public visibility unless ``Config.tiktok_app_audited`` is
explicitly true — that's a deliberate safety default, not a limitation
to work around.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests

API_BASE = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB — within the required 5-64MB range


@dataclass(frozen=True)
class PublishResult:
    status: str  # "published" | "processing" | "failed" | "dry_run" | "skipped"
    publish_id: str | None = None
    privacy_level: str | None = None
    detail: str | None = None


class TikTokPublisher:
    def __init__(self, access_token: str, app_audited: bool) -> None:
        self.access_token = access_token
        self.app_audited = app_audited

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def publish_video(
        self,
        video_path: Path,
        *,
        caption: str,
        requested_privacy_level: str = "SELF_ONLY",
    ) -> PublishResult:
        privacy_level = requested_privacy_level if self.app_audited else "SELF_ONLY"
        if privacy_level != requested_privacy_level:
            note = (
                f"Requested privacy_level={requested_privacy_level!r} but the app is not "
                f"marked audited (TIKTOK_APP_AUDITED) — forcing SELF_ONLY, matching what "
                f"TikTok itself would do to an unaudited app's posts anyway."
            )
        else:
            note = None

        video_bytes = video_path.read_bytes()
        total_size = len(video_bytes)
        total_chunks = max(1, -(-total_size // CHUNK_SIZE))  # ceil div

        init_resp = requests.post(
            f"{API_BASE}/post/publish/video/init/",
            headers=self._headers(),
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": privacy_level,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": total_size,
                    "chunk_size": CHUNK_SIZE,
                    "total_chunk_count": total_chunks,
                },
            },
            timeout=30,
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()["data"]
        publish_id = init_data["publish_id"]
        upload_url = init_data["upload_url"]

        for i in range(total_chunks):
            start = i * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, total_size)
            chunk = video_bytes[start:end]
            requests.put(
                upload_url,
                data=chunk,
                headers={
                    "Content-Range": f"bytes {start}-{end - 1}/{total_size}",
                    "Content-Type": "video/mp4",
                },
                timeout=120,
            ).raise_for_status()

        return PublishResult(
            status="processing", publish_id=publish_id, privacy_level=privacy_level, detail=note
        )

    def publish_video_from_url(
        self,
        video_url: str,
        *,
        caption: str,
        requested_privacy_level: str = "SELF_ONLY",
    ) -> PublishResult:
        """PULL_FROM_URL avoids downloading+re-uploading a Higgsfield-hosted
        asset, but the source domain must be pre-verified in your TikTok
        developer app settings, or TikTok will reject the request."""
        privacy_level = requested_privacy_level if self.app_audited else "SELF_ONLY"
        note = None
        if privacy_level != requested_privacy_level:
            note = (
                f"Requested privacy_level={requested_privacy_level!r} but the app is not "
                f"marked audited — forcing SELF_ONLY."
            )

        init_resp = requests.post(
            f"{API_BASE}/post/publish/video/init/",
            headers=self._headers(),
            json={
                "post_info": {
                    "title": caption,
                    "privacy_level": privacy_level,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
            },
            timeout=30,
        )
        init_resp.raise_for_status()
        init_data = init_resp.json()["data"]
        return PublishResult(
            status="processing",
            publish_id=init_data["publish_id"],
            privacy_level=privacy_level,
            detail=note,
        )

    def check_status(self, publish_id: str) -> dict:
        resp = requests.post(
            f"{API_BASE}/post/publish/status/fetch/",
            headers=self._headers(),
            json={"publish_id": publish_id},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]


class DryRunPublisher:
    """No access token configured (or the pipeline is running in
    --dry-run) — records what *would* be published without calling
    TikTok at all."""

    def publish_video(
        self,
        video_path: Path,
        *,
        caption: str,
        requested_privacy_level: str = "SELF_ONLY",
    ) -> PublishResult:
        return PublishResult(
            status="dry_run",
            detail=(
                f"Would publish {video_path} with caption={caption!r} "
                f"(requested privacy={requested_privacy_level})."
            ),
        )

    def publish_video_from_url(
        self,
        video_url: str,
        *,
        caption: str,
        requested_privacy_level: str = "SELF_ONLY",
    ) -> PublishResult:
        return PublishResult(
            status="dry_run",
            detail=(
                f"Would publish {video_url} with caption={caption!r} "
                f"(requested privacy={requested_privacy_level})."
            ),
        )


def get_publisher(*, access_token: str | None, app_audited: bool) -> "TikTokPublisher | DryRunPublisher":
    if access_token:
        return TikTokPublisher(access_token, app_audited)
    return DryRunPublisher()
