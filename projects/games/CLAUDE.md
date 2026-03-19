# games

## Overview

New-generation VLT game project with **improved architecture**.

## Architecture

- Games do **NOT** implement integrations directly
- Communication goes through an internal **kernel API** — a unified interface for all platforms
- The game's **FSM (Finite State Machine)** interacts with the kernel
- See `fsm-kernel-communication.md` (when available) for detailed communication flow

## Current Phase

- Under **active development**

## Integrations

Integration subdirectories will be created as work begins, following the standard structure (`CLAUDE.md` + `todo.md` + `discussion.md` + `docs/` + `ai_docs/`).

## Source Code

Located in `C:/mklinks/`:
- `games/` — checkout of current working branch

## Tasks

The `tasks/` directory contains structured task tracking for larger documentation or analysis work. Each task has its own subdirectory:

```
tasks/<task-name>/
├── description.md    — Scope, deliverables, references
├── progress.md       — Phase checklist
├── discussion.md     — Task-specific discussion log
└── todo.md           — Task-specific action items
```

Use `update-task` skill to update an active task. Use project-level `discussion.md` and `todo.md` only for cross-cutting topics not tied to a specific task.
