# workflow.yaml — Format Reference

A workflow definition file. Lives at `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` (user-defined) or `.agent/workflows/templates/predefined/<name>/workflow.yaml` (built-in).

## Top-Level Fields

```yaml
name: string                        # Required. Unique workflow identifier.
version: number                     # Required. Integer version for tracking changes.
description: string                 # Required. Human-readable purpose.

params:                              # Optional. User-provided arguments at invocation time.
  - name: string                     # Param name (used in goal text and by orchestrator)
    description: string              # Human-readable purpose — shown when asking user
    required: boolean                # If true, workflow won't start without it (default: false)
    default: string                  # Default value if not provided (optional)

gate:                                # Optional. Default gate config for all steps.
  structural: boolean                # Run structural validation script (default: true)
  semantic: boolean                  # Run LLM semantic check (default: false)
  human: boolean                     # Require human approval (default: false)
  max_step_retries: number           # Max subagent re-spawns on failure (default: 3)
  max_gate_retries: number           # Max gate-hook loops within one subagent (default: 5)

context:
  carry_forward: "none" | "summary"  # What context next steps receive (default: "none")
                                     # "summary" = auto-generated summaries from context/
                                     # Can be overridden per-step with step.carry_forward (bool).

tools:                               # Optional. Tool dependencies for this workflow.
  - name: string                     # Unique tool name (used in step-level tools: filter).
    type: "script" | "mcp"           # "script" = command exposed via the workflow_tools loader.
                                     # "mcp" = external MCP server dependency.
    # --- script-only fields ---
    command: string                  # Shell command to execute (e.g., "python scripts/extract.py").
                                     # The loader appends "--key=value" args from the input_schema.
    description: string              # Human-readable description (required for script, shown to LLM).
    input_schema: object             # Optional JSON Schema for tool arguments.
                                     # Validated server-side by the loader (jsonschema, when available)
                                     # AND by the workflow-tool-validator.py PreToolUse hook in CC.
    # --- mcp-only fields ---
    required: boolean                # If true, workflow blocks when server is unavailable (default: true).
    expected_tools: [string]         # Required for per-step subagent whitelist generation in CC.
                                     # Lists the specific tool names from this server that workflow
                                     # steps will call. Format: ["tool_a", "tool_b"]. The init-workflow
                                     # script writes "mcp__<server>__<tool>" entries into the per-step
                                     # AGENT.md tools whitelist for each tool listed here.
                                     # Without this field, subagents in CC will not see any tools from
                                     # this server (their whitelist would have no MCP entries for it).
    server_config:                   # Optional. Config for compatibility with older toolchains;
                                     # not used in Phase 38 — server registration happens in .mcp.json.
      command: string                # Executable (e.g., "python").
      args: [string]                 # Arguments (e.g., [".agent/mcp/my-server.py"]).

steps: []                            # Required. Ordered list of steps (see below).
```

## Params

Params let users pass arguments when invoking a workflow. The orchestrator includes all param values in every subagent's task prompt, so the subagent can adapt its behavior.

```yaml
params:
  - name: section
    description: "Specific document section to analyze (e.g., '3.2.1 Message Queue')"
    required: false

  - name: source
    description: "Path to the source document"
    required: false
    default: "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md"
```

**Invocation with params:**
```
/run-workflow astro-spec-extraction --section "3.2.1 Message Queue Management"
/run-workflow astro-spec-extraction                  # uses defaults, full doc analysis
```

**How params reach subagents:**
The orchestrator passes params as part of the task prompt. The step's `goal` uses natural language to describe what to do with each param value — including what to do when a param is not provided.

**Branching via natural language:**
Instead of `if/else` syntax in YAML, write conditional behavior in the step's `goal`:

```yaml
goal: >
  If a specific section was requested, locate it in the source document.
  If not found, list the closest matches and ASK the user to clarify.
  If no section was specified, scan the full document.
```

The LLM reads the goal + params and decides what to do. The gate validates the result.

## Tools (Workflow Tool Dependencies)

Workflows can declare tool dependencies that subagents need during execution. Two types:

### Script Tools (`type: script`)

Shell commands that the engine wraps as MCP tools. At `workflow_init`, the engine generates a temporary MCP server (`_workflow_tools_<name>.py`) that proxies tool calls to `subprocess.run()`. The subagent sees them as native MCP tool calls with structured arguments and schema validation.

