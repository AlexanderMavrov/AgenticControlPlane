---
name: spec-with-workflows
description: "Create and audit behavioral specs via workflow engine (with gates, manifest, trace)"
---

# /spec-with-workflows

Create and audit behavioral specs using the full workflow engine. Provides structural gates, manifest tracking, human approval, and traceable execution.

## Usage

```
/spec-with-workflows add <name>                # Create or update a spec (via spec-write workflow)
/spec-with-workflows add                       # Create a spec with auto-discovery (via spec-write workflow)
/spec-with-workflows audit                     # Full audit of all specs vs codebase (via spec-audit workflow)
```

## ⛔ FIRST: Did the user's original message contain [spec] or [spec::]?

If the user's message contains `[spec::ComponentName]` or `[spec]`, **do NOT use this skill**. Those patterns require the full pipeline:

```
/run-workflow spec-write-and-implement --component <ComponentName> --requirements "<user's text>"
/run-workflow spec-write-and-implement --requirements "<user's text>"
```

This skill (`/spec-with-workflows`) is for explicit spec management commands only: `add`, `audit`.

---

## You Are the Spec Manager (Workflow Mode)

When the user invokes this skill, you create or audit behavioral specs using the workflow engine. This provides gates, manifest, and trace — unlike the fast alternatives (`/spec-add`, `/spec-audit`).

**Read the spec format documentation first:** `.agent/docs/specs.md`

---

## Commands

### `/spec-with-workflows add [name]`

**Delegates to the `spec-write` workflow.** This ensures structural gates, discovery of overlaps, and proper user confirmation.

**Do NOT run spec creation logic yourself.** Instead, invoke the workflow:

- **Targeted:** `/spec-with-workflows add EditField` →
  ```
  /run-workflow spec-write --component EditField
  ```

- **Auto-discovery:** `/spec-with-workflows add` (no name) →
  ```
  /run-workflow spec-write
  ```

- If the user also provided requirements text, pass it:
  ```
  /run-workflow spec-write --component EditField --requirements "<user's text>"
  ```

**Why delegate?** The spec-write workflow provides:
- DISCOVER step — finds existing specs, overlaps, contradictions
- CLARIFY step — interactive refinement with human gate
- WRITE-SPEC step — validates the output
- REGISTER-SPEC step — updates _index.json

If the `spec-write` workflow template is not found, report:
"spec-write workflow not found. Ensure `.agent/workflows/templates/predefined/spec-write/` exists."

**For a faster alternative** without workflow overhead: `/spec-add`.

### `/spec-with-workflows audit [options]`

**Delegates to the `spec-audit` workflow.** This is a heavy operation with parallel per-domain scanning and structured gates — it MUST NOT run inline.

**Do NOT run audit logic yourself.** Instead, invoke the workflow:

```
/run-workflow spec-audit
```

Pass any user-specified options as workflow params:
- `--domain <name>` → `domain` param
- `--component <name>` → `component` param
- `--spec-id <id>` → `spec_id` param
- `--severity <level>` → `severity_filter` param ("all", "must", "must+should")
- `--suggest-fixes` → `suggest_fixes: "true"`
- `--include-unregistered` → `include_unregistered: "true"`

**Why delegate?** The spec-audit workflow provides:
- Parallel per-domain scanning (fan-out subagents)
- Human gate on discovery step (user confirms scope before scan)
- Structural validation of audit report (gates)
- Manifest tracking of audit run

If the `spec-audit` workflow template is not found, report:
"spec-audit workflow not found. Ensure `.agent/workflows/templates/predefined/spec-audit/` exists."

**For a faster alternative** without workflow overhead: `/spec-audit`.

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{name}.md` | Spec files (read/write) |
| `.agent/specs/_index.json` | Spec catalog (read/write) |
| `.agent/specs/_registry.json` | Implementation mapping (read/write) |
| `.agent/docs/specs.md` | Format reference (read) |
