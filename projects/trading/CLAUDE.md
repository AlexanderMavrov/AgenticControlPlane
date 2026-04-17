# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project has two layers:

1. **Agentic Control Plane** — a declarative workflow engine for LLM-driven development tasks, deployed from `tasks/fundamental_analyzer/dist/`. The engine defines multi-step workflows (YAML), executes them via subagents with structural/semantic/human gates, tracks state in manifests, and records execution traces.

2. **Argus** (target project) — an Elliott Wave analysis platform for financial markets (Python). Accessed via symlink `elliott_wave_source` → `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer`. The workflow engine is meant to be deployed into this project to manage specs, code changes, and audits.

The primary work here is developing and maintaining the **workflow engine** and its workflows, then deploying them to the Argus project.

## Directory Structure

```
projects/trading/
├── CLAUDE.md                          # This file
├── elliott_wave_source -> ...         # Symlink to Argus source code
└── tasks/
    └── fundamental_analyzer/
        └── dist/                      # Workflow engine distribution (development copy)
            ├── .agent/                # Universal engine layer
            │   ├── docs/              # Engine documentation (format references)
            │   ├── mcp/               # MCP servers (workflow-engine.py, workflow-tools-loader.py)
            │   ├── scripts/           # Engine scripts (gate-check.py, schema-validate.py, etc.)
            │   ├── specs/             # Behavioral specifications (_index.json, _registry.json)
            │   ├── tools/             # Browser-based viewers (trace-viewer.html, workflow-editor.html)
            │   └── workflows/templates/
            │       ├── predefined/    # Built-in workflows (read-only, shipped with engine)
            │       └── my_workflows/  # User-created workflows
            ├── .claude/               # Claude Code adapter
            │   ├── agents/            # Per-step subagent definitions (AGENT.md files)
            │   ├── rules/             # Always-active rules (spec-guard.md, workflow-context.md)
            │   ├── skills/            # Skill definitions (run-workflow, spec, etc.)
            │   └── settings.json      # Hook routing (SubagentStop → gate-check.py)
            ├── .cursor/               # Cursor adapter (parallel to .claude/)
            └── .mcp.json              # MCP server registration
```

## Workflow Engine Architecture

### Two Layers: Universal vs Adapter

- **`.agent/`** — universal engine: workflow definitions, gate scripts, specs, schemas, traces. IDE-agnostic.
- **`.claude/`** / **`.cursor/`** — adapter layers: hook routing, rules, skills, MCP config. IDE-specific.

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Workflow** | YAML file (`workflow.yaml`) defining a sequence of steps with inputs, outputs, gates |
| **Step** | Unit of work executed by an isolated subagent (or inline by orchestrator) |
| **Manifest** | Auto-generated JSON tracking runtime state (`manifest.json`) |
| **Struct** | Schema (`.schema.yaml`) defining expected format for step inputs/outputs |
| **Gate** | Validation between steps — structural (script), semantic (LLM), human (approval) |
| **Spec** | Behavioral specification in `.agent/specs/` — component requirements enforced by Spec Guard |
| **Delegation** | A step can hand off to another workflow via `delegate_to:` |
| **Trace** | Execution metrics per run — timing, gate results, retries, MCP calls |

### Execution Flow

1. `/run-workflow <name>` invoked → orchestrator calls MCP tools to resolve workflow
2. For each step sequentially:
   - `step_begin` → pre-composed text blocks for subagent
   - Subagent executes goal, writes outputs
   - Structural gate (`gate-check.py`) validates outputs via hook
   - `step_collect_result` → orchestrator reads gate result
   - `step_complete` → updates manifest, writes summary, applies param_bindings
3. `workflow_finalize` → completes trace with aggregates

### MCP Servers

- **`workflow-engine.py`** — orchestration tools: `workflow_resolve`, `workflow_init`, `step_begin`, `step_collect_result`, `step_complete`, `workflow_finalize`, `list_agent_files`
- **`workflow-tools-loader.py`** — exposes workflow-declared script tools as MCP tools

### Predefined Workflows

