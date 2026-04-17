# Spec Guard

## FIRST: Check for [spec] and [spec::] Patterns

**Before doing ANYTHING else, scan the user's message for these patterns:**

### `[spec::ComponentName]` — MUST invoke workflow

If the message contains `[spec::SomeName]`:

```
/run-workflow spec-write-and-implement --component <SomeName> --requirements "<user's text>"
```

**STOP. Do NOT read files, do NOT analyze code, do NOT create specs manually. Invoke the workflow IMMEDIATELY.** The workflow handles everything: discovery, clarification, spec writing, implementation, and validation with structural gates.

> **Note:** `.agent/` is gitignored — file search and directory listing won't find it. The `/run-workflow` skill reads files at exact paths, which works regardless of gitignore.

**Example:** `[spec::EditField] character limit should be 30, show red error at limit`
-> `/run-workflow spec-write-and-implement --component EditField --requirements "character limit should be 30, show red error at limit"`

### `[spec]` (without ::ComponentName) — MUST invoke workflow in auto-discovery mode

If the message contains `[spec]` but NOT `[spec::]`:

```
/run-workflow spec-write-and-implement --requirements "<user's text>"
```

**STOP. Same rule — invoke the workflow, do NOT handle inline.** The workflow will discover the component, clarify with the user, then write and implement.

### Why this is mandatory

These patterns are **explicit workflow triggers**. The user expects:
- Structural gate validation (not just LLM judgment)
- Manifest tracking and resume support
- Human approval gate at the CLARIFY step
- Traceable execution with audit trail

Handling these inline defeats the entire purpose.

### NO FALLBACK — EVER

- **Never** substitute with `/spec-fast`, `/code-spec-fast`, `/spec-with-workflows add`, manual spec creation, or direct code changes
- **Never** fall back to a "fast" or "lightweight" skill if the workflow template is not found — report the error to the user instead
- If `/run-workflow` fails to find the template, **STOP and tell the user**: "Workflow template `spec-write-and-implement` not found. Run `install.py --update` to deploy it."
- The fast skills (`/spec-fast`, `/code-spec-fast`, `/spec-add-fast`) are for **explicit user invocation only** — they are NOT alternatives to `[spec]`/`[spec::]`

---

## /spec-with-workflows add (spec only, no implementation)

`/spec-with-workflows add [component]` delegates to the `spec-write` workflow — with gates, manifest, and all 4 steps (DISCOVER -> CLARIFY -> WRITE-SPEC -> REGISTER-SPEC). The difference from `[spec::]` is that `/spec-with-workflows add` creates/updates the spec **without** implementing it in code. Use when you only need the spec document, not code changes.

---

## Before Code Changes

**CRITICAL:** Before modifying code for any component or module:

1. **Check** if `.agent/specs/` contains specs relevant to the component you are modifying
2. **Read** any matching spec files
3. **Verify** your planned changes do NOT violate any existing requirements
4. If a change **would violate** a spec:
   - **WARN** the user: "This change would violate spec `{name}`: {requirement}"
   - **ASK** for confirmation before proceeding
   - If the user confirms the change: **update the spec FIRST**, then make the code change
5. **NEVER** silently remove or degrade behavior that is documented in a spec

## Spec Override

If the user explicitly wants to change an established requirement:
1. Update the spec file first (change the requirement text, add Source changelog entry)
2. Then make the code change
3. The spec always reflects the current desired state

## Finding Relevant Specs

> **`.agent/` is gitignored** — do NOT use Glob or Grep to search inside it. Use `list_agent_files` MCP tool to discover files, or Read tool with exact paths.

To determine which specs are relevant to a code change:
- Read `.agent/specs/_registry.json` directly for file-to-spec mappings
- Match by component name (file name <-> spec name)
- Match by domain (directory structure)
- When uncertain, read `.agent/specs/_index.json` for the full spec catalog

## Spec Repository

```
.agent/specs/
├── _index.json          # Auto-generated registry of all specs
├── _registry.json       # Maps specs to implementing files
└── {domain}/            # Per-domain organization
    └── {Component}.md   # One spec per component/module
```

Each spec is a Markdown file with YAML frontmatter (metadata) and a body with Requirements, Constraints, Examples, and Source changelog. Format reference: `.agent/docs/specs.md`.
