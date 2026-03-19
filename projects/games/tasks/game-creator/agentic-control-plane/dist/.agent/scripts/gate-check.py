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
        with open(lock_path, "w") as lock_f:
            _lock_file(lock_f)
            try:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
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
AGENT_DIR = ".agent"
WORKFLOWS_DIR = os.path.join(AGENT_DIR, "workflows")
TEMPLATES_DIR = os.path.join(WORKFLOWS_DIR, "templates")
PREDEFINED_DIR = os.path.join(TEMPLATES_DIR, "predefined")
MY_WORKFLOWS_DIR = os.path.join(TEMPLATES_DIR, "my_workflows")
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

    Search order:
      1. .agent/workflows/templates/my_workflows/<name>/  (user-created templates)
      2. .agent/workflows/templates/predefined/<name>/    (built-in templates)
      3. Runtime dir itself (legacy: workflow.yaml in workflows/<name>/)
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

    # 3. Legacy fallback: workflow.yaml in runtime dir itself
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
                "index": len(trace.get("steps", [])),
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
        duration_ms = hook_input.get("duration_ms", 0)
        invocation = {
            "iteration": existing_count + 1,
            "retry_type": retry_type,
            "completed_at": now_iso,
            "duration_ms": duration_ms,
            "hook_status": hook_input.get("status", "unknown"),
            "message_count": hook_input.get("message_count", 0),
            "tool_call_count": hook_input.get("tool_call_count", 0),
            "modified_files": hook_input.get("modified_files", []),
            # Cursor-provided context (may be null on older Cursor versions)
            "subagent_id": hook_input.get("subagent_id"),
            "task_prompt": hook_input.get("task"),
            "subagent_summary": hook_input.get("summary"),
            "transcript_path": hook_input.get("agent_transcript_path"),
            "model": hook_input.get("model"),
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


def build_followup(step_name, passed, checks, failures, details, workflow_config):
    """Build the followup_message for the subagent (on failure) or None (on pass).

    CRITICAL DESIGN RULE (Cursor hook semantics):
    - followup_message continues the SAME subagent session (another turn)
    - returning {} (no followup) STOPS the subagent → control returns to orchestrator

    Therefore:
    - Gate PASS  → return None → subagent stops → orchestrator handles next step
    - Gate FAIL  → return message → subagent retries in same session (has context)
    - Retry limit → return None → subagent stops → orchestrator reads gate-result.json
    """
    if passed:
        # Gate passed — subagent should STOP, return control to orchestrator.
        # Orchestrator handles semantic gate, human gate, manifest update, next step.
        return None
    else:
        detail_str = "; ".join(details[:5])  # Limit to 5 issues
        remaining = len(details) - 5
        if remaining > 0:
            detail_str += f"; ... and {remaining} more issues"
        return (
            f"STRUCTURAL GATE FAILED for step '{step_name}' "
            f"({failures}/{checks} checks failed). "
            f"Issues: {detail_str}. "
            f"Fix the issues and retry the step."
        )


def main():
    """Main entry point — called by Cursor subagentStop hook.

    IMPORTANT: This function must ALWAYS output valid JSON on stdout and
    exit with code 0, even on errors. Crashing or outputting non-JSON
    would break the Cursor hook chain and block the workflow.
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

    status = hook_input.get("status", "unknown")
    loop_count = hook_input.get("loop_count", 0)

    # Only process completed subagents
    if status != "completed":
        # Don't interfere with errored or aborted subagents
        _log_error(f"Skipping non-completed subagent: status={status} | hook_keys={list(hook_input.keys())}")
        print(json.dumps({}))
        sys.exit(0)

    # Filter out orchestrator "phantom" invocations.
    # Real subagents have UUID subagent_id (e.g. "224b081f-866d-42ec-...").
    # When an orchestrator stops, Cursor fires the hook too — but with a
    # tool-use ID ("toolu_...") instead of UUID, and task="" (empty prompt).
    # These phantom invocations must be ignored: they duplicate gate results
    # and pollute the trace with empty entries.
    #
    # We check BOTH indicators to be safe:
    #   - subagent_id format: "toolu_" prefix = tool-use ID (orchestrator)
    #   - task field: empty string = no spawn prompt (orchestrator echo)
    # Either one is sufficient to identify a phantom invocation.
    subagent_id = hook_input.get("subagent_id", "")
    task_prompt = hook_input.get("task", "")
    if subagent_id.startswith("toolu_") or (not task_prompt.strip()):
        print(json.dumps({}))
        sys.exit(0)

    # ── Run token verification ──
    # The orchestrator injects a unique token into each subagent's task prompt:
    #   <!--workflow:run_token:<uuid>-->
    # Only subagents with a matching token are part of the active workflow.
    # This prevents "zombie workflow" false matches and phantom invocations
    # from unrelated subagents that happen to run while a workflow is active.
    run_token_match = re.search(r"<!--workflow:run_token:([a-f0-9-]+)-->", task_prompt)
    if not run_token_match:
        # No run token in prompt → not a workflow subagent. Exit silently.
        print(json.dumps({}))
        sys.exit(0)
    subagent_run_token = run_token_match.group(1)

    # Find active workflow
    workflow_dir = find_workflow_dir()
    if not workflow_dir:
        # No active workflow — this subagent wasn't part of a workflow.
        # Not an error: many subagents run outside of workflow context.
        print(json.dumps({}))
        sys.exit(0)

    # Load manifest and workflow definition
    try:
        manifest_path = os.path.join(workflow_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Verify run_token matches manifest (prevents zombie workflow matches)
        manifest_token = manifest.get("run_token", "")
        if manifest_token and subagent_run_token != manifest_token:
            # Token mismatch — subagent belongs to a different (possibly old) run
            print(json.dumps({}))
            sys.exit(0)

        # Definition dir may differ from runtime dir (predefined workflows)
        definition_dir = find_definition_dir(workflow_dir)
        workflow_path = os.path.join(definition_dir, "workflow.yaml")
        workflow_config = load_yaml_simple(workflow_path)
    except Exception as e:
        _log_error(f"Failed to load manifest/workflow: {e} (dir: {workflow_dir})")
        print(json.dumps({"followup_message": f"Gate error: {e}"}))
        sys.exit(0)

    # Find current step
    step_name, step_data = find_current_step(manifest)
    if not step_name:
        _log_error(f"No current step in manifest (workflow_dir: {workflow_dir})")
        print(json.dumps({}))
        sys.exit(0)

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

    # Build output: followup_message only on gate FAILURE (continues subagent loop)
    # On gate PASS or retry limit: {} stops subagent, returns control to orchestrator
    if followup:
        output = {"followup_message": followup}
    else:
        output = {}

    # Epilog: log the decision for diagnostics
    action = "RETRY" if followup else ("PASS" if passed else "STOP")
    try:
        log_path = os.path.join(AGENT_DIR, "gate-check-invocations.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now().isoformat()} | RESULT"
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
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
