# Behavioral Specs — Format Reference

Behavioral specs describe **requirements for how components and modules must behave**. They live in `.agent/specs/{domain}/` and are enforced by the Spec Guard rule.

## Purpose

- **Persistence**: Requirements survive across chat sessions — the LLM reads them every time
- **Enforcement**: The always-active Spec Guard rule checks specs before code changes
- **Documentation**: Specs are human-readable documentation of design decisions
- **Traceability**: `_registry.json` maps specs to implementing files

## File Location

```
.agent/specs/
├── _index.json              # Auto-generated: all specs metadata
├── _registry.json           # Auto-generated: spec → file mappings
├── ui/                      # Domain: user interface
│   ├── EditField.md
│   └── SubmitButton.md
├── messaging/               # Domain: message system
│   └── MessageQueue.md
└── recovery/                # Domain: error recovery
    └── SessionRecovery.md
```

**Domain** is a logical grouping (e.g., `ui`, `messaging`, `recovery`, `accounting`, `rng`). Choose the domain that best fits the component.

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

## Spec Lifecycle

```
Created → Active → (Updated)* → Deprecated
```

- **Created**: New spec, no implementing code yet (valid state)
- **Active**: Spec with implementing code, enforced by Spec Guard
- **Updated**: Requirements changed, Source changelog entry added
- **Deprecated**: `status: deprecated` — Spec Guard ignores it
