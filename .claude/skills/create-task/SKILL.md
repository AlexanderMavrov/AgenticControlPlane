---
name: create-task
description: Create a structured task in the project tasks/ directory. Use for complex multi-document or analysis work that needs tracking.
---

# Skill: Create Task

## Triggers

- **Bulgarian**: "създай task", "нова задача", "създай задача в tasks"
- **English**: "create task", "new task", "track this as a task"

## Behavior

1. **Determine the target project** based on the user's context. Tasks live at project level: `projects/<project>/tasks/<task-name>/`. If the user doesn't specify a project, ask.

2. **Generate a short kebab-case name** for the task directory (e.g., `platform-communication-analysis`, `astro-certification-prep`).

3. **Create the task directory** with 4 files:

   ```
   tasks/<task-name>/
   ├── description.md
   ├── progress.md
   ├── discussion.md
   └── todo.md
   ```

4. **Create `description.md`:**

   ```markdown
   # [Заглавие на задачата]

   **Дата:** YYYY-MM-DD
   **Статус:** В процес 🔄

   ---

   ## Контекст

   [Какъв е проблемът/нуждата — 2-3 параграфа с достатъчно контекст,
   за да може друга AI сесия да разбере задачата без допълнителни въпроси]

   ## Цел

   [Какво трябва да се постигне — bullet points]

   ## Deliverables

   | # | Документ | Output | Описание | Статус |
   |---|----------|--------|----------|--------|
   | 1 | ...      | `ai_docs/...` | ... | Pending |

   ## Изисквания

   [Per-deliverable изисквания, ако има]

   ## Референтни документи

   | Документ | Роля |
   |----------|------|
   | ...      | ...  |

   ## Key source code files

   | Файл | Роля |
   |------|------|
   | ...  | ...  |
   ```

5. **Create `progress.md`:**

   ```markdown
   # Прогрес: [Заглавие]

   **Последна актуализация:** YYYY-MM-DD

   ---

   ## Фаза 0: Инфраструктура
   - [x] Създаване на task директория
   - [x] Създаване на description.md
   - [x] Създаване на progress.md

   ## Фаза 1: Research
   - [ ] [Конкретни стъпки...]

   ## Фаза 2: Изпълнение
   - [ ] [Конкретни стъпки...]
   ```

6. **Create `discussion.md`:**

   ```markdown
   # Дискусия: [Заглавие]

   <!-- Записите са в обратен хронологичен ред (най-новите отгоре). -->
   <!-- Технически термини остават на английски. -->

   *(Все още няма записи.)*
   ```

7. **Create `todo.md`:**

   ```markdown
   # TODO: [Заглавие]

   *(Все още няма задачи.)*
   ```

8. **Populate all files** using context from the user's request. Don't leave empty placeholders in description.md — fill in what's known, omit sections that don't apply.

9. **Write in Bulgarian**, keeping technical terms in their original English form.

10. **Confirm in Bulgarian** what was created, including the full path and a brief summary.

## Rules

- Deliverables go into `ai_docs/` (or other appropriate locations), NOT into the task directory itself
- The task directory only contains tracking files: `description.md`, `progress.md`, `discussion.md`, `todo.md`
- Status values for description.md: `В процес 🔄`, `Завършена ✅`, `Отложена ⏸️`
- Phase structure in progress.md is flexible — adapt to the specific task
- If no deliverables are clear yet, use a simplified description.md without the Deliverables table
- If no source code files are relevant, omit the "Key source code files" section
