# Game Creator — Design Spec

**Version:** 0.2
**Date:** 2026-03-17
**Status:** In progress — UI built, workflow pending

---

## Overview

**game-creator** is a two-part tool for cloning Alpha Family VLT games in the `games` project:

1. **Config UI** (`game-creator.html`) — a browser-based wizard that collects parameters and exports a `game-creator-config.json`
2. **Workflow** (`workflow.yaml`) — an agentic-control-plane workflow that reads the config and performs all filesystem operations

The tool is standalone — it has its own `install.py` and installs into the same `.agent/` directory as the agentic-control-plane.

---

## Installation

```
dist/
├── install.py                        ← copies tool into target project
└── .agent/
    ├── tools/
    │   └── game-creator.html         ← config wizard UI
    └── workflows/
        └── game-creator/             ← workflow (not yet implemented)
            └── workflow.yaml
```

**Install command:**
```bash
python install.py <target>            # skip existing
python install.py <target> --update   # overwrite changed files
python install.py <target> --force    # overwrite all
python install.py <target> --dry-run  # preview only
```

After install, game-creator.html is accessible via `.agent/tools/game-creator.html`.

---

## UI Wizard Flow (v2 — math file as central input)

```
Step 1: Prototype      — choose source game
Step 2: New Name       — snake_case, derives PascalCase etc.
Step 3: Math File      — REQUIRED: user supplies var_*.json for the new game
                         UI reads symbolsData.symbolNames → shows symbol count
                         UI reads wildId, scatterIds → shows summary
Step 4: Settings       — games root path, integrations (astro/playground/inspired)
Step 5: Assets Mode    — two options:
         A) "Reuse prototype assets"  → no mapping, idata/ copied 1:1 (works by numeric ID)
         B) "Supply new assets"       → overlay dir + optional RSS key mapping for idata/
Step 6: Export         — JSON config preview + download
```

---

## Config Schema

The UI exports a JSON file with this structure:

```json
{
  "version": 1,
  "prototype": "burning_hot_coins",
  "newGame": {
    "snakeName": "dragon_fortune",
    "pascalName": "DragonFortune",
    "displayName": "Dragon Fortune"
  },
  "paths": {
    "gamesRoot": "C:/mklinks/games",
    "resourcesDir": null
  },
  "integrations": ["astro", "playground", "inspired"],
  "figureMapping": [
    { "from": "CHERRY", "to": "DRAGON" },
    { "from": "SEVEN",  "to": "COIN" }
  ],
  "math": {
    "variants": [
      { "id": "var_8407", "rtp": 0.8407, "file": "math/var_8407.json" }
    ]
  }
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `prototype` | yes | snake_case name of the source game |
| `newGame.snakeName` | yes | snake_case for dirs and cmake |
| `newGame.pascalName` | yes | PascalCase for C++ classes |
| `newGame.displayName` | yes | Human-readable name |
| `paths.gamesRoot` | yes | Absolute path to games repo root |
| `paths.resourcesDir` | no | External assets dir to overlay after copy (must match games resource structure) |
| `integrations` | yes | Which integration apps to generate |
| `figureMapping` | no | Symbol renames; null or empty = pure copy |
| `math.variants` | yes | At least one RTP variant |

---

## Naming Conventions

All names are derived from `snakeName`:

| Pattern | Example (input: `dragon_fortune`) |
|---------|----------------------------------|
| snake_case | `dragon_fortune` |
| PascalCase | `DragonFortune` |
| Library target | `EgtDragonFortuneFsmStatic` |
| Integration app dir | `AstroDragonFortune` |
| Executable target | `astrodragonfortune` |

---

## What the Workflow Must Do

### Files to CREATE (for game `dragon_fortune` from prototype `burning_hot_coins`)

**Game plugin** (~110 files, mostly copy+rename):
```
game/alpha_family/plugins/dragon_fortune/
├── CMakeLists.txt                          ← set(PLUGINS_SUBDIR dragon_fortune)
└── src/Egt/
    ├── DragonFortuneFsm/                   ← copy BurningHotCoinsFsm/ + rename
    ├── DragonFortuneMath/                  ← copy BurningHotCoinsMath/ + rename
    ├── DragonFortuneView/                  ← copy BurningHotCoinsView/ + rename
    └── DragonFortuneInfoView/              ← copy BurningHotCoinsInfoView/ + rename
