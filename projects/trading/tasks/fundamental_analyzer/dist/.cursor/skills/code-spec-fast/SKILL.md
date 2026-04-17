---
name: code-spec-fast
description: "Implement a code change while enforcing behavioral specs — fast inline, no workflow overhead"
---

# /code-spec-fast

Implement a code change while respecting all behavioral specs. Lightweight alternative to `/run-workflow-for-code-spec` (which uses the full workflow engine).

## Usage

```
/code-spec-fast <component> "instruction"
/code-spec-fast "instruction"                  # auto-discovery mode
```

---

## Phase 1: GATHER SPECS

**If component is specified (targeted mode):**
1. Find the primary spec: search `.agent/specs/**/{component}.md`
2. Read `_registry.json` — which files implement this component?
3. For each implementing file: check if OTHER specs also map to it (these are constraints to preserve)
4. Read all relevant specs — primary (to implement) + related (to not violate)

**If component is NOT specified (auto-discovery):**
1. Analyze the instruction to predict which files will be affected (search codebase)
2. Read `_registry.json` — for each spec's `implemented_by` files, check if any overlap with predicted affected files
3. Read `_index.json` — match spec components/domains against keywords in instruction
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

## Phase 3: VERIFY + REGISTER

1. For each modified file:
   - Check `_registry.json` for all specs that reference this file
   - Read each spec and verify the modified file still satisfies all requirements
   - Consider relationship types: `direct` → check all requirements; `imports` → check logic requirements; `style` → check visual requirements

2. If violations found: report them clearly with spec_id, requirement, file, and issue description.

3. Update `_registry.json`. If the file doesn't exist, create it:
   ```json
   { "version": 2, "updated_at": null, "mappings": {} }
   ```
   - **Targeted mode:** Add/update the mapping for the component
   - **Auto-discovery mode:** For each spec that was checked, add the modified files
     to that spec's `implemented_by` array (only if the file is relevant to that spec)
   - For each file entry: `{ "file": "<path>", "relationship": "<type>" }`
   - Relationship types: `direct`, `imports`, `imported_by`, `style`, `config`, `test`
   - Set `last_verified` to today's date, `verified_by: "code-spec-fast"`

4. Print summary:
   - Mode: targeted / auto-discovery
   - Files modified: list
   - Specs checked: count
   - Violations: none / list

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{component}.md` | Spec files (read) |
| `.agent/specs/_index.json` | Spec registry (read) |
| `.agent/specs/_registry.json` | Implementation mappings (read/write) |

## See Also

- `/spec-fast` — create a **new** spec and implement it (when no spec exists yet)
- `/run-workflow-for-code-spec` — same operation via full workflow with gates, manifest, trace (slower, more reliable)
