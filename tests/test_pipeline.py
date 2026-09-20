from pathlib import Path

from content_engine.config import Config
from content_engine.pipeline import default_trend_source, run_pipeline


def _dry_run_config(tmp_path: Path) -> Config:
    return Config(
        higgsfield_api_key=None,
        higgsfield_api_secret=None,
        higgsfield_default_model="higgsfield/soul/image-to-video",
        tiktok_client_key=None,
        tiktok_client_secret=None,
        tiktok_access_token=None,
        tiktok_app_audited=False,
        anthropic_api_key=None,
        output_dir=tmp_path,
    )


def test_full_pipeline_runs_end_to_end_with_no_credentials(tmp_path):
    items = run_pipeline(
        trend_source=default_trend_source(),
        config=_dry_run_config(tmp_path),
        top_n=2,
        publish=False,
    )
    assert len(items) == 2
    # Ranked descending by gap score
    assert items[0].gap.gap_score >= items[1].gap.gap_score
    for item in items:
        assert item.asset.status == "dry_run"
        assert item.asset.video_path is not None
        assert item.asset.video_path.exists()
        assert item.publish_result.status == "skipped"

    report = tmp_path / "run_report.json"
    assert report.exists()


def test_publish_flag_with_no_credentials_stays_dry_run(tmp_path):
    items = run_pipeline(
        trend_source=default_trend_source(),
        config=_dry_run_config(tmp_path),
        top_n=1,
        publish=True,
    )
    assert items[0].publish_result.status == "dry_run"


def test_saturated_trend_never_outranks_a_fresh_high_momentum_one(tmp_path):
    items = run_pipeline(
        trend_source=default_trend_source(),
        config=_dry_run_config(tmp_path),
        top_n=5,
        publish=False,
    )
    topics_in_order = [item.gap.signal.topic for item in items]
    fresh_idx = topics_in_order.index("AI-generated 'day in the life' of a fictional creature")
    saturated_idx = topics_in_order.index("Generic AI dance filter videos")
    assert fresh_idx < saturated_idx
