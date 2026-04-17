# Visual QA — Визуален тестер за VLT игри

**Дата:** 2026-04-16
**Статус:** В процес

---

## Контекст

След успешно клониране на игра чрез game-creator workflow-а, се наблюдават визуални бъгове — разместени ресурси, грешни символи на екрана. Тези проблеми не се засичат от static validation (файловете са налични, JSON-ите са валидни), но са видими при рендериране.

**visual-qa** е standalone tool за визуално тестване на ВСЯКА Alpha Family VLT игра — не само клонирани, а всяка игра с потенциални визуални проблеми.

## Подход

LLM vision-based анализ: моделът изгражда "mental model" на играта от config/resource файловете, после сравнява с реални screenshots и идентифицира несъответствия.

**Как LLM-ът "знае" как трябва да изглежда играта:**
1. Math file → символи (имена, ID-та, роли: wild/scatter/regular)
2. RSS манифести → кой image файл отговаря на кой RSS ID
3. idata/ view configs → layout: позиции, размери, z-order на всеки елемент
4. Reference screenshot от друга (правилна) игра → общата layout структура на Alpha Family

**Два типа проблеми (фокус):**
- **Тип 2 — Грешни ресурси:** файлът съществува, но е на грешен символ/позиция
- **Тип 3 — Разместени елементи:** координати/позиции в idata/ views са грешни

**Допълнително (nice-to-have):**
- Тип 1 — липсващи ресурси (RSS → несъществуващ файл)
- Тип 4 — грешни размери (sprite coords vs actual image dimensions)
- Тип 5 — липсващи RSS ID-та (idata → несъществуващ RSS ключ)

## Архитектура

**Две компоненти (планирани):**
1. **HTML Input Collector** — събира входни данни (paths, screenshots, game name) и генерира JSON config за workflow-а
2. **Workflow** — multi-step LLM analysis: gather model → analyze screenshots → diagnose → fix

**Workflow стъпки (предварителен план):**
1. `gather-game-model` — чете math, RSS, idata, resource файлове; изгражда модел на очакваната визуализация
2. `capture-states` — приема paths към screenshots (user ги прави през playground); states: idle, spin result, win, bonus
3. `visual-analysis` — LLM vision сравнява screenshots с модела; идентифицира findings
4. `diagnose-root-cause` — за всеки finding проследява resource pipeline обратно до конкретен файл/entry
5. `fix-issues` — предлага и прилага промени; ASK ON AMBIGUITY

## Текуща фаза: PoC

Преди да строим workflow, валидираме подхода ръчно:
- User подава screenshots + resource paths
- LLM анализира директно в conversation
- Оценяваме accuracy на vision detection

## Deliverables

| # | Документ | Output | Статус |
|---|----------|--------|--------|
| 1 | PoC validation | (в conversation) | В процес |
| 2 | Design spec | `dist/SPEC.md` | Планиран |
| 3 | HTML Input Collector | `dist/.agent/tools/visual-qa.html` | Планиран |
| 4 | Workflow YAML | `dist/.agent/workflows/visual-qa/workflow.yaml` | Планиран |
| 5 | Struct schemas | `dist/.agent/workflows/visual-qa/structs/` | Планиран |

## Референтни документи

| Документ | Роля |
|----------|------|
| `projects/games/tasks/game-creator/ai_docs/game-creator-research.md` | Alpha Family архитектура, RSS система, resource pipeline |
| `projects/games/tasks/game-creator/WORKFLOW_REQUIREMENTS.md` | Resource structure details (WR-002..004, WR-007, WR-014..018) |
