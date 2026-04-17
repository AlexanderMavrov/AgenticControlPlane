# 06 — Claude Code Adapter: Design Decisions

Този документ описва как всеки аспект от Workflow Engine е имплементиран в Cursor, как ще бъде имплементиран в Claude Code, и **защо** избираме конкретния подход. Обновява се при всяка промяна в имплементацията.

---

## Архитектурен принцип

**Не копираме Cursor имплементацията.** За всеки проблем:
1. Какъв проблем решаваме?
2. Какви инструменти предлага Claude Code?
3. Какъв е най-добрият native подход?

Engine layer (`.agent/`) остава **непроменен**. Адаптираме само integration layer.

---

## 1. Gate Retry Loop (Structural Validation)

### Проблем
След като subagent завърши стъпка, трябва да валидираме output-а срещу struct schema. Ако валидацията fail-не, subagent-ът трябва да получи feedback и да опита отново.

### Cursor подход
```
subagentStop hook → gate-check.py → stdout JSON
  PASS: return {}                    → subagent спира
  FAIL: return {followup_message: "fix X"} → subagent продължава (нов turn)
```
Семантика: `followup_message` = continuation marker. `{}` = stop signal. Контраинтуитивно — откритие от Phase 8 (2026-03-17), причинило дни debugging.

### Claude Code подход
```
SubagentStop hook → gate-check.py → exit code + stderr
  PASS: exit 0                      → subagent спира
  FAIL: exit 2 + stderr "fix X"     → subagent продължава (prevented from stopping)
```
Документирано в hooks-guide: "Exit 2 on SubagentStop = Prevents subagent stopping."

### Защо е по-добре
- **По-интуитивно:** exit 0 = success, exit 2 = block. Няма контраинтуитивна семантика.
- **По-просто:** Няма JSON parsing за stdout. Просто exit code.
- **Feedback е в stderr:** Стандартен Unix pattern. Claude Code автоматично подава stderr като feedback.

### Промени в gate-check.py
- Вместо `print(json.dumps({"followup_message": msg}))` → `sys.stderr.write(msg); sys.exit(2)`
- Вместо `print(json.dumps({})); sys.exit(0)` → `sys.exit(0)` (нищо на stdout)
- Exit code 0 = pass, exit code 2 = fail+retry
- BOM handling: Claude Code може да НЕ изпраща BOM — трябва тест. Ако не — BOM кодът остава но не пречи.

---

## 2. Phantom Invocation Filtering

### Проблем
Host-ът може да fire-не hook за subagents, които не са част от workflow. Трябва да ги филтрираме.

### Cursor подход
Три нива филтрация:
1. `subagent_id` format check (`toolu_` prefix = orchestrator echo)
2. Empty `task` field = no spawn prompt
3. `run_token` в task prompt = workflow authentication

### Claude Code подход
```json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "workflow-step",
        "hooks": [{ "type": "command", "command": "python .agent/scripts/gate-check.py" }]
      }
    ]
  }
}
```
`matcher` филтрира по `agent_type`. Hook-ът fire-ва **само** за agents от тип `workflow-step`.

### Защо е по-добре
- **Нулев custom код:** Matcher-ът е declarative — няма нужда от format checks в gate-check.py.
- **Елиминира run_token:** Не е нужен HTML comment injection. Matcher-ът гарантира, че hook-ът fire-ва само за workflow agents.
- **Елиминира phantom detection:** Built-in agents (Explore, Plan, general-purpose) автоматично изключени.

### Промени в gate-check.py
- Премахване на phantom detection блока (subagent_id format, empty task)
- Премахване на run_token extraction от task prompt
- Опростяване: gate-check.py получава САМО workflow subagent invocations

### Забележка: Run isolation
Ако два workflow-а работят паралелно (рядко), matcher-ът не ги разграничава — и двата са `workflow-step`. За това може да запазим file-based run_token check (четем от manifest, не от task prompt). Но за v1 — не е необходимо.

---

## 3. Step Subagent Definition

### Проблем
Всяка workflow стъпка трябва изолиран LLM контекст с конкретен goal, tools, и ограничения.

