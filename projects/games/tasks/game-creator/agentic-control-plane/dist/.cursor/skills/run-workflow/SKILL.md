---
name: run-workflow
description: "Run a declarative multi-phase workflow from .agent/workflows/"
---

# /run-workflow

Run a declarative multi-phase workflow defined in `.agent/workflows/` (user-defined or predefined).

## Usage

```
/run-workflow <workflow-name> [--param value] [--resume]
```

Examples:
```
/run-workflow astro-spec-extraction
/run-workflow astro-spec-extraction --section "3.2.1 Message Queue Management"
/run-workflow spec-write-and-implement --component EditField --domain ui
/run-workflow astro-spec-extraction --resume
```

## You Are the Orchestrator

When the user invokes this skill, you become the **workflow orchestrator**. Your job is to read the workflow definition, manage state, spawn subagents for each step, handle gate results, and drive the workflow to completion.

**You do NOT execute steps yourself.** You spawn a subagent for each step. Each subagent works in isolated context — it only knows its goal, inputs, and summaries you provide.

---

## Startup

### New Run

1. Read the workflow definition. Search in this order:
   - `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` (user-defined)
   - `.agent/workflows/templates/predefined/<name>/workflow.yaml` (built-in)
   - `.agent/workflows/<name>/workflow.yaml` (runtime dir, legacy)
   - If not found in any location → error: "Workflow '<name>' not found."
2. Validate the workflow file exists and has required fields (`name`, `steps`)
3. **Parse params** from the user's command:
   - Match `--<param-name> "<value>"` arguments against workflow's `params:` list
   - For missing optional params: use `default` if defined, otherwise `null`
   - For missing required params: ask the user before proceeding
   - Store resolved params in the manifest for resume support
4. **Generate a run token** — a UUID v4 that uniquely identifies this workflow run. This token is used to link subagents to their workflow: only subagents whose task prompt contains the matching token will trigger gate validation. Without this, any subagent completing while a workflow is active would be incorrectly processed by `gate-check.py`.
   Generate it (Python-style): `import uuid; run_token = str(uuid.uuid4())`
   Or in the prompt: use any unique hex string (32+ chars).

5. Create `manifest.json` in the workflow directory:
   ```json
   {
     "workflow": "<name>",
     "workflow_version": <version>,
     "run_id": "<name>-<YYYYMMDD-HHmmss>",
     "run_token": "<uuid-v4>",
     "status": "in_progress",
     "current_step": "<first-step-name>",
     "started_at": "<ISO 8601>",
     "updated_at": "<ISO 8601>",
     "params": { "section": "3.2.1 Message Queue", "source": "docs/astro/..." },
     "steps": { ... }
   }
   ```
   Initialize each step with `"status": "pending"`.
