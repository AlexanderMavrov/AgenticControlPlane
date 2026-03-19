# Workflow Requirements & Constraints

> Живи бележки — всеки открит извод, проблем или наблюдение, което workflow-ът трябва да съблюдава.
> Актуализира се при всяка нова находка по време на research/дискусия.
> Използва се като reference при имплементацията на `workflow.yaml`.

---

## WR-001 — Math файлът е задължителен вход

**Открито:** 2026-03-17
**Контекст:** Math файлът (`var_*.json`) съдържа пълния сертифициран математически модел — reel strips, paytable, вероятности, wildId, scatterIds. Не може да се генерира автоматично.

**Изисквания към workflow-а:**
- Workflow-ът ТРЯБВА да получи math файл като вход — не може да го генерира
- Math файлът се копира директно в `resources/{newGame}/math/`
- Workflow-ът трябва да валидира структурата: задължителни полета `symbolsData.symbolNames`, `symbolsData.wildId`, `symbolsData.scatterIds`
- Ако math файлът липсва → STOP, не продължава

---

## WR-002 — Символите са ID-базирани, не name-базирани

**Открито:** 2026-03-17
**Контекст:** Анализ на MathRules.cpp, idata/ файловете. Цялата game logic използва числови ID-та (0, 1, 2...). Имената са само labels/metadata.

**Изисквания към workflow-а:**
- При copy на `idata/` файлове — НЕ е нужна замяна на символни имена. Файловете работят правилно по numeric ID
- `idata/ReelsView.json` — `rssId` стойности (`REEL_BH_1`, `REEL_BH_2`) са generic и не зависят от имена
- `idata/WinFiguresView.json` — ключовете са числови стрингове; стойностите (RSS keys) могат да останат от прототипа
- `idata/LinesView.json` — same
- Workflow-ът НЕ трябва да прави string-replace на символни имена в idata/ при обикновено клониране

---

## WR-003 — RSS Key mapping е само при нови assets

**Открито:** 2026-03-17
**Контекст:** Стойностите в `idata/WinFiguresView.json` и `idata/LinesView.json` са RSS ключове (напр. `REEL_CHERRY_ANIM`). Те реферират entries в `RssImagesSeqData.json` и `RssSoundsData.json`.

**Изисквания към workflow-а:**
- RSS key mapping се прилага САМО ако потребителят е указал нови assets
- Ако assets режим = "Reuse prototype" → копирай idata/ 1:1, не правй промени
- Ако assets режим = "New assets" → workflow трябва да обнови RSS key стойностите в idata/ файловете, И да провери че съответните entries съществуват в `RssImagesSeqData.json` и `RssSoundsData.json`
- Gate: след RSS key mapping, всеки RSS key в idata/ трябва да има matching entry в Rss*Data.json файловете

---

## WR-004 — Различен брой символи изисква нови idata/ файлове

**Открито:** 2026-03-17
**Контекст:** idata/ файловете имат entries за всеки символ по numeric ID (0..N-1). Ако новата игра има различен брой символи от прототипа, entries трябва да се добавят/премахват.

**Изисквания към workflow-а:**
- При стартиране: сравни `len(newGame.math.symbolNames)` с `len(prototype.math.symbolNames)`
- Ако броят е различен:
  - `idata/ReelsView.json` → symbolsConfig масивът трябва да има точно N entries
  - `idata/WinFiguresView.json` → ключове 0..N-1 (добави или премахни)
  - `idata/LinesView.json` → sound keys 0..N-1
  - `RssImagesData.json` → add/remove image entries
  - `RssImagesSeqData.json` → add/remove animation entries
  - `RssSoundsData.json` → add/remove sound entries
- **Внимание:** Добавянето на entries изисква реални asset имена — workflow-ът не може да ги генерира. При различен брой символи + нови assets, workflow-ът трябва да поиска explicit mapping за новите символи
- Gate: `len(symbolsConfig)` в `idata/ReelsView.json` == `len(newMath.symbolNames)`

---

## WR-005 — CMake промяна: само 1 ред в root CMakeLists.txt

**Открито:** 2026-03-17
**Контекст:** CMake системата е autodiscovery-базирана. Единствената задължителна промяна е добавяне на играта към `EGT_BUILD_GAME_LIST` в root `CMakeLists.txt`.

