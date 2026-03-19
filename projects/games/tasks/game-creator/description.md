# Game Creator — Инструмент за клониране на VLT игри

**Дата:** 2026-03-17
**Статус:** В процес 🔄

---

## Контекст

В games проекта всяка нова VLT игра се базира на **Alpha Family framework**-а. В момента създаването на нова игра изисква ръчно копиране на ~100+ файла, адаптиране на CMakeLists.txt, преименуване на класове, подмяна на ресурси и конфигуриране на математики. Процесът е трудоемък и изисква задълбочено познаване на структурата.

**game-creator** автоматизира целия процес: потребителят конфигурира новата игра чрез UI wizard, генерира `game-creator-config.json`, и стартира LLM-driven workflow, който изпълнява клонирането.

## Архитектура (текущо разбиране)

**Двe компоненти:**
1. **Config UI** (`game-creator.html`) — browser-based wizard, генерира JSON config. **✅ Имплементиран (v2).**
2. **Workflow** (`workflow.yaml`) — agentic-control-plane workflow, чете config и изпълнява клонирането. **⏳ Предстои.**

**UI Wizard — текущи стъпки (v2):**
1. Прототип — избор от grid или ръчно въвеждане
2. Ново Име — snake_case, auto PascalCase derivation
3. Math Файл — **задължителен вход**; чете `symbolsData.symbolNames`, wildId, scatterIds
4. Настройки — games root path, integrations (astro / playground / inspired)
5. Assets — режим: "Reuse prototype" (1:1 copy) или "Нови assets" (overlay + prefix + per-symbol resource table)
6. Export — JSON preview, download, clipboard

**Asset Resolution Architecture (3-tier, за workflow):**
- **Tier 1 — Auto (script):** prefix replace (`bh_` → `df_`) в RSS манифестите; детерминистично
- **Tier 2 — Inferred (LLM):** fuzzy matching за подобни имена без точно съответствие
- **Tier 3 — Human:** LLM пита потребителя; записва решението като `user_decision` в config
- Config-ът натрупва `assetResolutions[]` — decision log за reuse при следващ clone

**Config schema (текуща):**
```json
{
  "version": 1,
  "prototype": "burning_hot_coins",
  "newGame": { "snakeName": "dragon_fortune", "pascalName": "DragonFortune", "displayName": "Dragon Fortune" },
  "paths": { "gamesRoot": "C:/mklinks/games" },
  "integrations": ["astro", "playground", "inspired"],
  "math": { "sourcePath": "...", "variantId": "var_8407", "rtp": 0.8407, "destFile": "math/var_8407.json", "symbolNames": [...], "wildId": 8, "scatterIds": [9,10] },
  "assets": {
    "mode": "reuse | new",
    "resourcesDir": null,
    "gamePrefix": "df",
    "prototypePrefixHint": "bh",
    "symbolResources": [...],
    "assetResolutions": [...]
  }
}
```

## Цел

- ✅ UI wizard за генериране на config
- ✅ install.py за копиране в `.agent/tools/`
- ⏳ Workflow (7 стъпки) за автоматично клониране:
  - VALIDATE_CONFIG, CREATE_GAME_MODULE, CREATE_CONFIGS, CREATE_RESOURCES
  - **RESOLVE_ASSETS** (3-tier asset resolution — виж WR-015..018)
  - CREATE_INTEGRATIONS, UPDATE_CMAKE

## Deliverables

| # | Документ | Output | Статус |
|---|----------|--------|--------|
| 1 | Research | `ai_docs/game-creator-research.md` | ✅ Завършен |
| 2 | Design spec | `dist/SPEC.md` | ✅ Завършен (v0.2) |
| 3 | Workflow requirements | `WORKFLOW_REQUIREMENTS.md` | ✅ Активен (WR-001..018) |
| 4 | Config UI | `dist/.agent/tools/game-creator.html` | ✅ Завършен (v2) |
| 5 | Installer | `dist/install.py` | ✅ Завършен |
| 6 | Workflow YAML | `dist/.agent/workflows/game-creator/workflow.yaml` | ⏳ Предстои |

## Ключови находки (summary)

- **ID-базирана архитектура:** Цялата game logic използва числови ID-та; символните имена са само labels — не се ползват в gameplay изчисления
- **Math файлът е mandatory input:** Не може да се генерира; трябва да идва от математик
- **Math JSON структурата варира по игри:** `symbolsData.symbolNames` (top-level) vs `roundMain.symbolsData.symbolNames`
- **idata/ файловете работят по ID:** При "Reuse prototype" не се нужда никаква промяна
- **RSS = Resource System:** Named handles (`REEL_CHERRY_ANIM`) → file paths; дефинирани в `Rss*Data.json` манифести
- **CMake:** Само 1 ред промяна в root `CMakeLists.txt` — добавяне към `EGT_BUILD_GAME_LIST`

## Референтни документи

| Документ | Роля |
|----------|------|
| `WORKFLOW_REQUIREMENTS.md` | Пълни изисквания към workflow-а (WR-001..018) |
| `dist/SPEC.md` | Design spec: UI flow, config schema, workflow steps |
| `ai_docs/game-creator-research.md` | Детайлен анализ на games проект структурата |
| `tasks/agentic-control-plane/dist/.agent/docs/` | Workflow engine документация |

## Key source code files

| Файл | Роля |
|------|------|
| `C:/mklinks/games/CMakeLists.txt` | Root CMake — `EGT_BUILD_GAME_LIST` |
| `C:/mklinks/games/game/alpha_family/plugins/burning_hot_coins/` | Прототип игра (reference) |
| `C:/mklinks/games/resources/burning_hot_coins/` | Ресурси на прототипа (math, idata, RSS манифести) |
| `C:/mklinks/games/configs/burning_hot_coins/modules/` | Module конфиги на прототипа |
| `C:/mklinks/games/integration/astro/apps/src/Egt/AstroBurningHotCoins/` | Integration app на прототипа |
