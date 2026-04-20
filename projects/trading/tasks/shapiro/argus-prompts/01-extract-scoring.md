# Cursor/Antigravity Prompt — Extract Shapiro scoring to Python

**Target repo:** `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer` (Argus)
**Goal:** Move the deterministic Shapiro scoring math out of the workflow's LLM step into a Python module. The LLM keeps only the `contrarian_thesis` generation.

---

## Why

Currently the `score-markets` step in the `shapiro` workflow computes COT/News/Narrative scores by reading a points table in the LLM prompt and doing arithmetic. This is:

1. Non-deterministic (same input → possibly different scores)
2. Expensive (every symbol × every run)
3. Fragile (threshold tweaks require workflow edits + re-runs to test)

The math is pure and simple — it belongs in code. The LLM is still useful for the *thesis* (narrative synthesis across COT/news/narrative context).

---

## Plan

### New module: `shapiro/scoring.py`

```python
"""Shapiro contrarian scoring — deterministic component math.

Reads the pipeline output (shapiro_report.json) + per-symbol narrative
metadata and emits per-symbol component scores. The LLM layer adds the
contrarian_thesis on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


Bias = Literal["BULLISH", "BEARISH"]
Crowding = Literal["LONG", "SHORT", "NEUTRAL"]
Confidence = Literal["CONVICTION", "HIGH", "MEDIUM", "LOW"]


@dataclass
class NarrativeMeta:
    direction: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    strength: float  # 0.0 – 1.0


@dataclass
class ScoreComponents:
    symbol: str
    cot_percentile: float
    cot_crowding: Crowding
    cot_score: int
    news_failure_score: int
    news_failure_detail: str
    narrative_score: int
    narrative_detail: str
    total_score: int
    confidence: Confidence
    bias: Optional[Bias]  # None if skipped (cot_score == 0)


def cot_score(percentile: float) -> int:
    """COT points from percentile. 31-69 => 0 (skip entirely)."""
    if percentile >= 90 or percentile <= 10:
        return 40
    if percentile >= 85 or percentile <= 15:
        return 35
    if percentile >= 80 or percentile <= 20:
        return 30
    if percentile >= 70 or percentile <= 30:
        return 15
    return 0


def news_failure_score(failures: list[dict]) -> tuple[int, str]:
    """Highest-scoring failure wins; +5 if multiple in last 5 days (cap 35).

    Buckets:
        STRONG   (<0.25 ATR move)            -> 35
        REVERSE  (price reverses into news)  -> 35
        MODERATE (<0.5 ATR move)             -> 25
        PENDING  (candle not yet closed)     -> 10  [preliminary, NOT confirmed]
        other                                -> 0
    """
    if not failures:
        return 0, "Няма квалифициращи се събития"

    best = 0
    best_detail = ""
    for f in failures:
        kind = f.get("type", "").upper()
        if kind in ("STRONG", "REVERSE"):
            pts = 35
        elif kind == "MODERATE":
            pts = 25
        elif kind == "PENDING":
            pts = 10
        else:
            pts = 0
        if pts > best:
            best = pts
            best_detail = f"{kind}: {f.get('description', '')}"

    if len(failures) > 1 and best > 0:
        best = min(best + 5, 35)
        best_detail += " (+5 multi-failure bonus)"

    return best, best_detail or "Няма квалифициращи се failures"


def narrative_score(
    crowding: Crowding,
    narrative: Optional[NarrativeMeta],
) -> tuple[int, str]:
    """Score how aligned FT consensus is with the CROWD (contrarian signal)."""
    if narrative is None or narrative.direction == "NEUTRAL":
        return 0, "Няма наратив данни"

    aligned = (
        (crowding == "LONG" and narrative.direction == "BULLISH")
        or (crowding == "SHORT" and narrative.direction == "BEARISH")
    )
    if not aligned:
        return 0, f"Несъгласуван: crowd={crowding}, narrative={narrative.direction}"
    if narrative.strength > 0.8:
        return 25, f"Силен consensus aligned with crowd (s={narrative.strength:.2f})"
    if narrative.strength >= 0.6:
        return 15, f"Умерен consensus aligned with crowd (s={narrative.strength:.2f})"
    return 0, f"Слаб consensus (s={narrative.strength:.2f})"


def confidence_level(total: int) -> Confidence:
    if total >= 85:
        return "CONVICTION"
    if total >= 70:
        return "HIGH"
    if total >= 50:
        return "MEDIUM"
    return "LOW"


def contrarian_bias(crowding: Crowding) -> Optional[Bias]:
    if crowding == "LONG":
        return "BEARISH"
    if crowding == "SHORT":
        return "BULLISH"
    return None


def score_market(
    symbol: str,
    market: dict,
    narrative: Optional[NarrativeMeta],
) -> Optional[ScoreComponents]:
    """Score a single market. Returns None if COT score == 0 (skip)."""
    percentile = float(market["cot_percentile"])
    crowding: Crowding = market["cot_crowding"]

    cs = cot_score(percentile)
    if cs == 0:
        return None

    ns, n_detail = news_failure_score(market.get("news_failures", []))
    nar, nar_detail = narrative_score(crowding, narrative)

    total = cs + ns + nar
    conf = confidence_level(total)
    if conf == "LOW":
        return None

    return ScoreComponents(
        symbol=symbol,
        cot_percentile=percentile,
        cot_crowding=crowding,
        cot_score=cs,
        news_failure_score=ns,
        news_failure_detail=n_detail,
        narrative_score=nar,
        narrative_detail=nar_detail,
        total_score=total,
        confidence=conf,
        bias=contrarian_bias(crowding),
    )
```

