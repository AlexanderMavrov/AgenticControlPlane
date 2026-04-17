# 05 — Changelog

Хронология на архитектурните решения и промени, групирани по фази.

---

## Phase 1: Core Design (2026-03-12)

- Pre-extracted specs подход; Skill-based workflow с LLM state machine
- 4 фази: PLAN → EXTRACT → VALIDATE → COMMIT
- Fan-out/fan-in subagent модел; `subagentStop` за continuation
- Хибриден 3-слоен gate: structural + semantic + human
- Clean context per phase + summary carry-forward
- Унифициран Workflow Engine вместо ad-hoc решение
- `.agent/` (data) + `.cursor/` (adapter) split
- Full struct validation за inputs и outputs
- Auto-generated manifest; потребителят не го пише

## Phase 2: Initial Implementation (2026-03-13)

- `dist/` + `install.py` за лесна интеграция
- `.agent/docs/` — LLM-consumable documentation (English)
- Gate scripts → Python (вместо Bash)
- Explicit: steps са sequential, parallel е само вътре в стъпка
- `/learn-workflows` skill за LLM onboarding
- `params:` — потребителски аргументи при стартиране
- Natural language branching — LLM е evaluator
- `.agent/specs/` — shared output location

## Phase 3: Spec Guard (2026-03-13)

- **Spec Guard** дизайн: behavioral specs в `.agent/specs/`, always-active rule
- Trigger chain: **Rule → LLM → Skill → Workflow** (LLM е "glue")
- `[specs::ComponentName]` capture syntax в чата
- CLARIFY стъпка: задължителна, интерактивна, `gate.human: true`
- `_registry.json` — implementation mapping (files → specs)
- `delegate_to:` — workflow delegation/composition
- Hybrid enforcement: always-active rule (soft) + workflow (hard)
- Predefined workflows: `spec-write-and-implement`, `spec-enforcement`, `create-workflow`, `registry-sync`

## Phase 4: Retry & Registry v2 (2026-03-14)

- `max_gate_retries` + `max_step_retries` — dual retry mechanism
- `gate-result.json` bridge между hook и orchestrator
- `_registry.json` v2: `implemented_by` → `object[]` с `relationship` type
- Transitive dependency tracking: `imports`, `imported_by`, `style`, `config`, `test`
- `spec-enforcement` v2: `component` optional, auto-discovery mode
- `spec_check` per-step field (default: `true`)
- `/code-with-spec` skill: wrapper around `spec-enforcement` workflow

## Phase 5: Trace System (2026-03-14)

- Execution traces в `trace/<run-id>.trace.json`
- `gate-check.py` capture — invocations, durations, gate results
- Browser-based Trace Viewer (`.agent/tools/trace-viewer.html`)
- `.agent/tools/` — нова директория за human-facing utilities
- `install.py` v2: 8 стъпки (добавен `.agent/tools/`)

## Phase 6: Audits & Bugfixes (2026-03-14 — 2026-03-15)

- Пълен аудит P-001 до P-017: param_bindings, file locking, schema fixes
- Втори аудит N-001 до N-005: Windows locking fix, affected_files rename
- `doc-spec-extraction` predefined workflow (universal, generic params)
- `spec-audit` predefined workflow: DISCOVER → SCAN(parallel) → REPORT

## Phase 7: End-to-End Testing (2026-03-15 — 2026-03-16)

- **BOM fix**: Windows Cursor prepends UTF-8 BOM на hook stdin
- `sys.stdin.buffer.read()` вместо `sys.stdin.read()` — root cause fix
- `hook-diagnostic` mini workflow за бърз hook тест
- Engine File Protection: explicit READ-ONLY path list
- 3 end-to-end runs на doc-spec-extraction в Cursor

## Phase 8: Subagent Isolation (2026-03-17)

- **КРИТИЧНО: followup_message семантика** — `followup_message` продължава СЪЩИЯ subagent, `{}` го спира
- Gate PASS → `{}` (subagent спира), Gate FAIL → followup (retry)
- Prolog/epilog logging: `gate-check-invocations.log`
- Trace NameError fix: `_build_trace_modifier()` parameter bug
- `hook-diagnostic` v2: 3 стъпки (probe-hook, probe-struct, probe-retry)
- `cursor-hook-reference.md` — пълен payload анализ (21 полета)

## Phase 9: Schema & Path Fixes (2026-03-17)

