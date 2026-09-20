"""Turns raw trend signals into a ranked list of content gaps.

The core thesis behind "bridge the gap between the market and the
content": a topic is worth making content about not because it's
popular, but because demand for it currently outstrips supply. A
trend with sky-high demand but also sky-high supply is already
saturated — jumping in adds noise, not value. A trend with rising
momentum and low existing supply is underserved, which is exactly
where new content has the best odds of actually being seen.
"""

from __future__ import annotations

from dataclasses import dataclass

from content_engine.trends import TrendSignal

# Tunable weights: demand and momentum pull the score up, supply pulls it
# down. Momentum is weighted highest because a rising-but-not-yet-saturated
# topic is the best window to publish into.
DEMAND_WEIGHT = 0.35
MOMENTUM_WEIGHT = 0.45
SUPPLY_WEIGHT = 0.40


@dataclass(frozen=True)
class ContentGap:
    signal: TrendSignal
    gap_score: float  # 0-100, higher = more underserved demand worth serving
    rationale: str


def score_gap(signal: TrendSignal) -> ContentGap:
    raw = (
        signal.demand_score * DEMAND_WEIGHT
        + signal.momentum * MOMENTUM_WEIGHT
        - signal.supply_score * SUPPLY_WEIGHT
    )
    # Normalize into 0-100. Max possible raw is 100*(DEMAND_WEIGHT+MOMENTUM_WEIGHT) when supply=0;
    # min possible is -100*SUPPLY_WEIGHT when demand=momentum=0.
    max_raw = 100 * (DEMAND_WEIGHT + MOMENTUM_WEIGHT)
    min_raw = -100 * SUPPLY_WEIGHT
    normalized = (raw - min_raw) / (max_raw - min_raw) * 100
    normalized = max(0.0, min(100.0, normalized))

    if signal.supply_score >= 70 and signal.demand_score >= 70:
        rationale = (
            f"'{signal.topic}' has high demand ({signal.demand_score:.0f}) but is already "
            f"saturated (supply {signal.supply_score:.0f}) — low marginal value in joining now."
        )
    elif signal.momentum >= 60 and signal.supply_score <= 40:
        rationale = (
            f"'{signal.topic}' is rising fast (momentum {signal.momentum:.0f}) with little "
            f"existing coverage (supply {signal.supply_score:.0f}) — strong window to publish into."
        )
    else:
        rationale = (
            f"'{signal.topic}': demand {signal.demand_score:.0f}, momentum {signal.momentum:.0f}, "
            f"supply {signal.supply_score:.0f} — moderate opportunity."
        )

    return ContentGap(signal=signal, gap_score=normalized, rationale=rationale)


def rank_gaps(signals: list[TrendSignal], top_n: int | None = None) -> list[ContentGap]:
    gaps = sorted((score_gap(s) for s in signals), key=lambda g: g.gap_score, reverse=True)
    return gaps[:top_n] if top_n else gaps
