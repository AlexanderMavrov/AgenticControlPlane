#!/usr/bin/env python3
"""
workflow-tool-validator.py — PreToolUse hook for script tool validation.

Reads a Claude Code PreToolUse hook payload from stdin, checks whether the
tool being called is a workflow script tool (`mcp__workflow_tools__<wf>__<tool>`),
and if so validates the arguments against the JSON schema declared in the
corresponding workflow.yaml.

Behavior:
- Tool not a workflow_tools call → exit 0 (no-op, allow)
- Schema not found / workflow.yaml malformed → exit 0 (graceful degradation,
  let the loader handle it server-side)
- Schema validation passes → exit 0 (allow)
- Schema validation fails → exit 2 + stderr message (CC blocks the tool call,
  shows the message to the LLM, which then has a chance to fix the input)

Why exit 2 specifically:
- exit 0 → allow
- exit 1 → permission denied (the LLM gets a permission error, less helpful)
- exit 2 → block + show stderr to LLM (recommended for validation feedback)

This hook is added to per-step subagent AGENT.md files automatically by
init-workflow.py with a matcher targeting `mcp__workflow_tools__.*` so
ONLY script tools go through this validation; built-in tools and other
MCP servers pass through untouched.

Server-side validation in workflow-tools-loader.py is the authoritative
guard. This hook is a defensive layer for faster, more obvious feedback
to the LLM (it sees the error before the call even reaches the loader).

Schema source: when a script tool is called, this hook resolves the
workflow.yaml that declared the tool by name (the loader's tool naming
convention is `<workflow>__<tool>`, so we know which workflow it came
from). It reads the workflow.yaml, finds the tool entry, and uses its
input_schema for validation.
"""

import glob as glob_module
import json
import os
import re
import sys


# ── Hook payload parsing ──

def _read_payload():
    """Read JSON payload from stdin (Claude Code hook contract)."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_tool_name(payload):
    """Extract the tool_name from a PreToolUse hook payload."""
    if not isinstance(payload, dict):
        return None
    return payload.get("tool_name") or payload.get("toolName") or ""


def _extract_tool_input(payload):
    """Extract the tool_input/arguments from a PreToolUse hook payload."""
    if not isinstance(payload, dict):
        return {}
    return (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("arguments")
        or {}
    )


# ── Workflow tool name parsing ──

WORKFLOW_TOOL_RE = re.compile(r"^mcp__workflow_tools__([a-zA-Z0-9_]+)__([a-zA-Z0-9_]+)$")


def _parse_workflow_tool(tool_name):
    """Return (workflow_normalized, tool_normalized) or None."""
    m = WORKFLOW_TOOL_RE.match(tool_name or "")
    if not m:
        return None
    return m.group(1), m.group(2)


# ── Workflow.yaml resolution ──

def _normalize(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", s or "")


def _find_workflow_with_tool(workflow_norm, tool_norm):
    """Scan workflow.yaml files and return (workflow_dict, tool_dict) or None.

    Both workflow_norm and tool_norm are the underscored MCP forms; we match
    against normalized workflow.name and tool.name fields.
    """
    try:
        import yaml
    except ImportError:
        return None  # No PyYAML — graceful degradation

    pattern = os.path.join(
        ".agent", "workflows", "templates", "**", "workflow.yaml"
    )
    for path in glob_module.glob(pattern, recursive=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                wf = yaml.safe_load(f)
        except Exception:
            continue
        if not isinstance(wf, dict):
            continue
        wf_name = wf.get("name", "")
        if _normalize(wf_name) != workflow_norm:
            continue
        for t in wf.get("tools", []) or []:
            if not isinstance(t, dict):
                continue
            if t.get("type") != "script":
                continue
            if _normalize(t.get("name", "")) == tool_norm:
                return wf, t
    return None


# ── Validation ──

def _validate_with_jsonschema(data, schema):
    """Use jsonschema if available; return None on success or error message."""
    try:
        import jsonschema
    except ImportError:
        return None  # Best effort — no validation if dependency missing
    try:
        jsonschema.validate(data, schema)
        return None
    except jsonschema.ValidationError as e:
        path = ".".join(str(p) for p in e.absolute_path) or "(root)"
        return f"Schema validation failed at '{path}': {e.message}"
    except Exception as e:
        return f"Schema validator error: {e}"


# ── Main ──

def main():
    payload = _read_payload()
    if payload is None:
        # Cannot parse payload — be permissive (don't block legitimate work)
        sys.exit(0)

    tool_name = _extract_tool_name(payload)
    parsed = _parse_workflow_tool(tool_name)
    if parsed is None:
        # Not a workflow tool — no-op
        sys.exit(0)

    workflow_norm, tool_norm = parsed

    found = _find_workflow_with_tool(workflow_norm, tool_norm)
    if found is None:
        # Workflow.yaml not found or no schema — let server handle it
        sys.exit(0)

    workflow, tool_def = found
    schema = tool_def.get("input_schema") or {}
    if not schema:
        sys.exit(0)

    args = _extract_tool_input(payload)
    if not isinstance(args, dict):
        sys.exit(0)

    error = _validate_with_jsonschema(args, schema)
    if error is None:
        sys.exit(0)

    # Block with explanatory message — CC will surface this to the LLM
    sys.stderr.write(
        f"workflow-tool-validator: {tool_name} input rejected.\n"
        f"{error}\n"
        f"Expected schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Received args: {json.dumps(args, ensure_ascii=False)}\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