**Изисквания към workflow-а:**
- Намери `set(EGT_BUILD_GAME_LIST ...)` блока в `CMakeLists.txt`
- Добави `{newGame.snakeName}` към списъка (semicolon-separated)
- НЕ трябва да модифицира нищо друго в CMake файловете
- Gate: `{newGame.snakeName}` присъства в `EGT_BUILD_GAME_LIST` след промяната
- **Внимание:** CMake cache variable може да е на един ред или multi-line; workflow-ът трябва да обработи и двата случая

---

## WR-006 — Naming convention е строга и предсказуема

**Открито:** 2026-03-17
**Контекст:** Всички имена се извличат механично от snake_case.

**Изисквания към workflow-а:**
- Преди всяка стъпка workflow-ът трябва да изчисли и използва консистентно:

| Стойност | Извличане | Пример |
|----------|-----------|--------|
| `snakeName` | директно от config | `dragon_fortune` |
| `pascalName` | toPascal(snakeName) | `DragonFortune` |
| `libPrefix` | `Egt{Pascal}` | `EgtDragonFortune` |
| `libFsm` | `Egt{Pascal}FsmStatic` | `EgtDragonFortuneFsmStatic` |
| `integrationApp` | `{Integration}{Pascal}` | `AstroDragonFortune` |
| `executableTarget` | lowercase(`{integration}{pascal}`) | `astrodragonfortune` |

- Search-and-replace при copy на C++ файлове трябва да замести ВСИЧКИ форми едновременно

---

## WR-007 — Resource overlay изисква съвместима структура

**Открито:** 2026-03-17
**Контекст:** Overlay механизмът е file-by-file copy по относителен path. Italy_games ресурси имат различен формат.

**Изисквания към workflow-а:**
- Ако `resourcesDir` е зададен: копирай файлове от там върху `resources/{newGame}/` по relative path
- НЕ валидира дали структурата е правилна — отговорност на потребителя
- Добави warning в output ако overlay директорията изглежда да е от italy_games формат (heuristic: няма `AllRssData.json`)
- Gate след overlay: `AllRssData.json` трябва да съществува в `resources/{newGame}/`

---

## WR-008 — Integration apps: 1 .cpp + 1 CMakeLists.txt на игра × integration

**Открито:** 2026-03-17
**Контекст:** За всяка комбинация игра × integration се генерира отделен executable с фиксиран boilerplate.

**Изисквания към workflow-а:**
- За всеки integration в `config.integrations`:
  - Копирай `integration/{integration}/apps/src/Egt/{Integration}{Prototype}/` → `{Integration}{NewGame}/`
  - Search-and-replace на class names в `.cpp` и `CMakeLists.txt`
  - `EGT_REGISTER_CLASS` блокът трябва да регистрира 4-те нови модула
- Gate: `.cpp` файлът съдържа `EGT_REGISTER_CLASS(IModule, {Pascal}Fsm)` и останалите 3 модула

---

## WR-009 — Configs: 5 JSON файла, модул имената са game-specific

**Открито:** 2026-03-17
**Контекст:** `configs/{game}/modules/` съдържа 5 файла. `{GameName}Modules.json` изброява 4-те модула по C++ клас имена.

**Изисквания към workflow-а:**
- Копирай `configs/{prototype}/modules/` → `configs/{newGame}/modules/`
- Rename файловете: `{Prototype}Modules.json` → `{NewGame}Modules.json`, `{Prototype}DebugModules.json` → `{NewGame}DebugModules.json`
- В JSON съдържанието: замени всички occurrences на `{Prototype}` → `{NewGame}` в `"name"` полетата
- `ModuleManager_*.json` файловете обикновено са идентични за всички игри — копирай без промяна (но провери)
- Gate: JSON е валиден след промените; 4-те модула присъстват с правилни имена

---

## WR-010 — Без rollback в v1

**Открито:** 2026-03-17
**Контекст:** Design decision.

**Изисквания към workflow-а:**
- Workflow-ът НЕ имплементира автоматичен rollback при failure
- При failure: логва точно кои файлове са създадени/модифицирани до момента на грешката
- Потребителят трябва ръчно да почисти при нужда
- TODO за v2: добави `--dry-run` режим, който показва какво ще се промени без да пише файлове

---

## WR-011 — Validate конфликт на имена преди старт

**Открито:** 2026-03-17
**Контекст:** Ако играта вече съществува (директорията присъства), workflow-ът не трябва да я презапише мълчаливо.

