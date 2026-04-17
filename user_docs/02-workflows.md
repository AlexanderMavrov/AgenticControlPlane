# 02 — Workflows

## Какво е workflow?

Workflow е декларативно описание на multi-step LLM задача. Всяка стъпка се изпълнява от изолиран subagent, който знае само своя goal, inputs и summaries от предни стъпки. Gate система валидира output-а преди преминаване към следваща стъпка.

---

## Workflow YAML формат

```yaml
name: my-workflow
version: 1
description: >
  Какво прави този workflow.

params:
  - name: component
    description: "Component name"
    required: true
  - name: domain
    description: "Logical domain"
    required: false
    default: "general"

gate:
  structural: true        # Python script валидация
  semantic: true           # LLM проверка
  human: false             # Human approval
  max_gate_retries: 5      # Retry-и в рамките на 1 subagent
  max_step_retries: 3      # Re-spawn на нов subagent

context:
  carry_forward: summary   # "none" | "summary"

steps:
  - name: step-name
    goal: >
      Какво трябва да направи subagent-ът.
    subagent: true          # Изолиран контекст (default: true)
    spec_check: true        # Проверява specs преди edit (default: true)
    inputs:
      - path: ".agent/docs/overview.md"
        inject: file
      - path: "data/input.json"
        inject: file_if_exists
        struct: my-schema
    outputs:
      - path: "data/result.json"
        struct: result-schema
    gate:                   # Per-step override
      human: true
      max_step_retries: 1
```

---

## Стартиране

```
/run-workflow my-workflow --component EditField --domain ui
```

Orchestrator-ът:
1. Чете `workflow.yaml`
2. Парсва params от командата
3. Създава `manifest.json` (runtime state)
4. За всяка стъпка: spawn subagent → gate валидация → next step

Resume след прекъсване:
```
/run-workflow my-workflow --resume
```

---

## Params

Потребителски аргументи при стартиране. Дефинират се в `params:` секцията.

### `{param}` placeholders

Params се заместват в goal текст и input/output пътища:

```yaml
steps:
  - name: write-spec
    goal: >
      Write a behavioral spec for {component} in domain {domain}.
    outputs:
      - path: ".agent/specs/{domain}/{component}.md"
```

### param_bindings — когато една стъпка открие нещо, което следващата трябва да знае

Понякога при стартиране на workflow-а не знаем всички стойности предварително. Например: стъпка CLARIFY пита потребителя какъв component иска — и чак тогава научаваме името. Следващата стъпка WRITE-SPEC трябва да го получи.

`param_bindings` решава точно това: казва на orchestrator-а "след тази стъпка, отвори файла, извади стойността и я запиши обратно в params".

```yaml
params:
  component:
    description: "Component name"
    # Няма default — ще бъде попълнен от clarify стъпката
  domain:
    description: "Spec domain"

steps:
  - name: clarify
    goal: >
      Ask the user what component they want to spec out.
    outputs:
      - path: data/approved.json
        struct: approved-requirements
    param_bindings:
      component: "data/approved.json::component"
      domain: "data/approved.json::domain"

  - name: write-spec
    goal: >
      Write spec for {component} in {domain}.
      # ^^^ тези стойности вече са попълнени от clarify
```

**Какво се случва стъпка по стъпка:**

1. **Subagent-ът** на CLARIFY работи — пита потребителя, взима решения, и накрая **записва** `data/approved.json` с нещо като `{"component": "message-queue", "domain": "persistence"}`. Subagent-ът не знае за param_bindings — просто си пише output-а.

2. Subagent-ът спира. **Structural gate** валидира файла срещу schema.

3. Gate PASS → subagent спира завинаги → контролът е при **orchestrator-а**.

4. Orchestrator-ът вижда `param_bindings` в workflow.yaml и прави нещо просто:
   - Отваря `data/approved.json`
   - Чете полето `component` → `"message-queue"`
   - Записва го в `manifest.params.component`

5. Когато spawn-ва subagent за WRITE-SPEC, `{component}` в goal-а вече е `"message-queue"`.

