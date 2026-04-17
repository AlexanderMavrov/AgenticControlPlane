---
name: spec
description: "View behavioral specs — list all or show details"
---

# /spec

View behavioral specs in `.agent/specs/`. Read-only — listing and inspection only.

## Usage

```
/spec                           # List all specs
/spec list                      # List all specs
/spec show <name>               # Display a spec's contents
```

> **To create or audit specs via workflows:** use `/spec-with-workflows add` or `/spec-with-workflows audit`.
> **For fast alternatives** (no workflow): `/spec-add-fast`, `/spec-audit-fast`.

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

4. If no specs found, say: "No specs found. Use `/spec-with-workflows add <name>` or `/spec-add-fast` to create one."

### `/spec show <name>`

1. Find the spec file: check `_index.json` for path, or search `.agent/specs/**/<name>.md`
2. Display the full spec contents
3. If `_registry.json` has a mapping for this spec, also show implementing files

---

## Key Files

| File | Purpose |
|------|---------|
| `.agent/specs/{domain}/{name}.md` | Spec files (read only) |
| `.agent/specs/_index.json` | Spec catalog (read only) |
| `.agent/specs/_registry.json` | Implementation mapping (read only) |
| `.agent/docs/specs.md` | Format reference (read only) |
