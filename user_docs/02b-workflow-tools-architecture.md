# 02b — Workflow Tools: Architecture & Design Rationale

Този документ обяснява **защо** workflow tools са устроени така, както са — не просто как да ги ползваш (за това виж [02-workflows.md § Workflow Tools](02-workflows.md)). Покриват се ключовите архитектурни решения, алтернативите, и причините да ги отхвърлим — включително няколко решения, които **опитахме и отхвърлихме емпирично** в течение на разработката.

> **За читателя:** Phase 38 архитектурата е резултат от три отделни design итерации, всяка от които открои нов проблем в Claude Code. Документът разказва пътя, защото следващите инженери (или AI агенти) трябва да знаят кои подходи вече сме пробвали и защо не работят, преди да предложат "очевидно по-просто" решение.

---

## 1. Gold standard за гаранция (контекст)

Преди да се потопим в конкретиката, важно е да установим йерархията на гаранциите. Workflow engine-ът трябва да изпълнява критичен код **надеждно** — не "обикновено работи". Различните механизми дават различна сигурност:

| Механизъм | Гаранция | Кой го изпълнява |
|-----------|----------|------------------|
| IDE hook (PreToolUse, SubagentStop) | **Най-висока** — IDE автоматично, LLM не може да пропусне | IDE |
| MCP tool (native) | **Висока** — native tool call, schema enforced server-side | LLM (judgement) + server |
| Engine код (Python, deterministic) | **100%** — subprocess, не зависи от LLM | Engine |
| "Пусни скрипт през Bash" инструкция в prompt | **Ниска** — LLM може да забрави, сбърка args, skip-не | LLM (judgement) |
| Инструкция в SKILL.md "направи X" | **Ниска** — същото като Bash; зависи от LLM judgment | LLM (judgement) |

**Правило:** ако нещо **трябва** да се случи, слагаме го колкото е възможно по-нагоре в таблицата. LLM judgment е fallback, не основа.

Това правило ни доведе до **четири** последователни архитектурни решения за tool delivery — всяко от които трябваше да преодолее проблем, открит от предишното.

---

## 2. Script tools: защо MCP proxy, а не Bash в prompt-а

### Проблемът

Workflow може да декларира script tools:

```yaml
tools:
  - name: extract_tables
    type: script
    command: "python scripts/extract-tables.py"
    input_schema:
      type: object
      properties:
        file_path: { type: string }
```

Въпрос: как subagent-ът ги "извиква"? Има два варианта:

- **Вариант A — Bash в goal текста:** В `step.goal` добавяме "To extract tables, run: `python scripts/extract-tables.py <file>`". Subagent-ът прочита goal-а, разбира инструкцията, и извиква Bash.
- **Вариант B — MCP proxy:** Engine-ът или отделен MCP server expose-ва script tool-а като native MCP tool. Subagent-ът го вижда в своя tool list и го извиква като `extract_tables(file_path=...)`.

### Защо избрахме Вариант B (MCP proxy) — четири причини

**1. Structured tracing** — основната причина.

MCP tool call се логва като structured event: `{name, args, duration, result, exit_code}`. Tool server-ът пише `.agent/workflows/<name>/tool-calls.json`, който при `workflow_finalize` се merge-ва в trace-а. Trace viewer-ът показва per-step tool calls с аргументи, duration, output preview, warnings за неизпълнени tools.

Bash call в сравнение е generic string: `Bash("python scripts/extract-tables.py foo.pdf '1-5'")`. От него не може да се парсне кой tool беше извикан, какви аргументи, или дори кой step-а го направи. Целият observability layer се губи.

**2. Schema validation** — `input_schema` полето гарантира правилни типове и required fields. При Bash LLM-ът може да забърка позиционни аргументи, да пропусне флагове, или да escape-не грешно (особено в Windows PowerShell vs Bash).

**3. Tool discovery** — subagent вижда named tool с description в своя tool list. При Bash инструкциите са в goal-а, който при дълъг prompt може да бъде "забравен" от модела (recency bias, attention decay). Native tool винаги е видим в tool list-а.

**4. IDE visibility** — trace viewer и Claude Code/Cursor UI показват `extract_tables(file_path=..., pages=...)` като именован tool call. Bash извикванията изглеждат като anonymous shell commands и се губят в noise-а.

