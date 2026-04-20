---
name: spec-add-do
description: "Write or update a behavioral spec and implement it in code — fast inline, no workflow overhead"
---

# /spec-add-do

Write or update a behavioral spec, then implement it in code — fast inline execution without workflow overhead.

## Usage

```
/spec-add-do <component> "requirements"
/spec-add-do "requirements"                      # auto-discovery mode
/spec-add-do <component> "requirements" --no-implement   # spec only, no code
/spec-add-do <component> "requirements" --scope <id>     # override active scope
```

---

## Phase 0: Resolve scope

Before anything else, determine the **target scope** for this operation:

1. If the user passed `--scope <id>`, use that (one-shot override, does not
   change persistent state).
2. Otherwise, run `python .agent/scripts/scope_cli.py show` to get the
   active scope, or read `.agent/local/active-scope` directly.
3. Default fallback: `generic`.

All reads load specs from `.agent/specs/<scope>/` **and** `.agent/specs/generic/`
(universal invariants always apply). All writes target
`.agent/specs/<scope>/<domain>/<Component>.md`.

If `--scope generic` is used (and the rule is truly cross-integration),
the spec is a universal invariant and the scope-write-validator hook will
always allow the write regardless of active scope.

---

## Phase 1: DISCOVER

1. Read `.agent/specs/<scope>/_index.json` AND `.agent/specs/generic/_index.json`
   (if exist) to get all existing specs applicable in this context
2. Read `.agent/specs/<scope>/_registry.json` AND `.agent/specs/generic/_registry.json`
   (if exist) for implementation mappings

**If component is specified (targeted mode):**
- Search for existing spec at `.agent/specs/<scope>/**/{component}.md`
  AND `.agent/specs/generic/**/{component}.md` — never inspect sibling
  scopes (they belong to different integration contexts)
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

## Phase 2: WRITE SPEC + REGISTER INDEX

Create or update the spec file at `.agent/specs/<scope>/<domain>/<component>.md`.

### Spec Format

```markdown
---
spec_id: ComponentName
component: ComponentName
domain: domainname
scope: [<scope>]
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

Update `.agent/specs/<scope>/_index.json` (per-scope index) with the spec
entry. If the file doesn't exist, create it with
`{"scope": "<scope>", "version": 1, "updated_at": "<today>", "specs": [...]}`.

```json
{
  "spec_id": "{domain}/{component}",
  "component": "{component}",
  "domain": "{domain}",
  "scope": "<scope>",
  "file_path": "specs/{scope}/{domain}/{component}.md",
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
   - **New spec** (created in Phase 2) → implement all requirements (MUST, SHOULD, MAY)
   - **Updated spec** (modified in Phase 2) → implement only the **new or changed** requirements. For pre-existing requirements that were NOT changed, verify they still work but do NOT re-implement them.
3. **While implementing, continuously check:** do your changes violate any OTHER spec? For each file you modify, check `_registry.json` for other specs that map to it.
4. If a conflict is found:
   - **STOP immediately**
   - Warn the user: "This change would violate spec `{name}`: {requirement}"
   - Ask how to proceed:
     - Modify the approach to avoid the violation
     - Update the spec first (change the requirement), then proceed
     - Override and proceed anyway

## Phase 4: VERIFY + REGISTER REGISTRY

1. For each modified file:
   - Check `_registry.json` for all specs that reference this file
   - Read each spec and verify the modified file still satisfies all requirements
   - Consider relationship types: `direct` → check all requirements; `imports` → check logic requirements; `style` → check visual requirements

2. If violations found: report clearly with spec_id, requirement, file, issue.

3. Update `.agent/specs/<scope>/_registry.json` (per-scope registry). If the
   file doesn't exist, create it:
   ```json
   { "scope": "<scope>", "version": 2, "updated_at": null, "mappings": {} }
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
       "verified_by": "spec-add-do"
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
| `.agent/specs/<scope>/<domain>/<component>.md` | Spec files (read/write) |
| `.agent/specs/<scope>/_index.json` | Per-scope spec registry (read/write) |
| `.agent/specs/<scope>/_registry.json` | Per-scope implementation mappings (read/write) |
| `.agent/specs/generic/**` | Universal invariants (read-only unless scope=generic) |
| `.agent/local/active-scope` | User's active scope (plain text, one line) |
| `.agent/specs/_scope-config.json` | Declared scopes (optional; absent = generic only) |

## See Also

- `/spec-add` — create/update spec **without** implementation (same as `--no-implement`)
- `/spec-do` — implement code with spec enforcement (no spec creation)
- `/run-workflow spec-write-and-implement` — full workflow with gates, manifest, trace (slower, more reliable)