```yaml
tools:
  - name: extract_tables
    type: script
    command: "python .agent/scripts/extract-tables.py"
    description: "Extract tables from PDF pages"
    input_schema:
      type: object
      required: [file_path]
      properties:
        file_path: { type: string, description: "Path to PDF file" }
        pages: { type: string, description: "Page range (e.g., '1-5', 'all')" }
```

Why MCP proxy instead of Bash? Tracing (structured tool call logs), schema validation (correct arguments), tool discovery (LLM sees named tool, not a generic Bash command), and IDE visibility.

**Note:** Nothing prevents a step's `goal` from also instructing the subagent to run ad-hoc commands via Bash. The `tools:` section is for tools that benefit from structured invocation and tracing.

### MCP Server Dependencies (`type: mcp`)

External MCP servers the workflow requires. The engine checks availability at `workflow_init` and blocks if a `required: true` server is missing.

```yaml
tools:
  - name: database_server
    type: mcp
    required: true
    server_config:                  # Optional: enables inline start in Claude Code
      command: "python"
      args: [".agent/mcp/db-server.py"]
```

Description is **not declared** in workflow.yaml for MCP tools — it comes from the MCP server itself via `tools/list`.

### Per-Step Tool Restriction

By default, a subagent sees all workflow-level tools. Use the step-level `tools:` field to restrict:

```yaml
steps:
  - name: extract
    tools: [extract_tables]        # only extract_tables available
    goal: "Extract tables from {source}..."
  - name: analyze
    # tools: omitted → sees ALL workflow tools
    goal: "Analyze the extracted data..."
```

### Adapter Behavior

| Adapter | Script tools | MCP dependencies |
|---------|-------------|-----------------|
| **Claude Code** | Engine injects proxy in AGENT.md `mcpServers:` (inline, scoped to subagent) | Engine injects `server_config` in AGENT.md or orchestrator verifies availability |
| **Cursor** | Subagent sees all parent tools automatically | User enables server manually; engine checks availability |

### Lifecycle

1. `workflow_init` → generates `_workflow_tools_<name>.py` (tool server), checks availability
2. `step_begin` → returns `tools_info` with proxy server config and MCP dependencies
3. Orchestrator injects `mcpServers:` into AGENT.md (Claude Code only — see example below)
4. Subagent runs, calls tools via MCP → tool server logs to `tool-calls.json`
5. `step_complete` → tags tool call entries with step name
6. `workflow_finalize` → merges `tool-calls.json` into trace, deletes tool server

### AGENT.md Injection Example (Claude Code)

In Claude Code, the orchestrator dynamically modifies `.claude/agents/workflow-step/AGENT.md` before spawning a subagent. This makes workflow tools visible to the subagent as MCP tools, scoped to that subagent's lifetime.

**Original AGENT.md:**
```yaml
---
name: workflow-step
tools: Read, Write, Edit, Bash, Glob, Grep
maxTurns: 100
---
```

**After orchestrator injection (for a step with script + MCP tools):**
```yaml
---
name: workflow-step
tools: Read, Write, Edit, Bash, Glob, Grep
maxTurns: 100
mcpServers:
  - workflow_tools_my_workflow:
      type: stdio
      command: "python"
      args: [".agent/mcp/_workflow_tools_my_workflow.py"]
  - fake_db:
      type: stdio
      command: "python"
      args: [".agent/mcp/fake-db-server.py"]
---
```

The subagent now sees tools like `mcp__workflow_tools_my_workflow__count_lines(...)` and `mcp__fake_db__query_db(...)` as native tool calls. The MCP servers start when the subagent spawns and stop when it completes — no permanent resource usage.

After `step_complete`, the orchestrator restores AGENT.md to its original state for the next step (which may need different tools).

**In Cursor** this is not needed — subagents see all parent MCP tools automatically.

## Param Bindings (Output-to-Param Re-binding)

Steps can update workflow params based on their output. This is essential when a step discovers values at runtime that subsequent steps need (e.g., auto-discovery of a component name).

```yaml
steps:
  - name: clarify
    goal: >
      Discover the component name from user requirements...
    outputs:
      - path: data/approved-requirements.json
        struct: approved-requirements
    param_bindings:
      component: "data/approved-requirements.json::component"
      domain: "data/approved-requirements.json::domain"
```

