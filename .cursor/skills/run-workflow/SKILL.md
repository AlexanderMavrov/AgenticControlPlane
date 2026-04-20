---
name: run-workflow
description: "Run a declarative multi-phase workflow (doc-spec-extraction, spec-write, spec-audit, spec-enforcement, create-workflow, or custom). Orchestrates subagents via MCP workflow engine with structural gates, trace, and parallel execution."
---

# /run-workflow

Run a declarative multi-phase workflow defined in `.agent/workflows/`.

## Usage

```
/run-workflow <workflow-name> [--param value] [--resume]
```

## You Are the Orchestrator

When the user invokes this skill, you become the **workflow orchestrator**. For regular steps you spawn subagents — but for **delegation steps** (`delegate_to:`) you execute the delegated workflow yourself, WITHOUT spawning a subagent.

> **⚠️ `.agent/` is gitignored (and may be behind symlinks).** File search, directory listing, and glob tools will NOT find files inside `.agent/`. To **discover** files, use `list_agent_files` MCP tool (uses Python os.walk — bypasses both gitignore and symlink issues). To **read** a known file, use the Read tool with the exact path. **NEVER use Glob or Grep** to search inside `.agent/`. When verifying step outputs, **trust the gate result** — gate-check.py already validated the files using Python, not IDE tools.
>
> **Fallback** (no MCP): `python -c "import glob; print('\n'.join(sorted(glob.glob('.agent/specs/**/*.md', recursive=True))))"` via Bash/terminal.

### ⛔ MANDATORY: Use MCP Workflow Engine Tools

**Before doing ANYTHING, verify MCP tools are available** by calling `workflow_resolve`. If it succeeds → use MCP for the ENTIRE run. The engine provides: `workflow_resolve`, `workflow_init`, `step_begin`, `step_collect_result`, `step_complete`, `workflow_finalize`.

