#!/usr/bin/env python3
"""
workflow-tools-loader.py — MCP server exposing script tools from workflow.yaml files.

At startup, scans .agent/workflows/templates/ recursively, parses every
workflow.yaml, and extracts tools of type: script. Each script tool becomes
a normal MCP tool with name "<workflow>__<tool_name>" (double underscore
separator within the loader namespace), description, and inputSchema from
workflow.yaml.

When a subagent calls one of these tools, the loader validates the args
against the schema (best-effort, with PyYAML/jsonschema if available),
then runs the underlying command via subprocess and returns stdout as
the MCP content.

Per-step subagent AGENT.md files reference these tools by their full
MCP-prefixed name: mcp__workflow_tools__<workflow>__<tool_name>.

Transport: stdio (JSON-RPC 2.0, newline-delimited).
Lifecycle: started by Claude Code at session start (registered in .mcp.json).
           Static — does NOT reload workflow.yaml files at runtime.
           User must restart CC after adding/editing workflows.

Naming:
    Tool name in MCP:    <workflow_name>__<tool_name>
    Full name in CC:     mcp__workflow_tools__<workflow_name>__<tool_name>
    Example:             mcp__workflow_tools__tools_demo__count_lines

Workflow names with hyphens are normalized to underscores in the tool
name (CC tool names cannot contain hyphens reliably).
"""

import glob as glob_module
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone


# ── Logging (stderr only — stdout reserved for JSON-RPC) ──

def _log(message):
    """Write debug message to stderr (visible in CC's MCP server logs)."""
    sys.stderr.write(f"[workflow-tools-loader] {message}\n")
    sys.stderr.flush()


# ── Constants ──

AGENT_DIR = os.path.abspath(".agent")
WORKFLOWS_DIR = os.path.join(AGENT_DIR, "workflows")
TEMPLATES_DIR = os.path.join(WORKFLOWS_DIR, "templates")


# ── YAML loading ──

_yaml_module = None


def _get_yaml():
    global _yaml_module
    if _yaml_module is None:
        try:
            import yaml
            _yaml_module = yaml
        except ImportError:
            _log("PyYAML not available — loader cannot read workflow.yaml")
            return None
    return _yaml_module


def _load_yaml_file(path):
    yaml = _get_yaml()
    if yaml is None:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        _log(f"Failed to load {path}: {e}")
        return None


# ── Tool name normalization ──

