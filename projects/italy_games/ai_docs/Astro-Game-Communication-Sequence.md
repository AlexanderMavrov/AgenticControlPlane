# Astro-Game Communication Sequence

**Базиран на:** Astro Game Development Kits - Programming Guide v3.2 (AK2API 1.8.7)
**Source code:** `C:/mklinks/italy_games_sisal_r1/integrations/Astro/`

> **Забележка:** Този документ описва комуникацията между играта и AstroKernel чрез AK2API.
> За сравнение с Inspired/iKernel комуникацията, виж `iKernel-Game-Communication-Sequence.md`.
> За обща FSM архитектура на italy_games, виж `fsm-communication-architecture.md`.

---

## Съдържание

1. [Обзор](#1-обзор)
2. [Post-Initialization State](#2-post-initialization-state)
3. [Main Game Loop](#3-main-game-loop)
4. [Game Cycle — Основен поток (без печалба)](#4-game-cycle--основен-поток-без-печалба)
5. [Game Cycle — С печалба](#5-game-cycle--с-печалба)
6. [Game Cycle — С Features (Free/Bonus Spins)](#6-game-cycle--с-features-freebonus-spins)
7. [Game Cycle — С Gamble](#7-game-cycle--с-gamble)
8. [Event Handling (Suspend/Resume/Terminate)](#8-event-handling-suspendresumeterminate)
9. [Tax Handling](#9-tax-handling)
10. [Responsible Gaming](#10-responsible-gaming)
11. [Recovery Flow](#11-recovery-flow)
12. [Shutdown / Exit Codes](#12-shutdown--exit-codes)
13. [Outcome Detail Format](#13-outcome-detail-format)
14. [AK2API Message Reference](#14-ak2api-message-reference)

---

## 1. Обзор

```
+------------------+                           +------------------+
|      GAME        |  <-- AK2API (so/dll) -->  |   AstroKernel    |
+------------------+                           +------------------+
        |                                               |
        |  1. Комуникацията е MESSAGE-BASED             |
        |  2. Играта ИЗПРАЩА съобщения (ca_*)           |
        |  3. Kernel-ът ОТГОВАРЯ с (ac_*)               |
        |  4. Съобщенията се получават чрез              |
        |     ak2api_check_message() в main loop        |
        |  5. НЯМА heartbeat (за разлика от Inspired)   |
        |                                               |
```

**Критични правила:**
- Комуникацията е **message-based**, не callback-based (за разлика от Inspired/OGAPI)
- Играта извиква `ak2api_check_message()` всеки frame за получаване на съобщения
- **Няма heartbeat** — не е нужно периодично ping-ване на kernel
- Random числа: максимум **63 числа** на заявка
- Outcome description: максимум **199 символа** + null terminator
- NVRAM: **8KB** за game state persistence
- RNG retry: 3 опита с 500ms интервал при timeout

### Имплементационна верига

В source code на italy_games, Astro комуникацията преминава през няколко слоя:

```
┌──────────────────────────────────────────────────────────────────────┐
│ GameFsm → CommComponent → OGAPIWrapperAstro → IAstroEgtApi/AstroEgt │
│                                                     ↓               │
│                                              AK2API messages        │
│                                              (ca_* / ac_*)         │
└──────────────────────────────────────────────────────────────────────┘
```

Mapping между OGAPIWrapper calls и AK2API messages:

| OGAPIWrapper Call | IKernelApi Method | AK2API Message |
|-------------------|-------------------|----------------|
| `ReserveStakeRequest()` | `RequestStartMatch(bet)` | `ca_game_start` |
| `RngNumbersRequest()` | `RequestRandoms(count, max)` | `ca_rng_request` |
| `SetCheckpointRequest()` | `RequestRoundOutcome(win, desc)` | `ca_game_step` |
| `EndGameCycleRequest()` | `RequestEndMatch(win, desc)` | `ca_game_end` |
| `CashoutRequest()` | `RequestCashout()` | `ca_credit_payout` |
| `AskContinueRequest()` | *(симулирано локално)* | — |
| `StartGameCycleRequest()` | *(симулирано локално)* | — |
| `CommitStakeRequest()` | *(симулирано локално)* | — |
| `AwardWinningsRequest()` | *(симулирано локално)* | — |

> **Важно:** AskContinue, StartGameCycle, CommitStake и AwardWinnings са **симулирани** в OGAPIWrapperAstro — не изпращат реални AK2API съобщения. Те съществуват само за съвместимост с OGAPIWrapper интерфейса.

---

## 2. Post-Initialization State

```
+==============================================================================+
|                         ИНИЦИАЛИЗАЦИЯ НА ASTRO ИГРАТА                        |
+==============================================================================+

    [ Стартиране на процеса ]
                |
                v
    +---------------------------------------+
    | 1. ak2api_init()                      |
    |    Инициализира AK2API библиотеката   |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 2. ak2api_init_until_complete()       |
    |    Цикъл: изчаква пълна init          |
    |    (workaround: винаги retry)         |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 3. ak2api_cfg_get_item()              |
    |    Чете конфигурация:                 |
    |    - Tax limits и проценти            |
    |    - Max win                          |
    |    - Game properties                  |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 4. ak2api_nvbuf_get_buffer()          |
    |    Взема 8KB NVRAM буфер              |
    |    (за game state persistence)        |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 5. Създаване на game обекти:          |
    |    - IAstroEgtApi                     |
    |    - OGAPIWrapperAstro                |
    |    - GameBase (конкретна игра)        |
    |    - GameFsm + CommComponent          |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 6. ca_flow_start                      |
    |    Съобщение към kernel: "играта      |
    |    е готова за работа"                |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 7. ac_credit_changed                  |
    |    Kernel изпраща начален кредит      |
    +---------------------------------------+
                |
                v
    +---------------------------------------+
    | 8. Изчакване 3 frames                 |
    |    (recovery startup delay —          |
    |     дава време на framework-а)        |
    +---------------------------------------+
                |
                v
           [ IDLE STATE ]
           (готов за игра)
```

**Key file:** `AstroMain.h` — `integrations/Astro/libs/src/Egt/AstroIntegration/AstroMain.h`

---

## 3. Main Game Loop

```
                         +------------------+
                         |   GAME RUNNING   |
                         +------------------+
                                  |
                                  v
            +---------------------------------------------+
            |            MAIN LOOP (всеки frame)          |
            +---------------------------------------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
         v                        v                        v
+------------------+   +--------------------+   +------------------+
| StartMainLoopTick|   | game.Update(dt)    |   | EndMainLoopTick  |
| (AstroEgt)       |   |                    |   | (AstroEgt)       |
+------------------+   +--------------------+   +------------------+
         |                        |                        |
         v                        v                        v
+------------------+   +--------------------+   +------------------+
| 1. SyncNvram()   |   | FSM state updates  |   | 1. Save NVRAM    |
| 2. Download msgs |   | Scene rendering    |   |    (ако е dirty) |
| 3. Process ac_*  |   | Input handling     |   | 2. Send pending  |
|    messages      |   | Animation updates  |   |    ca_* message  |
| 4. RNG retries   |   |                    |   |                  |
+------------------+   +--------------------+   +------------------+
         |                                                 |
         v                                                 v
+------------------+                            +------------------+
| Handle:          |                            | Pending messages:|
| - ac_game_start  |                            | - ca_game_start  |
| - ac_rng_result  |                            | - ca_game_step   |
| - ac_game_step   |                            | - ca_game_end    |
| - ac_game_end    |                            | (само 1 наведнъж)|
| - ac_credit_chg  |                            +------------------+
| - ac_flow_*      |
| - ac_key_*       |
| - ac_touch_*     |
+------------------+
```

**Разлика от Inspired:**
- Inspired изисква `processCallbacks()` всеки frame + `heartbeat()` на 15 секунди
- Astro изисква само `ak2api_check_message()` — по-прост model

**Key file:** `AstroEgt.cpp` линии 241-277 — `integrations/Astro/libs/src/Egt/AstroEgt/AstroEgt.cpp`

---

## 4. Game Cycle — Основен поток (без печалба)

```
+==============================================================================+
|                    ОСНОВЕН GAME CYCLE (Без печалба)                          |
+==============================================================================+

    [ IDLE STATE — Чакане за играч ]
                    |
                    | (Играч натиска START)
                    |
                    | [OGAPIWrapperAstro симулира AskContinue + StartGameCycle]
                    v
    +---------------------------------------+
    | 1. ca_game_start                      |
    |    (изпратено от RequestStartMatch)    |
    |                                       |
    |    Данни:                             |
    |    - bet_ce: залог в центове          |
    |    - bool_max_bet: 1 ако е max bet    |
    |                                       |
    |    State update:                      |
    |    - gameStepSeq = 0                  |
    |    - matchName = name                 |
    |    - matchInitialBet = bet            |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 2. ac_game_start_acked                |
    |    (отговор от AstroKernel)           |
    |                                       |
    |    bool_enabled:                      |
    |    - true  → играта е одобрена        |
    |    - false → недостатъчен кредит      |
    |              или друга забрана        |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
    [enabled=true]     [enabled=false]
           |                 |
           v                 v
           |          +------------------+
           |          | Отказ — връщане  |
           |          | към Idle         |
           |          +------------------+
           |
           | [OnCreditChangedEvent — кредит намалява]
           | [Стартира "fake" анимация — барабани се въртят]
           v
    +---------------------------------------+
    | 3. ca_rng_request                     |
    |    (изпратено от RequestRandoms)      |
    |                                       |
    |    Данни:                             |
    |    - count: брой random числа         |
    |      (максимум 63 на заявка)          |
    |                                       |
    |    Retry logic:                       |
    |    - Timeout: 500ms на опит           |
    |    - Максимум 3 опита                 |
    |    - При пълен timeout → exit code 11 |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]        [timeout / error]
           |                 |
           v                 v
           |          +------------------+
           |          | Exit code 11:    |
           |          | "RNG timeout"    |
           |          | Bet се връща     |
           |          | автоматично      |
           |          +------------------+
           |
    +---------------------------------------+
    | 4. ac_rng_result                      |
    |    (отговор от AstroKernel)           |
    |                                       |
    |    Данни:                             |
    |    - count: брой получени числа       |
    |    - random_nums[]: масив от числа    |
    |                                       |
    |    Конвертиране:                      |
    |    Raw RNG [0, 2^31-1] →              |
    |    Game range [min, max]:             |
    |    result = (number % (max-min)) + min|
    +---------------------------------------+
                    |
                    | (Изчисляване на game outcome)
                    | (Спиране на барабани)
                    v
    +---------------------------------------+
    | 5. ca_game_step                       |
    |    (изпратено от RequestRoundOutcome)  |
    |                                       |
    |    Данни:                             |
    |    - seq: gameStepSeq (за recovery)   |
    |    - outcome_won_ce: 0 (без печалба)  |
    |    - result: outcome description      |
    |      (напр. "RN:45,12|MG|STK:50|     |
    |       WIN:0|...")                     |
    |                                       |
    |    State update:                      |
    |    - gameStepSeq++ (инкрементира)     |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 6. ac_game_step_acked                 |
    |    (потвърждение от kernel)            |
    +---------------------------------------+
                    |
                    | (Показване на резултат — без печалба)
                    v
    +---------------------------------------+
    | 7. ca_game_end                        |
    |    (изпратено от RequestEndMatch)      |
    |                                       |
    |    Данни:                             |
    |    - won_ce: 0 (обща печалба)         |
    |    - result: summary description      |
    |      (напр. "END|STK:50|WIN:0|...")   |
    |                                       |
    |    State update:                      |
    |    - gameStepSeq = -1 (sentinel)      |
    |    - matchName.clear()                |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 8. ac_game_end_acked                  |
    |    (потвърждение от kernel)            |
    |                                       |
    |    Данни:                             |
    |    - net_won_ce: нетна печалба        |
    |      (след данъци)                    |
    +---------------------------------------+
                    |
                    | [OGAPIWrapper изпраща ca_game_snapshot]
                    | [OGAPIWrapper симулира AskContinue]
                    v
              [ IDLE STATE ]
              (готов за нов цикъл)
```

---

## 5. Game Cycle — С печалба

Потокът е идентичен до стъпка 5, но с разлики:

```
    ... (стъпки 1-4 идентични) ...
                    |
                    v
    +---------------------------------------+
    | 5. ca_game_step                       |
    |    - outcome_won_ce: > 0 (печалба!)   |
    |    - result: "RN:45,12|MG|STK:50|     |
    |      WIN:200|..."                     |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 6. ac_game_step_acked                 |
    +---------------------------------------+
                    |
                    | (Показване на печалба анимация)
                    | (OGAPIWrapper симулира AwardWinnings)
                    v
    +---------------------------------------+
    | 7. ca_game_end                        |
    |    - won_ce: 200 (обща печалба)       |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 8. ac_game_end_acked                  |
    |    - net_won_ce: печалба след данъци  |
    +---------------------------------------+
                    |
                    | ac_credit_changed (кредит нараства)
                    | [Може: OnTaxEvent ако win > праг]
                    v
              [ IDLE STATE ]
```

> **Важно:** В Astro, `AwardWinnings` е **симулирано** — кредитът се актуализира
> автоматично от kernel при `ac_game_end_acked`. В Inspired, `AwardWinnings`
> е реален OGAPI call.

---

## 6. Game Cycle — С Features (Free/Bonus Spins)

```
+==============================================================================+
|                    GAME CYCLE С FEATURES (Free Spins)                        |
+==============================================================================+

    ... (стъпки 1-4: game start + RNG за main spin) ...
                    |
    [Main spin показва feature trigger]
                    |
                    v
    +---------------------------------------+
    | 5. ca_game_step (PRIMARY phase)       |
    |    - seq: 1                           |
    |    - outcome_won_ce: 0                |
    |    - result: "RN:...|MG|STK:50|      |
    |      WIN:0|FEATURE:FG:10"            |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 6. ac_game_step_acked                 |
    +---------------------------------------+
                    |
                    v
          +------------------+
          | FREE GAMES LOOP  |
          | (10 free spins)  |
          +------------------+
                    |
         (за всеки free spin:)
                    |
                    v
    +---------------------------------------+
    | 7. ca_rng_request                     |
    |    (RNG за free spin N)               |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 8. ac_rng_result                      |
    +---------------------------------------+
                    |
                    | (Изчислява free spin резултат)
                    v
    +---------------------------------------+
    | 9. ca_game_step (FREE_GAMES phase)    |
    |    - seq: 2, 3, 4, ... (инкрементира) |
    |    - outcome_won_ce: win от този spin |
    |    - result: "RN:...|FG|VSTK:0|      |
    |      WIN:50|..."                     |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 10. ac_game_step_acked                |
    +---------------------------------------+
                    |
          [Повтори за всеки free spin]
                    |
                    v
    +---------------------------------------+
    | 11. ca_game_end                       |
    |    - won_ce: обща печалба от всички   |
    |      rounds                           |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 12. ac_game_end_acked                 |
    +---------------------------------------+
                    |
                    v
              [ IDLE STATE ]
```

> **Ключова разлика от Inspired:**
> В Inspired, всеки round изисква отделен `SetCheckpoint` call.
> В Astro, всеки round е отделен `ca_game_step` с инкрементиращ `seq` номер.
> Sequence номерът е критичен за **recovery** — kernel знае кой step е последно потвърден.

---

## 7. Game Cycle — С Gamble

```
+==============================================================================+
|                    GAME CYCLE С GAMBLE                                       |
+==============================================================================+

    ... (стъпки 1-6: main spin с печалба) ...
                    |
    [Играч избира GAMBLE]
                    |
                    v
    +---------------------------------------+
    | 7. ca_rng_request                     |
    |    (1 число за gamble: Red/Black)      |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 8. ac_rng_result                      |
    +---------------------------------------+
                    |
                    | (Изчислява gamble резултат)
                    v
    +---------------------------------------+
    | 9. ca_game_step (GAMBLE phase)        |
    |    - seq: (инкрементиран)             |
    |    - outcome_won_ce: doubled or 0     |
    |    - result: "RN:2|RG|VSTK:200|      |
    |      WIN:400|..."                    |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 10. ac_game_step_acked                |
    +---------------------------------------+
                    |
         +----------+----------+
         |                     |
    [WIN → ново gamble?]  [LOSE → край]
         |                     |
         v                     v
    (loop back to 7)    +------------------+
                        | ca_game_end      |
                        | won_ce: 0        |
                        +------------------+

    [COLLECT или max gamble опити:]
         |
         v
    +---------------------------------------+
    | 11. ca_game_end                       |
    |    - won_ce: финална печалба          |
    +---------------------------------------+
                    |
                    v
              [ IDLE STATE ]
```

---

## 8. Event Handling (Suspend/Resume/Terminate)

### Suspend (ac_flow_suspend)

Kernel може да поиска временно спиране на играта (напр. при responsible gaming проверка).

```
    [ GAME RUNNING ]
           |
           v
    +---------------------------+
    | ac_flow_suspend           |
    | → m_isSuspended = true    |
    | → Играта блокира всички  |
    |   game cycle операции     |
    | → Продължава rendering    |
    +---------------------------+
           |
           v
    [ GAME SUSPENDED ]
    (чака ac_flow_resume)
           |
           v
    +---------------------------+
    | ac_flow_resume            |
    | → m_isSuspended = false   |
    | → Играта продължава       |
    +---------------------------+
           |
           v
    [ GAME RUNNING ]
```

### Terminate (ac_flow_terminate)

```
    [ GAME RUNNING ]
           |
           v
    +---------------------------+
    | ac_flow_terminate         |
    | → terminateRequested.Post |
    | → Играта трябва да       |
    |   завърши gracefully      |
    +---------------------------+
           |
           v
    [ SHUTDOWN SEQUENCE ]
```

---

## 9. Tax Handling

В Astro имплементацията, данъчното изчисление се прави **локално** в OGAPIWrapperAstro (не от kernel):

```
    [ AwardWinnings ]
           |
           v
    +---------------------------+
    | Проверка: win > tax limit?|
    +---------------------------+
           |
      +----+----+
      |         |
    [ДА]      [НЕ]
      |         |
      v         v
    +------------------+     (продължава нормално)
    | Изчисление:      |
    | taxable = win -  |
    |   threshold      |
    | taxAmount =      |
    |   taxable * %    |
    | Форматиране на   |
    | tax съобщение    |
    +------------------+
           |
           v
    +------------------+
    | onTaxEvent(msg)  |
    | → OnTaxWin event |
    | → ShowTaxSplash  |
    +------------------+
```

> **Разлика от Inspired:** В Inspired, `OnTaxEvent` идва от iKernel (external).
> В Astro, tax се изчислява локално на базата на конфигурация четена при init.

**Key file:** `OGAPIWrapperAstro.cpp` линии 729-750

---

## 10. Responsible Gaming

AstroKernel управлява responsible gaming чрез:

- **ac_flow_suspend** — при breach на лимити
- **Gaming limits** — OGAPIWrapperAstro проверява `onBreachLimits` callback
- Играта показва `TimeAmountLimitsState` с оставащо време/сума

---

## 11. Recovery Flow

Astro използва фундаментално различен recovery модел от Inspired.

### NVRAM-базиран Recovery

```
+==============================================================================+
|                         ASTRO RECOVERY FLOW                                  |
+==============================================================================+

    [ Играта се рестартира след crash/power loss ]
                    |
                    v
    +---------------------------------------+
    | 1. ak2api_init()                      |
    | 2. ak2api_nvbuf_get_buffer()          |
    |    → Чете 8KB NVRAM                   |
    |    → Съдържа persisted game state     |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 3. Проверка на AstroEgt state:        |
    |    - gameStepSeq стойност             |
    |    - matchName (празно = не беше      |
    |      в match)                         |
    |    - pendingMsg (незавършено           |
    |      съобщение)                       |
    +---------------------------------------+
                    |
         +----------+----------+----------+
         |          |          |          |
    [seq=0,       [seq>0]    [seq=-1]   [no match]
     pending                              |
     game_start]                          v
         |          |                (нормален старт)
         v          v
    +---------+ +---------+
    | Изчакай | | Провери |
    | 3 frames| | step_   |
    | + resend| | seq_    |
    | pending | | acked   |
    +---------+ +---------+
                    |
         +----------+----------+
         |                     |
    [acked == seq]       [acked == seq-1]
    (вече потвърден)     (не е потвърден)
         |                     |
         v                     v
    +---------+         +---------+
    | Емулирай|         | Изпрати |
    | acked   |         | отново  |
    | response|         | pending |
    +---------+         | message |
                        +---------+
```

### Recovery по step_seq_acked

| gameStepSeq | step_seq_acked | Действие |
|-------------|----------------|----------|
| 0 | 0 | Match не е започнал → изчисти state, нов старт |
| 1+ | == seq | Step вече потвърден → емулирай acked |
| 1+ | == seq-1 | Step изпратен, но не потвърден → resend |
| -1 | — | Match вече завършен → емулирай end acked |

### Pending Message Management

Само **3 типа** съобщения могат да бъдат pending (незавършени):

1. `ca_game_start` — match е заявен, но не потвърден
2. `ca_game_step` — round outcome е изпратен, но не потвърден
3. `ca_game_end` — match end е изпратен, но не потвърден

Pending message се записва в NVRAM преди изпращане и се изчиства след получаване на acked.

> **Разлика от Inspired:**
> Inspired: Memento файлове + gameCycleId → `StartGameCycle(previousId)` за recovery
> Astro: NVRAM + step_seq_acked → автоматично resend на pending messages

**Key file:** `AstroEgt.cpp` линии 610-693

---

## 12. Shutdown / Exit Codes

Astro дефинира специфични exit codes за различни сценарии:

| Exit Code | Описание | Поведение |
|-----------|----------|-----------|
| 0 | Нормален изход | Играта завършва gracefully |
| 11 | RNG timeout | Bet се връща автоматично от kernel |
| 12 | Комуникационна грешка | Kernel обработва recovery |
| 13 | NVRAM корупция | Kernel нулира game state |
| 14 | Init грешка | Kernel рестартира играта |
| 19 | Некритична грешка | Играта се рестартира |
| 20 | Критична грешка | Kernel спира играта |

### Exit Code 11 (RNG Timeout) — специален случай

```
    [ RNG Request ]
           |
    (500ms × 3 опита без отговор)
           |
           v
    +---------------------------+
    | Exit code 11              |
    | → Kernel автоматично      |
    |   връща bet-а             |
    | → Играта се рестартира    |
    | → Кредитът е непроменен   |
    +---------------------------+
```

> **Разлика от Inspired:** В Inspired, при RNG грешка играта показва error message
> за 5 секунди на италиански ("Il terminale ha fallito la connessione al server RNG...")
> и излиза без EndGameCycle. В Astro, exit code 11 автоматично обработва ситуацията.

---

## 13. Outcome Detail Format

Всеки `ca_game_step` и `ca_game_end` включва `result` string с outcome description.

### Формат

Pipe-delimited string, максимум 199 символа:

```
RN:<random_numbers>|<game_type>|STK:<stake>|WIN:<win>|<details>
```

### Полета

| Поле | Описание | Примери |
|------|----------|---------|
| `RN:` | Random числа (comma-separated) | `RN:45,12,78` |
| Game type | Тип на round-а | `MG` (main), `FG` (free), `RG` (risk/gamble), `EG` (energy/bonus) |
| `STK:` | Реален stake (real money) | `STK:50` |
| `VSTK:` | Виртуален stake (от печалба) | `VSTK:200` |
| `WIN:` | Печалба от round-а | `WIN:100` |
| Details | Допълнителна информация | Символи, линии, множители |

### Примери

**Main game без печалба:**
```
RN:45,12,78,33,90|MG|STK:50|WIN:0
```

**Main game с печалба:**
```
RN:45,12,78,33,90|MG|STK:50|WIN:200
```

**Free spin:**
```
RN:23,67|FG|VSTK:0|WIN:50
```

**Gamble round (печалба):**
```
RN:2|RG|VSTK:200|WIN:400
```

**Game end summary:**
```
END|STK:50|WIN:650
```

**Key file:** `GameRoundHelper.cpp` — `integrations/Astro/libs/src/Egt/AstroIntegration/GameRoundHelper.cpp`

---

## 14. AK2API Message Reference

### Съобщения Game → Kernel (ca_*)

| Съобщение | Полета | Описание |
|-----------|--------|----------|
| `ca_flow_start` | — | Играта е инициализирана и готова |
| `ca_game_start` | `bet_ce`, `bool_max_bet` | Започни match с даден залог |
| `ca_rng_request` | `count` | Заяви random числа (max 63) |
| `ca_game_step` | `seq`, `outcome_won_ce`, `result[200]` | Отчети round outcome |
| `ca_game_end` | `won_ce`, `result[200]` | Завърши match |
| `ca_game_snapshot` | `monitor` | Направи screenshot |
| `ca_credit_payout` | — | Заяви cashout/ticket print |

### Съобщения Kernel → Game (ac_*)

| Съобщение | Полета | Описание |
|-----------|--------|----------|
| `ac_game_start_acked` | `bool_enabled` | Match одобрен/отказан |
| `ac_rng_result` | `count`, `random_nums[]` | Random числа |
| `ac_game_step_acked` | — | Step потвърден |
| `ac_game_end_acked` | `net_won_ce` | Match завършен, нетна печалба |
| `ac_credit_changed` | `credit_ce` | Кредит променен |
| `ac_flow_suspend` | — | Спри играта временно |
| `ac_flow_resume` | — | Продължи играта |
| `ac_flow_terminate` | — | Завърши играта |
| `ac_key_down` | `button_id` | Бутон натиснат |
| `ac_key_up` | `button_id` | Бутон отпуснат |
| `ac_touch_pressed` | `x`, `y` | Touch down |
| `ac_touch_released` | `x`, `y` | Touch up |
| `ac_meter_info` | meter data | Meter query отговор |
| `ac_cfg_updated` | — | Конфигурация обновена (unexpected) |

---

## Допълнителни бележки

### RNG Retry механизъм

```
Заявка → чакай 500ms → [няма отговор] → retry #1
       → чакай 500ms → [няма отговор] → retry #2
       → чакай 500ms → [няма отговор] → retry #3
       → EXIT CODE 11 (RNG timeout)
```

### Game Snapshot

При `ca_game_end`, OGAPIWrapperAstro автоматично изпраща `ca_game_snapshot` с `monitor=0`.
Това позволява на kernel-а да направи screenshot за регулаторни цели.

### Workaround за Init Flow

В `AstroEgt.cpp` има `initFlowIssueWorkaround = true` (винаги включен) — повторно
извикване на `ak2api_init_until_complete()` за обработка на edge case при startup.
