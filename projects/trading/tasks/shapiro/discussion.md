# Дискусия: Shapiro

---

## 2026-04-18 — Миграция към generic installer

**Контекст:** Първоначално task-ът имаше собствен `dist/` (пълен engine snapshot) + `install.py` на task ниво. С развитието на Agentic Control Plane този pattern стана проблемен — dist/ ставаше stale в сравнение с root engine.

**Решение:** Преместихме на централизиран дизайн:
- Engine живее само в root (`C:/Projects/AgenticControlPlane/`)
- `install.py` на root — generic, с `--task <name>` филтър
- Task-specific workflows в root `.agent/workflows/templates/my_workflows/<name>/`
- Task папките съдържат само tracking docs (description/progress/discussion/todo)

**Ефект за този task:**
- `shapiro/` workflow премина от `fundamental_analyzer/dist/.agent/workflows/templates/my_workflows/shapiro/` към `.agent/workflows/templates/my_workflows/shapiro/` (root)
- Argus се install-ва чрез `python install.py C:/Projects/ElliotWaveAnalyzer --update --task shapiro`

---

## 2026-04-18 — Workflow hardening pass

**Контекст:** Преглед на workflow + create-workflow skill-а откри набор от structural дефекти в shapiro v1.

**Намерени проблеми:**
- Step 1 (run-pipeline) — `subagent: false` + декларирани tools + goal инструкции за subagent → никой не изпълняваше копирането от Argus/data/ към workflow/data/. Gate вероятно fail-ваше при първи run.
- Step 6 (send-alerts) — `shapiro-notifier` script tool декларира `alerts_json_path`, но command-ът приема JSON директно през sys.argv. Goal инструктира raw Python. Tool-ът беше мъртъв код.
- Hardcoded абсолютни пътища към `C:/Users/aleksandar.mavrov/...` навсякъде → не portable между машини.
- Watchlist (20 символа) дупликирана в 3 места в workflow-а.
- Struct schemas бяха минимални (само top-level `markets: object, min_items: 1`).
- Scoring math живееше изцяло в LLM prompt — недетерминистично, скъпо, fragile при threshold tuning.
- Нямаше feedback loop → Phase 4 "анализ на false positives" нямаше реални данни.

**Предприети действия (всички в ACP repo):**
1. workflow.yaml v2 — параметризация (`argus_root`, `watchlist`, `notify` dry-run), поправени двата структурни bug-а, dual-write pattern документиран.
2. 5 struct schemas усилени с enum + per-item validation (standard JSON schema style).
3. `/init-workflow shapiro` → 7 per-step AGENT.md.
4. Добавена VERIFY стъпка към `create-workflow` (предотвратява този клас bug-ове при бъдещи workflows).

**Argus-side work (изчаква Cursor/Antigravity):**
- `argus-prompts/01-extract-scoring.md` — изнеса scoring math в `shapiro/scoring.py` + `shapiro/score_runner.py`.
- `argus-prompts/02-feedback-loop.md` — `shapiro/history.py` + `shapiro/feedback_runner.py` за prediction→outcome tracking.

**Защо не направих Argus частта директно:** Per `elliott_wave_source/CLAUDE.md` policy — Claude Code не пише в Argus; генерира детайлни prompts за Cursor/Antigravity.

---

## 2026-04-18 — Cross-workflow enrichment: analyze_ew ↔ shapiro

**Контекст:** User попита как да комбинира `analyze_ew` skill-а (EW + COT technical scan) с `shapiro` workflow-а (fundamental contrarian scan). Обмислихме три варианта: (a) един голям комбиниран workflow, (b) chain на двата workflow-а, (c) analyze_ew чете shapiro output като enrichment.

**Решение: (c) — enrichment pattern.** Двата остават напълно независими:
- shapiro: daily batch workflow, пише `data/scoring-result.json`
- analyze_ew: on-demand skill, чете market_report.json + optional scoring-result.json

**Причини против комбиниран workflow:**
- Различни cadence (daily batch vs on-demand при преглед на графики)
- 14+ steps в един workflow → крехка chain, failure в единия блокира другия
- Orthogonal логики (fundamental vs technical)

**Имплементация (direct edit в Argus, per user explicit override):**
- Добавена секция "Shapiro Fundamental Enrichment (cross-workflow, optional)" в analyze_ew.md Step 5
- 24h staleness check, per-symbol match
- Нова Quality Modifier table за Shapiro alignment (+3/-3 при HIGH/CONVICTION)
- Нов tier "ULTIMATE (⭐⭐)": EW weekly + COT EXTREME + Shapiro score ≥ 85 same bias
- Response format обновен: COT OVERVIEW table разширена с Shapiro колони; JOURNAL CHECK + NEW OPPORTUNITIES показват Shapiro когато е наличен
- Graceful fallback: липсващ/stale файл → бележка + продължава само с COT

**Защо direct edit (не prompt):** User изрично каза "не ми пиши промпт, а направо извърши промяната". Argus CLAUDE.md не съдържа такова ограничение при проверка; beyond that, user има override authority.

---

## 2026-04-18 — Canonical alignment pass

**Контекст:** След hardening pass-а сравних workflow output format с canonical skill в Argus (`.claude/commands/shapiro.md`). Workflow-ът беше опростен в няколко ключови места и това щеше да доведе до output, който не съвпада с оригиналния Shapiro daily report формат.

**Несъответствия намерени:**
1. **PENDING failure bucket липсваше** — canonical има 10 pts за незатворени свещи (предварителен сигнал). Workflow имаше само STRONG/REVERSE/MODERATE.
2. **EXTREME COT rule липсваше** — canonical винаги включва markets с COT percentile >= 90 или <= 10 в анализа, дори при total_score < 50. Workflow филтрираше само >= 50.
3. **Notifier Python API грешен** — workflow ползваше `PushoverNotifier(cfg).send(title, body, priority=X)`. Canonical ползва `PushoverNotifier(PUSHOVER_USER, PUSHOVER_TOKEN).send(title=, message=, priority=)`. Това би било runtime error при deploy.
4. **Tables опростени** — canonical 6-col risks/confirmations с inline ⚡📊📎 markers; workflow имаше 3-col с отделна "Значимост" колона.
5. **News Failures table липсваше** — canonical има 8-col table само за score >= 65.
6. **Per-market header format** — canonical е 3-level (### SYMBOL — BIAS — Score: X/100 — CONFIDENCE); workflow беше 2-level.

**Действия:**
- workflow.yaml: PENDING bucket + INCLUSION RULE + notifier API fix + full write-analysis rewrite
- scoring-result.schema v3: `include_reason` enum + `markets_extreme_cot` count
- argus-prompts/01: PENDING bucket в `news_failure_score()` + acceptance tests
- Final YAML parse + `init-workflow` — всичко OK

**Поука:** При миграция от prompt-based skill към structured workflow е лесно да загубиш fidelity в output формата. Винаги трябва strict diff срещу canonical source на финала, преди deploy.

---

## Открити въпроси

_(Няма активни.)_
