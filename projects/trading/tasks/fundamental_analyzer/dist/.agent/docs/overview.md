# Agentic Control Plane — Overview

The Agentic Control Plane is a system for managing LLM-driven development. It has two components:

1. **Workflow Engine** — A declarative system for defining and executing multi-phase LLM-driven tasks. You describe your workflow in a YAML file — steps, inputs, outputs, gates — and the engine handles execution, state tracking, validation, and resume.

2. **Spec Guard** — A behavioral specification enforcement system. Specs in `.agent/specs/` capture component requirements that the LLM must respect during every code change. An always-active rule enforces compliance; the `/spec` and `/spec-with-workflows` skills manage the spec lifecycle.

## Key Concepts

| Concept | What it is |
|---------|-----------|
| **Workflow** | A YAML file (`workflow.yaml`) describing a sequence of steps |
| **Step** | A unit of work executed by an isolated subagent |
| **Manifest** | Auto-generated JSON (`manifest.json`) tracking runtime state |
| **Struct** | A schema (`.schema.yaml`) defining expected format for inputs/outputs |
| **Gate** | Validation between steps — structural (script), semantic (LLM), human (optional) |
| **Context** | Summaries from previous steps, carried forward to the next |
| **Spec** | A behavioral specification in `.agent/specs/` — requirements a component must satisfy |
| **Tools** | Workflow-declared tool dependencies — script proxies and MCP server refs |
| **Spec Guard** | Always-active enforcement — LLM checks specs before code changes |

## How It Works

1. User invokes `/run-workflow <name>` (or `/run-workflow <name> --resume`)
2. Orchestrator calls MCP tools to resolve the workflow and create/resume manifest
3. For each step (sequentially):
   a. Calls `step_begin` MCP tool → gets pre-composed text blocks for subagent task
   b. **If `subagent: true`** (default): spawns a subagent with goal + input files + summaries from previous steps. **If `subagent: false`**: orchestrator executes the goal inline (no subagent spawn, no gate hook).
   c. Subagent/orchestrator executes the goal, writes outputs
   d. **Structural gate**: For `subagent: true` steps, `gate-check.py` runs via `subagentStop` hook (automatic, deterministic). For `subagent: false` steps, `step_complete` validates outputs against struct schemas before accepting the step — if validation fails, it returns an error and the orchestrator must fix outputs and retry.
      - On **fail**: `gate-check.py` returns `followup_message` → subagent retries in-place (same session, up to `max_gate_retries`)
      - On **pass**: `gate-check.py` returns `{}` → subagent **stops** → control returns to orchestrator
   e. Orchestrator calls `step_collect_result` → reads `gate-result.json` (for subagent steps), handles **semantic gate** (LLM check) and **human gate** (optional approval)
   f. On pass: calls `step_complete` → updates manifest, writes summary to `context/`, applies param_bindings
   g. If gate retries exhausted: orchestrator re-spawns up to `max_step_retries` (default: 3), then **workflow STOPS**
   h. **On gate not executing** (script crash, hook not firing — for `subagent: true` steps only): **workflow STOPS immediately.** A gate that doesn't run is worse than a gate that fails.
4. Workflow completes when all steps pass → orchestrator calls `workflow_finalize`

## File Structure