### Cursor подход
Orchestrator-ът compose-ва task prompt string и spawn-ва generic subagent. Няма type system — всеки subagent е "blank slate" с injected prompt.

### Claude Code подход
Дефинираме custom agent `.claude/agents/workflow-step/AGENT.md`:

```yaml
---
name: workflow-step
description: Execute a single workflow step with structural gate validation
model: inherit
tools: Read, Write, Edit, Bash, Glob, Grep
maxTurns: 100
---

You are executing a single step in a multi-step workflow.
Follow the goal precisely. Write outputs to the specified paths.
Do not modify engine infrastructure files.
```

AGENT.md подчертава: "Follow struct schemas exactly" — когато goal-ът включва "Output schemas" секция, agent-ът ТРЯБВА да пише в правилния формат (JSON/YAML/Markdown) и да спазва required fields. Това е свързано с inline schema injection (виж долу).

Orchestrator-ът spawn-ва с: `Agent tool → subagent_type: "workflow-step"`.

### Защо е по-добре
- **Explicit tool restrictions:** `tools` field в AGENT.md ограничава какво може agent-ът. В Cursor — всичко е достъпно.
- **maxTurns:** Естествен retry limit без external counting.
- **System prompt separation:** Agent-ът има базов system prompt. Orchestrator-ът добавя goal като user message. По-чист от single-prompt injection.
- **Matcher integration:** `agent_type: "workflow-step"` автоматично match-ва SubagentStop hook-а.

---

## 3a. Inline Schema Injection

### Проблем
Агентът получаваше само path към schema файла в natural language text ("`read <path>`"). Не винаги го четеше — пишеше `.txt` вместо `.json`, пропускаше required fields.

### Решение
`step_begin` чете schema файловете и ги embed-ва **inline** в `outputs_text`. Агентът вижда пълната schema структура директно в prompt-а:

```
**Write outputs to:**
- `.agent/workflows/hook-diagnostic/data/diagnostic-output.json` — **JSON** file, struct: `diagnostic-output`

**Output schemas — your output MUST match these exactly:**

**Struct `diagnostic-output`** (output: `data/diagnostic-output.json`):
\```yaml
name: diagnostic-output
type: object
required: [status, timestamp]
properties:
  status: {type: string}
  timestamp: {type: string}
\```
Write as **JSON** matching this schema exactly.
```

### Допълнителни мерки
- `output_schemas` field в `step_begin` response — structured metadata (path, struct, format, content)
- AGENT.md подчертава: "Follow struct schemas exactly, write to the exact file path"
- Форматът се извежда от файловото разширение (`.json` → JSON, `.yaml` → YAML, `.md` → Markdown)

---

## 4. Trace Capture (Per-Step Metrics)

### Проблем
Нужни са метрики: duration, message_count, tool_call_count, modified_files, model. За trace viewer и debugging.

### Cursor подход
Hook payload съдържа pre-computed полета: `duration_ms`, `message_count`, `tool_call_count`, `modified_files`, `model`. Gate-check.py ги записва директно в trace.

### Claude Code подход
SubagentStop payload съдържа `agent_transcript_path` — пълен JSONL transcript. Парсваме го:

```python
def parse_transcript(path):
    entries = [json.loads(line) for line in open(path)]
    started = entries[0].get("timestamp")
    ended = entries[-1].get("timestamp")
    messages = sum(1 for e in entries if e.get("role") == "assistant")
    tool_calls = sum(1 for e in entries if e.get("type") == "tool_use")
    modified = extract_modified_files(entries)  # from Edit/Write tool inputs
    model = extract_model(entries)  # from API response metadata
    tokens = extract_token_usage(entries)  # input/output tokens
    return { "duration_ms": ..., "message_count": messages, ... }
```

### Защо е по-добре
- **Повече данни:** Token usage, individual tool durations, full conversation flow.
- **По-точни данни:** Изчислени от raw transcript, не от host estimates.
- **Extensible:** Можем да добавим нови метрики без host зависимост.
- **Debugging:** Transcript path в trace-а позволява deep dive.

