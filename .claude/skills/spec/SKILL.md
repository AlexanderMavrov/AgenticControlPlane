---
name: spec
description: "View behavioral specs — list all or show details"
---

# /spec

View behavioral specs in `.agent/specs/`. Read-only — listing and inspection only.

## Usage

```
/spec                           # List specs in active scope + generic
/spec list                      # Same as above
/spec list --scope <id>         # List specs from specific scope + generic
/spec list --scope all          # List specs from all scopes
/spec show <name>               # Display a spec's contents
/spec show <scope>:<name>       # Explicit scope-qualified lookup
```

> **To create or audit specs via workflows:** use `/spec-with-workflows add` or `/spec-with-workflows audit`.
> **For fast alternatives** (no workflow): `/spec-add`, `/spec-audit`.

---

## Commands

### `/spec` or `/spec list [--scope <id>|all]`

1. Resolve the scope set:
   - `--scope all` → every scope from `.agent/specs/_scope-config.json`
     plus `generic`
   - `--scope <id>` → `[<id>, "generic"]`
   - default → `[<active_scope>, "generic"]` (from
     `.agent/local/active-scope`, or project default)
2. For each scope in the set: read `.agent/specs/<scope>/_index.json`
3. Display a table (include the Scope column):

```
| Scope | Spec ID | Domain | Component | Status | Requirements | Updated |
|-------|---------|--------|-----------|--------|-------------|---------|
| astro | NVRM-001 | nvram | NVRAM | active | 3 | 2026-04-15 |
```

4. If no specs found, say: "No specs found in scope(s) [<set>]. Use `/spec-add --scope <id>` to create one."

### `/spec show <name>` or `/spec show <scope>:<name>`

1. If name is `<scope>:<id>`, look in that specific scope only.
   Otherwise, search `.agent/specs/<active_scope>/**/<name>.md` and
   `.agent/specs/generic/**/<name>.md`.
2. Display the full spec contents, prefixed with the scope header.
3. If the scope's `_registry.json` has a mapping for this spec, also
   show implementing files.

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/<scope>/<domain>/<name>.md` | Spec files (read only) |
| `.agent/specs/<scope>/_index.json` | Per-scope spec catalog (read only) |
| `.agent/specs/<scope>/_registry.json` | Per-scope impl mapping (read only) |
| `.agent/specs/_scope-config.json` | Declared scopes (read only) |
| `.agent/local/active-scope` | User's active scope (plain text, one line) |
| `.agent/docs/specs.md` | Format reference (read only) |
