---
name: update-task
description: Update an active task — mark progress, log discussion, add/complete todos, or change status. Combines progress tracking, discussion logging, and todo management at task level.
---

# Skill: Update Task

## Triggers

- **Bulgarian**: "обнови task", "обнови задача", "маркирай като готово", "актуализирай прогреса", "запиши в дискусията на task-а", "добави todo към task-а"
- **English**: "update task", "mark done", "update progress", "log task discussion", "add task todo"

## Behavior

1. **Identify the task** to update. Look for tasks in `projects/<project>/tasks/`. If there is only one active task (status `В процес 🔄`), use it. If there are multiple active tasks or none is obvious from context, ask the user which one.

2. **Read the current task files** (`progress.md`, `description.md`, and optionally `discussion.md`, `todo.md`) to understand the task state.

3. **Determine what to update** based on the user's request. Multiple actions can be combined in a single update.

### Progress updates (`progress.md`)

   **a) Mark items as done:**
   - Check off completed `- [ ]` items
   - Add `**Резултат:** [output path or summary] ✅` after the last item in a completed phase

   **b) Add new phases or items:**
   - Append new phases or checklist items when research reveals additional work

   **c) Always update** the `**Последна актуализация:**` date to today

### Discussion updates (`discussion.md`)

   **Format new entries** like this and insert at the TOP (after header/comments, before existing entries):

   ```markdown
   ---
   ## YYYY-MM-DD — [Short title]

   [Brief context — 1-2 sentences]

   **Обсъдени теми:**
   - [Topic 1]
   - [Topic 2]

   **Решения:**
   - [Decision 1]

   **Отворени въпроси:**
   - [Open question 1]
   ```

   Remove placeholder `*(Все още няма записи.)*` if present.

### Todo updates (`todo.md`)

   **Add new items:**
   ```
   - [ ] YYYY-MM-DD | PRIORITY | Description
   ```
   Priority: HIGH, MEDIUM (default), or LOW.

   **Complete items:** Change `- [ ]` to `- [x]`.

   Remove placeholder `*(Все още няма задачи.)*` if present.

### Status changes (`description.md`)

   **Complete the task:**
   - Change status from `В процес 🔄` to `Завършена ✅`
   - Update deliverables table statuses to `Done ✅`
   - Verify that all deliverables actually exist at their output paths

   **Pause the task:**
   - Change status to `Отложена ⏸️`
   - Add a note about why it was paused

4. **Write in Bulgarian**, keeping technical terms in their original English form.

5. **Confirm in Bulgarian** what was updated, including which files were modified and the current overall status.

## Rules

- Never delete existing checked items — they are part of the task history
- Discussion entries are always in reverse chronological order (newest first)
- When marking the task as complete, verify deliverables exist
- If a deliverable path changed during execution, update it in `description.md`
- Keep progress.md concise — don't add excessive detail to individual checklist items
- If the task doesn't have `discussion.md` or `todo.md` yet (older tasks), create them on first use
