# TODO: Game Creator

---

## Фаза 1 & 2 ✅ — Research + Config UI
Завършени. Виж `progress.md` за детайли.

---

## Фаза 3: Workflow (следваща)

### Преди да започнеш workflow имплементацията — провери:
- [ ] `configs/{game}/modules/ModuleManager_*.json` — идентични ли са за всички игри или game-specific? (`C:/mklinks/games/configs/`)
- [ ] Integration app `.cpp` template — колко boilerplate е общ между игрите? (`C:/mklinks/games/integration/astro/apps/src/Egt/`)
- [ ] Как точно се регистрира integration app в integration-level CMakeLists.txt? Нужна ли е промяна там?

### Workflow стъпки за имплементация:
- [ ] **VALIDATE_CONFIG** — schema check, name conflict, prototype exists, math file paths (WR-001, WR-011, WR-012, WR-013)
- [ ] **CREATE_GAME_MODULE** — copy plugins/{prototype}/ → {newGame}/; search-replace всички naming форми (WR-006)
- [ ] **CREATE_CONFIGS** — copy configs/{prototype}/ → {newGame}/; rename JSON файлове (WR-009)
- [ ] **CREATE_RESOURCES** — copy resources/{prototype}/ → {newGame}/; валидация symbol count (WR-004, WR-012)
- [ ] **RESOLVE_ASSETS** — 3-tier: auto (prefix replace) → inferred (LLM fuzzy) → human (пита + записва) (WR-015..018)
- [ ] **CREATE_INTEGRATIONS** — за всеки integration: copy + search-replace app файловете (WR-008)
- [ ] **UPDATE_CMAKE** — добави snakeName в EGT_BUILD_GAME_LIST (WR-005)

### Инфраструктура:
- [ ] `workflow.yaml` структура (виж agentic-control-plane docs за формата)
- [ ] Struct schemas за inputs/outputs на всяка стъпка
- [ ] Добави workflow copy в `install.py`

---

## Decisions (взети)

- [x] Собствен `install.py` за game-creator (не разширение на agentic-control-plane)
- [x] Инсталира в `<target>/.agent/tools/`; workflow в `<target>/.agent/workflows/game-creator/`
- [x] UI v2: math файлът е централният вход (Стъпка 3)
- [x] Символни имена са само labels — game logic работи по numeric ID → idata/ не се променя при "Reuse"
- [x] Figure mapping е заменено с per-symbol resource table + 3-tier RESOLVE_ASSETS
- [x] `prototypePrefixHint` + `gamePrefix` = ключ за tier-1 auto-resolution на non-symbol assets
- [x] Config-ът натрупва `assetResolutions[]` — decision log за reuse при следващ clone
- [x] italy_games ресурси са несъвместими с overlay — извън scope v1
- [x] Без rollback в v1 (WR-010)
