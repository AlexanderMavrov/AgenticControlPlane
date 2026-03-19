# Trace System

The trace system captures execution metrics for every workflow run, enabling
post-hoc analysis and visualization.

## Overview

When a workflow runs, the system automatically creates a **trace file** — a JSON
log that records per-step timing, token counts, gate results, and modified files.
The trace is written incrementally: the orchestrator creates the initial file at
workflow start, and `gate-check.py` appends an entry after each subagent
completion. The orchestrator finalizes the trace when the workflow completes.

Traces can be visualized using the built-in **Trace Viewer** — a self-contained
HTML file that opens in any browser with no dependencies.

## Storage

Traces are stored alongside the workflow's runtime data:

```
.agent/workflows/<name>/
  manifest.json          ← runtime state
  gate-result.json       ← latest gate output
  trace/
    <run-id>.trace.json  ← execution trace
  data/                  ← step outputs
  context/               ← carry-forward summaries
```

The `run_id` format is: `<workflow-name>-<YYYYMMDD-HHmmss>`
(e.g., `spec-enforcement-20260314-103025`).

Multiple traces can coexist in the `trace/` directory from different runs.

## Trace JSON Format

```json
{
  "trace_version": 1,
  "workflow": "spec-enforcement",
  "workflow_version": 2,
  "run_id": "spec-enforcement-20260314-103025",
  "params": {
    "component": "EditField",
    "instruction": "add max length validation"
  },
  "gate_config": {
    "structural": true,
    "semantic": true,
    "human": false,
    "max_gate_retries": 5,
    "max_step_retries": 3
  },
  "started_at": "2026-03-14T10:30:25+02:00",
  "completed_at": "2026-03-14T10:45:12+02:00",
  "status": "completed",
  "total_duration_ms": 887000,
  "total_messages": 42,
  "total_tool_calls": 87,
  "total_modified_files": 5,
  "steps": [
    {
      "name": "check-specs",
      "index": 0,
      "status": "completed",
      "config": {
        "spec_check": false,
        "subagent": true,
        "gate": null
      },
      "goal": "Find the primary spec for {component} in .agent/specs/...",
      "inputs": [
        { "path": ".agent/specs/_registry.json", "inject": "reference" }
      ],
      "outputs": [
        { "path": "data/spec-context.json", "struct": "spec-context" }
      ],
      "started_at": "2026-03-14T10:30:25+02:00",
      "completed_at": "2026-03-14T10:33:10+02:00",
      "duration_ms": 165000,
      "invocations": [
        {
          "iteration": 1,
          "retry_type": null,
          "completed_at": "2026-03-14T10:33:10+02:00",
          "duration_ms": 165000,
          "hook_status": "completed",
          "message_count": 8,
          "tool_call_count": 15,
          "modified_files": ["data/spec-context.json"],
          "task_prompt": "Find the primary spec for EditField in .agent/specs/...",
          "subagent_summary": "Found EditField spec with 5 requirements.",
          "transcript_path": null,
          "model": "claude-sonnet-4-20250514",
          "gate": {
            "type": "structural",
            "passed": true,
            "checks": 1,
            "failures": 0,
            "details": []
          }
        }
      ],
      "retry_count": 0,
      "summary": null
    },
    {
      "name": "implement",
      "index": 1,
      "status": "completed",
      "config": { "spec_check": false, "subagent": true, "gate": null },
      "goal": "Implement the code change, respecting ALL specs...",
      "inputs": [
        { "path": "data/spec-context.json", "inject": "file", "struct": "spec-context" }
      ],
      "outputs": [
        { "path": "data/implementation-report.json", "struct": "implementation-report" }
      ],
      "started_at": "2026-03-14T10:33:12+02:00",
      "completed_at": "2026-03-14T10:40:45+02:00",
      "duration_ms": 453000,
      "invocations": [
        {
          "iteration": 1,
          "retry_type": null,
          "completed_at": "2026-03-14T10:37:00+02:00",
          "duration_ms": 228000,
          "hook_status": "completed",
          "message_count": 12,
          "tool_call_count": 25,
          "modified_files": ["src/components/EditField.tsx"],
          "gate": {
            "type": "structural",
            "passed": false,
            "checks": 3,
            "failures": 1,
            "details": ["Missing field: files_modified[].relationship"]
          }
        },
        {
          "iteration": 2,
          "retry_type": "gate",
          "completed_at": "2026-03-14T10:40:45+02:00",
          "duration_ms": 225000,
          "hook_status": "completed",
          "message_count": 5,
          "tool_call_count": 8,
          "modified_files": ["data/implementation-report.json"],
          "gate": {
            "type": "structural",
            "passed": true,
            "checks": 3,
            "failures": 0,
            "details": []
          }
        }
      ],
      "retry_count": 1,
      "summary": "Implemented max length validation for EditField. Modified EditField.tsx to enforce 30-char limit with red error message."
    }
  ]
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `trace_version` | number | Schema version (currently `1`) |
| `workflow` | string | Workflow name |
| `workflow_version` | number | Workflow version from definition |
| `run_id` | string | Unique run identifier |
| `description` | string (optional) | Workflow description copied from workflow.yaml at startup |
| `context` | object (optional) | Context config from workflow.yaml (e.g., `{ "carry_forward": "summary" }`) |
| `params` | object | Workflow params as passed at invocation (runtime values) |
| `param_defs` | array (optional) | Param definitions from workflow.yaml: `name`, `description`, `required` per entry |
| `gate_config` | object | Workflow-level gate configuration from workflow.yaml |
| `started_at` | string | ISO 8601 timestamp — workflow start |
| `completed_at` | string\|null | ISO 8601 timestamp — workflow end (null if still running) |
| `status` | string | `"completed"`, `"failed"`, `"paused"`, or `"in_progress"` |
| `total_duration_ms` | number\|null | Total wall-clock duration (null if still running) |
| `total_messages` | number | Sum of all invocation message_count |
| `total_tool_calls` | number | Sum of all invocation tool_call_count |
| `total_modified_files` | number | Count of unique files modified across all steps |
| `warnings` | array (optional) | Diagnostic warnings from `gate-check-error.log` (added at finalize if log exists) |

### Gate Config Fields

| Field | Type | Description |
|-------|------|-------------|
| `structural` | boolean | Whether structural gate is enabled |
| `semantic` | boolean | Whether semantic gate is enabled |
| `human` | boolean | Whether human gate is enabled |
| `max_gate_retries` | number | Max gate-loop retries per step (default: 5) |
| `max_step_retries` | number | Max new subagent spawns per step (default: 3) |

### Step Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Step name from workflow.yaml |
| `index` | number | Zero-based step index |
| `status` | string | `"completed"`, `"failed"`, `"in_progress"`, `"pending"` |
| `config` | object | Step configuration snapshot |
| `config.spec_check` | boolean | Whether spec enforcement is active for this step |
| `config.subagent` | boolean | Whether step runs as a subagent |
| `config.gate` | object\|null | Step-level gate overrides (null = use workflow defaults) |
| `goal` | string\|null | Goal text from workflow.yaml — the task description sent to the subagent |
| `inputs` | array\|null | Input definitions from workflow.yaml (path, inject mode, struct) |
| `outputs` | array\|null | Output definitions from workflow.yaml (path, struct schema) |
| `started_at` | string\|null | First invocation start time |
| `completed_at` | string\|null | Last invocation completion time |
| `duration_ms` | number\|null | Total step duration (including retries) |
| `invocations` | array | List of subagent invocations (one per attempt) |
| `retry_count` | number | Number of retries (invocations.length - 1) |
| `summary` | string\|null | Context carry-forward summary (if available) |

### Invocation Fields

Each invocation represents one subagent execution attempt. Multiple invocations
occur due to retries. The `retry_type` field distinguishes the two retry mechanisms:

- **`"gate"`** — The subagent received a `followup_message` from `gate-check.py`
  and retried in-place (same subagent session, gate-loop). Up to `max_gate_retries`.
- **`"step"`** — The gate loop was exhausted; the orchestrator spawned a **new**
  subagent with the same task. Up to `max_step_retries`.
- **`null`** — First attempt (not a retry).

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | number | 1-based iteration number |
| `retry_type` | string\|null | `null` (first attempt), `"gate"` (gate-loop retry), `"step"` (new subagent) |
| `completed_at` | string | ISO 8601 timestamp |
| `duration_ms` | number | Subagent execution time |
| `hook_status` | string | `"completed"` or `"errored"` (from hook input) |
| `message_count` | number | Number of messages in the subagent session |
| `tool_call_count` | number | Number of tool calls made |
| `modified_files` | array | List of files modified by the subagent |
| `subagent_id` | string\|null | Cursor subagent ID — use to group gate retries under their parent subagent |
| `task_prompt` | string\|null | The composed task prompt sent to the subagent (from Cursor `task` field) |
| `subagent_summary` | string\|null | The subagent's own summary of what it did (from Cursor `summary` field) |
| `transcript_path` | string\|null | Path to the full agent transcript file (from Cursor `agent_transcript_path`) |
| `model` | string\|null | LLM model used for this invocation (from Cursor `model` field) |
| `followup_message` | string\|null | The gate feedback sent back to the subagent (explains retry reason) |
| `note` | string\|null | Diagnostic note (e.g., "Synthetic — hook did not fire") |
| `gate` | object | Gate result for this invocation |

### Invocation Grouping

Invocations within a step can be **grouped by `subagent_id`**:

- Multiple invocations sharing the same `subagent_id` are gate retries within
  a single subagent session (same context, `retry_type: "gate"`).
- A new `subagent_id` means a fresh subagent was spawned (`retry_type: "step"`).
- The `followup_message` on a gate retry invocation shows the gate feedback
  that triggered the retry (e.g., "STRUCTURAL GATE FAILED... Fix the issues").
- The `task_prompt` on the first invocation of a subagent shows the composed
  input context from the orchestrator.

### Gate Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Gate type: `"structural"`, `"semantic"`, `"human"` |
| `passed` | boolean | Whether the gate passed |
| `checks` | number | Number of structural checks performed |
| `failures` | number | Number of failed checks |
| `details` | array | Failure detail messages |

## Data Flow

```
Orchestrator                    gate-check.py
    │                                │
    ├─ Create manifest.json          │
    ├─ Create trace/<run-id>.trace.json (header + empty steps)
    │                                │
    ├─ Launch subagent (step 1)      │
    │   └─ subagent completes ──────►│
    │                                ├─ Read hook stdin (duration, messages, etc.)
    │                                ├─ Validate outputs (structural gate)
    │                                ├─ Write gate-result.json
    │                                ├─ Append trace entry (step + invocation)
    │                                └─ Return followup_message
    ├─ (orchestrator continues)      │
    │   ...                          │
    ├─ All steps complete            │
    ├─ Finalize trace (aggregates, status, completed_at)
    └─ Set manifest status = completed
