# Дискусия: Game Creator

<!-- Записите са в обратен хронологичен ред (най-новите отгоре). -->
<!-- Технически термини остават на английски. -->

---

### 2026-03-18 — Agentic Control Plane интеграция + Workflow стратегия

**Контекст:** Потребителят добави папка `agentic-control-plane/` вътре в task директорията. Запознахме се с нея и дефинирахме как game-creator workflow-ът ще се изгражда и изпълнява.

#### Местоположение на agentic-control-plane

`tasks/game-creator/agentic-control-plane/dist/` — съдържа пълна дистрибуция на Agentic Control Plane engine-а:

| Директория | Съдържание |
|---|---|
| `.agent/docs/` | Engine документация (overview, workflow-yaml, structs, manifest, trace) |
| `.agent/scripts/` | `gate-check.py`, `schema-validate.py` |
| `.agent/tools/` | `trace-viewer.html`, `workflow-editor.html` |
| `.agent/workflows/templates/predefined/` | Built-in workflows (spec-enforcement, doc-spec-extraction, create-workflow и др.) |
| `.cursor/hooks.json` | Cursor `subagentStop` hook → `gate-check.py` |
| `.cursor/skills/` | `run-workflow`, `learn-workflows`, `spec`, `code-with-spec` |
| `examples/` | `sample-workflow.yaml`, реален trace |

> **При load-task:** Винаги провери дали `agentic-control-plane/dist/` е актуален — може да е обновен. Прегледай `overview.md` и `workflow-yaml.md` ако предстои работа по workflow YAML.

#### Как работи системата (summary за game-creator контекста)

- **Workflow definition:** живее в `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` (user-created)
- **Стартиране в Cursor:** `/run-workflow game-creator --config <path-to-config.json>`
- **Orchestrator:** LLM в Cursor чете `workflow.yaml`, управлява стъпките, spawn-ва subagents
- **Gate system:** след всяка стъпка `gate-check.py` (извикан от `subagentStop` hook) валидира output-а срещу struct schemas; при fail — subagent-ът получава feedback и retry-ва in-place
- **Struct schemas:** `.schema.yaml` файлове в `structs/` подпапка на workflow-а — дефинират очаквания формат на inputs/outputs
- **Context carry-forward:** всяка стъпка получава summary-та от предишните

#### Game-Creator Workflow стратегия

**Ключово решение: config файлът е primary input**
- Потребителят генерира `game-creator-config.json` чрез `game-creator.html` tool-а
- Workflow-ът получава конфига като input param (`--config <path>`) или като inject: file
- Всички стъпки четат от конфига — не се питат потребителя за параметри по средата

**Местоположение на workflow файловете (след инсталация в target проекта):**
```
.agent/workflows/templates/my_workflows/game-creator/
├── workflow.yaml
└── structs/
    ├── validate-report.schema.yaml
    ├── clone-report.schema.yaml
    └── ...
```

**Стъпки на workflow-а (предварителен план):**
1. `VALIDATE_CONFIG` — schema check, name conflict, prototype exists
2. `CREATE_GAME_MODULE` — copy plugins/{prototype}/ → {newGame}/; search-replace naming
3. `CREATE_CONFIGS` — copy configs/{prototype}/ → {newGame}/
4. `CREATE_RESOURCES` — copy resources/{prototype}/ → {newGame}/
5. `RESOLVE_ASSETS` — 3-tier: auto prefix replace → LLM fuzzy → human approval (human gate!)
6. `CREATE_INTEGRATIONS` — copy + search-replace за всеки integration app
7. `UPDATE_CMAKE` — добави newGame в `EGT_BUILD_GAME_LIST`

**spec_check:** `false` за всички стъпки — не модифицираме source код с behavioral specs, правим файлови операции.

**RESOLVE_ASSETS** е единствената стъпка с `gate: human: true` (за tier-3 решения, когато LLM не може да разреши автоматично).

#### Workflow файловете са в task-а, не в agentic-control-plane

Самият `workflow.yaml` и structs-овете ще се пишат и поддържат в `tasks/game-creator/dist/` (заедно с `game-creator.html` и `install.py`). `install.py` ще ги копира в `.agent/workflows/templates/my_workflows/game-creator/` при инсталация.

---

### 2026-03-17 — Asset resolution архитектура: 3-tier система + config като decision log

**Контекст:** Дискусия за как workflow-ът да разреши non-symbol assets (backgrounds, UI, музика) автоматично или с минимална намеса.