6. Create `trace/<run-id>.trace.json` in the workflow directory:
   ```json
   {
     "trace_version": 1,
     "workflow": "<name>",
     "workflow_version": <version>,
     "run_id": "<name>-<YYYYMMDD-HHmmss>",
     "description": "<workflow.description — omit field if absent>",
     "context": { "carry_forward": "<value>" },
     "params": { ... },
     "param_defs": [
       { "name": "<param-name>", "description": "<param.description>", "required": <true|false> }
     ],
     "gate_config": { ... },
     "started_at": "<ISO 8601>",
     "completed_at": null,
     "status": "in_progress",
     "total_duration_ms": null,
     "total_messages": 0,
     "total_tool_calls": 0,
     "total_modified_files": 0,
     "steps": []
   }
   ```
   - `description`: copy from `workflow.description` in workflow.yaml (omit field if absent)
   - `context`: copy from `workflow.context` in workflow.yaml (omit field if absent)
   - `param_defs`: for each entry in `workflow.params`, include `name`, `description`, `required` (omit field if no params defined)
   - These three fields are static — written once at startup, never modified again

   The `run_id` format uses the workflow name and current timestamp (e.g., `spec-enforcement-20260314-103025`). Use the same `run_id` and `run_token` in the manifest so `gate-check.py` can find the trace file and verify subagent ownership.

   **Cursor subagentStop hook fields** (reference — these are captured automatically by `gate-check.py` into trace invocations):
   - `status`, `duration_ms`, `message_count`, `tool_call_count`, `modified_files` — execution metrics
   - `task` — the composed task prompt sent to the subagent (captured as `task_prompt` in trace)
   - `summary` — the subagent's own summary (captured as `subagent_summary` in trace)
   - `agent_transcript_path` — path to full agent transcript file (captured as `transcript_path` in trace)
   - `model` — which LLM model was used (captured in trace)
   - `loop_count` — gate-loop iteration count

   **Note:** The composed task prompt is automatically captured by Cursor's `task` field and written to the trace by `gate-check.py`. No separate logging by the orchestrator is needed.

   > **Trace ownership**: The orchestrator creates the initial trace file at startup (step 5 above) with metadata and an empty `steps` array. During execution, `gate-check.py` appends invocation entries via the subagentStop hook. The orchestrator touches the trace file again ONLY at **finalize time** (step 8) — to READ the existing file, UPDATE top-level fields, ADD synthetic entries for missing steps, and WRITE BACK the merged result. Never overwrite existing step invocations.
7. Tell the user: "Starting workflow `<name>` (version <V>). <description>. Params: <list>. N steps to execute."
8. Proceed to **Step Execution**.

### Resume (`--resume`)

1. Read `manifest.json` from the workflow directory
2. If it doesn't exist → error: "No manifest found. Start a new run without --resume."
3. Read `current_step` and its status:
   - `completed` → advance to the next pending step
   - `in_progress` → resume this step (read summaries from `context/`)
   - `failed` → ask user: "Step '<name>' failed previously. Retry or skip?"
4. Read all `context/<step>.summary.md` files for completed steps
5. Tell the user: "Resuming workflow `<name>` from step '<step>'. N steps remaining."
6. Proceed to **Step Execution**.

---

## Step Execution

For each step, in order:

### 1. Check if step should run

- If `status` is `completed` → skip, move to next
- If `status` is `skipped` → skip, move to next

### 2. Update manifest

```json
"<step-name>": { "status": "in_progress", "started_at": "<ISO 8601>" }
```
Set `current_step` to this step's name. Write manifest.

### 3. Compose subagent task

Build the task prompt for the subagent. Include ALL of these:

**a) Goal** — from `step.goal` in workflow.yaml

**b) Params** — from `manifest.params`:
- Include ALL resolved params in the prompt, clearly labeled
- Format: `**Params:** section = "3.2.1 Message Queue", source = "docs/astro/..."`
- For null/unset params: `**Params:** section = (not specified — full document analysis)`
- The goal's natural language instructions tell the subagent how to use each param

**c) Input files** — from `step.inputs`:
- `inject: "file"` → read file content and include it in the prompt
- `inject: "file_if_exists"` → include if exists, note if missing
- `inject: "reference"` → mention the path: "Read this file yourself: <path>"
- If `input.struct` is defined → mention the schema but don't validate here (gate validates outputs)
- **Resolve `{param}` placeholders** in paths: replace `{source}` with the actual param value

**d) Summaries** — include previous step summaries if carry_forward is enabled:
- Check per-step override first: if `step.carry_forward` is explicitly `false` → skip summaries for this step
- Otherwise, if `step.carry_forward` is `true` (or not set) AND `context.carry_forward` is `"summary"` → include summaries
- Default behavior: `carry_forward` defaults to `true` at step level, so all steps receive summaries unless explicitly opted out
- Read all `context/<completed-step>.summary.md` files
- Include them as: "Previous step '<name>' summary: <content>"

**e) Output expectations** — from `step.outputs`:
- Tell the subagent what files to create and where
- If `output.struct` is defined: "Output must follow the struct schema at structs/<name>.schema.yaml"
- Instruct: "Read the schema file to understand the expected format."