### Какво НЕ значи това

**Bash в goal не е забранен.** За прости еднократни команди (`ls`, `cat`, quick check) е напълно ок. Разделението е:

- **Формално декларирани tools** (в `workflow.yaml` `tools:` секция) → MCP proxy, защото workflow-ът поема отговорност за тях.
- **Ad-hoc команди в goal-а** → Bash, защото не са част от формалния контракт.

---

## 3. История на доставката: от Phase 35 до Phase 38

Решихме да доставяме script tools като MCP tools. Но **как** да направим това в Claude Code-ска среда оказа се мъчителен въпрос. Минахме през три неуспешни архитектури, преди да стигнем до текущата. Заслужава си да ги опишем — защото и трите изглеждаха разумни на хартия.

### Phase 35: per-workflow proxy server, генериран при `workflow_init`

**Идея:** Engine-ът, при `workflow_init`, генерира `_workflow_tools_<name>.py` файл — temporary MCP server, който expose-ва script tool-овете на този конкретен workflow. Файлът се изтрива при `workflow_finalize`.

**Защо изглеждаше добре:** lifecycle бе ясен (per-run), token overhead = 0 при idle (server съществува само докато workflow тече), концепцията беше просто "временен MCP сървър".

**Защо счупи:** Phase 35 разчиташе на friend, който трябваше да дойде в Phase 36 — engine-driven AGENT.md injection. Без него subagent-ът никога не виждаше този temporary server.

### Phase 36: engine-driven AGENT.md injection

**Идея:** Subagent-ите в Claude Code декларират своите MCP servers в YAML frontmatter на `.claude/agents/workflow-step/AGENT.md`. Първоначалният подход беше: SKILL.md (`run-workflow`) казва на orchestrator LLM-а "при `step_begin` модифицирай AGENT.md, добави `mcpServers:` от tools_info, запиши обратно". Това е **LLM injection**.

**Реален e2e тест в italy_games (2026-04-05) показа защо LLM injection не работи:** workflow завърши `completed`, но `tool-calls.json` беше **празен** — orchestrator LLM-ът просто пропусна стъпката от SKILL.md, subagent-ът стартира с base AGENT.md без tool server, и fallback-на към Bash.

Това е самопротиворечивост: избрахме MCP proxy защото "LLM може да забрави", а после поставихме активирането му в зависимост от същата слабост.

**Решението на Phase 36:** engine-ът директно модифицира AGENT.md от Python код, без участие на LLM. Backup при `workflow_init`, inject при `step_begin`, restore при `step_complete` и `workflow_finalize`. 161 unit теста минаха.

**Защо счупи (емпирично доказано на 2026-04-06):** Claude Code **кешира subagent config при session startup**. Когато engine-ът модифицира AGENT.md по време на работа, **CC не го препрочита** при следващия Agent spawn. Forensic debug log (`agent-md-trace.jsonl`) показа физическо доказателство: AGENT.md е в injected състояние 30+ секунди преди spawn-а, но subagent-ът никога не вижда tool server-а.

Documented поведение от Claude Code docs твърди, че няма cache invalidation mechanism за subagent config — единственият път е CC restart. Това разкри Phase 36 като фундаментално невалиден.

### Phase 37: stable inline `mcpServers:` + dynamic state file

**Идея:** Вместо runtime modification на AGENT.md, регистрираме **един стабилен** inline `mcpServers:` entry в `.claude/agents/workflow-step/AGENT.md` (никога не се пипа след install) и го свързваме с **generic loader Python script**, който при startup чете state file (`.agent/_active.json`). State file-ът се update-ва от engine-а при `workflow_init` (active tool definitions) и се изчиства при `workflow_finalize`. Hypothesis: CC спавнва **fresh** Python процес per subagent invocation → fresh процес чете state → винаги вижда current tools.

**PoC се изпълни на 2026-04-07.** Multiple test scenarios:

| Test | Конфигурация | Резултат |
|------|--------------|----------|
| 1 | inline `mcpServers:` без `tools:` whitelist | ❌ Server процес не стартира, subagent вижда само built-ins |
| 2 | inline `mcpServers:` + `tools:` whitelist с wildcard `mcp__workflow_tools__*` | ❌ Същото — server не стартира |
| 3 | server в `.mcp.json` + `tools:` whitelist с explicit MCP име в `workflow-step` | ❌ Parent session вижда tool, subagent не |
| 4 | server в `.mcp.json` + **без** `tools:` (default inheritance) | ❌ Subagent вижда само built-ins |

