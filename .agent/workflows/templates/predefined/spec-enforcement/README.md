# spec-enforcement

Implement code changes while respecting all behavioral specs. This workflow checks existing specs before implementation, verifies no violations after, and registers affected files.

## When to Use

- Via `/code-with-spec <instruction>` — implement a change with spec enforcement (no spec creation)
- Via `delegate_to` from `spec-write-and-implement` — after a new spec is created, enforce it
- Directly: `/run-workflow spec-enforcement --component EditField`

## Steps

1. **CHECK-SPECS** — Gather all relevant specs for the component. Find the primary spec and related specs that must not be violated.
2. **IMPLEMENT** — Make the code change, respecting all specs. Stop and report if conflicts are found.
3. **VERIFY** — Post-implementation verification. Check ALL modified files against ALL mapped specs.
4. **REGISTER** — Update `_registry.json` with the implementation mapping.

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `component` | No | auto-discover | Component name (e.g., `EditField`). If omitted, auto-discovers affected specs from the instruction. |
| `domain` | No | auto-detect | Logical domain (e.g., `ui`) |
| `instruction` | No | — | Specific code change instruction |
| `spec_path` | No | auto-search | Explicit path to the spec file |

## Invocation (Cursor)

### Mode A — Targeted (specific component)

```
/run-workflow spec-enforcement --component EditField
```

Reads the spec for `EditField`, finds its implementing files, implements ALL requirements from the spec, verifies, and registers.

**Expected output:**
- Code changes that satisfy the `EditField` spec
- `.agent/specs/_registry.json` — updated with implementing files
- Verification report confirming no spec violations

### With domain (explicit spec location)

```
/run-workflow spec-enforcement --component MessageQueue --domain messaging
```

Looks for the spec at `.agent/specs/messaging/MessageQueue.md` instead of searching all domains.

### With specific instruction

```
/run-workflow spec-enforcement --component EditField --instruction "Add character counter display that updates on each keystroke"
```

Instead of implementing ALL spec requirements, focuses on the specific instruction. Still checks that the change doesn't violate any existing spec.

### With explicit spec path

```
/run-workflow spec-enforcement --component SessionTimer --spec_path ".agent/specs/recovery/SessionTimer.md"
```

Skips the spec search and reads directly from the provided path.

### Mode B — Auto-discovery (no component, just instruction)

```
/run-workflow spec-enforcement --instruction "Refactor the validation logic to use a shared utility module"
```

No component specified — the workflow analyzes the instruction, searches the codebase for affected files, checks `_registry.json` to find ALL specs that map to those files, and enforces them all.

**Expected output:**
- Code changes following the instruction
- Verification that NO existing spec was violated by the refactoring
- Updated `_registry.json` if file paths changed

### Typical use via /code-with-spec skill

```
/code-with-spec Refactor the validation logic to use a shared utility module
```

The `/code-with-spec` skill internally invokes `spec-enforcement` in auto-discovery mode. You don't need to call `/run-workflow` directly for this use case.

## Relation to spec-write-and-implement

`spec-write-and-implement` handles spec **creation** (CLARIFY + WRITE-SPEC), then delegates to `spec-enforcement` for **implementation** (CHECK-SPECS + IMPLEMENT + VERIFY + REGISTER).

```
spec-write-and-implement:           spec-enforcement:
  CLARIFY                             CHECK-SPECS
  WRITE-SPEC                          IMPLEMENT
  delegate_to: spec-enforcement  →    VERIFY
                                      REGISTER
```