**How it works:**

1. The step completes and passes the gate
2. The orchestrator reads `param_bindings`
3. For each binding, it reads the specified field from the output file:
   - `"data/approved-requirements.json::component"` → reads the `component` field from `data/approved-requirements.json`
   - Supports dot notation: `"file.json::metadata.name"` reads nested fields
4. Updates `manifest.params` with the new values
5. Subsequent steps see the updated params — all `{param}` placeholders resolve to the new values

**Syntax:** `"<output-file-path>::<json-field-path>"`

- The file path is relative to the workflow runtime directory
- The field path uses dot notation for nested fields
- Array access is not supported — use top-level or nested object fields

**When to use:**

- Auto-discovery flows where a step determines a value the user didn't provide
- Multi-phase workflows where early steps produce metadata consumed by later steps
- Any time a param starts as empty/null and gets resolved at runtime

**Important:** `param_bindings` runs AFTER the gate passes. If the gate fails and the step retries, bindings are NOT applied until the gate passes. This ensures only validated outputs update params.

## Step Fields

```yaml
steps:
  - name: string                     # Required. Unique within workflow. Used in manifest keys.
    goal: string                     # Required. Prompt for the subagent — what to accomplish.
    subagent: boolean                # Run in isolated subagent (default: true).
                                     # Set to false for inline execution by the orchestrator.
                                     # Inline steps: no subagent spawn, no gate hook, faster.
                                     # Use for lightweight steps (register, verify) or when
                                     # the orchestrator already has sufficient context.
    spec_check: boolean              # Check behavioral specs before/after code changes (default: true).
    tools: [string]                  # Optional. Restrict which workflow-level tools this step can use.
                                     # List of tool names from the top-level tools: section.
                                     # If omitted, the step sees ALL workflow tools.
    model: string                    # Optional. Model hint for the subagent (e.g., "haiku", "sonnet", "opus").
                                     # Opaque string — the engine forwards it to the orchestrator.
                                     # The adapter decides how to use it (Claude Code: Agent tool model param,
                                     # Cursor: may map to Max Mode, other adapters: custom logic).
                                     # If omitted, the subagent inherits the orchestrator's model.

    parallel: boolean                # Fan-out into multiple concurrent subagents (default: false).
    parallel_key: string             # Required if parallel: true.
                                     # JSONPath-like expression pointing to array items.
                                     # Example: "extraction-manifest.tasks[status=pending]"

    inputs:                          # Optional. Files/data the subagent receives.
      - path: string                 # File path. Supports {variable} placeholders and globs.
                                     # Glob patterns (*, **, ?) are resolved by step_begin
                                     # using Python glob (bypasses gitignore). Each matched
                                     # file becomes a separate input entry.
        inject: "file" | "file_if_exists" | "reference"
                                     # Default: "reference" (if omitted)
                                     # "file"          = read and include full content
                                     # "file_if_exists" = include if exists, skip otherwise
                                     # "reference"     = mention path, don't include content
        struct: string               # Optional. Struct name for pre-step input validation.

    outputs:                         # Optional. Files the subagent should produce.
      - path: string                 # Expected output path. Supports {variable} and globs.
        struct: string               # Optional. Struct name for post-step gate validation.

    param_bindings:                  # Optional. Update params from step outputs after gate passes.
      <param_name>: "<file>::<field>" # "data/output.json::component" reads component from file

    carry_forward: boolean           # Optional. Override workflow-level carry_forward for this step.
                                     # true = force summaries even if workflow-level is "none".
                                     # false = suppress summaries even if workflow-level is "summary".
                                     # Omitted = inherit from workflow-level setting.

    gate:                            # Optional. Per-step override of workflow-level gate.
      structural: boolean
      semantic: boolean
      human: boolean
      max_step_retries: number       # Override workflow-level retry limit for this step
      max_gate_retries: number       # Override workflow-level gate loop limit for this step
```

## Spec Check (Behavioral Spec Enforcement)

The `spec_check` field controls whether the orchestrator adds **behavioral spec enforcement instructions** to the subagent's task prompt. Defaults to `true`.

When `spec_check: true`, the orchestrator appends these instructions to the subagent task:

