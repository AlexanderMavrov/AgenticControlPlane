#!/usr/bin/env python3
"""
schema-validate.py — Validate files against workflow struct schemas.

Usage:
    python schema-validate.py <file-path> <schema-path>
    python schema-validate.py <glob-pattern> <schema-path>

Output: JSON to stdout
    { "passed": true/false, "checks": N, "failures": N, "details": [...] }

Exit codes:
    0 = validation ran (check "passed" field for result)
    1 = script error (bad args, missing schema, etc.)
"""

import sys
import os
import re
import json
import glob as glob_module

try:
    import yaml
except ImportError:
    # Fallback: try to parse YAML manually for simple cases
    yaml = None


def load_yaml(path):
    """Load a YAML file. Requires PyYAML; raises RuntimeError if not installed."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if yaml:
        return yaml.safe_load(content)
    # No fallback — PyYAML is required; raise immediately
    raise RuntimeError(
        f"PyYAML not installed. Install with: pip install pyyaml"
    )


def load_json(path):
    """Load a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_markdown_frontmatter(path):
    """Extract YAML frontmatter from a Markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return None, content

    end = content.find("---", 3)
    if end == -1:
        return None, content

    frontmatter_str = content[3:end].strip()
    body = content[end + 3 :].strip()

    if yaml:
        frontmatter = yaml.safe_load(frontmatter_str)
    else:
        raise RuntimeError("PyYAML required for frontmatter parsing")

    return frontmatter, body


def parse_markdown_sections(body):
    """Extract ## section headings from Markdown body."""
    sections = []
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            sections.append(line[3:].strip())
    return sections