**f) Spec check** — if `step.spec_check` is `true` (default) or not set:
- Add these instructions to the subagent task:
  - "Before making code changes, read `.agent/specs/_registry.json` to find specs whose `implemented_by` files overlap with files you plan to modify."
  - "Read each relevant spec and verify your changes do NOT violate any requirement."
  - "If a violation is found: STOP and report the conflict in your summary (do NOT proceed with conflicting changes)."
  - "After completing changes, verify no specs were violated."
- If `step.spec_check` is explicitly `false`: do NOT add spec instructions.

**g) Constraints:**
- "Write outputs ONLY to the specified paths."
- "Do NOT modify files outside the output paths."
- "NEVER modify engine/infrastructure files: `.agent/scripts/`, `.agent/docs/`, `.agent/tools/`, `.cursor/skills/`, `.cursor/rules/`, `.cursor/hooks.json`. These are read-only system files. If you encounter errors caused by these files, report the problem in your summary — do NOT attempt to fix them."
- "When done, summarize what you did in 2-3 sentences."

**h) Run token** — ALWAYS append this at the very end of the task prompt:
```
<!--workflow:run_token:<run_token from manifest>-->
```
This invisible marker links the subagent to the active workflow run. `gate-check.py` uses it to verify that a completing subagent belongs to the current workflow — without it, the gate will NOT fire for this subagent. The HTML comment is invisible to the model and does not affect behavior.

### 4. Execute the step

**Delegation step** (`delegate_to: <workflow-name>`):

**IMPORTANT:** Do NOT spawn a subagent for a delegation step. YOU (the orchestrator) execute the delegated workflow directly — read its definition, create a nested manifest, and run each of its steps (spawning subagents for each step as usual). This avoids nested subagent limitations.

1. **Circular delegation check:** Before proceeding, verify the target workflow is NOT already in the delegation stack. Maintain a list of workflow names being executed (e.g., `["spec-write-and-implement"]`). If the target is already in the stack → abort with error: "Circular delegation detected: <parent> → <target>. Aborting."
2. Read the delegated workflow (search `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` then `.agent/workflows/templates/predefined/<name>/workflow.yaml`)
3. Resolve params: merge step-level params with delegated workflow's defaults. **Resolve `{param}` placeholders** in the delegation params from the parent's current `manifest.params` (which may have been updated by `param_bindings` from previous steps).
4. **Gate config:** The delegated workflow uses its OWN gate configuration. Parent gate config is NOT inherited — this is by design, since different workflows have different validation needs.
5. Create a **nested manifest** for the delegated workflow (separate from parent)
6. Run ALL steps of the delegated workflow sequentially (same execution rules as parent — each step spawns its own subagent)
7. When complete, record result in parent manifest: `"delegation_result": { "workflow": "<name>", "status": "completed" }`
8. Continue to next step in parent workflow

**Non-parallel step:** Spawn ONE subagent with the composed task. Wait for it to complete.

**Parallel step** (`parallel: true`):
1. Read the file referenced by `parallel_key` (e.g., `extraction-manifest.json`)
2. Resolve the key expression to get a list of items
3. For each item, compose a task prompt with the item's context (e.g., domain name)
4. Spawn ALL subagents in a SINGLE message (multiple tool calls) — they run concurrently
5. Wait for all to complete

### 5. Handle gate results

> **⛔ HOW THE GATE LOOP WORKS (Cursor hook semantics)**
>
> When a subagent completes, the `subagentStop` hook runs `gate-check.py`.
> - **Gate FAIL** → `gate-check.py` returns `followup_message` with failure details → **the same subagent continues** (gets another turn to fix its output) → hook fires again → repeat up to `max_gate_retries`
> - **Gate PASS** → `gate-check.py` returns `{}` (no followup) → **subagent STOPS** → control returns to YOU (the orchestrator)
> - **Retry limit reached** → `gate-check.py` returns `{}` → subagent stops → you read `gate-result.json`
>
> This means: **you do NOT receive a followup_message when the gate passes.** The subagent simply completes and returns to you. The gate retry loop happens entirely inside the subagent session — you never see intermediate failures.