**Ключова находка: Разделението script / LLM / human е определящо за архитектурата.**

- Ако всичко е детерминистично (prefix replace, 1:1 структура) → скрипт е достатъчен, LLM не добавя стойност
- LLM е нужен само за „дългата опашка" от edge cases — fuzzy matching, семантично съответствие
- При нерешим случай: LLM пита потребителя → записва отговора в config

**3-tier архитектура (WR-015):**

| Tier | Инструмент | Условие |
|------|-----------|---------|
| 1 — Auto | Script | Prefix replace, 1:1 структура |
| 2 — Inferred | LLM | Fuzzy match, подобни имена |
| 3 — Human | LLM + потребител | Не може да се реши автоматично |

**Config като decision log (WR-017):**
- Всяко взето решение се записва в `config.assets.assetResolutions[]` с тип (auto / inferred / user_decision / skip) и причина
- При следващ clone на подобна игра: вече взетите решения се прилагат директно без ново питане
- Config-ът се превръща от „входни параметри" в „документация на архитектурните решения"

**Нов config параметър (WR-016):**
- `prototypePrefixHint`: `"bh"` — позволява tier-1 automation за ВСИЧКИ assets (не само символните), не само за символните
- С `prototypePrefixHint` + `gamePrefix`: workflow-ът може да автоматично разреши пълния RSS манифест на прототипа

**Допълнителни детайли:** Виж WR-015, WR-016, WR-017, WR-018 в `WORKFLOW_REQUIREMENTS.md`.

---

### 2026-03-17 — Символи: ID-базирана архитектура + нов UI flow

**Контекст:** Анализирахме MathRules.cpp, MathTypes.cpp и idata/ файловете.

**Ключова находка: Цялата game logic работи с числови ID-та. Имената на символите са само labels.**

- `MathRules.cpp` зарежда names в metadata при инициализация, но никога не ги използва в изчисления
- `idata/ReelsView.json` — `rssId` е generic (`REEL_BH_1`, `REEL_BH_2`), НЕ е name-based
- `idata/WinFiguresView.json` — ключовете са числови стрингове (`"0"`, `"1"`), не имена
- `idata/LinesView.json` — same pattern
- C++ кодът никога не чете имена по време на gameplay

**Следствие:** Ако клонираш игра с нов math файл (различни имена, същия брой символи), idata/ файловете работят правилно без промяна — по numeric ID.

**Кога е нужен "mapping" (RSS key rename)?**
- САМО когато подаваш нови animation/sound assets с различни имена (напр. `reel_dragon_anim.dds`)
- Тогава `WinFiguresView.json` и `LinesView.json` трябва да map-нат ID 0 → новото RSS key
- Ако използваш assets на прототипа → mapping не е нужен

**Нов UI flow (v2):**
- Math файлът е задължителен вход (Стъпка 3) — дефинира символите и математиката
- Assets стъпка (Стъпка 5) избираш: "Reuse prototype assets" (без mapping) или "Supply new assets" (overlay + RSS key mapping)
- Figure mapping вече не е за имена на символи, а за RSS key преименуване в idata/ файлове

**Design decision:** UI-ът трябва да се преработи да отразява v2 flow. Текущата Стъпка 4 (figure mapping по имена) се заменя с нов подход.

---

### 2026-03-17 — Figure mapping: как работи и какво засяга

**Контекст:** Проучихме как точно се реферират имена на фигури в ресурсите на `burning_hot_coins`.

#### Находки

**Имената на фигурите НЕ са в MathTypes.h.** C++ структурите само десериализират JSON. Реалните имена са в:
```
resources/{game}/math/var_*.json → symbolsData.symbolNames
```

**Фигурите за burning_hot_coins** (от `var_8407.json`):
| ID | Символ | Роля |
|----|--------|------|
| 0 | CHERRY | обикновен |
| 1 | LEMON | обикновен |
| 2 | ORANGE | обикновен |
| 3 | PLUM | обикновен |
| 4 | BELL | обикновен |
| 5 | GRAPES | обикновен |
| 6 | WATERMELON | обикновен |
| 7 | SEVEN | обикновен |
| 8 | WILD | wild (wildId=8) |
| 9 | STAR | scatter (scatterIds=[9,10]) |
| 10 | DOLLAR | scatter |

**Символните имена се появяват в 3 различни форми в ресурсите:**