```

**Config files** (~5 files, copy+rename):
```
configs/dragon_fortune/modules/
├── DragonFortuneModules.json
├── DragonFortuneDebugModules.json
├── ModuleManager_Astro.json
├── ModuleManager_Playground.json
└── ModuleManager_Inspired.json
```

**Resources** (copy prototype + optional overlay + apply figureMapping):
```
resources/dragon_fortune/                   ← copy resources/burning_hot_coins/ + apply mapping
```

**Integration apps** (per integration in config.integrations):
```
integration/astro/apps/src/Egt/AstroDragonFortune/
├── AstroDragonFortune.cpp                  ← generated from template
└── CMakeLists.txt                          ← generated from template
```

### Files to MODIFY

| File | Change |
|------|--------|
| `CMakeLists.txt` (root) | Add `dragon_fortune` to `EGT_BUILD_GAME_LIST` |

---

## Figure Mapping — What Gets Changed

When `figureMapping` is non-empty, the workflow modifies these files in `resources/dragon_fortune/`:

| File | How symbol names appear | Change |
|------|------------------------|--------|
| `math/var_*.json` | Array element: `"CHERRY"` | Replace value at that index |
| `idata/ReelsView.json` | Object field: `"name": "CHERRY"` | Replace name field |
| `idata/WinFiguresView.json` | RSS ID value: `"REEL_CHERRY_ANIM"` | Replace CHERRY part in string |
| `idata/LinesView.json` | Sound key value: `"WIN_FIGURE_CHERRY_SOUND"` | Replace CHERRY part in string |
| `RssImagesSeqData.json` | Animation `"id"` field | Replace CHERRY part in string |
| `RssSoundsData.json` | Sound `"id"` field | Replace CHERRY part in string |
| `RssImagesData.json` | Image paths: `bh_r_cherry.dds` | Replace filename (requires new asset) |

**NOT affected by figure mapping:**
- `v/` directory (view layouts use generic RSS keys, no symbol names)
- C++ source files (symbol names are only in JSON/resources)

**Important:** RSS IDs in `idata/` use the symbol name as a substring of a composite ID
(e.g., `REEL_CHERRY_ANIM`, `WIN_FIGURE_CHERRY_SOUND`). Only the symbol-name part changes —
the prefix (`REEL_`, `WIN_FIGURE_`) stays the same.

---

## Resource Overlay

If `paths.resourcesDir` is set, after copying prototype resources, the workflow overlays
files from that directory onto `resources/dragon_fortune/` by relative path.

**Requirement:** The overlay directory must already match the games resource structure
(`RssImagesData.json`, `AllRssData.json`, `p/`, `s/`, `v/`, etc.).

**italy_games resources are NOT compatible** — they use a different format and structure.
Using italy_games assets would require a separate conversion tool (out of scope for v1).

---

## Workflow Steps (Planned)

```
Step 1: VALIDATE_CONFIG
  Input: game-creator-config.json path
  Action: validate JSON schema, check prototype exists, check no name conflict
  Gate: structural (schema) + semantic (name uniqueness)

Step 2: CREATE_GAME_MODULE
  Input: config
  Action: copy game/alpha_family/plugins/{prototype}/ → {newGame}/
          search-and-replace all class names and CMake targets
  Gate: CMakeLists.txt syntax, C++ class declarations well-formed

Step 3: CREATE_CONFIGS
  Input: config
  Action: copy configs/{prototype}/ → configs/{newGame}/
          replace module names in JSON
  Gate: JSON valid, module names match

Step 4: CREATE_RESOURCES
  Input: config
  Action: copy resources/{prototype}/ → resources/{newGame}/
          apply figureMapping to affected files (see table above)
          apply overlay from resourcesDir if set
  Gate: AllRssData.json valid, symbolNames count matches

Step 5: CREATE_INTEGRATIONS
  Input: config
  Action: for each integration in config.integrations:
            generate {Integration}{GameName}.cpp from template
            generate CMakeLists.txt from template
  Gate: .cpp compiles (syntax check), cmake syntax valid

Step 6: UPDATE_CMAKE
  Input: config, gamesRoot
  Action: edit CMakeLists.txt — add newGame.snakeName to EGT_BUILD_GAME_LIST
  Gate: EGT_BUILD_GAME_LIST contains new entry