---

## 5. Workflow Orchestration (MCP vs Direct)

### Проблем
Orchestrator-ът трябва да управлява manifest, trace, step sequencing, param bindings. В Cursor това беше бавно чрез manual file I/O.

### Cursor подход
MCP server (`workflow-engine.py`) с 7 tools. SKILL.md извиква MCP tools. Намали startup от 30s на 5s.

### Claude Code подход — **три варианта за оценка:**

**Вариант A: Запазване на MCP server**
- Claude Code поддържа stdio MCP. Регистрираме в `.mcp.json`.
- SKILL.md извиква `mcp__workflow_engine__*` tools.
- Плюс: Минимални промени. Минус: Допълнителна зависимост.

**Вариант B: `!`command`` preprocessing в SKILL.md**
- Skills поддържат shell command injection: `` !`python .agent/scripts/workflow-helper.py init ...` ``
- Preprocessing зарежда state преди Claude да види skill-а.
- Плюс: Няма MCP dependency. Минус: Preprocessing е one-shot, не interactive.

**Вариант C: Direct file I/O чрез Bash tool**
- SKILL.md инструктира Claude да чете/пише manifest, trace директно.
- Плюс: Нулева зависимост. Минус: По-бавно, повече LLM turns.

### Решение: Вариант A (MCP) за v1
- Claude Code поддържа MCP нативно. workflow-engine.py работи без промени.
- Ако performance е проблем — преминаваме към hybrid (MCP + `!`command``).
- Вариант C е fallback ако MCP не работи.

---

## 6. Rules (Always-Active Enforcement)

### Проблем
Spec Guard трябва да проверява specs преди всеки code change. Workflow context трябва да е наличен при работа с .agent/ файлове.

### Cursor подход
`.cursor/rules/spec-guard.mdc` с `alwaysApply: true`. MDC формат с glob patterns.

### Claude Code подход
`.claude/rules/spec-guard.md` — Markdown без frontmatter = loaded at session start (same as alwaysApply).

За workflow-context: `.claude/rules/workflow-context.md` с paths frontmatter:
```yaml
---
paths:
  - ".agent/**/*"
---
```
Зарежда се само когато Claude чете файлове от .agent/.

### Защо е по-добре
- **Conditional loading:** `paths` frontmatter зарежда context rule САМО при нужда. Cursor зарежда ВСИЧКИ alwaysApply rules винаги.
- **Standard Markdown:** Няма MDC формат — чист Markdown.

---

## 7. Skills (Slash Commands)

### Проблем
Потребителят извиква workflows чрез `/run-workflow`, `/spec-fast`, и др.

### Cursor подход
`.cursor/skills/*/SKILL.md`. Frontmatter: минимален (без context/agent/allowed-tools в повечето).

### Claude Code подход
`.claude/skills/*/SKILL.md`. Почти идентичен формат, с допълнителни възможности:
- `context: fork` — за read-only skills (learn-workflows, spec-audit-fast)
- `allowed-tools` — ограничаване на tools per skill
- `disable-model-invocation: true` — за destructive skills (deploy, commit)
- `$ARGUMENTS`, `$0`, `$1` — по-мощен argument parsing
- `${CLAUDE_SKILL_DIR}` — reference към skill directory

### Портиране
12 от 13 skills се портират с минимални промени (frontmatter adaptation). Само `/run-workflow` изисква значителна работа (gate protocol, MCP vs direct).

---

## 8. Subagent Nesting Constraint

### Проблем
Orchestrator-ът трябва да spawn-ва step subagents. Но ако orchestrator-ът е subagent (context: fork), не може да spawn-ва други.

### Claude Code ограничение
"Subagents cannot spawn other subagents."

### Решение
`/run-workflow` skill НЕ използва `context: fork`. Работи inline в main conversation context. Може да spawn-ва Agent tool за стъпки.

Това е **същият** подход като в Cursor — orchestrator-ът работи inline.

---

## 9. File Protection

### Проблем
Step subagents не трябва да модифицират engine файлове (.agent/scripts/, .agent/docs/, .cursor/, и др.).

