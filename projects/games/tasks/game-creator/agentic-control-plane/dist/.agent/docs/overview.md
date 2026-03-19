# Agentic Control Plane — Overview

The Agentic Control Plane is a system for managing LLM-driven development. It has two components:

1. **Workflow Engine** — A declarative system for defining and executing multi-phase LLM-driven tasks. You describe your workflow in a YAML file — steps, inputs, outputs, gates — and the engine handles execution, state tracking, validation, and resume.

2. **Spec Guard** — A behavioral specification enforcement system. Specs in `.agent/specs/` capture component requirements that the LLM must respect during every code change. An always-active rule enforces compliance; the `/spec` skill manages the spec lifecycle.

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
| **Spec Guard** | Always-active enforcement — LLM checks specs before code changes |

## How It Works

1. User invokes `/run-workflow <name>` (or `/run-workflow <name> --resume`)
2. Orchestrator reads `workflow.yaml` and creates/resumes `manifest.json`
3. For each step (sequentially):
   a. Validates inputs against struct schemas (if defined)
   b. Spawns a subagent with: goal + input files + summaries from previous steps
   c. Subagent executes the goal, writes outputs
   d. **Structural gate runs** (via `subagentStop` hook): `gate-check.py` validates outputs against struct schemas
      - On **fail**: `gate-check.py` returns `followup_message` → subagent retries in-place (same session, up to `max_gate_retries`)
      - On **pass**: `gate-check.py` returns `{}` → subagent **stops** → control returns to orchestrator
   e. Orchestrator reads `gate-result.json`, handles **semantic gate** (LLM check) and **human gate** (optional approval)
   f. On pass: updates manifest, writes summary to `context/`, spawns new subagent for next step
   g. If gate retries exhausted: orchestrator re-spawns up to `max_step_retries` (default: 3), then **workflow STOPS**
   h. **On gate not executing** (script crash, hook not firing): **workflow STOPS immediately.** A gate that doesn't run is worse than a gate that fails.
4. Workflow completes when all steps pass

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
├── scripts/                     # Generic engine scripts
│   ├── gate-check.py            # Structural gate — called by subagentStop hook
│   └── schema-validate.py       # File-vs-schema validator
│
├── gate-check-invocations.log   # Prolog/epilog log — confirms hook was invoked (auto-generated)
├── gate-check-error.log         # Error log — diagnostics when gate-check.py fails (auto-generated)
├── *.lock                       # Lock files created by gate-check.py for concurrent write safety (can be gitignored)
│
├── tools/                       # Human-facing utilities
│   ├── trace-viewer.html        # Browser-based workflow trace viewer
│   └── workflow-editor.html     # Browser-based workflow YAML editor
│
├── specs/                       # Behavioral specifications (Spec Guard)
│   ├── _index.json              # Registry of all specs
│   ├── _registry.json           # Implementation mapping (files → specs)
│   └── {domain}/                # Per-domain spec files
│       └── ComponentName.md     # Individual spec (YAML frontmatter + Markdown)
│
├── templates/
│   ├── predefined/              # Built-in workflows (read-only, shipped with engine)
│   │   ├── spec-write-and-implement/
│   │   │   ├── workflow.yaml
│   │   │   └── structs/
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
└── workflows/                   # Runtime instances only
    └── <workflow-name>/
        ├── manifest.json         # Runtime state (auto-generated)
        ├── context/              # Step summaries (auto-generated)
        │   └── <step>.summary.md
        └── trace/                # Execution traces (auto-generated)
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

3. **`/spec` skill** — Manages the spec lifecycle: `list`, `show`, `add`, `check`, `audit`. The `add` command includes an interactive CLARIFY step where the LLM refines requirements with the user before writing the spec.

