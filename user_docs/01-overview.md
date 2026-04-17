# 01 — Overview

## Какво е Agentic Control Plane?

Система от два компонента за управление на LLM-driven разработка:

1. **Workflow Engine** — декларативна система за multi-phase LLM workflows. Описваш workflow в YAML (стъпки, inputs, outputs, gates), engine-ът управлява execution, state tracking, validation и resume.

2. **Spec Guard** — система за enforcement на behavioral specifications. Spec-ове описват изисквания за поведение на компоненти. Always-active rule + workflows гарантират, че LLM-ът ги зачита при code changes.

Системата е **tool-agnostic** по дизайн. `workflow.yaml` описва *какво* да се направи. Tool-specific adapter (Cursor, Claude Code) решава *как*. Аналогията е **Dockerfile vs Docker runtime**.

---

## Архитектура

Три слоя:

```
 ┌────────────────────────────────────────────────────────┐
 │                 EXECUTION LAYER                        │
 │                                                        │
 │   Orchestrator ──spawn──► Subagent (Step 1)            │
 │       │         ──spawn──► Subagent (Step 2)           │
 │       │         ──spawn──► Subagent (Step N)           │
 │       │                                                │
 ├───────┼────────────────────────────────────────────────┤
 │       │         INTEGRATION LAYER (.cursor/)           │
 │       │                                                │
 │   skills/          hooks.json        rules/            │
 │   run-workflow     subagentStop →    spec-guard.mdc    │
 │   spec             gate-check.py    workflow-context   │
 │   learn-workflows                                      │
 │                                                        │
 ├────────────────────────────────────────────────────────┤
 │                 DATA LAYER (.agent/)                   │
 │                                                        │
 │   workflows/       specs/          docs/               │
 │   ├─ predefined/   ├─ _index.json  ├─ overview.md      │
 │   ├─ my-workflow/  ├─ _registry    ├─ workflow-yaml.md │
 │   │  ├─ yaml       ├─ {domain}/    ├─ structs.md       │
 │   │  ├─ manifest   scripts/        ├─ manifest.md      │
 │   │  ├─ structs/   ├─ gate-check   ├─ specs.md         │
 │   │  ├─ context/   ├─ schema-val   └─ trace.md         │
 │   │  └─ trace/                                         │
 │   tools/                                               │
 │   ├─ trace-viewer.html                                 │
 │   └─ workflow-editor.html                              │
 └────────────────────────────────────────────────────────┘
```

### Data Layer (`.agent/`)

Всичко, което **не зависи от конкретен инструмент** — workflow дефиниции, runtime state, schemas, validation scripts, LLM docs (English).

- `workflows/templates/predefined/` — built-in workflows (read-only, shipped with engine)
- `workflows/templates/my_workflows/` — потребителски workflow дефиниции (yaml, structs)
- `workflows/<name>/` — runtime instances (manifest, data, context, trace — auto-generated per run)
- `specs/` — behavioral specifications
- `scripts/` — gate validation scripts (Python)
- `mcp/` — MCP server (`workflow-engine.py`)
- `docs/` — LLM-consumable documentation (English)
- `tools/` — browser-based utilities (trace viewer, workflow editor)

### Integration Layer (`.cursor/` или `.claude/`)

Tool-specific adapter. За Cursor:
- `skills/` — entry points (`/run-workflow`, `/spec`, `/spec-with-workflows`, `/learn-workflows`)
- `hooks.json` — `subagentStop` hook за gate triggers
- `rules/` — `spec-guard.mdc` (always-active), `workflow-context.mdc`

### Execution Layer

LLM агенти:
- **Orchestrator** — main agent, чете workflow.yaml, управлява transitions, обновява manifest
- **Subagents** — изпълняват отделни стъпки в изолиран, чист контекст

---

## `.agent/` vs `.cursor/` разделение

| | `.agent/` (Data) | `.cursor/` (Adapter) |
|---|---|---|
| **Съдържание** | Workflows, specs, scripts, docs, tools | Skills, hooks, rules |
| **Tool-agnostic** | Да | Не — Cursor-specific |
| **Портативност** | Преносимо между инструменти | Заменя се при смяна на tool |
| **Кой го пише** | Потребителят + engine | Engine (install.py) |

```
Инструмент    Skill            Hooks              Rules
─────────────────────────────────────────────────────────
Cursor        .cursor/skills/  .cursor/hooks.json  .cursor/rules/
Claude Code   .claude/skills/  .claude/settings    CLAUDE.md
Antigravity   .agent/skills/   Built-in RDD        .agents/rules/
```

---

## Инсталация

```bash
python path/to/install.py <target-project-dir> [--update] [--dry-run]
```

**По подразбиране (Phase 38) install.py инсталира И ДВАТА адаптера** — Cursor (`.cursor/`) и Claude Code (`.claude/` + `.mcp.json`). Един run прави пълен setup.

Изпълнявани стъпки:

**Universal layer (един път, независимо от адаптерите):**
1. `[1/6]` Engine documentation → `.agent/docs/`
2. `[2/6]` Gate scripts → `.agent/scripts/`
3. `[3/6]` MCP servers → `.agent/mcp/` (включва workflow-engine.py + workflow-tools-loader.py)
4. `[4/6]` Workflow templates → `.agent/workflows/templates/`
5. `[5/6]` Behavioral specs → `.agent/specs/` (template-и + user-data файлове, които никога не се overwrite-ват)
6. `[6/6]` Tools → `.agent/tools/`

