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
  gate-result.json       ← latest gate output (includes run_token for stale detection)
  trace/
    <run-id>.trace.json  ← execution trace
  data/                  ← step outputs
    prompts/             ← parallel branch prompt files (persist for debugging)
      branch_0.md
      branch_1.md
  context/               ← carry-forward summaries
```

The `run_id` format is: `<workflow-name>-<YYYYMMDD-HHmmss>-<4hex>`
(e.g., `spec-enforcement-20260314-103025-a3f1`).

Multiple traces can coexist in the `trace/` directory from different runs.

### gate-result.json

Written by `gate-check.py` after each gate invocation. Read by `step_collect_result` MCP tool.

| Field | Type | Description |
|-------|------|-------------|
| `step` | string | Step name this result belongs to |
| `passed` | boolean | Whether structural gate passed |
| `checks` | number | Total structural checks performed |
| `failures` | number | Number of failed checks |
| `details` | array | Failure descriptions |
| `loop_count` | number | Gate retry iteration (0 = first attempt) |
| `run_token` | string | Manifest run_token at time of writing — used by `step_collect_result` to detect **stale results** from previous runs/sessions (token mismatch → stale → PROCEED with safety net) |
| `branch_results` | array\|null | Per-branch validation results for parallel steps (CC only — when branch identity is unknown). Each entry: `{branch_index, passed, checks, failures, details}` |

### Gate Verification

Gate verification is **manifest-based** (unified for both CC and Cursor). `gate-check.py` checks `manifest.status == "in_progress"` — no dependency on `run_token` in the subagent's task prompt. Phantom filtering (Cursor only) uses `subagent_id` prefix and empty `task` field.

## Trace JSON Format

```json
{
  "trace_version": 1,
  "workflow": "spec-enforcement",
  "workflow_version": 2,
  "run_id": "spec-enforcement-20260314-103025-a3f1",
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
  "total_mcp_calls": 7,
  "mcp_calls": [
    {"timestamp": "2026-03-14T10:30:20+02:00", "tool": "workflow_resolve", "duration_ms": 12, "success": true, "workflow": "spec-enforcement", "summary": "Resolved spec-enforcement v2, 3 steps"},
    {"timestamp": "2026-03-14T10:30:24+02:00", "tool": "workflow_init", "duration_ms": 35, "success": true, "workflow": "spec-enforcement", "summary": "Initialized run spec-enforcement-20260314-103025-a3f1"},
    {"timestamp": "2026-03-14T10:30:25+02:00", "tool": "step_begin", "duration_ms": 18, "success": true, "workflow": "spec-enforcement", "step": "check-specs", "summary": "Prepared check-specs (regular, subagent: true)"}
  ],
  "total_tool_calls_proxy": 2,
  "tool_calls": [
    {"tool": "count_lines", "arguments": {"file_path": "src/Widget.tsx"}, "timestamp": "2026-03-14T10:31:05+02:00", "duration_ms": 45, "exit_code": 0, "success": true, "output_length": 82},
    {"tool": "transform_json", "arguments": {"input": "data/analysis.json", "operation": "enrich"}, "timestamp": "2026-03-14T10:31:10+02:00", "duration_ms": 32, "exit_code": 0, "success": true, "output_length": 156}
  ],
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
      "summary": null,
      "prompt_files": null
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
| `total_step_duration_ms` | number | Sum of `duration_ms` across all steps (from manifest step entries) |
| `warnings` | array (optional) | Diagnostic warnings from `gate-check-error.log` (added at finalize if log exists) |
| `total_mcp_calls` | number (optional) | Count of MCP tool calls logged during the run (added at finalize) |
| `mcp_calls` | array (optional) | Ordered list of MCP tool call entries (see MCP Call Fields below) |
| `total_tool_calls_proxy` | number (optional) | Count of proxy tool calls from `_workflow_tools` (added at finalize) |
| `tool_calls` | array (optional) | Ordered list of proxy tool call entries (see Proxy Tool Call Fields below) |

### MCP Call Fields

Each entry in the `mcp_calls` array represents one MCP tool call made by the orchestrator
to the workflow engine during the run. Logged automatically by the MCP server and embedded
into the trace at finalize.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 timestamp — when the call was made |
| `tool` | string | MCP tool name (e.g., `"step_begin"`, `"workflow_init"`) |
| `duration_ms` | number | Server-side execution time in milliseconds |
| `success` | boolean | Whether the call succeeded |
| `workflow` | string (optional) | Workflow name (from call arguments) |
| `step` | string (optional) | Step name (from call arguments, when relevant) |
| `summary` | string (optional) | Human-readable 1-line summary of the call result |
| `error` | string (optional) | Error message (present only when `success: false`) |

### Proxy Tool Call Fields

Each entry in the `tool_calls` array represents one script tool call made through the
generated `_workflow_tools_<name>.py` MCP proxy. The proxy logs calls to `tool-calls.json`
in the workflow runtime directory; `workflow_finalize` merges them into the trace and
cleans up the log file.

| Field | Type | Description |
|-------|------|-------------|
| `tool` | string | Tool name (e.g., `"count_lines"`, `"transform_json"`) |
| `arguments` | object | Arguments passed to the tool call |
| `timestamp` | string | ISO 8601 timestamp — when the call was made |
| `duration_ms` | number | Execution time of the subprocess in milliseconds |
| `exit_code` | number | Subprocess exit code (0 = success) |
| `success` | boolean | Whether the call succeeded (`exit_code == 0`) |
| `output_length` | number (optional) | Length of stdout output in characters (success only) |
| `error` | string (optional) | Error message — stderr content or timeout/exception info |

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
| `retry_count` | number | Number of actual retries (gate + step). Excludes branch invocations. |
| `summary` | string\|null | Context carry-forward summary (if available) |
| `prompt_files` | array\|null | Paths to per-branch prompt files for parallel steps (e.g., `["data/prompts/branch_0.md", ...]`). Self-contained files that each subagent reads. Persist after completion for debugging. `null` for non-parallel steps. |
| `note` | string\|null | Present only on synthetic entries (see below) |

> **Synthetic entries:** Steps that don't fire the `subagentStop` hook (delegation steps, inline steps with `subagent: false`, or manual fallback runs) have no invocation data from `gate-check.py`. At finalization, the engine adds **synthetic entries** for these steps with `invocations: []` and a `note` field explaining why (e.g., `"Delegation step (delegate_to: spec-enforcement)"` or `"Synthetic — no hook invocations recorded"`). The `config`, `goal`, `inputs`, `outputs` fields may be `null` in synthetic entries.

### Invocation Fields

Each invocation represents one subagent execution attempt. Multiple invocations
occur due to retries. The `retry_type` field distinguishes the two retry mechanisms:

- **`null`** — First attempt (not a retry).
- **`"gate"`** — The subagent received a `followup_message` from `gate-check.py`
  and retried in-place (same subagent session, gate-loop). Up to `max_gate_retries`.
- **`"step"`** — The gate loop was exhausted; the orchestrator spawned a **new**
  subagent with the same task. Up to `max_step_retries`.
- **`"branch"`** — A parallel branch invocation. When a step has `parallel_key`,
  the engine spawns multiple subagents (one per branch item). Each branch after the
  first is recorded with `retry_type: "branch"`. These are NOT retries — they are
  independent parallel executions. Detected by `<!--workflow:branch:N-->` marker
  in the task prompt.

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | number | 1-based iteration number |
| `retry_type` | string\|null | `null` (first attempt), `"gate"` (gate-loop retry), `"step"` (new subagent), `"branch"` (parallel branch) |
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
| `model` | string\|null | LLM model used for this invocation (actual, may differ from the `model` hint in workflow.yaml). Cursor: from hook payload `model` field. Claude Code: extracted from subagent transcript (`message.model`). |
| `token_usage` | object\|null | Token counts: `{input: number, output: number}`. Present only when transcript data is available (Claude Code). Summed across all assistant messages in the subagent session. |
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
Orchestrator                    gate-check.py          MCP Server (workflow-engine.py)
    │                                │                        │
    ├─ workflow_resolve ────────────────────────────────────►│ (logged)
    ├─ workflow_init ──────────────────────────────────────►│ (logged)
    │   └─ Creates manifest.json + trace/<run-id>.trace.json │
    │                                │                        │
    ├─ step_begin ─────────────────────────────────────────►│ (logged)
    ├─ Launch subagent (step 1)      │                        │
    │   └─ subagent completes ──────►│                        │
    │                                ├─ Read hook stdin        │
    │                                ├─ Validate outputs       │
    │                                ├─ Write gate-result.json │
    │                                ├─ Append trace entry     │
    │                                └─ Return followup_message│
    ├─ step_collect_result ────────────────────────────────►│ (logged)
    ├─ step_complete ──────────────────────────────────────►│ (logged)
    │   ...                          │                        │
    ├─ All steps complete            │                        │
    ├─ workflow_finalize ──────────────────────────────────►│ (logged)
    │   └─ Embeds mcp_calls[] into trace, computes aggregates │
    └─ Set manifest status = completed                        │
```

## Trace Viewer

The viewer is located at `.agent/tools/trace-viewer.html`. Open it directly in
any browser — no server or build tools needed.

### Usage

1. Open `trace-viewer.html` in a browser
2. Load a trace file via the "Load Trace" button or drag-drop
3. Explore: workflow overview, timeline, step details (click to expand)

### Features

- **Workflow card**: name, version, status, run ID, description, parameters (with tooltips), gate config (ON/OFF chips with click-to-show explanations), context settings, and run stats (including MCP call count when available)
- **Orchestration panel** (collapsible): shows all MCP tool calls made during the run — timestamp, tool name, step context, duration, and summary. Color-coded by tool type (blue = init/finalize, purple = step_begin/complete, green = step_complete, amber = collect_result, gray = resolve/list). Hidden for older traces without `mcp_calls` data.
- **Global timeline bar**: proportional step durations, click any segment to scroll to that step
- **Step cards** (collapsible):
  - **Step Config**: effective gate config (merged workflow defaults + step overrides). Step overrides are marked with a dashed outline. Click any chip for tooltip explaining the setting.
  - **Goal text**: the step's goal from workflow.yaml
  - **Inputs/Outputs**: file paths, injection modes, struct schemas
  - **Timing**: start, end, duration, retry count
  - **Model badge**: step header shows the LLM model(s) used (purple badge). For Claude Code, extracted from subagent transcript; for Cursor, from hook payload.
  - **Subagent Timeline (Gantt chart)**: shows a visual timeline of subagent execution. Displayed for steps with parallel subagents, gate/step retries, or any invocation with duration data. Color-coded bars: green = gate passed, amber = retry (gate failed, not final), red = final fail. Phantom invocations shown as dimmed gray markers. Duration labels on every bar segment. Click any bar to scroll to the corresponding attempt in Invocations.
  - **Invocations**: each attempt is a distinct visual block with colored background (amber = failed retry, green = passed). Each block contains: meta info (model, ID, token usage), task prompt (expandable), subagent summary (expandable), gate section (visually separated with colored border — red for fail, green for pass, showing check/failure counts and expandable details), and feedback arrow (dashed amber box showing `followup_message` sent to the next attempt).
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
| `trace.json` | Orchestrator (initial structure) | gate-check.py (appends invocations); MCP server (embeds mcp_calls at finalize); Orchestrator (finalizes: aggregates, status, completed_at) | Trace Viewer |
| `gate-result.json` | gate-check.py (after each gate check) | gate-check.py (overwritten each invocation) | Orchestrator (after subagent returns) |
| `mcp_calls` (in trace) | MCP server (in-memory log during run) | MCP server (embedded into trace at workflow_finalize) | Trace Viewer |