def _normalize_name(name):
    """Convert hyphens to underscores for MCP tool name compatibility."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _make_tool_name(workflow_name, tool_name):
    """Build the unprefixed MCP tool name: <workflow>__<tool>.

    CC will further prefix with mcp__workflow_tools__ when registering.
    """
    return f"{_normalize_name(workflow_name)}__{_normalize_name(tool_name)}"


# ── Workflow scanning ──

def _scan_workflows():
    """Find all workflow.yaml files under templates/."""
    pattern = os.path.join(TEMPLATES_DIR, "**", "workflow.yaml")
    return sorted(glob_module.glob(pattern, recursive=True))


def _build_tool_registry():
    """Scan workflows, return list of MCP tool dicts ready for tools/list response.

    Each entry also has hidden `_command` and `_workflow` fields used by tools/call.
    """
    tools = []
    paths = _scan_workflows()
    _log(f"Scanning {len(paths)} workflow.yaml files in {TEMPLATES_DIR}")

    for path in paths:
        wf = _load_yaml_file(path)
        if not isinstance(wf, dict):
            continue

        wf_name = wf.get("name")
        if not wf_name:
            _log(f"Skipping {path}: no name field")
            continue

        wf_tools = wf.get("tools", [])
        if not isinstance(wf_tools, list):
            continue

        for tool_def in wf_tools:
            if not isinstance(tool_def, dict):
                continue
            if tool_def.get("type") != "script":
                continue

            tool_name = tool_def.get("name")
            command = tool_def.get("command")
            if not tool_name or not command:
                _log(f"Skipping incomplete tool in {path}: {tool_def}")
                continue

            mcp_name = _make_tool_name(wf_name, tool_name)
            description = tool_def.get(
                "description",
                f"Script tool '{tool_name}' from workflow '{wf_name}'",
            )
            input_schema = tool_def.get("input_schema") or {
                "type": "object",
                "properties": {},
            }

            tools.append({
                "name": mcp_name,
                "description": description,
                "inputSchema": input_schema,
                "_command": command,
                "_workflow": wf_name,
                "_original_name": tool_name,
            })

    _log(f"Loaded {len(tools)} script tools from workflows")
    return tools


# ── Schema validation (best-effort) ──

_jsonschema_module = None


def _get_jsonschema():
    global _jsonschema_module
    if _jsonschema_module is None:
        try:
            import jsonschema
            _jsonschema_module = jsonschema
        except ImportError:
            _log("jsonschema not available — input validation disabled")
            _jsonschema_module = False
    return _jsonschema_module or None


def _validate_args(args, schema):
    """Validate args against JSON schema. Returns None on success or error string."""
    if not isinstance(schema, dict) or not schema:
        return None
    js = _get_jsonschema()
    if js is None:
        return None  # Skip validation if jsonschema not installed
    try:
        js.validate(args, schema)
        return None
    except js.ValidationError as e:
        return f"Input validation failed: {e.message} (path: {list(e.absolute_path)})"
    except Exception as e:
        return f"Schema validation error: {e}"


# ── Tool execution ──

def _execute_script_tool(tool, args):
    """Execute a script tool's command, passing args as `--key=value` CLI flags.

    Convention: workflow script tools expect arguments as `--<key>=<value>`
    flags appended to the command (matching the legacy proxy behavior).
    Values are stringified; complex types (dict/list) are JSON-encoded.

    The full args object is also exposed via the WORKFLOW_TOOL_ARGS environment
    variable as a JSON string, so newer scripts can read it directly if they
    prefer (no parsing of argv).

    Returns dict suitable for MCP content array.
    """
    command = tool["_command"]
    args_json = json.dumps(args, ensure_ascii=False)

    # Build --key=value suffix for legacy CLI scripts
    arg_parts = []
    for k, v in (args or {}).items():
        if isinstance(v, (dict, list)):
            v_str = json.dumps(v, ensure_ascii=False)
        else:
            v_str = str(v) if v is not None else ""
        arg_parts.append(f"--{k}={v_str}")
    full_command = command + (" " + " ".join(arg_parts) if arg_parts else "")

    env = os.environ.copy()
    env["WORKFLOW_TOOL_ARGS"] = args_json
    env["WORKFLOW_TOOL_NAME"] = tool["_original_name"]
    env["WORKFLOW_TOOL_WORKFLOW"] = tool["_workflow"]

    try:
        proc = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=os.getcwd(),
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {
            "isError": True,
            "content": [{
                "type": "text",
                "text": f"Tool '{tool['name']}' timed out after 300s",
            }],
        }
    except Exception as e:
        return {
            "isError": True,
            "content": [{
                "type": "text",
                "text": f"Tool '{tool['name']}' execution failed: {e}",
            }],
        }

    if proc.returncode != 0:
        err = proc.stderr or proc.stdout or "(no output)"
        return {
            "isError": True,
            "content": [{
                "type": "text",
                "text": (
                    f"Tool '{tool['name']}' exited with code {proc.returncode}\n"
                    f"stderr: {err.strip()}"
                ),
            }],
        }

    output = proc.stdout or ""
    return {
        "isError": False,
        "content": [{"type": "text", "text": output}],
    }


# ── JSON-RPC server loop ──

def _send(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    _log(f"Starting workflow-tools-loader (cwd={os.getcwd()})")

    tools_internal = _build_tool_registry()
    # Public form for tools/list (drop internal fields)
    tools_public = [
        {k: v for k, v in t.items() if not k.startswith("_")}
        for t in tools_internal
    ]
    tool_map = {t["name"]: t for t in tools_internal}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _log(f"Invalid JSON-RPC: {e}")
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "workflow_tools",
                        "version": "1.0.0",
                    },
                },
            })

        elif method == "notifications/initialized":
            pass  # No response for notifications

        elif method == "tools/list":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools_public},
            })

        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {}) or {}

            tool = tool_map.get(tool_name)
            if tool is None:
                _send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    },
                })
                continue

            # Validate args against schema (best effort)
            err = _validate_args(args, tool.get("inputSchema"))
            if err:
                _send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": err}],
                    },
                })
                continue

            # Execute the underlying command
            result = _execute_script_tool(tool, args)
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            })

        else:
            if req_id is not None:
                _send({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                })

    _log("workflow-tools-loader shutting down")


if __name__ == "__main__":
    main()
