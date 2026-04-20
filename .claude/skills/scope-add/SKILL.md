---
name: scope-add
description: "Create a new scope — add entry in _scope-config.json, create directory + empty indexes"
---

# /scope-add

Declare a new scope. Self-contained: updates config and creates the directory with empty `_index.json` and `_registry.json`.

## Usage

```
/scope-add <id> "<label>"
```

- `<id>`: lowercase, starts with a letter, digits and hyphens only (`^[a-z][a-z0-9-]*$`)
- `<label>`: human-readable description (used in `/scope-list`, error messages, analysis reports)

## Behavior

Run:

```bash
python .agent/scripts/scope_cli.py add <id> "<label>"
```

The script:

1. Validates `<id>` format
2. Refuses if `<id>` == `generic` (reserved)
3. Refuses if `<id>` already exists in `_scope-config.json`
4. Creates `_scope-config.json` if absent (with `scopes: [], default_active_scope: null`)
5. Appends `{id, label}` to `scopes[]`
6. Creates `.agent/specs/<id>/` with:
   - `_index.json` = `{"scope": "<id>", "specs": []}`
   - `_registry.json` = `{"scope": "<id>", "mappings": []}`

Atomic writes where possible.

## Examples

```
/scope-add astro "Astro VLT integration (AK2API 1.8.x)"
/scope-add ares  "Ares VLT integration (EOS Framework 1.8)"
/scope-add regulatory-italy "Italian AAMS regulatory requirements"
```

## Related

- `/scope-list` — verify the new scope appears
- `/scope-set <id>` — switch to working in the new scope