After the subagent completes and returns control to you:

1. **Read `gate-result.json`** from the workflow directory. This file is written by `gate-check.py` after every gate check and contains the final result.

2. **Check `gate-result.json` contents:**

**If `passed: true`:**
- Structural gate passed. Now handle semantic/human gates if enabled:
  - If `semantic` gate enabled → read the step's outputs, verify they are correct, complete, and coherent with the goal. If semantic fail → spawn a new subagent to retry the step.
  - If `human` gate enabled → present summary and ask user for approval
  - If neither → proceed directly
- Continue to step 6 (param bindings) and step 7 (complete the step)

**If `passed: false`:**
- The subagent exhausted its gate retries and still failed
- Spawn a **new** subagent with the original task PLUS failure details from `gate-result.json`
- This is a **step retry** (fresh subagent, fresh context)
- Read `max_step_retries` from the step's `gate:` config (falls back to workflow-level `gate:`, default: 3)
- If retry count exceeds `max_step_retries` → **STOP the workflow.** Set manifest status to `"failed"` with reason: the gate is failing consistently after all retries.

**If `gate-result.json` is missing or stale:**
- This means `gate-check.py` did not execute — **gate infrastructure failure**
- Read `.agent/gate-check-invocations.log` — was the hook invoked at all?
- Read `.agent/gate-check-error.log` — did it crash?
- **STOP the workflow.** Set manifest status to `"failed"`. Report to the user.
- **Do NOT:** continue, retry, diagnose, or modify any files.

### 6. Apply param bindings (if defined)

After all gates pass, BEFORE completing the step, check if the step has `param_bindings:` in its workflow.yaml definition. If yes:

1. For each binding entry (e.g., `component: "data/approved-requirements.json::component"`):
   a. Split the value at `::` → file path + field path
   b. Resolve the file path relative to the workflow runtime directory
   c. Read the JSON file
   d. Extract the field value using dot notation (e.g., `metadata.name` → `data["metadata"]["name"]`)
   e. Update `manifest.params.<param_name>` with the extracted value
2. Write the updated manifest
3. Log which params were updated: "Param bindings applied: component='EditField', domain='ui'"

**This is critical for auto-discovery flows.** Without param bindings, subsequent steps would receive empty `{param}` placeholders and produce invalid file paths.

### 7. Complete the step

After all gates pass (and param bindings applied, if any):

1. Write summary to `context/<step-name>.summary.md`
   - Extract the summary from the subagent's final output — use the last 2-3 sentences where the subagent describes what it accomplished
   - If the subagent didn't provide a clear summary, generate one yourself from: the step's goal + gate results + list of files created/modified
   - Keep it concise (3-5 sentences max)
   - Format: plain text paragraph, no headers or bullet points
2. Update manifest:
   ```json
   "<step-name>": {
     "status": "completed",
     "completed_at": "<ISO 8601>",
     "gate_results": { ... },
     "summary": "<brief summary>"
   }
   ```
3. Move to the next step.

### 8. Workflow completion

> ⚠️ **CRITICAL — Trace file integrity**
> The trace file (`trace/<run-id>.trace.json`) is written by `gate-check.py` during the workflow.
> It contains rich per-step invocation data (message counts, tool calls, gate details, timing).
> At finalize you MUST:
> 1. **Read** the existing JSON file — do NOT start from an empty object
> 2. **Preserve** the existing `steps` array entries and their `invocations` — do NOT recreate or replace them
> 3. Only **add** synthetic entries for steps that are MISSING from the `steps` array (by name)
> 4. Only **update** top-level scalar fields (`completed_at`, `status`, `total_*`)
> 5. **Write back** the merged result
>
> Do NOT generate a new trace JSON from scratch. The existing step invocations are irreplaceable runtime data captured by the hook.