```
CLARIFY subagent пише data/approved.json
    │
    ▼ Gate PASS → subagent спира
    │
Orchestrator чете param_bindings:
    component ← data/approved.json::component → "message-queue"
    domain    ← data/approved.json::domain    → "persistence"
    │
    ▼ manifest.params обновен
    │
WRITE-SPEC subagent получава goal: "Write spec for message-queue in persistence."
```

**Синтаксис:** `"<file-path>::<json-field>"`
- `data/approved.json` — относителен път спрямо workflow директорията
- `::component` — JSON field selector (поддържа dot notation: `::metadata.name`)

**Важно:** param-ът **трябва** да е деклариран в `params:` секцията на workflow-а — bindings не създават нови параметри, а попълват вече дефинирани.

---

## Gate Protocol

Трислоен механизъм за валидация след всяка стъпка:

```
Subagent завършва → writes outputs
    │
    ▼ Layer 1: STRUCTURAL (Python script)
gate-check.py валидира:
    - Файловете съществуват ли?
    - Валиден JSON/YAML?
    - Schema match?
    │
    ├─ FAIL → followup message → subagent retry
    │
    ▼ Layer 2: SEMANTIC (LLM)
Orchestrator проверява:
    - Смислен ли е output-ът?
    - Покрива ли goal-а?
    - Коректни ли са данните?
    │
    ├─ FAIL → нов subagent spawn (с feedback)
    │
    ▼ Layer 3: HUMAN (optional)
Orchestrator пита потребителя:
    "Step X done. Summary: [...]. Approve?"
    │
    ├─ "No, fix Y" → нов subagent spawn
    │
    ▼ PASS → следваща стъпка
```

### step_complete Safety Net

`step_complete` MCP tool-ът валидира output-ите **преди** да маркира стъпката като завършена, когато gate hook-ът **не е fire-нал**. Три случая:

| Случай | Защо hook-ът не fire-ва | step_complete валидира? |
|--------|------------------------|----------------------|
| `subagent: false` (inline) | Няма subagent → няма SubagentStop | ✅ Да |
| Parallel steps | Claude Code може да не fire-не hook за parallel agents | ✅ Да |
| Hook пропуснат | Crash, timeout, missing config | ✅ Да |
| Нормален subagent | Hook fire-на, gate-result.json съществува | ❌ Skip (вече валидирано) |

Ако валидацията fail-не, tool-ът връща `action: "FIX_AND_RETRY"` — orchestrator-ът трябва да fix-не output-а и да извика `step_complete` отново.

Това е **safety net** — основният механизъм остава hook-базираният gate. step_complete хваща случаите, в които hook-ът не е fire-нал.

### Retry логика

Два вида retry:

| Тип | Trigger | Какво се случва | Лимит |
|-----|---------|-----------------|-------|
| **Gate retry** | Structural FAIL | `followup_message` → същият subagent получава нов turn | `max_gate_retries` (default: 5) |
| **Step retry** | Semantic FAIL или gate retry limit | Orchestrator spawn-ва **нов** subagent с feedback | `max_step_retries` (default: 3) |

Gate retry е евтин (продължава същия subagent). Step retry е скъп (нов контекст).

### Per-step override

```yaml
steps:
  - name: clarify
    gate:
      human: true              # Изисква human approval за тази стъпка
      max_step_retries: 1      # Само 1 retry (интерактивна стъпка)
  - name: scan
    gate:
      structural: true
      semantic: false           # Не е нужна LLM проверка
```

---

## Struct Schemas

Описват очаквания формат на inputs и outputs. Живеят в `structs/` директорията на workflow-а.

### Два стила

**Custom format (за Markdown + frontmatter):**
```yaml
name: spec
format: markdown
frontmatter:
  required:
    - field: spec_id
      type: string
      pattern: "^[A-Z]+-\\d{3}$"
required_sections:
  - "Requirements"
  - "Examples"
```

**Standard JSON Schema (за JSON outputs):**
```yaml
name: result
type: object
required: [status, items]
properties:
  status:
    type: string
    enum: [success, partial, failed]
  items:
    type: array
    items:
      type: object
      required: [name]
```

---