```
.agent/
├── docs/                        # This documentation (you're reading it)
│   ├── overview.md              # System overview (this file)
│   ├── workflow-yaml.md         # workflow.yaml format reference
│   ├── structs.md               # Struct schema format reference
│   ├── manifest.md              # manifest.json format reference
│   ├── specs.md                 # Behavioral spec format reference
│   └── trace.md                 # Trace system format reference
│
├── mcp/                         # MCP servers (Model Context Protocol)
│   ├── workflow-engine.py       # Provides workflow orchestration tools via MCP
│   └── workflow-tools-loader.py # Stable MCP server exposing all script tools (Phase 38)
│
├── scripts/                     # Generic engine scripts
│   ├── gate-check.py            # Structural gate — called by subagentStop hook
│   ├── schema-validate.py       # File-vs-schema validator
│   ├── init-workflow.py         # Generates per-step subagent files for one workflow
│   ├── update-workflows.py      # Bulk sync of all workflows' subagent files
│   └── workflow-tool-validator.py  # PreToolUse hook for script tool input schema validation
│
├── gate-check-invocations.log   # Prolog/epilog log — confirms hook was invoked (auto-generated)
├── gate-check-error.log         # Error log — diagnostics when gate-check.py fails (auto-generated)
├── *.lock                       # Lock files created by gate-check.py for concurrent write safety (can be gitignored)
│
├── tools/                       # Human-facing utilities
│   ├── trace-viewer.html        # Browser-based workflow trace viewer
│   ├── workflow-editor.html     # Browser-based workflow YAML editor
│   └── audit-viewer.html       # Browser-based spec-audit report viewer (for spec-audit workflow)
│
├── specs/                       # Behavioral specifications (Spec Guard)
│   ├── _index.json              # Registry of all specs
│   ├── _registry.json           # Implementation mapping (files → specs)
│   └── {domain}/                # Per-domain spec files
│       └── ComponentName.md     # Individual spec (YAML frontmatter + Markdown)
│
└── workflows/
    ├── templates/
    │   ├── predefined/              # Built-in workflows (read-only, shipped with engine)
    │   │   ├── spec-write/
    │   │   │   ├── workflow.yaml    # DISCOVER → CLARIFY → WRITE-SPEC → REGISTER-SPEC
    │   │   │   └── structs/
    │   │   ├── spec-write-and-implement/
    │   │   │   └── workflow.yaml    # delegate_to: spec-write → delegate_to: spec-enforcement
    │   │   ├── spec-enforcement/
    │   │   │   ├── workflow.yaml
    │   │   │   └── structs/
    │   │   ├── doc-spec-extraction/
    │   │   │   ├── workflow.yaml
    │   │   │   └── structs/
    │   │   ├── create-workflow/
    │   │   │   ├── workflow.yaml
    │   │   │   └── structs/
    │   │   ├── registry-sync/
    │   │   │   ├── workflow.yaml
    │   │   │   └── structs/
    │   │   ├── spec-audit/
    │   │   │   ├── workflow.yaml
    │   │   │   └── structs/
    │   │   └── hook-diagnostic/
    │   │       ├── workflow.yaml
    │   │       └── structs/
    │   │
    │   └── my_workflows/            # User-created workflows
    │       └── <workflow-name>/
    │           ├── workflow.yaml     # Definition (user writes)
    │           └── structs/          # I/O schemas (user writes)
    │               └── <name>.schema.yaml
    │
    └── <workflow-name>/             # Runtime instances (auto-generated per run)
        ├── manifest.json            # Runtime state
        ├── gate-result.json         # Last gate check result
        ├── data/                    # Step output data
        ├── context/                 # Step summaries
        │   └── <step>.summary.md
        └── trace/                   # Execution traces
            └── <run-id>.trace.json
```

## Execution Model

**Steps are always sequential.** Step B does not start until Step A completes AND passes the gate. The workflow is a pipeline.

**Parallelism is within a step.** When a step has `parallel: true`, it fans out into N subagents (determined by `parallel_key`). All N run concurrently, but the step is not "complete" until ALL finish and pass the gate.

```
Step 1 (plan)    → GATE ✓ → Step 2 (extract)              → GATE ✓ → Step 3
  [1 subagent]               [subagent: domain-A]                     ...
                              [subagent: domain-B] concurrent
                              [subagent: domain-C]
                              ... all finish → GATE
```

## Spec Guard

Spec Guard enforces behavioral specifications during code changes. It works through four mechanisms:

1. **Always-active rule** (`.cursor/rules/spec-guard.mdc`) — Instructs the LLM to check `.agent/specs/` before modifying code. If a change would violate a spec, the LLM warns the user. This is "soft" enforcement — always present, low friction.