When all steps are completed:
1. Update manifest: `"status": "completed"`
2. **Finalize trace**: read `trace/<run-id>.trace.json` (the file already exists — created by `gate-check.py`), then:
   - **Fallback enrichment**: For each step that has `status: "completed"` in manifest but has NO invocations in the trace `steps` array (or the step entry is missing entirely), create a synthetic entry. Fill in everything you know from your own context — timestamps, file lists, summaries:
     ```json
     {
       "name": "<step-name>",
       "index": <step-index>,
       "status": "completed",
       "config": null,
       "goal": "<step.goal from workflow.yaml>",
       "inputs": null,
       "outputs": null,
       "started_at": "<from manifest step.started_at>",
       "completed_at": "<from manifest step.completed_at>",
       "duration_ms": "<compute from started_at to completed_at, in milliseconds>",
       "invocations": [{
         "iteration": 1,
         "retry_type": null,
         "completed_at": "<from manifest step.completed_at>",
         "duration_ms": "<compute from started_at to completed_at, in milliseconds>",
         "hook_status": "completed",
         "message_count": "<estimate from your context if possible, else 0>",
         "tool_call_count": "<estimate from your context if possible, else 0>",
         "modified_files": ["<list files you know the subagent created/modified>"],
         "subagent_id": null,
         "task_prompt": "<the composed task prompt you sent to the subagent>",
         "subagent_summary": "<the subagent's summary response>",
         "followup_message": null,
         "gate": { "type": "unknown", "passed": true },
         "note": "Synthetic — gate-check.py hook did not execute for this step"
       }],
       "retry_count": 0,
       "summary": "<from manifest step.summary>"
     }
     ```
     This ensures the trace captures as much data as possible even if the hook failed to fire. The `note` field marks it as synthetic so the viewer can distinguish it from real hook data.
   - Set `completed_at` to the current ISO 8601 timestamp
   - Set `status` to `"completed"` (or `"failed"` if any step failed)
   - Compute `total_duration_ms` = difference from `started_at` to `completed_at` in ms
   - Aggregate `total_messages` = sum of all invocation `message_count` values
   - Aggregate `total_tool_calls` = sum of all invocation `tool_call_count` values
   - Aggregate `total_modified_files` = count of unique files across all invocations
   - Also check `.agent/gate-check-error.log` — if it exists and has entries from this run, add a `"warnings"` array to the trace root with the error messages
   - Write the finalized trace file
3. Tell the user: "Workflow `<name>` completed. All N steps passed."
4. Provide a brief summary of what was accomplished.

---

## Parallel Steps: Detail

For `parallel: true` steps, manifest tracks each parallel task:

```json
"extract": {
  "status": "in_progress",
  "parallel_tasks": [
    { "key": "messaging", "status": "completed", "summary": "..." },
    { "key": "recovery", "status": "in_progress" },
    { "key": "rng", "status": "pending" }
  ]
}
```

**On resume**, only spawn subagents for `pending` and `failed` tasks — skip `completed` ones.

The step's gate runs after ALL parallel tasks complete (not after each individual one).

---

## Error Handling

### Gate failure at any level — STOP the workflow

The gate system is the **quality guarantee** of every workflow. If any gate in the chain fails to execute — structural (script), semantic (LLM), or human — the workflow MUST stop. This is a foundational principle: **a gate that doesn't run is worse than a gate that fails.** A failed gate gives feedback and allows retry. A gate that doesn't run produces unvalidated output with false confidence.

The cause may be internal (bug in gate-check.py, schema error) or **external** (Cursor hook not firing, network issue, LLM service down, user unavailable for human gate). The orchestrator does not need to know the cause — it only needs to detect that the expected gate did not complete, and stop.

