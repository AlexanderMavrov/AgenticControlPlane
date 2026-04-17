#!/usr/bin/env python3
"""
gate-check.py — Structural gate handler for the Workflow Engine.

Called by Cursor's subagentStop hook. Reads hook input from stdin,
determines which workflow step completed, validates outputs against
struct schemas, and returns a followup_message for the orchestrator.

Input:  JSON on stdin (Cursor subagentStop hook payload)
Output: JSON on stdout with "followup_message" field

Exit codes:
    0 = processed successfully (check followup_message for result)
    2 = block the action
    other = error (action proceeds anyway — fail-open)
"""

import sys
import os
import re
import json
import subprocess
import glob as glob_module
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Cross-platform file locking (prevents race conditions in parallel steps)
# ---------------------------------------------------------------------------
try:
    import msvcrt  # Windows

    def _lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(f):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

except ImportError:
    try:
        import fcntl  # Unix/macOS

        def _lock_file(f):
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        def _unlock_file(f):
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except ImportError:
        def _lock_file(f):
            pass

        def _unlock_file(f):
            pass


def locked_json_read_modify_write(path, modifier_fn, default=None):
    """Atomically read-modify-write a JSON file with file locking.

    Uses a separate .lock file for mutual exclusion. This prevents race
    conditions when multiple parallel subagents complete simultaneously
    and gate-check.py runs concurrently for each one.

    Args:
        path: Path to the JSON file.
        modifier_fn: Function(data) -> modified_data.
        default: Default value if file doesn't exist.

    Returns:
        The modified data, or None on error.
    """
    lock_path = path + ".lock"
    try:
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        with open(lock_path, "a") as lock_f:
            _lock_file(lock_f)
            try:
                if os.path.isfile(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        _log_error(f"Corrupt JSON in {path}, resetting to default")
                        try:
                            backup = path + ".corrupt"
                            with open(path, "rb") as src, open(backup, "wb") as dst:
                                dst.write(src.read())
                            _log_error(f"Corrupt file backed up to {backup}")
                        except Exception:
                            pass
                        data = default if default is not None else {}
                else:
                    data = default if default is not None else {}

                data = modifier_fn(data)

                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                return data
            finally:
                _unlock_file(lock_f)
    except Exception as e:
        _log_error(f"locked_json_read_modify_write failed for {path}: {type(e).__name__}: {e}")
        return None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_DIR = os.path.abspath(".agent")
WORKFLOWS_DIR = os.path.join(AGENT_DIR, "workflows")
TEMPLATES_DIR = os.path.join(WORKFLOWS_DIR, "templates")
PREDEFINED_DIR = os.path.join(TEMPLATES_DIR, "predefined")
MY_WORKFLOWS_DIR = os.path.join(TEMPLATES_DIR, "my_workflows")
EXAMPLES_DIR = os.path.join(TEMPLATES_DIR, "examples")
SCRIPTS_DIR = os.path.join(AGENT_DIR, "scripts")
SCHEMA_VALIDATE = os.path.join(SCRIPTS_DIR, "schema-validate.py")


def find_workflow_dir():
    """Find the active workflow's runtime directory by looking for manifest.json.

    Returns the runtime dir (e.g., .agent/workflows/<name>/) which contains
    manifest.json. Workflow definitions (workflow.yaml, structs/) live in
    .agent/workflows/templates/ — use find_definition_dir() to locate them.

    When multiple active manifests exist (e.g., parent + delegated workflow),
    picks the most recently updated one — the delegated workflow is the one
    whose subagent just completed.
    """
    if not os.path.isdir(WORKFLOWS_DIR):
        return None
    best_dir = None
    best_time = ""
    for name in os.listdir(WORKFLOWS_DIR):
        manifest = os.path.join(WORKFLOWS_DIR, name, "manifest.json")
        if os.path.isfile(manifest):
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("status") in ("in_progress", "paused"):
                    updated = data.get("updated_at", "")
                    if updated > best_time:
                        best_time = updated
                        best_dir = os.path.join(WORKFLOWS_DIR, name)
            except (json.JSONDecodeError, OSError):
                continue
    return best_dir


def find_definition_dir(workflow_dir):
    """Find the directory containing workflow.yaml and structs/ for a workflow.

    Search order matches workflow-engine.py's resolve_workflow():
      1. .agent/workflows/templates/my_workflows/<name>/  (user-created templates)
      2. .agent/workflows/templates/predefined/<name>/    (built-in templates)
      3. .agent/workflows/templates/examples/<name>/      (shipped example workflows)
      4. Runtime dir itself (legacy: workflow.yaml in workflows/<name>/)
    """
    workflow_name = os.path.basename(workflow_dir)

    # 1. User-created templates
    my_path = os.path.join(MY_WORKFLOWS_DIR, workflow_name)
    if os.path.isfile(os.path.join(my_path, "workflow.yaml")):
        return my_path

    # 2. Built-in (predefined) templates
    predefined_path = os.path.join(PREDEFINED_DIR, workflow_name)
    if os.path.isfile(os.path.join(predefined_path, "workflow.yaml")):
        return predefined_path

    # 3. Shipped example workflows (e.g. tools-demo)
    examples_path = os.path.join(EXAMPLES_DIR, workflow_name)
    if os.path.isfile(os.path.join(examples_path, "workflow.yaml")):
        return examples_path

    # 4. Legacy fallback: workflow.yaml in runtime dir itself
    if os.path.isfile(os.path.join(workflow_dir, "workflow.yaml")):
        return workflow_dir

    # Not found — return runtime dir (will produce a clear error downstream)
    return workflow_dir


def load_yaml_simple(path):
    """Load YAML using PyYAML."""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        raise RuntimeError("PyYAML required: pip install pyyaml")


def find_current_step(manifest):
    """Find the current step name and its config from manifest."""
    current = manifest.get("current_step")
    if current and current in manifest.get("steps", {}):
        return current, manifest["steps"][current]
    return None, None


def _definition_index(workflow_config, step_name, fallback):
    """Return the step's zero-based index from the workflow definition."""
    if workflow_config:
        for i, s in enumerate(workflow_config.get("steps", [])):
            if s.get("name") == step_name:
                return i
    return fallback


def find_step_config(workflow_yaml, step_name):
    """Get the full step configuration from workflow.yaml."""
    for step in workflow_yaml.get("steps", []):
        if step.get("name") == step_name:
            return step
    return {}


def find_step_outputs(workflow_yaml, step_name):
    """Get the outputs configuration for a step from workflow.yaml."""
    step = find_step_config(workflow_yaml, step_name)
    return step.get("outputs", [])


def get_max_gate_retries(workflow_config, step_name):
    """Resolve max_gate_retries: step gate → workflow gate → default 5."""
    default = 5
    workflow_limit = workflow_config.get("gate", {}).get("max_gate_retries", default)
    step = find_step_config(workflow_config, step_name)
    return step.get("gate", {}).get("max_gate_retries", workflow_limit)


def resolve_output_path(path_template, workflow_dir):
    """Resolve an output path template to actual file paths.

    Paths in workflow.yaml outputs are relative to the **workflow directory**
    (e.g. ``data/retry-test.json`` → ``<workflow_dir>/data/retry-test.json``).

    Handles {variable} placeholders and globs.
    """
    # Replace {variable} with wildcard for glob matching
    glob_pattern = re.sub(r"\{[^}]+\}", "*", path_template)
    # Resolve relative to workflow directory
    abs_pattern = os.path.join(workflow_dir, glob_pattern)
    files = glob_module.glob(abs_pattern, recursive=True)
    return files


def validate_outputs(outputs, definition_dir, runtime_dir):
    """Validate all step outputs against their struct schemas.

    Args:
        outputs: list of output dicts from workflow.yaml step definition
        definition_dir: where struct schemas live (predefined/<name>/structs/)
        runtime_dir: where output data files live (<name>/data/)

    Returns (passed, checks, failures, details).
    """
    if not outputs:
        return True, 0, 0, ["No output schemas defined — skipping structural gate"]

    total_checks = 0
    total_failures = 0
    all_details = []

    structs_dir = os.path.join(definition_dir, "structs")

    for output in outputs:
        struct_name = output.get("struct")
        if not struct_name:
            continue  # No schema for this output

        output_path = output.get("path", "")
        schema_path = os.path.join(structs_dir, f"{struct_name}.schema.yaml")

        if not os.path.isfile(schema_path):
            total_checks += 1
            total_failures += 1
            all_details.append(f"Schema not found: {schema_path}")
            continue

        # Resolve output files relative to runtime dir (where subagent writes)
        files = resolve_output_path(output_path, runtime_dir)
        if not files:
            total_checks += 1
            total_failures += 1
            all_details.append(f"No output files matching: {output_path}")
            continue

        # Run schema-validate.py for each file
        for file_path in files:
            try:
                result = subprocess.run(
                    [sys.executable, SCHEMA_VALIDATE, file_path, schema_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    total_checks += 1
                    total_failures += 1
                    all_details.append(
                        f"Validator error for {file_path}: {result.stderr.strip()}"
                    )
                    continue

                validation = json.loads(result.stdout)
                total_checks += validation.get("checks", 0)
                total_failures += validation.get("failures", 0)
                all_details.extend(validation.get("details", []))

            except subprocess.TimeoutExpired:
                total_checks += 1
                total_failures += 1
                all_details.append(f"Validation timeout for {file_path}")
            except Exception as e:
                total_checks += 1
                total_failures += 1
                all_details.append(f"Validation error for {file_path}: {e}")

    passed = total_failures == 0
    return passed, total_checks, total_failures, all_details


# ---------------------------------------------------------------------------
# Transcript extraction (Claude Code)
# ---------------------------------------------------------------------------

def _extract_from_transcript(transcript_path):
    """Extract model, duration, message/tool counts, and modified files
    from a Claude Code subagent transcript (JSONL format).

    Claude Code's SubagentStop hook payload lacks these fields (unlike Cursor).
    The transcript contains everything: each assistant message has model,
    usage (tokens), and tool_use blocks.

    Returns dict with extracted fields (any may be None if extraction fails).
    """
    result = {
        "model": None,
        "duration_ms": None,
        "message_count": 0,
        "tool_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "modified_files": [],
    }

    if not transcript_path or not os.path.isfile(transcript_path):
        return result

    try:
        timestamps = []
        models = set()
        tool_calls = 0
        modified = set()
        msg_count = 0
        detailed_tool_calls = []  # Structured tool call info

        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_count += 1
                ts = entry.get("timestamp")
                if ts:
                    timestamps.append(ts)

                msg = entry.get("message", {})
                if not isinstance(msg, dict):
                    continue

                model = msg.get("model")
                if model:
                    models.add(model)

                usage = msg.get("usage", {})
                if isinstance(usage, dict):
                    result["input_tokens"] += usage.get("input_tokens", 0)
                    result["output_tokens"] += usage.get("output_tokens", 0)

                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_calls += 1
                            name = block.get("name", "")
                            inp = block.get("input", {})
                            if isinstance(inp, dict):
                                fp = inp.get("file_path", "")
                                if name in ("Write", "Edit") and fp:
                                    modified.add(fp)

                            # Collect detailed info for MCP tool calls
                            # (prefix mcp__ indicates MCP tool, skip built-in tools)
                            if name.startswith("mcp__"):
                                tc_entry = {
                                    "tool": name,
                                    "tool_short": name.split("__")[-1],
                                    "server": name.split("__")[1] if name.count("__") >= 2 else "",
                                    "arguments": inp if isinstance(inp, dict) else {},
                                    "timestamp": ts or "",
                                    "source": "mcp_transcript",
                                }
                                detailed_tool_calls.append(tc_entry)

        result["message_count"] = msg_count
        result["tool_call_count"] = tool_calls
        result["modified_files"] = sorted(modified)
        result["detailed_tool_calls"] = detailed_tool_calls

        if models:
            result["model"] = sorted(models)[0]  # Primary model

        if len(timestamps) >= 2:
            try:
                t1 = datetime.fromisoformat(timestamps[0])
                t2 = datetime.fromisoformat(timestamps[-1])
                result["duration_ms"] = max(0, int((t2 - t1).total_seconds() * 1000))
            except (ValueError, TypeError):
                pass

    except Exception as e:
        _log_error(f"Transcript extraction failed for {transcript_path}: {e}")

    return result


# ---------------------------------------------------------------------------
# Trace capture
# ---------------------------------------------------------------------------

def _build_trace_modifier(manifest, step_name, hook_input, gate_result,
                           workflow_config, loop_count, followup_message=None):
    """Build a modifier function for locked_json_read_modify_write on trace."""

    def modifier(trace):
        # Ensure gate_config exists
        if "gate_config" not in trace and workflow_config:
            wf_gate = workflow_config.get("gate", {})
            trace["gate_config"] = {
                "structural": wf_gate.get("structural", True),
                "semantic": wf_gate.get("semantic", False),
                "human": wf_gate.get("human", False),
                "max_gate_retries": wf_gate.get("max_gate_retries", 5),
                "max_step_retries": wf_gate.get("max_step_retries", 3),
            }

        # Find or create step entry
        step_entry = None
        for s in trace.get("steps", []):
            if s.get("name") == step_name:
                step_entry = s
                break

        if step_entry is None:
            step_cfg = find_step_config(workflow_config, step_name) if workflow_config else {}
            step_gate_override = step_cfg.get("gate")

            raw_inputs = step_cfg.get("inputs", [])
            raw_outputs = step_cfg.get("outputs", [])
            inputs_list = []
            for inp in raw_inputs:
                if isinstance(inp, dict):
                    inputs_list.append({
                        "path": inp.get("path", ""),
                        "inject": inp.get("inject", "reference"),
                        "struct": inp.get("struct"),
                    })
                elif isinstance(inp, str):
                    inputs_list.append({"path": inp, "inject": "reference"})
            outputs_list = []
            for out in raw_outputs:
                if isinstance(out, dict):
                    outputs_list.append({
                        "path": out.get("path", ""),
                        "struct": out.get("struct"),
                    })
                elif isinstance(out, str):
                    outputs_list.append({"path": out})

            step_entry = {
                "name": step_name,
                "index": _definition_index(workflow_config, step_name, len(trace.get("steps", []))),
                "status": "in_progress",
                "config": {
                    "spec_check": step_cfg.get("spec_check", True),
                    "subagent": step_cfg.get("subagent", True),
                    "gate": step_gate_override,
                },
                "goal": step_cfg.get("goal"),
                "inputs": inputs_list if inputs_list else None,
                "outputs": outputs_list if outputs_list else None,
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
                "invocations": [],
                "retry_count": 0,
                "summary": None,
            }
            trace.setdefault("steps", []).append(step_entry)

        # Determine retry_type
        existing_count = len(step_entry["invocations"])
        if existing_count == 0:
            retry_type = None
        elif loop_count > 1:
            retry_type = "gate"
        else:
            retry_type = "step"

        # Build invocation entry
        now_iso = datetime.now(timezone.utc).astimezone().isoformat()

        # Claude Code hook payload lacks model, duration, message/tool counts.
        # Extract from transcript if available (Claude Code provides
        # agent_transcript_path with full JSONL conversation log).
        transcript_path = hook_input.get("agent_transcript_path")
        tx = _extract_from_transcript(transcript_path)

        # Use hook_input fields first (Cursor provides them directly),
        # fall back to transcript-extracted values (Claude Code).
        duration_ms = hook_input.get("duration_ms") or tx["duration_ms"] or 0
        model = hook_input.get("model") or tx["model"]
        message_count = hook_input.get("message_count") or tx["message_count"]
        tool_call_count = hook_input.get("tool_call_count") or tx["tool_call_count"]
        modified_files = hook_input.get("modified_files") or tx["modified_files"]
        subagent_id = hook_input.get("subagent_id") or hook_input.get("agent_id")

        invocation = {
            "iteration": existing_count + 1,
            "retry_type": retry_type,
            "completed_at": now_iso,
            "duration_ms": duration_ms,
            "hook_status": hook_input.get("status", "unknown"),
            "message_count": message_count,
            "tool_call_count": tool_call_count,
            "modified_files": modified_files,
            "subagent_id": subagent_id,
            "task_prompt": hook_input.get("task"),
            "subagent_summary": hook_input.get("summary") or hook_input.get("last_assistant_message"),
            "transcript_path": transcript_path,
            "model": model,
            "token_usage": {
                "input": tx["input_tokens"],
                "output": tx["output_tokens"],
            } if (tx["input_tokens"] or tx["output_tokens"]) else None,
            "gate": {
                "type": gate_result.get("gate_type", "structural"),
                "passed": gate_result.get("passed", False),
                "checks": gate_result.get("checks", 0),
                "failures": gate_result.get("failures", 0),
                "details": gate_result.get("details", []),
            },
            "followup_message": followup_message,
        }
        step_entry["invocations"].append(invocation)

        # Update step timing
        if step_entry["started_at"] is None:
            if duration_ms:
                start_dt = datetime.fromisoformat(now_iso) - \
                    timedelta(milliseconds=duration_ms)
                step_entry["started_at"] = start_dt.isoformat()
            else:
                step_entry["started_at"] = now_iso

        step_entry["completed_at"] = now_iso
        step_entry["retry_count"] = max(0, len(step_entry["invocations"]) - 1)

        if step_entry["started_at"]:
            try:
                start = datetime.fromisoformat(step_entry["started_at"])
                end = datetime.fromisoformat(now_iso)
                step_entry["duration_ms"] = int((end - start).total_seconds() * 1000)
            except (ValueError, TypeError):
                step_entry["duration_ms"] = duration_ms

        if gate_result.get("passed", False):
            step_entry["status"] = "completed"

        return trace

    return modifier


def append_trace_entry(workflow_dir, manifest, step_name, hook_input,
                       gate_result, workflow_config, loop_count,
                       followup_message=None):
    """Append an invocation entry to the trace file for the current step.

    Uses file locking to prevent race conditions when multiple parallel
    subagents complete simultaneously. Creates the trace file (lazy init)
    if it doesn't exist yet. Never raises — trace failures must not block
    workflow execution.
    """
    try:
        trace_dir = os.path.join(workflow_dir, "trace")
        os.makedirs(trace_dir, exist_ok=True)

        run_id = manifest.get("run_id", "")
        if not run_id:
            wf_name = manifest.get("workflow", "unknown")
            run_id = f"{wf_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        trace_path = os.path.join(trace_dir, f"{run_id}.trace.json")

        # Build default trace structure for lazy init
        wf_gate = workflow_config.get("gate", {}) if workflow_config else {}
        default_trace = {
            "trace_version": 1,
            "workflow": manifest.get("workflow", "unknown"),
            "workflow_version": manifest.get("workflow_version", 1),
            "run_id": run_id,
            "params": manifest.get("params", {}),
            "gate_config": {
                "structural": wf_gate.get("structural", True),
                "semantic": wf_gate.get("semantic", False),
                "human": wf_gate.get("human", False),
                "max_gate_retries": wf_gate.get("max_gate_retries", 5),
                "max_step_retries": wf_gate.get("max_step_retries", 3),
            },
            "started_at": manifest.get("started_at", ""),
            "completed_at": None,
            "status": "in_progress",
            "total_duration_ms": None,
            "total_messages": 0,
            "total_tool_calls": 0,
            "total_modified_files": 0,
            "steps": [],
        }

        modifier = _build_trace_modifier(
            manifest, step_name, hook_input, gate_result,
            workflow_config, loop_count, followup_message
        )

        locked_json_read_modify_write(trace_path, modifier, default=default_trace)

        # Write MCP tool calls from transcript to tool-calls.json
        transcript_path = hook_input.get("agent_transcript_path")
        if transcript_path:
            tx = _extract_from_transcript(transcript_path)
            mcp_tool_calls = tx.get("detailed_tool_calls", [])
            if mcp_tool_calls:
                for tc in mcp_tool_calls:
                    tc["step"] = step_name
                tc_path = os.path.join(workflow_dir, "tool-calls.json")
                existing = []
                if os.path.isfile(tc_path):
                    try:
                        with open(tc_path, "r", encoding="utf-8") as tcf:
                            existing = json.load(tcf)
                    except (json.JSONDecodeError, OSError):
                        pass
                existing.extend(mcp_tool_calls)
                try:
                    with open(tc_path, "w", encoding="utf-8") as tcf:
                        json.dump(existing, tcf, indent=2, ensure_ascii=False)
                except OSError:
                    pass

    except Exception as e:
        # Trace failures must never block workflow execution.
        # Write diagnostic info to error log for debugging.
        _log_error(f"append_trace_entry failed: {type(e).__name__}: {e}")


def _log_error(message):
    """Write a diagnostic message to .agent/gate-check-error.log.

    Append-mode, never raises — purely for debugging when hooks fail silently.
    """
    try:
        log_path = os.path.join(AGENT_DIR, "gate-check-error.log")
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {message}\n")
    except Exception:
        pass  # If even logging fails, give up silently


def detect_host(hook_input):
    """Detect which host is calling the hook based on payload format.

    Claude Code: has 'hook_event_name' field in all hook payloads.
    Cursor: has 'status', 'loop_count', 'task' fields without 'hook_event_name'.
    """
    if "hook_event_name" in hook_input:
        return "claude-code"
    return "cursor"


def build_followup(step_name, passed, checks, failures, details, workflow_config):
    """Build the retry feedback message (on failure) or None (on pass).

    Gate semantics (both hosts):
    - Gate PASS  → return None → subagent stops → orchestrator handles next step
    - Gate FAIL  → return message → subagent retries in same session
    - Retry limit → return None → subagent stops → orchestrator reads gate-result.json

    Delivery mechanism differs by host:
    - Cursor:     JSON {"followup_message": msg} on stdout, exit 0
    - Claude Code: msg on stderr, exit 2 (prevents subagent stopping)
    """
    if passed:
        # Gate passed — subagent should STOP, return control to orchestrator.
        # Orchestrator handles semantic gate, human gate, manifest update, next step.
        return None
    else:
        detail_str = "; ".join(details[:10])  # Limit to 10 issues
        remaining = len(details) - 10
        if remaining > 0:
            detail_str += f"; ... and {remaining} more issues"
        return (
            f"STRUCTURAL GATE FAILED for step '{step_name}' "
            f"({failures}/{checks} checks failed). "
            f"Issues: {detail_str}. "
            f"Fix the issues and retry the step."
        )


def _output_and_exit(host, followup, passed):
    """Output gate result and exit with host-appropriate semantics.

    Cursor:      Always exit 0. followup_message JSON on stdout for retry.
    Claude Code: Exit 0 for pass/stop. Exit 2 + stderr for retry.
    """
    if host == "claude-code":
        if followup:
            sys.stderr.write(followup + "\n")
            sys.exit(2)  # Prevent subagent stopping → retry
        else:
            sys.exit(0)  # Allow subagent to stop
    else:
        # Cursor mode: JSON on stdout, always exit 0
        if followup:
            output = {"followup_message": followup}
        else:
            output = {}
        print(json.dumps(output))
        sys.exit(0)


def main():
    """Main entry point — called by host subagentStop hook.

    Supports both Cursor and Claude Code:
    - Cursor:     Always exit 0, JSON on stdout
    - Claude Code: Exit 0 (pass) or exit 2 (retry), feedback on stderr
    """
    # --- PROLOG: Log immediately on invocation, before any processing. ---
    # If this line never appears in the log, Cursor is not calling the hook.
    try:
        log_path = os.path.join(AGENT_DIR, "gate-check-invocations.log")
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().isoformat()} | INVOKED"
                f" | cwd={os.getcwd()}"
                f" | argv={sys.argv}"
                f" | stdin_isatty={sys.stdin.isatty()}"
                f"\n"
            )
    except Exception:
        pass  # Prolog must never prevent execution
    # --- END PROLOG ---

    try:
        _main_inner()
    except Exception as e:
        # Global safety net — log error and output empty JSON
        error_msg = f"gate-check.py unhandled error: {type(e).__name__}: {e}"
        _log_error(error_msg)
        sys.stderr.write(error_msg + "\n")
        print(json.dumps({}))
        sys.exit(0)


def _main_inner():
    # Read hook input from stdin as raw bytes, then decode manually.
    # REASON: On Windows, sys.stdin.read() uses the system locale encoding
    # (e.g., cp1252), NOT UTF-8. When Cursor prepends a UTF-8 BOM (\xEF\xBB\xBF),
    # those 3 bytes get decoded as 3 cp1252 characters (ï»¿), making
    # raw.lstrip("\ufeff") ineffective. Reading bytes and decoding as UTF-8
    # ensures the BOM is handled correctly on all platforms.
    try:
        raw_bytes = sys.stdin.buffer.read()
        # Strip UTF-8 BOM if present (bytes: \xEF\xBB\xBF)
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            raw_bytes = raw_bytes[3:]
        raw = raw_bytes.decode("utf-8")
        if not raw.strip():
            _log_error(f"Empty stdin received | raw_length={len(raw_bytes)} | raw_repr={repr(raw_bytes[:100])}")
        hook_input = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        _log_error(f"Invalid hook input JSON: {e} | raw_length={len(raw_bytes)} | raw_repr={repr(raw_bytes[:500])}")
        print(json.dumps({"followup_message": f"Gate error: invalid hook input — {e}"}))
        sys.exit(0)
    except UnicodeDecodeError as e:
        _log_error(f"Stdin decode error: {e} | raw_repr={repr(raw_bytes[:500])}")
        print(json.dumps({"followup_message": f"Gate error: stdin decode failed — {e}"}))
        sys.exit(0)

    # --- TEST MODE: force specific exit code for testing gate retry ---
    # Set GATE_TEST_EXIT=2 in the terminal BEFORE starting Claude Code.
    # When set, gate-check.py will immediately return the specified exit code
    # with a diagnostic message, allowing you to test exit 2 (retry) behavior.
    _test_exit = os.environ.get("GATE_TEST_EXIT", "")
    if _test_exit:
        host = detect_host(hook_input)
        test_code = int(_test_exit)
        msg = (
            f"GATE TEST MODE: Returning exit {test_code}. "
            f"Host detected: {host}. "
            f"If exit 2 works, this agent should NOT stop — "
            f"it should receive this message and continue."
        )
        _log_error(f"GATE_TEST_EXIT={test_code} | host={host}")
        if host == "claude-code":
            sys.stderr.write(msg + "\n")
            sys.exit(test_code)
        else:
            if test_code != 0:
                print(json.dumps({"followup_message": msg}))
            else:
                print(json.dumps({}))
            sys.exit(0)

    # --- DEBUG: dump hook_input when GATE_DEBUG env var is set ---
    _gate_debug = os.environ.get("GATE_DEBUG", "")
    if _gate_debug:
        debug_path = os.path.join(AGENT_DIR, "gate-check-debug.log")
        try:
            # Level "1" = keys only; "2" = full payload; "keys" = keys + model field
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n{datetime.now().isoformat()} | HOOK INPUT DUMP\n")
                if _gate_debug == "1":
                    f.write(f"keys: {sorted(hook_input.keys())}\n")
                    f.write(f"model: {hook_input.get('model')}\n")
                    f.write(f"status: {hook_input.get('status')}\n")
                else:
                    f.write(json.dumps(hook_input, indent=2, ensure_ascii=False, default=str))
                    f.write("\n")
        except Exception:
            pass
    # --- END DEBUG ---

    # ── Host detection ──
    host = detect_host(hook_input)

    # ── Cursor-only: status and phantom filtering ──
    # Claude Code: matcher in settings.json filters by agent_type,
    # so only workflow-step agents reach this code. No phantom detection needed.
    if host == "cursor":
        status = hook_input.get("status", "unknown")
        if status != "completed":
            _log_error(f"Skipping non-completed subagent: status={status}")
            print(json.dumps({}))
            sys.exit(0)

        # Filter phantom invocations (Cursor-specific)
        subagent_id = hook_input.get("subagent_id", "")
        task_prompt = hook_input.get("task", "")
        if subagent_id.startswith("toolu_") or (not task_prompt.strip()):
            print(json.dumps({}))
            sys.exit(0)

        # Run token from task prompt (Cursor-specific)
        run_token_match = re.search(r"<!--workflow:run_token:([a-f0-9-]+)-->", task_prompt)
        if not run_token_match:
            print(json.dumps({}))
            sys.exit(0)
        subagent_run_token = run_token_match.group(1)
    else:
        subagent_run_token = None  # Claude Code: verify via manifest only

    # ── Loop count ──
    # Cursor: provided in hook payload.
    # Claude Code: computed from gate-result.json history.
    if host == "cursor":
        loop_count = hook_input.get("loop_count", 0)
    else:
        loop_count = 0  # Will be computed after we find workflow_dir

    # Find active workflow
    workflow_dir = find_workflow_dir()
    if not workflow_dir:
        _output_and_exit(host, None, True)  # No active workflow — exit silently

    # Load manifest and workflow definition
    try:
        manifest_path = os.path.join(workflow_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Run token verification
        # Cursor: compare token from task prompt vs manifest
        # Claude Code: skip (matcher already filtered by agent_type)
        manifest_token = manifest.get("run_token", "")
        if host == "cursor" and manifest_token and subagent_run_token != manifest_token:
            print(json.dumps({}))
            sys.exit(0)

        # Definition dir may differ from runtime dir (predefined workflows)
        definition_dir = find_definition_dir(workflow_dir)
        workflow_path = os.path.join(definition_dir, "workflow.yaml")
        workflow_config = load_yaml_simple(workflow_path)
    except Exception as e:
        _log_error(f"Failed to load manifest/workflow: {e} (dir: {workflow_dir})")
        _output_and_exit(host, f"Gate error: {e}", False)

    # Find current step
    step_name, step_data = find_current_step(manifest)
    if not step_name:
        _log_error(f"No current step in manifest (workflow_dir: {workflow_dir})")
        _output_and_exit(host, None, True)

    # ── Claude Code: compute loop_count from gate-result.json ──
    if host == "claude-code":
        result_path = os.path.join(workflow_dir, "gate-result.json")
        if os.path.isfile(result_path):
            try:
                with open(result_path, "r", encoding="utf-8") as f:
                    prev_result = json.load(f)
                if prev_result.get("step") == step_name:
                    loop_count = prev_result.get("loop_count", 0) + 1
                else:
                    loop_count = 0  # Different step — reset counter
            except (json.JSONDecodeError, OSError):
                loop_count = 0
        else:
            loop_count = 0

    # Check if structural gate is disabled (workflow-level or step-level override)
    wf_structural = workflow_config.get("gate", {}).get("structural", True)
    step_cfg = find_step_config(workflow_config, step_name)
    step_structural = step_cfg.get("gate", {}).get("structural", wf_structural)
    if not step_structural:
        # Structural gate disabled — skip validation, report pass
        passed, checks, failures, details = True, 0, 0, [
            "Structural gate disabled (structural: false) — skipping validation"
        ]
    else:
        # Get output schemas for current step
        outputs = find_step_outputs(workflow_config, step_name)

        # Run structural validation
        # - Struct schemas live in definition_dir (predefined/<name>/structs/)
        # - Output data files live in workflow_dir (runtime: <name>/data/)
        passed, checks, failures, details = validate_outputs(
            outputs, definition_dir, workflow_dir
        )

    # Write gate-result.json for orchestrator visibility (with locking)
    gate_result = {
        "step": step_name,
        "passed": passed,
        "checks": checks,
        "failures": failures,
        "details": details,
        "loop_count": loop_count,
    }
    result_path = os.path.join(workflow_dir, "gate-result.json")
    locked_json_read_modify_write(
        result_path, lambda _: gate_result, default={}
    )

    # Build followup message (needed for both trace and Cursor response)
    followup = build_followup(
        step_name, passed, checks, failures, details, workflow_config
    )

    # Append trace entry (non-blocking side-effect) — includes followup for retry context
    append_trace_entry(workflow_dir, manifest, step_name, hook_input,
                       gate_result, workflow_config, loop_count, followup)

    # Check max_gate_retries: if loop_count reached the limit, stop the loop
    max_gate = get_max_gate_retries(workflow_config, step_name)
    if not passed and loop_count >= max_gate:
        # Limit reached — return {} so subagent stops, orchestrator reads gate-result.json
        _log_error(
            f"Gate retry limit reached for step '{step_name}': "
            f"{loop_count}/{max_gate} (failures: {failures}/{checks})"
        )
        followup = None  # Clear followup so subagent stops

    # Epilog: log the decision for diagnostics
    action = "RETRY" if followup else ("PASS" if passed else "STOP")
    try:
        log_path = os.path.join(AGENT_DIR, "gate-check-invocations.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().isoformat()} | RESULT"
                f" | host={host}"
                f" | step={step_name}"
                f" | passed={passed}"
                f" | action={action}"
                f" | checks={checks}"
                f" | failures={failures}"
                f" | loop={loop_count}"
                f" | workflow_dir={workflow_dir}"
                f"\n"
            )
    except Exception:
        pass

    # Output with host-appropriate semantics
    _output_and_exit(host, followup, passed)


if __name__ == "__main__":
    main()
