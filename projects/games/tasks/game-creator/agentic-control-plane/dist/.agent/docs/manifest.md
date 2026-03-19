# manifest.json — Format Reference

The manifest is the workflow's runtime state file. It is **auto-generated** by the orchestrator — you never write it manually. This document is a read reference so you understand the format when reading or resuming workflows.

Lives at: `.agent/workflows/<name>/manifest.json`

## Structure

```json
{
  "workflow": "string",
  "workflow_version": 1,
  "run_id": "string",
  "params": {},
  "status": "string",
  "current_step": "string",
  "started_at": "ISO 8601",
  "updated_at": "ISO 8601",
  "steps": {
    "<step-name>": {
      "status": "string",
      "started_at": "ISO 8601",
      "completed_at": "ISO 8601",
      "gate_results": {
        "structural": { "passed": true, "checks": 3, "failures": 0, "details": [] },
        "semantic": { "passed": true, "notes": "string" },
        "human": { "passed": true, "approved_by": "user" }
      },
      "summary": "string",
      "parallel_tasks": []
    }
  }
}
```

## Field Reference

### Top-level

| Field | Type | Description |
|-------|------|-------------|
| `workflow` | string | Name from `workflow.yaml` |
| `workflow_version` | number | Version from `workflow.yaml` |
| `run_id` | string | Unique run identifier (format: `<name>-<YYYYMMDD-HHmmss>`, e.g., `spec-enforcement-20260314-103025`) |
| `params` | object | Resolved workflow parameters (from user args + defaults + `param_bindings`). Used for resume and `{param}` interpolation. |
| `status` | string | Overall workflow status |
| `current_step` | string | Name of the step currently executing (or last executed) |
| `started_at` | ISO 8601 | When this run started |
| `updated_at` | ISO 8601 | Last manifest update |

### Workflow status values

| Status | Meaning |
|--------|---------|
| `in_progress` | Workflow is running |
| `completed` | All steps passed |
| `failed` | A step failed and was not recovered |
| `paused` | Stopped mid-run (e.g., user interrupted, session ended) |

### Step entry

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Step status (see below) |
| `started_at` | ISO 8601 | When step execution began |
| `completed_at` | ISO 8601 | When step passed all gates |
| `gate_results` | object | Results from each gate layer |
| `summary` | string | Brief description of what was done (for context carry-forward) |
| `parallel_tasks` | array | Only for parallel steps — per-task status |

### Step status values

| Status | Meaning |
|--------|---------|
| `pending` | Not started yet |
| `in_progress` | Currently executing |
| `completed` | Passed all gates |
| `failed` | Failed and not recovered |
| `skipped` | Explicitly skipped (e.g., via resume decision) |

### Parallel tasks entry

For steps with `parallel: true`, each parallel task has its own status:

```json
{
  "key": "messaging",
  "status": "completed",
  "started_at": "ISO 8601",
  "completed_at": "ISO 8601",
  "summary": "Created 12 spec files"
}
```

## Gate Results

Each gate layer reports independently:

```json
{
  "structural": {
    "passed": true,
    "checks": 5,
    "failures": 0,
    "details": []
  },
  "semantic": {
    "passed": true,
    "notes": "All domains covered, cross-references valid."
  },
  "human": {
    "passed": true,
    "approved_by": "user"
  }
}
```

On failure, `details` contains specific issues:

```json
{
  "structural": {
    "passed": false,
    "checks": 5,
    "failures": 2,
    "details": [
      "Missing required field 'spec_id' in data/drafts/recovery/REC-003.md",
      "File data/drafts/rng/RNG-001.md is below minimum size (200 bytes)"
    ]
  }
}
```

## Resume Behavior

When the orchestrator resumes a workflow:
1. Reads `manifest.json`
2. Skips steps with `status: "completed"`
3. For `in_progress` steps: reads `context/<step>.summary.md` from completed sub-tasks, resumes remaining
4. For `failed` steps: shows error, asks user to retry or skip
5. For parallel steps: checks each `parallel_tasks[].status`, resumes only `pending` or `failed` items

## Example

```json
{
  "workflow": "astro-spec-extraction",
  "workflow_version": 1,
  "run_id": "astro-spec-extraction-20260313-100000",
  "status": "in_progress",
  "current_step": "extract",
  "started_at": "2026-03-13T10:00:00+02:00",
  "updated_at": "2026-03-13T12:30:00+02:00",
  "steps": {
    "plan": {
      "status": "completed",
      "started_at": "2026-03-13T10:00:00+02:00",
      "completed_at": "2026-03-13T10:15:00+02:00",
      "gate_results": {
        "structural": { "passed": true, "checks": 3, "failures": 0, "details": [] },
        "semantic": { "passed": true, "notes": "All 12 domains identified correctly." },
        "human": { "passed": true, "approved_by": "user" }
      },
      "summary": "Identified 12 domains with ~100 extractable rules. Created extraction-manifest.json."
    },
    "extract": {
      "status": "in_progress",
      "started_at": "2026-03-13T10:20:00+02:00",
      "parallel_tasks": [
        { "key": "messaging", "status": "completed", "summary": "Created 12 spec files" },
        { "key": "recovery", "status": "in_progress", "summary": "Created 5 of ~8 specs" },
        { "key": "rng", "status": "pending" }
      ]
    },
    "validate": { "status": "pending" },
    "commit": { "status": "pending" }
  }
}
```
