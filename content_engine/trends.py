"""Market signal ingestion.

This is the "what does the market want" half of the pipeline. TikTok
doesn't expose a public trends API to third parties, so this module is
built around a pluggable ``TrendSource`` interface rather than one hard
wired scraper:

- ``JsonTrendSource`` reads a locally maintained/curated file of trend
  signals (``data/sample_trends.json`` ships one to get started).
- Point a future source at TikTok's Creative Center exports, a paid
  trends API (e.g. Exolyt, Kalodata), or your own analytics, by
  implementing the same ``TrendSignal`` shape and the ``TrendSource``
  protocol below — nothing else in the pipeline needs to change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol


@dataclass(frozen=True)
class TrendSignal:
    """One observed unit of market demand."""

    topic: str
    niche: str
    demand_score: float  # 0-100: how much the audience wants this (search/view volume proxy)
    supply_score: float  # 0-100: how saturated existing content already is
    momentum: float  # 0-100: how fast demand is rising right now
    sample_hashtags: list[str] = field(default_factory=list)
    notes: str = ""
    country_code: str = "GLOBAL"  # ISO country code the signal was observed in, e.g. "TH"
    source_url: str | None = None  # link to the underlying trend (e.g. a TikTok sound page)

    def __post_init__(self) -> None:
        for name in ("demand_score", "supply_score", "momentum"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100, got {value}")


class TrendSource(Protocol):
    def fetch(self) -> Iterable[TrendSignal]: ...


def save_trend_signals(signals: Iterable[TrendSignal], path: Path) -> None:
    """Serialize signals back to the JSON shape ``JsonTrendSource`` reads.

    Used by scripts/notebooks that pull live signals from somewhere (e.g.
    a connected TikTok account's trending-sounds chart) and want to persist
    a snapshot for the pipeline to consume via ``JsonTrendSource``.
    """
    payload = [
        {
            "topic": s.topic,
            "niche": s.niche,
            "demand_score": s.demand_score,
            "supply_score": s.supply_score,
            "momentum": s.momentum,
            "sample_hashtags": s.sample_hashtags,
            "notes": s.notes,
            "country_code": s.country_code,
            "source_url": s.source_url,
        }
        for s in signals
    ]
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


@dataclass
class JsonTrendSource:
    """Reads trend signals from a local JSON file.

    Expected shape: a list of objects matching ``TrendSignal`` fields.
    This is deliberately simple — it's the seam where a real trend feed
    plugs in later without touching gap analysis, ideation, or
    generation.
    """

    path: Path

    def fetch(self) -> list[TrendSignal]:
        raw = json.loads(Path(self.path).read_text())
        return [
            TrendSignal(
                topic=item["topic"],
                niche=item["niche"],
                demand_score=item["demand_score"],
                supply_score=item["supply_score"],
                momentum=item["momentum"],
                sample_hashtags=item.get("sample_hashtags", []),
                notes=item.get("notes", ""),
                country_code=item.get("country_code", "GLOBAL"),
                source_url=item.get("source_url"),
            )
            for item in raw
        ]
