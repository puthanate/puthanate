"""Command-line entry point.

    python -m content_engine.cli run --top-n 3
    python -m content_engine.cli run --top-n 1 --publish --privacy PUBLIC_TO_EVERYONE
    python -m content_engine.cli run --trends path/to/my_trends.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from content_engine.config import load_config
from content_engine.pipeline import default_trend_source, run_pipeline
from content_engine.trends import JsonTrendSource


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="content_engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full trend-to-publish pipeline")
    run_parser.add_argument(
        "--trends", type=Path, default=None, help="Path to a trend signals JSON file"
    )
    run_parser.add_argument(
        "--top-n", type=int, default=3, help="How many top gaps to turn into content"
    )
    run_parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to TikTok (requires TIKTOK_ACCESS_TOKEN). Without this flag, "
        "the pipeline always stops after generation.",
    )
    run_parser.add_argument(
        "--privacy",
        default="SELF_ONLY",
        choices=["SELF_ONLY", "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"],
        help="Requested privacy level. Ignored (forced to SELF_ONLY) unless "
        "TIKTOK_APP_AUDITED=true, matching TikTok's own restriction on unaudited apps.",
    )

    args = parser.parse_args(argv)
    config = load_config()

    if args.command == "run":
        trend_source = JsonTrendSource(path=args.trends) if args.trends else default_trend_source()
        items = run_pipeline(
            trend_source=trend_source,
            config=config,
            top_n=args.top_n,
            publish=args.publish,
            requested_privacy_level=args.privacy,
        )
        _print_summary(items, config)


def _print_summary(items, config) -> None:
    print(f"\n{'=' * 60}")
    print(f"Higgsfield configured: {config.higgsfield_ready}")
    print(f"TikTok configured:     {config.tiktok_ready}")
    print(f"{'=' * 60}\n")
    for item in items:
        print(f"[{item.gap.gap_score:5.1f}] {item.gap.signal.topic}")
        print(f"        rationale: {item.gap.rationale}")
        print(f"        hook: {item.brief.hook}")
        print(f"        asset: {item.asset.status}"
              + (f" -> {item.asset.video_path or item.asset.video_url}" if item.asset.status != "failed" else f" ({item.asset.error})"))
        print(f"        publish: {item.publish_result.status}" + (f" ({item.publish_result.detail})" if item.publish_result.detail else ""))
        print()
    print(f"Full report: {config.output_dir / 'run_report.json'}")


if __name__ == "__main__":
    main()
