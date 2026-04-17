# doc-spec-extraction — Extract Specs from Documentation

Extracts behavioral specifications from any technical document — programming guides, API references, standards, specifications. Performs **deep analysis** to find requirements that may be scattered across sections, interdependent, or implicit.

Outputs go to `.agent/specs/` for reuse by other workflows (spec-enforcement, registry-sync, etc.).

## Why this workflow exists

Large technical documents (thousands of lines) contain requirements buried across chapters, cross-referencing each other, sometimes contradicting each other. Manually extracting and organizing them is tedious and error-prone. This workflow automates the process with a systematic 4-step pipeline:

1. **Deep analysis** — reads the full document, discovers all domains and requirements, checks existing specs, proposes placement
2. **Systematic extraction** — writes structured spec files per domain (parallel)
3. **Cross-validation** — verifies every spec against the source document for accuracy, completeness, consistency
4. **Safe commit** — writes only validated specs; conflicts and regressions are flagged for human review

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `source` | **Yes** | — | Path to the source document |
| `focus` | No | *(full document)* | Free-text: which sections/topics to analyze (e.g., "error handling", "sections 3.2-3.5") |
| `supplementary` | No | — | Path to a supplementary document (FAQ, errata, addendum) |
| `domain` | No | *(auto-discover)* | Target domain for the specs (e.g., "messaging") |

## Usage

```
# Analyze a full document
/run-workflow doc-spec-extraction --source "docs/astro/Programming Guide v3.2.md"

# Focus on specific topics
/run-workflow doc-spec-extraction --source "docs/api-reference.md" --focus "authentication and authorization"

# With supplementary document
/run-workflow doc-spec-extraction --source "docs/spec.md" --supplementary "docs/faq.md"

# Target a specific domain
/run-workflow doc-spec-extraction --source "docs/guide.md" --focus "message queue" --domain "messaging"

# Resume after interruption
/run-workflow doc-spec-extraction --resume
```

## Steps

### Step 1: ANALYZE (human gate)

Reads the full source document and performs deep requirements analysis.

**Key behaviors:**
- Even with `--focus`, reads the FULL document for cross-references and dependencies
- Identifies requirements scattered across multiple sections
- Traces indirect dependencies between requirements
- Extracts implicit requirements from examples and error descriptions
- Checks `.agent/specs/` for existing specs — proposes merge/create per domain
- Flags ambiguities and discrepancies for user review

**Output:** `data/analysis-report.json` — understanding summary, discovered domains, per-domain requirements with source references, proposed spec placement, existing spec status, discrepancies.

**Gate:** Human — user reviews the analysis and confirms before extraction begins.

### Step 2: EXTRACT (parallel)

Writes draft spec files per domain, based on the approved analysis.

**Key behaviors:**
- Parallel fan-out: one subagent per domain
- Each spec: YAML frontmatter (spec_id, title, severity, domain, source_sections, related_specs) + Markdown body (Rule Statement, Rationale, Valid/Invalid Examples, Validation Criteria, Source Reference)
- For domains with existing specs: reads old specs, produces merged drafts that preserve valid content and improve/correct based on the source document
- Cross-references between specs via `related_specs` frontmatter

**Output:** `data/drafts/{domain}/*.md` — one file per spec.

### Step 3: VALIDATE

Cross-validates ALL draft specs against the source document and existing specs.

**Checks per spec:**
- **Accuracy** — does the rule statement match the source?
- **Completeness** — are all requirements from cited sections captured?
- **Consistency** — do specs contradict each other?
- **Traceability** — can a reader find the source text?
- **Testability** — are validation criteria concrete?
- **Examples** — are they realistic and correct?

**For merge drafts:** verifies the merge is strictly better — flags regressions.

**Output:** `data/validation-report.json` — per-spec status (valid / issues_found / conflict / regression), overall quality score.

### Step 4: COMMIT

Writes validated specs to `.agent/specs/`. Handles edge cases safely:
- **valid** → committed to `.agent/specs/{domain}/`
- **issues_found** (minor) → fixed inline and committed
- **issues_found** (significant) → left in `data/drafts/` for human review
- **conflict** → left in `data/drafts/`, NOT overwritten
- **regression** → left in `data/drafts/`, existing spec preserved

Updates `_index.json`. Prints a detailed summary to chat.

## Gate Configuration

| Step | Structural | Semantic | Human |
|------|-----------|----------|-------|
| ANALYZE | ✅ | ✅ | ✅ |
| EXTRACT | ✅ | ✅ | — |
| VALIDATE | ✅ | ✅ | — |
| COMMIT | ✅ | ✅ | — |

## Merge Mode

When running against a domain that already has specs in `.agent/specs/`, the workflow automatically detects this:

- **ANALYZE** marks the domain as `mode: merge` (or `mixed` if some specs exist and some don't)
- **EXTRACT** reads existing specs and produces improved drafts with a `## Changes` section
- **VALIDATE** compares old vs new — passes only if the merge is strictly better
- **COMMIT** overwrites only validated merges; conflicts are left for human review

This means you can safely re-run the workflow on the same document/domain — it won't destroy existing work.

## Output Structure

```
.agent/specs/
├── _index.json                 # Metadata for all specs
├── _registry.json              # Implementation mapping (files → specs)
├── messaging/
│   ├── MSG-001.md
│   ├── MSG-002.md
│   └── ...
├── recovery/
│   ├── REC-001.md
│   └── ...
└── ... (one directory per domain)
```

Each spec file:

```markdown
---
spec_id: MSG-001
title: Message Queue Size Validation
severity: MUST
domain: messaging
source_sections:
  - "3.2.1 Message Queue Management"
  - "3.2.2 Queue Size Limits"
related_specs:
  - MSG-002
  - MSG-005
---

## Rule Statement
...

## Rationale
...

## Valid Examples
...

## Invalid Examples
...

## Validation Criteria
...

## Source Reference
...
```

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 4-step workflow definition (ANALYZE → EXTRACT → VALIDATE → COMMIT) |
| `structs/analysis-report.schema.yaml` | Schema for the analysis output (JSON) |
| `structs/spec.schema.yaml` | Schema for individual spec files (Markdown with frontmatter) |
| `structs/validation-report.schema.yaml` | Schema for validation results (JSON) |
| `README.md` | This file |
