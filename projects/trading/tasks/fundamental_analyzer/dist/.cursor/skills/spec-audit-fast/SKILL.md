---
name: spec-audit-fast
description: "Audit behavioral specs against codebase — fast inline, no workflow overhead"
---

# /spec-audit-fast

Check whether code complies with behavioral specs. Read-only — never modifies files. Lightweight alternative to `/spec-with-workflows audit` (which uses the full workflow engine with parallel scanning and gates).

## Usage

```
/spec-audit-fast                                     # audit all specs
/spec-audit-fast --domain <name>                     # filter by domain
/spec-audit-fast --component <name>                  # filter by component
/spec-audit-fast --severity must                     # only MUST requirements
```

---

## Phase 1: SCOPE

Determine what to audit.

1. Read `.agent/specs/_index.json` to get all specs
2. Read `.agent/specs/_registry.json` for implementation mappings
3. Apply filters (most specific wins):
   - `--component` → audit only that component's spec
   - `--domain` → audit all specs in that domain
   - No filter → audit everything
4. If `--severity` is set: only check requirements of that level and above (`must` = MUST only, `must+should` = MUST + SHOULD, `all` = everything)

Report scope to user: "Auditing N specs across M domains."

## Phase 2: CHECK

For each spec in scope:

1. Read the spec file (`.agent/specs/{domain}/{component}.md`)
2. Find implementing files from `_registry.json`
3. If no files registered: note "No implementing files registered" and skip
4. Read each implementing file
5. Check every requirement against the code:
   - **compliant** — code satisfies the requirement
   - **violation** — code breaks the requirement
   - **partial** — partially satisfied
   - **unverifiable** — cannot determine from code alone

Consider relationship types when checking:
- `direct` → check ALL requirements
- `imports` → check logic-related requirements
- `style` → check visual/UI requirements
- `config` → check value constraints
- `test` → check coverage of spec requirements

## Phase 3: REPORT

Print a structured report:

```
## Audit Report

**Scope:** N specs, M domains
**Compliance:** X/Y requirements satisfied (Z%)

### Violations

| Spec | Requirement | File | Issue |
|------|-------------|------|-------|
| EditField | MUST enforce 30 char limit | src/EditField.cpp | No length check found |

### Summary by Domain

| Domain | Specs | Compliant | Violations | Partial |
|--------|-------|-----------|------------|---------|
| ui | 3 | 11 | 2 | 1 |
```

If no violations found: "All requirements satisfied."

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{component}.md` | Spec files (read only) |
| `.agent/specs/_index.json` | Spec catalog (read only) |
| `.agent/specs/_registry.json` | Implementation mappings (read only) |

## See Also

- `/spec-with-workflows audit` — full workflow with parallel domain scanning, gates, and structured trace (slower, more thorough)
- `/spec show <component>` — view a single spec
