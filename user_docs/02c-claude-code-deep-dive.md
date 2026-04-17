# 02c — Claude Code Deep Dive: защо изборите ни са такива

Този документ обяснява **защо** Phase 38 работи в Claude Code по специфичен начин, който може да изглежда неочаквано или прекомерно сложен на пръв поглед. Целта е да дадем на бъдещите инженери (и AI агенти) всичко, което сме научили емпирично за CC, така че да не повтарят експериментите.

> **Чете се след:** [02b-workflow-tools-architecture.md](02b-workflow-tools-architecture.md). 02b обяснява крайната архитектура. Този документ обяснява защо алтернативите не работят.

---

## 1. Каква е спецификата на Claude Code, която ни ограничава

Claude Code има четири характеристики, които правят нашия design проблем нетривиален:

### 1.1. Subagent config caching при session startup

CC чете `.claude/agents/<name>/AGENT.md` файловете **веднъж**, при стартирането на сесия. След това държи конфигурацията в паметта и я ползва за всеки `Agent(subagent_type=<name>)` spawn. **Няма cache invalidation mechanism.**

Това означава: ако ти модифицираш AGENT.md по време на работеща сесия, CC няма да забележи промяната. Спавн-натите subagents ще използват старата (cached) конфигурация. Единственият начин да накараш CC да види промяната е **restart на цялата сесия**.

**Емпирично доказано на 2026-04-06:** Phase 36 беше базиран на runtime AGENT.md modification (engine пишеше mcpServers entries при step_begin). Forensic debug log (`agent-md-trace.jsonl`) показа физически readback verification — файлът беше в "injected" състояние 30+ секунди преди subagent spawn-а — но subagent transcript-ът съдържаше нула MCP tool calls. CC просто не препрочете файла.

### 1.2. Subagent file scanning само при startup

Подобно на 1.1, но за **новосъздадени** subagent типове: ако създадеш `.claude/agents/<new-name>/AGENT.md` по време на работеща сесия, CC няма да го види. Спавн с `Agent(subagent_type="new-name")` връща error `Agent type 'new-name' not found`.

**Емпирично доказано на 2026-04-07:** Тестов файл `runtime-test/AGENT.md` беше създаден в течение на CC сесия. Опитът да се spawn-не върна:

```
Error: Agent type 'runtime-test' not found.
Available agents: general-purpose, statusline-setup, ..., workflow-step, mcp-tester
```

Забележете, че `mcp-tester` (създаден в **предишна** сесия) присъства в списъка, но `runtime-test` не. Това е definitive empirical proof, че scanning-ът е startup-only.

### 1.3. Inline `mcpServers:` в subagent frontmatter — Bug #25200

Документацията на CC твърди, че subagents могат да дефинират собствени MCP servers в YAML frontmatter:

```yaml
---
name: my-subagent
mcpServers:
  my_server:
    command: python
    args: [".agent/mcp/my-server.py"]
---
```

