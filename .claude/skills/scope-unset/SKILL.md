---
name: scope-unset
description: "Clear the user-level active scope override and fall back to project default"
---

# /scope-unset

Remove `.agent/local/active-scope`. Next command will resolve the active scope from `_scope-config.json` → `default_active_scope` or fall back to `generic`.

## Usage

```
/scope-unset
```

No arguments.

## Behavior

Run:

```bash
python .agent/scripts/scope_cli.py unset
```

If the file did not exist, reports "no override to clear" (no-op, not an error).

## Related

- `/scope-set <id>` — set user-level override
- `/scope-show` — display current active scope after unset