**Only if `workflow_resolve` fails** (server not running, tool not found) → use the [Manual Fallback](#manual-fallback-no-mcp) section at the bottom. Manual Fallback is a **last resort** — it produces no trace file, gate validation is partial, and audit history is lost.

> **⚠️ NEVER mix MCP and Manual paths.** Choose ONE at the start and use it for the entire run. If you call `workflow_init` via MCP, use MCP for ALL subsequent calls (`step_begin`, `step_complete`, `workflow_finalize`). If MCP tools are not available, use Manual Fallback for everything. Mixing creates duplicate state (two manifests, incomplete traces) that corrupts the workflow history.

### ⛔ Anti-Patterns — NEVER Do These

- **NEVER call per-step subagent types directly** (e.g., `doc-spec-extraction-analyze`, `doc-spec-extraction-extract`). These are internal subagent definitions managed by the engine. Use `step_begin` to get the task prompt, then spawn a generic subagent with it.
- **NEVER write `manifest.json` manually** when MCP is available. The engine manages manifest lifecycle (state transitions, timestamps, run_token, step tracking).
- **NEVER skip `step_collect_result`** after a subagent completes. This is where gate results are read, retry decisions are made, and trace is verified.
- **NEVER advance to the next step without calling `step_complete`**. This writes the summary, applies param_bindings, and transitions manifest state.
- **NEVER assume gate passed** without evidence. If `gate-result.json` is absent or stale, something went wrong — STOP and report.

---

## Startup

### New Run

1. Call `workflow_resolve` to get workflow metadata (steps, params, gates, tools)
2. Parse `--param value` arguments. For missing required params → ask the user
3. Call `workflow_init` with name and resolved params → creates manifest, trace, run_token
4. **Check tools availability** — if `workflow_init` returns `tools.blocked: true`:
   - Show the user: `tools.block_message` (lists missing required tools/MCP servers)
   - **STOP** — user must enable the missing MCP servers in Cursor settings before continuing
   - If `tools.missing` contains only `required: false` items → warn but continue
5. Tell the user: "Starting workflow `<name>` (version <V>). <description>. N steps."
6. Proceed to **Step Execution**

### Resume (`--resume`)

1. Call `workflow_resume` → returns current state, summaries, next step
2. If error → report to user
3. Based on `current_step_status`:
   - `completed` → call `step_complete` then advance
   - `in_progress` → resume this step
   - `failed` → ask user: "Retry or skip?"
4. Tell the user: "Resuming from step '<step>'. N steps remaining."
5. Proceed to **Step Execution**

---

## Step Execution

For each step, in order:

### 1. Begin the step

Call `step_begin` with workflow name and step name. Check `type` in response:

**`type: "delegation"`** → do NOT spawn a subagent. See [Delegation](#delegation) below.

**`type: "regular"`** → check the `subagent` field:

- **`subagent: false`** → execute the step **yourself** (inline). Read the `goal`, resolve inputs, do the work, write outputs. Do NOT spawn a subagent. After completing, proceed directly to step 4 (Complete the step). The gate hook will NOT fire — skip step 3 entirely.

- **`subagent: true`** (or field absent) → compose a subagent task from the returned text blocks:

1. **Goal** — `goal` field (already has params resolved)
2. **Params** — `params_text` field
3. **Inputs** — for each entry in `inputs`:
   - `inject: "file"` → read the file yourself and include full content in the prompt
   - `inject: "file_if_exists"` → read if exists, note if missing
   - `inject: "reference"` → tell subagent: "Read this file yourself: `<path>`"
4. **Summaries** — `summaries_text` field (if non-empty)
5. **Outputs** — `outputs_text` field (includes inline struct schemas with format hints — pass verbatim to the agent)
6. **Spec check** — `spec_check_text` field (if non-empty)
7. **Constraints** — `constraints_text` field
8. **Run token** — `run_token_text` field (append at the end if present — used for traceability, not required for gate matching)

### 2. Spawn subagent (only when `subagent` is true)

- **Regular step** (`type: "regular"`): spawn ONE subagent with the composed task
- **Parallel step** (`type: "parallel"`): `step_begin` returns lightweight branch metadata — each entry has `branch_index`, `prompt_file`, `spawn_prompt`, `subagent_type`, `model`, and a brief `summary`. For each branch, spawn a subagent using **`branch.spawn_prompt`** as the task prompt. Spawn ALL subagents in a SINGLE message. **Do NOT resolve parallel_key yourself** — the engine has already done it. **Do NOT read the prompt files yourself** — the subagent reads its own file.

### 3. Handle gate results

> **⛔ HOW THE GATE LOOP WORKS (Cursor hook semantics)**
>
> When a subagent completes, the `subagentStop` hook runs `gate-check.py`.
> - **Gate FAIL** → same subagent continues (another turn to fix) → hook fires again
> - **Gate PASS** → subagent STOPS → control returns to YOU
> - **Retry limit** → subagent stops → you read the result
>
> You do NOT see intermediate gate failures. The retry loop happens inside the subagent session.

After subagent completes, call `step_collect_result`. Check `action`:

- **`PROCEED`** → gate passed
  - If `needs_semantic_gate` → verify outputs are correct and coherent
  - If `needs_human_gate` → present summary and ask user for approval
  - Then proceed to step 4

- **`RETRY_STEP`** → gate failed after retries. Spawn a **new** subagent with original task + failure `details` from the response. Track retry count. If retries exceed `max_step_retries` → **STOP workflow.**

- **`STOP_WORKFLOW`** → gate infrastructure failure. **STOP immediately.** Report to user.

### 4. Complete the step

Call `step_complete` with workflow name, step name, and a brief summary (2-3 sentences).

The tool handles: manifest update, summary file, param_bindings, next step.

- **`action: "FIX_AND_RETRY"`** → output validation failed for an inline step (`subagent: false`). Read `validation_errors`, fix the output files, then call `step_complete` again.
- `workflow_done: false` → proceed to `next_step`
- `workflow_done: true` → proceed to [Finalization](#finalization)

---

## Delegation

When `step_begin` returns `type: "delegation"`:

1. **Check `goal`** — if it contains conditional logic (skip conditions), evaluate it first
2. **Circular delegation check** — verify target is not already in the execution stack
3. Call `workflow_init` for the delegated workflow using `resolved_params`
4. Run ALL steps of the delegated workflow (same step execution loop — each step spawns its own subagents)
5. When complete, call `workflow_finalize` for the delegated workflow
6. Call `step_complete` on the **parent** workflow's delegation step — the tool applies `param_bindings` (reads from delegated workflow's output dir)
7. Continue parent workflow

**Important:** Delegation is NOT a subagent. YOU execute the delegated workflow directly. Max one level deep (A→B OK, A→B→C prohibited).

---

## Finalization

Call `workflow_finalize` with workflow name. The tool sets manifest status, finalizes trace with aggregates and synthetic entries.

Tell the user: "Workflow `<name>` completed. All N steps passed." + brief summary.

---

## Error Handling

### Gate failure at any level — STOP

If any gate fails to execute (`STOP_WORKFLOW` from `step_collect_result`):
1. **STOP immediately** — do NOT continue
2. Report to user: which step, which gate, what happened
3. Do NOT: retry, skip, diagnose, or modify files

### Other errors

- **Subagent error/abort**: STOP workflow. Report to user.
- **Gate loop exhausted**: `step_collect_result` returns `RETRY_STEP`. Re-spawn new subagent up to `max_step_retries`.
- **Missing input files**: Error before spawning subagent.

## Engine File Protection

**CRITICAL:** Neither you nor subagents may modify:
`.agent/scripts/`, `.agent/docs/`, `.agent/tools/`, `.agent/workflows/templates/predefined/`, `.cursor/skills/`, `.cursor/rules/`, `.cursor/hooks.json`

Report bugs to the user — never fix engine files during a workflow run.

## Output File Ownership

**CRITICAL:** You (the orchestrator) must **NEVER write workflow output files** (drafts, specs, reports, data files). Only subagents write outputs. If a subagent misses an expected output:

1. **Do NOT fill the gap yourself** — you are the orchestrator, not a worker
2. **Retry the subagent** with specific instructions about what was missed
3. If retries are exhausted, **report the gap** to the user — let them decide

Why: Orchestrator-written files bypass the gate validation loop. The gate validates subagent outputs through the subagentStop hook. Files you write silently skip this check.

---

## Parallel Steps

For `parallel: true` steps:

1. `step_begin` returns `type: "parallel"` with lightweight `branches` metadata (engine resolves `parallel_key` automatically)
2. Each branch's **full task prompt** is written to a file (e.g., `data/prompts/branch_0.md` inside the workflow runtime dir). The orchestrator does NOT compose prompts from fields — it tells each subagent to read its prompt file. These files persist after workflow completion for debugging.
3. Each branch has **isolated output paths** (`_branch_0/`, `_branch_1/`, ...) — subagents write to their own directories
4. Gate-check validates **only the branch's files** (not the entire output directory) — no cross-branch feedback
5. Spawn ALL branches in a single message, one subagent per branch entry
6. `step_complete` automatically **merges** branch dirs to the final location and cleans up `_branch_*/`
7. On resume, only spawn subagents for `pending` and `failed` branches — skip `completed` ones

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` | User-defined workflow (read) |
| `.agent/workflows/templates/predefined/<name>/workflow.yaml` | Built-in workflow (read) |
| `.agent/workflows/<name>/manifest.json` | Runtime state (managed by MCP tools) |
| `.agent/workflows/<name>/gate-result.json` | Gate check result (written by gate-check.py) |
| `.agent/workflows/<name>/trace/<run-id>.trace.json` | Execution trace (managed by MCP tools + gate-check.py) |
| `.agent/workflows/<name>/context/*.summary.md` | Step summaries (managed by MCP tools) |
| `.agent/specs/` | Behavioral specs (read/write by spec workflows) |
| `.agent/scripts/gate-check.py` | Structural gate (called by hook) |

---

## Manual Fallback (No MCP)

> **⚠️ LAST RESORT ONLY.** Use this section ONLY after verifying that `workflow_resolve` MCP tool call fails. Manual orchestration produces **no trace file**, gate validation is **partial** (structural only, no engine-managed semantic/human gates), and **audit history is lost**. If MCP tools are available but you use Manual Fallback anyway, you are breaking the workflow contract.

Use this section ONLY if `mcp__workflow_engine__*` tools are not available. This replicates what the MCP server does, using file tools directly.

> **⚠️ `.agent/` is gitignored.** File search and directory listing tools will NOT find it. Always use **direct file reads** at exact paths — never search or list directories to discover `.agent/` contents.

### F1. Find the workflow definition

**Read the file directly** at these exact paths (first that exists wins):
1. `.agent/workflows/templates/my_workflows/<name>/workflow.yaml`
2. `.agent/workflows/templates/predefined/<name>/workflow.yaml`
3. `.agent/workflows/<name>/workflow.yaml` (legacy)

Use a direct file read tool for each path — do NOT use file search, directory listing, or glob tools (they skip gitignored paths). Note the `definition_dir` (where the file lives) — structs are in `<definition_dir>/structs/`.

### F2. Create manifest + trace

Runtime dir: `.agent/workflows/<name>/` (NOT inside `templates/`).

Generate a `run_token` (any UUID, e.g., `550e8400-e29b-41d4-a716-446655440000`).

**Timestamps:** All timestamps MUST be real values from the system clock. Use a tool call to get the current time (e.g., `date +%Y-%m-%dT%H:%M:%S%z` or equivalent). NEVER use placeholder times like `12:00:00` or round numbers — these corrupt the trace history and make debugging impossible.

Write `manifest.json`:
```json
{
  "workflow": "<name>",
  "workflow_version": <version from yaml>,
  "run_id": "<name>-YYYYMMDD-HHMMSS",
  "run_token": "<generated UUID>",
  "status": "in_progress",
  "current_step": "<first step name>",
  "started_at": "<real ISO timestamp from system clock>",
  "updated_at": "<real ISO timestamp from system clock>",
  "params": { "<resolved params>" },
  "steps": { "<step1>": {"status": "pending"}, "<step2>": {"status": "pending"}, ... }
}
```

Write `trace/<run_id>.trace.json`:
```json
{
  "trace_version": 1,
  "workflow": "<name>",
  "workflow_version": "<version from yaml>",
  "run_id": "<same run_id as manifest>",
  "params": { "<same resolved params as manifest>" },
  "gate_config": { "<gate config from workflow.yaml>" },
  "started_at": "<same timestamp as manifest>",
  "description": "<workflow description from yaml, if present>",
  "context": { "<context config from workflow.yaml, if present>" },
  "param_defs": [ "<param definitions from workflow.yaml, if present>" ],
  "completed_at": null,
  "status": "in_progress",
  "total_duration_ms": null,
  "steps": []
}
```

### F3. For each step — compose subagent task

Read the step config from `workflow.yaml`.

> **⛔ DELEGATION CHECK (do this FIRST, before anything else):**
> If step has `delegate_to:` → **STOP here. Do NOT compose a subagent task. Do NOT spawn an agent.** Go directly to F6.
> If step has `subagent: false` (without `delegate_to:`) → the orchestrator executes the goal directly, no subagent.

**Only for regular steps (no `delegate_to:`, `subagent` is not `false`):**

Mark step as `in_progress` in manifest: set `steps.<name>.status = "in_progress"`, `steps.<name>.started_at` (real ISO timestamp), `manifest.current_step = "<name>"`, `manifest.updated_at` (same timestamp). Write manifest. Then compose the task prompt from these blocks:

1. **Goal** — `step.goal` with `{param}` placeholders resolved from `manifest.params`
2. **Params** — list all params and values
3. **Inputs** — for each entry in `step.inputs`:
   - `inject: "file"` → read file, include content in prompt
   - `inject: "file_if_exists"` → include if exists, skip if missing
   - `inject: "reference"` → tell subagent the path, it reads itself
   - Resolve `{param}` placeholders in paths
4. **Summaries** — if `context.carry_forward: "summary"` (and step doesn't override with `carry_forward: false`), include content of `context/<prev_step>.summary.md` for each completed previous step
5. **Outputs** — list expected output paths + struct names (tell subagent to read the schema)
6. **Spec check** — if `step.spec_check` is not `false`: "Before code changes, read `.agent/specs/_registry.json`, find affected specs, verify no violations."
7. **Constraints** — "Write outputs ONLY to specified paths. Do NOT modify engine files. Summarize in 2-3 sentences when done."
8. **Run token** — append `<!--workflow:run_token:<UUID>-->` at the very end

Spawn subagent with the composed task.

### F4. Handle gate results

> **If step has `subagent: false`:** The gate hook does NOT fire for inline steps (no subagent → no `subagentStop` event). **Skip this entire section** — proceed directly to F5.

**Only for subagent steps (`subagent: true` or default):**

After subagent completes, read `.agent/workflows/<name>/gate-result.json`.

- **`passed: true`** → check if step has `gate.semantic: true` or `gate.human: true`, handle accordingly → proceed to F5
- **`passed: false`** → spawn a NEW subagent (step retry) with original task + failure details. Track retry count vs `gate.max_step_retries` (default 3). If exhausted → STOP workflow.
- **File not found** → gate didn't fire → STOP workflow immediately.

### F5. Complete the step

1. **Inline validation** — if step has `subagent: false` AND outputs with `struct:`, run `python .agent/scripts/schema-validate.py <output-file> <schema-file>` for each. If any fail, fix the output and re-validate before proceeding.
2. Update manifest: `steps.<name>.status = "completed"`, `steps.<name>.completed_at` (real timestamp from system clock), `steps.<name>.summary`, `manifest.updated_at` (same timestamp)
3. Compute `steps.<name>.duration_ms`: if `steps.<name>.started_at` exists, compute milliseconds between started_at and completed_at
4. Write summary to `context/<step>.summary.md`
5. If step has `param_bindings` — for each binding `"<file>::<field>"`:
   - Read the JSON file (relative to runtime dir, or delegated workflow dir for delegation steps)
   - Extract the field value (dot notation)
   - Update `manifest.params.<param_name>`
6. Advance `manifest.current_step` to the next step
6. Write updated manifest

### F6. Delegation (manual)

If step has `delegate_to:`:
1. Resolve `{param}` placeholders in the step's `params` block
2. Find the delegated workflow definition (same search order as F1)
3. Create a **separate** manifest in `.agent/workflows/<delegated-name>/`
4. Run all steps of the delegated workflow (F3-F5 loop)
5. On completion — apply `param_bindings` from the parent step (paths resolve relative to **delegated** workflow's runtime dir)
6. Mark the parent step as completed

### F7. Finalize

> **⚠️ CRITICAL — Trace file integrity**
> The trace file may already contain step entries with invocation data written by `gate-check.py` during the workflow. This data is irreplaceable.
> 1. **READ** the existing trace JSON — do NOT start from an empty object
> 2. **PRESERVE** all existing `steps` array entries and their `invocations` — do NOT recreate or replace them
> 3. Only **ADD** synthetic entries for steps that are **MISSING** from the `steps` array (by name)
> 4. Only **UPDATE** top-level scalar fields (`completed_at`, `status`, `total_*`)
> 5. **WRITE BACK** the merged result

1. Update manifest: `status: "completed"` (or `"failed"` if not all steps completed), `completed_at` (real timestamp from system clock), `updated_at` (same). If status is `"failed"`, mark any `in_progress` steps as `"failed"` with `completed_at`.
2. **Read** the trace file (`trace/<run_id>.trace.json`) — it already exists
3. Set `completed_at`, `status` in the trace
4. Compute `total_duration_ms` from `started_at` to now
5. **Fallback enrichment** — collect the names of steps already in the trace `steps` array. For each step in manifest that has `status: "completed"` or `"failed"` but is **NOT already in the trace** (by name), add a synthetic entry:
   ```json
   {
     "name": "<step>",
     "index": <definition order in workflow.yaml>,
     "status": "<from manifest>",
     "config": null,
     "goal": "<goal text from workflow.yaml step definition>",
     "inputs": null,
     "outputs": null,
     "started_at": "<from manifest>",
     "completed_at": "<from manifest>",
     "duration_ms": <from manifest, or compute from started_at/completed_at, or null>,
     "summary": "<from manifest>",
     "invocations": [],
     "retry_count": 0,
     "note": "Synthetic — no hook invocations recorded"
   }
   ```
6. Compute aggregates from **all** step entries (existing + synthetic): `total_messages`, `total_tool_calls`, `total_modified_files` (sum from invocations), `total_step_duration_ms` (sum of all step `duration_ms` values)
7. **Write back** the merged trace — preserving all existing hook data
