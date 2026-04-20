# Прогрес: Shapiro

**Последна актуализация:** 2026-04-18 (workflow hardening pass)

---

## Фаза 0: Инфраструктура ✅
- [x] Създаване на task директория `projects/trading/tasks/shapiro/`
- [x] Миграция от стар `dist/` + собствен `install.py` към споделен root installer

## Фаза 1: Data Pipeline (Python) ✅
- [x] `shapiro.runner` — COT data fetching (Quandl)
- [x] Events detection (economic calendar)
- [x] News failure detection (post-event price action)
- [x] Output: `data/shapiro_report.json`

## Фаза 2: Workflow ✅
- [x] 7-step workflow в `.agent/workflows/templates/my_workflows/shapiro/`
  - [x] Step 1: run-pipeline — извиква `shapiro.runner`
  - [x] Step 2: load-context — чете pipeline output + memory + narratives
  - [x] Step 3: analyze-newsletters — Gmail MCP, FT newsletters
  - [x] Step 4: score-markets — COT (40) + News (35) + Narrative (25)
  - [x] Step 5: update-memory — `shapiro_memory.md`
  - [x] Step 6: send-alerts — Pushover + Email за score ≥ 70
  - [x] Step 7: write-analysis — Bulgarian daily report
- [x] 4 struct schemas (context-summary, newsletter-analysis, scoring-result, shapiro-report)

## Фаза 3: Deploy Integration ✅
- [x] Миграция на workflow от task `dist/` към root `my_workflows/shapiro/`
- [x] Тест на `install.py --task shapiro` към Argus — успешен
- [x] Верификация: в Argus има само shapiro, не game-creator/visual-qa (правилен филтър)

## Фаза 3.5: Workflow Hardening ✅ (2026-04-18)
- [x] workflow.yaml v2: fix run-pipeline output path mismatch (+ subagent:true + explicit copy)
- [x] workflow.yaml v2: fix send-alerts tool/goal несъответствие (removed broken shapiro-notifier tool)
- [x] Parametrize `argus_root`, `watchlist`, `notify` (dry-run support)
- [x] Strengthened struct schemas (newsletter-analysis, scoring-result, context-summary, alerts-summary) — per-item validation with enums
- [x] `/init-workflow shapiro` — създадени 7 per-step AGENT.md дефиниции
- [x] Added VERIFY step към create-workflow (catches this class of bugs преди deploy)
- [x] Argus prompts готови: `argus-prompts/01-extract-scoring.md`, `argus-prompts/02-feedback-loop.md`

## Фаза 3.6: Canonical Alignment ✅ (2026-04-18)
Преглед vs. canonical `C:/Projects/ElliotWaveAnalyzer/.claude/commands/shapiro.md`:
- [x] score-markets: добавен PENDING failure bucket (10 pts) + INCLUSION RULE за EXTREME COT
- [x] send-alerts: поправен notifier API — explicit-creds constructor + named args (`p.send(title=, message=, priority=)`)
- [x] write-analysis: пренаписан към canonical формат (6-col risks/confirmations, 8-col news failures, 5-col events, ⚡📊📎 inline markers, 3-level per-market header, "## Оценени Пазари" wrapper)
- [x] scoring-result.schema v3: `include_reason` enum `[scored, extreme_cot]`, `markets_extreme_cot`, разрешено `confidence: LOW`
- [x] analyze-newsletters: Bulgarian source contributions table + audit-trail правила
- [x] Argus prompt 01 обновен с PENDING bucket (10 pts) + acceptance tests
- [x] Final YAML parse validation — 7 steps, 4 params, 5 structs всички OK

## Фаза 4: Operational Use 🔄
- [ ] Restart Claude Code (new per-step agents + new create-workflow-verify agent)
- [ ] Deploy към Argus: `python install.py C:/Projects/ElliotWaveAnalyzer --update --task shapiro`
- [ ] Мониторинг на daily runs за 2-3 седмици
- [ ] Execute Argus prompt 01 (scoring extraction) — unblocks deterministic scoring
- [ ] Execute Argus prompt 02 (feedback loop) — unblocks Phase 4 threshold tuning
- [ ] Tuning на scoring thresholds след като feedback loop акумулира 2-3 седмици данни