1. Before making code changes, read `.agent/specs/_registry.json`
2. Find all specs whose `implemented_by` files overlap with files you plan to modify
3. Read each relevant spec and check that your changes do NOT violate any requirement
4. If a violation is found: STOP and report the conflict in your summary (do NOT proceed with conflicting changes)
5. After completing changes, verify no specs were violated

When `spec_check: false`, no spec-related instructions are added. Use this for steps that do not modify source code (planning, scanning, reporting, documentation).

```yaml
steps:
  - name: implement
    goal: "Make changes to the codebase..."
    spec_check: true       # default — specs are checked (can be omitted)

  - name: plan
    goal: "Analyze the codebase and create a plan..."
    spec_check: false      # no code changes — skip spec checking
```

**Note:** `spec_check` works independently of the `spec-guard.mdc` always-active rule. The rule provides soft guidance to all LLM sessions; `spec_check` adds explicit, stronger instructions specifically to workflow subagent tasks. Both can coexist — `spec_check` reinforces what the rule already suggests.

## Input Injection Modes

| Mode | Behavior | Use when |
|------|----------|----------|
| `file` | Full file content injected into subagent prompt | Small-medium files the subagent must read |
| `file_if_exists` | Like `file`, but silently skips if missing | Optional inputs (e.g., config that may not exist yet) |
| `reference` | Only the file path is mentioned, not content | Large files — subagent reads them itself via tools |

## Parallel Steps

When `parallel: true`, the orchestrator:
1. Reads `parallel_key` to resolve a list of items (from a JSON file or manifest)
2. Spawns one subagent per item, all concurrently
3. Each subagent's goal receives the item as context (e.g., domain name, file path)
4. The step is complete only when ALL subagents finish
5. The gate validates ALL outputs together

The `parallel_key` uses a JSONPath-like syntax:
- `"extraction-manifest.tasks[status=pending]"` — read `extraction-manifest.json`, get `.tasks` array, filter where `status == "pending"`
- `"scan-results.files[*]"` — read `scan-results.json`, get all items in `.files`

## Workflow Delegation (Hand-off)

A step can delegate to another workflow instead of running its own goal. This avoids duplicating steps across workflows that share common logic.

```yaml
steps:
  - name: verify-and-register
    delegate_to: spec-enforcement        # Name of the workflow to invoke
    params:                              # Params to pass to the delegated workflow
      component: "{component}"
      domain: "{domain}"
```

**`goal` + `delegate_to` coexistence:**

A delegation step can have BOTH `goal` and `delegate_to`. The `goal` text provides conditional logic for the orchestrator (not for a subagent). The orchestrator reads the `goal` to decide whether to execute or skip the delegation:

```yaml
  - name: enforce
    goal: >
      IF the "implement" param is "false": skip this step entirely.
      OTHERWISE: delegate to spec-enforcement.
    delegate_to: spec-enforcement
    params:
      component: "{component}"
```

The orchestrator evaluates the `goal` conditions first. If the step should be skipped, it marks it `skipped` in the manifest without running the delegation. Otherwise, it proceeds with the delegation normally.

**How it works:**
1. The orchestrator reads `delegate_to` and finds the workflow (searches `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` then `.agent/workflows/templates/predefined/<name>/workflow.yaml`)
2. The orchestrator runs the delegated workflow **directly** (NOT as a subagent) — creates a separate manifest, runs each step sequentially (each step spawns its own subagent)
3. Params from the delegating step are merged with the delegated workflow's defaults
4. When the delegated workflow completes, control returns to the parent workflow
5. The parent workflow's manifest records the delegation result

**Param interpolation in `delegate_to`:**

The `params:` block in a delegation step uses `{param}` placeholders that resolve from the parent workflow's current params (including any values updated by `param_bindings` from earlier steps):

```yaml
  - name: enforce
    delegate_to: spec-enforcement
    params:
      component: "{component}"       # Resolved from parent's manifest.params.component
      domain: "{domain}"             # May have been set by param_bindings in a previous step
      spec_path: ".agent/specs/{domain}/{component}.md"  # Multiple placeholders OK
```

If a placeholder references a param that is null/empty, the resolved value will be an empty string. The delegated workflow's goal should handle this case (e.g., auto-discovery mode).

**`subagent: false` — two use cases:**

