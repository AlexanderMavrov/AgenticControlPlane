---
name: run-workflow
description: "Run a declarative multi-phase workflow from .agent/workflows/. Orchestrates step subagents, structural gates, delegation, and parallel execution."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
disable-model-invocation: true
---

# /run-workflow

Run a declarative multi-phase workflow defined in `.agent/workflows/`.

## Usage

```
/run-workflow <workflow-name> [--param value] [--resume]
```

## You Are the Orchestrator

When the user invokes this skill, you become the **workflow orchestrator**. For regular steps you spawn `workflow-step` agents — but for **delegation steps** (`delegate_to:`) you execute the delegated workflow yourself, WITHOUT spawning an agent.

> **`.agent/` is gitignored.** All workflow engine files live under `.agent/`. File search, directory listing, and glob tools will NOT find them. To **discover** files in `.agent/`, use `list_agent_files` MCP tool (bypasses gitignore). To **read** a known file, use the Read tool with the exact path. **NEVER use Glob or Grep** to search inside `.agent/`.
>
> **Fallback** (no MCP): `python -c "import glob; print('\n'.join(sorted(glob.glob('.agent/specs/**/*.md', recursive=True))))"` via Bash.

**Preferred:** Use `mcp__workflow_engine__*` tools for all file operations. If MCP tools are available, follow the sections below.

