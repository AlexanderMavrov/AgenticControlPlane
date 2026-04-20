# registry-sync

Discover and register source files that implement behavioral specs but aren't tracked in `_registry.json`. Keeps the implementation mapping up-to-date after manual edits, new file creation, or refactoring.

## When to Use

- After manual code edits that affect spec-covered components
- After refactoring (renamed/moved files)
- Periodically, to catch drift between code and registry
- Directly: `/run-workflow registry-sync`
- For a specific component: `/run-workflow registry-sync --component EditField`

## Steps

| Step | Gate | Description |
|------|------|-------------|
| **SCAN** | structural + semantic | Read all specs and `_registry.json`. Search the codebase for unregistered implementations and stale entries. |
| **REVIEW** | structural + semantic + **human** | Present findings with confidence levels. User approves which files to add/remove. |
| **REGISTER** | structural + semantic | Apply approved changes to `_registry.json`. |

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `component` | No | *(all specs)* | Limit scan to a specific component |
| `search_paths` | No | *(entire project)* | Comma-separated directories to scan |

## What It Finds

- **New matches**: Files that implement a spec but aren't in `_registry.json`
- **Stale entries**: Files listed in `_registry.json` that no longer exist or no longer match
- **Confidence levels**: HIGH (filename + content match), MEDIUM (naming pattern), LOW (possible reference)

## Invocation (Cursor)

### Full scan — all specs

```
/run-workflow registry-sync
```

Scans the entire codebase against ALL specs in `_index.json`. Finds unregistered implementing files and stale entries.

**Expected output:**
- A grouped report showing new matches (with confidence: HIGH/MEDIUM/LOW) and stale entries per spec
- User approves which changes to apply (human gate)
- `.agent/specs/_registry.json` — updated with approved changes

### Specific component

```
/run-workflow registry-sync --component EditField
```

Scans only for files related to the `EditField` spec. Faster and more focused.

### Limit search directories

```
/run-workflow registry-sync --search_paths "src/components/,src/hooks/"
```

Restricts the scan to specific directories. Useful in large codebases where you know where the relevant code lives.

### Combined — component + search paths

```
/run-workflow registry-sync --component MessageQueue --search_paths "src/messaging/,src/utils/"
```

Scans only the specified directories for files implementing the `MessageQueue` spec.

### When to run

- After **manual code edits** that affect spec-covered components
- After **refactoring** (renamed or moved files) — catches stale registry entries
- After **adding new files** that implement existing specs
- **Periodically** as a hygiene task to keep `_registry.json` accurate

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 3-step workflow (SCAN → REVIEW → REGISTER) |
| `structs/scan-report.schema.yaml` | Schema for SCAN output |
| `structs/approved-changes.schema.yaml` | Schema for REVIEW output |
