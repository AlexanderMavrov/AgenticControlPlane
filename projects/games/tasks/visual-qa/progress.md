# Прогрес: Visual QA

**Последна актуализация:** 2026-04-16

---

## Фаза 0: Инфраструктура ✅
- [x] Създаване на task директория
- [x] description.md, progress.md, discussion.md, todo.md

## Фаза 1: PoC Validation ✅
- [x] Screenshots от клонирана игра с визуални бъгове (7 bugs injected)
- [x] Reference screenshot от правилно работеща игра
- [x] Resource file paths (burning_hot_coins)
- [x] LLM vision анализ — резултат: 2/7 самостоятелно (зелен текст, деформиран label)
- [x] Извод: vision е слаб за position shifts, alpha, subtle tints → static analysis е primary
- [x] Rule extraction от reference game → 50+ правила в `rules.md`

## Фаза 2: Design ✅
- [x] Design spec (`dist/SPEC.md` v0.1) — 4-step workflow
- [x] Workflow architecture (gather → analyze → visual validate → fix)
- [x] Input config schema
- [x] Output struct schemas (game-model, analysis, visual, fix reports)
- [ ] HTML input collector design (Phase 2 deliverable)

## Фаза 3: Implementation ⏳
- [x] HTML Input Collector (`dist/.agent/tools/visual-qa.html`) — 5-step wizard
- [x] Workflow YAML (`dist/.agent/workflows/visual-qa/workflow.yaml`)
- [x] Struct schemas (4/4):
  - [x] `game-model-report.schema.yaml`
  - [x] `analysis-report.schema.yaml`
  - [x] `visual-report.schema.yaml`
  - [x] `fix-report.schema.yaml`
- [x] Rules document copied to `dist/.agent/docs/visual-qa-rules.md`
- [x] `install.py` — installer script (tested: default, --update, --dry-run)

## Фаза 4: Testing ⏳
- [ ] End-to-end тест с реална игра
