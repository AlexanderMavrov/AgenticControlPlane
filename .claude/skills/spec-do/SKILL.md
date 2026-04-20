---
name: spec-do
description: "Implement a code change while enforcing behavioral specs — fast inline, no workflow overhead"
---

# /spec-do

Implement a code change while respecting all behavioral specs. Lightweight alternative to `/run-workflow-for-code-spec` (which uses the full workflow engine).

## Usage

```
/spec-do <component> "instruction"
/spec-do "instruction"                  # auto-discovery mode
/spec-do <component> "..." --scope <id> # one-shot override
```

---

## Phase 0: Resolve scope

Before anything else, determine the **target scope** for this operation:

1. If the user passed `--scope <id>`, use that (one-shot override, does not
   change persistent state).
2. Otherwise, run `python .agent/scripts/scope_cli.py show` to get the
   active scope, or read `.agent/local/active-scope` directly.
3. Default fallback: `generic`.

The spec set loaded for enforcement is always `active_scope + generic`
(universal invariants always apply). Never inspect sibling scopes.

## Phase 1: GATHER SPECS

**If component is specified (targeted mode):**
1. Find the primary spec: search `.agent/specs/<scope>/**/{component}.md`
   AND `.agent/specs/generic/**/{component}.md`
2. Read `.agent/specs/<scope>/_registry.json` AND
   `.agent/specs/generic/_registry.json` — which files implement this
   component?
3. For each implementing file: check if OTHER specs (in the loaded set)
   also map to it (these are constraints to preserve)
4. Read all relevant specs — primary (to implement) + related (to not violate)

**If component is NOT specified (auto-discovery):**
1. Analyze the instruction to predict which files will be affected (search codebase)
2. Read `.agent/specs/<scope>/_registry.json` and
   `.agent/specs/generic/_registry.json` — for each spec's `implemented_by`
   files, check if any overlap with predicted affected files
3. Read `.agent/specs/<scope>/_index.json` and
   `.agent/specs/generic/_index.json` — match spec components/domains
   against keywords in instruction
4. All matched specs are protective constraints (no "primary" spec in this mode)

If no specs are found: warn the user ("No behavioral specs found for the affected area. Proceeding without spec enforcement.") and continue.

## Phase 2: IMPLEMENT

Make the code change as instructed.

**While working, continuously check:**
- Does this change violate any gathered spec requirement?
- If a conflict is found between the change and a spec:
  1. **STOP immediately**
  2. Warn the user: "This change would violate spec `{name}`: {requirement}"
  3. Ask how to proceed:
     - Modify the approach to avoid the violation
     - Update the spec first (change the requirement), then proceed
     - Override and proceed anyway

Be precise. Follow the instruction exactly. Do not add unrequested behavior.

## Phase 3: VERIFY + REGISTER REGISTRY

1. For each modified file:
   - Check `_registry.json` for all specs that reference this file
   - Read each spec and verify the modified file still satisfies all requirements
   - Consider relationship types: `direct` → check all requirements; `imports` → check logic requirements; `style` → check visual requirements

2. If violations found: report them clearly with spec_id, requirement, file, and issue description.

3. Update `.agent/specs/<scope>/_registry.json` (per-scope registry). If the file doesn't exist, create it:
   ```json
   { "scope": "<scope>", "version": 2, "updated_at": null, "mappings": {} }
   ```
   - **Targeted mode:** Add/update the mapping for the component
   - **Auto-discovery mode:** For each spec that was checked, add the modified files
     to that spec's `implemented_by` array (only if the file is relevant to that spec)
   - For each file entry: `{ "file": "<path>", "relationship": "<type>" }`
   - Relationship types: `direct`, `imports`, `imported_by`, `style`, `config`, `test`
   - Set `last_verified` to today's date, `verified_by: "spec-do"`

4. Print summary:
   - Mode: targeted / auto-discovery
   - Files modified: list
   - Specs checked: count
   - Violations: none / list

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/<scope>/<domain>/<component>.md` | Spec files (read) |
| `.agent/specs/<scope>/_index.json` | Per-scope spec registry (read) |
| `.agent/specs/<scope>/_registry.json` | Per-scope impl mappings (read/write) |
| `.agent/specs/generic/**` | Universal invariants (read, always loaded) |

## See Also

- `/spec-add-do` — create a **new** spec and implement it (when no spec exists yet)
- `/run-workflow-for-code-spec` — same operation via full workflow with gates, manifest, trace (slower, more reliable)
