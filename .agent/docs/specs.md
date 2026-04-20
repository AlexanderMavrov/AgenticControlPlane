# Behavioral Specs — Format Reference

Behavioral specs describe **requirements for how components and modules must behave**. They live in `.agent/specs/{scope}/{domain}/` and are enforced by the Spec Guard rule.

> **Scope:** an orthogonal axis added on top of domain. Specs may apply only in a specific integration, platform, or product variant (e.g., "astro", "ares"), while others are universal ("generic"). Section "Scopes" below covers the full model. For projects that do not need multi-scope isolation, the default `generic` scope applies invisibly — existing workflows continue to work unchanged.

## Purpose

- **Persistence**: Requirements survive across chat sessions — the LLM reads them every time
- **Enforcement**: The always-active Spec Guard rule checks specs before code changes
- **Documentation**: Specs are human-readable documentation of design decisions
- **Traceability**: `_registry.json` maps specs to implementing files

## File Location

```
.agent/specs/
├── _scope-config.json        # Optional: declared scopes
├── generic/                  # Implicit scope; always present
│   ├── _index.json
│   ├── _registry.json
│   └── security/
│       └── SEC-001.md
├── astro/                    # Declared in _scope-config.json
│   ├── _index.json
│   ├── _registry.json
│   ├── nvram/                # Domain under scope
│   │   └── NVRM-001.md
│   └── recovery/
│       └── RECV-001.md
└── ares/
    ├── _index.json
    ├── _registry.json
    └── nvram/
        └── NVRM-001.md       # Same spec_id as astro; no collision (different scope dir)
```

**Scope** is a *where/in-what-context* axis. Every spec belongs to exactly one primary scope; its file path includes the scope id. The reserved `generic` scope is always present and applies across all integrations. See "Scopes" below.

**Domain** is a *what-about* axis — a logical grouping within a scope (e.g., `ui`, `messaging`, `nvram`, `recovery`).

**Per-scope index files:** `_index.json` and `_registry.json` live inside each scope directory, not at the specs root. Cross-scope queries compute aggregates on the fly from all per-scope files.

**Naming rules:**
- **Component names** must match `^[A-Za-z][A-Za-z0-9_-]*$` — letters, digits, hyphens, underscores only. No spaces, slashes, or special characters. The name is used directly in file paths (`.agent/specs/{domain}/{component}.md`), so invalid characters would create broken paths.
- **Domain names** follow the same rule: `^[a-z][a-z0-9_-]*$` (lowercase recommended).
- **`spec_id` conventions**: In spec frontmatter, `spec_id` is the bare component name (e.g., `EditField`). In `_index.json`, spec_id uses `{domain}/{component}` format (e.g., `ui/EditField`) for global uniqueness. The `doc-spec-extraction` workflow uses a different convention: `DOMAIN-NNN` (e.g., `MSG-001`) for auto-extracted specs — this is specific to that workflow and does not affect interactive specs.

## Spec File Format

Each spec is a Markdown file with YAML frontmatter:

```markdown
---
spec_id: EditField
component: EditField
domain: ui
tags: [input, validation, forms]
status: active
created_at: 2026-03-13
updated_at: 2026-03-13
---

# EditField

## Requirements

- MUST enforce character limit of 30 characters maximum
- MUST show error message in RED when character limit is reached
- MUST block input beyond 31 characters (must not appear on screen)
- MUST disable Submit button when input exceeds character limit

## Constraints

- Error message must be visible without scrolling
- Character count must update in real-time

## Examples

Valid state: 25 characters entered, no error, Submit enabled
Error state: 30 characters entered, red error shown, Submit enabled
Blocked state: 31+ characters attempted, input blocked, Submit disabled

## Source

- [2026-03-13] Initial: character limit of 30 + red error message
- [2026-03-13] Added: input blocking at 31 chars + Submit button disable
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `spec_id` | string | Yes | Unique identifier (usually same as component name) |
| `component` | string | Yes | Component or module name |
| `domain` | string | Yes | Logical grouping (ui, messaging, recovery, etc.) |
| `tags` | list | No | Searchable tags for categorization |
| `status` | string | Yes | `active` or `deprecated` |
| `created_at` | string | Yes | ISO date when spec was created |
| `updated_at` | string | Yes | ISO date of last update |

### Body Sections

| Section | Required | Description |
|---------|----------|-------------|
| `## Requirements` | Yes | Behavioral requirements. Use MUST/SHOULD/MAY severity. |
| `## Constraints` | No | Non-functional constraints (performance, visibility, etc.) |
| `## Examples` | No | Expected states and behaviors |
| `## Source` | Yes | Changelog — when each requirement was added/changed |