Стигнахме до временно заключение, че **CC subagents в текущия build (v2.1.92) изобщо не могат да виждат MCP tools при никакви обстоятелства**.

### Phase 37 breakthrough: fresh `mcp-tester` subagent

Ключово прозрение: всички тестове бяха върху `workflow-step` — subagent, който беше **много пъти редактиран** (Phase 36 backup/restore + ръчни тестови edits). Възможно е CC да държи някаква "broken state" за subagents, които са били модифицирани runtime.

Създадохме **съвсем нов** subagent type `mcp-tester` с минимална конфигурация, идентична на сложните тестове, но fresh файл, никога не пипан runtime:

```yaml
---
name: mcp-tester
description: Fresh subagent created for MCP tool visibility test
model: inherit
tools: Read, Bash, mcp__workflow_tools_poc__poc_tool_A
maxTurns: 20
---
```

След CC restart, spawn-нахме `mcp-tester`. Резултат: **Subagent-ът видя `mcp__workflow_tools_poc__poc_tool_A`.** Server logs потвърдиха, че CC извика `tools/list` от MCP сървъра.

**Изводи:**
1. CC subagents **МОГАТ** да виждат MCP tools чрез explicit `tools:` whitelist с конкретни MCP tool имена.
2. `workflow-step` беше "corrupted" в CC's вътрешна state, защото беше много пъти runtime-edited. Това е CC bug или edge case, който не можем да заобиколим.
3. **Всички runtime modification стратегии (Phase 36 + Phase 37 inline pattern) са dead.** Решението изисква static, install-time generation.

### Допълнителен констринт: runtime pickup

Тествахме дали CC picks up `.claude/agents/<new-name>/AGENT.md` файлове, създадени по време на активна сесия. Резултат: ❌ **CC сканира `.claude/agents/` САМО при session startup.** Runtime added subagent файлове не са достъпни без restart.

Това окончателно затвори всички "engine генерира subagent при workflow_init" стратегии.

### Phase 38: per-step subagent files, генерирани при install/init time

С empirical findings в ръка, дизайнът се промени радикално:

- **Един стабилен MCP server** (`workflow-tools-loader.py`) регистриран в `.mcp.json`. Чете всички workflow.yaml-и при startup, expose-ва всички script tools от всички workflows. Никога не се променя runtime.
- **Per-(workflow, step) subagent файлове** в `.claude/agents/<workflow>-<step>/AGENT.md`, генерирани от Python скриптове (`init-workflow.py`, `update-workflows.py`), всеки със **строг `tools:` whitelist**, който включва точно tool-овете нужни за тази стъпка.
- **Engine не модифицира никакви файлове runtime.** При `workflow_init` той просто проверява availability. При `step_begin` връща `subagent_type: <workflow>-<step>` за orchestrator-а да spawn-не правилния subagent.
- **CC restart-required event** е само при добавяне или редактиране на workflow — никога per run.

Това е финалната работеща архитектура. Тестове в `dist/playground/test_phase38.py` (32 нови теста) и end-to-end тест в `dist/playground/e2e2/` (fresh install + 18 auto-generated subagents) потвърждават, че всичко работи.

---

## 4. Phase 38 архитектура — детайлно

### Компоненти

```
.mcp.json (registered at install time, never modified)
├── workflow_engine          → workflow-engine.py (orchestrator tools)
└── workflow_tools           → workflow-tools-loader.py (script tool exposure)

.agent/scripts/
├── init-workflow.py         → generates per-step subagent files for one workflow
├── update-workflows.py      → bulk sync for all workflows
├── workflow-tool-validator.py → PreToolUse hook for script tool args
├── file-guard.py            → PreToolUse hook for engine file protection
└── ...

.agent/mcp/
├── workflow-engine.py       → orchestrator MCP server (workflow_init, step_begin, ...)
└── workflow-tools-loader.py → script tools MCP server (per-workflow tool name namespacing)

.claude/agents/
├── workflow-step/           → generic fallback (when /init-workflow not run)
└── <workflow>-<step>/       → auto-generated per-step subagents
    └── AGENT.md             → strict tools whitelist + standard hooks

.claude/skills/
├── run-workflow/            → orchestrator slash command
├── init-workflow/           → wraps init-workflow.py
└── update-workflows/        → wraps update-workflows.py
```