1. **Delegation steps** — `delegate_to:` **must** have `subagent: false`. Without it, the adapter (e.g., Cursor) may spawn a subagent using a weaker model that cannot interpret the workflow skill.

2. **Inline regular steps** — any step can set `subagent: false` to execute directly by the orchestrator instead of spawning a subagent. Benefits: no spawn overhead (~5-10s per step), no inter-step gaps (~30-60s reduction), the orchestrator retains full context. Trade-off: no gate hook fires (structural validation skipped), no hook-based invocation data in trace.

**Delegation example:**

```yaml
  - name: write
    delegate_to: spec-write
    subagent: false              # REQUIRED — prevents adapter from spawning subagent
    params:
      component: "{component}"
```

**Constraints:**
- Max one level of delegation depth: a parent can delegate (A→B, A→C), but a delegated workflow must NOT delegate further (A→B→D is prohibited). Circular delegation (A→B→A) is also detected and aborted.
- The orchestrator must detect circular delegation (A→B→A) and abort with an error
- The delegated workflow runs with its own manifest and context
- The delegated workflow uses its OWN gate config — parent gate config is NOT inherited
- Gate results from the delegated workflow are reported to the parent
- The orchestrator must NOT spawn a subagent for the delegation step itself — use `subagent: false`

## Gate Configuration

Gates validate outputs between steps. Three layers, each independently configurable:

| Layer | What | How | When to use |
|-------|------|-----|-------------|
| `structural` | File existence, schema compliance, field types | Python script (`gate-check.py`) | Always (deterministic, fast) |
| `semantic` | Completeness, correctness, coherence | LLM evaluation by orchestrator | When content quality matters |
| `human` | Manual approval | Orchestrator asks user | Critical steps (e.g., planning) |

**Two retry mechanisms:**

| Parameter | What retries | Scope | Default |
|-----------|-------------|-------|---------|
| `max_gate_retries` | Gate-hook loops **within** one subagent session. The subagent gets feedback ("missing field X") and tries to fix it in-place. Preserves context. | Same subagent | 5 |
| `max_step_retries` | Orchestrator re-spawns a **new** subagent with fresh context + failure feedback. Used when the subagent fundamentally can't self-correct. | New subagent | 3 |

`max_gate_retries` is enforced by `gate-check.py` — when `loop_count` reaches the limit, the script stops returning `followup_message` and writes `gate-result.json` for the orchestrator. The Cursor `hooks.json` has a hard ceiling of 25 as a safety net.

Per-step `gate:` overrides workflow-level defaults:

```yaml
gate:              # workflow default
  structural: true
  semantic: true
  human: false
  max_gate_retries: 5     # subagent self-correction loops (default: 5)
  max_step_retries: 3     # orchestrator re-spawns (default: 3)

steps:
  - name: plan
    gate:
      human: true         # override: require human approval
  - name: extract
    gate:
      max_gate_retries: 8 # complex step — more self-correction chances
  - name: commit
    gate:
      max_step_retries: 1 # critical step — 1 re-spawn, then STOP
      max_gate_retries: 2 # minimal self-correction
```

## Minimal Example

The simplest possible workflow — two sequential steps, no params, no structs:

```yaml
name: code-review
version: 1
description: >
  Review code files for quality issues and write a report.

gate:
  structural: false
  semantic: true
  human: false

context:
  carry_forward: summary

steps:
  - name: analyze
    goal: >
      Read all source files in the src/ directory.
      Identify code quality issues: duplications, naming, complexity.
      Write a JSON report with findings.
    subagent: true
    outputs:
      - path: .agent/workflows/code-review/data/findings.json

  - name: report
    goal: >
      Read the findings and generate a human-readable Markdown report.
      Group by severity (critical, warning, info).
      Include file paths and line numbers for each finding.
    subagent: true
    inputs:
      - path: .agent/workflows/code-review/data/findings.json
        inject: file
    outputs:
      - path: .agent/workflows/code-review/data/report.md
```

**Key points:**
- Only `name`, `version`, `description`, and `steps` are required at top-level
- Each step needs `name` and `goal` at minimum
- `outputs` are optional but recommended (the gate checks them)
- `struct` validation is optional — omit it for quick workflows
- `context.carry_forward: summary` lets later steps see what earlier steps did
- Output paths use `.agent/workflows/<workflow-name>/data/` convention (full path from project root; runtime data always goes in `.agent/workflows/`, not in `templates/`)
- The `data/`, `context/`, and `trace/` directories are created automatically on first write — you do not need to pre-create them