4. **`[specs::ComponentName]` pattern** — When the user types this in chat, the always-active rule instructs the LLM to invoke `/spec add` to capture the specification.

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
| `spec-write-and-implement` | Capture spec (CLARIFY → WRITE-SPEC) → delegate to `spec-enforcement` |
| `spec-enforcement` | Implement code with spec checking (CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER) |
| `doc-spec-extraction` | Extract specs from documentation (ANALYZE → EXTRACT → VALIDATE → COMMIT) |
| `create-workflow` | Interactive workflow creation assistant (LEARN → DISCUSS → CREATE) |
| `registry-sync` | Discover unregistered spec implementations, sync `_registry.json` (SCAN → REVIEW → REGISTER) |
| `spec-audit` | Read-only QA compliance audit — scan code against specs, report violations (DISCOVER → SCAN → REPORT) |
| `hook-diagnostic` | 3-step diagnostic — tests hook firing, struct validation, and retry loop |

`spec-write-and-implement` handles spec **creation** (interactive CLARIFY + WRITE-SPEC), then delegates to `spec-enforcement` for **implementation**. `spec-enforcement` can also be used standalone via `/code-with-spec` or `/run-workflow` when no new spec is being created.

`spec-enforcement` supports two modes:
- **Targeted** (with `component`): enforces a specific component's spec
- **Auto-discovery** (without `component`): analyzes the instruction to find all affected specs via `_registry.json`

```
spec-write-and-implement:           spec-enforcement:
  CLARIFY (human gate)                CHECK-SPECS
  WRITE-SPEC                          IMPLEMENT
  ENFORCE ─── delegate_to ──────→     VERIFY
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
.agent/
├── templates/
│   └── predefined/
│       └── spec-write-and-implement/
│           ├── workflow.yaml        # Definition (read-only, shipped with engine)
│           └── structs/             # Schemas (read-only)
│
└── workflows/
    └── spec-write-and-implement/
        ├── manifest.json            # Runtime state (auto-generated per run)
        ├── data/                    # Step output data (auto-generated)
        └── context/                 # Step summaries (auto-generated)
```

### How Predefined Workflows Are Triggered

There are five ways to run a predefined workflow:

**1. Via `[specs::X]` pattern (most natural):**
User types `[specs::EditField] character limit 30, show red error`. The always-active rule instructs the LLM to invoke `/spec add EditField`, which runs the `spec-write-and-implement` workflow.

**2. Via `/spec` skill (explicit):**
User runs `/spec add EditField`. The skill handles CLARIFY interactively, then runs the workflow steps.

**3. Via `/code-with-spec` (implement with enforcement):**
User runs `/code-with-spec EditField "add max length validation"` or `/code-with-spec "refactor the retry logic"` (auto-discovery mode). This invokes `spec-enforcement` directly — no new spec is created.

**4. Via `/run-workflow` (direct):**
User runs `/run-workflow spec-write-and-implement --component EditField --domain ui`. The orchestrator finds the definition in `templates/predefined/` and runs it.

**5. Via delegation from another workflow:**
A parent workflow step has `delegate_to: spec-write-and-implement`. The orchestrator reads the predefined workflow and runs all its steps as a nested workflow.

## Workflow Delegation

A workflow can delegate to another workflow using `delegate_to:`. The orchestrator reads the target workflow definition (searching `templates/my_workflows/<name>/` then `templates/predefined/<name>/`), creates a nested manifest, and runs all its steps sequentially (each step spawns its own subagent). When complete, control returns to the parent workflow. This enables workflow composition without duplicating steps.

**Important:** Delegation is NOT a subagent spawn — the orchestrator executes the delegated workflow directly. This avoids nested subagent limitations.

See [workflow-yaml.md](workflow-yaml.md) for the `delegate_to` reference.

## Param Bindings

Steps can update workflow params based on their output using `param_bindings`. This is critical for auto-discovery flows where early steps determine values (e.g., component name) that subsequent steps need. After a step passes its gate, the orchestrator reads specified fields from output files and updates `manifest.params` for all downstream steps.

See [workflow-yaml.md](workflow-yaml.md) for the full `param_bindings` reference.

## Trace System

The trace system captures execution metrics for every workflow run. When a workflow runs:

