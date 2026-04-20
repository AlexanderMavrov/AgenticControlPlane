# Cursor/Antigravity Prompt — Shapiro feedback loop (prediction vs. outcome)

**Target repo:** `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer` (Argus)
**Goal:** Persist each day's Shapiro setups and, on the next run, measure what happened to yesterday's predictions. This feeds Phase 4 tuning (cutoff thresholds, false-positive analysis) with real data instead of intuition.

---

## Why

The workflow produces HIGH/CONVICTION setups daily but never looks back. Without a record of "on day D we said BEARISH XAUUSD at score 82; on day D+1 price moved X", threshold tuning is guesswork. A minimal feedback loop turns every daily run into a data point.

This is explicitly blocking Phase 4 ("Анализ на false positives/negatives") from the task's todo.md — there's currently no dataset to analyze.

---

## Plan

### New module: `shapiro/history.py`

Append-only log of daily scored setups + their next-day outcome.

```python
"""Append-only log of Shapiro predictions and measured outcomes.

File format: data/shapiro_history.jsonl — one JSON object per line per prediction.

Schema per entry:
{
    "prediction_date": "YYYY-MM-DD",         # when the setup was called
    "symbol": "EURUSD",
    "bias": "BEARISH",                        # Shapiro's contrarian call
    "total_score": 82,
    "confidence": "HIGH",
    "cot_percentile": 91.3,
    "entry_price": 1.08450,                   # price at prediction_date close
    "outcome_date": "YYYY-MM-DD",             # prediction_date + 1 trading day
    "outcome_price": null,                    # filled on next run
    "outcome_move_pct": null,                 # (outcome - entry) / entry
    "hit": null,                              # bool — did price move in bias direction?
    "resolved": false                         # true once outcome is filled
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class Prediction:
    prediction_date: str
    symbol: str
    bias: str
    total_score: int
    confidence: str
    cot_percentile: float
    entry_price: Optional[float]
    outcome_date: Optional[str] = None
    outcome_price: Optional[float] = None
    outcome_move_pct: Optional[float] = None
    hit: Optional[bool] = None
    resolved: bool = False


def append_predictions(path: Path, entries: list[Prediction]) -> None:
    with path.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")


def load_unresolved(path: Path) -> list[Prediction]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if not d.get("resolved"):
            out.append(Prediction(**d))
    return out


def rewrite_with_updates(path: Path, updated: dict[tuple[str, str], Prediction]) -> None:
    """Rewrite the JSONL, merging resolved outcomes for (prediction_date, symbol)."""
    if not path.exists():
        return
    new_lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        key = (d["prediction_date"], d["symbol"])
        if key in updated:
            d = asdict(updated[key])
        new_lines.append(json.dumps(d, ensure_ascii=False))
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def compute_stats(path: Path) -> dict:
    """Aggregate hit rate by confidence bucket. Only resolved entries."""
    if not path.exists():
        return {"total": 0, "resolved": 0}

    buckets: dict[str, dict] = {
        "CONVICTION": {"hits": 0, "total": 0},
        "HIGH": {"hits": 0, "total": 0},
        "MEDIUM": {"hits": 0, "total": 0},
    }
    total = 0
    resolved = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        total += 1
        if not d.get("resolved"):
            continue
        resolved += 1
        bucket = buckets.setdefault(d["confidence"], {"hits": 0, "total": 0})
        bucket["total"] += 1
        if d.get("hit"):
            bucket["hits"] += 1

    return {
        "total": total,
        "resolved": resolved,
        "by_confidence": buckets,
    }
```

### New CLI entry: `shapiro/feedback_runner.py`