### New CLI entry: `shapiro/score_runner.py`

```python
"""Score all watchlist markets from shapiro_report.json + narratives.

Usage:
    uv run python -m shapiro.score_runner --output data/scoring-components.json

Reads:
    data/shapiro_report.json
    data/narratives/*.md  (parses frontmatter-ish block for direction + strength)

Writes:
    data/scoring-components.json  (deterministic component scores, no thesis)
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

from shapiro.scoring import NarrativeMeta, score_market


NARRATIVE_DIRECTION_RE = re.compile(
    r"\*\*Direction:\*\*\s+(BULLISH|BEARISH|NEUTRAL)", re.IGNORECASE
)
NARRATIVE_STRENGTH_RE = re.compile(r"\*\*Strength:\*\*\s+([0-9.]+)")


def parse_narrative(path: Path) -> NarrativeMeta | None:
    text = path.read_text(encoding="utf-8")
    d_m = NARRATIVE_DIRECTION_RE.search(text)
    s_m = NARRATIVE_STRENGTH_RE.search(text)
    if not d_m or not s_m:
        return None
    return NarrativeMeta(
        direction=d_m.group(1).upper(),
        strength=float(s_m.group(1)),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="data/shapiro_report.json")
    ap.add_argument("--narratives-dir", default="data/narratives")
    ap.add_argument("--output", default="data/scoring-components.json")
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    narratives_dir = Path(args.narratives_dir)

    results = []
    for symbol, market in report.get("markets", {}).items():
        narrative_file = narratives_dir / f"{symbol}.md"
        narrative = parse_narrative(narrative_file) if narrative_file.exists() else None
        scored = score_market(symbol, market, narrative)
        if scored is not None:
            results.append(asdict(scored))

    results.sort(key=lambda r: r["total_score"], reverse=True)

    out = {
        "scored_at": report["generated_at"],
        "markets_analyzed": len(report.get("markets", {})),
        "markets_qualifying": len(results),
        "results": results,
    }
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {args.output} — {len(results)} qualifying markets")


if __name__ == "__main__":
    main()
```

### Tests: `tests/test_scoring.py` (or wherever tests live in Argus)

Cover: every COT percentile bucket, single STRONG failure, single PENDING
failure (10 pts), multiple failures cap at 35, narrative aligned/misaligned,
CONVICTION/HIGH/MEDIUM/LOW thresholds, NEUTRAL crowding yields None bias.

### Workflow update (I will do this — not Argus work)

After this Argus-side change ships, the `score-markets` step in
`.agent/workflows/templates/my_workflows/shapiro/workflow.yaml` should:

1. Add a script tool `shapiro-scorer` that calls `shapiro.score_runner`.
2. Invoke the tool, then read `scoring-components.json`.
3. LLM's only job: fill in `contrarian_thesis` per market (Bulgarian, 2-3 sentences).
4. Merge thesis into components → write final `scoring-result.json`.

---

## BEFORE / AFTER

### BEFORE

`shapiro/scoring.py` — does not exist.
`shapiro/score_runner.py` — does not exist.
Scoring math lives in LLM prompt at workflow `score-markets` step.

### AFTER

Two new files, purely deterministic. LLM is offloaded from arithmetic.

---

## Acceptance

- `uv run python -m shapiro.score_runner` produces `data/scoring-components.json` with the same structure as today's `scoring-result.json` MINUS the `contrarian_thesis` field.
- Running on a sample `shapiro_report.json` yields identical scores to what the LLM produces today (within rounding — if they disagree, the Python version is the new source of truth).
- Pyright basic mode passes.
- At least 7 unit tests cover: each COT bucket boundary, single STRONG (35), single PENDING (10), multi-failure bonus cap at 35, narrative-aligned vs. misaligned, LOW threshold rejection.
