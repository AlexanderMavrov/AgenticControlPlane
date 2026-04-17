---
name: spec-fast
description: "Write or update a behavioral spec and implement it in code — fast inline, no workflow overhead"
---

# /spec-fast

Write or update a behavioral spec, then implement it in code — fast inline execution without workflow overhead.

> **Important:** This skill is invoked explicitly as `/spec-fast`. It is NOT a fallback for the `[spec]` or `[spec::]` chat patterns. Those patterns MUST always go through `/run-workflow spec-write-and-implement` — never substitute with this skill.

## Usage

```
/spec-fast <component> "requirements"
/spec-fast "requirements"                      # auto-discovery mode
/spec-fast <component> "requirements" --no-implement   # spec only, no code
```

---

## Phase 1: DISCOVER

1. Read `.agent/specs/_index.json` (if exists) to get all existing specs
2. Read `.agent/specs/_registry.json` (if exists) for implementation mappings

**If component is specified (targeted mode):**
- Search for existing spec at `.agent/specs/**/{component}.md`
- If found: read current requirements
- Check other specs in `_index.json` for overlapping requirements
- Check `_registry.json` for files that already implement this component

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

**Засегнати файлове (_registry.json):**
- {file} — mapped към {other_spec}
(или: няма засегнати файлове с други specs)

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

## Phase 2: WRITE SPEC + REGISTER

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

Update `.agent/specs/_index.json` with the spec entry. If the file doesn't exist, create it with `"version": 1, "updated_at": "<today>", "specs": [...]`.

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

**If `--no-implement` flag is set: STOP here. Print summary and exit.**

## Phase 3: IMPLEMENT

1. Find implementation files: check `_registry.json` for existing mappings, or search the codebase
2. Scope the implementation:
   - **New spec** (created in Phase 2) → implement all MUST requirements
   - **Updated spec** (modified in Phase 2) → implement only the **new or changed** requirements. For pre-existing requirements that were NOT changed, verify they still work but do NOT re-implement them.
3. **While implementing, continuously check:** do your changes violate any OTHER spec? For each file you modify, check `_registry.json` for other specs that map to it.
4. If a conflict is found:
   - **STOP immediately**
   - Warn the user: "This change would violate spec `{name}`: {requirement}"
   - Ask how to proceed

## Phase 4: VERIFY + REGISTER

1. For each modified file:
   - Check `_registry.json` for all specs that reference this file
   - Read each spec and verify the modified file still satisfies all requirements

2. If violations found: report clearly with spec_id, requirement, file, issue.

3. Update `_registry.json`. If the file doesn't exist, create it:
   ```json
   { "version": 2, "updated_at": null, "mappings": {} }
   ```
   Add/update the mapping for the component:
   ```json
   {
     "ComponentName": {
       "spec": "specs/{domain}/{component}.md",
       "implemented_by": [
         { "file": "<path>", "relationship": "<type>" }
       ],
       "last_verified": "YYYY-MM-DD",
       "verified_by": "spec-fast"
     }
   }
   ```
   Relationship types: `direct`, `imports`, `imported_by`, `style`, `config`, `test`.

4. Print summary:
   - Spec: path + new/updated
   - Files modified: list
   - Specs checked: count
   - Violations: none / list

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{component}.md` | Spec files (read/write) |
| `.agent/specs/_index.json` | Spec registry (read/write) |
| `.agent/specs/_registry.json` | Implementation mappings (read/write) |

## See Also

- `/spec-add-fast` — create/update spec **without** implementation (same as `--no-implement`)
- `/code-spec-fast` — implement code with spec enforcement (no spec creation)
- `/run-workflow spec-write-and-implement` — full workflow with gates, manifest, trace (slower, more reliable)
