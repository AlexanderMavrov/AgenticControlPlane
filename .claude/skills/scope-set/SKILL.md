---
name: scope-set
description: "Set the active scope for spec operations (user-level override, or project default with --project)"
---

# /scope-set

Change the active scope used by spec-touching workflows and skills.

## Usage

```
/scope-set <scope-id>              # User-level override (writes .agent/local/active-scope)
/scope-set <scope-id> --project    # Team-level default (writes _scope-config.json default_active_scope)
```

## Behavior

Run:

```bash
python .agent/scripts/scope_cli.py set <scope-id> [--project]
```

The script:

1. Validates that `<scope-id>` matches `^[a-z][a-z0-9-]*$`
2. Validates that `<scope-id>` is either `generic` (implicit) or declared in `_scope-config.json`
3. Without `--project`: writes `<scope-id>\n` to `.agent/local/active-scope` (creates dir if needed, gitignored)
4. With `--project`: sets `default_active_scope: <scope-id>` in `.agent/specs/_scope-config.json`, commits via atomic replace

If the scope is not found, the command exits with error and suggests `/scope-add` or `/scope-list`.

## Examples

```
/scope-set astro            → user now works in astro scope
/scope-set generic          → user explicitly works only on generic rules
/scope-set ares --project   → team default becomes ares (committed to git)
```

## Related

- `/scope-add` — create a new scope
- `/scope-unset` — remove user override
- `/scope-show` — display current active scope
- `/scope-list` — list available scopes
