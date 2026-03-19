# Discussion Log — italy_games

<!-- Записите са в обратен хронологичен ред (най-новите отгоре). -->
<!-- Технически термини остават на английски. -->

---
## 2026-03-04 — Анализ на платформената комуникация (Inspired vs Astro)

Създадени са 3 документа, описващи комуникацията между играта и двете VLT платформи в проекта italy_games. Целта е да се подготви ясна документация преди сертификацията на Astro интеграцията.

**Обсъдени теми:**
- Архитектурата на italy_games FSM (GameFsm → CommComponent → OGAPIWrapper) и разликите с проекта games (IGameflow → IKernelApi)
- AK2API протоколът на Astro — message-based модел с ca_*/ac_* съобщения, без heartbeat
- Inspired/OGAPI протоколът — callback-based модел с processCallbacks() и heartbeat на 15s
- Mapping между OGAPI calls и AK2API: 4 от 9 calls са симулирани в Astro (AskContinue, StartGameCycle, CommitStake, AwardWinnings)
- Recovery разлики: Inspired ползва memento файлове + gameCycleId, Astro ползва 8KB NVRAM + step_seq_acked
- Tax handling: Inspired получава OnTaxEvent от kernel, Astro изчислява локално
- Въведена е нова конвенция `tasks/` за проследяване на сложни задачи
- Езикът на документите: решено е всички нови ai_docs да бъдат на български с английски технически термини

**Решения:**
- Document 1 (`fsm-communication-architecture.md`) — FSM архитектура на italy_games, базирана на source code анализ
- Document 2 (`Astro-Game-Communication-Sequence.md`) — Astro/AK2API комуникационен протокол, базиран на Programming Guide v3.2 и source code
- Document 3 (`inspired-vs-astro-comparison.md`) — сравнителен анализ между двете платформи
- CLAUDE.md актуализирани: добавени `tasks/` конвенция и Inspired в Integrations таблицата на italy_games

**Отворени въпроси:**
- Дали Inspired интеграцията трябва да има собствена поддиректория (`inspired/`) подобно на `astro/`?
- Съществуващият `iKernel-Game-Communication-Sequence.md` е на английски — дали трябва да се пренапише на български за консистентност?
