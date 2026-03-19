# Struct Schemas — Format Reference

Struct schemas define the expected format of workflow inputs and outputs. They live in `.agent/workflows/<name>/structs/` as `.schema.yaml` files.

The same struct can validate both inputs (before a step) and outputs (after a step, as part of the gate).

## Schema Formats

Two schema styles are supported. Both can be mixed with `file_checks`.

### Standard JSON Schema style (recommended for new schemas)

Uses familiar JSON Schema conventions (`type`, `required`, `properties`). The validator auto-detects this style when `type: object` is present at the top level.

```yaml
name: string                  # Required. Referenced by workflow.yaml outputs[].struct
description: string           # Required. Human-readable purpose.
version: number               # Optional. Schema version.
type: object                  # Triggers standard JSON Schema validation.

required:                     # List of required field names.
  - field_a
  - field_b

properties:                   # Field definitions with type, enum, pattern.
  field_a:
    type: "string" | "integer" | "number" | "boolean" | "array" | "object"
    description: string       # Optional. Human-readable purpose.
    enum: [values]            # Optional. Allowed values.
    pattern: string           # Optional. Regex for strings.
    min_items: number         # Optional. For arrays.
    items:                    # Optional. Schema for array items.
      type: object
      required: [...]
      properties: { ... }
  field_b:
    type: object              # Nested objects are validated recursively.
    required: [...]
    properties: { ... }

file_checks:                  # Optional (see below).
```

**Note:** `format` is not needed — the validator infers JSON from `type: object`.

### Custom format style (legacy, still fully supported)

Uses explicit `format` key and format-specific schema blocks.

```yaml
name: string                  # Required. Referenced by workflow.yaml outputs[].struct
description: string           # Required. Human-readable purpose.
format: "json" | "yaml" | "markdown" | "text"
                              # Required for this style.

# For format: json
json_schema:                  # Optional. JSON structure validation.
  required_fields:
    - field: string           # Dot-notation path (e.g., "metadata.version")
      type: "string" | "integer" | "number" | "boolean" | "array" | "object"
      pattern: string         # Optional. Regex pattern for string fields.
      enum: [values]          # Optional. Allowed values.
      min_items: number       # Optional. For array fields.

# For format: yaml (same structure as json_schema)
yaml_schema:
  required_fields:
    - field: string
      type: string
      pattern: string
      enum: [values]

# For format: markdown
frontmatter:                  # Optional. YAML frontmatter validation.
  required:
    - field: string           # Field name in frontmatter.
      type: "string" | "number" | "enum" | "list" | "boolean"
      pattern: string         # Optional. Regex for string fields.
      values: [values]        # Required for type: enum.

required_sections:            # Optional. Required Markdown ## headings.
  - "Section Name"
  - "Another Section"

file_checks:                  # Optional (see below).
```

### file_checks (universal)

```yaml
file_checks:                  # Optional. File-level validation.
  exists: boolean             # File must exist (default: true).
  min_size: number            # Minimum file size in bytes.
  max_size: number            # Maximum file size in bytes.
  name_pattern: string        # Regex for filename validation.
```

## Validation Layers

Struct schemas are checked by the **structural gate** (Python script). The script performs deterministic checks only:

| Check | What it validates |
|-------|-------------------|
| File existence | Does the output file exist? |
| File size | Within min/max bounds? |
| Format parsing | Valid JSON/YAML/Markdown? |
| Required fields | All required fields present with correct types? |
| Pattern matching | String fields match regex patterns? |
| Enum validation | Values in allowed set? |
| Frontmatter | YAML frontmatter has required fields? |
| Required sections | Markdown has required ## headings? |

**Semantic validation** (completeness, correctness, coherence) is done by the LLM in the semantic gate layer — not by struct schemas.

## Examples

### Standard style — simple diagnostic output

```yaml
name: diagnostic-output
version: 1
description: Minimal diagnostic output for hook testing.
type: object
required:
  - status
  - timestamp
properties:
  status:
    type: string
    description: "Must be 'ok'"
  timestamp:
    type: string
    description: ISO 8601 timestamp
  message:
    type: string
    description: Optional echo of the message param
```

### Standard style — with nested objects and arrays

```yaml
name: scan-result
version: 1
description: Per-domain compliance scan results.
type: object
required:
  - domain
  - specs_checked
  - results
properties:
  domain:
    type: string
  specs_checked:
    type: integer
  results:
    type: array
    min_items: 1
    items:
      type: object
      required: [spec_id, status]
      properties:
        spec_id:
          type: string
        status:
          type: string
          enum: [compliant, violation, partial]
```

### Custom style — extraction manifest

```yaml
name: extraction-manifest
description: Plan output — domains, sections, estimated counts
format: json

json_schema:
  required_fields:
    - field: workflow
      type: string
    - field: source_document
      type: string
    - field: tasks
      type: array
      min_items: 1
    - field: tasks[].domain
      type: string
    - field: tasks[].status
      type: string
      enum: [pending, in_progress, completed, failed]
    - field: tasks[].source_sections
      type: array
    - field: tasks[].estimated_specs
      type: number
```

### Custom style — Markdown spec file

```yaml
name: spec
description: Validation spec — YAML frontmatter + Markdown body
format: markdown

frontmatter:
  required:
    - field: spec_id
      type: string
      pattern: "^[A-Z]+-\\d{3}$"
    - field: severity
      type: enum
      values: [MUST, SHOULD, MAY]
    - field: domain
      type: string
    - field: source_sections
      type: list

required_sections:
  - "Rule Statement"
  - "Rationale"
  - "Valid Examples"
  - "Invalid Examples"
  - "Validation Criteria"
  - "Source Reference"

file_checks:
  exists: true
  min_size: 200
```

### Custom style — validation report

```yaml
name: validation-report
description: Validation results per spec
format: json

json_schema:
  required_fields:
    - field: workflow
      type: string
    - field: total_specs
      type: number
    - field: passed
      type: number
    - field: failed
      type: number
    - field: results
      type: array
    - field: results[].spec_id
      type: string
    - field: results[].status
      type: string
      enum: [passed, failed]
    - field: results[].issues
      type: array
```

## Tips for Writing Structs

1. **Start simple.** Begin with `file_checks` and a few `required_fields`. Add detail as you iterate.
2. **Use patterns for IDs.** Regex patterns catch format errors the LLM might make (e.g., `spec_id` must be `DOMAIN-NNN`).
3. **Match your workflow.** If a step's output is the next step's input, use the same struct for both — the gate validates the output, and the next step's input validation confirms it's still valid.
4. **Frontmatter is powerful.** For Markdown outputs, frontmatter validation catches missing metadata without parsing the full document.
5. **Prefer standard style for JSON.** It's cleaner and supports nested validation. Use custom style only for Markdown/YAML formats or when you need dot-notation array checks like `tasks[].domain`.
