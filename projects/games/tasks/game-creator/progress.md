# Прогрес: Game Creator

**Последна актуализация:** 2026-03-17

---

## Фаза 0: Инфраструктура ✅
- [x] Създаване на task директория
- [x] Създаване на description.md, progress.md, discussion.md, todo.md
- [x] Създаване на dist/ структура

## Фаза 1: Research ✅
- [x] Explore games source code — Alpha Family структура
- [x] Анализ на CMakeLists.txt йерархия (само 1 ред в root!)
- [x] Идентифициране на всички ~100+ файла при нова игра
- [x] Анализ на ресурсната структура (RSS system, Rss*Data.json манифести)
- [x] Анализ на math JSON структура (варира по игри: top-level vs roundMain.symbolsData)
- [x] Пълна верига символ → ресурс в burning_hot_coins (WR-014)
- [x] Документиране в `ai_docs/game-creator-research.md`
- [x] Документиране на workflow requirements в `WORKFLOW_REQUIREMENTS.md` (WR-001..018)

## Фаза 2: Config UI ✅
- [x] `game-creator.html` — v2 wizard (6 стъпки)
  - [x] Стъпка 1: Прототип (grid + ръчно)
  - [x] Стъпка 2: Ново Име (snake_case + auto PascalCase)
  - [x] Стъпка 3: Math Файл (file picker + path; чете symbolNames, wildId, scatterIds; поддържа top-level и roundMain структури)
  - [x] Стъпка 4: Настройки (games root, integrations)
  - [x] Стъпка 5: Assets (режим toggle: reuse / нови; gamePrefix + prototypePrefixHint; per-symbol resource table)
  - [x] Стъпка 6: Export (JSON preview + download + clipboard)
  - [x] Dark/light mode; wizard progress bar
- [x] `install.py` — standalone installer за `.agent/tools/`
- [x] `dist/SPEC.md` — design spec (v0.2)

## Фаза 3: Workflow ⏳
- [ ] `workflow.yaml` — 7 стъпки (виж `dist/SPEC.md` + `WORKFLOW_REQUIREMENTS.md`)
- [ ] Стъпка VALIDATE_CONFIG (WR-001, WR-011, WR-012, WR-013)
- [ ] Стъпка CREATE_GAME_MODULE (WR-006, WR-008)
- [ ] Стъпка CREATE_CONFIGS (WR-009)
- [ ] Стъпка CREATE_RESOURCES (WR-002, WR-003, WR-004, WR-007)
- [ ] Стъпка RESOLVE_ASSETS — 3-tier архитектура (WR-015, WR-016, WR-017, WR-018)
- [ ] Стъпка CREATE_INTEGRATIONS (WR-008)
- [ ] Стъпка UPDATE_CMAKE (WR-005)
- [ ] Struct schemas за всяка стъпка
- [ ] Обновяване на `install.py` с workflow copy

## Фаза 4: Testing & Integration ⏳
- [ ] End-to-end тест: клониране на реална игра (burning_hot_coins → dragon_fortune)
- [ ] Провери ModuleManager_*.json — game-specific или идентични?
- [ ] Провери integration app .cpp template