## Complete Example

```yaml
name: astro-spec-extraction
version: 2
description: >
  Extract validation specs from Astro Programming Guide v3.2.
  Supports full document analysis or targeted section extraction.
  Detects existing specs and merges/updates instead of overwriting.

params:
  - name: section
    description: "Specific section to analyze (e.g., '3.2.1 Message Queue'). Omit for full document."
    required: false
  - name: source
    description: "Path to the source document"
    required: false
    default: "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md"

gate:
  structural: true
  semantic: true
  human: false

context:
  carry_forward: summary

steps:
  - name: plan
    goal: >
      Read the source document.

      If a specific SECTION was requested:
        - Locate it in the document. If not found, list the 3 closest
          section headings and ASK the user which one they meant.
        - Identify which domain(s) the section belongs to.
      If NO section specified:
        - Scan the full document. Identify all domains with extractable rules.

      Check .agent/specs/ for existing specs that cover the same sections.
      For each existing spec, mark the task as mode "merge".
      For new sections without specs, mark as mode "create".

      Generate an extraction manifest with tasks.
    inputs:
      - path: "{source}"
        inject: reference
      - path: ".agent/specs/**/*.md"
        inject: file_if_exists
    outputs:
      - path: .agent/workflows/astro-spec-extraction/data/extraction-manifest.json
        struct: extraction-manifest
    gate:
      human: true

  - name: extract
    goal: >
      For each task in the manifest, extract validation specs from the
      source document. Write one .md file per spec in data/drafts/{domain}/.

      Follow the spec struct schema strictly (read structs/spec.schema.yaml).

      For "create" tasks: write new spec from scratch.
      For "merge" tasks: read the existing spec from .agent/specs/,
        extract fresh content from the source, and write a draft that
        incorporates improvements while preserving valid existing content.
        Add a "Changes" section at the end noting what was updated.
    parallel: true
    parallel_key: "extraction-manifest.tasks[status=pending]"
    inputs:
      - path: .agent/workflows/astro-spec-extraction/data/extraction-manifest.json
        struct: extraction-manifest
      - path: .agent/workflows/astro-spec-extraction/structs/spec.schema.yaml
        inject: file
      - path: "{source}"
        inject: reference
      - path: ".agent/specs/{domain}/*.md"
        inject: file_if_exists
    outputs:
      - path: ".agent/workflows/astro-spec-extraction/data/drafts/{domain}/*.md"
        struct: spec

  - name: reconcile
    goal: >
      Review all draft specs:

      For "create" drafts: validate against source document —
        accuracy, completeness, correct source references.
      For "merge" drafts: compare old spec vs new draft —
        what changed, what improved, what was lost.
        Ensure the merged version is strictly better.

      Produce a reconciliation report with per-spec results:
        - status: created | merged | unchanged | conflict
        - For merged specs: list of changes made
        - For conflicts: what needs human decision
    inputs:
      - path: ".agent/workflows/astro-spec-extraction/data/drafts/**/*.md"
        struct: spec
      - path: ".agent/specs/**/*.md"
        inject: file_if_exists
      - path: "{source}"
        inject: reference
    outputs:
      - path: .agent/workflows/astro-spec-extraction/data/reconciliation-report.json
        struct: reconciliation-report

  - name: commit
    goal: >
      Finalize specs based on the reconciliation report:

      1. Copy all "created" and "merged" specs to .agent/specs/{domain}/
      2. Skip "conflict" specs — leave in data/drafts/ for human review
      3. Update .agent/specs/_index.json with spec metadata

      Write a summary report to the chat:
        - How many specs created, merged, unchanged, conflicts
        - For each merged spec: brief description of what changed
        - For conflicts: what needs manual resolution

      Do NOT commit to git.
    inputs:
      - path: .agent/workflows/astro-spec-extraction/data/reconciliation-report.json
      - path: ".agent/workflows/astro-spec-extraction/data/drafts/**/*.md"
      - path: ".agent/specs/_index.json"
        inject: file_if_exists
    outputs:
      - path: ".agent/specs/{domain}/*.md"
      - path: ".agent/specs/_index.json"
```
