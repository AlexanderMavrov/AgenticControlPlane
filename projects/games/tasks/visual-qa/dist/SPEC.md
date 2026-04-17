# Visual QA — Design Spec v0.1

**Дата:** 2026-04-16
**Статус:** Draft

---

## 1. Overview

Visual QA е standalone tool за визуално тестване на Alpha Family VLT игри. Работи за **всяка** игра — не изисква прототип или reference game за сравнение.

**Подход:** Хибрид — static analysis (primary) + LLM vision (secondary).

- **Static analysis** чете view JSON файловете и прилага ~50 правила (дефинирани в `rules.md`), проверявайки позиции, цветове, scale, symmetry, zone violations, RSS reference integrity и т.н.
- **LLM vision** анализира screenshots и потвърждава/допълва findings-ите.
- При намерени проблеми, tool-ът може да **предложи и приложи fixes** в JSON конфигурациите.

---

## 2. Input Config Schema

```json
{
  "version": 1,
  "gameName": "burning_hot_coins",
  "resourcesPath": "C:/Workspace/games/resources/burning_hot_coins",
  "resolution": "1920x1080",
  "screenWidth": 1920,
  "screenHeight": 1080,
  "screenshots": {
    "idle": "path/to/idle_screenshot.png",
    "reference": "path/to/reference_game_screenshot.png"
  },
  "options": {
    "autoFix": false,
    "severityThreshold": "low",
    "skipRules": [],
    "onlyRules": []
  }
}
```

| Поле | Тип | Задължително | Описание |
|------|-----|-------------|----------|
| `gameName` | string | Да | snake_case име на играта |
| `resourcesPath` | string | Да | Път до `resources/{game}/` директорията |
| `resolution` | string | Да | Resolution за проверка: `"1920x1080"` или `"1440x900"` |
| `screenWidth/Height` | int | Не | Defaults от resolution |
| `screenshots.idle` | string | Не | Screenshot на играта в idle state |
| `screenshots.reference` | string | Не | Screenshot от друга правилна игра (за layout reference) |
| `options.autoFix` | bool | Не | Auto-apply fixes без потвърждение (default: false) |
| `options.severityThreshold` | string | Не | Минимален severity за reporting: `critical/high/medium/low/info` |
| `options.skipRules` | string[] | Не | Правила за пропускане (напр. `["A1", "D1"]`) |
| `options.onlyRules` | string[] | Не | Проверявай САМО тези правила |

---

## 3. Workflow Architecture

```
                    ┌─────────────────────┐
                    │  visual-qa-config    │
                    │      .json           │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │  Step 1: GATHER      │
                    │  Read all resource   │
                    │  files, build model  │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │  Step 2: ANALYZE     │
                    │  Apply rules,        │
                    │  produce findings    │
                    └─────────┬───────────┘
                              │
                   ┌──────────┴──────────┐
                   │ screenshots          │
                   │ provided?            │
                   └──────┬─────┬────────┘
                     Yes  │     │  No
                   ┌──────▼──┐  │
                   │ Step 3:  │  │
                   │ VISUAL   │  │
                   │ VALIDATE │  │
                   └──────┬──┘  │
                          │     │
                   ┌──────▼─────▼────────┐
                   │  Step 4: FIX         │
                   │  Propose & apply     │
                   │  fixes               │
                   └──────────────────────┘
```

---

## 4. Workflow Steps

### Step 1: `gather-game-model`

**Goal:** Прочети всички resource файлове на играта и изгради пълен structured model.

