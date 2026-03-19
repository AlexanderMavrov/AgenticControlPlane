# spec-write-and-implement

Write or update a behavioral spec, then delegate to `spec-enforcement` for implementation, verification, and registration.

## When to Use

- Triggered by `[specs::ComponentName]` pattern in chat (via Spec Guard rule) — **targeted mode**
- Triggered by `[spec]` pattern in chat (via Spec Guard rule) — **auto-discovery mode**
- Triggered by `/spec add ComponentName` or `/spec add` (via /spec skill)
- Directly: `/run-workflow spec-write-and-implement --component EditField`
- Auto-discovery: `/run-workflow spec-write-and-implement --requirements "description of what you need"`

## Two Modes

### Mode A: Targeted (with `--component`)

You specify the component name. The workflow searches for an existing spec by that name and proceeds directly to refining requirements.

### Mode B: Auto-discovery (without `--component`)

You describe what you need in natural language. The CLARIFY step:
1. Reads all existing specs from `_index.json`
2. Analyzes your description to identify the relevant component
3. Searches for overlapping or related existing specs
4. **Proposes** a component name, domain, and whether this is new or an update
5. Waits for your confirmation before proceeding

This is useful when you know **what** you want but not **which component it belongs to**.

## Steps

1. **CLARIFY** — Interactive: auto-discover component (if needed), refine requirements, draft concise summary, get approval (human gate)
2. **WRITE-SPEC** — Create/update `.agent/specs/{domain}/{Component}.md` + `_index.json`
3. **ENFORCE** — `delegate_to: spec-enforcement` — hand-off for implementation (skippable via `--implement false`)

The ENFORCE step delegates to `spec-enforcement`, which runs:
- CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `component` | No | *(auto-discover)* | Component name (e.g., EditField). If omitted, CLARIFY discovers it from requirements text |
| `domain` | No | *(auto-detect)* | Logical domain (ui, messaging, etc.) |
| `requirements` | No | — | Initial requirements text from user |
| `implement` | No | `true` | Set to `false` to only write spec without code changes |

## Workflow Composition

This workflow demonstrates `delegate_to:` — workflow hand-off:

```
spec-write-and-implement:           spec-enforcement:
  CLARIFY (human gate)                CHECK-SPECS
  WRITE-SPEC                          IMPLEMENT
  ENFORCE ─── delegate_to ──────→     VERIFY
                                      REGISTER
```

## Invocation (Cursor)

### Targeted — create a spec for a known component

```
/run-workflow spec-write-and-implement --component EditField
```

The workflow will:
1. Ask you to describe the behavioral requirements for `EditField`
2. Refine them into a structured MUST/SHOULD/MAY list
3. Ask for your approval (human gate)
4. Create `.agent/specs/<domain>/EditField.md` (domain auto-detected or asked)
5. Delegate to `spec-enforcement` → implement, verify, register

**Expected output:**
- `.agent/specs/ui/EditField.md` — behavioral spec
- `.agent/specs/_index.json` — updated index
- `.agent/specs/_registry.json` — updated with implementing files
- Code changes that satisfy all spec requirements

### Auto-discovery — describe what you need, let the workflow figure out the rest

```
/run-workflow spec-write-and-implement --requirements "The save button should be disabled while the form is submitting. Show a spinner. Re-enable after success or failure."
```

The CLARIFY step will:
1. Read `_index.json` to see all existing specs
2. Analyze the description → likely component: `SaveButton` or `FormSubmit`
3. Check if a related spec already exists (e.g., `SubmitButton`, `FormValidation`)
4. Propose: "I think this belongs to component **SaveButton** in domain **ui**. Related: FormValidation spec. Is this correct?"
5. You confirm or correct → workflow proceeds as normal

**Expected output:** same as targeted mode, but the component name is discovered interactively.

### Using `[spec]` in chat (auto-discovery shorthand)

```
[spec] When the user clicks "Export", the system should generate a ZIP file
containing all selected items. MUST show progress bar. MUST handle errors gracefully.
```

Spec Guard recognizes `[spec]` (without `::ComponentName`) and invokes auto-discovery mode. The workflow analyzes your text, proposes a component name, and asks for confirmation.

### Using `[specs::X]` in chat (targeted shorthand)

```
[specs::EditField] character limit should be 30, show red error at limit
```

Spec Guard recognizes `[specs::EditField]` and invokes targeted mode with `component=EditField`.

### With domain and initial requirements

```
/run-workflow spec-write-and-implement --component MessageQueue --domain messaging --requirements "MUST process messages in FIFO order. MUST retry failed messages up to 3 times. SHOULD log all message transitions."
```

Skips some back-and-forth in the CLARIFY step because requirements are pre-filled. The subagent still refines and asks for approval.

### Spec only — no code changes

```
/run-workflow spec-write-and-implement --component SessionTimer --domain recovery --implement false
```

Creates the spec file but skips the ENFORCE step entirely. Useful when you want to define requirements first and implement later.

**Expected output:**
- `.agent/specs/recovery/SessionTimer.md` — behavioral spec
- `.agent/specs/_index.json` — updated index
- No code changes, no registry update

### Auto-discovery + spec only

```
/run-workflow spec-write-and-implement --requirements "Error messages should use red background, bold text, and fade in with animation" --implement false
```

Discovers the component (e.g., `ErrorDisplay` in `ui` domain), writes the spec, but does NOT implement. Useful for planning ahead.

### Update an existing spec

```
/run-workflow spec-write-and-implement --component EditField --requirements "MUST support maximum 256 characters (changed from 128)"
```

If a spec already exists for `EditField`, the CLARIFY step shows the current requirements and merges the new ones. The WRITE-SPEC step updates the existing file with a changelog entry.

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 3-step workflow (CLARIFY → WRITE-SPEC → ENFORCE via delegation) |
| `structs/approved-requirements.schema.yaml` | Schema for CLARIFY output |