### Workflow lifecycle (типичен поток)

```
Author writes workflow.yaml
        │
        │  /init-workflow <name> (or /update-workflows)
        ▼
init-workflow.py reads workflow.yaml
        │
        │  generates .claude/agents/<name>-<step>/AGENT.md
        │  for each step with subagent: true
        ▼
"Restart Claude Code" notice
        │
        ▼
User restarts CC
        │
        │  CC reads .mcp.json → starts workflow-tools-loader.py
        │  CC reads .claude/agents/ → indexes all subagent types
        ▼
/run-workflow <name> --target ...
        │
        ▼
Orchestrator: workflow_resolve → workflow_init
        │
        ▼
For each step:
    step_begin returns subagent_type: <workflow>-<step>
        │
        ▼
    Agent(subagent_type=<workflow>-<step>, prompt=...)
        │
        │  Subagent sees only its whitelisted tools.
        │  Calls mcp__workflow_tools__<wf>__<tool>(...)
        │  loader executes the underlying script
        │  PreToolUse hook validates input schema
        ▼
    step_complete → next step
        │
        ▼
workflow_finalize → trace, summary
```

### Naming convention

| Subagent type | `<workflow-name>-<step-name>` | kebab-case |
| MCP tool name (in CC inventory) | `mcp__workflow_tools__<workflow_normalized>__<tool_normalized>` | hyphens → underscores |
| Per-step AGENT.md path | `.claude/agents/<workflow>-<step>/AGENT.md` | one dir per step |

`workflow_normalized` and `tool_normalized` apply `re.sub(r"[^a-zA-Z0-9_]", "_", name)` — necessary because CC tool names cannot contain hyphens reliably.

### Tool docs (engine-side prompt enrichment)

`step_begin` returns a `tool_docs` field that the orchestrator appends to the agent task prompt verbatim. The format depends on adapter:

- **CC per-step subagent** (file present in `.claude/agents/`): brief affordance reminder. The subagent already has the tools whitelisted, so the LLM sees them in its inventory; the brief block is just a one-line nudge per tool.
- **Cursor / inline orchestrator step** (no per-step subagent file): full inline docs — command, schema fields, example invocation. Cursor has no per-subagent tool whitelist mechanism, so this is the only path for the LLM to know about the script tools.

Adapter detection is file-presence: `os.path.isfile(.claude/agents/<workflow>-<step>/AGENT.md)`. No adapter classes, no conditionals on environment variables.

---

## 5. PreToolUse hook for script tool validation

Phase 38 adds `workflow-tool-validator.py` — a PreToolUse hook attached to every per-step subagent that intercepts calls to `mcp__workflow_tools__.*` and validates the arguments against the `input_schema` declared in workflow.yaml.

**Why a hook in addition to server-side validation?** The loader already validates server-side using jsonschema (when available). The hook is a **defensive extra layer** that gives the LLM faster, more obvious feedback:

- Hook fires **before** the call reaches the loader → faster feedback loop
- Hook can return a clear `Schema validation failed at 'file_path': required field is missing` message via stderr → CC surfaces this to the LLM, which retries with corrected input
- Without the hook, the loader's error response goes through the MCP transport and the LLM sees a more abstract `tool error` message

**Hook policy:**
- Non-workflow tool name → exit 0 (no-op pass-through)
- External MCP tool (e.g. `mcp__demo_db__query_table`) → exit 0 (out of scope)
- Workflow tool with no schema → exit 0 (graceful degradation)
- Schema validation passes → exit 0
- Schema validation fails → exit 2 + stderr (CC blocks, surfaces message)

**Hook scope explicitly does NOT cover external MCP tools.** External servers are responsible for their own input validation. We don't try to discover their schemas dynamically — that would require a runtime registry and cache invalidation logic, both of which add complexity for a benefit that already exists (the external server itself rejects invalid input).

---

## 6. Cursor adapter (asymmetric)

Cursor doesn't have:
- A `.claude/agents/` directory equivalent
- A per-subagent `tools:` whitelist mechanism  
- Subagent frontmatter parsing

What this means for the design:

