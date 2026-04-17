# 07 — Test Plan

Документ за проследяване на тестове за всяка имплементация. Целта е всеки компонент да има поне минимален тест, който гарантира, че промените не чупят съществуваща функционалност.

---

## Принцип

Всяка нова feature или промяна трябва да има тест. Тестовете може да не се пишат веднага (в същата сесия), но **трябва да бъдат отбелязани тук** като pending, за да се направят в свободно време.

## Статус легенда

- **DONE** — тест съществува и минава
- **MANUAL** — тестван ръчно (ad-hoc скрипт или CLI), но няма автоматизиран тест
- **PENDING** — тест е необходим, но все още не е написан

---

## Engine (workflow-engine.py)

| Компонент | Какво тестваме | Статус | Бележки |
|-----------|---------------|--------|---------|
| `step_begin` — inline schema injection | Schema content се embed-ва в `outputs_text` | MANUAL | Ad-hoc Python test, 2026-04-03 |
| `step_begin` — format inference | `.json` → "JSON", `.yaml` → "YAML", `.md` → "Markdown" | PENDING | |
| `step_begin` — missing schema file | Graceful error когато schema файл не съществува | PENDING | |
| `step_begin` — glob expansion | `.agent/specs/**/*.md` → 59 конкретни paths | MANUAL | Ad-hoc Python test, 2026-04-03 |
| `list_agent_files` — basic | List files with path + pattern filter | MANUAL | Ad-hoc Python test, 2026-04-03 |
| `list_agent_files` — missing dir | Graceful error за несъществуваща директория | PENDING | |
| `step_complete` — inline validation | `subagent: false` + struct → validation преди completion | MANUAL | Ad-hoc Python test, 2026-04-03 |
| `step_complete` — FIX_AND_RETRY response | Error response с `validation_errors` при fail | PENDING | |
| `step_complete` — gate-aware skip | Не валидира когато gate-result.json показва pass за тази стъпка | PENDING | |
| `step_complete` — parallel step validation | Валидира когато gate-result.json липсва (parallel agents) | PENDING | |
| `step_begin` — stale gate-result cleanup | Изтрива gate-result.json преди нова стъпка | PENDING | |
| `workflow_init` | Manifest + trace creation | PENDING | |
| `workflow_resolve` | Find predefined vs my_workflows vs legacy | PENDING | |
| `workflow_resume` | Resume from existing manifest | PENDING | |
| `step_collect_result` | Read gate-result.json, action routing | PENDING | |
| `workflow_finalize` | Trace aggregates, manifest completion | PENDING | |

## Gate Scripts

| Компонент | Какво тестваме | Статус | Бележки |
|-----------|---------------|--------|---------|
| `gate-check.py` — structural validation | Valid output → exit 0, invalid → exit 2 | MANUAL | Ad-hoc subprocess test, 2026-04-03 |
| `gate-check.py` — host detection | `hook_event_name` → claude-code, без → cursor | PENDING | |
| `gate-check.py` — phantom filtering (Cursor) | `toolu_` prefix, empty task → skip | PENDING | |
| `gate-check.py` — retry limit | loop_count > max → exit 0 (stop) | MANUAL | Наблюдавано от invocations.log |
| `gate-check.py` — trace capture | Trace entry с checks/failures/details | PENDING | |
| `schema-validate.py` — JSON validation | Required fields, types, patterns, enums | PENDING | |
| `schema-validate.py` — Markdown validation | Frontmatter, required sections | PENDING | |
| `schema-validate.py` — custom format | `format: json` + `json_schema` style | PENDING | |

## Adapter: Claude Code

| Компонент | Какво тестваме | Статус | Бележки |
|-----------|---------------|--------|---------|
| SubagentStop hook | Hook fires за workflow-step agent | MANUAL | Verified 2026-04-02 |
| Exit 2 retry | Agent продължава при exit 2 | MANUAL | Verified 2026-04-02 |
| MCP server | Зарежда се, tools достъпни | MANUAL | Verified 2026-04-02 |
| AGENT.md workflow-step | Agent спазва schema instructions | DONE | probe-struct first-try pass, 2026-04-03 |
| file-guard.py PreToolUse | Protected paths blocked | PENDING | |

## Adapter: Cursor

| Компонент | Какво тестваме | Статус | Бележки |
|-----------|---------------|--------|---------|
| subagentStop hook | Hook fires, followup_message работи | MANUAL | Production tested |
| gate-check.py Cursor mode | JSON stdout, exit 0 | PENDING | |
| MCP server в Cursor | Зарежда се, tools достъпни | MANUAL | Production tested |

## End-to-End Workflows

| Workflow | Какво тестваме | Статус | Бележки |
|----------|---------------|--------|---------|
| `hook-diagnostic` (Claude Code) | 3 стъпки: probe-hook, probe-struct, probe-retry | DONE | 3/3 pass, 2026-04-03. probe-struct first-try (schema injection fix verified), probe-retry gate feedback loop verified |
| `hook-diagnostic` (Cursor) | Същите 3 стъпки | PENDING | |
| `doc-spec-extraction` (Cursor) | Реален workflow, 4+ стъпки | MANUAL | Multiple production runs |
| `spec-write-and-implement` | Delegation + gates | PENDING | |
| `spec-audit` | Read-only audit, 3 стъпки | MANUAL | Production tested |

---

## Бъдещо развитие

- [ ] Автоматизиран test runner (pytest или shell script)
- [ ] CI integration (при промяна на engine → run tests)
- [ ] Snapshot тестове за `step_begin` output format
- [ ] Mock workflow за пълен end-to-end тест без реален LLM