**When to detect:**
- Subagent completes but NO `followup_message` received AND `gate-result.json` is missing or stale
- Semantic gate cannot be performed (LLM error, context too large)
- Human gate cannot be presented (UI issue, unexpected state)
- Any unexpected state in the gate chain that prevents validation from completing

**What to do:**
1. **STOP the workflow immediately.** Do NOT proceed to the next step.
2. Set manifest status to `"failed"` with reason describing what was expected and what happened (e.g., `"Gate did not complete — structural gate did not execute for step 'extract'."`)
3. Report to the user:
   - Which step was affected
   - Which gate did not complete (structural / semantic / human)
   - That the workflow has been stopped
   - That the cause must be identified and resolved before re-running
4. **Do NOT:** retry the step, skip the gate, continue to the next step, diagnose the cause, or modify any files.

**Why this is strict:** The workflow's entire value comes from its gates. Without them, it is just unvalidated LLM output — no better than asking the LLM directly. Skipping a gate "just this once" defeats the purpose of having a workflow engine at all.

### Other error scenarios

- **Subagent error/abort:** The structural gate (`gate-check.py`) only runs on completed subagents — if a subagent errors or aborts, you will NOT receive a `followup_message`. **STOP the workflow.** Log the error in the manifest and report to the user. The subagent erroring is an infrastructure-level failure — do not retry automatically.
- **Gate loop exhausted:** When `max_gate_retries` is reached, `gate-check.py` stops returning `followup_message` and writes `gate-result.json`. Read it — if gate still failed, re-spawn a new subagent up to `max_step_retries`. If step retries also exhausted → **STOP the workflow.**
- **`gate-result.json`:** Written by `gate-check.py` after every gate check. Contains `step`, `passed`, `checks`, `failures`, `details`, `loop_count`. Always check this file when a subagent completes without a followup message.
- **Missing files:** If a required input file doesn't exist → error before spawning subagent
- **Schema not found:** If a struct schema is referenced but doesn't exist → warn and skip structural gate for that output
- **Output directories:** Subagents create output directories as needed when writing files. The orchestrator does NOT pre-create `data/`, `context/`, or `trace/` directories — they are created on first write. The workflow runtime directory (`.agent/workflows/<name>/`) is created by the orchestrator at startup when writing `manifest.json`.

## Engine File Protection

**CRITICAL: Neither the orchestrator nor any subagent may modify engine infrastructure files.** The following paths are READ-ONLY during workflow execution:

- `.agent/scripts/` — gate scripts, validators
- `.agent/docs/` — engine documentation
- `.agent/tools/` — viewer, utilities
- `.agent/workflows/templates/predefined/` — built-in workflow definitions
- `.cursor/skills/` — skill definitions
- `.cursor/rules/` — rule files
- `.cursor/hooks.json` — hook configuration

If these files contain bugs, the orchestrator must **report the problem to the user** and wait for instructions. Attempting to fix engine files during a workflow run risks corrupting the engine for all future runs.

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/workflows/templates/my_workflows/<name>/workflow.yaml` | User-defined workflow definition (read) |
| `.agent/workflows/templates/predefined/<name>/workflow.yaml` | Built-in workflow definition (read) |
| `.agent/workflows/<name>/manifest.json` | Runtime state (read/write) |
| `.agent/workflows/<name>/gate-result.json` | Last gate check result (read — written by gate-check.py) |
| `.agent/workflows/<name>/trace/<run-id>.trace.json` | Execution trace (created by orchestrator, appended by gate-check.py) |
| `.agent/workflows/<name>/structs/*.schema.yaml` | I/O schemas (read) |
| `.agent/workflows/<name>/context/*.summary.md` | Step summaries (write) |
| `.agent/specs/` | Behavioral specs (read/write by spec workflows) |
| `.agent/scripts/gate-check.py` | Structural gate (called by hook) |
| `.agent/scripts/schema-validate.py` | Schema validator (called by gate-check) |
| `.agent/docs/` | Engine documentation (reference) |
