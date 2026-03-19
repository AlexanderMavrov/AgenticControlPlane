---
name: spec
description: "Manage behavioral specs — create, read, update, check, and audit"
---

# /spec

Manage behavioral specs in `.agent/specs/`. Create, read, update, check, and audit specs.

## Usage

```
/spec                           # List all specs
/spec list                      # List all specs
/spec show <name>               # Display a spec's contents
/spec add <name>                # Create or update a spec (interactive, targeted)
/spec add                       # Create a spec with auto-discovery (interactive)
/spec check [component]         # Check code against specs
/spec audit                     # Full audit of all specs vs codebase
```

## You Are the Spec Manager

When the user invokes this skill, you manage behavioral specs. Your job is to read, create, update, and validate specs in `.agent/specs/`.

**Read the spec format documentation first:** `.agent/docs/specs.md`

> **Note:** This skill provides a lightweight inline flow (no manifest, no structural gates). For the full workflow pipeline with structural gates, manifests, and delegation, use `/run-workflow spec-write-and-implement` instead.

---

## Commands

### `/spec` or `/spec list`

1. Read `.agent/specs/_index.json`
2. If it doesn't exist, scan `.agent/specs/` for `.md` files manually
3. Display a table:

```
| Spec ID | Domain | Component | Status | Requirements | Updated |
|---------|--------|-----------|--------|-------------|---------|
| EditField | ui | EditField | active | 4 | 2026-03-13 |
```

4. If no specs found, say: "No specs found. Use `/spec add <name>` to create one."

### `/spec show <name>`

1. Find the spec file: check `_index.json` for path, or search `.agent/specs/**/<name>.md`
2. Display the full spec contents
3. If `_registry.json` has a mapping for this spec, also show implementing files

### `/spec add [name]`

This is the **interactive spec creation/update flow**. This is the most important command.

**Two modes:**
- **Targeted:** `/spec add EditField` — component name is known
- **Auto-discovery:** `/spec add` (no name) — analyze requirements to discover the component

**If triggered by `[specs::ComponentName]` pattern** (via Spec Guard rule):
- Targeted mode — the user's message contains the component name and initial requirements

**If triggered by `[spec]` pattern** (via Spec Guard rule):
- Auto-discovery mode — the user's message contains requirements but no component name

**Step 0: AUTO-DISCOVER** (only when no `<name>` is provided)

When no component name is given, you must discover it:

1. Read `.agent/specs/_index.json` to get all existing specs
2. Analyze the user's requirements text — what component, module, or feature is this about?
3. Search existing specs for overlapping or related requirements:
   - Same component under a different name?
   - Existing spec that already covers part of this?
4. **Propose** to the user:
   - "I believe this belongs to component **[NAME]** in domain **[DOMAIN]**."
   - "Related existing specs: [list, if any]."
   - "Is this a NEW spec or an UPDATE to an existing one?"
5. Wait for user confirmation or correction
6. Use the confirmed name as `<name>` for all subsequent steps

**Step 1: CLARIFY** (mandatory, interactive)

The user's initial description may be unclear, incomplete, or too verbose. You MUST:

1. Read the user's requirements carefully
2. If a spec already exists for `<name>`:
   - Read it and show the current requirements
   - Ask: "Which requirements should I add/change?"
3. Ask clarifying questions if anything is ambiguous:
   - "What should happen when X?"
   - "Does this apply to all Y or only Z?"
   - "What severity: MUST (mandatory) or SHOULD (recommended)?"
4. Draft a **concise summary** of the requirements in MUST/SHOULD/MAY format
5. Show the summary to the user: "Here's what I'll write to the spec:"
6. **Wait for user approval** before proceeding

**CRITICAL:** Do NOT skip the clarification step. Do NOT write the spec until the user approves the summary. The whole point is to get a clean, unambiguous spec.

**Step 2: WRITE-SPEC**

After user approval:

1. Determine the domain (ask user if unclear)
2. Create or update `.agent/specs/{domain}/{name}.md`:
   - Proper YAML frontmatter (spec_id, component, domain, tags, status, dates)
   - Requirements section with approved text
   - Constraints section if applicable
   - Examples section if the user provided any
   - Source section with changelog entry
3. Update `_index.json` (add or update entry)

**Step 3: IMPLEMENT** (if the user's original message included a code change request)

If the `/spec add` was triggered by `[specs::X]` with an implementation request:

1. Read ALL existing specs that might be affected by this change
2. Implement the code change
3. Check: does the implementation violate any other specs?
   - If yes: warn the user, ask how to proceed
   - If no: continue
4. Update `_registry.json` with the files you modified

If the `/spec add` was just about creating a spec (no code change), skip this step.

**Step 4: REGISTER**

1. Read `_registry.json` (or create if missing)
2. Add/update the mapping for this spec:
   ```json
   {
     "spec": "specs/{domain}/{name}.md",
     "implemented_by": ["list", "of", "modified", "files"],
     "last_verified": "ISO date",
     "verified_by": "/spec add"
   }
   ```
3. Write updated `_registry.json`

**Step 5: SUMMARY**

Tell the user:
- Spec created/updated: `{path}`
- Requirements count: N
- Files modified: list (if implementation was done)
- Other specs checked: list (if verification was done)

### `/spec check [component]`

Check code against behavioral specs.

**If `component` is specified:**
1. Find the spec for that component
2. Read the spec requirements
3. Find implementing files (from `_registry.json` or by component name search)
4. Read the implementing files
5. Check each requirement against the code
6. Report: which requirements are met, which are violated

**If no `component`:**
1. Read `_registry.json` for all mappings
2. For each mapping: spot-check requirements vs code
3. Report summary: N specs checked, N compliant, N violations

### `/spec audit`

Full audit of all specs against the codebase.

1. Read all spec files from `.agent/specs/`
2. For each active spec:
   - Find implementing files
   - Check ALL requirements against the code
   - Report violations
3. Produce audit summary:
   - Total specs: N
   - Fully compliant: N
   - Violations found: N (list each)
   - Specs without implementations: N
4. Suggest fixes for violations

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{name}.md` | Spec files (read/write) |
| `.agent/specs/_index.json` | Spec registry (read/write) |
| `.agent/specs/_registry.json` | Implementation mapping (read/write) |
| `.agent/docs/specs.md` | Format reference (read) |
