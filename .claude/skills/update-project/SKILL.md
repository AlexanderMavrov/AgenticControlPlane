---
name: update-project
description: Update project-level discussion or todo. Use for cross-cutting topics that don't belong to a specific task — project-wide decisions, conventions, architectural notes.
---

# Skill: Update Project

## Triggers

- **Bulgarian**: "запиши в проектната дискусия", "добави project todo", "логни на проектно ниво"
- **English**: "add project discussion", "project todo", "log at project level"

## Behavior

1. **Determine the target level** based on the user's context:
   - **Cross-project**: `projects/discussion.md` or `projects/todo.md`
   - **Per-project**: `projects/<project>/discussion.md` or `projects/<project>/todo.md`
   - **Per-integration**: `projects/<project>/<integration>/discussion.md` or `todo.md`

   If not clear from context, ask the user.

2. **Determine what to update:**

### Discussion (`discussion.md`)

   If the user gives a **specific point** — log it as a single entry.
   If the user asks to **"summarize our discussion"** — create a structured summary.

   **Format** and insert at the TOP (after header/comments, before existing entries):

   ```markdown
   ---
   ## YYYY-MM-DD — [Short title]

   [Brief context — 1-2 sentences]

   **Обсъдени теми:**
   - [Topic 1]

   **Решения:**
   - [Decision 1]

   **Отворени въпроси:**
   - [Open question 1]
   ```

   Remove placeholder `*(Все още няма записи.)*` if present.

### Todo (`todo.md`)

   **Add items:**
   ```
   - [ ] YYYY-MM-DD | PRIORITY | Description
   ```
   Priority: HIGH, MEDIUM (default), or LOW.

   **Complete items:** Change `- [ ]` to `- [x]`.

   Remove placeholder `*(Все още няма задачи.)*` if present.

3. **Write in Bulgarian**, keeping technical terms in their original English form.

4. **Confirm in Bulgarian** what was logged, including the file path and a brief summary.

## When to use project-level vs task-level

- **Project-level**: decisions that affect the whole project (e.g., "всички ai_docs на български"), architectural conventions, cross-task notes
- **Task-level**: everything specific to the task being worked on — use `update-task` instead
- **Rule of thumb**: if it only matters within the current task, it's task-level