- `schema-validate.py`: Standard JSON Schema support (auto-detect)
- `gate-check.py`: `resolve_output_path` bug fix (glob от CWD)
- Phantom invocation filter (orchestrator parasitic invocations)
- Cursor hook payload — пълен анализ (v2.6.19): 21 полета потвърдени
- Adapter separation: trace leak — Cursor-specific полета в `.agent/`

## Phase 10: UI & Spec Skill (2026-03-19)

### Workflow Editor UI
- Compact params: single-row layout
- Gate defaults: clickable chip toggles + inline retries
- Step gate overrides: inline с config chips + Clear overrides
- Help система: rich modal dialogs с SVG flowcharts
- Example бутон: зарежда демо workflow

### /spec Skill Architecture
- `/spec audit` делегира към `spec-audit` workflow (преди: inline)
- "Upgrade path" hints: `/spec add` → suggests workflow, `/spec check` → suggests audit
- `[specs::X]` и `[spec]` patterns → тригерват workflow (преди: inline skill)

### Stronger Borders
- Light-mode borders: `#e2e6ec` → `#c2c9d6` в trace viewer + workflow editor

### User Documentation
- Нова `user_docs/` директория с 5 структурирани документа
- Trigger decision tree диаграми за spec guard
- Reliability анализ на enforcement chains

## Phase 11: MCP Server (2026-03-20)

- MCP server (`workflow-engine.py`): 7 tools за workflow orchestration
- SKILL.md пренаписан: 458 → 172 реда (MCP-based orchestration)
- Manual Fallback (F1-F7) за когато MCP tools не са налични
- `install.py` v3: 10 стъпки, `merge_mcp_config()`
- MCP/Manual no-mix rule: "Choose ONE path, NEVER mix"
- Delegation `subagent: false` fix: Cursor spawn-ва слаб модел без него
- Real timestamps изискване (не placeholder стойности)

## Phase 12: Performance & Inline Execution (2026-03-21)

### Inline Execution (`subagent: false`)
- `subagent: false` за всички стъпки в `spec-write` и `spec-enforcement`
- MCP `step_begin` връща `subagent` поле; SKILL.md обработва inline
- Inter-step gaps: 27-61s → 3-4s; общо ~18% подобрение
- Trade-off: без gate hook → без structural validation за inline стъпки

### MCP Server Hardening (11 fixes)
- Atomic writes (`_safe_write_json()` — temp + replace с fallback)
- Cache mtime check (workflow.yaml промени без server restart)
- `run_id` collision protection (4-char hex suffix)
- `step_begin` merge vs overwrite; `param_bindings` error safety
- `step_complete` duration_ms; CWD absolute paths; graceful error handling

### Manual Fallback F7 Trace Fix
- CRITICAL blockquote: preserve hook invocations, add only MISSING step entries
- Потвърдено: hook-diagnostic subagent invocations запазени

### Fast Skills (нови lightweight алтернативи)
- `/spec-fast` — spec + implement inline (~1-2 мин вместо 7-10)
- `/code-spec-fast` — code с spec enforcement inline
- `/spec-add-fast` — spec създаване без implement inline
- `/code-with-spec` преименуван на `/run-workflow-for-code-spec`
- Старата система (workflows, MCP, gates) остава непроменена

## Phase 13: Mandatory Confirmation for Fast Skills (2026-03-23)

- **Задължителен CONFIRM checkpoint** в `/spec-fast` и `/spec-add-fast` (Phase 1.5)
- Преди записване на spec, LLM-ът **винаги** показва: интерпретирани requirements, свързани/конфликтни specs, засегнати файлове от registry, дали поведението вече е имплементирано
- Потребителят одобрява, коригира, или отказва преди да продължи
- `/code-spec-fast` без промяна — не интерпретира нови requirements, работи с вече записани specs
- Мотивация: LLM интерпретацията на free-text requirements е ненадеждна; цената на грешен spec + грешен код е много по-висока от 1 confirmation turn

## Phase 14: doc-spec-extraction Quality Protection (2026-04-01)

### Validation Criteria Semantic Alignment
- EXTRACT: Validation Criteria трябва да е семантично подравнен с Rule Statement и Rationale — не pattern search
- Ако правило забранява X "for purpose Y", criteria проверява дали harm-ът може реално да се случи — unreachable/dead код не е violation
- Self-check инструкция: ако criterion е "search for X" — агентът проверява дали намирането е достатъчно или трябва verify (reachable, functional, can trigger harm) + exclude
- Адресира EXCD-001 false positive: `exit()` след `[[noreturn]]` `ak2api_exit()` погрешно маркиран от spec-audit