**На практика това не работи** в текущия CC build (v2.1.92 към 2026-04-07). Server процесът не се стартира при subagent spawn, и subagent-ът не вижда никакви tools от него. Това е документирано в [GitHub issue #25200](https://github.com/anthropics/claude-code/issues/25200) ("Custom agents cannot use deferred MCP tools").

**Емпирично доказано** в няколко варианта:
- С `tools:` whitelist съдържащ `mcp__my_server__*` (wildcard) → не работи
- С `tools:` whitelist съдържащ explicit `mcp__my_server__some_tool` → не работи
- Без `tools:` whitelist (default inheritance) → не работи

PoC server включваше startup logging — log файлът никога не беше създаден, потвърждавайки, че процесът никога не беше стартиран.

### 1.4. `tools:` field е strict allowlist (по дизайн)

Това **не е bug** — официално documented behavior. Когато subagent frontmatter съдържа `tools: <list>`, само tools-овете в списъка са достъпни за subagent-а. Всичко друго (built-ins not in list, MCP tools not in list) е филтрирано. Полето е по подразбиране **explicit allowlist**, не denylist.

Wildcards като `mcp__my_server__*` **не работят** — empirically тествани и не match-ват нищо. Само explicit tool names.

Това разкрива **fundamental design constraint** за нас: ако искаме per-step филтриране на MCP tools, трябва да enumerate-нем explicit tool names в whitelist-а. Това е изпълнимо за `script` type tools (engine знае имената от workflow.yaml), но изисква explicit declaration за `mcp` type tools (`expected_tools` field).

---

## 2. Защо избрахме точно тази архитектура

С 4-те ограничения от секция 1, разгледай защо Phase 38 е (вярваме) единствената работеща опция в текущия CC.

### 2.1. Защо НЕ можем да генерираме subagents runtime

От 1.2: CC не picks up нови subagent файлове без restart. Това убива всеки дизайн, при който engine-ът генерира subagent при `workflow_init`. Дори да генерираме файла **точно преди** spawn-а, CC няма да го види.

Това ни принуждава към **install/edit-time generation**: subagent файловете се създават **преди** CC startup, не по време на работата на workflow-а.

### 2.2. Защо НЕ можем да модифицираме съществуващи subagents runtime

От 1.1: CC кешира parsed AGENT.md при startup. Phase 36 опитваше да модифицира `workflow-step/AGENT.md` динамично — engine-ът добавяше `mcpServers:` entry при `step_begin`, restore-ваше при `step_complete`. Цикълът беше Python-deterministic, доказан с unit tests.

Но CC не препрочиташе файла. Subagent-ът виждаше cached pre-injection версия. Доказателство в `agent-md-trace.jsonl`: readback verification confirm-ваше, че файлът съдържа injected content на disk-а, но subagent transcript-ът показваше нула MCP tool calls.

Това ни принуждава към **per-step subagent files**: всяка стъпка си има свой собствен subagent type, генериран веднъж и неmodified runtime. Никакъв "modify единичен файл" подход не работи.

### 2.3. Защо НЕ можем да ползваме inline `mcpServers:` в subagent frontmatter

От 1.3: Bug #25200. Inline mcpServers в subagent frontmatter не стартира servers и не expose-ва tools. Това убива Phase 37 Variant A (state file pattern в inline server).

Това ни принуждава към **`.mcp.json` registration** на loader-а — global ниво, видимо от parent session, и **наследяемо** от subagents (когато се използва explicit whitelisting).

### 2.4. Защо ИМАМЕ нужда от explicit MCP tool names в whitelist

От 1.4: wildcards не работят, default inheritance също. Това ни принуждава да enumerate-нем explicit tool names.

За **script** type tools това е тривиално — engine знае имената от workflow.yaml. Init-workflow.py форматира `mcp__workflow_tools__<workflow>__<tool>` за всеки.

За **mcp** type tools е по-деликатно — engine не знае имената на tools-овете в external server. Решение: explicit `expected_tools` field в workflow.yaml декларира кои tools от server-а ще се ползват:

```yaml
tools:
  - name: pdf_tools
    type: mcp
    required: true
    expected_tools: [extract_text, get_metadata]
```

Init-workflow.py формира `mcp__pdf_tools__extract_text` и `mcp__pdf_tools__get_metadata` в whitelist-а на стъпката.

Алтернатива би била query на server-а live при generation, но това би изисквало server-ът да е достъпен при `init-workflow` time, което не винаги е случая. Explicit declaration е по-предсказуемо.

---

## 3. Какво НЕ направихме (и защо)

Тук са няколкото "очевидно по-прости" варианта, които някой бъдещ инженер (или AI агент) може да предложи. Разглежда ги и обяснявам защо не работят.

### 3.1. "Просто използвай Bash за всички script tools"

Това е **Phase 35 alternative**, който формално отхвърлихме в [02b § 2](02b-workflow-tools-architecture.md). Това реално работи технически — но губи:

- **Structured tracing** — Bash calls в trace-а са anonymous shell commands, не именовани tool calls
- **Schema validation** — LLM може да форматира арг-овете грешно (особено в Windows PowerShell vs Bash)
- **Tool discovery** — LLM трябва да помни от prompt-а как да формира командата, вместо да види именован tool в инвентара
- **IDE visibility** — trace viewer показва анонимни Bash calls вместо `extract_tables(file_path=...)`

В обобщение: цялата инвестиция в `tools:` section на workflow.yaml отпада. Phase 35 целта (named, traceable script tools) се изпарява.

### 3.2. "Просто инсталирай един subagent за всеки workflow, не за всяка стъпка"

Това е по-просто архитектурно — един `<workflow>-step` subagent file per workflow, който whitelist-ва всички tools от workflow.tools. Защо не?

Защото губиш **per-step tool filtering**. Workflow `tools-demo` има три стъпки: `analyze` (count_lines), `enrich` (transform_json), `report` (query_table). С единичен subagent file и трите стъпки виждат и трите tools — `analyze` ще види `transform_json` и `query_table`, въпреки че не ги ползва.

Това нарушава [02-workflows.md update 6](../discussion.md) решението за step-level tool filtering, и:

- Затрупва subagent's context с irrelevant tool definitions (по-високи tokens per step)
- Дава на LLM-а опция да ползва tools, които не са планирани за тази стъпка (по-малко предсказуемост)
- Прави spec checking по-слаб (subagent може случайно да направи нещо извън scope-а)

Per-step филтриране е reason d'être за цялата `tools:` секция.

### 3.3. "Просто register-ни всички MCP servers в `.mcp.json` глобално"

Това е **Phase 37 Variant C**, отхвърлен в [discussion.md 2026-04-06](../discussion.md):

- **Token overhead** — всички tools от всички workflows са в parent session инвентара постоянно. ~150-300 tokens per tool × 20 tools = 3-6K tokens на всеки prompt в parent session. Това е приемливо за нас сега (Phase 38 държи бюджета bounded), но при scaling на много workflows, проблемът се натрупва.
- **Boundary** — orchestrator tools (`workflow_init`, `step_begin`...) се виждат от subagent-и, освен ако subagent има explicit `disallowedTools` filter (което не сме тествали emirically да работи).
- **No per-step filtering** — subagents виждат глобалния set, не филтриран за конкретната стъпка.

Phase 38 ползва вариант на това (`.mcp.json` registration на **един** loader server), но компенсира за per-step filtering с per-step subagent files и whitelist-ове. Това дава "best of both" — глобална регистрация (за да работи в CC), per-step видимост (за да запазим filtering целите).

### 3.4. "Use Anthropic Skills вместо MCP tools"

Skills (`.claude/skills/<name>/SKILL.md`) са `progressive disclosure` mechanism — names + descriptions винаги в системния prompt, full body load-ва при invocation. Това би било по-евтино на токени за големи tool инвентари.

Но Skills имат критични ограничения за нашия случай:
- Не са function-call tools — те са instruction wrappers. LLM-ът ги "извиква", body-то се inject-ва в conversation, и LLM-ът чете инструкциите. Това **не дава** schema validation, structured args, tracing като MCP tools.
- За script tools, инструкциите в Skill body биха казали "run `python scripts/extract-tables.py <file>`" — точно това е Bash fallback с по-лъскав wrapper. Същите downsides.

Skills работят отлично за **reusable, cross-workflow capabilities** като "git commit pattern" или "code review checklist". Но не са подходящи за **per-workflow script tools**, които искат structured tracing и schema enforcement.

### 3.5. "Просто чакай Anthropic да поправи bug #25200"

Може би. Но:

- Нямаме контрол над сроковете на CC fixes
- Тествахме на 2026-04-07 в v2.1.92; bug-ът е still open
- Нашата система трябва да работи **сега**, не "когато може би"
- Дори ако bug-ът се поправи, runtime AGENT.md modification (Phase 36) пак не работи заради 1.1, и runtime subagent file generation (1.2) пак не работи

Дори частично fix на #25200 не би заместило per-step subagent generation pattern. Phase 38 е robust независимо от status на този bug.

---

## 4. Какво научихме за работа с Claude Code в общ план

Тези инсайти са валидни и за бъдещи Phase-ове и за други custom workflow engines.

### 4.1. Static is reliable, runtime is fragile

CC's mental model е "проектът се сетъп-ва веднъж, после се ползва". Това не е grade A или B — просто е **дизайн философия**. Runtime modifications срещу `.claude/`, `.mcp.json` или config файлове са в gray zone — понякога CC ги picks up, понякога не, и почти никога няма ясен сигнал кога. **Static, install-time generation** е винаги предсказуема.

### 4.2. Empirical testing > documentation

Multiple findings от Phase 36/37 contradict-ваха documented behavior:
- Documentation твърди subagents inherit MCP tools by default → empirically не
- Documentation твърди inline `mcpServers:` works → empirically не (bug #25200)
- Documentation не споменава subagent file scanning timing → empirically startup-only

**Винаги empirically test-вай преди да базираш дизайн на CC docs.** Бъди готов да хвърлиш дни работа.

### 4.3. CC restart е нормална част от workflow

В Phase 38 priemame, че `/init-workflow` followed by CC restart е acceptable UX cost при добавяне или промяна на workflow. Това е реалност, която не можем да заобиколим — и след като я приемем, дизайнът става много по-прост.

Алтернативно: ако някога Anthropic добави "rescan agents" или "reload mcp servers" runtime команди, бихме могли да премахнем restart-а. Но не градим архитектурата си около това.

### 4.4. Намаляване на cycle time на error feedback

PreToolUse hooks (`workflow-tool-validator.py`) дават **по-бърз** error feedback от server-side validation. Server returns MCP error → CC обвива в "tool error" → LLM вижда обобщение. Hook returns exit 2 + stderr → CC директно показва на LLM специфичното съобщение → LLM по-точно знае какво да поправи.

И двете работят, hook-ът е допълнителен defensive layer, не заместител.

### 4.5. Dual schema source: design vs runtime

Workflow.yaml-ите служат като **design-time source of truth** за tool schemas. Loader-ът чете workflow.yaml-ите при startup и ги ползва runtime. Validator-ът също чете workflow.yaml-ите при hook invocation. Това е "single source, multiple consumers" pattern.

Алтернативата би била schema-та да живее само в loader's runtime memory. Но тогава validator hook-ът би трябвало да query-ва loader-а за schema-та live, което adds latency и failure modes (loader crashed, slow responding, etc.).

---

## 5. Какво да направиш ако се сблъскаш с CC проблем при следващите фази

### 5.1. Преди да предложиш ново runtime modification решение

Ask:
- Може ли да се направи install-time или edit-time? (по-сигурно)
- Изисква ли CC restart? Ако да — приеми го; не го заобикаляй със trickery
- Тествай emirically с минимален PoC преди да assume-неш че CC ще се държи както documentation казва

### 5.2. Преди да базираш design на documented CC feature

Test it. Серiously. Multiple of our empirical findings contradicted official docs. Build a minimal test case (separate from your real code), restart CC, observe actual behavior. Документирай finding-а в `discussion.md` — бъдещият ти ще ти благодари.

### 5.3. Преди да добавиш сложност за "edge cases"

Ask: "what does the empirical evidence say about this?" If none — make a tiny PoC and observe. Don't speculate.

---

## 6. Референции

- [02b-workflow-tools-architecture.md](02b-workflow-tools-architecture.md) — финалната Phase 38 архитектура
- [discussion.md 2026-04-06](../discussion.md) — discovery на CC subagent caching
- [discussion.md 2026-04-07](../discussion.md) — Phase 37 PoC, breakthrough с fresh subagent
- [Bug #25200](https://github.com/anthropics/claude-code/issues/25200) — Custom agents cannot use deferred MCP tools
- `dist/playground/test_phase38.py` — empirical tests за всички critical paths
- `dist/playground/e2e2/` — fresh install fixture за end-to-end validation
