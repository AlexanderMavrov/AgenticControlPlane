# 04 — Tools

Browser-based utilities в `.agent/tools/`. Отварят се директно в браузър, без dependencies.

---

## Trace Viewer

**Файл:** `.agent/tools/trace-viewer.html`

Визуализира workflow execution traces — какво се е случило, кога, с какъв резултат.

### Какво показва

- **Workflow card** — име, версия, статус, параметри като цветни badges, gate configuration, агрегирани статистики (duration, messages, tool calls)
- **Timeline bar** — пропорционални сегменти за стъпки, click за scroll
- **Step cards** (collapsible):
  - Step config chips (spec_check, subagent, gate overrides — dashed = override)
  - "inline" badge за `subagent: false` стъпки
  - Goal text от workflow.yaml
  - Inputs/outputs с inject modes и struct schemas
  - **Tool Calls** секция — per-step tool calls с source badge (script/mcp), аргументи, duration, output preview (click-to-expand)
  - Gate results с failure details
  - Invocation history с retry_type badges (gate retry / new subagent)
  - Modified files per invocation
  - Task prompt, summary, gate feedback (expandable)
- **Tool Calls (all steps)** panel — global overview на всички tool calls от tool server и MCP transcript
- **Timeline маркери** — tool calls показани като цветни точки (зелена=script, лилава=mcp), click → scroll до детайла
- **Dark/light theme** toggle

### Как се ползва

1. Отвори `trace-viewer.html` в браузър
2. Drag-and-drop `.trace.json` файл (от `workflows/<name>/trace/`)
3. Или click "Load" и избери файл
4. Разгледай стъпките, gate резултатите, retry историята

### Trace файлове

Живеят в `workflows/<name>/trace/<run-id>.trace.json`. Формат:

```json
{
  "workflow": "my-workflow",
  "run_id": "my-workflow-20260319-143022-b7e2",
  "status": "completed",
  "gate_config": { "structural": true, "semantic": true, "human": false },
  "params": { "component": "EditField" },
  "steps": [
    {
      "name": "clarify",
      "config": { "spec_check": false, "subagent": true },
      "goal": "Refine requirements...",
      "inputs": [...],
      "outputs": [...],
      "invocations": [
        {
          "iteration": 1,
          "retry_type": null,
          "duration_ms": 45000,
          "gate": { "passed": true, "checks": [...] }
        }
      ]
    }
  ]
}
```

---

## Workflow Editor

**Файл:** `.agent/tools/workflow-editor.html`

Визуален editor за `workflow.yaml` файлове. Позволява създаване и редактиране без ръчно писане на YAML.

### Какво може

- **Workflow tab:**
  - Metadata (name, version, description)
  - Runtime Parameters — inline single-row layout (name, description, required, default)
  - **Tools** — card layout per tool:
    - Type dropdown (script/mcp) с описания
    - Script: command, description, collapsible input_schema с "Template" бутон
    - MCP: required checkbox, info note за description, collapsible server_config
    - Hint текст за всяко поле
  - Gate Defaults — clickable chip toggles + inline retry inputs
  - Steps — collapsible cards с:
    - Step config chips (spec_check, subagent, carry_forward, gate overrides)
    - Goal textarea
    - Inputs/outputs (path, inject mode, struct)
    - Step tools — comma-separated tool names (пока��ва се само ако workflow-ът има tools)
    - Param bindings
    - Gate overrides с "Clear overrides" бутон
  - Drag-and-drop reorder на стъпки

- **Structs tab:**
  - Преглед и редакция на struct schemas
  - Auto-detect от workflow outputs

- **Toolbar:**
  - New / Load / Copy / Export / Export All / Preview / Dark
  - **Example** — зарежда демо workflow с всички feature-и

### Как се ползва

1. Отвори `workflow-editor.html` в браузър
2. Click "New" за нов workflow или "Load" за зареждане на съществуващ YAML
3. Click "Example" за демо workflow с всички настройки
4. Редактирай визуално — params, steps, gates, inputs/outputs
5. Click "Export" за YAML download или "Copy" за clipboard
6. Click "Preview" за YAML preview

### Help система

Всяка `?` иконка отваря **rich modal** с:
- Текстово обяснение
- SVG flowchart диаграма
- Интерактивни hover states

---

## Съвместимост

И двата инструмента:
- Работят в **всеки** модерен браузър (Chrome, Firefox, Safari, Edge)
- Нямат **нулеви** external dependencies
- Поддържат **dark/light** theme
- Синхронизирана цветова гама между тях
