---
name: run-workflow-for-code-spec
description: "Implement a code change via the full spec-enforcement workflow — with manifest, trace, and gates"
---

# /run-workflow-for-code-spec

Implement a code change while automatically enforcing all relevant behavioral specs, using the **full workflow engine** (manifest, trace, gates).

This is a convenience wrapper around the `spec-enforcement` workflow. It implements the change, verifies no specs are violated, and registers affected files in `_registry.json`.

> **For a faster alternative** without workflow overhead, use `/spec-do`.

## Usage

```
/run-workflow-for-code-spec [component] "<instruction>" [--scope <id>] [--domain <domain>]
```

Examples:
```
/run-workflow-for-code-spec EditField "add max length validation of 100 chars"
/run-workflow-for-code-spec EditField "add max length" --scope astro
/run-workflow-for-code-spec "refactor the message queue retry logic"
/run-workflow-for-code-spec MessageQueue "add exponential backoff" --domain messaging
```

## Argument Parsing

Parse the user's input to extract:

1. **component** (optional) — first argument if it looks like a component name (PascalCase, kebab-case, or snake_case word without spaces). If not provided, the workflow runs in auto-discovery mode.
2. **instruction** (required) — the quoted string or remaining text describing what to do.
3. **--scope** (optional) — scope override (e.g., astro, ares). If not provided, the workflow uses the active scope from `.agent/local/active-scope` or defaults to `generic`. Specs in the target scope + `generic` are both enforced (universal invariants always apply).
4. **--domain** (optional) — logical domain hint (e.g., ui, messaging).

## Execution

Invoke the `spec-enforcement` workflow with the parsed arguments:

```
/run-workflow spec-enforcement [--scope <scope>] [--component <component>] --instruction "<instruction>" [--domain <domain>]
```

**That's it.** The workflow handles everything:
- **CHECK-SPECS** — finds relevant specs (by component or auto-discovery from instruction)
- **IMPLEMENT** — makes the code change while respecting specs
- **VERIFY** — confirms no spec violations
- **REGISTER** — updates `_registry.json` with affected files

## When Component Is Omitted

When no component is specified, the workflow enters **auto-discovery mode**:
- Analyzes the instruction text to predict which files will be affected
- Scans `_registry.json` to find all specs that map to those files
- Treats all matched specs as protective constraints
- Implements the instruction while respecting all discovered specs

This is useful for broad changes like refactoring, where you don't know upfront which specs might be affected.

## Error Handling

- If no instruction is provided → ask the user what code change they want to make
- If the workflow is not found → tell the user to check that `.agent/workflows/templates/predefined/spec-enforcement/` exists
- If spec violations are found during VERIFY → the workflow will report them and stop