**Reads:**
- `{resourcesPath}/v/{resolution}/RssElementsListData.json` → списък на всички view файлове
- Всички `v/{resolution}/*.json` view файлове (GameBackgroundView, KnobsView, CreditBarView, etc.)
- Всички `v/{resolution}/SwButtons/*.json`
- `{resourcesPath}/idata/{resolution}/ReelsView.json` → символи, reel grid
- `{resourcesPath}/idata/{resolution}/WinFiguresView.json` → win animations mapping
- `{resourcesPath}/idata/{resolution}/LinesView.json` → win lines config
- `{resourcesPath}/idata/{resolution}/StatusLineView.json` → status line config
- `{resourcesPath}/idata/{resolution}/GambleRoundView.json` → gamble config
- `{resourcesPath}/math/var_*.json` → symbol names, grid size, wild/scatter IDs
- `{resourcesPath}/AllRssData.json` → RSS manifest includes
- `{resourcesPath}/art/{resolution}/RssImagesData.json` → image RSS entries
- `{resourcesPath}/art/{resolution}/RssImagesSeqData.json` → animation RSS entries
- `{resourcesPath}/art/{resolution}/RssTextStylesData.json` → text style definitions
- `{resourcesPath}/s/RssAudioData.json` → sound RSS entries

**Output struct: `game-model-report`**
```yaml
gameName: string
resolution: string
screenWidth: int
screenHeight: int

views:
  # key = view filename (без .json)
  GameBackgroundView:
    elements: [...]       # raw parsed elements
    elementCount: int
  KnobsView:
    elements: [...]
  # ... etc for all views

idataReels:
  visibleCols: int
  visibleRows: int
  reelAreaX: int
  reelAreaY: int
  reelStepX: int
  reelStepY: int
  symbolCount: int
  symbols: [{id, rssId, name, hue}]

idataLines:
  lineCount: int
  reelArea: {x, y, stepX, stepY}

idataWinFigures:
  reelArea: {x, y, stepX, stepY}
  figureKeys: {id: rssKey}

math:
  reelsCount: int
  rowsCount: int
  symbolNames: [string]
  wildId: int
  scatterIds: [int]

rssRegistry:
  images: [string]        # list of all image RSS IDs
  animations: [string]    # list of all animation RSS IDs
  sounds: [string]        # list of all sound RSS IDs
  styles: [string]        # list of all style IDs

fileInventory:
  viewFiles: [string]     # paths to all view JSONs read
  idataFiles: [string]
  mathFile: string
  rssManifests: [string]

errors: [string]          # any files that couldn't be read
```

**Behavioral Rules:**
1. ATTEMPT FIRST — прочети всички файлове системно
2. ASK ON AMBIGUITY — ако math файлът не е намерен (multiple var_*.json), питай кой да ползва
3. ONLY SPECIFIED CHANGES — read-only step, не модифицирай нищо
4. RECORD DECISIONS — запиши ако е трябвало да избереш между файлове

---

### Step 2: `static-analysis`

**Goal:** Приложи всички правила от rules.md върху модела от Step 1. Генерирай findings report.

**Input:** game-model-report от Step 1, rules.md, config

**Rule application order:**
1. **N-series (Cross-cutting):** RSS key exists (N1), style exists (N2), unique IDs (N3), type properties (N4), resolution (N5)
2. **I-series (Reel Grid):** Symbol count (I1), sequential IDs (I2), rssId exists (I3), dimensions (I4), cross-file consistency (I5), fits screen (I6)
3. **A-series (Background):** Alpha (A1), tint (A2), panel gap (A3), width (A4), 18+ position (A5)
4. **B-series (Knobs):** Symmetry (B1), same rssKey (B2), zone (B3)
5. **C-series (Credit):** Color (C1), scale (C2), min/max consistency (C3), position (C4)
6. **D-series (Coins):** Pure white (D1), consistency (D2), ordering (D3)
7. **E-series (Bet):** Structure (E1), alignment (E2), button symmetry (E3)
8. **F-series (Win):** Style (F1), position (F2), multi-state (F3)
9. **G-series (Status):** Group consistency (G1), zone (G2), sides (G3), idata match (G4)
10. **H-series (Buttons):** 3 rssKeys (H1), co-location (H2), zone (H3), distribution (H4), overlap (H5)
11. **J-series (Win Figures/Lines):** Keys (J1-J6)
12. **K-series (Gamble):** Cards (K1), history (K2), symmetry (K3), overlay (K4)
13. **L-series (Wheel):** Center (L1), text (L2), panel (L3)
14. **M-series (Menus):** Spacing (M1), alignment (M2), button symmetry (M3)
15. **O-series (Touch):** Spacing (O1), bounds (O2)