**Fallback:** If MCP tools are NOT in your tool list (server not running, not deployed, crashed), use the [Manual Fallback](#manual-fallback-no-mcp) section at the bottom of this document.

> **NEVER mix MCP and Manual paths.** Choose ONE at the start and use it for the entire run.

---

## Startup

### New Run

1. Call `workflow_resolve` to get workflow metadata (steps, params, gates, tools)
2. Parse `--param value` arguments. For missing required params → ask the user
3. Call `workflow_init` with name and resolved params → creates manifest, trace, run_token
4. **Check tools availability** — if `workflow_init` returns `tools.blocked: true`:
   - Show the user: `tools.block_message` (lists missing required tools)
   - **STOP** — do not proceed until the user resolves the issue
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

**`type: "delegation"`** → do NOT spawn an agent. See [Delegation](#delegation) below.

**`type: "regular"`** → check the `subagent` field:

- **`subagent: false`** → execute the step **yourself** (inline). Read the `goal`, resolve inputs, do the work, write outputs. Do NOT spawn an agent. After completing, proceed directly to step 5 (Complete the step). The gate hook will NOT fire — skip steps 3-4 entirely.

- **`subagent: true`** (or field absent) → compose an agent task from the returned text blocks:

1. **Goal** — `goal` field (already has params resolved)
2. **Params** — `params_text` field
3. **Inputs** — for each entry in `inputs`:
   - `inject: "file"` → read the file yourself and include full content in the prompt
   - `inject: "file_if_exists"` → read if exists, note if missing
   - `inject: "reference"` → tell agent: "Read this file yourself: `<path>`"
4. **Summaries** — `summaries_text` field (if non-empty)
5. **Outputs** — `outputs_text` field (includes inline struct schemas with format hints — pass verbatim to the agent)
6. **Spec check** — `spec_check_text` field (if non-empty)
7. **Constraints** — `constraints_text` field

### 2. Tool docs (added to the prompt by you)

`step_begin` returns a `tool_docs` block — append it verbatim to the agent task prompt **after** the goal, params, and inputs but **before** outputs/constraints. This tells the agent which workflow tools are available for this step.

- If `tool_docs` is empty, the step has no declared tools — skip this section.
- The block content depends on adapter:
  - **Claude Code per-step subagent** (default for subagent steps when `/init-workflow` has been run) — short affordance reminder; the subagent already has the tools whitelisted in its frontmatter and can call them directly as `mcp__workflow_tools__<wf>__<tool>`.
  - **Cursor or inline orchestrator step** — full inline documentation with command, schema fields, and example invocation.

> **Pre-generated subagents:** for each step with `subagent: true`, an init-time script has generated `.claude/agents/<workflow>-<step>/AGENT.md` with a strict `tools:` whitelist. The orchestrator does NOT modify these files at runtime. If the file is missing, `step_begin` returns `subagent_warning` telling you to run `/init-workflow <name>` and restart.

### 3. Spawn agent (only when `subagent` is true)

Use the **Agent tool** with `subagent_type` from the `step_begin` response:

- The `subagent_type` field contains either `<workflow>-<step>` (when the per-step subagent file exists) or `"workflow-step"` (fallback when init-workflow has not been run for this workflow).
- If `subagent_warning` is present, **surface it to the user** before spawning — explain that the per-step subagent file is missing and instruct them to run `/init-workflow <name>` followed by a CC restart so future runs do not need this fallback.
- **Cached subagent override (Phase 38, R4 finding):** when `subagent_warning` is present BUT the warned-about per-step subagent type (e.g. `tools-demo-analyze`) is **still visible in your current available agent list**, you SHOULD prefer it over the engine's `workflow-step` fallback. CC indexes `.claude/agents/` at session startup and does not invalidate the cache when files are deleted at runtime, so the cached per-step subagent still has the correct `tools:` whitelist with MCP tool access. The engine's warning is forward-looking — it tells you the file is missing on disk, which becomes a real blocker only after the next CC restart. Always still surface the warning to the user; the override only affects which `subagent_type` you actually pass to the Agent tool.
- If `step_begin` response includes a `model` field, pass it to the Agent tool: `Agent(subagent_type: <chosen_type>, model: result.model, prompt: ...)`
- If `model` is absent or null, omit the model parameter (agent inherits orchestrator's model)
- **Regular step**: spawn ONE agent with the composed task
- **Parallel step** (`is_parallel: true`): read the `parallel_key` file, resolve the list, spawn ALL agents in a SINGLE message (multiple Agent tool calls), all with the same `subagent_type`

### 4. Handle gate results

> **HOW THE GATE LOOP WORKS (Claude Code hook semantics)**
>
> When a `workflow-step` agent completes, the `SubagentStop` hook runs `gate-check.py`.
> - **Gate FAIL** → exit 2 + stderr feedback → same agent continues (another turn to fix) → hook fires again
> - **Gate PASS** → exit 0 → agent STOPS → control returns to YOU
> - **Retry limit** → exit 0 → agent stops → you read the result
>
> You do NOT see intermediate gate failures. The retry loop happens inside the agent session.
> The `SubagentStop` hook has `matcher: "workflow-step"` — only workflow agents trigger the gate.

After agent completes, call `step_collect_result`. Check `action`:

- **`PROCEED`** → gate passed
  - If `needs_semantic_gate` → verify outputs are correct and coherent
  - If `needs_human_gate` → present summary and ask user for approval
  - Then proceed to step 5

- **`RETRY_STEP`** → gate failed after retries. Spawn a **new** agent with original task + failure `details` from the response. Track retry count. If retries exceed `max_step_retries` → **STOP workflow.**

- **`STOP_WORKFLOW`** → gate infrastructure failure. **STOP immediately.** Report to user.

### 5. Complete the step

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
4. Run ALL steps of the delegated workflow (same step execution loop — each step spawns its own agents)
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

- **Agent error/abort**: STOP workflow. Report to user.
- **Gate loop exhausted**: `step_collect_result` returns `RETRY_STEP`. Re-spawn new agent up to `max_step_retries`.
- **Missing input files**: Error before spawning agent.

## Engine File Protection

**CRITICAL:** Neither you nor agents may modify:
`.agent/scripts/`, `.agent/docs/`, `.agent/tools/`, `.agent/workflows/templates/predefined/`, `.claude/skills/`, `.claude/rules/`, `.claude/agents/`

The `workflow-step` agent has a `PreToolUse` hook (`file-guard.py`) that enforces this automatically. Report bugs to the user — never fix engine files during a workflow run.

## Output File Ownership

**CRITICAL:** You (the orchestrator) must **NEVER write workflow output files** (drafts, specs, reports, data files). Only agents write outputs. If an agent misses an expected output:

1. **Do NOT fill the gap yourself** — you are the orchestrator, not a worker
2. **Retry the agent** with specific instructions about what was missed
3. If retries are exhausted, **report the gap** to the user — let them decide

Why: Orchestrator-written files bypass the gate validation loop. The gate validates agent outputs through the SubagentStop hook. Files you write silently skip this check.

---

## Parallel Steps

For `parallel: true` steps, manifest tracks each parallel task. On resume, only spawn agents for `pending` and `failed` tasks — skip `completed` ones. The step's gate runs after ALL parallel tasks complete.

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
| `.agent/scripts/gate-check.py` | Structural gate (called by SubagentStop hook) |

---

## Manual Fallback (No MCP)

Use this section ONLY if `mcp__workflow_engine__*` tools are not available.

> **`.agent/` is gitignored.** Always use **direct file reads** at exact paths.

### F1. Find the workflow definition

**Read the file directly** at these exact paths (first that exists wins):
1. `.agent/workflows/templates/my_workflows/<name>/workflow.yaml`
2. `.agent/workflows/templates/predefined/<name>/workflow.yaml`
3. `.agent/workflows/<name>/workflow.yaml` (legacy)

Note the `definition_dir` — structs are in `<definition_dir>/structs/`.

### F2. Create manifest + trace

Runtime dir: `.agent/workflows/<name>/` (NOT inside `templates/`).

Generate a `run_token` (any UUID).

**Timestamps:** All timestamps MUST be real values from the system clock. Use `date +%Y-%m-%dT%H:%M:%S%z` via Bash. NEVER use placeholder times.

Write `manifest.json`:
```json
{
  "workflow": "<name>",
  "workflow_version": "<version from yaml>",
  "run_id": "<name>-YYYYMMDD-HHMMSS",
  "run_token": "<generated UUID>",
  "status": "in_progress",
  "current_step": "<first step name>",
  "started_at": "<real ISO timestamp>",
  "updated_at": "<real ISO timestamp>",
  "params": { "<resolved params>" },
  "steps": { "<step1>": {"status": "pending"}, "<step2>": {"status": "pending"} }
}
```

Write `trace/<run_id>.trace.json`:
```json
{
  "trace_version": 1,
  "workflow": "<name>",
  "workflow_version": "<version>",
  "run_id": "<same as manifest>",
  "params": { "<resolved params>" },
  "gate_config": { "<gate config from yaml>" },
  "started_at": "<same as manifest>",
  "completed_at": null,
  "status": "in_progress",
  "steps": []
}
```

### F3. For each step — compose agent task

Read the step config from `workflow.yaml`.

> **DELEGATION CHECK (do this FIRST):**
> If step has `delegate_to:` → STOP here. Go to F6.
> If step has `subagent: false` → execute inline, no agent.

**Only for regular steps:**

Mark step as `in_progress` in manifest. Then compose the task prompt:

1. **Goal** — `step.goal` with `{param}` placeholders resolved
2. **Params** — list all params
3. **Inputs** — resolve `inject` modes, read files as needed
4. **Summaries** — include if `carry_forward: "summary"`
5. **Outputs** — list expected paths + struct names
6. **Spec check** — if `spec_check` not false
7. **Constraints** — "Write outputs ONLY to specified paths."

Spawn agent with `subagent_type: "workflow-step"`.

### F4. Handle gate results

> **If `subagent: false`:** Skip — no gate fires for inline steps.

After agent completes, read `.agent/workflows/<name>/gate-result.json`.

- **`passed: true`** → handle semantic/human gates → proceed to F5
- **`passed: false`** → spawn NEW agent with original task + failure details. Track retry count vs `max_step_retries`. If exhausted → STOP.
- **File not found** → STOP workflow.

### F5. Complete the step

1. **Inline validation** — if step has `subagent: false` AND outputs with `struct:`, run `python .agent/scripts/schema-validate.py <output-file> <schema-file>` for each. If any fail, fix the output and re-validate before proceeding.
2. Update manifest: status, completed_at, summary
3. Compute `duration_ms`
4. Write summary to `context/<step>.summary.md`
5. Apply `param_bindings` if present
6. Advance `current_step`
7. Write manifest

### F6. Delegation (manual)

1. Resolve params, find delegated workflow
2. Create separate manifest
3. Run all delegated steps (F3-F5 loop)
4. Apply parent `param_bindings`
5. Mark parent step completed

### F7. Finalize

> **CRITICAL — Trace file integrity**
> READ existing trace. PRESERVE all `steps` entries and `invocations`. Only ADD synthetic entries for MISSING steps. Only UPDATE top-level fields.

1. Update manifest: `status`, `completed_at`
2. Read trace file
3. Set `completed_at`, `status`
4. Compute `total_duration_ms`
5. Add synthetic entries for steps not in trace
6. Compute aggregates
7. Write back merged trace
