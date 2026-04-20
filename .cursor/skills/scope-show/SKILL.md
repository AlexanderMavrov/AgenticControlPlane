---
name: scope-show
description: "Show the currently active scope and where it was resolved from"
---

# /scope-show

Display the active scope for spec operations and its resolution source.

## Usage

```
/scope-show
```

No arguments.

## Behavior

Run the Bash tool to execute:

```bash
python .agent/scripts/scope_cli.py show
```

The script resolves the active scope via the priority chain:

1. CLI `--scope` flag (n/a for this command — no CLI workflow context)
2. `.agent/local/active-scope` (user override)
3. `.agent/specs/_scope-config.json` `default_active_scope`
4. `generic` (hard-coded fallback)

Output format:

```
Active scope: astro
Label:        Astro VLT integration (AK2API 1.8.x)
Source:       user (.agent/local/active-scope)

Available scopes:
  generic  [implicit]  Cross-integration invariants (implicit; always available)
  astro    [config  ]  Astro VLT integration (AK2API 1.8.x)
  ares     [config  ]  Ares VLT integration (EOS Framework 1.8)
```

## Related

- `/scope-set <id>` — change active scope
- `/scope-unset` — clear override and fall back to project default
- `/scope-list` — list available scopes only