2. **`spec_check` in workflow steps** — Every workflow step has a `spec_check` field (default: `true`). When enabled, the orchestrator adds explicit spec-checking instructions to the subagent's task: read `_registry.json`, find affected specs, verify no violations. This is "hard" enforcement — integrated into the workflow engine. Set `spec_check: false` for steps that don't modify source code.

3. **`/spec` skill** — Views specs: `list`, `show`. **`/spec-with-workflows` skill** — Creates and audits specs via workflow engine: `add` (delegates to `spec-write`), `audit` (delegates to `spec-audit`). The `add` command includes an interactive CLARIFY step where the LLM refines requirements with the user before writing the spec.

4. **`[spec::ComponentName]` pattern** — When the user types this in chat, the always-active rule instructs the LLM to invoke `/run-workflow spec-write-and-implement` for the full spec + implementation pipeline.

### Spec Format

Specs are Markdown files with YAML frontmatter, stored in `.agent/specs/{domain}/`:

```
.agent/specs/
├── _index.json           # All specs metadata
├── _registry.json        # Which files implement which specs
├── ui/
│   └── EditField.md      # Behavioral spec for EditField component
└── messaging/
    └── MessageQueue.md   # Behavioral spec for MessageQueue
```

Each spec has: `spec_id`, `component`, `domain`, `status`, requirements with severity levels (MUST/SHOULD/MAY), constraints, examples, and source changelog. See [specs.md](specs.md) for the full format reference.

### Implementation Mapping

`_registry.json` tracks which source files implement which specs — both direct implementations and indirect dependencies (imports, styles, configs, tests). Each entry has a `relationship` type so Spec Guard knows how the file relates to the spec. Maintained by `spec-enforcement` (REGISTER step) and `registry-sync` workflows:

```json
{
  "version": 2,
  "updated_at": "2026-03-13T14:00:00+02:00",
  "mappings": {
    "EditField": {
      "spec": "specs/ui/EditField.md",
      "implemented_by": [
        { "file": "src/components/EditField.tsx", "relationship": "direct" },
        { "file": "src/validation/fieldRules.ts", "relationship": "imports" },
        { "file": "src/styles/EditField.module.css", "relationship": "style" }
      ],
      "last_verified": "2026-03-13",
      "verified_by": "spec-enforcement"
    }
  }
}
```

Relationship types: `direct` (primary implementation), `imports` (imported module with spec logic), `imported_by` (consumer of the component), `style` (CSS/SCSS), `config` (constants/i18n), `test` (test files). See [specs.md](specs.md) for details.

## Predefined Workflows

The engine ships with built-in workflows in `.agent/workflows/templates/predefined/`. These are generic, reusable workflows that work with any project:

| Workflow | Purpose |
|----------|---------|
| `spec-write` | Create/update a spec without implementation (DISCOVER → CLARIFY → WRITE-SPEC → REGISTER-SPEC) |
| `spec-write-and-implement` | Delegate to `spec-write` then `spec-enforcement` — full pipeline from spec to code |
| `spec-enforcement` | Implement code with spec checking (CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER) |
| `doc-spec-extraction` | Extract specs from documentation (ANALYZE → EXTRACT → VALIDATE → COMMIT) |
| `create-workflow` | Interactive workflow creation assistant (LEARN → DISCUSS → CREATE) |
| `registry-sync` | Discover unregistered spec implementations, sync `_registry.json` (SCAN → REVIEW → REGISTER) |
| `spec-audit` | Read-only QA compliance audit — scan code against specs, report violations (DISCOVER → SCAN → REPORT) |
| `hook-diagnostic` | 3-step diagnostic — tests hook firing, struct validation, and retry loop |