### Requirement Severity

- **MUST** — Mandatory. Violation = bug.
- **SHOULD** — Recommended. Can be overridden with justification.
- **MAY** — Optional. Nice-to-have.

## Index File (`_index.json`)

Auto-generated registry of all specs. The `spec_id` field uses `{domain}/{component}` format to ensure global uniqueness (two components with the same name in different domains won't collide):

```json
{
  "version": 1,
  "updated_at": "2026-03-13T14:00:00+02:00",
  "specs": [
    {
      "spec_id": "ui/EditField",
      "component": "EditField",
      "domain": "ui",
      "tags": ["input", "validation", "forms"],
      "status": "active",
      "file_path": "specs/ui/EditField.md",
      "requirements_count": 4,
      "created_at": "2026-03-13",
      "updated_at": "2026-03-13"
    }
  ]
}
```

**Note:** The `spec_id` format changed from bare component name to `{domain}/{component}` to prevent collisions. When searching for a spec by component name, match on the `component` field, not `spec_id`.

## Registry File (`_registry.json`)

Maps specs to implementing source files — both direct implementations and indirect dependencies (imports, styles, configs, tests). This enables Spec Guard to detect violations in files that transitively affect a spec.

Each entry in `implemented_by` has a `file` path and a `relationship` type:

| Relationship | Meaning | Example |
|-------------|---------|---------|
| `direct` | Primary implementation of the component | `EditField.tsx` |
| `imports` | Module imported by the direct file that contains spec-relevant logic | `fieldRules.ts` (char limit constant) |
| `imported_by` | Module that imports the direct file and relays spec behavior | `FormBuilder.tsx` (uses EditField) |
| `style` | CSS/SCSS that styles the component | `EditField.module.css` |
| `config` | Config, i18n, or constants with values mentioned in the spec | `en.json` (error messages) |
| `test` | Test file that verifies spec requirements | `EditField.test.tsx` |

```json
{
  "version": 2,
  "updated_at": "2026-03-13T14:00:00+02:00",
  "mappings": {
    "EditField": {
      "spec": "specs/ui/EditField.md",
      "implemented_by": [
        { "file": "src/components/EditField.tsx", "relationship": "direct" },
        { "file": "src/validation/fieldRules.ts", "relationship": "imports" },
        { "file": "src/styles/EditField.module.css", "relationship": "style" },
        { "file": "src/tests/EditField.test.tsx", "relationship": "test" }
      ],
      "last_verified": "2026-03-13",
      "verified_by": "spec-enforcement"
    }
  }
}
```

> **Version note:** v2 changed `implemented_by` from `string[]` to `object[]` with `relationship` types. All new installations use v2.

## Creating Specs

Three ways to create specs:

1. **Manual**: Create `.agent/specs/{domain}/{Component}.md` with proper frontmatter
2. **Skill**: `/spec-with-workflows add ComponentName` — interactive creation with LLM assistance
3. **Chat pattern**: `[spec::ComponentName] your requirements here` — triggers the spec-write-and-implement workflow

## Scopes

A **scope** declares the context in which a spec applies. Typical uses:
- Per-integration isolation (e.g., `astro` vs `ares`)
- Per-platform rules (e.g., `windows`, `linux`)
- Per-market/regulatory regime (e.g., `italy-aams`)
- Cross-integration invariants (always the reserved `generic` scope)

### The `generic` scope is special

- Always available — no need to declare it
- Reserved id — cannot appear in `_scope-config.json`
- Included alongside the active scope in every read operation
- When the project has no `_scope-config.json`, *everything* is implicitly `generic`

### Project configuration — `_scope-config.json`

Optional. Lives at `.agent/specs/_scope-config.json`. Declares scopes beyond `generic`:

```json
{
  "scopes": [
    { "id": "astro", "label": "Astro VLT integration (AK2API 1.8.x)" },
    { "id": "ares",  "label": "Ares VLT integration (EOS Framework 1.8)" }
  ],
  "default_active_scope": "astro"
}
```

- `scopes[]` — id must match `^[a-z][a-z0-9-]*$`; doubles as the directory name
- `label` — optional human-readable description (UI only, no logic impact)
- `default_active_scope` — team-level default; falls back to `generic` if absent

Projects with no `_scope-config.json` operate in effectively single-scope mode — everything is `generic`, no cognitive overhead.

### Active scope — user-level override

Active scope is the **currently selected working context**. Every spec-touching workflow/skill defaults to it when no `--scope` is given.

Resolution priority:
1. CLI `--scope <id>` (per-command, not persisted)
2. `.agent/local/active-scope` — plain text, gitignored, per-developer
3. `_scope-config.json` → `default_active_scope` — team default
4. `generic` — hard-coded fallback

Commands (skills):
- `/scope-show` — display active scope and resolution source
- `/scope-set <id>` — set user override (writes `.agent/local/active-scope`)
- `/scope-set <id> --project` — set team default (writes `_scope-config.json`)
- `/scope-unset` — remove user override
- `/scope-list` — list available scopes
- `/scope-add <id> "<label>"` — declare a new scope (adds entry + creates directory)

### Spec frontmatter `scope` field

Scope is declared in the YAML frontmatter:

```yaml
---
spec_id: NVRM-001
scope: [astro]
domain: nvram
...
---
```

- `scope` is an array of scope ids. Primary scope = first entry (determines directory location).
- Missing `scope` field is treated as `[generic]` for backwards compatibility with pre-scoping specs.
- Multi-scope specs (same rule applicable across several integrations) use `scope: [astro, ares]`; the file lives in the primary scope directory.

### Cross-scope references

`related_specs` supports three forms:

- `NVRM-002` — same-scope (resolved within the current scope)
- `astro:NVRM-002` — cross-scope, short
- `astro/nvram/NVRM-002` — cross-scope, fully qualified path

### Scope write protection

A PreToolUse hook (`scope-write-validator.py`) blocks writes to a scope directory that does not match the user's active scope. This prevents agents from accidentally overwriting an existing scope's specs when the active scope differs.

- Writes to `.agent/specs/generic/**` are always allowed (universal rules apply in every context).
- The hook is a defensive layer — the authoritative guard is the workflow's `--scope` resolution.

## Scope Usage Patterns (for LLMs / agents)

The rules below prescribe **how an agent must behave** when operating on specs. They are normative — the engine, hooks, and workflows assume this behavior.

### When reading specs

1. **Default load set = active scope + generic.** When no explicit scope is given, load specs from `.agent/specs/<active_scope>/` *and* `.agent/specs/generic/`. Never load other scopes unless the user/workflow explicitly requests it.

2. **Inferring active scope.** Read `.agent/local/active-scope` if present; otherwise read `default_active_scope` from `_scope-config.json`; otherwise assume `generic`. Never infer scope from file paths the user mentions in their request — that is a design choice (too error-prone). Explicit resolution or `generic` only.

3. **Cross-scope queries require `--scope`.** If the user asks "list all specs across all integrations", or the workflow explicitly passes `--scope all` / `--scope a,b`, include the requested scopes. Otherwise, stay within the default load set.

4. **`_index.json` is per-scope.** To list every spec across all scopes, iterate over each scope directory's `_index.json`. There is no global index file.

5. **Backwards compatibility.** A spec without a `scope:` frontmatter field is treated as `scope: [generic]` for all read operations. Never silently upgrade the frontmatter — if a migration is appropriate, the user/workflow must invoke it explicitly.

### When writing or creating specs

1. **Determine target scope first.**
   - If the workflow passes `--scope <id>`, use that.
   - Else, use active scope (via resolution chain).
   - If neither is available and a write is destructive (e.g., `doc-spec-extraction` EXTRACT step), surface the resolved scope in the human gate for confirmation — never write silently.

2. **Target scope must exist.** If the target is not `generic` and not declared in `_scope-config.json`, stop with an error. Do not silently create a new scope. The user creates scopes deliberately with `/scope-add`.

3. **Destination path.** Always write to `.agent/specs/<target_scope>/<domain>/<id>.md`. Primary scope = first element of the spec's `scope:` array. Set `scope:` frontmatter to match the target path.

4. **Cross-scope related_specs.** When a spec references specs in other scopes, always use qualified form (`astro:NVRM-002` or `astro/nvram/NVRM-002`). Same-scope references may be bare (`NVRM-002`). Verify referenced specs exist.

5. **Mass-updating specs.** When updating multiple specs in the same scope (e.g., COMMIT step of extraction), operate only within that scope's directory. Never touch files under a different scope id, even if the spec_id or domain matches.

### When the user's request is ambiguous

If the user says "audit our specs" without specifying scope, and the project has multiple scopes declared:

- If a destructive workflow (audit/enforcement): **ask** which scope, or hand them the list of scopes and suggest `--scope <id>` / `--scope all`.
- If a read-only view: default to active scope + generic, state this in the response ("Showing specs in active scope `astro` + `generic`"), and offer `--scope all` for wider view.

### When encountering the write-validator hook

If you (the LLM) get a `scope-write-validator: BLOCKED` error with exit 2 from stderr:

1. **Do not retry the same write.** The block is deterministic; retrying will hit the same error.
2. **Re-examine intent.** Is the active scope correct? Was a `--scope` flag dropped by the workflow? Is the path you're writing to correct for the requested operation?
3. **Surface the mismatch to the user.** Tell them the active scope, the target scope from the path, and ask for confirmation before proposing `/scope-set` or changing the workflow invocation.
4. **Never bypass by changing the path to generic/.** If the spec is genuinely scope-specific, that would lose information. Only use `generic/` when the rule is truly universal.

### Nuances to know

- **Scope is not inheritance.** There is no "if spec X in astro extends a generic spec". Specs are independent documents; use `related_specs` to link them but do not assume any spec is "overridden" by another.

- **Scope ≠ version.** The system intentionally does not model versions as sub-scopes. If you need to distinguish `astro-v1.8` from `astro-v2.0`, create them as separate scopes (`astro-legacy` / `astro-current`) or handle the versioning within the spec body.

- **Same spec_id across scopes is NOT a collision.** `astro/nvram/NVRM-001.md` and `ares/nvram/NVRM-001.md` coexist cleanly. When comparing them, be explicit about which one you mean.

- **`generic` writes are always allowed, but that doesn't make them always *correct*.** Writing a truly integration-specific rule to `generic/` contaminates the universal scope. When uncertain whether a rule is universal, prefer writing it to the active scope; promote to `generic` only after seeing the same rule apply in 2+ scopes.

- **Multi-scope specs (`scope: [a, b]`) are advanced.** Reserve for specs that are genuinely identical across scopes. If two specs diverge later, split into separate per-scope files with `related_specs` cross-references.

- **`_scope-config.json` may be absent.** Absence means "no additional scopes beyond `generic`". Treat it the same as an empty config. Never fail on missing file; only fail on malformed content.

- **Don't cache active scope across long operations.** Active scope can be changed by the user mid-conversation via `/scope-set`. Re-resolve before destructive writes.

## Spec Lifecycle

```
Created → Active → (Updated)* → Deprecated
```

- **Created**: New spec, no implementing code yet (valid state)
- **Active**: Spec with implementing code, enforced by Spec Guard
- **Updated**: Requirements changed, Source changelog entry added
- **Deprecated**: `status: deprecated` — Spec Guard ignores it
