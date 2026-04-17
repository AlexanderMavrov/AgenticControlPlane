# Дискусия: Visual QA

<!-- Записите са в обратен хронологичен ред (най-новите отгоре). -->

---

### 2026-04-16 — Инициализация и архитектурни решения

**Контекст:** Потребителят клонира игра чрез game-creator workflow-а. Играта работи, но има визуални бъгове (разместени ресурси). Необходим е tool за визуално тестване.

#### Ключови решения

1. **Standalone tool, не само за клонирани игри** — трябва да работи за ВСЯКА Alpha Family игра с визуални проблеми

2. **LLM vision-based подход** — моделът изгражда "mental model" от config/resource файлове и сравнява с реални screenshots. Не pixel diff, а семантичен анализ.

3. **Reference screenshot от друга игра — полезен** — показва на LLM-а layout структурата на Alpha Family (reel grid, UI позиции, spacing). Label-ва се като "структурен reference", не като "така трябва да изглежда".

4. **LLM-ът трябва да разбира и кода** — при намерен проблем, да може да проследи root cause и да го оправи в source файловете

5. **HTML tool за input collection** — събира paths, screenshots, генерира config JSON за workflow-а. Същият pattern като game-creator.html → config.json → workflow.

6. **Screenshots подадени от потребителя** — за v1 потребителят прави screenshots ръчно (през playground). Автоматизация на capture е за бъдеща версия.

#### Подход за валидация (PoC)

Преди да строим пълен workflow, валидираме ръчно:
- Потребителят подава screenshots + resource paths
- LLM анализира директно в conversation
- Оценяваме колко добре vision detection работи

---

### 2026-04-16 — PoC резултати и промяна на подхода

**Контекст:** Тестване с burning_hot_coins — 7 injected бъга в view JSON файловете.

#### Vision detection scorecard

| Bug | Тип | Vision засече? |
|-----|-----|---------------|
| Panel y offset (10px) | Position | Не |
| Knob asymmetry (50px) | Position | Не |
| Green credit text | Color | Да (с hint) |
| Background alpha:140 | Alpha | Частично (видя цвят, грешна причина) |
| Displaced status text | Position | Не |
| Label scale deformation | Scale | Да (с hint) |
| Warm tint (255,240,220) | Color | Не |

**Резултат:** 2/7 самостоятелно. Vision е ненадежден за position shifts, alpha аномалии, субтилни цветови разлики.

#### Ключов извод: static analysis е primary

Всичките 7 бъга са промени в JSON view файлове (позиции, цветове, alpha, scale). Static analysis на JSON стойностите е детерминистичен и хваща 100% от тях.

**Решение:** Подходът е hybrid — static analysis (primary) + vision (secondary confirmation).

#### Rule extraction подход: без прототип

Потребителят изрично поиска tool-ът да работи за ВСЯКА игра, не само клонирани. Затова вместо сравнение с прототип, извличаме generic правила от reference игри.

**Избран подход:** LLM анализира view JSON-ите на 1-2 reference игри и извлича patterns/правила за "нормална" Alpha Family игра. Извлечени 50+ правила от burning_hot_coins, организирани по визуален елемент (A-O секции).

---

### 2026-04-16 — Workflow design

**Контекст:** Design на 4-step workflow за visual QA.

#### Архитектура

4 стъпки:
1. `gather-game-model` — чете ВСИЧКИ resource файлове, изгражда structured model
2. `static-analysis` — прилага 50+ правила, генерира findings report
3. `visual-validation` — conditional (ако има screenshots), LLM vision потвърждава findings
4. `fix-issues` — предлага и прилага fixes, gate: human: true

#### Ключови решения

- **Step 3 е conditional** — screenshots са optional. Static analysis работи без тях.
- **Step 4 има human gate** — fixes не се прилагат автоматично (освен при autoFix: true)
- **Rules са в отделен файл** (`visual-qa-rules.md`) — inject-ва се като context в workflow-а
- **Config schema** поддържа skipRules/onlyRules за selective проверка
- **HTML input collector** е Phase 2 deliverable — за сега config-ът се пише ръчно