`spec-write-and-implement` is a **composition workflow** — it has no inline steps. It delegates to `spec-write` (DISCOVER → CLARIFY → WRITE-SPEC → REGISTER-SPEC), then to `spec-enforcement` (CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER). Both are standalone workflows that can also be invoked directly. `spec-write` is also used by `/spec-with-workflows add`.

`spec-enforcement` supports two modes:
- **Targeted** (with `component`): enforces a specific component's spec
- **Auto-discovery** (without `component`): analyzes the instruction to find all affected specs via `_registry.json`

```
spec-write-and-implement:
  WRITE ─── delegate_to ──→  spec-write:
                                DISCOVER
                                CLARIFY (human gate)
                                WRITE-SPEC
                                REGISTER-SPEC

  ENFORCE ── delegate_to ──→  spec-enforcement:
                                CHECK-SPECS
                                IMPLEMENT
                                VERIFY
                                REGISTER
```

User-created workflows go in `.agent/workflows/templates/my_workflows/`. Predefined workflows in `templates/predefined/` are read-only — they are part of the engine distribution.

### Workflow Resolution Order

When `/run-workflow <name>` is invoked, the orchestrator searches for the workflow definition in this order:

1. `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` — user-defined (takes priority)
2. `.agent/workflows/templates/predefined/<name>/workflow.yaml` — built-in (fallback)
3. `.agent/workflows/<name>/workflow.yaml` — runtime dir (legacy)

If not found in any location, an error is reported.

### Runtime State for Predefined Workflows

Predefined workflow definitions in `templates/predefined/` are **read-only**. Runtime state (manifest, context, data) is generated in a separate directory at `workflows/<name>/` (not inside `templates/`):

```
.agent/workflows/
├── templates/
│   └── predefined/
│       └── spec-write-and-implement/
│           ├── workflow.yaml        # Definition (read-only, shipped with engine)
│           └── structs/             # Schemas (read-only)
│
└── spec-write-and-implement/        # Runtime instance (auto-generated per run)
    ├── manifest.json
    ├── gate-result.json
    ├── data/                        # Step output data
    └── context/                     # Step summaries
```

### How Predefined Workflows Are Triggered

There are five ways to run a predefined workflow:

**1. Via `[spec::X]` pattern (most natural):**
User types `[spec::EditField] character limit 30, show red error`. The always-active rule instructs the LLM to invoke `/run-workflow spec-write-and-implement --component EditField --requirements "..."`. This runs the full pipeline: spec creation + implementation.

**2. Via `/spec-with-workflows add` skill (spec only, no implementation):**
User runs `/spec-with-workflows add EditField`. The skill delegates to `/run-workflow spec-write` — creates/updates the spec with gates and manifest, but does NOT implement it in code.

**3. Via `/run-workflow-for-code-spec` (implement with enforcement, full workflow):**
User runs `/run-workflow-for-code-spec EditField "add max length validation"`. This invokes `spec-enforcement` workflow directly — no new spec is created. Full pipeline with manifest, trace, and gates.

**4. Via fast skills (lightweight, no workflow overhead):**
- `/spec-fast EditField "requirements"` — write/update spec + implement in code (inline, ~1-2 min)
- `/code-spec-fast EditField "instruction"` — code change with spec enforcement (inline, ~1-2 min)
- `/spec-add-fast EditField "requirements"` — write/update spec only, no code changes (inline)

Fast skills do the same logical work as workflows but without manifest, trace, gates, or subagents. Use for everyday tasks. Use full workflows for bulk operations or when audit trail is needed.

**5. Via `/run-workflow` (direct):**
User runs `/run-workflow spec-write-and-implement --component EditField --domain ui`. The orchestrator finds the definition in `templates/predefined/` and runs it.

**6. Via delegation from another workflow:**
A parent workflow step has `delegate_to: spec-write-and-implement`. The orchestrator reads the predefined workflow definition and executes its steps sequentially in the same session, with a separate manifest in a sibling directory.

## Workflow Delegation