**Изисквания към workflow-а:**
- В Стъпка VALIDATE_CONFIG:
  - Провери дали `game/alpha_family/plugins/{snakeName}/` вече съществува → ERROR ако да
  - Провери дали `configs/{snakeName}/` вече съществува → ERROR ако да
  - Провери дали `resources/{snakeName}/` вече съществува → ERROR ако да
  - Провери дали прототипът съществува → ERROR ако не
- Gate failure при конфликт → не продължава

---

## WR-012 — Math файлът диктува символния брой за idata/ валидация

**Открито:** 2026-03-17
**Контекст:** symbolNames масивът в новия math файл определя колко символа има играта.

**Изисквания към workflow-а:**
- При VALIDATE_CONFIG: прочети `newMath.symbolsData.symbolNames.length` → запази като `expectedSymbolCount`
- При CREATE_RESOURCES: след copy на `idata/ReelsView.json`, валидирай `symbolsConfig.length == expectedSymbolCount`
- Ако count е различен → workflow спира и предупреждава кои idata/ файлове трябва да се адаптират ръчно

---

## WR-013 — Math файловете имат различна JSON структура по игри

**Открито:** 2026-03-17
**Контекст:** При тест с Rise of Ra — грешка „не намерих symbolsData.symbolNames". Оказа се, че структурата се различава:

| Игра | Path до symbolNames |
|------|-------------------|
| `burning_hot_coins` | `symbolsData.symbolNames` (top-level) |
| `joker_reels_coins_10` | `symbolsData.symbolNames` (top-level) |
| `rise_of_ra` | `roundMain.symbolsData.symbolNames` |
| `nordic_rush` | `roundMain.symbolsData.symbolNames` |

Допълнителни разлики:
- `rise_of_ra`, `nordic_rush`: използват `coinId` (single int) вместо `scatterIds` (array)
- `rise_of_ra`, `nordic_rush`: имат `roundMain` и `roundFree` секции

**Изисквания към workflow-а:**
- При четене на math файл — опитвай множество пътища в ред:
  1. `symbolsData.symbolNames`
  2. `roundMain.symbolsData.symbolNames`
- При четене на wildId/scatterIds — проверявай и за `coinId` като алтернатива на `scatterIds`
- Ако нито един path не съвпадне → ERROR с ясно съобщение кои пътища са опитани
- При copy на math файл в новата игра — копирай целия файл без структурни промени; само символните имена в `symbolNames` масива могат да са различни (ако новата игра има различни имена)

---

## WR-014 — Ресурсните пътища следват предсказуем pattern по символно име

**Открито:** 2026-03-17
**Контекст:** Анализ на пълната верига символ → ресурс в burning_hot_coins.

**Пълна верига:**
```
Symbol ID 0 (CHERRY)
  ├─ idata/ReelsView.json     → rssId = "REEL_BH_1"  (generic, positional)
  ├─ RssImagesData.json       → REEL_BH_1 → p/reels/reelline/bh_REELLINE/.../bh_r_cherry.dds
  ├─ idata/WinFiguresView.json → "0": "REEL_CHERRY_ANIM"  (name-based RSS key)
  ├─ RssImagesSeqData.json    → REEL_CHERRY_ANIM → p/reels/cherry/cherry_normal/bh_r_cherry_{01-57}.dds
  └─ RssSoundsData.json       → WIN_FIGURE_CHERRY_SOUND → s/bg_cherry.wav
```

**Конвенция (за burning_hot_coins, prefix = "bh"):**

| Тип ресурс | Файлов pattern |
|-----------|---------------|
| Static sprite | `p/reels/reelline/{prefix}_REELLINE/{prefix}_r_reelline_{size}/{prefix}_r_{name_lower}.dds` |
| Win animation | `p/reels/{name_lower}/{name_lower}_normal/{prefix}_r_{name_lower}_{01-57}.dds` (57 кадъра, 100ms/кадър) |
| Win sound | `s/bg_{name_lower}.wav` |

**Изисквания към workflow-а:**
- При режим "нови assets": workflow-ът трябва да знае **game prefix** на новата игра (напр. `df` за dragon_fortune)
- С prefix + символни имена (от math файла) workflow-ът може да генерира очакваните пътища за всеки символ
- Ако файловете в overlay директорията следват конвенцията → автоматично се намират без допълнителна конфигурация
- Ако файловете имат различни имена → потребителят трябва да посочи mapping или да преименува файловете

