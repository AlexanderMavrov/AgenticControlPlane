# italy_games

## Overview

Legacy VLT game project for the **Italian market**.

## Architecture

- Integrations are implemented **directly inside the game code** (not via kernel API)
- This is the key difference from the `games` project — integration code lives inside the game itself

## Current Phase

- **Polish, bugfixing, and certification**
- Active work continues on existing games and integrations

## Integrations

| Partner   | Status    | Docs                          |
| --------- | --------- | ----------------------------- |
| Sisal (Astro) | Active    | `docs/astro/`, `ai_docs/`    |
| Inspired  | Certified | `docs/inspired/`, `ai_docs/` |

> **Note:** Integration-specific documentation lives in subdirectories of `docs/` (e.g., `docs/astro/`, `docs/inspired/`). AI-generated analysis documents live in `ai_docs/` at project level. Task-specific work is tracked in `tasks/`.


## Source Code

Located in `C:/mklinks/`. Each subdirectory is a checkout of a specific branch:

| Directory                                      | Branch                         | Notes                  |
| ---------------------------------------------- | ------------------------------ | ---------------------- |
| `italy_games_sisal_r1/`                        | `sisal_r1`                     | Current working branch |
| `italy_games_release_shining_crown_chc_37/`    | `release/shining_crown_chc_37` | May not always be present |

> **Note:** Branch checkouts may be added or removed over time. If the expected directory does not exist, ask the user how to proceed.

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
