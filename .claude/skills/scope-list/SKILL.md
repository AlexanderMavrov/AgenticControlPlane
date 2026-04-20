---
name: scope-list
description: "List all available scopes (implicit generic + declared in _scope-config.json)"
---

# /scope-list

Display the available scopes for the current project.

## Usage

```
/scope-list              # Table with id, source, label
/scope-list --counts     # Also show number of specs per scope
```

## Behavior

Run:

```bash
python .agent/scripts/scope_cli.py list [--counts]
```

The `generic` scope is always listed first and marked `[implicit]`. Scopes declared in `_scope-config.json` are marked `[config]`.

With `--counts`, the script scans each scope's directory for `.md` files (excluding management files starting with `_`) and appends a count.

Example output:

```
Available scopes:
  generic  [implicit]  Cross-integration invariants     (12 specs)
  astro    [config  ]  Astro VLT integration             (47 specs)
  ares     [config  ]  Ares VLT integration              ( 0 specs)
```

## Related

- `/scope-show` — active scope + available list
- `/scope-add <id> "<label>"` — create a new scope