**Backgrounds и UI елементи** не са обвързани със символи — копират се директно чрез overlay, без mapping.

**Забележка:** `rssId` в `idata/ReelsView.json` е generic (`REEL_BH_1`) и **не се променя** при клониране — рефереира директно файловия path в `RssImagesData.json`. Само `WinFiguresView.json` и `LinesView.json` използват name-based RSS ключове.

**Config поле нужно за workflow:**
```json
"assets": {
  "mode": "new",
  "gamePrefix": "df",        ← нужен за генериране на очаквани пътища
  "resourcesDir": "C:/...",
  "rssKeyMapping": [...]
}
```

---

## WR-015 — Asset Resolution: 3-tier архитектура (script / LLM / human)

**Открито:** 2026-03-17
**Контекст:** Non-symbol assets (backgrounds, UI елементи, музика, idle animations) не следват предсказуем pattern обвързан с math файла. Ако всичко е 100% детерминистично, LLM не е необходим — скрипт е достатъчен. LLM добавя стойност само при неопределеност.

**Трите нива:**

| Ниво | Инструмент | Условие | Резултат |
|------|-----------|---------|---------|
| 1 — Auto | Script (детерминистично) | Prefix replace, 1:1 структура | `resolution: "auto"` |
| 2 — Inferred | LLM (fuzzy reasoning) | Подобни имена, различна структура | `resolution: "inferred"` |
| 3 — Human | LLM + потребител | LLM не може да реши | `resolution: "user_decision"` |
| — | Skip | Entry не е нужен в новата игра | `resolution: "skip"` |

**Изисквания към workflow-а:**
- Workflow-ът ТРЯБВА да обработи всеки RSS entry от прототипа — нито един не може да остане нерешен
- Tier 1: изпълнява автоматично, без user interaction
- Tier 2: LLM предлага resolution с обяснение → изчаква потвърждение; потребителят може да промени предложението
- Tier 3: LLM задава конкретен въпрос с конкретни опции; записва отговора като `user_decision`
- Gate след RESOLVE_ASSETS: всеки RSS entry има resolution в {auto, inferred, user_decision, skip}

---

## WR-016 — prototypePrefixHint: ключ за tier-1 automation на non-symbol assets

**Открито:** 2026-03-17
**Контекст:** При prefix-only промяна (bh_ → df_), workflow-ът може да автоматично разреши ВСИЧКИ assets — символни и non-символни — само с два параметъра.

**Config полета:**
```json
"assets": {
  "mode": "new",
  "gamePrefix": "df",
  "prototypePrefixHint": "bh",
  "resourcesDir": "C:/..."
}
```

**Алгоритъм при наличие на prototypePrefixHint:**
1. Прочети всички RSS entries от прототипните манифести
2. За всеки entry: замести `{prototypePrefixHint}_` → `{gamePrefix}_` в RSS ключа и file path-а
3. Провери дали новият файл съществува в overlay директорията → ако да: `auto`; ако не: → tier 2

**Изисквания:**
- `prototypePrefixHint` е **optional** — ако липсва, tier-1 automation важи само за символните assets (WR-014)
- Ако е зададен, workflow-ът трябва да провери дали substitution-ът е consistent (да не замества неволно в несвързани контексти)
- Ако overlay файлът не се намери след prefix замяна → escalate to tier 2

---

## WR-017 — assetResolutions[]: config като decision log

**Открито:** 2026-03-17
**Контекст:** Решенията взети по RESOLVE_ASSETS се записват в config-а. Цел: (1) документация какво е направено и защо; (2) reuse при следващ clone на подобна игра — вече взетите решения не се питат отново.

**Структура на запис:**
```json
{
  "rssKey":     "BH_BACKGROUND_MAIN",
  "rssFile":    "RssImagesData.json",
  "resolution": "auto",
  "method":     "prefix_replace",
  "newKey":     "DF_BACKGROUND_MAIN",
  "newPath":    "p/bg/df_bg_main.dds",
  "note":       "..."
}
```

**Resolution типове:**

| Тип | Кога | note поле |
|-----|------|-----------|
| `auto` | Tier 1 — детерминистично | не |
| `inferred` | Tier 2 — LLM предложи, потребителят потвърди | опционално |
| `user_decision` | Tier 3 — потребителят избра явно | задължително |
| `skip` | Entry не е нужен в новата игра | задължително (причина) |

