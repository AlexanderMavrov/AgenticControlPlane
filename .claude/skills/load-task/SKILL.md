---
name: load-task
description: Load context for an existing task — read description, progress, discussion, todo, and optionally referenced documents. Use at the start of a new session to resume work on a task.
---

# Skill: Load Task

## Triggers

- **Bulgarian**: "зареди task", "продължи задачата", "зареди контекста", "върни се към задачата"
- **English**: "load task", "resume task", "continue task", "pick up task"

## Behavior

1. **Identify the task** to load. Look for tasks in `projects/<project>/tasks/`. If the user specifies a task name, use it. If not, list available tasks with their statuses and ask which one.

2. **Read all task files** in order:
   - `description.md` — scope, deliverables, requirements, references
   - `progress.md` — what's done, what remains
   - `discussion.md` — past decisions and open questions
   - `todo.md` — pending action items

3. **Summarize the task state in Bulgarian:**

   ```
   ## Зареден task: [Заглавие]

   **Статус:** [В процес 🔄 / Завършена ✅ / Отложена ⏸️]

   **Завършено:**
   - [Completed phases/items — brief]

   **Остава:**
   - [Remaining phases/items — brief]

   **Отворени въпроси:**
   - [From discussion.md, if any]

   **Pending TODOs:**
   - [From todo.md, if any]
   ```

4. **Optionally read referenced documents** if the user asks to "deep load" or if the remaining work clearly requires it. Referenced documents are listed in `description.md` under "Референтни документи" and "Key source code files". Do NOT read them by default — only when:
   - The user explicitly asks ("зареди всичко", "deep load", "прочети и документите")
   - The next pending phase requires knowledge from those documents

5. **After summary, ask** what the user wants to work on next, suggesting the first incomplete item from `progress.md`.

## Rules

- This is a **read-only** skill — it does not modify any files
- Keep the summary concise — the user wants quick orientation, not a wall of text
- If a task has no `discussion.md` or `todo.md` (older task), note this but don't fail
- If deliverables exist at their output paths, mention this in the summary