## Workflow Tools

Workflow-ите могат да декларират tool dependencies — инструменти, които subagent-ите ползват по време на изпълнение. Два типа:

### Script tools (`type: script`)

Shell команди, които се обвиват като MCP tools от стабилния `workflow-tools-loader.py` сървър (Phase 38). Loader-ът се стартира при CC startup, чете всички workflow.yaml-и в `.agent/workflows/templates/`, и експозва script tools от тях с пълна schema. Subagent-ите ги виждат като `mcp__workflow_tools__<workflow>__<tool>` с хранен описание и `inputSchema`.

```yaml
tools:
  - name: count_lines
    type: script
    command: "python .agent/scripts/count-lines.py"
    description: "Count lines in a file"
    input_schema:
      type: object
      required: [file_path]
      properties:
        file_path:
          type: string
          description: "Path to the file"
```

**Защо MCP server, а не Bash в prompt-а?**
- **Tracing** — всяко извикване се логва: tool name, аргументи, duration, резултат
- **Schema validation** — `input_schema` гарантира правилни аргументи
- **Tool discovery** — LLM вижда named tool в tool list-а си, не зависи от текст в prompt-а
- **IDE visibility** — tool call се показва като `count_lines(file_path=...)`, не като `Bash("python ...")`

> **Забележка:** Нищо не пречи в `goal` текста да се каже "пусни X чрез Bash" — просто няма да има structured tracing.

### MCP server dependencies (`type: mcp`)

Външни MCP сървъри, от които workflow-ът зависи. Engine-ът проверява наличността им при стартиране.

```yaml
tools:
  - name: database_server
    type: mcp
    required: true                  # Блокира workflow ако липсва
    server_config:                  # За auto-start в Claude Code
      command: "python"
      args: [".agent/mcp/db-server.py"]
```

- **`required: true`** → workflow не тръгва ако сървърът не е наличен. Показва се съобщение на потребителя.
- **`required: false`** → предупреждение, но workflow продължава.
- **Description** идва от MCP сървъра (чрез `tools/list`) — не се дублира в workflow.yaml.
- **Потребителят** е отговорен MCP сървърът да е наличен — engine-ът само проверява и предупреждава.

### Per-step tool restriction

По подразбиране subagent-ът вижда **всички** workflow tools. Може да се ограничи:

```yaml
steps:
  - name: analyze
    tools: [count_lines]           # Само count_lines за тази стъпка
    goal: "Count lines in {target}..."
  - name: process
    # tools: не е зададен → вижда всички
    goal: "Process with any available tool..."
```

### Как tools стигат до subagent-а (Phase 38)

**В Claude Code:**

При **install time** (или след `/init-workflow`), Python скрипт (`init-workflow.py`) генерира **per-step subagent файл** в `.claude/agents/<workflow>-<step>/AGENT.md` за всяка стъпка с `subagent: true`. Файлът съдържа **строг `tools:` whitelist**, включващ:

- Built-in tools (Read, Write, Edit, Bash, Glob, Grep)
- Script tool-овете на тази стъпка като `mcp__workflow_tools__<workflow>__<tool>`
- Mcp tool-овете (от `expected_tools` в workflow.yaml) като `mcp__<server>__<tool>`

```yaml
# .claude/agents/tools-demo-analyze/AGENT.md (auto-generated):
---
name: tools-demo-analyze
description: Workflow step subagent for 'analyze' step of 'tools-demo' workflow
model: inherit
tools: Read, Write, Edit, Bash, Glob, Grep, mcp__workflow_tools__tools_demo__count_lines
maxTurns: 100
hooks:
  PreToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "python .agent/scripts/file-guard.py"
    - matcher: "mcp__workflow_tools__.*"
      hooks:
        - type: command
          command: "python .agent/scripts/workflow-tool-validator.py"
---
```

При `step_begin` engine-ът връща `subagent_type: tools-demo-analyze`. Orchestrator-ът spawn-ва точно този subagent с `Agent(subagent_type="tools-demo-analyze")`. Subagent-ът вижда **точно** tool-овете, които му трябват за стъпката — нищо повече.