### Cursor подход
Text в SKILL.md: "Never modify these files: ..." Soft enforcement — разчита на LLM compliance.

### Claude Code подход
Custom agent с `hooks` в frontmatter:

```yaml
---
name: workflow-step
hooks:
  PreToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "python .agent/scripts/file-guard.py"
---
```

`file-guard.py` проверява дали target path е protected и exit 2 ако да.

### Защо е по-добре
- **Deterministic:** Script проверява, не LLM. Невъзможно да се заобиколи.
- **Scoped:** Hook-ът е само за workflow-step agent, не за main conversation.

---

## 10. Hook Configuration

### Cursor подход
```json
// .cursor/hooks.json
{
  "version": 1,
  "hooks": {
    "subagentStop": [{ "command": "python .agent/scripts/gate-check.py", "loop_limit": 25 }]
  }
}
```

### Claude Code подход
```json
// .claude/settings.json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "workflow-step",
        "hooks": [
          { "type": "command", "command": "python .agent/scripts/gate-check.py", "timeout": 60 }
        ]
      }
    ]
  }
}
```

### Разлики
- `SubagentStop` (PascalCase) вместо `subagentStop` (camelCase)
- `matcher` field за agent type filtering (няма нужда от run_token)
- `timeout` вместо `loop_limit` (Claude Code не има loop_limit — retry-ите се контролират от exit codes)
- Nested `hooks` array вместо flat object

---

## 11. MCP Server Registration

### Cursor подход
```json
// .cursor/mcp.json
{ "mcpServers": { "workflow_engine": { "command": "python", "args": [".agent/mcp/workflow-engine.py"] } } }
```

### Claude Code подход
```json
// .mcp.json (project root) или .claude/.mcp.json
{ "mcpServers": { "workflow_engine": { "type": "stdio", "command": "python", "args": [".agent/mcp/workflow-engine.py"] } } }
```

### Разлика
- `type: "stdio"` е explicit (Cursor го infer-ва)
- File location: `.mcp.json` в project root (shared) или `.claude/.mcp.json`

---

## 12. Adapter File Structure

### Cursor
```
.cursor/
├── hooks.json
├── mcp.json
├── rules/
│   ├── spec-guard.mdc
│   └── workflow-context.mdc
└── skills/
    ├── run-workflow/SKILL.md
    ├── spec-fast/SKILL.md
    └── ... (13 total)
```

### Claude Code
```
.claude/
├── settings.json          ← hooks config (вместо hooks.json)
├── rules/
│   ├── spec-guard.md      ← Markdown (вместо MDC)
│   └── workflow-context.md
├── skills/
│   ├── run-workflow/SKILL.md
│   ├── spec-fast/SKILL.md
│   └── ... (13 total)
└── agents/
    └── workflow-step/AGENT.md  ← НОВА: custom agent дефиниция

.mcp.json                  ← MCP config (project root, вместо .cursor/mcp.json)
```

---

## Обобщение: Cursor → Claude Code mapping

| # | Аспект | Cursor | Claude Code | Подобрение |
|---|--------|--------|-------------|------------|
| 1 | Gate retry | followup_message JSON | exit 2 + stderr | По-интуитивно |
| 2 | Phantom filter | 3 custom checks в Python | matcher: "workflow-step" | Declarative, 0 код |
| 3 | Step agents | Generic subagent + prompt | Custom AGENT.md | Tool restrictions, maxTurns |
| 4 | Trace metrics | Pre-computed от host | Parsed от transcript JSONL | Повече данни, по-точни |
| 5 | MCP | .cursor/mcp.json | .mcp.json | Същият, portable |
| 6 | Rules | .mdc format | .md с paths frontmatter | Conditional loading |
| 7 | Skills | SKILL.md | SKILL.md + advanced features | !`cmd`, $ARGS, context:fork |
| 8 | Nesting | Inline orchestrator | Inline orchestrator | Същият подход |
| 9 | File protection | LLM instructions | PreToolUse hook + script | Deterministic |
| 10 | Hook config | hooks.json | settings.json hooks | Matcher filtering |