1. The orchestrator creates `trace/<run-id>.trace.json` at startup (alongside `manifest.json`)
2. `gate-check.py` appends an invocation entry after each subagent completion — recording `duration_ms`, `message_count`, `tool_call_count`, `modified_files`, and gate results
3. The orchestrator finalizes the trace at workflow completion — computing aggregates

Each trace entry captures per-step timing, gate pass/fail history, retry counts, and modified files. Traces are stored in `.agent/workflows/<name>/trace/` and accumulate across runs.

### Run Token

Each workflow run generates a unique UUID `run_token`, stored in `manifest.json` and injected into every subagent's task prompt as `<!--workflow:run_token:<uuid>-->`. When a subagent completes, `gate-check.py` checks for this token before processing — subagents without a matching token are silently ignored. This prevents:

- **Zombie workflows**: a stopped workflow's manifest stays `in_progress`, and an unrelated subagent triggers false gate validation
- **Phantom invocations**: a casual chat subagent completing while a workflow is active
- **Cross-run collision**: two workflows running simultaneously

### Trace Viewer

Use the **Trace Viewer** (`.agent/tools/trace-viewer.html`) to visualize traces in a browser. Open the HTML file, load a `.trace.json`, and explore: workflow overview, proportional timeline, collapsible step cards with gate details and invocation history. Key features:

- **Subagent Timeline (Gantt chart)**: for parallel steps, shows when each subagent started/finished relative to the step duration. Color-coded: green = gate passed, amber = retry (gate failed), red = final fail. Phantom invocations shown as dimmed markers. Click any bar to scroll to that specific attempt in the invocations section.
- **Attempt blocks**: each invocation attempt is a visually distinct block with colored background (amber = gate failed retry, green = gate passed). Gate results are separated into their own section within each attempt.
- **Feedback arrows**: when a gate fails and triggers a retry, the `followup_message` is shown as a dashed amber arrow connecting the failed gate to the next attempt — making the retry flow visually clear.
- **Effective gate config**: step cards show all gate types (structural, semantic, human) with ON/OFF state. Step-level overrides are marked with a dashed outline; inherited values show "(from workflow)" in tooltips.
- **Config tooltips**: workflow parameters, gate settings, and context options have click-to-show tooltips explaining what each setting does. A floating `?` indicator appears on hover.

Use the **Workflow Editor** (`.agent/tools/workflow-editor.html`) to create and edit workflow definitions in a browser. Features: form-based editing of all workflow.yaml fields, struct schema editor tab, live YAML preview, validation, help tooltips, load/export YAML, dark/light theme.

See [trace.md](trace.md) for the full format reference.

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

### Current State (Cursor Adapter)

The Cursor adapter consists of:
- `.cursor/hooks.json` — Routes `subagentStop` events to `gate-check.py`
- `.cursor/rules/` — Always-active rules (`workflow-context.mdc`, `spec-guard.mdc`)
- `.cursor/skills/` — Skill definitions (`run-workflow`, `learn-workflows`, `spec`, `code-with-spec`)

`gate-check.py` acts as the **bridge** between the Cursor adapter and the universal engine: it receives Cursor's hook payload (IDE-specific), performs universal gate validation, writes universal `gate-result.json`, and returns Cursor-specific `followup_message` format.

### Future Adapters

To support a new IDE (e.g., Claude Code), create a new adapter directory (e.g., `.claude/`) with equivalent hook routing and rules. The `.agent/` layer remains unchanged — same `gate-check.py`, same workflow definitions, same trace format.

## Development & Deployment

The engine source lives in a `dist/` directory (the development copy). To deploy changes to a target project:

```
# Full install (first time)
python install.py <target-project-path>

# Update existing installation (preserves user workflows, specs, runtime state)
python install.py --update <target-project-path>
```

`install.py --update` copies only engine files (`.agent/docs/`, `.agent/scripts/`, `.agent/workflows/templates/predefined/`, `.agent/tools/`, `.cursor/`) without touching user-created content (`.agent/workflows/templates/my_workflows/`, `.agent/specs/`, runtime state like `manifest.json`).

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