**Изисквания:**
- `assetResolutions[]` се записва в config-а като резултат от RESOLVE_ASSETS
- При следващо изпълнение: ако config-ът вече съдържа `assetResolutions[]`, workflow-ът ги прилага директно — не преминава отново tier 1-3 за вече решените
- `note` при `user_decision` позволява на бъдеща сесия да разбере защо е взето решението

---

## WR-018 — RESOLVE_ASSETS: пълен алгоритъм

**Открито:** 2026-03-17
**Контекст:** Детайлен алгоритъм на стъпката. Вижте WR-015, WR-016, WR-017 за принципите.

**Входни данни:**
- `config.prototype` → path до прототипа в games root
- `config.assets.gamePrefix` → prefix на новата игра
- `config.assets.prototypePrefixHint` → prefix на прототипа (optional)
- `config.assets.resourcesDir` → overlay директория с нови файлове
- `config.assets.assetResolutions[]` → вече взети решения от предишно изпълнение (ако има)

**Алгоритъм:**
```
1. LOAD PROTOTYPE MANIFESTS
   Прочети: RssImagesData.json, RssImagesSeqData.json, RssSoundsData.json
   Резултат: списък от { rssKey, filePath, manifestFile } за всеки entry

2. LOAD OVERLAY INVENTORY
   Изброй всички файлове в resourcesDir рекурсивно
   Резултат: set от relative paths

3. APPLY EXISTING RESOLUTIONS (ако config съдържа assetResolutions[])
   Маркирай като "resolved" — не ги обработвай отново

4. TIER 1 — AUTO RESOLVE
   За всеки нерешен entry:
     a. Ако prototypePrefixHint е зададен:
          newKey  = rssKey.replace("{hint}_", "{prefix}_")
          newPath = filePath.replace("{hint}_", "{prefix}_")
          Ако newPath ∈ overlayInventory → resolved: auto, method: prefix_replace
     b. Символни assets — pattern от WR-014:
          Генерирай очакван path от gamePrefix + symbolName
          Ако съществува в overlayInventory → resolved: auto, method: symbol_pattern

5. TIER 2 — LLM INFER
   За всеки нерешен entry след tier 1:
     LLM анализира rssKey, filePath, overlayInventory
     LLM търси fuzzy match (подобни имена, семантично съответствие)
     Ако LLM е уверен:
       Показва предложение с обяснение → изчаква потвърждение
       resolved: inferred (или user_decision ако потребителят промени)

6. TIER 3 — HUMAN
   За всеки нерешен entry след tier 2:
     LLM задава конкретен въпрос:
       "RSS entry '{rssKey}' ({filePath}) няма съответствие.
        Избери: [a] Посочи файл от overlay  [b] Skip — не е нужен
                [c] Reuse от прототипа без промяна  [d] Въведи ръчно"
     Записва: resolution: user_decision, note: ...

7. WRITE RESOLUTIONS
   Запиши всички решения в config.assets.assetResolutions[]
   (записва се обратно в config файла — потребителят може да го провери/редактира)

8. APPLY RESOLUTIONS
   Генерирай новите RSS манифести (Rss*Data.json) с новите ключове и пътища
   Копирай файловете от overlay → resources/{newGame}/
```

**Gates:**
- Gate 1: Всеки RSS entry от прототипа е в {auto, inferred, user_decision, skip} — нито един нерешен
- Gate 2: Всеки entry с resolution ≠ skip и ≠ "reuse" → файлът съществува в overlay директорията

---

## Отворени въпроси (за бъдещ research)

- [ ] `ModuleManager_Astro.json`, `ModuleManager_Playground.json`, `ModuleManager_Inspired.json` — идентични ли са за всички игри или game-specific? Ако са идентични → copy без промяна
- [ ] Как точно se регистрира integration app в integration-level CMakeLists.txt? Нужна ли е промяна там или е само per-game CMakeLists.txt?
- [ ] `egt_add_resources()` CMake macro — как се конфигурира резолюцията и езиците? Те ли трябва да се вземат от config или се копират от прототипа?
- [ ] Съществуват ли допълнителни registration файлове извън CMakeLists.txt (напр. game registry JSON, plugin manifest)?
