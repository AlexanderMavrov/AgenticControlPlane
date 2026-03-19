# TODO: Game Creator

---

## Фаза 1, 2 & 3 ✅ — Research + Config UI + Workflow
Завършени. Виж `progress.md` за детайли.

---

## Фаза 4: Testing & Integration (следваща)

### Преди end-to-end тест:
- [x] Обнови `install.py` да копира workflow файловете (`workflow.yaml` + `structs/`) в `.agent/workflows/game-creator/`
- [ ] Обнови `dist/SPEC.md` да отразява финалната workflow структура (8 стъпки вместо 7)

### Open questions:
- [ ] `displayName` — config-ът го има, но нито един step не го използва. Трябва ли да се записва някъде? (playground manifest? UI label?)
- [ ] RESOLVE_ASSETS (3-tier) — отложен за v2. Текущият workflow поддържа само "reuse" и "overlay" mode чрез Step 5.
- [ ] Gate конфигурация за Step 8 (validate-and-build) — дали `human: true` е по-подходящо за последната стъпка?

### End-to-end тест:
- [ ] Генерирай `game-creator-config.json` чрез UI-а за test game (burning_hot_coins → test_dragon)
- [ ] Стартирай workflow-а в agentic-control-plane
- [ ] Провери всеки step report за грешки
- [ ] Верифицирай CMake configure + build успех

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
- [x] Workflow е 8 стъпки (не 7 от SPEC.md) — validate-and-build добавена като финална стъпка
- [x] 6 naming variants: oldPascal/pascalName, prototype/snakeName, oldLower/newLower, oldUpper/newUpper
- [x] Всички стъпки са generic (scan-based), не hardcoded за конкретна игра
- [x] Integration-level CMakeLists.txt НЕ се модифицира — auto-discovery чрез foreach+egt_pascal_case
- [x] Playground manifest id е споделено (2121) — не е уникално per game
- [x] ModuleManager_Playtech_Server.json има собствено копие на math setup config — Step 4 сканира всички файлове
- [x] Playtech има 3+ sub-components (Client, Server, Database, Bot) — Step 6 сканира всички
