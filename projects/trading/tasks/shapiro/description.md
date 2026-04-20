# Shapiro — Daily Fundamental Analysis

**Дата:** 2026-04-18
**Статус:** Имплементиран, в употреба 🔄

---

## Контекст

**Shapiro contrarian strategy** — идентифицира setup-и чрез комбинация от три сигнала:

1. **COT positioning** — екстремни позиции на Commercials/Large Specs (40 точки)
2. **News failure** — пазар игнорира фундаментална новина (35 точки)
3. **FT narrative alignment** — дали FT newsletters потвърждават/отричат contrarian теза (25 точки)

Преди този task: анализът се правеше ръчно чрез `/shapiro` skill — бавно, error-prone, не се автоматизира.

Този task имплементира workflow, който пуска целия анализ автоматично всеки ден и генерира доклад на български език.

---

## Deliverables

- [x] `shapiro` workflow в `.agent/workflows/templates/my_workflows/shapiro/`
  - 7 стъпки: run-pipeline → load-context → analyze-newsletters → score-markets → update-memory → send-alerts → write-analysis
  - 4 struct schemas: context-summary, newsletter-analysis, scoring-result, shapiro-report
  - README с цялата документация
- [x] Интеграция с Gmail MCP (FT newsletters)
- [x] Pushover + Email notifications за score ≥ 70
- [x] Автоматичен deploy към Argus чрез `install.py --task shapiro`

---

## Scoring

| Компонент | Max точки | Източник |
|-----------|-----------|----------|
| COT Positioning | 40 | Python pipeline (`cot_percentile`) |
| News Failure | 35 | Python pipeline (`news_failures`) |
| FT Narrative | 25 | Gmail newsletters → narrative files |

**Confidence levels:** CONVICTION (85-100), HIGH (70-84), MEDIUM (50-69), LOW (<50, exclude)

---

## Watchlist

EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD, USTEC, US500, US30, US2000, DE40, FR40, JP225, XAUUSD, XAGUSD, XNGUSD, XBRUSD, BTCUSD, ETHUSD

---

## Предпоставки

- Python pipeline: `shapiro.runner` модул в `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer/`
- Gmail MCP server с достъп до `label:FT-Newsletters`
- `ShapiroConfig.from_env()` за Pushover и Email credentials
- `uv` package manager

---

## Usage

```bash
# Deploy workflow към Argus
cd C:/Projects/AgenticControlPlane
python install.py C:/Projects/ElliotWaveAnalyzer --update --task shapiro

# Стартиране (в Argus)
/run-workflow shapiro
/run-workflow shapiro --lookback_days 7
```

---

## Output файлове

Всички в `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer/data/`:

| Файл | Описание |
|------|----------|
| `shapiro_report.json` | Pipeline output (COT, events, failures) |
| `narratives/{SYMBOL}.md` | Per-symbol FT narrative файлове |
| `shapiro_memory.md` | Run memory с активни setups и промени |
| `shapiro_daily_analysis.md` | Пълен daily analysis report (Bulgarian) |

---

## Референтни документи

- Workflow: `.agent/workflows/templates/my_workflows/shapiro/workflow.yaml`
- README: `.agent/workflows/templates/my_workflows/shapiro/README.md`
- Structs: `.agent/workflows/templates/my_workflows/shapiro/structs/`

### Key source code files (Argus)

- `shapiro/runner.py` — data pipeline (COT, events, failures)
- `shapiro/notifier.py` — Pushover + Email notifier
- `shapiro/config.py` — `ShapiroConfig.from_env()`