```python
"""Reconcile yesterday's predictions with today's prices, then record today.

Usage:
    uv run python -m shapiro.feedback_runner \
        --scoring data/scoring-result.json \
        --history data/shapiro_history.jsonl

Idempotent — safe to re-run on the same day (dedupes by prediction_date+symbol).
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from shapiro.history import (
    Prediction,
    append_predictions,
    compute_stats,
    load_unresolved,
    rewrite_with_updates,
)
# Reuse whatever price-fetching utility Argus already has for closing prices.
# Likely options in the codebase: MarketDataProvider, yfinance wrapper, etc.
# Pick the one that matches the symbol universe.
from shapiro.data_provider import get_latest_close  # adjust import to what exists


def resolve_outcomes(history_path: Path) -> dict[tuple[str, str], Prediction]:
    unresolved = load_unresolved(history_path)
    resolved = {}
    today = date.today().isoformat()
    for p in unresolved:
        if p.outcome_date is None:
            continue  # not ready to resolve
        if p.outcome_date > today:
            continue  # still in the future
        price = get_latest_close(p.symbol, p.outcome_date)
        if price is None or p.entry_price is None:
            continue
        move = (price - p.entry_price) / p.entry_price
        hit = (move < 0 and p.bias == "BEARISH") or (move > 0 and p.bias == "BULLISH")
        p.outcome_price = price
        p.outcome_move_pct = move
        p.hit = hit
        p.resolved = True
        resolved[(p.prediction_date, p.symbol)] = p
    return resolved


def record_today(scoring_path: Path, history_path: Path) -> int:
    scoring = json.loads(scoring_path.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    new_entries = []
    for r in scoring.get("results", []):
        entry_price = get_latest_close(r["symbol"], today)
        new_entries.append(
            Prediction(
                prediction_date=today,
                symbol=r["symbol"],
                bias=r["bias"],
                total_score=int(r["total_score"]),
                confidence=r["confidence"],
                cot_percentile=float(r["cot_percentile"]),
                entry_price=entry_price,
                # outcome_date: next trading day. Simplification: +1 calendar day.
                # Robust version: use Argus's market calendar util.
                outcome_date=(date.fromisoformat(today)).isoformat(),  # replace with +1 trading day
            )
        )
    # TODO: dedupe — if today's entries already exist in history, skip.
    append_predictions(history_path, new_entries)
    return len(new_entries)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scoring", default="data/scoring-result.json")
    ap.add_argument("--history", default="data/shapiro_history.jsonl")
    args = ap.parse_args()

    history = Path(args.history)
    scoring = Path(args.scoring)

    resolved = resolve_outcomes(history)
    if resolved:
        rewrite_with_updates(history, resolved)

    added = record_today(scoring, history)
    stats = compute_stats(history)

    print(json.dumps({
        "resolved_today": len(resolved),
        "added_today": added,
        "stats": stats,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

### Workflow update (I'll do this — not Argus work)

Add Step 8 `reconcile-history` to the shapiro workflow after `write-analysis`:

```yaml
- name: reconcile-history
  spec_check: false
  subagent: true
  model: haiku
  tools: [shapiro-feedback]
  goal: >
    Record today's setups in the prediction history and resolve yesterday's
    outcomes. Emit updated hit-rate stats so the next daily report can
    reference them.
  inputs:
    - path: data/scoring-result.json
      inject: file
  outputs:
    - path: data/feedback-stats.json
```

Add tool:

```yaml
- name: shapiro-feedback
  type: script
  command: "cd {argus_root} && PYTHONUTF8=1 uv run python -m shapiro.feedback_runner"
  description: "Reconcile yesterday's predictions, record today's, and emit hit-rate stats."
```

And in Step 7 (`write-analysis`), the daily report can now include a new section:

```markdown
## Историческа Статистика (Последни 30 дни)
| Confidence | Total | Resolved | Hit rate |
|------------|-------|----------|----------|
| CONVICTION | {N}   | {M}      | {pct}%   |
| HIGH       | {N}   | {M}      | {pct}%   |
| MEDIUM     | {N}   | {M}      | {pct}%   |
```

This is where threshold tuning starts — after ~2-3 weeks of data, if
MEDIUM hit rate is < 40%, raise the cutoff; if CONVICTION is under 60%,
something in the scoring is miscalibrated.

---

## BEFORE / AFTER

### BEFORE
No history file. No outcome tracking. Phase 4 tuning is pure vibes.

### AFTER
- `data/shapiro_history.jsonl` accumulates one row per (date, symbol) prediction.
- Each row is resolved on the next run with outcome_price + hit flag.
- Daily report includes 30-day rolling hit rate by confidence bucket.

---

## Acceptance

- `uv run python -m shapiro.feedback_runner` runs cleanly.
- First invocation on an empty `shapiro_history.jsonl`: writes today's
  predictions, no outcomes to resolve (stats show `resolved: 0`).
- Second invocation next day: resolves yesterday's rows, writes today's.
- The `get_latest_close` import is wired to whatever market data provider
  Argus already uses (don't add a new one — reuse existing).
- Outcome date uses the project's existing trading calendar util (don't
  hand-roll +1 calendar day — weekends will break it).
- At least 3 unit tests: record only, resolve only, full round-trip.

---

## Open question for the implementer

Argus has multiple data providers (yfinance, twelvedata, ib_insync, ctrader).
Pick the one already configured for daily-close fetches on the watchlist
symbols. If no single provider covers all 20 symbols (FX + indices + crypto),
route per-symbol — but document the routing in `feedback_runner.py`'s
docstring.
