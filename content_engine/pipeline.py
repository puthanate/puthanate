"""Ties trends -> gap analysis -> ideation -> generation -> publishing
into one run. Every stage degrades gracefully without credentials, so
``run_pipeline`` always produces a full, inspectable result — the only
thing that changes with real API keys configured is whether the video
and publish steps actually hit the network.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from content_engine.config import Config, load_config
from content_engine.gap_analysis import ContentGap, rank_gaps
from content_engine.higgsfield_client import GeneratedAsset, get_video_generator
from content_engine.ideation import ContentBrief, generate_brief
from content_engine.tiktok_publisher import PublishResult, get_publisher
from content_engine.trends import JsonTrendSource, TrendSource


@dataclass(frozen=True)
class PipelineItem:
    gap: ContentGap
    brief: ContentBrief
    asset: GeneratedAsset
    publish_result: PublishResult


def run_pipeline(
    *,
    trend_source: TrendSource,
    config: Config | None = None,
    top_n: int = 3,
    publish: bool = False,
    requested_privacy_level: str = "SELF_ONLY",
) -> list[PipelineItem]:
    config = config or load_config()

    signals = list(trend_source.fetch())
    gaps = rank_gaps(signals, top_n=top_n)

    video_generator = get_video_generator(
        api_key=config.higgsfield_api_key,
        api_secret=config.higgsfield_api_secret,
        output_dir=config.output_dir,
    )
    publisher = get_publisher(
        access_token=config.tiktok_access_token, app_audited=config.tiktok_app_audited
    )

    items: list[PipelineItem] = []
    for gap in gaps:
        brief = generate_brief(gap, config.anthropic_api_key)
        asset = video_generator.generate(
            topic=brief.topic,
            prompt=brief.higgsfield_prompt,
            model=config.higgsfield_default_model,
        )

        caption = f"{brief.caption}\n\n{' '.join(brief.hashtags)}".strip()
        if not publish:
            publish_result = PublishResult(status="skipped", detail="publish=False")
        elif asset.status == "failed":
            publish_result = PublishResult(
                status="skipped", detail=f"asset generation failed: {asset.error}"
            )
        elif asset.video_url:
            publish_result = publisher.publish_video_from_url(
                asset.video_url,
                caption=caption,
                requested_privacy_level=requested_privacy_level,
            )
        elif asset.video_path and asset.status == "completed":
            publish_result = publisher.publish_video(
                asset.video_path,
                caption=caption,
                requested_privacy_level=requested_privacy_level,
            )
        else:
            # dry-run asset (a .txt stub) — never actually attempt to upload it
            publish_result = PublishResult(
                status="dry_run", detail="asset was a dry-run stub, not a real video"
            )

        items.append(
            PipelineItem(gap=gap, brief=brief, asset=asset, publish_result=publish_result)
        )

    _write_report(items, config.output_dir)
    return items


def _write_report(items: list[PipelineItem], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for item in items:
        report.append(
            {
                "topic": item.gap.signal.topic,
                "gap_score": round(item.gap.gap_score, 1),
                "rationale": item.gap.rationale,
                "brief": asdict(item.brief),
                "asset_status": item.asset.status,
                "video_path": str(item.asset.video_path) if item.asset.video_path else None,
                "video_url": item.asset.video_url,
                "publish_status": item.publish_result.status,
                "publish_detail": item.publish_result.detail,
                "publish_id": item.publish_result.publish_id,
            }
        )
    (output_dir / "run_report.json").write_text(json.dumps(report, indent=2))


def default_trend_source() -> JsonTrendSource:
    repo_root = Path(__file__).resolve().parent.parent
    return JsonTrendSource(path=repo_root / "data" / "sample_trends.json")
