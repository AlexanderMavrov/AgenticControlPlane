# hook-diagnostic

Fast diagnostic workflow (3 steps) that tests the full hook → gate → trace pipeline. Each step tests a different scenario:

| Step | What it tests | Expected behavior |
|------|--------------|-------------------|
| `probe-hook` | Does the hook fire at all? | gate-check.py invoked, writes to invocations.log and trace |
| `probe-struct` | Does struct validation work? | gate-check.py validates output against schema, PASS |
| `probe-retry` | Does the retry loop work? | First attempt FAILS (invalid output), subagent gets feedback, retries, PASSES |

## When to Use

- After initial installation (`install.py`) to verify hooks work
- After updating `gate-check.py` or `hooks.json` to confirm nothing broke
- When troubleshooting "hook not firing" issues
- When verifying the gate retry loop (followup_message → subagent retry)

## Usage

```
/run-workflow hook-diagnostic
```

## Diagnostic Checklist After Running

| File | What to check |
|------|---------------|
| `.agent/gate-check-invocations.log` | **Most important.** Should have INVOKED + RESULT entries for each step. If empty — Cursor is not calling the hook. |
| `.agent/gate-check-error.log` | Should NOT have new entries. If it does — gate-check.py is crashing. |
| `gate-result.json` | Should exist in the workflow dir. Shows last gate check result. |
| `trace/<run-id>.trace.json` | Should have 3 step entries with real invocation data (not synthetic). |

## Interpreting Results

**All 3 steps pass with real trace data** — hook infrastructure is healthy.

**invocations.log is empty** — Cursor is not calling the `subagentStop` hook. Check:
- `.cursor/hooks.json` exists and has the correct `subagentStop` entry
- The `command` path is correct relative to Cursor's CWD
- Cursor version supports hooks

**invocations.log has INVOKED but no RESULT** — gate-check.py starts but crashes mid-execution. Check gate-check-error.log.

**probe-hook passes but probe-struct fails** — structural validation (schema-validate.py) has an issue.

**probe-retry never gets feedback** — followup_message is not being delivered to the subagent. The hook fires but Cursor ignores the response.

**All steps are Synthetic in trace** — the orchestrator ignored the STOP rule. This is an orchestrator compliance issue, not a hook issue.