A workflow can delegate to another workflow using `delegate_to:`. The orchestrator reads the target workflow definition (searching `templates/my_workflows/<name>/` then `templates/predefined/<name>/`), creates a separate manifest in a sibling directory (`.agent/workflows/<delegated-name>/`), and runs all its steps sequentially (each step spawns its own subagent). When complete, control returns to the parent workflow. This enables workflow composition without duplicating steps.

**Important:** Delegation is NOT a subagent spawn — the orchestrator executes the delegated workflow directly. This avoids nested subagent limitations.

See [workflow-yaml.md](workflow-yaml.md) for the `delegate_to` reference.

## Param Bindings

Steps can update workflow params based on their output using `param_bindings`. This is critical for auto-discovery flows where early steps determine values (e.g., component name) that subsequent steps need. After a step passes its gate, the orchestrator reads specified fields from output files and updates `manifest.params` for all downstream steps.

**Delegation steps can also have `param_bindings`.** When a delegation step has bindings, the file paths resolve relative to the **delegated** workflow's runtime directory (where the output files were written), not the parent's. This enables param propagation across delegation boundaries — e.g., `spec-write-and-implement` delegates to `spec-write`, which discovers `component`/`domain` in its CLARIFY step. After delegation completes, the parent reads the values from `spec-write`'s output and uses them for the next delegation (`spec-enforcement`).

See [workflow-yaml.md](workflow-yaml.md) for the full `param_bindings` reference.

## MCP Server (Workflow Orchestration Tools)

The workflow engine provides an MCP (Model Context Protocol) server at `.agent/mcp/workflow-engine.py`. Registered via `.cursor/mcp.json` (Cursor) or `.mcp.json` (Claude Code / generic). The IDE spawns it automatically as a child process. Tools appear as `mcp__workflow_engine__<tool>`.

**Why MCP?** Without MCP, the orchestrator reads a 400+ line SKILL.md, then manually creates manifest.json, trace files, and composes subagent tasks via file tools (~30-60 seconds of overhead). With MCP, each operation is a single tool call (~2-5 seconds total).

### Tools

| Tool | Purpose |
|------|---------|
| `workflow_resolve` | Find workflow definition, return metadata (steps, params, gates) |
| `workflow_init` | Create manifest + trace + run_token, generate tools proxy, check availability |
| `workflow_resume` | Resume from existing manifest |
| `step_begin` | Prepare step: returns pre-composed text blocks (goal, constraints, spec_check, run_token) + `tools_info` for AGENT.md injection. Also returns `model` hint if defined in workflow.yaml. For delegation steps, returns delegation metadata. |
| `step_collect_result` | Read gate-result.json, determine next action (PROCEED / RETRY / STOP) |
| `step_complete` | Mark step done, write summary, apply param_bindings, advance to next step. **Safety net:** validates outputs against struct schemas when the gate hook did not fire (inline steps, parallel steps, or any case where gate-result.json is missing). |
| `workflow_finalize` | Complete workflow, finalize trace with aggregates, clean up tools proxy |
| `list_agent_files` | List files under `.agent/` (bypasses gitignore). Use instead of Glob/Grep for `.agent/` file discovery. |

### How step_begin works

`step_begin` is the key performance optimization. Instead of the LLM manually:
1. Reading workflow.yaml to find the step config
2. Reading manifest.json for params and run_token
3. Composing constraints, spec_check instructions, output expectations
4. Writing updated manifest status

...the tool does all of this in one call and returns ready-to-use text blocks. The orchestrator just concatenates them with the step's goal and input file contents to compose the subagent task.

### Transport

The MCP server uses stdio transport (JSON-RPC 2.0, newline-delimited). The IDE spawns it as a child process and manages the lifecycle. The server maintains in-memory cache for workflow definitions and an **MCP call log** — every tool call is logged with timestamp, duration, and result summary. At `workflow_finalize`, the call log is embedded into the trace as `mcp_calls` for orchestration-level visibility in the Trace Viewer.

### Fallback (No MCP)

