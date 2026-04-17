---
name: init-workflow
description: "Generate per-step subagent files for a workflow from workflow.yaml. Run this after creating or editing a workflow, then restart Claude Code."
allowed-tools: Bash
disable-model-invocation: true
---

# /init-workflow

Generate or update the per-step subagent files for a single workflow.

## Usage

```
/init-workflow <workflow-name>
```

## What this does

For each step in the workflow that has `subagent: true`, this command generates a dedicated subagent file at `.claude/agents/<workflow>-<step>/AGENT.md`. Each generated file has a strict `tools:` whitelist containing:

- Built-in tools (Read, Write, Edit, Bash, Glob, Grep)
- Script tools the step declares (exposed as `mcp__workflow_tools__<workflow>__<tool>`)
- MCP tools the step declares (via `expected_tools` in workflow.yaml)

After running this command, **you MUST restart Claude Code** before running the workflow — CC only scans `.claude/agents/` at session startup.

## How to invoke

Execute the generation script directly via Bash:

```bash
python .agent/scripts/init-workflow.py <workflow-name>
```

After the script completes, report to the user:

1. Which subagent files were **created**, **updated**, or left **unchanged**
2. Which **orphan** files (from removed steps) were **deleted**
3. **Explicitly tell the user** to restart Claude Code if there were any changes
4. After restart, the workflow can be run via `/run-workflow <workflow-name>`

## If the script reports an error

- **Workflow not found** → ask the user to check the name or create the workflow first
- **Malformed workflow.yaml** → show the error and suggest fixing the YAML
- **File write error** → check filesystem permissions

## NEVER

- **Never** write or edit AGENT.md files manually. Always go through `python .agent/scripts/init-workflow.py`.
- **Never** skip the restart reminder when files changed.
- **Never** proceed to `/run-workflow` yourself — tell the user to restart first.