| Workflow | Purpose |
|----------|---------|
| `spec-write` | Create/update a spec (DISCOVER → CLARIFY → WRITE-SPEC → REGISTER-SPEC) |
| `spec-write-and-implement` | Composition: delegates to `spec-write` then `spec-enforcement` |
| `spec-enforcement` | Implement code with spec checking (CHECK-SPECS → IMPLEMENT → VERIFY → REGISTER) |
| `doc-spec-extraction` | Extract specs from documentation (ANALYZE → EXTRACT → VALIDATE → COMMIT) |
| `create-workflow` | Interactive workflow creation assistant (LEARN → DISCUSS → CREATE) |
| `registry-sync` | Sync `_registry.json` with unregistered implementations |
| `spec-audit` | Read-only QA audit — scan code against specs, report violations |
| `hook-diagnostic` | Test hook firing, struct validation, and retry loop |

### Key Skills

| Skill | Purpose |
|-------|---------|
| `/run-workflow <name>` | Execute a workflow with full manifest/trace/gates |
| `/spec` | View specs (list, show) |
| `/spec-with-workflows add` | Create spec via workflow (no implementation) |
| `/spec-fast`, `/code-spec-fast`, `/spec-add-fast` | Lightweight inline alternatives (no workflow overhead) |
| `/init-workflow <name>` | Generate per-step subagent AGENT.md files |
| `/update-workflows` | Bulk sync all workflows' subagent files |

### Deployment

```bash
# Full install to target project
python install.py <target-project-path>

# Update existing installation (preserves user content)
python install.py --update <target-project-path>
```

Always edit files in `dist/` — deployed files are overwritten on next `--update`.

### Documentation Reference

Detailed format references live in `dist/.agent/docs/`:

| Doc | Contents |
|-----|----------|
| `overview.md` | Full system overview, execution model, file structure |
| `workflow-yaml.md` | `workflow.yaml` format: steps, params, gates, tools, delegation, param_bindings |
| `structs.md` | Struct schema format (JSON Schema style and custom style) |
| `manifest.md` | `manifest.json` runtime state format |
| `specs.md` | Behavioral spec format, registry, lifecycle |
| `trace.md` | Trace system: per-step timing, gate results, MCP call log |

## Argus (Target Project) — Quick Reference

**Source:** `elliott_wave_source` symlink → `C:/Users/aleksandar.mavrov/Projects/ElliotWaveAnalyzer`

### Tech Stack

- Python 3.10+, uv package manager, Pyright (basic mode)
- FastAPI + uvicorn (server), APScheduler (periodic scans)
- Key libs: pandas, numpy, scipy, TA-Lib, plotly, lightweight_charts, yfinance, twelvedata, ib_insync, ctrader-open-api

### Commands

```bash
cd elliott_wave_source
uv sync                              # Install dependencies
python main.py                       # Run analysis (CLI)
cd server && uvicorn server:app      # Run scanner server
```

### Architecture

```
MarketDataProvider → Indicators → MarketStructureAnalyzer → Trader/SignalGenerator → Visualization
```

- **Wave detection:** ZigZag (tolerance-based) or Fractals (Bill Williams 5-bar)
- **Pattern analysis:** Impulse (5-wave), Correction (ZigZag), Forming patterns
- **Trading:** Market replay with lookahead bias prevention; strategies in `signal_one.py`, `signal_two.py`
- **Server mode:** FastAPI + APScheduler scans watchlist, generates HTML reports
- **MTF:** LiveTrader composes Trader instances across H1/D1/W1/MN timeframes

### Code Conventions

- Documentation language: Bulgarian (comments, docstrings)
- Type hints: modern syntax (`list[X]`, `dict[K, V]`), comprehensive
- Data modeling: `@dataclass` extensively
- No formal test suite — manual testing via `main.py` and `diagnostic_tools/`

### Important Constraint

Per the source repo's CLAUDE.md: **do not write code directly** in Argus. Generate detailed prompts for Cursor/Antigravity with step-by-step instructions and BEFORE/AFTER diffs. Claude Code is used for analysis, planning, and prompt generation.