If MCP tools are not available (server not deployed, not started, Cursor not restarted after install), the orchestrator falls back to manual file operations — same behavior as before MCP, just slower. The `/run-workflow` skill contains a "Manual Fallback" section with condensed instructions for: finding workflow.yaml, creating manifest/trace, composing subagent tasks, reading gate results, updating manifest, and finalizing. No workflow format changes are needed — fallback works with the same `workflow.yaml` files.

**Important:** The orchestrator must choose ONE path (MCP or Manual) at the start and use it for the entire run. Mixing creates duplicate state — MCP traces alongside manual manifests with different run_ids and timestamps — that corrupts workflow history. The Manual Fallback path also requires real system-clock timestamps (not placeholder values).

## Trace System

The trace system captures execution metrics for every workflow run at two levels:

**Subagent level** (from `gate-check.py`):
1. `gate-check.py` appends an invocation entry after each subagent completion — recording `duration_ms`, `message_count`, `tool_call_count`, `modified_files`, and gate results

**Orchestration level** (from MCP server):
2. The MCP server logs every tool call (timestamp, tool name, duration, result summary) in an in-memory call log
3. At `workflow_finalize`, the call log is embedded into the trace as `mcp_calls[]`

The orchestrator creates `trace/<run-id>.trace.json` at startup and finalizes it at completion — computing aggregates across both levels. Each trace captures per-step timing, gate pass/fail history, retry counts, modified files, and the orchestration call sequence. Traces are stored in `.agent/workflows/<name>/trace/` and accumulate across runs.

### Run Token

Each workflow run generates a unique UUID `run_token`, stored in `manifest.json` and injected into every subagent's task prompt as `<!--workflow:run_token:<uuid>-->`. When a subagent completes, `gate-check.py` checks for this token before processing — subagents without a matching token are silently ignored. This prevents:

- **Zombie workflows**: a stopped workflow's manifest stays `in_progress`, and an unrelated subagent triggers false gate validation
- **Phantom invocations**: a casual chat subagent completing while a workflow is active
- **Cross-run collision**: two workflows running simultaneously

### Trace Viewer

Use the **Trace Viewer** (`.agent/tools/trace-viewer.html`) to visualize traces in a browser. Open the HTML file, load a `.trace.json`, and explore: workflow overview, orchestration timeline, proportional step timeline, collapsible step cards with gate details and invocation history. Key features:

- **Orchestration panel**: collapsible section showing all MCP tool calls made during the run — timestamp, tool name, step context, duration, and summary. Color-coded by tool type. Shows the orchestration layer (how the workflow was driven), complementing the subagent-level invocation data.
- **Subagent Timeline (Gantt chart)**: for parallel steps, shows when each subagent started/finished relative to the step duration. Color-coded: green = gate passed, amber = retry (gate failed), red = final fail. Phantom invocations shown as dimmed markers. Click any bar to scroll to that specific attempt in the invocations section.
- **Attempt blocks**: each invocation attempt is a visually distinct block with colored background (amber = gate failed retry, green = gate passed). Gate results are separated into their own section within each attempt.
- **Feedback arrows**: when a gate fails and triggers a retry, the `followup_message` is shown as a dashed amber arrow connecting the failed gate to the next attempt — making the retry flow visually clear.
- **Effective gate config**: step cards show all gate types (structural, semantic, human) with ON/OFF state. Step-level overrides are marked with a dashed outline; inherited values show "(from workflow)" in tooltips.
- **Config tooltips**: workflow parameters, gate settings, and context options have click-to-show tooltips explaining what each setting does. A floating `?` indicator appears on hover.

Use the **Workflow Editor** (`.agent/tools/workflow-editor.html`) to create and edit workflow definitions in a browser. Features: form-based editing of all workflow.yaml fields (including per-step model preference with grouped dropdown for Claude models + custom model text input), struct schema editor tab, live YAML preview, validation, help tooltips, load/export YAML, dark/light theme. The model field is only shown for subagent steps (`subagent: true`) — inline steps inherit the orchestrator's model.

