---
name: commit
description: Commit current changes. Groups by top-level directory if changes span multiple areas. No push.
---

# Skill: Commit

## Triggers

- **Bulgarian**: "комитни", "направи комит", "запази промените"
- **English**: "commit", "save changes", "commit changes"

## Behavior

1. **Run `git status`** to see all modified, deleted, and untracked files.

2. **Group changes by top-level directory** (the first path segment: `AI/`, `C++/`, `RandomNotes/`, `TestProjects/`, etc.). If all changes are in a single top-level directory, proceed with one commit. If changes span **multiple** top-level directories, propose separate commits — one per directory.

3. **For each proposed commit:**
   - Run `git diff` (staged + unstaged) scoped to that directory for a quick overview
   - Draft a concise commit message (1-2 lines) based on the nature of the changes
   - Format: `<directory>: <what changed>`
   - Examples: `RandomNotes/WORK_TOPICS: add task tracking system`, `C++: update build config`

4. **Show the user** the proposed commit(s) — files to be included and the message — and ask for confirmation before committing.

5. **On confirmation, for each commit:**
   - `git add` only the files in that group
   - `git commit -m "<message>"`

6. **Do NOT push.** Only commit locally.

7. **Do NOT create branches.** Work on the current branch.

## Rules

- Never stage files that look like secrets (`.env`, credentials, tokens)
- Never stage `.claude/worktrees/` — these are ephemeral
- If unsure whether a file should be included, ask the user
- Keep commit messages short and descriptive — no need for deep analysis
- If the user specifies a custom message, use it instead of generating one
