# content-engine

An AI content pipeline for TikTok that starts from a market-gap thesis, not a content calendar: **don't make content because it's trending — make content where demand is outrunning supply.** A topic everyone's already covering (high demand, high supply) is worse to enter than a topic quietly picking up momentum with almost no coverage yet (high momentum, low supply). That scoring judgment is the core of this project; generation and publishing are just the delivery mechanism.

```
trends.py  ─▶  gap_analysis.py  ─▶  ideation.py  ─▶  higgsfield_client.py  ─▶  tiktok_publisher.py
(market      (demand vs. supply    (Claude turns a     (generates the         (Direct Post API,
 signals)     -> ranked gaps)       gap into a brief)    actual video)          private by default)
```

Every stage degrades gracefully with no credentials configured, so `python -m content_engine.cli run` works out of the box in **dry-run mode** — you see real gap scores and real Claude-quality (or template) briefs, with generation/publishing stubbed out. Add API keys incrementally and each stage goes live independently.

## Quick start

```bash
pip install -r requirements.txt
python -m content_engine.cli run --top-n 3
cat output/run_report.json
```

No `.env` needed for this. It reads `data/sample_trends.json` and prints a ranked list of content gaps with generated briefs.

## Going live, one stage at a time

Copy `.env.example` to `.env` and fill in what you have:

1. **Ideation quality** — set `ANTHROPIC_API_KEY` to replace the template briefs with real Claude-written hooks, scripts, and Higgsfield prompts tailored to each gap.
2. **Real video generation** — `pip install higgsfield-client`, get a key from [cloud.higgsfield.ai/api-keys](https://cloud.higgsfield.ai/api-keys), set `HIGGSFIELD_API_KEY`. Check the model you set in `HIGGSFIELD_DEFAULT_MODEL` on Higgsfield's model catalog — they host 50+ models (text-to-video, image-to-video, Soul/identity-consistent) and parameter names vary per model.
3. **Real publishing** — register an app at [developers.tiktok.com](https://developers.tiktok.com), get the `video.publish` scope authorized by the account you want to post as, set `TIKTOK_CLIENT_KEY`/`TIKTOK_ACCESS_TOKEN`. Run with `--publish`.

## The one constraint that shapes everything about step 3

**TikTok forces every unaudited app's posts to private (`SELF_ONLY`) regardless of what privacy level you request, until the app passes TikTok's content-posting audit.** That's TikTok's restriction, not a bug here — `tiktok_publisher.py` enforces the same default itself (see `TIKTOK_APP_AUDITED` in `.env.example`) so you can't accidentally assume you're posting publicly before you actually are. Practically: you can build and test the entire pipeline today, including real posts to your own account, but they'll only be visible to you until the audit clears. Budget for that review cycle before counting on public reach.

There is no way to skip this from the outside — it's enforced server-side by TikTok, not by anything in this repo.

## Where the market-gap data comes from

`data/sample_trends.json` is a hand-seeded example. TikTok doesn't expose a public trends API to third parties, so `trends.py` is built around a small `TrendSource` interface specifically so this can be swapped for something real without touching any other module:

- A paid trends API (Exolyt, Kalodata, TikTok's own Creative Center exports)
- Your own analytics (which of your past posts under- or over-performed relative to their niche)
- Manual research you feed in as JSON, matching the `TrendSignal` shape (`topic`, `niche`, `demand_score`, `supply_score`, `momentum`, `sample_hashtags`, `notes`)

Implement `TrendSource.fetch() -> Iterable[TrendSignal]` against whichever source you pick and pass it to `run_pipeline(trend_source=...)`.

## How the gap score works (`gap_analysis.py`)

```
gap_score = normalize(demand * 0.35 + momentum * 0.45 - supply * 0.40)
```

Momentum is weighted highest deliberately: a topic that's rising *and* under-covered right now is the best window to publish into — by the time supply catches up to demand, the opportunity is gone. A topic with high demand AND high supply scores low even though it "looks" popular, because joining a saturated conversation adds noise, not value. See `tests/test_gap_analysis.py` for the exact behavior this guarantees (e.g. a saturated trend can never outrank a fresh high-momentum one, regardless of raw popularity).

## Project layout

```
content_engine/
  config.py             — env/`.env` loading, all fields optional
  trends.py             — TrendSignal + pluggable TrendSource
  gap_analysis.py        — demand-vs-supply scoring and ranking
  ideation.py            — gap -> content brief (Claude, or template fallback)
  higgsfield_client.py   — content brief -> generated video (or dry-run stub)
  tiktok_publisher.py    — video -> TikTok Direct Post (or dry-run stub)
  pipeline.py            — orchestrates the above, writes output/run_report.json
  cli.py                 — `python -m content_engine.cli run [...]`
data/sample_trends.json  — example market signals to get started
tests/                    — unit tests, all runnable with zero API keys
```

## Running the tests

```bash
pip install pytest
python -m pytest -q
```
