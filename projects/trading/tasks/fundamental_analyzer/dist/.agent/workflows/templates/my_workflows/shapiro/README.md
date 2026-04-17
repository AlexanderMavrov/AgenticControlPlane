# shapiro-daily-analysis

Fully automated daily workflow for Shapiro contrarian analysis.

## What it does

Replaces the manual `/shapiro` skill with a 7-step automated workflow:

1. **run-pipeline** — Executes `python -m shapiro.runner` to fetch COT data, events, and news failures
2. **load-context** — Reads pipeline output, memory, and narrative files
3. **analyze-newsletters** — Searches Gmail for FT newsletters, updates per-symbol narrative files
4. **score-markets** — Computes Shapiro scores: COT (0-40) + News Failure (0-35) + Narrative (0-25)
5. **update-memory** — Writes `shapiro_memory.md` with current run state and delta from previous
6. **send-alerts** — Pushover + Email notifications for score >= 70
7. **write-analysis** — Generates `shapiro_daily_analysis.md` in Bulgarian

## Scoring Formula

| Component | Max Points | Source |
|-----------|-----------|--------|
| COT Positioning | 40 | Pipeline (cot_percentile) |
| News Failure | 35 | Pipeline (news_failures) |
| FT Narrative | 25 | Gmail newsletters -> narrative files |

**Confidence levels:** CONVICTION (85-100), HIGH (70-84), MEDIUM (50-69), LOW (<50, excluded)

## Prerequisites

- Python pipeline: `shapiro.runner` module in `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer/`
- Gmail MCP server configured in `.mcp.json` with access to `label:FT-Newsletters`
- Shapiro notifier config: `ShapiroConfig.from_env()` for Pushover and Email credentials
- `uv` package manager installed

## Usage

```
/run-workflow shapiro-daily-analysis
/run-workflow shapiro-daily-analysis --lookback_days 7
```

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `lookback_days` | No | 3 | How many days back to search for FT newsletters |

## Output Files

All written to `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer/data/`:

| File | Description |
|------|-------------|
| `shapiro_report.json` | Pipeline output (COT, events, failures) |
| `narratives/{SYMBOL}.md` | Per-symbol FT narrative files |
| `shapiro_memory.md` | Run memory with active setups and changes |
| `shapiro_daily_analysis.md` | Full daily analysis report (Bulgarian) |

## Watchlist

EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, USTEC, US500, US30, US2000, DE40, FR40, JP225, XAUUSD, XAGUSD, XNGUSD, XBRUSD, BTCUSD, ETHUSD