### spec_mapping — Structural Change Tracking
- ANALYZE генерира `spec_mapping` в analysis report: за ВСЕКИ existing spec, кой proposed spec го покрива
- Mapping работи дори при domain rename, spec split/merge, различен spec_id
- Existing specs без proposed еквивалент → mapped to null с причина
- Schema update: `analysis-report.schema.yaml` + `validation-report.schema.yaml`

### Universal Regression Protection
- VALIDATE regression check сега важи за ВСИЧКИ drafts (merge AND rewrite), не само merge
- Ползва spec_mapping за сравнение на правилните двойки
- Нов validation status `coverage_gap` за orphaned existing specs
- COMMIT не изтрива existing spec при coverage_gap, не презаписва при regression

### workflow-editor.html — Quotes Fix
- `esc()` escape-ва `"` (`&quot;`) и `'` (`&#39;`) в HTML attribute values
- Поправя отрязване на текст при кавички в YAML полета

## Phase 15: Regression Protection & Severity Gate (2026-04-02)

### Severity Body Match (structural gate)
- Нова generic schema feature `body_match_section` в `schema-validate.py`
- `extract_section_content()` helper: извлича текст под конкретен `##` heading от markdown body
- `spec.schema.yaml`: severity field добавя `body_match_section: "Rule Statement"` — structural gate проверява case-insensitive, че severity keyword присъства в Rule Statement body
- Хваща POWC-001/POWC-003 "SHALL" bug и EXCD-005/EXCD-006 severity mismatch детерминистично

