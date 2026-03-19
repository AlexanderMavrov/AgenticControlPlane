# WORK_TOPICS

## Overview

This workspace tracks work on **VLT (Video Lottery Terminal) reel-based games** developed in **C++**. All games go through strict **regulatory certification** by official institutions. We support multiple platforms (called **integrations**).

## Top-Level Structure

| Path              | Purpose                                                        |
| ----------------- | -------------------------------------------------------------- |
| `CLAUDE.md`       | Workspace-wide context and instructions (this file)            |
| `.claude/skills/` | Skill definitions for workflows                               |
| `projects/`       | All project work — cross-project and per-project scopes        |
| `tasks/`          | **Universal tasks** — not tied to a specific project           |
| `.user/`          | **Personal notes** — not used by CLAUDE.md or AI workflows     |

### `.user/` Directory

The `.user/` directory contains the user's private notes and scratch files. Claude should **not** read, modify, or reference files in `.user/` unless the user explicitly asks.

## Projects

All projects live under `projects/`. Cross-project `todo.md`, `discussion.md`, `docs/`, and `ai_docs/` also live there.

### italy_games (Legacy)

- VLT games for the Italian market
- Integrations are implemented **directly inside the game code** (no kernel API)
- Current phase: **polish, bugfixing, and certification**
- Active work continues

### games (New Generation)

- Improved architecture with cleaner separation of concerns
- Games communicate with integrations through an internal **kernel API** (unified interface)
- The game's **FSM (Finite State Machine)** interacts with the kernel
- Under **active development**

## Directory Convention

Every level inside `projects/` follows the same structure:

| File/Dir         | Purpose                                                       |
| ---------------- | ------------------------------------------------------------- |
| `CLAUDE.md`      | Context and instructions for that level                       |
| `todo.md`        | Task tracking scoped to that level                            |
| `discussion.md`  | Discussion log scoped to that level                           |
| `docs/`          | Human-authored documents, specs, references                   |
| `ai_docs/`       | AI-generated summaries, notes, analysis                       |
| `tasks/`         | Structured task tracking with subdirectories per task          |

> **Source priority:** `docs/` is the **authoritative source** — it contains original documentation from partners and specs. `ai_docs/` is a helpful reference but may contain inaccuracies or outdated information. When in doubt, always trust `docs/` over `ai_docs/`.

**Scope resolution:**

- **Cross-project** (`projects/`) — topics spanning multiple projects
- **Project** (`projects/italy_games/`, `projects/games/`) — whole-project scope

## Level Resolution Rule

When the user asks to add a todo, log a discussion, or generate an ai_doc, they will explicitly specify the level if it differs from the current working directory. If no level is specified, default to the **current working directory** level.

## Language Rules

- **CLAUDE.md files**: Always in English
- **todo.md, discussion.md, ai_docs/ content**: Written in **Bulgarian**, with technical terms kept in their original English form

## File Format Preference

Always prefer `.md` over `.pdf`. The `docs/` directories contain **PDF files** with documentation (specs, partner documents, etc.), but each PDF also has an equivalent **`.md` version** in the same directory for convenience — use whichever is easier to open. When new PDFs are added, an `.md` equivalent should be created alongside them. AI-generated summaries and analysis go into `ai_docs/`, not `docs/`.

## Workflows

| Action                          | Skill                                       |
| ------------------------------- | ------------------------------------------- |
| Creating structured tasks       | `.claude/skills/create-task/SKILL.md`       |
| Loading task context            | `.claude/skills/load-task/SKILL.md`         |
| Updating a task (progress, discussion, todo, status) | `.claude/skills/update-task/SKILL.md` |
| Updating project-level discussion or todo | `.claude/skills/update-project/SKILL.md` |
| Committing changes              | `.claude/skills/commit/SKILL.md`            |

## Source Code Locations

Game source code lives **outside** this repository, accessed via `C:/mklinks/`:

| Project        | Path                                | Details                              |
| -------------- | ----------------------------------- | ------------------------------------ |
| `italy_games`  | `C:/mklinks/italy_games_sisal_r1/`  | Branch `sisal_r1` (current working)  |
| `games`        | `C:/mklinks/games/`                 | Current working branch               |

Each project's `CLAUDE.md` has the full list of available checkouts. Branch checkouts may be added or removed over time — if an expected directory does not exist, ask the user how to proceed.

## Task Tracking Convention

Tasks live in `tasks/` directories and follow a standard structure:

```
tasks/<task-name>/
├── description.md    — Task description, scope, deliverables
├── progress.md       — Progress tracking checklist
├── discussion.md     — Discussion log scoped to this task
└── todo.md           — Todo items scoped to this task
```

**Two scopes for tasks:**

- **Root-level** (`tasks/`) — universal tasks not tied to a specific project (e.g., tooling, cross-project infrastructure, reusable systems)
- **Project-level** (`projects/<project>/tasks/`) — tasks specific to a single project

Task deliverables go into their appropriate locations (e.g., `ai_docs/`, or within the task's own `dist/` directory for self-contained systems), NOT scattered outside.

**Task-level vs project-level tracking:**
- **Task-level** (`tasks/<task>/discussion.md`, `todo.md`): everything specific to the current task — decisions, open questions, action items
- **Project-level** (`projects/<project>/discussion.md`, `todo.md`): cross-cutting topics that affect the whole project — conventions, architectural decisions, items not tied to a specific task

## Integration Documentation

Integration-specific documentation lives in subdirectories of `docs/` at the project level (e.g., `projects/italy_games/docs/astro/`). There are no separate integration-level directories — all tracking (tasks, discussion, todos) happens at project or task level.

## Working Directory Rules

- **Never hardcode absolute paths to this repo.** The repo can live on any drive or machine.
- **Always write files to the main repo**, not to any worktree path. If running inside a worktree (the working directory contains `.claude/worktrees/` in its path), determine the main repo root dynamically — run `git worktree list` and use the path listed as `[main]`.
- **Never commit automatically.** Only commit when the user explicitly asks.

## Worktree Policy — ABSOLUTE PROHIBITION

**Worktrees are completely forbidden in this workspace.** This is a hard rule with no exceptions.

- **NEVER use `isolation: "worktree"` when launching agents.**
- **NEVER create worktrees**, even if asked to do so without explicit mention of the word "worktree".
- **If Claude Code has already placed this session inside a worktree**: notify the user, determine the main repo path via `git worktree list`, and write all files there directly.

Why worktrees are harmful here:
1. **Invisible to the user**: Files written inside a worktree do not appear in the user's notebook/editor until manually copied out.
2. **Source code is external**: Source code lives in separate repos under `C:/mklinks/`. A worktree in the notebook repo does not isolate those repos — agents still write to them directly, making isolation pointless.
3. **No benefit**: All work here is `.md` files — there is zero risk that justifies the complexity and confusion of worktrees.

If code isolation is ever needed, use **git branches** in the source code repos (`C:/mklinks/`) directly.

## Diagram Preference

- Prefer **Mermaid** format for all diagrams (class diagrams, sequence diagrams, flowcharts, state diagrams, etc.).
