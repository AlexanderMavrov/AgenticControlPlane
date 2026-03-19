# spec-audit — Read-Only Compliance Audit

Scans source code against behavioral specs and produces a structured violation report. **NEVER modifies any files** — pure read-only QA workflow.

## Why this workflow exists

`spec-enforcement` checks specs during implementation (write path). `spec-audit` checks specs after the fact (read path) — periodic QA, pre-release audits, compliance checks. It answers: **"How compliant is our codebase right now?"**

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `domain` | No | *(all)* | Filter to specific domain (e.g., `recovery`) |
| `component` | No | *(all)* | Filter to specific component (e.g., `EditField`) |
| `spec_id` | No | *(all)* | Filter to single spec (e.g., `ui/EditField`). Most specific — overrides domain/component |
| `severity_filter` | No | `all` | `all`, `must`, `must+should` |
| `suggest_fixes` | No | `false` | Include fix suggestions in report (text only, no actual edits) |
| `include_unregistered` | No | `false` | Also search codebase for files not in `_registry.json` |

## Usage

```
# Audit all specs
/run-workflow spec-audit

# Audit only MUST requirements
/run-workflow spec-audit --severity_filter must

# Audit a specific domain
/run-workflow spec-audit --domain recovery

# Audit a single spec with fix suggestions
/run-workflow spec-audit --spec_id "recovery/GameRecovery" --suggest_fixes true

# Audit with codebase search for unregistered files
/run-workflow spec-audit --include_unregistered true

# Resume after interruption
/run-workflow spec-audit --resume
```

## Steps

### Step 1: DISCOVER (human gate)

Resolves the audit scope: which specs to check and which source files to scan.

**Key behaviors:**
- Reads `_index.json` for the spec catalog, `_registry.json` for implementation mappings
- Applies filters: `spec_id` > `component` > `domain` > all (most specific wins)
- Applies `severity_filter` to determine which requirement levels to check
- Groups specs by domain for parallel fan-out
- Flags specs with no registry mapping or no implementation files

**Output:** `data/discovery-plan.json` — audit scope with per-domain spec lists, file paths, active filters, warnings.

**Gate:** Human — user reviews the scope and confirms before scanning begins.

### Step 2: SCAN (parallel by domain)

Each subagent checks all in-scope specs for its assigned domain against the implementing source code.

**Key behaviors:**
- Parallel fan-out: one subagent per domain
- For each spec: reads the spec file + all implementing source files
- For each requirement at active severity level: determines compliance status
- Compliance statuses: `compliant`, `violation`, `partial`, `unverifiable`
- Violations include: file path, line number, code snippet, explanation, impact rating
- If `suggest_fixes` is enabled: includes concrete fix descriptions per violation
- If `include_unregistered` is enabled and spec has no registry mapping: searches codebase for matching files

**Output:** `data/scans/{domain}-scan-result.json` — per-spec, per-requirement compliance details.

### Step 3: REPORT

Consolidates all domain scan results into a single actionable audit report.

**Key behaviors:**
- Aggregates statistics: total specs, requirements, compliance rate
- Groups violations by severity (MUST first), then by impact (critical > moderate > minor)
- Produces domain-level summaries with compliance rates
- Generates prioritized recommendations
- Prints a human-readable summary to chat

**Output:** `data/audit-report.json` — full structured report with all findings.

## Gate Configuration

| Step | Structural | Semantic | Human |
|------|-----------|----------|-------|
| DISCOVER | yes | yes | **yes** |
| SCAN | yes | yes | no |
| REPORT | yes | yes | no |

## Compliance Statuses

| Status | Meaning |
|--------|---------|
| `compliant` | Code satisfies the requirement |
| `violation` | Code clearly violates the requirement |
| `partial` | Code partially satisfies (some cases handled, others not) |
| `unverifiable` | Cannot determine from static analysis alone |

## Impact Ratings (for violations)

| Impact | Meaning |
|--------|---------|
| `critical` | Breaks core behavior |
| `moderate` | Degrades functionality |
| `minor` | Cosmetic or edge case |

## Output Structure

```
.agent/workflows/spec-audit/data/
  discovery-plan.json              # Audit scope (from DISCOVER)
  scans/
    recovery-scan-result.json      # Per-domain results (from SCAN)
    messaging-scan-result.json
    ...
  audit-report.json                # Final consolidated report (from REPORT)
```

## Edge Cases

**No specs found:** DISCOVER warns at human gate. REPORT produces empty report with "No specs to audit" message.

**No _registry.json:** All specs marked `no_registry_mapping`. With `include_unregistered=false` (default): requirements reported as `unverifiable`. With `include_unregistered=true`: subagents search codebase for matching files.

**Missing implementation files:** Reported as `unverifiable` with suggestion to run `/run-workflow registry-sync`.

**Filter matches nothing:** DISCOVER catches at human gate, shows available specs/domains for user to choose from.

**All compliant:** REPORT shows 100% compliance rate. No violations section.

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 3-step workflow (DISCOVER, SCAN, REPORT) |
| `structs/discovery-plan.schema.yaml` | Audit scope schema |
| `structs/scan-result.schema.yaml` | Per-domain scan results schema |
| `structs/audit-report.schema.yaml` | Final consolidated report schema |
| `README.md` | This file |
