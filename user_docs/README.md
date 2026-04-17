# Agentic Control Plane — User Documentation

Потребителска документация за Agentic Control Plane системата.
Предназначена за разработчици, които инсталират и ползват системата в своите проекти.

## Документи

| Документ | Описание |
|----------|----------|
| [01-overview.md](01-overview.md) | Какво е системата, архитектура, инсталация, файлова структура |
| [02-workflows.md](02-workflows.md) | Как се пишат и стартират workflows — YAML, params, gates, structs |
| [02b-workflow-tools-architecture.md](02b-workflow-tools-architecture.md) | Design rationale за workflow tools (Phase 38): per-step subagents, loader, история Phase 35→36→37→38 |
| [02c-claude-code-deep-dive.md](02c-claude-code-deep-dive.md) | Защо нашите CC решения изглеждат точно така: empirical findings, ограничения, alternatives отхвърлени |
| [03-spec-guard.md](03-spec-guard.md) | Spec система: triggers, flows, диаграми, reliability анализ |
| [04-tools.md](04-tools.md) | Trace Viewer и Workflow Editor — какво са, как се ползват |
| [05-changelog.md](05-changelog.md) | Хронология на архитектурните решения, групирани по фази |
| [06-claude-code-adapter.md](06-claude-code-adapter.md) | Claude Code adapter: Cursor vs Claude Code подход за всеки аспект, design decisions |
| [07-test-plan.md](07-test-plan.md) | Test plan: какво е тествано, какво чака, статус на всеки компонент |

## Свързани ресурси

- **Архитектурен дизайн** (development reference): `../agentic-control-plane-design.md`
- **LLM reference docs** (English): `../dist/.agent/docs/`
- **Cursor hook reference** (technical): `../cursor-hook-reference.md`
- **Claude Code official docs** (references): `../docs/claude-code-references.md`
- **Claude Code implementation plan**: `../docs/claude-code-implementation-plan.md`

## Конвенции

- Документите са на **български**, технически термини на English
- Диаграмите са Mermaid формат (render-ват се в GitHub, VS Code, etc.)
- Номерацията (01-, 02-) определя реда на четене
