# Agentic Control Plane — Examples

Project-specific example workflows demonstrating the engine's capabilities.

> **Note:** Generic/reusable workflows (like `spec-write-and-implement`) live in `.agent/workflows/predefined/`, not here. Examples are project-specific use cases.

## Available Examples

| Example | Description | Steps |
|---------|-------------|-------|
| [astro-spec-extraction](astro-spec-extraction/) | Extract validation specs from Astro Programming Guide v3.2 | PLAN → EXTRACT → RECONCILE → COMMIT |

## Reference Files

| File | Description |
|------|-------------|
| [sample-workflow.yaml](sample-workflow.yaml) | Annotated `spec-enforcement` workflow definition — shows all config fields with comments explaining `carry_forward`, `spec_check`, `inject` modes, etc. |
| [sample-trace.json](sample-trace.json) | Execution trace produced by `sample-workflow.yaml` — load in Trace Viewer (`.agent/tools/trace-viewer.html`) to see how config maps to execution |

## How to Use an Example

1. **Install the engine** in your project (if not done):
   ```bash
   python install.py <your-project-path>
   ```

2. **Copy the example** to your project's `.agent/workflows/` directory:
   ```bash
   mkdir -p <your-project>/.agent/workflows/<example-name>/structs
   cp examples/<example-name>/workflow.yaml <your-project>/.agent/workflows/<example-name>/
   cp examples/<example-name>/structs/*.schema.yaml <your-project>/.agent/workflows/<example-name>/structs/
   ```

3. **Run it** in Cursor:
   ```
   /run-workflow <example-name>
   ```

Each example has its own README with project-specific setup instructions.

## Predefined vs Example Workflows

| Location | Purpose | Installed by |
|----------|---------|-------------|
| `.agent/workflows/predefined/` | Generic workflows shipped with the engine (spec-write-and-implement, etc.) | `install.py` (automatic) |
| `.agent/workflows/` | Your project-specific workflows | Manual (copy from examples or create new) |
| `examples/` | Reference implementations for specific use cases | Manual copy |

## Creating Your Own Workflow

1. Run `/learn-workflows` in Cursor to learn the format
2. Create `.agent/workflows/<name>/workflow.yaml`
3. Create struct schemas in `.agent/workflows/<name>/structs/`
4. Run `/run-workflow <name>`

See `.agent/docs/` for the full format reference.
