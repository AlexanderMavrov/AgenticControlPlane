---
name: spec-add-fast
description: "Create or update a behavioral spec — fast inline execution, no workflow overhead"
---

# /spec-add-fast

Create or update a behavioral spec without implementing it in code. Lightweight alternative to `/spec-with-workflows add` (which uses the full workflow engine).

## Usage

```
/spec-add-fast <component> "requirements"
/spec-add-fast "requirements"                  # auto-discovery mode
```

---

## Phase 1: DISCOVER

1. Read `.agent/specs/_index.json` (if exists) to get all existing specs
2. Read `.agent/specs/_registry.json` (if exists) for implementation mappings

**If component is specified (targeted mode):**
- Search for existing spec at `.agent/specs/**/{component}.md`
- If found: read current requirements
- Check other specs in `_index.json` for overlapping requirements
- Check `_registry.json` for files that already implement this component — if code exists but has no spec, note it for the confirmation step

**If component is NOT specified (auto-discovery):**
- Analyze the requirements text — what component/module is this about?
- Search existing specs for overlapping or related requirements
- Check `_registry.json` — is there code that already implements this behavior but has no spec?
- Determine component name and domain

## Phase 1.5: CONFIRM (mandatory)

**ALWAYS** present a confirmation summary before proceeding — even if everything looks clear.

Show the user:

```
## Потвърждение

**Компонент:** {component}
**Домейн:** {domain}
**Режим:** нов spec / обновяване на съществуващ

**Как разбрах изискванията:**
- MUST: ...
- SHOULD: ...

**Съществуващи specs в същия домейн:**
- {related_spec} — {brief description}
  → {relationship: свързан / конфликтен / вече покрива това}
(или: няма намерени)

**Вече имплементирано?**
- {file} — изглежда вече реализира подобно поведение (но няма spec)
(или: не е намерено)

Продължавам? (y / коригирай / откажи)
```

**Rules:**
- This confirmation is **mandatory** — never skip it, even for trivial cases
- If the spec already exists, show the **current requirements** alongside the proposed changes (what will be added/changed)
- If overlaps or conflicts are found, highlight them prominently
- Wait for explicit user approval before proceeding to Phase 2
- If the user provides corrections, update your understanding and show the confirmation again

## Phase 2: WRITE SPEC

Create or update the spec file at `.agent/specs/{domain}/{component}.md`.

### Spec Format

```markdown
---
spec_id: ComponentName
component: ComponentName
domain: domainname
tags: [relevant, tags]
status: active
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
---

# ComponentName

## Requirements

- MUST requirement text here
- SHOULD requirement text here
- MAY requirement text here

## Constraints

- Constraint text (if applicable)

## Examples

- Example of expected behavior (if helpful)

## Source

- [YYYY-MM-DD] Initial: what was added
```

**Rules:**
- Component names: `^[A-Za-z][A-Za-z0-9_-]*$` (PascalCase preferred)
- Domain names: `^[a-z][a-z0-9_-]*$` (lowercase)
- Each requirement MUST start with MUST / SHOULD / MAY
- If updating an existing spec: preserve existing requirements unless the user explicitly wants to change them. Add a new Source changelog entry.

## Phase 3: REGISTER

Update `.agent/specs/_index.json`. If the file doesn't exist, create it with `"version": 1, "updated_at": "<today>", "specs": [...]`.

Add or update the entry for the spec:

```json
{
  "spec_id": "{domain}/{component}",
  "component": "{component}",
  "domain": "{domain}",
  "file_path": "specs/{domain}/{component}.md",
  "status": "active",
  "tags": ["..."],
  "requirements_count": N,
  "created_at": "YYYY-MM-DD",
  "updated_at": "YYYY-MM-DD"
}
```

**Do NOT touch `_registry.json`** — no code changes were made.

## Summary

Print:
- Spec path: `.agent/specs/{domain}/{component}.md`
- Status: new / updated
- Requirements count
- Domain

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{component}.md` | Spec file (read/write) |
| `.agent/specs/_index.json` | Spec registry (read/write) |
| `.agent/specs/_registry.json` | Implementation mappings (read only, for discovery) |

## See Also

- `/spec-fast` — create/update spec **and** implement it in code
- `/spec-with-workflows add` — same operation via full workflow with gates and manifest (slower, more reliable)
