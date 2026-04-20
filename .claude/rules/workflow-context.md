---
paths:
  - ".agent/workflows/**/*"
  - ".agent/specs/**/*"
---

# Agentic Control Plane Context

You are working with Agentic Control Plane files (Workflow Engine + Spec Guard).

Documentation is at `.agent/docs/` — read it if you need format reference.

## CRITICAL: /run-workflow Protocol

**When the user invokes `/run-workflow` (or you need to execute a workflow), you MUST:**

1. **Read the skill file FIRST** — `.claude/skills/run-workflow/SKILL.md` — before doing anything else. This file contains the mandatory protocol, anti-patterns, and error handling.
2. **Verify MCP tools** — call `workflow_resolve` via MCP as the very first action. If it succeeds, use MCP (`workflow_init`, `step_begin`, `step_collect_result`, `step_complete`, `workflow_finalize`) for the ENTIRE run.
3. **NEVER orchestrate manually** when MCP tools are available. NEVER call per-step agent types directly (e.g., `doc-spec-extraction-analyze`). NEVER write `manifest.json` by hand.

Skipping this protocol results in: no trace file, no gate validation, no audit history, corrupted workflow state.

## Workflow Engine Conventions

- `workflow.yaml` defines steps, inputs, outputs, and gate config
- Struct schemas in `structs/` define expected I/O formats
- `manifest.json` is auto-generated — **never edit it manually**
- `context/` contains auto-generated step summaries — **never edit manually**
- Use `/run-workflow` to execute a workflow
- Use `/learn-workflows` to learn the format before creating new workflows
- Predefined workflows live in `.agent/workflows/templates/predefined/` — **do not modify** (engine distribution)
- User workflows live in `.agent/workflows/templates/my_workflows/`

## Spec Guard Conventions

- Behavioral specs live in `.agent/specs/{scope}/{domain}/ComponentName.md`
- Each spec has YAML frontmatter (`spec_id`, `component`, `domain`, `severity`, `scope`) + Markdown body
- `_index.json` and `_registry.json` are **per-scope** (inside each scope directory)
- Active scope resolution: `.agent/local/active-scope` -> `_scope-config.json` default -> `generic`
- Use `/spec` to view specs (list, show)
- Use `/spec-with-workflows` to create or audit specs via workflow engine (add, audit)
- `[spec::ComponentName]` in chat triggers the full spec pipeline via `/run-workflow spec-write-and-implement`
- `[spec]` (without component) triggers auto-discovery via `/run-workflow spec-write-and-implement`
- `/spec-with-workflows add` delegates to the `spec-write` workflow (spec only, no implementation)
- Spec format reference: `.agent/docs/specs.md`