Step 7: BUILD (optional)
  Input: config, build dir
  Action: cmake configure + build
  Gate: build success
```

---

## Symbol System Architecture — Critical

### How symbols work (ID-based, not name-based)

**All game logic uses numeric IDs only. Symbol names are labels with no gameplay meaning.**

```
math/var_*.json
├── symbolNames: ["CHERRY", "LEMON", ...]   ← labels only, never used in calculations
├── wildId: 8                                ← numeric — used in win detection
├── scatterIds: [9, 10]                      ← numeric — used in bonus triggers
├── paytable                                 ← indexed by numeric symbol ID
└── reelStrips                               ← numeric IDs only (e.g. [0,0,1,1,2,...])

MathRules.cpp  → uses only numeric IDs; names loaded as metadata, never in calculations
idata/ReelsView.json      → rssId = "REEL_BH_1" (GENERIC, not name-based)
idata/WinFiguresView.json → "0": "REEL_CHERRY_ANIM"  (key = numeric ID)
idata/LinesView.json      → "0": "WIN_FIGURE_CHERRY_SOUND" (key = numeric ID)
```

### What the math file actually is

The math file is the **complete certified mathematical model** for the game:
- Reel strips, paytable, probabilities — all pre-calculated
- Cannot be auto-generated — requires a mathematician and regulatory certification

**The math file is a mandatory input to game-creator.** A new game must supply its own math file.

### When is "mapping" (RSS key renaming) needed?

Mapping is NOT about gameplay — the game works correctly by numeric ID regardless of names.
Mapping is only needed when supplying new animation/sound assets with different filenames.

| Scenario | Mapping needed? | Why |
|----------|----------------|-----|
| New math file, reuse prototype animations/sounds | **No** | idata/ keys are numeric; cherry animation plays for symbol 0 even if it's now called DRAGON |
| New math file + new assets (e.g. `reel_dragon_anim.dds`) | **Yes** | `WinFiguresView.json` must map `"0"` to `"REEL_DRAGON_ANIM"`, and `RssImagesSeqData.json` must define that entry |

**Mapping = RSS key renaming in idata/ files only. Never affects C++ or game logic.**

### Symbol count changes

If the new game has a different number of symbols than the prototype:

| File | Change required |
|------|----------------|
| `math/var_*.json` | New file (required anyway) |
| `idata/ReelsView.json` | symbolsConfig array length changes |
| `idata/WinFiguresView.json` | Add/remove numeric keys |
| `idata/LinesView.json` | Add/remove numeric keys |
| `RssImagesData.json` | Add/remove image entries |
| `RssImagesSeqData.json` | Add/remove animation entries |
| `RssSoundsData.json` | Add/remove sound entries |

C++ is NOT affected — it only uses the count from the math file at runtime.

---

## Known Limitations (v1)

1. **No rollback** — if workflow fails midway, partial changes remain; manual cleanup required
2. **No italy_games resource conversion** — overlay must already be in games resource format
3. **Known games list is hardcoded in UI** — future: scan `game/alpha_family/plugins/` via path config
4. **Figure mapping requires same symbol count** — different symbol count requires new math file (see above)
5. **Figure mapping is coarse** — renames by string substitution in RSS IDs; may need manual review
6. **No codegen for business logic** — FSM/Math/View implementations are copied from prototype unchanged; actual game logic must be modified manually after cloning

---

## Source Locations Reference

| Resource type | Path pattern |
|--------------|-------------|
| Game plugin | `{gamesRoot}/game/alpha_family/plugins/{game}/` |
| Config files | `{gamesRoot}/configs/{game}/modules/` |
| Resources | `{gamesRoot}/resources/{game}/` |
| Math JSON | `{gamesRoot}/resources/{game}/math/var_*.json` |
| Symbol names | `{gamesRoot}/resources/{game}/math/var_*.json` → `symbolsData.symbolNames` |
| idata files | `{gamesRoot}/resources/{game}/idata/` |
| View layouts | `{gamesRoot}/resources/{game}/v/{resolution}/` |
| Integration apps | `{gamesRoot}/integration/{integration}/apps/src/Egt/{Integration}{Game}/` |
| Root CMake | `{gamesRoot}/CMakeLists.txt` |
