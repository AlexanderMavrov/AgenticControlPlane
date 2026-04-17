# spec-write-and-implement

Composition workflow — delegates to `spec-write` then `spec-enforcement`. No inline steps.

## When to Use

- Triggered by `[spec::ComponentName]` pattern in chat (via Spec Guard rule) — **targeted mode**
- Triggered by `[spec]` pattern in chat (via Spec Guard rule) — **auto-discovery mode**
- Directly: `/run-workflow spec-write-and-implement --component EditField`
- Auto-discovery: `/run-workflow spec-write-and-implement --requirements "description of what you need"`

**Note:** `/spec-with-workflows add` triggers the `spec-write` workflow (spec only, no implementation). For spec + implementation, use `[spec::]`, `[spec]`, or `/run-workflow spec-write-and-implement`.

## Two Modes

### Mode A: Targeted (with `--component`)

You specify the component name. The `spec-write` workflow searches for an existing spec by that name and proceeds directly to refining requirements.

### Mode B: Auto-discovery (without `--component`)

You describe what you need in natural language. The CLARIFY step in `spec-write`:
1. Reads all existing specs from `_index.json`
2. Analyzes your description to identify the relevant component
3. Searches for overlapping or related existing specs
4. **Proposes** a component name, domain, and whether this is new or an update
5. Waits for your confirmation before proceeding

Discovered values (`component`, `domain`) propagate back to the parent via `param_bindings` on the delegation step.

## Steps

This workflow has **2 delegation steps** — no inline logic:

1. **WRITE** — `delegate_to: spec-write` — discover overlaps, clarify requirements (human gate), write spec, register in `_index.json`
2. **ENFORCE** — `delegate_to: spec-enforcement` — implement code, verify no specs violated, register in `_registry.json` (skippable via `--implement false`)

```
spec-write-and-implement:
  WRITE ─── delegate_to ──→  spec-write:
                                DISCOVER
                                CLARIFY (human gate)
                                WRITE-SPEC
                                REGISTER-SPEC

  ENFORCE ── delegate_to ──→  spec-enforcement:
                                CHECK-SPECS
                                IMPLEMENT
                                VERIFY
                                REGISTER
```

Each delegated workflow runs with its own manifest in a **sibling directory** (not a subdirectory of the parent).

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `component` | No | *(auto-discover)* | Component/subsystem/convention name (e.g., EditField, nvram, exit-code). If omitted, discovered in CLARIFY |
| `domain` | No | *(auto-detect)* | Logical domain (ui, messaging, protocol, etc.) |
| `requirements` | No | — | Initial requirements text from user |
| `implement` | No | `true` | Set to `false` to only write spec without code changes |

## Param Propagation

In auto-discovery mode, `component` and `domain` start empty. The `spec-write` workflow discovers them in its CLARIFY step. After delegation completes, `param_bindings` on the WRITE step read `component` and `domain` from `spec-write/data/approved-requirements.json` and update the parent manifest. The ENFORCE step then receives populated values.

## Invocation Examples

### Targeted — create a spec for a known component

```
/run-workflow spec-write-and-implement --component EditField
```

### Auto-discovery — describe what you need

```
/run-workflow spec-write-and-implement --requirements "The save button should be disabled while the form is submitting. Show a spinner."
```

### Using `[spec::X]` in chat (targeted shorthand)

```
[spec::EditField] character limit should be 30, show red error at limit
```

### Using `[spec]` in chat (auto-discovery shorthand)

```
[spec] When the user clicks "Export", the system should generate a ZIP file
containing all selected items. MUST show progress bar.
```

### Spec only — no code changes

```
/run-workflow spec-write-and-implement --component SessionTimer --domain recovery --implement false
```

Creates the spec file but skips the ENFORCE delegation entirely.

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 2-step composition workflow (WRITE → ENFORCE via delegation) |
