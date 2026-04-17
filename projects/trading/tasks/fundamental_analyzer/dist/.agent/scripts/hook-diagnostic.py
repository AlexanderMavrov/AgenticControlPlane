#!/usr/bin/env python3
"""
hook-diagnostic.py — Diagnostic script for verifying Claude Code hook behavior.

Run as a SubagentStop hook to capture the exact payload format,
test exit code semantics, and verify matcher filtering.

Usage in .claude/settings.json:
{
  "hooks": {
    "SubagentStop": [{
      "matcher": "workflow-step",
      "hooks": [{ "type": "command", "command": "python .agent/scripts/hook-diagnostic.py" }]
    }]
  }
}

Logs everything to .agent/hook-diagnostic-capture.log.
Always exits 0 (does not interfere with normal operation).
Set HOOK_DIAG_EXIT=2 to test exit 2 behavior (subagent continuation).
"""

import sys
import os
import json
from datetime import datetime

AGENT_DIR = os.path.abspath(".agent")
LOG_PATH = os.path.join(AGENT_DIR, "hook-diagnostic-capture.log")


def main():
    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)

    # Read raw stdin
    try:
        raw_bytes = sys.stdin.buffer.read()
    except Exception as e:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n{datetime.now().isoformat()} | STDIN READ ERROR: {e}\n")
        sys.exit(0)

    # Log raw bytes info
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")
    if has_bom:
        raw_bytes = raw_bytes[3:]

    try:
        raw_text = raw_bytes.decode("utf-8")
        hook_input = json.loads(raw_text) if raw_text.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(
                f"\n{'='*60}\n{datetime.now().isoformat()} | PARSE ERROR\n"
                f"Error: {e}\n"
                f"Has BOM: {has_bom}\n"
                f"Raw length: {len(raw_bytes)}\n"
                f"Raw repr (first 500): {repr(raw_bytes[:500])}\n"
            )
        sys.exit(0)

    # Log full payload
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"{datetime.now().isoformat()} | HOOK INVOCATION\n")
        f.write(f"Has BOM: {has_bom}\n")
        f.write(f"Raw length: {len(raw_bytes)}\n")
        f.write(f"CWD: {os.getcwd()}\n")
        f.write(f"Keys: {sorted(hook_input.keys())}\n")
        f.write(f"\nFull payload:\n")
        f.write(json.dumps(hook_input, indent=2, ensure_ascii=False, default=str))
        f.write(f"\n\n--- Field analysis ---\n")

        # Analyze each field
        for key in sorted(hook_input.keys()):
            value = hook_input[key]
            value_type = type(value).__name__
            if isinstance(value, str) and len(value) > 200:
                display = repr(value[:200]) + "..."
            else:
                display = repr(value)
            f.write(f"  {key}: ({value_type}) {display}\n")

        # Compare with expected Claude Code fields
        expected = {
            "session_id", "transcript_path", "cwd", "permission_mode",
            "hook_event_name", "agent_id", "agent_type",
            "stop_hook_active", "agent_transcript_path", "last_assistant_message"
        }
        found = set(hook_input.keys())
        f.write(f"\n--- Expected vs Found ---\n")
        f.write(f"Expected (from docs): {sorted(expected)}\n")
        f.write(f"Found:                {sorted(found)}\n")
        f.write(f"Missing:              {sorted(expected - found)}\n")
        f.write(f"Extra (undocumented):  {sorted(found - expected)}\n")

    # Check if we should test exit 2
    exit_code = int(os.environ.get("HOOK_DIAG_EXIT", "0"))
    if exit_code == 2:
        sys.stderr.write(
            "DIAGNOSTIC: Testing exit 2 behavior. "
            "If you see this message, exit 2 on SubagentStop "
            "successfully prevents the subagent from stopping "
            "and feeds this stderr as feedback.\n"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