**Output struct: `analysis-report`**
```yaml
totalRulesChecked: int
totalFindings: int
findingsBySeverity:
  critical: int
  high: int
  medium: int
  low: int
  info: int

findings:
  - id: "F001"
    ruleId: "C1"
    ruleName: "Credit text — no green color"
    category: "convention"        # integrity | consistency | convention
    reportLevel: "warning"        # error (integrity/consistency) | warning (convention)
    severity: critical
    file: "v/1920x1080/CreditBarView.json"
    element: "text_amount_max"
    property: "color"
    actualValue: "{r:0, g:255, b:0, a:255}"
    expectedValue: "{r:255, g:255, b:255, a:255}"
    description: "Credit text amount_max is green instead of white"
    suggestedFix:
      file: "v/1920x1080/CreditBarView.json"
      path: "elements[2].color"
      newValue: "{r:255, g:255, b:255, a:255}"

  - id: "F002"
    ruleId: "B1"
    category: "consistency"
    reportLevel: "error"
    severity: high
    # ... etc

rulesSkipped: [string]    # rules not applicable (e.g. no gamble round)
rulesPassed: [string]     # rules that passed cleanly
```

**Behavioral Rules:**
1. ATTEMPT FIRST — приложи всички правила системно
2. ASK ON AMBIGUITY — ако правило е неприложимо (напр. няма gamble round), skip-ни го
3. ONLY SPECIFIED CHANGES — analysis only, не модифицирай файлове
4. RECORD DECISIONS — запиши ако е skip-нал правило и защо

---

### Step 3: `visual-validation` (conditional)

**Goal:** Използвай LLM vision за потвърждение на static findings + допълнително detection.

**Condition:** Изпълнява се САМО ако `config.screenshots` е предоставен.

**Input:** analysis-report от Step 2, screenshot файлове, game-model-report от Step 1

**Process:**
1. Прочети screenshot(s) с vision
2. Ако reference screenshot е наличен → анализирай layout структурата (reel grid, panel, buttons)
3. За всеки finding от Step 2 с severity >= medium:
   - Опитай да потвърдиш визуално: "Виждам ли този проблем на screenshot-а?"
   - Маркирай като `confirmed` или `unconfirmed`
4. Сканирай за допълнителни проблеми, невидими за static analysis:
   - Грешни/липсващи image файлове (image exists но показва wrong content)
   - Visual artifacts
   - Елементи, скрити зад други елементи (z-order issues)

**Output struct: `visual-report`**
```yaml
screenshotsAnalyzed: int
findingsConfirmed: [string]      # finding IDs потвърдени визуално
findingsUnconfirmed: [string]    # finding IDs, които не можаха да се потвърдят
additionalFindings:
  - id: "VF001"
    description: string
    severity: string
    location: string             # описание на зоната на екрана
    possibleCause: string

visionLimitations: [string]      # неща, които vision не можа да провери
```

**Behavioral Rules:**
1. ATTEMPT FIRST — анализирай screenshot-ите внимателно
2. ASK ON AMBIGUITY — ако screenshot-ът е неясен или с ниска резолюция, отбележи в limitations
3. ONLY VALIDATE — не предлагай fixes в тази стъпка, само потвърждавай/допълвай findings
4. RECORD DECISIONS — запиши confidence level за всяко потвърждение

---

### Step 4: `fix-issues`

**Goal:** Предложи и (при autoFix) приложи fixes за потвърдени findings.

**Input:** analysis-report от Step 2, visual-report от Step 3 (ако е наличен), config

**Process:**
1. Приоритизирай findings по severity (critical → high → medium → low)
2. За всеки finding:
   - Определи точния файл и JSON path за промяна
   - Определи правилната стойност (от rules.md reference values)
   - Ако `autoFix: true` → приложи промяната
   - Ако `autoFix: false` → предложи промяната и чакай потвърждение