Script tools идват от стабилния `workflow-tools-loader.py` MCP сървър, регистриран в `.mcp.json`. Той се стартира при CC startup, чете всички workflow.yaml-и, и експозва всички script tools. Subagent-ите ги виждат filter-нати чрез своя `tools:` whitelist.

**Защо тази архитектура (Phase 38)?**

По-рано подходите бяха различни:
- **Phase 35**: per-workflow MCP proxy generation при `workflow_init` (`_workflow_tools_<name>.py`) — изискваше Phase 36 за да работи в CC
- **Phase 36**: engine-driven runtime AGENT.md injection — emirically не работи, защото CC кешира subagent config при session startup
- **Phase 37**: stable inline `mcpServers:` + dynamic state file — блокирано от CC bug #25200 (inline mcpServers не стартира servers)

Phase 38 ползва **static, install-time generation** на per-step subagent файлове — единственият емпирично работещ pattern в текущия CC. Виж [02b](02b-workflow-tools-architecture.md) и [02c](02c-claude-code-deep-dive.md) за пълна история.

**В Cursor:** `.claude/agents/<workflow>-<step>/AGENT.md` не съществува (Cursor няма subagent frontmatter mechanism). Engine-ът детектира това чрез file-presence и в `step_begin` връща `subagent_type: null` + **full inline tool docs** в `tool_docs` field. Orchestrator-ът ги добавя към step prompt-а, и Cursor LLM-ът ползва script tool-овете чрез shell tool. Loader-ът остава регистриран в `.cursor/mcp.json` за compatibility, но per-step filtering се прави чрез prompt enrichment, не чрез subagent whitelist.

### Lifecycle (Phase 38)

```
Install time / /init-workflow / /update-workflows
  ├── Чете workflow.yaml файлове
  ├── За всяка стъпка с subagent: true:
  │     ├── Изчислява expected tools (built-ins + script + mcp expected_tools)
  │     └── Пише .claude/agents/<workflow>-<step>/AGENT.md
  └── Изтрива orphan subagent файлове от премахнати стъпки
  ➜ "Restart Claude Code" notice

workflow_init
  ├── Парсва workflow.yaml
  ├── Проверява availability на declared tools
  └── Ако required mcp tool липсва → STOP + съобщение

step_begin
  ├── Изчислява active_tools (per-step filter или всички workflow tools)
  ├── File-presence detection: CC mode (per-step subagent file present) или Cursor/inline mode
  ├── В CC: subagent_type = <workflow>-<step>, tool_docs = brief affordance
  ├── В Cursor: subagent_type = null, tool_docs = full inline docs
  └── Връща готов prompt blocks за orchestrator-а

  Orchestrator spawn-ва Agent(subagent_type=...) или изпълнява inline.
  Subagent вижда филтрирани tools чрез своя whitelist (CC) или чрез prompt docs (Cursor).
  Calls → loader.py изпълнява script-овете → връща структуриран резултат
  PreToolUse hook валидира input schema преди всеки call

step_complete
  └── Тагва tool calls с име на стъпка

workflow_finalize
  └── Merge-ва tool-calls.json в trace
```

**Без runtime modification на конфигурационни файлове** — нито на AGENT.md, нито на `.mcp.json`. Всичко е статично, install-time.

### Trace Viewer показва tool calls

- **Global панел** "Tool Calls (all steps)" — overview на всички извиквания
- **Per-step секция** в step cards — source badge (`script`/`mcp`), аргументи, duration, output preview
- **Timeline маркери** — зелени за script tools, лилави за MCP tools, click → scroll до детайла

---

## Context & Carry Forward

### `carry_forward: "summary"`

След всяка стъпка orchestrator-ът записва summary в `context/<step-name>.summary.md`. Следващите стъпки получават summaries от предни стъпки — не пълния output, а кратко резюме. Част от predefined workflows ползват този режим (spec-audit, doc-spec-extraction, create-workflow, registry-sync). Другите (spec-write, spec-enforcement, spec-write-and-implement, hook-diagnostic) използват default `"none"` и разчитат на input файлове вместо summaries.