def extract_section_content(body, section_name):
    """Extract the text content under a ## section heading.

    Returns the body text between the named heading and the next ## heading
    (or end of document). Returns None if the section is not found.
    """
    pattern = re.compile(r"^## " + re.escape(section_name) + r"\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return None
    start = match.end()
    next_section = re.search(r"^## ", body[start:], re.MULTILINE)
    if next_section:
        return body[start : start + next_section.start()]
    return body[start:]


def get_nested_field(obj, dotpath):
    """Get a nested field using dot notation. Returns (value, found)."""
    parts = dotpath.split(".")
    current = obj
    for part in parts:
        # Handle array notation like "tasks[]"
        if part.endswith("[]"):
            key = part[:-2]
            if isinstance(current, dict) and key in current:
                current = current[key]
                if not isinstance(current, list):
                    return None, False
                continue
            return None, False
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True


def check_type(value, expected_type):
    """Check if value matches expected type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "list": list,
    }
    expected = type_map.get(expected_type)
    if expected is None:
        if expected_type == "enum":
            return True  # Enum check is separate
        return True  # Unknown type — pass
    return isinstance(value, expected)


def detect_format(schema):
    """Detect the schema format.

    Two schema styles are supported:
    1. Custom format: explicit ``format: json`` with ``json_schema.required_fields``
    2. Standard JSON Schema style: ``type: object`` with ``required`` list and
       ``properties`` dict (no ``format`` key needed).

    Returns the effective format string ("json", "markdown", "yaml", or "text").
    """
    fmt = schema.get("format")
    if fmt:
        return fmt
    # Auto-detect: top-level type: object + required/properties → JSON
    if schema.get("type") == "object" and (
        "required" in schema or "properties" in schema
    ):
        return "json"
    return "text"


def validate_standard_json_schema(data, schema, filename):
    """Validate *data* against a standard JSON Schema-style struct.

    Supports: ``required``, ``properties`` (with ``type`` and ``enum``),
    and nested ``properties`` of ``type: object`` / ``type: array`` with
    ``items.properties``.

    Returns (checks, failures, details).
    """
    checks = 0
    failures = 0
    details = []

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # 1. Check required fields exist
    for field_name in required:
        checks += 1
        if not isinstance(data, dict) or field_name not in data:
            failures += 1
            details.append(f"{filename}: missing required field '{field_name}'")

    # 2. Check property types and constraints for fields that exist
    if isinstance(data, dict):
        for field_name, field_schema in properties.items():
            if field_name not in data:
                continue  # Only required check enforces presence

            value = data[field_name]
            expected_type = field_schema.get("type")

            if expected_type:
                checks += 1
                if not check_type(value, expected_type):
                    failures += 1
                    details.append(
                        f"{filename}: '{field_name}' type mismatch "
                        f"(expected {expected_type}, got {type(value).__name__})"
                    )

            if "enum" in field_schema:
                checks += 1
                if value not in field_schema["enum"]:
                    failures += 1
                    details.append(
                        f"{filename}: '{field_name}' value '{value}' "
                        f"not in {field_schema['enum']}"
                    )

            if "pattern" in field_schema and isinstance(value, str):
                checks += 1
                if not re.match(field_schema["pattern"], value):
                    failures += 1
                    details.append(
                        f"{filename}: '{field_name}' doesn't match "
                        f"pattern '{field_schema['pattern']}'"
                    )

            if "min_items" in field_schema and isinstance(value, list):
                checks += 1
                if len(value) < field_schema["min_items"]:
                    failures += 1
                    details.append(
                        f"{filename}: '{field_name}' has {len(value)} items, "
                        f"min is {field_schema['min_items']}"
                    )

            # Recurse into nested objects
            if expected_type == "object" and isinstance(value, dict):
                if "required" in field_schema or "properties" in field_schema:
                    nc, nf, nd = validate_standard_json_schema(
                        value, field_schema, f"{filename}.{field_name}"
                    )
                    checks += nc
                    failures += nf
                    details.extend(nd)

            # Validate array items
            if expected_type == "array" and isinstance(value, list):
                items_schema = field_schema.get("items", {})
                if items_schema.get("type") == "object" and (
                    "required" in items_schema or "properties" in items_schema
                ):
                    for i, item in enumerate(value):
                        nc, nf, nd = validate_standard_json_schema(
                            item,
                            items_schema,
                            f"{filename}.{field_name}[{i}]",
                        )
                        checks += nc
                        failures += nf
                        details.extend(nd)

    return checks, failures, details


def validate_file(file_path, schema):
    """Validate a single file against a schema. Returns (checks, failures, details)."""
    checks = 0
    failures = 0
    details = []

    filename = os.path.basename(file_path)

    # --- File checks ---
    file_checks = schema.get("file_checks", {})

    if file_checks.get("exists", True):
        checks += 1
        if not os.path.isfile(file_path):
            failures += 1
            details.append(f"File not found: {file_path}")
            return checks, failures, details  # Can't check further

    if "min_size" in file_checks:
        checks += 1
        size = os.path.getsize(file_path)
        if size < file_checks["min_size"]:
            failures += 1
            details.append(
                f"{filename}: file is too small ({size} bytes, minimum {file_checks['min_size']}). "
                f"Likely cause: required content is missing or sections are empty. "
                f"Fix: ensure all required sections have substantive content."
            )

    if "max_size" in file_checks:
        checks += 1
        size = os.path.getsize(file_path)
        if size > file_checks["max_size"]:
            failures += 1
            details.append(
                f"{filename}: file is too large ({size} bytes, maximum {file_checks['max_size']}). "
                f"Fix: split the content into multiple files or remove redundant sections."
            )

    if "name_pattern" in file_checks:
        checks += 1
        if not re.match(file_checks["name_pattern"], filename):
            failures += 1
            details.append(
                f"{filename}: filename does not match required pattern '{file_checks['name_pattern']}'. "
                f"Fix: rename the file so its basename matches this regex."
            )

    # --- Format-specific checks ---
    fmt = detect_format(schema)

    if fmt == "json":
        checks += 1
        try:
            data = load_json(file_path)
        except (json.JSONDecodeError, Exception) as e:
            failures += 1
            details.append(
                f"{filename}: invalid JSON — {e}. "
                f"Fix: check the file for JSON syntax errors (missing commas, "
                f"unmatched braces/brackets, trailing commas, unquoted keys)."
            )
            return checks, failures, details

        # Standard JSON Schema style (type: object + required + properties)
        if "required" in schema or "properties" in schema:
            nc, nf, nd = validate_standard_json_schema(data, schema, filename)
            checks += nc
            failures += nf
            details.extend(nd)

        # Custom format (json_schema.required_fields)
        json_schema = schema.get("json_schema", {})
        for field_def in json_schema.get("required_fields", []):
            field_name = field_def["field"]

            # Handle array item notation like "tasks[].domain"
            # Supports nested arrays: "domains[].requirements[].title"
            if "[]." in field_name:
                def _validate_array_field(parent_data, full_path, field_def,
                                          _checks, _failures, _details):
                    """Recursively validate fields in nested arrays."""
                    arr_path, item_field = full_path.split("[].", 1)
                    arr_value, arr_found = get_nested_field(parent_data, arr_path)
                    _checks += 1
                    if not arr_found or not isinstance(arr_value, list):
                        _failures += 1
                        _details.append(
                            f"{filename}: required array '{arr_path}' not found "
                            f"(or value is not an array). "
                            f"Fix: add '{arr_path}' as an array at the "
                            f"appropriate path."
                        )
                        return _checks, _failures
                    # Check min_items constraint on the array itself
                    min_items = field_def.get("min_items")
                    if min_items is not None and len(arr_value) < min_items:
                        _checks += 1
                        _failures += 1
                        _details.append(
                            f"{filename}: array '{arr_path}' has "
                            f"{len(arr_value)} items "
                            f"(minimum required: {min_items}). "
                            f"Fix: add more items until the array has at least "
                            f"{min_items} entries."
                        )
                    for i, item in enumerate(arr_value):
                        # Nested array — recurse
                        if "[]." in item_field:
                            _checks, _failures = _validate_array_field(
                                item, item_field, field_def,
                                _checks, _failures, _details
                            )
                            continue
                        item_val, item_found = get_nested_field(item, item_field)
                        if not item_found:
                            _checks += 1
                            _failures += 1
                            _details.append(
                                f"{filename}: array item "
                                f"'{arr_path}[{i}]' is missing "
                                f"required field '{item_field}'. "
                                f"Fix: add '{item_field}: <value>' to "
                                f"item at index {i}."
                            )
                        elif "type" in field_def and not check_type(
                            item_val, field_def["type"]
                        ):
                            _checks += 1
                            _failures += 1
                            _details.append(
                                f"{filename}: array item "
                                f"'{arr_path}[{i}].{item_field}' "
                                f"has wrong type "
                                f"(expected '{field_def['type']}', "
                                f"got '{type(item_val).__name__}'). "
                                f"Fix: change the value to match the "
                                f"expected type."
                            )
                        elif "enum" in field_def and \
                                item_val not in field_def["enum"]:
                            _checks += 1
                            _failures += 1
                            _details.append(
                                f"{filename}: array item "
                                f"'{arr_path}[{i}].{item_field}' "
                                f"= '{item_val}' is not allowed. "
                                f"Fix: choose one of {field_def['enum']}."
                        )
                    return _checks, _failures

                checks, failures = _validate_array_field(
                    data, field_name, field_def, checks, failures, details
                )
            else:
                checks += 1
                value, found = get_nested_field(data, field_name)
                if not found:
                    failures += 1
                    details.append(
                        f"{filename}: required field '{field_name}' is missing. "
                        f"Fix: add '{field_name}' to the JSON object at the appropriate path."
                    )
                    continue

                if "type" in field_def and not check_type(value, field_def["type"]):
                    checks += 1
                    failures += 1
                    details.append(
                        f"{filename}: field '{field_name}' has wrong type "
                        f"(expected '{field_def['type']}', got '{type(value).__name__}'). "
                        f"Fix: change the value to match the expected type."
                    )

                if "pattern" in field_def and isinstance(value, str):
                    checks += 1
                    if not re.match(field_def["pattern"], value):
                        failures += 1
                        details.append(
                            f"{filename}: field '{field_name}' = '{value}' does not match "
                            f"required pattern '{field_def['pattern']}'. "
                            f"Fix: change '{field_name}' to match this regex."
                        )

                if "enum" in field_def and value not in field_def["enum"]:
                    checks += 1
                    failures += 1
                    details.append(
                        f"{filename}: field '{field_name}' = '{value}' is not allowed. "
                        f"Fix: choose one of {field_def['enum']}."
                    )

                if "min_items" in field_def and isinstance(value, list):
                    checks += 1
                    if len(value) < field_def["min_items"]:
                        failures += 1
                        details.append(
                            f"{filename}: array '{field_name}' has {len(value)} items "
                            f"(minimum required: {field_def['min_items']}). "
                            f"Fix: add more items until the array has at least "
                            f"{field_def['min_items']} entries."
                        )

    elif fmt == "markdown":
        frontmatter_schema = schema.get("frontmatter", {})
        required_sections = schema.get("required_sections", [])

        checks += 1
        try:
            frontmatter, body = parse_markdown_frontmatter(file_path)
        except Exception as e:
            failures += 1
            details.append(
                f"{filename}: failed to parse markdown file — {e}. "
                f"Fix: ensure the file has valid YAML frontmatter between '---' "
                f"markers at the top, followed by markdown body content."
            )
            return checks, failures, details

        # Frontmatter validation
        if frontmatter_schema.get("required"):
            if frontmatter is None:
                checks += 1
                failures += 1
                details.append(
                    f"{filename}: YAML frontmatter block is missing. "
                    f"Fix: add a frontmatter block at the very top of the file, "
                    f"delimited by '---' on its own line before and after the YAML."
                )
            else:
                for field_def in frontmatter_schema["required"]:
                    field_name = field_def["field"]
                    checks += 1
                    if field_name not in frontmatter:
                        allowed = field_def.get("values")
                        hint = f" Allowed values: {allowed}." if allowed else ""
                        failures += 1
                        details.append(
                            f"{filename}: required frontmatter field '{field_name}' is missing. "
                            f"Fix: add '{field_name}: <value>' to the YAML frontmatter.{hint}"
                        )
                        continue

                    value = frontmatter[field_name]

                    if "type" in field_def and not check_type(
                        value, field_def["type"]
                    ):
                        checks += 1
                        failures += 1
                        details.append(
                            f"{filename}: frontmatter '{field_name}' has wrong type "
                            f"(expected '{field_def['type']}', got '{type(value).__name__}'). "
                            f"Fix: change the value format to match the expected type."
                        )

                    if "pattern" in field_def and isinstance(value, str):
                        checks += 1
                        if not re.match(field_def["pattern"], value):
                            failures += 1
                            details.append(
                                f"{filename}: frontmatter '{field_name}' = '{value}' does not "
                                f"match required pattern '{field_def['pattern']}'. "
                                f"Fix: change '{field_name}' to match this regex."
                            )

                    if "values" in field_def and value not in field_def["values"]:
                        checks += 1
                        failures += 1
                        details.append(
                            f"{filename}: frontmatter '{field_name}' = '{value}' is not allowed. "
                            f"Fix: choose one of {field_def['values']}."
                        )

                    # Cross-field check: frontmatter value must appear in a body section
                    if "body_match_section" in field_def and isinstance(value, str):
                        target_section = field_def["body_match_section"]
                        section_text = extract_section_content(body, target_section)
                        checks += 1
                        if section_text is not None and \
                                value.lower() not in section_text.lower():
                            failures += 1
                            details.append(
                                f"{filename}: frontmatter declares "
                                f"'{field_name}: {value}' but the word '{value}' does not "
                                f"appear literally in the body of '## {target_section}'. "
                                f"This is a cross-field consistency check (RFC 2119 style): "
                                f"the modal verb/value declared in frontmatter must appear in "
                                f"the section prose. "
                                f"Fix: rewrite '## {target_section}' body to use '{value}' "
                                f"directly (e.g., 'The system {value} do X' instead of "
                                f"'The system shall do X')."
                            )

        # Required sections
        if required_sections:
            sections = parse_markdown_sections(body)
            for section in required_sections:
                checks += 1
                if section not in sections:
                    failures += 1
                    details.append(
                        f"{filename}: required markdown section '## {section}' is missing. "
                        f"Fix: add '## {section}' as a heading at the top level (##, not ### "
                        f"or deeper), followed by body content for that section."
                    )

    elif fmt == "yaml":
        checks += 1
        try:
            data = load_yaml(file_path)
        except Exception as e:
            failures += 1
            details.append(
                f"{filename}: invalid YAML — {e}. "
                f"Fix: check the file for YAML syntax errors (indentation, "
                f"unmatched quotes, tabs mixed with spaces)."
            )
            return checks, failures, details

        yaml_schema = schema.get("yaml_schema", {})
        for field_def in yaml_schema.get("required_fields", []):
            field_name = field_def["field"]
            checks += 1
            value, found = get_nested_field(data, field_name)
            if not found:
                failures += 1
                details.append(
                    f"{filename}: required YAML field '{field_name}' is missing. "
                    f"Fix: add '{field_name}: <value>' at the appropriate path."
                )

    return checks, failures, details


def resolve_files(pattern):
    """Resolve a file path or glob pattern to a list of files."""
    if os.path.isfile(pattern):
        return [pattern]
    files = glob_module.glob(pattern, recursive=True)
    return [f for f in files if os.path.isfile(f)]


def main():
    if len(sys.argv) < 3:
        print("Usage: schema-validate.py <file-or-glob> <schema-path>", file=sys.stderr)
        sys.exit(1)

    file_pattern = sys.argv[1]
    schema_path = sys.argv[2]

    # Load schema
    try:
        schema = load_yaml(schema_path)
    except Exception as e:
        print(f"Error loading schema: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve files
    files = resolve_files(file_pattern)
    if not files:
        result = {
            "passed": False,
            "checks": 1,
            "failures": 1,
            "details": [f"No files matching '{file_pattern}'"],
        }
        print(json.dumps(result))
        sys.exit(0)

    # Validate each file
    total_checks = 0
    total_failures = 0
    all_details = []

    for file_path in files:
        checks, failures, details = validate_file(file_path, schema)
        total_checks += checks
        total_failures += failures
        all_details.extend(details)

    result = {
        "passed": total_failures == 0,
        "checks": total_checks,
        "failures": total_failures,
        "details": all_details,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