### VALIDATE Enhanced Checks
- **Traceability (#4)**: сравнява `related_specs` на draft-а с `cross_domain_dependencies` от analysis report-а
- **Testability (#5)**: при existing predecessor (чрез spec_mapping), сравнява Validation Criteria — флагва загубени exclusions и boundary guidance
- Без нови check-ове: по 1 изречение добавено към existing checks #4 и #5

### spec_mapping Completeness
- ANALYZE инструкция усилена: spec_mapping трябва да има entry за ВСЕКИ файл в `.agent/specs/`, включително specs в домейни различни от proposed структурата
- Гарантира пълно покритие при domain restructuring

### Run 3 Analysis (no-script + CRITICAL)
- VALIDATE изпълни 6 semantic checks без скриптове (Run 2 писа Python script)
- COMMIT следва validation report без override (Run 1 го третираше като "stale")
- 93.22% quality (55/59 valid); 4 issues = реални source contradictions (§3.3.1 vs §3.6)
- What/Where/Exclude структура: 3 → 19 specs (+533%); празни related_specs: 16 → 7 (-56%)
- 3 minor regressions (FLOW-002, POWC-004, POWC-005 загубиха структура) → адресирани с testability enhancement

## Phase 16: Claude Code Adapter & Engine Hardening (2026-04-03)

### Inline Schema Injection
- `step_begin` чете struct schema файловете и ги embed-ва директно в `outputs_text` (вместо "read this file yourself")
- Форматът (JSON/YAML/Markdown) се извежда от файловото разширение
- `output_schemas` — нов structured field в response-а
- `AGENT.md` подсилен: "Follow struct schemas exactly, do NOT write plain text"
- **Резултат:** hook-diagnostic probe-struct мина от първия опит (преди loop-ваше с .txt файл)

### step_complete Inline Validation
- За `subagent: false` стъпки, `step_complete` валидира outputs преди да маркира стъпката
- При fail → `action: "FIX_AND_RETRY"` + `validation_errors` — orchestrator-ът retry-ва tool call-а
- Гарантира structural validation за всички стъпки, не само subagent ones

### Gitignore Discovery Fix
- **Проблем:** `.agent/` е gitignored → IDE Glob/Grep не намират файлове в нея → orchestrator казва "No existing specs" въпреки 59 spec файла
- **Три слоя на fix:**
  1. `step_begin` resolve-ва glob patterns в Python (`glob.glob()` не зачита gitignore) → workflow inputs се expand-ват коректно
  2. `list_agent_files` — нов MCP tool за file discovery в `.agent/` (Python `os.walk`, bypasses gitignore)
  3. Bash fallback за случаи без MCP: `python -c "import glob; ..."`
- Обновени инструкции в run-workflow SKILL.md (Cursor + Claude Code) и spec-guard rules: "NEVER use Glob/Grep inside .agent/"

### hook-diagnostic End-to-End (Claude Code)
- 3/3 стъпки PASS: probe-hook, probe-struct (7 checks, first-try), probe-retry (8 checks, gate feedback loop verified)
- Claude Code adapter е напълно функционален

### Нови правила
- **All-adapters rule:** промени задължително за всички интеграции
- **Test tracking rule:** всяка промяна → запис в `07-test-plan.md`

### Нов документ
- `user_docs/07-test-plan.md` — test plan с DONE/MANUAL/PENDING статус за всеки компонент

---

## Phase 17: Workflow Tools & Engine-Driven AGENT.md Injection (2026-04-05 — 2026-04-06)

### Workflow-level tools (`tools:` секция)
- `workflow.yaml` поддържа `tools:` секция на workflow ниво с два типа: `type: script` (engine wrap-ва като MCP proxy) и `type: mcp` (dependency на external MCP сървър)
- Engine-ът при `workflow_init` генерира `_workflow_tools_<name>.py` — temporary MCP server, експозиращ всички script tools като native MCP tools с schema validation
- Tool server логва всяко извикване в `.agent/workflows/<name>/tool-calls.json` → merge в trace при `workflow_finalize`
- `required` field на tool → блокира workflow ако липсва (с message към user)
- Per-step `tools: [name1, name2]` — optional restrict кои tools вижда subagent-ът за конкретна стъпка
- `step_complete` тагва tool calls по step name, издава warnings ако декларирани tools не са използвани

### Trace Viewer & Workflow Editor
- **Trace viewer** — global "Tool Calls" панел, per-step tool calls section с source badge (`script`/`mcp`), timeline маркери (зелени/лилави точки), warnings box за неизвикани tools
- **Workflow editor** — card layout за tools, select dropdown за type, 9 hint entries, Template button за quick-start

### Engine-driven AGENT.md injection (2026-04-06)
- **Проблем:** първоначалният дизайн разчиташе на orchestrator LLM-а да модифицира `.claude/agents/workflow-step/AGENT.md` преди всеки step spawn (по инструкция от SKILL.md). Реален e2e тест (italy_games, `tools-demo`) показа, че LLM-ът пропуска тази стъпка → subagent работи без tool server → 0 structured tool calls в trace
- **Решение:** engine-ът сам модифицира AGENT.md като Python код, без участие на LLM → 100% гаранция
  - `workflow_init` → `_backup_agent_md(name)` — snapshot в `.agent/workflows/<name>/agent-md-backup.md`
  - `step_begin` → `_inject_agent_md(name, tools_info)` — винаги от backup (никога accumulation), парсва YAML frontmatter, добавя `mcpServers:` dict
  - `step_complete` → `_restore_agent_md(name)` — hygiene restore
  - `workflow_finalize` → final restore + delete backup
- **Adapter separation без abstraction:** всички helper функции short-circuit-ват ако `.claude/agents/workflow-step/AGENT.md` липсва → Cursor е автоматично no-op без adapter клас
- SKILL.md (`run-workflow`) обновена — премахната обсолентната "step 2: inject tools into AGENT.md" секция
- **Tests:** 12 нови unit теста в `playground/test_tools.py` (`TestAgentMdBackup`, `TestAgentMdInjectionStepBegin`, `TestAgentMdRestore`) — общо 161 теста, всички минават автономно в playground

### Нов документ
- `user_docs/02b-workflow-tools-architecture.md` — design rationale за workflow tools: защо MCP proxy вместо Bash, защо engine-driven injection вместо LLM, adapter separation чрез file-presence, token overhead анализ

---

## Phase 18: Per-Step Subagent Generation (2026-04-07 — 2026-04-08)

Phase 17 (engine-driven AGENT.md runtime injection) се оказа фундаментално неработещ в Claude Code. Целият подход беше преработен от край до край.

### Проблеми с Phase 17 (емпирично доказани)

- **CC кешира subagent config при session startup** — runtime AGENT.md modification от engine-а не достига до spawn-натите subagents. Forensic debug log (`agent-md-trace.jsonl`) показа, че файлът е физически в "injected" състояние 30+ секунди преди subagent spawn-а, но subagent transcript-ът съдържа нула MCP tool calls.
- **CC bug #25200** — inline `mcpServers:` в subagent frontmatter не работи: server процесите не се стартират при subagent spawn. Това убива всички варианти на "stable inline server" pattern (Phase 37).
- **CC сканира `.claude/agents/` САМО при session startup** — runtime added subagent файлове не са достъпни без CC restart.
- **`tools:` whitelist е strict allowlist** с **explicit tool names** — wildcards като `mcp__server__*` empirically не работят.

### Phase 38 архитектура (приета 2026-04-07, имплементирана 2026-04-08)

**Static, install-time generation** на per-step subagent файлове:

- **Един стабилен MCP server** `workflow-tools-loader.py` регистриран в `.mcp.json`. Сканира всички workflow.yaml-и при startup и експозва всички script tools от тях. Никога не се променя runtime. Naming: `mcp__workflow_tools__<workflow>__<tool>` (нормализирани hyphens към underscores).
- **Per-(workflow, step) subagent файлове** в `.claude/agents/<workflow>-<step>/AGENT.md`, генерирани от Python скрипт `init-workflow.py`. Всеки файл има строг `tools:` whitelist, включващ built-ins + script tools на стъпката + mcp tools (от `expected_tools` в workflow.yaml).
- **Phase 36 helper-и премахнати:** `_backup_agent_md`, `_inject_agent_md`, `_restore_agent_md`, `_delete_agent_md_backup`, `_agent_md_debug_log`. Engine не модифицира никакви файлове runtime.
- **Phase 35 per-workflow proxy generation премахнат:** `_WORKFLOW_TOOLS_TEMPLATE`, `_generate_workflow_tools_proxy`, `_cleanup_workflow_tools_proxy`. Заменен с глобалния loader.

### Нови компоненти

- **`workflow-tools-loader.py`** — стабилен MCP сървър за script tools (~320 реда)
- **`init-workflow.py`** — Python скрипт за генериране на per-step subagents за един workflow (idempotent, поддържа orphan cleanup за изтрити стъпки)
- **`update-workflows.py`** — bulk sync скрипт за всички workflows
- **`workflow-tool-validator.py`** — PreToolUse hook за script tool args schema validation (defensive layer над server-side validation в loader-а)
- **`/init-workflow` slash command** — обвивка около init-workflow.py
- **`/update-workflows` slash command** — обвивка около update-workflows.py
- **`install.py` step 12/12** — извиква update-workflows.py автоматично при Claude Code install

### Engine surgery

`workflow-engine.py` намален от 2412 до 2030 реда (–382 реда):
- Премахнати: всички Phase 35 proxy generation + Phase 36 AGENT.md injection helper-и и call sites
- Преоформен `tool_step_begin`: връща ново поле `subagent_type: <workflow>-<step>` (за CC) или fallback `workflow-step` (когато per-step файлът липсва) или `null` (за inline стъпки)
- Ново поле `tool_docs`: prompt enrichment block, асиметрично рендиран (brief affordance в CC, full inline docs в Cursor/inline)
- Ново поле `subagent_warning`: surface-ва на потребителя ако per-step subagent файлът липсва, с инструкция да пусне `/init-workflow`

### Cursor адаптер (асиметричен)

- Cursor няма subagent frontmatter с whitelist mechanism
- File-presence detection (`.claude/agents/<workflow>-<step>/AGENT.md` exists?) разделя двата режима
- В Cursor: `subagent_type: null`, full tool docs в step prompt, script tools видими глобално от loader-а в `.cursor/mcp.json`
- В CC: per-step subagent с brief affordance, script tools whitelist-нати per step

### Нов формат: `expected_tools` в workflow.yaml

За `type: mcp` tools, workflow авторите трябва да декларират конкретните tool имена, които стъпката използва, защото engine-ът не може да query-ва external server при init time:

```yaml
tools:
  - name: pdf_tools
    type: mcp
    required: true
    expected_tools: [extract_text, get_metadata]
```

Init-workflow.py включва тези в whitelist-а: `mcp__pdf_tools__extract_text`, `mcp__pdf_tools__get_metadata`.

### Test suite

- `playground/test_tools.py` намален от 964 до 416 реда (премахнати Phase 35/36 тестове, добавени Phase 38 тестове за `workflow_init` без proxy generation/AGENT.md backup)
- `playground/test_phase38.py` — нов файл с 32 теста за loader, init-workflow, update-workflows, step_begin enrichment, PreToolUse hook
- Total: 156 unit теста pass, 4 skipped (jsonschema-зависими)

### Documentation

- `02b-workflow-tools-architecture.md` пренаписан с честна Phase 35→36→37→38 история и empirical findings
- `02c-claude-code-deep-dive.md` — нов документ обясняващ defensively защо нашите CC-specific решения изглеждат точно така (за бъдещи engineers и AI агенти)
- `02-workflows.md` обновен за Phase 38 lifecycle
- `MANUAL_TESTS.md` в playground — стъпки за тестове, изискващи CC restart

### Empirical validation в e2e2 (2026-04-08, post-implementation)

Manual tests M1-M5 минаха. По време на validation бяха открити и поправени 8 bugs:

1. **SubagentStop hook matcher** в `.claude/settings.json` — `"workflow-step"` literal не match-ваше per-step имена. Fixed to `".*"`. gate-check.py вече има bail-out за non-workflow subagents. _(commit `86f4babf`)_
2. **gate-check.py search path** — `find_definition_dir()` пропускаше `templates/examples/`. Fixed да match-ва resolve_workflow's search order. _(commit `63349da8`)_
3. **Tool warnings false positives — full vs short MCP names** — comparison сравняваше bare name срещу full MCP-prefixed name recorded by gate-check.py от subagent transcript. Fixed да включва двете форми. _(commit `63349da8`)_
4. **Tool warnings policy** — emit-ваха се за стъпки без explicit `tools:` filter и за inline orchestrator стъпки. Fixed: warnings само за explicit filter + само за subagent steps (orchestrator-side MCP calls не могат да се track-ват). _(commit `7ee14ce8`)_
5. **Global orphan cleanup gap в `update-workflows.py`** — изтриване на цял workflow.yaml оставяше subagents orphaned, защото init-workflow.py само scan-ва per-workflow. Fixed: добавена global orphan scan logic. _(commit `ce5297b4`)_
6. **Loader CLI args formatting** — script tools очакваха `--key=value` от proxy convention, loader ги подаваше през stdin/env vars. Fixed: loader formats arguments като CLI flags. _(commit `bff5751f`)_
7. **MANUAL_TESTS.md prerequisite** — споменаваше само директния `python` invocation, не `/init-workflow` slash command. Fixed. _(commit `e3e44153`)_

Test suite след всички fixes: **166 passing, 0 skipped** (jsonschema е инсталиран в env-а).

**Validation status:** Phase 38 е architecturally validated end-to-end. Workflows минават с structured MCP tool calls (не Bash fallback), per-step subagent filtering работи както е дизайниран, schema validation hook блокира bad input с ясен feedback, целият init-workflow lifecycle (create → run → edit → orphan → cleanup) минава без regressions.

### install.py default behavior — install both adapters

Преди Phase 38 (и по време на foundation): `install.py target` инсталираше **само Cursor** (default), а `--claude` инсталираше **само** Claude Code. Това означаваше, че за пълен setup трябваше да се изпълнят **два** install run-а, което беше confusing UX.

**Промяна (post-Phase 38):**

- **Default behavior** (без флагове): инсталира **двата** адаптера в един run.
- `--cursor` (нов): инсталира само Cursor.
- `--claude` (renamed semantic): инсталира само Claude Code (преди беше "claude вместо cursor", сега е "claude only").
- `--cursor` и `--claude` са mutually exclusive (argparse group).
- `--update`, `--force`, `--prune`, `--dry-run` остават orthogonal.

Refactor:
- Adapter-specific code изтеглен в нова `install_adapter(adapter, args, target, script_dir)` функция, която приема `"cursor"` или `"claude"`.
- Universal стъпки (1-6: docs, scripts, mcp, workflows templates, specs, tools) се изпълняват веднъж.
- За всеки активен адаптер се изпълнява `install_adapter()` с 5 стъпки (skills, hooks, mcp config, rules, agents).
- Output форматирането сега groups стъпките под `=== Cursor adapter ===` / `=== Claude Code adapter ===` headers.

Bug fix: pycache в target — install.py step "Generating per-step subagents" пускаше `update-workflows.py` като subprocess в target dir, което създаваше `__pycache__/` в `.agent/scripts/` на target. Fixed чрез подаване на `PYTHONDONTWRITEBYTECODE=1` env var към subprocess-а.

`test_install.py` — 25 tests pass без модификации (тестовете очакваха старото default = Cursor, но новото default включва и Cursor, така че assertion-ите за `.cursor/` присъствие продължават да работят; assertion-ите за `.claude/` отсъствие не съществуваха в default тестовете). Test `test_no_pycache_in_target` сега работи коректно благодарение на bytecode fix-а.

`user_docs/01-overview.md` обновен с новия install workflow и пълна таблица на флаговете.