### `carry_forward: "none"` (default)

Стъпките не получават контекст от предни стъпки. Подходящо за напълно независими стъпки. Това е default стойността — ако workflow-ът не зададе `carry_forward`, summaries не се предават.

### Per-step override

```yaml
steps:
  - name: learn
    carry_forward: false    # Opt-out: тази стъпка не получава summaries
  - name: report
    carry_forward: true     # Opt-in: тази стъпка получава summaries дори при wf-level "none"
```

> **Забележка:** Per-step override е **симетричен** — стъпка може да зададе `carry_forward: false` за да пропусне summaries (когато workflow-level е `"summary"`), или `carry_forward: true` за да получи summaries (когато workflow-level е `"none"`). Ако не е зададен, стъпката наследява workflow-level настройката.

---

## Parallel Execution

Стъпка може да се изпълнява паралелно за множество items:

```yaml
steps:
  - name: scan
    parallel: true
    parallel_key: "discovery-plan.domains[status=pending]"
    inputs:
      - path: data/discovery-plan.json
    outputs:
      - path: "data/scans/{domain}-result.json"
        struct: scan-result
```

Orchestrator-ът чете `discovery-plan.json`, намира всички domains със `status: pending`, и spawn-ва **отделен subagent** за всеки domain. Всички вървят паралелно.

---

## Delegation

Стъпка може да делегира към друг workflow вместо да spawn-ва subagent:

```yaml
steps:
  - name: enforce
    delegate_to: spec-enforcement
    params:
      component: "{component}"
      domain: "{domain}"
```

Когато orchestrator-ът стигне до стъпка с `delegate_to`, той **не spawn-ва subagent**. Вместо това отваря `workflow.yaml` на делегирания workflow, създава **отделен manifest** за него, и започва да изпълнява стъпките му последователно — spawn-ва subagent за всяка стъпка, обработва gates, точно както за обикновени стъпки. Това е **същият LLM, в същата сесия** — просто изпълнява повече стъпки. Когато делегираните стъпки свършат, orchestrator-ът продължава със следващата стъпка от parent-а.

Важни детайли:

**Manifest-и:** Делегираният workflow има **собствен manifest в собствена директория**. Всеки workflow живее на `.agent/workflows/<name>/` — те са **сестрински директории**, не вложени:

```
.agent/workflows/
├── spec-write-and-implement/        ← parent
│   └── manifest.json                   steps: write (delegate), enforce (delegate)
│
├── spec-write/                      ← делегиран (сестринска, не подпапка)
│   └── manifest.json                   steps: discover, clarify, write-spec, register
│
└── spec-enforcement/                ← делегиран
    └── manifest.json                   steps: check-specs, implement, verify, register
```

Parent manifest-ът **не поема** стъпките на делегирания — вижда само крайния резултат. При startup parent-ът знае за своите 2 стъпки (`write`, `enforce`), без да знае колко стъпки съдържат делегираните workflows. Manifest-ът на делегирания workflow се създава **чак когато orchestrator-ът стигне до delegation стъпката**.

Когато delegation-ът завърши, parent-ът получава:
```json
"write": { "status": "completed", "delegation_result": { "workflow": "spec-write", "status": "completed" } }
```

**Gate config:** Делегираният workflow използва **собствена gate конфигурация** от своя `workflow.yaml` — не наследява parent-а.

**Params:** Предават се през `params:` секцията на стъпката. `{component}` се resolve-ва от parent manifest-а.

**Param bindings при delegation:** Delegation стъпка може да има `param_bindings` — точно както обикновена стъпка. Разликата е, че пътищата се resolve-ват спрямо **делегирания** workflow runtime dir (защото output файловете са там). Това е критично за auto-discovery: делегираният workflow открива стойности (напр. component name), а parent-ът ги получава обратно чрез bindings и ги подава на следващите стъпки.

**Пример:** `spec-write-and-implement` делегира към два workflow-а. В auto-discovery mode, `spec-write` открива component/domain в CLARIFY стъпката, и parent-ът ги получава обратно чрез `param_bindings`:

