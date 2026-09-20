"""Turns a scored content gap into a concrete, shootable content brief.

Uses the Claude API when ``ANTHROPIC_API_KEY`` is configured, for
genuinely tailored hooks/scripts/prompts. Without a key, falls back to a
deterministic template so the rest of the pipeline (generation,
publishing) can still be exercised end-to-end in dry-run mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

from content_engine.gap_analysis import ContentGap

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT = """\
You are a TikTok content strategist. Given a single underserved content \
gap (a topic where audience demand currently outstrips existing supply), \
produce ONE concrete, shootable short-form video brief designed for an \
AI video generator (Higgsfield). Reply with ONLY a JSON object, no prose, \
matching exactly this schema:

{
  "hook": "the first ~3 seconds of spoken/on-screen text, written to stop the scroll",
  "beats": ["beat 1", "beat 2", "beat 3", "..."],
  "higgsfield_prompt": "a single detailed visual generation prompt: subject, action, camera, style, mood",
  "caption": "the TikTok caption, ready to post",
  "hashtags": ["#tag1", "#tag2", "..."],
  "cta": "the specific ask at the end (follow, comment, save, etc.)"
}

Ground everything in the gap's topic and rationale you're given. The \
hashtags should mix the niche hashtag with 2-4 more specific ones — \
never just repeat the topic name as a hashtag with no variation. Keep \
beats to 3-5 items; each is a single concrete visual/narrative beat, not \
a vague instruction like "show some footage".
"""


@dataclass(frozen=True)
class ContentBrief:
    topic: str
    gap_score: float
    rationale: str
    hook: str
    beats: list[str]
    higgsfield_prompt: str
    caption: str
    hashtags: list[str]
    cta: str
    sample_hashtags_from_trend: list[str] = field(default_factory=list)


def _fallback_brief(gap: ContentGap) -> ContentBrief:
    """Deterministic, no-API-key brief. Good enough to exercise the
    pipeline; not a substitute for the Claude-generated version."""
    signal = gap.signal
    niche_tag = "#" + signal.niche.lower().replace(" ", "")
    topic_tag = "#" + "".join(ch for ch in signal.topic if ch.isalnum())
    return ContentBrief(
        topic=signal.topic,
        gap_score=gap.gap_score,
        rationale=gap.rationale,
        hook=f"Nobody is talking about {signal.topic} yet — here's why that's about to change.",
        beats=[
            f"Cold open on {signal.topic} with an unexpected visual hook",
            "State the surprising fact or tension driving the trend",
            "Show the payoff / transformation / result",
            "Land the takeaway in one sentence",
        ],
        higgsfield_prompt=(
            f"Cinematic short-form vertical video about {signal.topic}, "
            f"in the {signal.niche} niche, energetic pacing, natural lighting, "
            f"handheld-style camera movement, bold on-screen text overlay for the hook line"
        ),
        caption=f"{signal.topic} — here's what's actually happening. {signal.notes}".strip(),
        hashtags=list(dict.fromkeys([niche_tag, topic_tag, "#fyp", "#trending"])),
        cta="Follow for the full breakdown",
        sample_hashtags_from_trend=signal.sample_hashtags,
    )


def _claude_brief(gap: ContentGap, api_key: str, model: str) -> ContentBrief:
    signal = gap.signal
    user_content = (
        f"Topic: {signal.topic}\n"
        f"Niche: {signal.niche}\n"
        f"Gap score: {gap.gap_score:.1f}/100\n"
        f"Rationale: {gap.rationale}\n"
        f"Known related hashtags: {', '.join(signal.sample_hashtags) or 'none given'}\n"
        f"Extra notes: {signal.notes or 'none'}"
    )
    response = requests.post(
        ANTHROPIC_API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
        },
        timeout=60,
    )
    response.raise_for_status()
    text = response.json()["content"][0]["text"]
    payload = json.loads(text)
    return ContentBrief(
        topic=signal.topic,
        gap_score=gap.gap_score,
        rationale=gap.rationale,
        hook=payload["hook"],
        beats=list(payload["beats"]),
        higgsfield_prompt=payload["higgsfield_prompt"],
        caption=payload["caption"],
        hashtags=list(payload["hashtags"]),
        cta=payload["cta"],
        sample_hashtags_from_trend=signal.sample_hashtags,
    )


def generate_brief(
    gap: ContentGap, anthropic_api_key: str | None, model: str = DEFAULT_MODEL
) -> ContentBrief:
    if not anthropic_api_key:
        return _fallback_brief(gap)
    try:
        return _claude_brief(gap, anthropic_api_key, model)
    except (requests.RequestException, KeyError, json.JSONDecodeError, IndexError):
        # Never let a flaky ideation call take down the whole pipeline —
        # degrade to the template brief and let the caller decide whether
        # to surface the failure.
        return _fallback_brief(gap)
