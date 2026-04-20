# create-workflow

Interactive workflow creation assistant. Guides you through designing and generating a custom workflow definition.

## When to Use

- When you want to create a new workflow but aren't sure about the format
- When you want the LLM to help design the workflow steps and validation
- Directly: `/run-workflow create-workflow`
- With a starting point: `/run-workflow create-workflow --workflow_name my-pipeline --description "Extract and validate data from CSV files"`

## Steps

1. **LEARN** — LLM reads all engine documentation (overview, workflow-yaml format, structs, manifest) and examines existing workflows for reference patterns.
2. **DISCUSS** — Interactive: discuss the desired workflow with the user. Clarify steps, inputs, outputs, gates. Draft a design summary. User approves (human gate).
3. **CREATE** — Generate `workflow.yaml`, struct schemas (if needed), and `README.md` in `.agent/workflows/<name>/`.

## Parameters

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `workflow_name` | No | *(determined during DISCUSS)* | Name for the new workflow (kebab-case) |
| `description` | No | — | Brief description of the workflow's purpose |

## Output

The workflow generates files directly in `.agent/workflows/<name>/`:

```
.agent/workflows/<name>/
├── workflow.yaml           # Generated workflow definition
├── structs/                # Generated struct schemas (if needed)
│   └── *.schema.yaml
└── README.md               # Generated documentation
```

After creation, run the new workflow with:
```
/run-workflow <name> [--param value]
```

## Invocation (Cursor)

### Fully interactive — no params

```
/run-workflow create-workflow
```

The workflow will:
1. Read all engine documentation (overview, workflow-yaml format, structs, manifest)
2. Ask you to describe the task you want to automate
3. Help you design the steps, inputs, outputs, and gates
4. Generate the complete workflow definition

**Expected output:**
- `.agent/workflows/<name>/workflow.yaml` — generated workflow
- `.agent/workflows/<name>/structs/*.schema.yaml` — struct schemas (if needed)
- `.agent/workflows/<name>/README.md` — documentation

### With a starting point

```
/run-workflow create-workflow --workflow_name api-test-generator --description "Generate API integration tests from OpenAPI spec files"
```

Skips the naming discussion. The DISCUSS step starts with the provided description and refines it into a complete design.

### Name only

```
/run-workflow create-workflow --workflow_name data-migration
```

The subagent knows the target name but will ask you to describe the purpose and design the steps interactively.

### After creation — run the new workflow

Once `create-workflow` finishes, it will tell you how to run the generated workflow:

```
/run-workflow api-test-generator --spec_file "docs/openapi.yaml"
```

(The exact params depend on the workflow that was generated.)

## Files

| File | Purpose |
|------|---------|
| `workflow.yaml` | 3-step workflow (LEARN → DISCUSS → CREATE) |
| `structs/learn-summary.schema.yaml` | Schema for LEARN output |
| `structs/workflow-design.schema.yaml` | Schema for DISCUSS output |
