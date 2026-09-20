from content_engine.gap_analysis import score_gap
from content_engine.ideation import generate_brief
from content_engine.trends import TrendSignal


def _gap():
    signal = TrendSignal(
        topic="AI product photography for small Etsy sellers",
        niche="small business",
        demand_score=64,
        supply_score=21,
        momentum=58,
        sample_hashtags=["#etsyseller"],
    )
    return score_gap(signal)


def test_fallback_brief_has_no_network_dependency_and_fills_every_field():
    brief = generate_brief(_gap(), anthropic_api_key=None)
    assert brief.topic == "AI product photography for small Etsy sellers"
    assert brief.hook
    assert len(brief.beats) >= 3
    assert brief.higgsfield_prompt
    assert brief.caption
    assert brief.hashtags
    assert brief.cta


def test_fallback_hashtags_are_deduplicated():
    brief = generate_brief(_gap(), anthropic_api_key=None)
    assert len(brief.hashtags) == len(set(brief.hashtags))


def test_claude_failure_degrades_to_fallback(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise requests.RequestException("network is down")

    monkeypatch.setattr("content_engine.ideation.requests.post", boom)
    brief = generate_brief(_gap(), anthropic_api_key="fake-key-for-test")
    # Should not raise — falls back to the deterministic template instead.
    assert brief.hook