```

## Trace Viewer

The viewer is located at `.agent/tools/trace-viewer.html`. Open it directly in
any browser — no server or build tools needed.

### Usage

1. Open `trace-viewer.html` in a browser
2. Load a trace file via the "Load Trace" button or drag-drop
3. Explore: workflow overview, timeline, step details (click to expand)

### Features

- **Workflow card**: name, version, status, run ID, description, parameters (with tooltips), gate config (ON/OFF chips with click-to-show explanations), context settings, and run stats
- **Global timeline bar**: proportional step durations, click any segment to scroll to that step
- **Step cards** (collapsible):
  - **Step Config**: effective gate config (merged workflow defaults + step overrides). Step overrides are marked with a dashed outline. Click any chip for tooltip explaining the setting.
  - **Goal text**: the step's goal from workflow.yaml
  - **Inputs/Outputs**: file paths, injection modes, struct schemas
  - **Timing**: start, end, duration, retry count
  - **Subagent Timeline (Gantt chart)**: for steps with 2+ parallel subagents, shows a visual timeline of when each subagent started/finished. Color-coded bars: green = gate passed, amber = retry (gate failed, not final), red = final fail. Phantom invocations shown as dimmed gray markers. Duration labels on every bar segment. Click any bar to scroll to the corresponding attempt in Invocations.
  - **Invocations**: each attempt is a distinct visual block with colored background (amber = failed retry, green = passed). Each block contains: meta info (model, ID), task prompt (expandable), subagent summary (expandable), gate section (visually separated with colored border — red for fail, green for pass, showing check/failure counts and expandable details), and feedback arrow (dashed amber box showing `followup_message` sent to the next attempt).
  - **Modified files**: list of files changed across all attempts
  - **Summary**: carry-forward summary (if available)
- **Config tooltips**: hover shows a floating `?` indicator, click shows a popup with a detailed explanation
- **Dark/light theme**: toggle in the header
- **No dependencies**: pure HTML/CSS/JS, works offline

### Trace Viewer and Optional Fields

The viewer gracefully handles missing optional fields (`description`, `context`, `param_defs`):
- If `description` is absent, the description section is not shown
- If `context` is absent, the context column is not shown
- If `param_defs` is absent, params are shown as key/value rows without descriptions

## Troubleshooting

### Empty invocations / total_messages: 0

If trace steps show no invocations or zero message counts:

1. **Check `.agent/gate-check-error.log`** — `gate-check.py` logs diagnostic errors here
2. **Common cause: UTF-8 BOM** — Windows Cursor may prepend a BOM (`\xEF\xBB\xBF`) to stdin JSON. `gate-check.py` handles this by reading raw bytes via `sys.stdin.buffer.read()`, stripping the 3-byte BOM at the bytes level, then decoding as UTF-8. If you see "Invalid hook input JSON" errors, verify the BOM fix is deployed.
3. **Hook not firing** — Verify `.cursor/hooks.json` has `subagentStop` configured and the hook command path is correct.
4. **Orchestrator overwrite** — If the orchestrator rewrites the trace from scratch at finalize instead of merging, invocations are lost. SKILL.md contains explicit warnings to prevent this.

### Quick hook diagnostic

Use the `hook-diagnostic` predefined workflow (3 steps: probe-hook, probe-struct, probe-retry — structural gates enabled) to test hook firing, schema validation, and the gate retry loop:

```
/run-workflow hook-diagnostic --message "test"
```

Then check `.agent/gate-check-error.log` for any errors.

## Run Token Verification

Each workflow run generates a UUID `run_token` (stored in `manifest.json`). The orchestrator injects it into every subagent's task prompt as an invisible HTML comment: `<!--workflow:run_token:<uuid>-->`.

When `gate-check.py` runs on `subagentStop`, it checks for this token **before** any workflow lookup:

1. No token in prompt → exit silently (not a workflow subagent)
2. Token found but no active workflow → exit silently
3. Token found but doesn't match manifest's `run_token` → exit silently (wrong/old run)
4. Token matches → proceed with structural gate validation

This prevents "zombie workflow" false matches (interrupted workflow + unrelated subagent), phantom invocations from casual chat during an active run, and cross-run collisions.

## Phantom Invocations

Cursor fires the `subagentStop` hook for orchestrator turns too, not just real subagents. These are filtered at two levels:

**Level 1 — Format check** (before token verification):
- `subagent_id` starting with `"toolu_"` (tool-use ID, not a UUID)
- Empty `task` field (no spawn prompt)

**Level 2 — Run token** (after format check):
- No `<!--workflow:run_token:...-->` in the task prompt → not a workflow subagent

Both levels produce a silent `{}` exit — no trace entries, no gate results. The Trace Viewer shows phantom invocations (that made it into the trace from older runs without run_token) as dimmed gray markers in the Gantt timeline.

## Responsibility Matrix

| File | Created by | Updated by | Read by |
|------|-----------|------------|---------|
| `manifest.json` | Orchestrator (at workflow start) | Orchestrator (step status, params, finalize) | gate-check.py (current step lookup) |
| `trace.json` | Orchestrator (initial structure) | gate-check.py (appends invocations); Orchestrator (finalizes: aggregates, status, completed_at) | Trace Viewer |
| `gate-result.json` | gate-check.py (after each gate check) | gate-check.py (overwritten each invocation) | Orchestrator (after subagent returns) |
