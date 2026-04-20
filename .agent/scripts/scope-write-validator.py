#!/usr/bin/env python3
"""
scope-write-validator.py — PreToolUse hook for scope write protection.

Reads a PreToolUse hook payload from stdin and blocks writes to a spec
scope directory that does not match the user's active scope.

The single policy: if a file-mutating tool targets a path under
.agent/specs/<scope_X>/ and the active scope resolved from
.agent/local/active-scope (or project default, or fallback) is <scope_Y>
with X != Y — block. Writes to .agent/specs/ roots (management files like
_scope-config.json or _index.json under a scope) are allowed.

Exit codes:
- 0 : allow (no-op or matching scope)
- 2 : block + surface stderr message to the LLM (CC convention)

Graceful degradation: any I/O error, missing config, or unexpected payload
shape → exit 0. The hook never blocks on its own malfunction; it only
blocks on an identified scope mismatch.

Shared logic lives in scope_context.py. This hook is the CC adapter; the
Cursor adapter integrates the same policy via gate-check.py.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure scope_context is importable when invoked via hook runner
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    import scope_context as sc  # noqa: E402
except ImportError:
    # Hook runs without scope_context available — don't block legitimate work
    sys.exit(0)


# Tools that perform file writes we care about. MCP tools named with a
# path-like argument (e.g. mcp__workflow_tools__*__commit) are covered by
# inspecting tool_input["path"] / ["file_path"].
_WRITING_TOOLS_PREFIX = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def _read_payload() -> dict | None:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_tool_name(payload: dict) -> str:
    return (
        payload.get("tool_name")
        or payload.get("toolName")
        or ""
    )


def _extract_target_path(payload: dict) -> str | None:
    """Pull a file path out of common tool_input shapes."""
    inp = (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("arguments")
        or {}
    )
    if not isinstance(inp, dict):
        return None
    for key in ("file_path", "path", "filePath", "target", "output_path"):
        val = inp.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _is_writing_tool(tool_name: str) -> bool:
    """Return True for tools that mutate the filesystem."""
    if any(tool_name == t or tool_name.endswith("__" + t) for t in _WRITING_TOOLS_PREFIX):
        return True
    # Bash tools that might use redirect/cp/mv are not gated — too noisy and
    # path isn't reliably in tool_input. The hook is a defensive layer, not
    # a replacement for spec writer logic.
    return False


def main() -> None:
    payload = _read_payload()
    if not isinstance(payload, dict):
        sys.exit(0)

    tool_name = _extract_tool_name(payload)
    if not _is_writing_tool(tool_name):
        sys.exit(0)

    target = _extract_target_path(payload)
    if not target:
        sys.exit(0)

    # Ignore if target is not under .agent/specs/ at all.
    target_scope = sc.scope_from_path(target)
    if target_scope is None:
        sys.exit(0)

    try:
        active_scope, source = sc.resolve_active_scope()
    except Exception:
        sys.exit(0)

    # Generic is always writable — universal rules apply across all contexts.
    if target_scope == sc.GENERIC_SCOPE:
        sys.exit(0)

    # Active scope matches target scope — allowed.
    if active_scope == target_scope:
        sys.exit(0)

    # Mismatch — surface a clear, actionable message and block.
    sys.stderr.write(
        f"scope-write-validator: BLOCKED write to .agent/specs/{target_scope}/\n"
        f"  Active scope is '{active_scope}' (source: {source}).\n"
        f"  Target path belongs to scope '{target_scope}'.\n"
        f"  This is almost certainly unintended — cross-scope writes are\n"
        f"  a common bug when workflows forget to pass --scope explicitly.\n"
        f"\n"
        f"  To proceed intentionally, do ONE of:\n"
        f"    1. /scope-set {target_scope}  (if you want to switch)\n"
        f"    2. Re-run the workflow with --scope {target_scope}\n"
        f"\n"
        f"  Target: {target}\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