```yaml
# spec-write-and-implement/workflow.yaml
steps:
  - name: write
    delegate_to: spec-write              # 4 стъпки: DISCOVER → CLARIFY → WRITE → REGISTER
    params:
      component: "{component}"
      domain: "{domain}"
    param_bindings:                       # ← след delegation, чети от spec-write/data/
      component: "data/approved-requirements.json::component"
      domain: "data/approved-requirements.json::domain"

  - name: enforce
    delegate_to: spec-enforcement        # 4 стъпки: CHECK → IMPLEMENT → VERIFY → REGISTER
    params:
      component: "{component}"           # ← вече попълнен от bindings
      domain: "{domain}"
```

За потребителя изглежда като един workflow с 8 стъпки. Технически са три manifest-а: parent + spec-write + spec-enforcement.

> Подробности за имплементацията на param propagation при delegation: [02a — Workflows: Cursor Implementation](02a-workflows-cursor-impl.md).

---

## Natural Language Branching

Вместо `if/else` в YAML, условната логика се описва в `goal` на стъпката:

```yaml
goal: >
  IF a "section" param was provided:
    - Search the document for that section heading
    - If NOT FOUND: list the 5 closest matches and ASK the user
  IF NO "section" param:
    - Scan the full document
```

LLM-ът е branch evaluator — чете goal + params и решава. Gate-ът валидира резултата.

---

## Manifest

Auto-generated runtime state. Живее в `manifest.json` в директорията на workflow-а.

```json
{
  "workflow": "my-workflow",
  "workflow_version": 1,
  "run_id": "my-workflow-20260319-143022-b7e2",
  "status": "in_progress",
  "params": { "component": "EditField", "domain": "ui" },
  "current_step": "write-spec",
  "steps": {
    "clarify": { "status": "completed", "started_at": "...", "completed_at": "..." },
    "write-spec": { "status": "in_progress", "started_at": "..." }
  }
}
```

Потребителят **не пише** manifest — engine-ът го създава и обновява. При `--resume` orchestrator-ът чете manifest-а и продължава от текущата стъпка.

---

## Predefined Workflows

Built-in workflows, shipped с engine-а:

| Workflow | Описание | Стъпки |
|----------|----------|--------|
| `spec-write` | Запиши/обнови spec (без имплементация) | DISCOVER → CLARIFY → WRITE-SPEC → REGISTER-SPEC |
| `spec-write-and-implement` | Напиши spec + имплементирай | delegate: spec-write → delegate: spec-enforcement |
| `spec-enforcement` | Имплементирай с spec проверка | CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER |
| `spec-audit` | Read-only QA одит | DISCOVER → SCAN(parallel) → REPORT |
| `doc-spec-extraction` | Извлечи specs от документ | ANALYZE → EXTRACT(parallel) → VALIDATE → COMMIT |
| `create-workflow` | Интерактивно създаване на workflow | LEARN → DISCUSS → CREATE |

### doc-spec-extraction — подробности

Извлича behavioral specs от техническа документация. Два режима:

**Merge mode** (default):
```
/run-workflow doc-spec-extraction --source "path/to/doc.md" --focus "section 3.3"
```
- ANALYZE чете source + existing specs, маркира "confirmed" или "needs_update"
- EXTRACT при "confirmed" → запазва стария spec; при "needs_update" → merge
- VALIDATE проверява drafts спрямо source + existing specs
- Подходящ за инкрементални обновления и добавяне на нови фокус области

**Rewrite mode** (`--rewrite true`):
```
/run-workflow doc-spec-extraction --source "path/to/doc.md" --focus "..." --rewrite true
```
- ANALYZE маркира ВСИЧКИ existing specs като "needs_update"
- EXTRACT пише всички specs от нулата от source-а
- Подходящ за периодичен quality reset, когато specs са натрупали неточности

**spec_mapping** — ANALYZE генерира mapping между existing и proposed specs в analysis report-а. VALIDATE ползва mapping-а за да сравнява правилните двойки, дори когато структурата е променена (различен домейн, различен spec_id, split/merge). Existing specs без proposed еквивалент се маркират като `coverage_gap`.