| Aspect | Claude Code (Phase 38) | Cursor |
|--------|----|----|
| Per-step subagents | Generated, with strict whitelist | Not applicable — no mechanism |
| Loader registration | `.mcp.json` | `.cursor/mcp.json` |
| Script tool visibility | Per-step (filtered by whitelist) | Global (all script tools always visible) |
| Tool docs in goal prompt | Brief affordance reminder | Full inline command + schema docs |
| Token overhead per session | Bounded (only built-ins + whitelisted tools per subagent) | Postoянен (all script tools loaded globally) |
| Schema validation hook | Yes (`workflow-tool-validator.py`) | No (Cursor hook system is different) |
| Server-side validation | Yes (in loader) | Yes (in loader, same code) |

**The asymmetry is acknowledged trade-off**, not a missing feature. Cursor users get global script tool visibility with full inline docs — different UX, same capability surface, different token economics. Both are valid for their respective environments.

---

## 7. Token overhead analysis

The Phase 38 architecture has bounded, predictable token costs:

| Source | Tokens | Frequency | Notes |
|--------|--------|-----------|-------|
| `workflow_engine` MCP tool definitions | ~1500-2000 | Every prompt | Orchestrator-only tools |
| `workflow_tools` (loader) tool definitions | ~150-300 per script tool, all workflows | Every prompt | Loaded globally |
| Per-step subagent inventory (CC only) | Built-ins + step's tools (~500-1500 tokens) | Subagent only, per spawn | Filtered by whitelist |
| `tool_docs` block in step prompt | ~50-200 tokens (brief) or ~500-1500 (full) | Per step | Depends on adapter |

For a project with 5 workflows × 4 script tools = 20 script tools, the loader exposes ~3-6K tokens of tool definitions globally. This is a **fixed cost** independent of how many workflows run per session.

The cost is acceptable because:
- Per-step subagents in CC stay minimal (only what they need)
- The orchestrator pays the cost once per session, not per workflow run
- The original Phase 35 dream of "0 tokens at idle" was empirically unreachable in CC; Phase 38 gives bounded cost with full functionality

---

## 8. Известни ограничения и future work

### Не решено в Phase 38

- **Concurrent workflow runs** — не съществува механизъм за паралелно изпълнение на различни workflows в една и съща CC сесия. State в `.agent/workflows/<name>/manifest.json` е per-workflow, така че не conflict-ва, но `subagent_type` dispatch е stateless. Не препоръчителна употреба.
- **Hot reload на workflow промени** — добавяне или редактиране на workflow.yaml изисква CC restart, защото CC сканира `.claude/agents/` само при startup. `/init-workflow` ясно casz "restart required". Това е fundamental CC constraint, не наша архитектурна слабост.
- **External MCP server tool discovery** — за `type: mcp` tools трябва explicit `expected_tools` field в workflow.yaml. Engine-ът не query-ва server-а dynamic при generation. Решение: добавено `expected_tools` поле, документирано в `workflow-yaml.md`.
- **CC bug #25200** — Custom subagents не могат да виждат tools от inline `mcpServers:` в собственото им frontmatter. Phase 38 заобикаля това чрез `.mcp.json` registration. Ако bug-ът се поправи, бихме могли да преразгледаме inline scope (по-стрига boundary), но не е блокер.

### Какво отпадна (за справка)

- **Phase 35** _workflow_tools_<name>.py per-workflow proxy generation — отпада в Phase 38
- **Phase 36** runtime AGENT.md injection — не е възможно в CC
- **Phase 37** Variant A (stable inline mcpServers + state file) — блокирано от CC bug #25200

---

## 9. Референции

- [02-workflows.md § Workflow Tools](02-workflows.md) — практическа употреба на `tools:` секцията
- [04-tools.md](04-tools.md) — Trace Viewer и Workflow Editor
- [05-changelog.md](05-changelog.md) — хронология на phase-овете
- [06-claude-code-adapter.md](06-claude-code-adapter.md) — общата Claude Code adapter архитектура
- Test coverage: `dist/playground/test_phase38.py` — 32 unit теста за loader, init-workflow, hook, step_begin
- Empirical findings: `tasks/agentic-control-plane/discussion.md` — entries 2026-04-06 и 2026-04-07
- LLM reference docs: `dist/.agent/docs/workflow-yaml.md` (за tool authors)
