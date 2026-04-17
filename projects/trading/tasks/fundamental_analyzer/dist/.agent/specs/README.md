# Behavioral Specs

This directory contains behavioral specifications — requirements that components must satisfy. The LLM checks these specs before making code changes (via the Spec Guard always-active rule).

## Structure

```
specs/
├── _index.json          # Registry of all specs (auto-maintained)
├── _registry.json       # Implementation mapping: which files implement which specs
├── README.md            # This file
└── {domain}/            # Per-domain directories
    └── ComponentName.md # Individual spec (YAML frontmatter + Markdown body)
```

## How to Add Specs

- **From chat:** Type `[spec::ComponentName]` followed by your requirements. The LLM will invoke the `spec-write-and-implement` workflow to capture, refine, and implement the spec.
- **Via skill:** Run `/spec-with-workflows add ComponentName` and follow the interactive CLARIFY flow.
- **Manually:** Create a `.md` file in the appropriate domain directory following the format in `.agent/docs/specs.md`.

## Format Reference

See `.agent/docs/specs.md` for the full spec format (frontmatter fields, body sections, severity levels).

## Key Files

| File | Purpose | Edited by |
|------|---------|-----------|
| `_index.json` | Metadata for all specs | `/spec-with-workflows` skill, workflows |
| `_registry.json` | Maps specs to implementation files | REGISTER step of `spec-enforcement` workflow (also via delegation from `spec-write-and-implement`) |
| `{domain}/*.md` | Individual behavioral specs | `/spec-with-workflows add`, manual, workflows |