See [trace.md](trace.md) for the full format reference.

## Workflow Tools (Phase 38)

Workflows can declare tool dependencies in their `tools:` section. Two types:

**Script tools** (`type: script`) — Shell commands exposed via the stable `workflow-tools-loader.py` MCP server registered in `.mcp.json`. The loader scans every `workflow.yaml` under `.agent/workflows/templates/` at startup and exposes every script tool as a normal MCP tool with `mcp__workflow_tools__<workflow>__<tool>` naming. The subagent sees named tools with descriptions and JSON Schema validation — not raw Bash commands. Schema is enforced server-side by the loader (jsonschema, when available) AND by the `workflow-tool-validator.py` PreToolUse hook in Claude Code.

**MCP server dependencies** (`type: mcp`) — External MCP servers the workflow requires. The engine checks availability at `workflow_init` and blocks the run if a `required: true` server is missing. The `expected_tools` field in workflow.yaml lists the specific tool names to whitelist in per-step subagents (because CC's `tools:` whitelist requires explicit names — wildcards do not work).

**Lifecycle:**
1. **Install time / `/init-workflow`** — `init-workflow.py` reads `workflow.yaml` and writes `.claude/agents/<workflow>-<step>/AGENT.md` files for each step with `subagent: true`. Each generated file has a strict `tools:` whitelist with built-ins + script tools (`mcp__workflow_tools__<wf>__<tool>`) + mcp tools (`mcp__<server>__<expected_tool>`).
2. **CC restart** — required after any workflow add/edit so CC re-scans `.claude/agents/`.
3. **`workflow_init`** — checks tool availability only. Does NOT generate proxies or modify any files.
4. **`step_begin`** — returns `subagent_type: <workflow>-<step>` (CC) or `null` (inline/Cursor). Returns a `tool_docs` block (brief affordance for CC, full inline command + schema docs for Cursor/inline) for the orchestrator to append to the agent prompt.
5. **`workflow_finalize`** — merges `tool-calls.json` into the trace. Does NOT delete or restore any files.

**Per-step restriction:** Steps can declare `tools: [tool_a, tool_b]` to limit which workflow tools their subagent sees. If omitted, all workflow tools are included in that step's whitelist.

**Token efficiency:** In Claude Code, per-step subagents only see their whitelisted tools — bounded cost per step. The orchestrator (parent session) loads the loader's full tool catalog from `.mcp.json` once per session — fixed, predictable cost.

**Slash commands:**
- `/init-workflow <name>` — generate or update per-step subagent files for one workflow
- `/update-workflows` — bulk sync for all workflows (also called automatically by `install.py`)

See [workflow-yaml.md](workflow-yaml.md) for the full `tools:` format reference, including `expected_tools` for `type: mcp`.

## Architecture: Universal Layer vs Adapter Layer

The Agentic Control Plane has a strict separation between **universal** (engine) and **adapter** (IDE-specific) components:

| Layer | Directory | Purpose | Examples |
|-------|-----------|---------|----------|
| **Universal** | `.agent/` | Engine logic, workflows, specs, schemas, traces | `gate-check.py`, `workflow.yaml`, `manifest.json`, `trace.json` |
| **Adapter** | `.cursor/` | IDE-specific integration (Cursor) | `hooks.json`, `rules/*.mdc`, `skills/*.md` |

### Design Principle

`.agent/` must contain **only engine-native data** — nothing that is specific to a particular IDE or LLM runtime. Adapter-specific behavior stays in the adapter layer (`.cursor/` for Cursor, future `.claude/` for Claude Code, etc.).

This means:
- **Workflow definitions** (`workflow.yaml`) never reference Cursor-specific concepts
- **Struct schemas** validate data format, not IDE behavior
- **Gate scripts** (`gate-check.py`) produce universal output; IDE-specific payload fields are handled at the boundary
- **Trace files** store engine-level metrics; adapter-specific fields (e.g., `subagent_id`, `model`, Cursor's `tool_call_count`) are namespaced under `adapter.<name>` to prevent leaking IDE details into the universal trace format

### Cursor Adapter

The Cursor adapter consists of:
- `.cursor/hooks.json` — Routes `subagentStop` events to `gate-check.py`
- `.cursor/mcp.json` — Registers the workflow-engine MCP server (auto-spawned by Cursor)
- `.cursor/rules/` — Always-active rules (`workflow-context.mdc`, `spec-guard.mdc`)
- `.cursor/skills/` — Skill definitions (`run-workflow`, `learn-workflows`, `spec`, `run-workflow-for-code-spec`, `spec-fast`, `code-spec-fast`, `spec-add-fast`)

### Claude Code Adapter

The Claude Code adapter consists of:
- `.claude/settings.json` — Routes `SubagentStop` events to `gate-check.py` (with `matcher: "workflow-step"` to filter only workflow subagents)
- `.mcp.json` — Registers the workflow-engine MCP server (standard MCP config location)
- `.claude/rules/` — Always-active rules (`spec-guard.md`)
- `.claude/skills/` — Skill definitions (same set as Cursor)

**Key differences from Cursor:**
- Hook format: `SubagentStop` (PascalCase) vs `subagentStop` (camelCase)
- Hook matcher: Claude Code supports `matcher` field to filter which subagents trigger the hook
- Parallel agents: Claude Code's parallel `Agent` tool calls do NOT trigger `SubagentStop` — the `step_complete` safety net validates outputs in this case
- MCP config: `.mcp.json` at project root (not `.cursor/mcp.json`)

### Bridge: gate-check.py

`gate-check.py` acts as the **bridge** between either adapter and the universal engine: it receives the IDE's hook payload (IDE-specific format), performs universal gate validation, writes universal `gate-result.json`, and returns the appropriate `followup_message` format.

**Transcript extraction (Claude Code):** Claude Code's SubagentStop hook payload lacks `model`, `duration_ms`, `message_count`, `tool_call_count`, and `modified_files` — fields that Cursor provides directly. To compensate, `gate-check.py` reads the subagent's transcript file (JSONL, path provided in `agent_transcript_path`) and extracts: model name, duration (from timestamps), message/tool counts, token usage (input + output), and modified files (from Write/Edit tool_use blocks). These are used as fallback values when the hook payload doesn't include them — Cursor fields always take priority when present.

### Adding New Adapters

To support a new IDE, create a new adapter directory with equivalent hook routing, rules, and MCP config. The `.agent/` layer remains unchanged — same `gate-check.py`, same workflow definitions, same trace format.

## Development & Deployment

The engine source lives in a `dist/` directory (the development copy). To deploy changes to a target project:

```
# Full install (first time)
python install.py <target-project-path>

# Update existing installation (preserves user workflows, specs, runtime state)
python install.py --update <target-project-path>
```

`install.py --update` copies only engine files (`.agent/docs/`, `.agent/scripts/`, `.agent/mcp/`, `.agent/workflows/templates/predefined/`, `.agent/tools/`, `.cursor/`) without touching user-created content (`.agent/workflows/templates/my_workflows/`, `.agent/specs/`, runtime state like `manifest.json`).

**Development workflow:**
1. Edit files in `dist/`
2. Run `python install.py --update <target>` to deploy
3. Test in the target project (run workflows, verify gates, check traces)
4. Iterate

**Important:** Always edit `dist/` — never edit deployed files directly. Deployed files are overwritten on next `--update`.

## Related Docs

- [workflow-yaml.md](workflow-yaml.md) — Full reference for `workflow.yaml` format
- [structs.md](structs.md) — How to write struct schemas
- [manifest.md](manifest.md) — `manifest.json` format (read reference)
- [specs.md](specs.md) — Behavioral spec format reference
- [trace.md](trace.md) — Trace system format reference