**Regression protection** — VALIDATE сравнява всеки draft (merge или rewrite) с existing spec чрез spec_mapping. Ако draft-ът губи информация (cross-references, interpretation notes, примери), се маркира като `regression`. COMMIT не презаписва regression и coverage_gap specs — оставя ги за review.

| Validation status | Значение | COMMIT действие |
|-------------------|----------|-----------------|
| `valid` | Draft е коректен | Записва в `.agent/specs/` |
| `issues_found` | Проблеми открити | Minor → fix, major → review |
| `conflict` | Противоречие между specs | Не записва, review |
| `regression` | Draft губи информация от existing spec | Не записва, review |
| `coverage_gap` | Existing spec няма еквивалент в new drafts | Не изтрива existing, review |

**Validation Criteria quality** — EXTRACT инструкциите изискват Validation Criteria да бъде семантично подравнен с Rule Statement и Rationale. Ако правило забранява X "for purpose Y" и Rationale обяснява конкретен механизъм на вреда, criteria трябва да проверява дали вредата може реално да се случи — forbidden pattern в unreachable код не е violation.

**Severity body match (structural gate)** — Struct schema за spec файлове проверява, че severity keyword-ът от frontmatter (MUST, SHOULD, MAY) присъства case-insensitive в `## Rule Statement` body. Ако frontmatter казва `severity: MUST`, но Rule Statement използва "SHALL" или само "may" — structural gate fail, EXTRACT retry. Това хваща терминологични грешки детерминистично, без зависимост от LLM.

**Enhanced VALIDATE checks** — Два от 6-те семантични check-а на VALIDATE са усилени:
- **Traceability (#4)**: Освен source references, VALIDATE сравнява `related_specs` на draft-а с `cross_domain_dependencies` от analysis report-а. Ако документирана зависимост липсва от related_specs — flag.
- **Testability (#5)**: Когато spec_mapping показва existing predecessor, VALIDATE сравнява Validation Criteria на draft-а с тези на стария spec. Ако старият spec имаше specific exclusions или boundary guidance, които draft-ът пропуска — flag като testability concern.

**spec_mapping completeness** — ANALYZE трябва да генерира spec_mapping entry за ВСЕКИ файл в `.agent/specs/`, включително specs в домейни, различни от proposed структурата. Гарантира, че при restructuring нито един стар spec не е "забравен" без explicit причина.
| `registry-sync` | Синхронизирай `_registry.json` | SCAN → REVIEW → REGISTER |
| `hook-diagnostic` | Диагностика на hook/gate системата | 3 lightweight тестови стъпки |

---

## Minimal Workflow Example

```yaml
name: hello
version: 1
description: Simple one-step workflow

gate:
  structural: true
  semantic: false
  human: false

steps:
  - name: greet
    goal: >
      Say hello to the user and write a greeting to data/greeting.json
      with fields: message (string), timestamp (string).
    outputs:
      - path: data/greeting.json
```

---

## `.agent/` и Gitignore

`.agent/` е в `.gitignore` — runtime файлове (manifests, traces, gate results) не се commit-ват. Но gitignore засяга и IDE search tools: **Glob и Grep не намират файлове в `.agent/`**.

Това е проблем, когато LLM трябва да **открие** кои файлове съществуват (напр. "кои specs има?"). Три механизма решават проблема:

| Механизъм | Кога работи | Как |
|-----------|------------|-----|
| `step_begin` glob expansion | Автоматично при workflow стъпки | Python `glob.glob()` resolve-ва patterns в `.agent/` |
| `list_agent_files` MCP tool | Когато MCP сървърът е наличен | Python `os.walk()` за file discovery |
| Bash fallback | Винаги | `python -c "import glob; ..."` в терминал |

**Правило:** Никога не ползвай Glob или Grep за търсене в `.agent/`. Ползвай `list_agent_files` за discovery и Read с exact path за четене.

---

## Имплементация в Cursor

Как workflow engine-ът работи в Cursor — orchestrator, subagents, hook, gate retry loop, trace, delegation, error handling: **[02a — Workflows: Cursor Implementation](02a-workflows-cursor-impl.md)**
