---
name: learn-workflows
description: "Learn the Workflow Engine format by reading its documentation"
---

# /learn-workflows

Learn how the Workflow Engine works by reading its documentation.

## Usage

```
/learn-workflows
/learn-workflows <topic>
```

Topics: `overview`, `workflow-yaml`, `structs`, `manifest`, `specs`, `trace`, `all`

## What To Do

When the user invokes this skill, read the engine documentation and internalize the formats. This prepares you to create new workflows, write struct schemas, or understand existing workflow definitions.

### No topic specified (or `all`)

Read ALL documentation files in order:
1. `.agent/docs/overview.md` — key concepts, architecture, execution model
2. `.agent/docs/workflow-yaml.md` — workflow.yaml format, all fields, examples
3. `.agent/docs/structs.md` — struct schema format, validation options, examples
4. `.agent/docs/manifest.md` — manifest.json format, status values, resume behavior
5. `.agent/docs/specs.md` — behavioral spec format, _registry.json, Spec Guard
6. `.agent/docs/trace.md` — trace file format, invocation grouping, troubleshooting

After reading, tell the user:
> "I've read the Workflow Engine documentation. I understand:
> - How to define workflows in YAML (steps, inputs, outputs, gates)
> - How to write struct schemas for validation
> - How the manifest tracks runtime state
> - How the gate protocol works (structural → semantic → human)
> - How behavioral specs and Spec Guard work (_registry.json, _index.json)
> - How the trace system captures invocations and gate results
>
> I'm ready to help you create a new workflow, write struct schemas, or work with existing workflows."

### Specific topic

Read only the requested documentation file:
- `overview` → `.agent/docs/overview.md`
- `workflow-yaml` → `.agent/docs/workflow-yaml.md`
- `structs` → `.agent/docs/structs.md`
- `manifest` → `.agent/docs/manifest.md`
- `specs` → `.agent/docs/specs.md`
- `trace` → `.agent/docs/trace.md`

After reading, summarize what you learned and offer to help.

---

## When This Skill is Useful

- **Before creating a new workflow** — run `/learn-workflows` to understand the format
- **Before writing struct schemas** — run `/learn-workflows structs`
- **When debugging a workflow** — run `/learn-workflows manifest` to understand state tracking
- **For new team members or new LLM sessions** — quick onboarding to the engine
