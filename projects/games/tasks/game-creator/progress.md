# Прогрес: Game Creator

**Последна актуализация:** 2026-03-19

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

## Фаза 3: Workflow ✅
- [x] `workflow.yaml` — 8 стъпки (итеративно разработени, верифицирани срещу source code)
- [x] Step 1: `copy-and-rename-plugin` — копиране на plugin dir + rename dirs/files (WR-006)
- [x] Step 2: `rename-in-source-files` — find/replace в .cpp/.h/.data.h и CMakeLists.txt (WR-006, WR-008)
- [x] Step 3: `register-in-root-cmake` — добавяне в EGT_BUILD_GAME_LIST (WR-005)
- [x] Step 4: `create-configs` — copy configs/, rename, global replace, math setup update (WR-009)
- [x] Step 5: `create-resources` — copy resources/, math file, RssRawData, optional overlay (WR-002, WR-003, WR-004, WR-007)
- [x] Step 6: `create-integrations` — per integration: copy/rename, 4-way text replace (WR-008)
- [x] Step 7: `create-playground-manifest` — copy playground configs/, update manifest.json
- [x] Step 8: `validate-and-build` — filesystem scan, CMake configure + build validation
- [x] Struct schemas за всяка стъпка (8 schema файла)
- [x] Обновяване на `install.py` с workflow copy (10 файла: tool + workflow.yaml + 8 schemas)

## Фаза 4: Testing & Integration ⏳
- [ ] End-to-end тест: клониране на реална игра (burning_hot_coins → test game)
- [ ] Обновяване на `dist/SPEC.md` да отразява финалната workflow структура
- [ ] Проверка дали `displayName` трябва да се записва някъде (config го има, но нито един step не го използва)
