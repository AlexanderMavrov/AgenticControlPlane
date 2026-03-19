# Example: Astro Spec Extraction (using doc-spec-extraction)

This example shows how to use the **`doc-spec-extraction`** predefined workflow to extract validation specs from the Astro Programming Guide.

> **Note:** The `doc-spec-extraction` workflow is now a **predefined workflow** shipped with the engine at `.agent/workflows/predefined/doc-spec-extraction/`. This example directory contains Astro-specific usage instructions.

## Prerequisites

- Workflow Engine installed in the target project (via `install.py`)
- Astro Programming Guide v3.2 available at `docs/astro/`
- Python 3.8+ with PyYAML (`pip install pyyaml`)

## Quick Start

```
# Full document analysis
/run-workflow doc-spec-extraction --source "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md"

# With FAQ as supplementary reference
/run-workflow doc-spec-extraction \
  --source "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md" \
  --supplementary "docs/astro/Astro Game Development Kits - Programming FAQ - v3.2.md"

# Focus on a specific section
/run-workflow doc-spec-extraction \
  --source "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md" \
  --focus "3.2.1 Message Queue Management"

# Focus on a topic (free text)
/run-workflow doc-spec-extraction \
  --source "docs/astro/Astro Game Development Kits - Programming Guide - v3.2.md" \
  --focus "error handling and recovery mechanisms"

# Resume after interruption
/run-workflow doc-spec-extraction --resume
```

## What happens

The workflow executes 4 steps:

1. **ANALYZE** — Reads the Astro Programming Guide fully. Identifies domains (messaging, recovery, rng, persistence, accounting, session, display, input, audio, configuration, security, lifecycle). Checks existing specs in `.agent/specs/`. Proposes spec placement. **Human gate** — you review and approve.

2. **EXTRACT** — Writes draft specs per domain (parallel subagents). For existing specs: merges improvements. Drafts go to `data/drafts/{domain}/`.

3. **VALIDATE** — Cross-validates every draft against the source document. Checks accuracy, completeness, consistency. Flags regressions for existing specs.

4. **COMMIT** — Writes validated specs to `.agent/specs/{domain}/`. Conflicts left for human review. Updates `_index.json`. Prints summary.

## Expected output

```
.agent/specs/
├── _index.json
├── messaging/    (MSG-001, MSG-002, ...)
├── recovery/     (REC-001, ...)
├── rng/          (RNG-001, ...)
├── persistence/  (PER-001, ...)
└── ... (~12 domains, ~100 specs total)
```

## See also

- `.agent/workflows/predefined/doc-spec-extraction/README.md` — Full workflow documentation
- `.agent/workflows/predefined/doc-spec-extraction/workflow.yaml` — Workflow definition