**За всеки адаптер (Cursor, после Claude Code) — пет стъпки:**
1. `[1/5]` Skills → `.cursor/skills/` или `.claude/skills/`
2. `[2/5]` Hooks → `.cursor/hooks.json` (merge) или `.claude/settings.json`
3. `[3/5]` MCP server config → `.cursor/mcp.json` или `.mcp.json` (merge)
4. `[4/5]` Rules → `.cursor/rules/` или `.claude/rules/`
5. `[5/5]` Agents → `.claude/agents/` (CC only — Cursor няма subagent files). За Claude Code се изпълнява автоматично `update-workflows.py`, който генерира per-step subagent файлове за всички shipped workflows.

**Флагове:**

| Flag | Значение |
|------|----------|
| (no flag) | **Default** — инсталира двата адаптера |
| `--cursor` | Само Cursor (без `.claude/`, без `.mcp.json`) |
| `--claude` | Само Claude Code (без `.cursor/`) |
| `--update` | Smart update mode — overwrite-ва само файлове с различен content. Не пипа потребителски workflows и user-data в `.agent/specs/` |
| `--force` | **Destructive** — overwrite-ва всичко, включително merged hooks/mcp configs |
| `--prune` | Само с `--update` — изтрива файлове в target, които вече не съществуват в source |
| `--dry-run` | Само с `--update` — preview без да пише нищо |

**Примери:**

```bash
# Default — двата адаптера
python install.py /path/to/project

# Само Cursor
python install.py /path/to/project --cursor

# Само Claude Code
python install.py /path/to/project --claude

# Smart update след нов release
python install.py /path/to/project --update

# Preview какво ще се промени
python install.py /path/to/project --update --dry-run
```

**След install:**
- За Cursor: рестартирай Cursor IDE-то, за да picks up MCP servers и rules.
- За Claude Code: рестартирай CC сесията, за да индексира `.claude/agents/<workflow>-<step>/` per-step subagent типове, които install-ът току-що генерира.

---

## Файлова структура (пълна)

```
.agent/
├── docs/                                  # Engine documentation (English, LLM-consumable)
│   ├── overview.md
│   ├── workflow-yaml.md
│   ├── structs.md
│   ├── manifest.md
│   ├── specs.md
│   └── trace.md
│
├── mcp/                                   # MCP server (Model Context Protocol)
│   └── workflow-engine.py                 # Workflow orchestration tools via MCP
│
├── scripts/
│   ├── gate-check.py                      # Structural gate validation
│   └── schema-validate.py                 # Schema validation
│
├── specs/                                 # Behavioral specifications
│   ├── _index.json                        # Registry of all specs
│   ├── _registry.json                     # Implementation mapping
│   └── {domain}/
│       └── ComponentName.md
│
├── tools/
│   ├── trace-viewer.html                  # Trace visualization
│   └── workflow-editor.html               # Workflow YAML editor
│
└── workflows/
    ├── templates/
    │   ├── predefined/                    # Built-in (read-only)
    │   │   ├── spec-write/
    │   │   ├── spec-write-and-implement/
    │   │   ├── spec-enforcement/
    │   │   ├── spec-audit/
    │   │   ├── doc-spec-extraction/
    │   │   ├── create-workflow/
    │   │   ├── registry-sync/
    │   │   └── hook-diagnostic/
    │   │
    │   └── my_workflows/                  # User-created definitions
    │       └── <workflow-name>/
    │           ├── workflow.yaml
    │           └── structs/
    │
    └── <workflow-name>/                   # Runtime instances (auto-generated)
        ├── manifest.json
        ├── gate-result.json
        ├── data/
        ├── context/
        └── trace/

.cursor/
├── skills/
│   ├── run-workflow/SKILL.md              # /run-workflow
│   ├── learn-workflows/SKILL.md           # /learn-workflows
│   ├── spec/SKILL.md                      # /spec (list, show)
│   ├── spec-with-workflows/SKILL.md       # /spec-with-workflows (add, audit → workflows)
│   ├── run-workflow-for-code-spec/SKILL.md # /run-workflow-for-code-spec
│   ├── spec-fast/SKILL.md                 # /spec-fast (бърз spec + implement)
│   ├── code-spec-fast/SKILL.md            # /code-spec-fast (бърз code с enforcement)
│   ├── spec-add-fast/SKILL.md             # /spec-add-fast (бърз spec без implement)
│   └── spec-audit-fast/SKILL.md           # /spec-audit-fast (бърз audit)
├── hooks.json
├── mcp.json                               # MCP server registration
└── rules/
    ├── workflow-context.mdc
    └── spec-guard.mdc
```

---

## Quick Start

1. Инсталирай: `python install.py`
2. Научи LLM-а: `/learn-workflows` (чете `.agent/docs/`)
3. Създай workflow: `/run-workflow create-workflow`
4. Стартирай: `/run-workflow my-workflow --param value`
5. Виж trace: отвори `trace-viewer.html` и drop-ни `.trace.json`

За specs:
1. Добави spec: `[spec::EditField] character limit 30`
2. Виж spec: `/spec show EditField`
3. Одитирай: `/spec-with-workflows audit` или `/spec-audit-fast`
