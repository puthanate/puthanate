from content_engine.gap_analysis import rank_gaps, score_gap
from content_engine.trends import TrendSignal


def make_signal(demand, supply, momentum, topic="t"):
    return TrendSignal(topic=topic, niche="n", demand_score=demand, supply_score=supply, momentum=momentum)


def test_high_demand_high_supply_is_a_low_priority_gap():
    saturated = score_gap(make_signal(demand=95, supply=95, momentum=10, topic="saturated"))
    fresh = score_gap(make_signal(demand=60, supply=10, momentum=80, topic="fresh"))
    assert fresh.gap_score > saturated.gap_score


def test_score_is_bounded_0_to_100():
    for demand in (0, 50, 100):
        for supply in (0, 50, 100):
            for momentum in (0, 50, 100):
                gap = score_gap(make_signal(demand, supply, momentum))
                assert 0.0 <= gap.gap_score <= 100.0


def test_rank_gaps_sorts_descending_and_respects_top_n():
    signals = [
        make_signal(demand=90, supply=90, momentum=5, topic="low"),
        make_signal(demand=80, supply=10, momentum=90, topic="high"),
        make_signal(demand=50, supply=50, momentum=50, topic="mid"),
    ]
    ranked = rank_gaps(signals, top_n=2)
    assert len(ranked) == 2
    assert ranked[0].signal.topic == "high"
    assert ranked[0].gap_score >= ranked[1].gap_score


def test_invalid_score_raises():
    import pytest

    with pytest.raises(ValueError):
        TrendSignal(topic="t", niche="n", demand_score=150, supply_score=10, momentum=10)