3. Генерирай summary report

**Output struct: `fix-report`**
```yaml
totalFixesProposed: int
totalFixesApplied: int
totalFixesSkipped: int

fixes:
  - findingId: "F001"
    ruleId: "C1"
    file: "v/1920x1080/CreditBarView.json"
    change:
      path: "elements[2].color"
      oldValue: "{r:0, g:255, b:0, a:255}"
      newValue: "{r:255, g:255, b:255, a:255}"
    status: "applied" | "proposed" | "skipped" | "user_approved"
    reason: string

decisions: [...]
```

**Behavioral Rules:**
1. ATTEMPT FIRST — предложи fix на база правилата
2. ASK ON AMBIGUITY — при неясна "правилна" стойност, предложи варианти и питай потребителя
3. ONLY SPECIFIED CHANGES — модифицирай САМО файловете, посочени във findings. Не "подобрявай" нищо друго.
4. RECORD DECISIONS — запиши всяко взето решение, особено user approvals

---

## 5. File Structure (след инсталация)

```
.agent/workflows/visual-qa/
├── workflow.yaml
└── structs/
    ├── game-model-report.schema.yaml
    ├── analysis-report.schema.yaml
    ├── visual-report.schema.yaml
    └── fix-report.schema.yaml

.agent/tools/
└── visual-qa.html          # Input collector (Phase 2)

.agent/docs/
└── visual-qa-rules.md      # Rules reference за LLM
```

---

## 6. Workflow YAML Structure (preview)

```yaml
name: visual-qa
version: "0.1"
description: "Visual QA tool for Alpha Family VLT games"
tags: [qa, visual, validation]

params:
  config:
    type: file
    description: "Path to visual-qa-config.json"

inject:
  - file: ${config}
    as: CONFIG

context:
  - file: .agent/docs/visual-qa-rules.md
    as: RULES

steps:
  - id: gather-game-model
    agent: workflow-step
    spec_check: false
    goal: |
      Read all resource files for game "${CONFIG.gameName}" at "${CONFIG.resourcesPath}".
      Build a complete structured model of the game's visual elements.
      Resolution: ${CONFIG.resolution}
      ... (detailed instructions)
    struct: game-model-report

  - id: static-analysis
    agent: workflow-step
    spec_check: false
    goal: |
      Apply ALL rules from RULES against the game model from previous step.
      Check every view file, every element, every property.
      ... (detailed instructions referencing rules.md)
    struct: analysis-report

  - id: visual-validation
    agent: workflow-step
    spec_check: false
    condition: CONFIG.screenshots != null
    goal: |
      Analyze screenshots and validate findings from static analysis.
      ... (detailed instructions)
    struct: visual-report

  - id: fix-issues
    agent: workflow-step
    spec_check: false
    gate:
      human: true
    goal: |
      Propose and apply fixes for confirmed findings.
      AutoFix mode: ${CONFIG.options.autoFix}
      ... (detailed instructions)
    struct: fix-report
```

---

## 7. HTML Input Collector (Phase 2)

Standalone HTML tool за генериране на `visual-qa-config.json`.

**Стъпки:**
1. **Game Selection** — path до resources директория, game name auto-detect
2. **Resolution** — избор на resolution (scan наличните в `v/`)
3. **Screenshots** — optional file upload / path input за idle + reference screenshots
4. **Options** — severity threshold, autoFix toggle, skip/only rules
5. **Export** — JSON preview, download, clipboard

Следва същия pattern като `game-creator.html`.

---

## 8. Бъдещи разширения (v2+)

- **Multi-game batch mode** — пусни visual QA за всички игри наведнъж
- **Rule learning** — автоматично извличане на правила от N reference игри
- **Screenshot auto-capture** — интеграция с playground за автоматични screenshots
- **Historical tracking** — запазване на findings между runs за regression detection
- **Custom rules** — потребителят може да добави собствени правила в config
- **Clone-check mode** — допълнителен diff с прототип (config.prototype field)