| Форма | Пример | Файлове |
|-------|--------|---------|
| **Bare string** | `"CHERRY"` | `math/var_*.json` (symbolNames масив), `idata/ReelsView.json` (name поле) |
| **Префикс в RSS ID** | `REEL_CHERRY_ANIM`, `WIN_FIGURE_CHERRY_SOUND` | `idata/WinFiguresView.json`, `idata/LinesView.json`, `RssImagesSeqData.json`, `RssSoundsData.json` |
| **Path fragment в image paths** | `bh_r_cherry.dds` | `RssImagesData.json` |

**Пълен списък файлове, засегнати от figure rename (CHERRY→DRAGON):**

| Файл | Тип промяна |
|------|------------|
| `math/var_*.json` | `symbolNames[0]`: `"CHERRY"` → `"DRAGON"` |
| `idata/ReelsView.json` | `symbolsConfig[0].name`: `"CHERRY"` → `"DRAGON"` |
| `idata/WinFiguresView.json` | RSS key value: `"REEL_CHERRY_ANIM"` → `"REEL_DRAGON_ANIM"` |
| `idata/LinesView.json` | Sound key: `"WIN_FIGURE_CHERRY_SOUND"` → `"WIN_FIGURE_DRAGON_SOUND"` |
| `RssImagesSeqData.json` | Animation ID: `"id": "REEL_CHERRY_ANIM"` → `"id": "REEL_DRAGON_ANIM"` |
| `RssSoundsData.json` | Sound ID: `"id": "WIN_FIGURE_CHERRY_SOUND"` → `"id": "WIN_FIGURE_DRAGON_SOUND"` |
| `RssImagesData.json` | Image paths: `bh_r_cherry.dds` → нови asset имена |

**Важна бележка:** `v/` директорията (view layouts) **не** реферира символни имена — използва generic RSS ключове. Figure mapping не засяга нея.

**Важна бележка 2:** RSS ID стринговете в `idata/` са специфични за прототипа (prefix `bh_` за burning_hot_coins, `REEL_BH_*` за image IDs). При pure copy, тези ID-та ще се копират непроменени в новата игра — валидно, но объркващо. При figure rename, само name частта в composite ID-та трябва да се промени (CHERRY→DRAGON), не prefix-а (REEL_ и WIN_FIGURE_ остават).

#### Решение за UI

В Стъпка 4 е добавен file picker ("Зареди math JSON от прототипа"). Потребителят избира `resources/{prototype}/math/var_*.json`, браузърът чете `symbolsData.symbolNames` и попълва лявата колонка автоматично. Не се hardcode-ват имена.

---

### 2026-03-17 — Resource overlay ограничения

**Въпрос:** Трябва ли overlay директорията да има същата файлова структура като `games/resources/{game}/`?

**Отговор:** Да — текущият overlay механизъм е прост file-by-file copy по относителен path. Файловете трябва да съвпадат по структура.

**Конкретен случай:** Ресурсите на `italy_games` (напр. `ZodiacWheel`) имат различна конвенция от `games` проекта — различни JSON манифести, различна йерархия. За да се използват, е нужна конверсия (italy_games формат → games формат), която генерира `RssImagesData.json`, `AllRssData.json` и т.н.

**Design decision:** Конверсията на italy_games ресурси е извън scope-а на game-creator v1. Overlay полето е предназначено само за активи, вече организирани в games resource структурата. За тестване → оставяй празно (pure copy от прототипа).

---

### 2026-03-17 — Инициализация на задачата

**Контекст:** Задачата е инициализирана на базата на описание от потребителя.

**Ключови решения при инициализация:**

- **Местоположение на task-а:** `projects/games/tasks/game-creator/` — тъй като е специфичен за games проекта
- **Базиран на agentic-control-plane:** Tool-ът ще се инсталира като разширение на agentic-control-plane, следвайки същите конвенции (dist/ структура, install.py)
- **UI подход:** Standalone HTML/JS tool (без framework зависимости), по модела на trace-viewer.html и workflow-editor.html
- **Workflow engine:** Ще използваме съществуващия agentic-control-plane workflow engine — game-creator ще дефинира нов workflow.yaml
- **Две компоненти:** (1) UI за генериране на config + (2) LLM workflow за изпълнение на клонирането
- **Собствен install.py** за game-creator (не разширение на agentic-control-plane)
- **Workflow** отива в `.agent/workflows/game-creator/` (user space, не predefined)

**Отворени въпроси:**
- Трябва ли workflow-ът да поддържа отмяна (rollback) при failure?
