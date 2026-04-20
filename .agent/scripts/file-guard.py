#!/usr/bin/env python3
"""
file-guard.py — PreToolUse hook for workflow-step agents.

Prevents step subagents from modifying engine infrastructure files.
Used as a hook in .claude/agents/workflow-step/AGENT.md.

Input:  JSON on stdin (Claude Code PreToolUse hook payload)
Output: Exit 0 = allow, Exit 2 = block (stderr = reason)

Protected paths (relative to project root):
  - .agent/scripts/       — engine scripts
  - .agent/docs/          — engine documentation
  - .agent/tools/         — browser tools
  - .agent/mcp/           — MCP server
  - .agent/workflows/templates/predefined/  — built-in workflows
  - .claude/              — Claude Code adapter
  - .cursor/              — Cursor adapter
"""

import sys
import json
import os

PROTECTED_PREFIXES = [
    ".agent/scripts/",
    ".agent/docs/",
    ".agent/tools/",
    ".agent/mcp/",
    ".agent/workflows/templates/predefined/",
    ".claude/",
    ".cursor/",
]


def normalize_path(path):
    """Normalize a file path for prefix matching."""
    # Convert backslashes, make relative
    path = path.replace("\\", "/")
    # Strip leading ./ if present
    if path.startswith("./"):
        path = path[2:]
    # If absolute, try to make relative to CWD
    cwd = os.getcwd().replace("\\", "/")
    if path.startswith(cwd):
        path = path[len(cwd):].lstrip("/")
    return path


def is_protected(file_path):
    """Check if a file path falls under a protected prefix."""
    normalized = normalize_path(file_path)
    return any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def main():
    try:
        raw = sys.stdin.buffer.read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        hook_input = json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Can't parse input — allow by default (fail-open)
        sys.exit(0)

    # Extract file path from tool input
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)  # No file path — not a file operation, allow

    if is_protected(file_path):
        msg = (
            f"BLOCKED: Cannot modify '{file_path}' — "
            f"engine infrastructure file. "
            f"Workflow steps must only write to their designated output paths."
        )
        sys.stderr.write(msg)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
