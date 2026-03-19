# Inspired vs Astro: Сравнителен анализ на платформената комуникация

Този документ сравнява комуникацията между играта и двете VLT платформи — **Inspired** (iKernel/OGAPI) и **Astro** (AstroKernel/AK2API) — в проекта `italy_games`.

> **Свързани документи:**
> - `fsm-communication-architecture.md` — обща FSM архитектура на italy_games
> - `iKernel-Game-Communication-Sequence.md` — детайлен Inspired/OGAPI протокол
> - `Astro-Game-Communication-Sequence.md` — детайлен Astro/AK2API протокол

---

## 1. Обобщение

И двете платформи използват общ `OGAPIWrapper` интерфейс — играта не знае директно с коя платформа работи. Различията са скрити в имплементациите `OGAPIWrapperInspired` и `OGAPIWrapperAstro`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INSPIRED (iKernel)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  GameFsm → CommComponent → OGAPIWrapperInspired                             │
│                                  │                                          │
│                                  ├→ LegionItComma6_Interface_v2             │
│                                  ├→ OGAPI_Admin_Interface_v2                │
│                                  └→ OGAPI_CabinetButtons_Interface_v1       │
│                                                                             │
│  Модел: CALLBACK-BASED (C-style static callbacks)                           │
│  DLL: ogapiDLL_Release.dll                                                  │
│  Heartbeat: ДА (на 15 секунди)                                              │
│  ProcessCallbacks: ДА (всеки frame, за двата интерфейса)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          ASTRO (AstroKernel)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  GameFsm → CommComponent → OGAPIWrapperAstro                                │
│                                  │                                          │
│                                  ├→ IAstroEgtApi / AstroEgt                 │
│                                  └→ AK2API (message-based)                  │
│                                                                             │
│  Модел: MESSAGE-BASED (ak2api_check_message)                                │
│  DLL: Injected IAstroEgtApi                                                 │
│  Heartbeat: НЕ                                                              │
│  ProcessCallbacks: НЕ (messages се четат при check_message)                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Архитектурно сравнение

### 2.1 Communication Model

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Модел** | Callback-based (OGAPI DLL) | Message-based (AK2API) |
| **Стил на callbacks** | C-style static functions с `void* userData` | C++ lambdas в EventMgr |
| **Инициализация** | Синхронна (blocking loops с ProcessCallbacks) | Асинхронна (event-driven) |
| **DLL зареждане** | `LoadLibraryA("ogapiDLL_Release.dll")` + `GetProcAddress` | Injected `IAstroEgtApi` |
| **Thread safety** | Всичко на main thread | Всичко на main thread |

### 2.2 Integration Layer

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Wrapper** | `OGAPIWrapperInspired` | `OGAPIWrapperAstro` |
| **Kernel interface** | `LegionItComma6_Interface_v2` | `IAstroEgtApi` → `AstroEgt` → AK2API |
| **Брой интерфейси** | 3 (Admin, CabinetButtons, LegionItComma6) | 1 (IAstroEgtApi, обединен) |
| **Допълнителен слой** | Няма | IKernelApi abstract layer |
| **Event mapping** | Директни callbacks → ICommComponent | Events → onKernelResponse enum → ICommComponent |

### 2.3 Main Loop

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Message pump** | Windows MSG loop / X11 XEvent | SDL/OpenGL based |
| **Callback processing** | `adminInterface->ProcessCallbacks()` + `buttonsInterface->ProcessCallbacks()` всеки frame | `ak2api_check_message()` в StartMainLoopTick |
| **Heartbeat** | `legionInterface->Heartbeat()` на 15s (timeout 25s) | Няма |
| **Frame rate** | 60 FPS target, `Sleep`/`usleep` | 60 FPS target, frame control |
| **NVRAM sync** | Memento файлове | `SyncNvram()` при StartMainLoopTick |

---

## 3. OGAPI Calls Mapping (детайлна таблица)

Това е ключовата таблица — показва как всеки OGAPIWrapper call е имплементиран в двете платформи:

| OGAPIWrapper Call | Inspired имплементация | Astro имплементация | Astro Реален/Симулиран |
|-------------------|------------------------|---------------------|------------------------|
| **AskContinueRequest()** | `legionInterface->AskContinue(cb, null)` → callback с int (1=OK, 0=exit) | `simulateEvents[eAskContinue] = true` → симулира callback | **Симулиран** |
| **StartGameCycleRequest(id)** | `legionInterface->StartGameCycle(cb, null, id)` → callback с gameCycleId | `simulateEvents[eGameCycleStart] = true` → симулира callback | **Симулиран** |
| **ReserveStakeRequest(amount)** | `legionInterface->ReserveStake(cb, null, amount)` → callback с token | `astroEgtApi->RequestStartMatch(bet, "main")` → `ca_game_start` | **Реален** |
| **RngNumbersRequest(from,to,cnt)** | `legionInterface->GetRandomInts32(cb, this, reqs, 1)` с range конвертиране | `astroEgtApi->RequestRandoms(count, max)` → `ca_rng_request` | **Реален** |
| **SetCheckpointRequest(sum,phase)** | `legionInterface->SetCheckpoint(cb, null, result, phaseInfo)` | `astroEgtApi->RequestRoundOutcome(win, desc)` → `ca_game_step` | **Реален** |
| **CommitStakeRequest(token)** | `legionInterface->CommitStake(cb, null, token)` → callback | `simulateEvents[eCommitTakeCredit] = true` → симулира callback | **Симулиран** |
| **AwardWinningsRequest(amount)** | `legionInterface->AwardWinnings(cb, null, amount)` → callback + credit change | `generateTaxationMsg(amount)` + `simulateEvents[eAwardWinnings] = true` | **Симулиран** |
| **EndGameCycleRequest(sum)** | `legionInterface->EndGameCycle(cb, null, result, null)` → callback | `astroEgtApi->RequestEndMatch(win, "main")` → `ca_game_end` | **Реален** |
| **CashoutRequest()** | `legionInterface->Cashout(cb, null)` → start/end callbacks | `simulateEvents[eCollect] = true` → `RequestCashout()` → `ca_credit_payout` | **Реален** |
| **RollbackStakeRequest(token)** | `legionInterface->RollbackStake(cb, null, token)` | Няма еквивалент (kernel управлява при exit code) | — |

> **Ключов извод:** В Astro, 4 от 9 основни OGAPI calls са **симулирани** (AskContinue, StartGameCycle, CommitStake, AwardWinnings). Това е защото AK2API протоколът е по-опростен — `ca_game_start` обединява ReserveStake + CommitStake, а `ca_game_end` обединява AwardWinnings + EndGameCycle.

---

## 4. Flow-by-Flow сравнение

### 4.1 Game Start Flow

```
INSPIRED:                              ASTRO:
════════                               ═════
1. AskContinue → callback(1)           1. AskContinue → СИМУЛИРАН(1)
2. StartGameCycle → callback(id)       2. StartGameCycle → СИМУЛИРАН(id)
3. ReserveStake(bet) → callback(token) 3. ReserveStake(bet) → RequestStartMatch
   [Credit намалява]                      → ca_game_start(bet_ce, max_bet)
                                          → ac_game_start_acked(enabled)
                                          [Credit намалява]

Стъпки: 3 OGAPI calls                 Стъпки: 1 реален AK2API call
        3 kernel round-trips                   1 kernel round-trip
```

### 4.2 RNG Request Flow

```
INSPIRED:                              ASTRO:
════════                               ═════
GetRandomInts32(cb, ranges, count)     RequestRandoms(count, max)
  • Range конверсия:                     → ca_rng_request(count)
    EGT [min,max] → Inspired bounds      → ac_rng_result(nums[])
  • Callback с raw числа                 • Конверсия:
  • Обратна конверсия:                     raw [0, 2^31-1] →
    Inspired → EGT range                   game [min, max]
                                         • Retry: 3×500ms

Max числа: 32 на заявка               Max числа: 63 на заявка
Timeout: RNG error splash (5s)         Timeout: Exit code 11 (auto-return bet)
```

### 4.3 Round Outcome Reporting

```
INSPIRED:                              ASTRO:
════════                               ═════
SetCheckpoint(summary, phaseInfo)      SetCheckpoint → RequestRoundOutcome
  • PhaseInfo struct:                    → ca_game_step(seq, won_ce, result)
    phase, prize, randomNumbers,         → ac_game_step_acked
    randomCount, stake
  • Result string:                     • Outcome description:
    "R1:123|R2:456|Total:200"            "RN:45,12|MG|STK:50|WIN:200"
                                       • seq инкрементира (за recovery)
CommitStake(token)                     CommitStake → СИМУЛИРАН
  • Потвърждава stake
```

> **Ключова разлика:** В Inspired, `SetCheckpoint` + `CommitStake` са два отделни calls.
> В Astro, `ca_game_step` обединява двете функции — няма отделен CommitStake.

### 4.4 Game End Flow

```
INSPIRED:                              ASTRO:
════════                               ═════
[win > 0]:                             [win > 0]:
AwardWinnings(amount)                  AwardWinnings → СИМУЛИРАН
  → callback + OnCreditChanged           (tax msg генериран локално)
  → [може: OnTaxEvent от kernel]

EndGameCycle(summary, null)            EndGameCycle → RequestEndMatch
  → callback                             → ca_game_end(won_ce, result)
                                          → ac_game_end_acked(net_won_ce)
                                          → ac_credit_changed
                                          → ca_game_snapshot (автоматично)

AskContinue() → callback(1)           AskContinue → СИМУЛИРАН(1)

Стъпки: 3 OGAPI calls                 Стъпки: 1 реален AK2API call
```

### 4.5 Gamble Flow

```
INSPIRED:                              ASTRO:
════════                               ═════
GetRandomInt32(cb, lower, upper)       RequestRandoms(1, max)
  → 1 random число за карта              → ca_rng_request(1)
                                          → ac_rng_result
SetCheckpoint(gambleInfo)              SetCheckpoint → ca_game_step
  phase: GAME_PHASE_GAMBLE               (gamble outcome description)
  prize: doubled or 0
  stake: risked amount

CommitStake(token)                     CommitStake → СИМУЛИРАН

[Идентични FSM states: GambleIntro → GambleIdle → GambleResults → GambleOutro]
```

### 4.6 Free Games Flow

```
INSPIRED:                              ASTRO:
════════                               ═════
[Използва FreeGamesInspiredState]      [Използва FreeGamesAresState]

За всеки free spin:                    За всеки free spin:
  GetRandomInts32(cb, ranges, cnt)       RequestRandoms(count, max)
  SetCheckpoint(freeSpinInfo)             → ca_game_step(seq++, won, desc)
    phase: GAME_PHASE_FEATURE
  CommitStake(token)

Phase mapping:                         Outcome type:
  MainSpin → PRIMARY                     MG (main game)
  FreeSpin → FEATURE                     FG (free game)
  ExtraSpin → FEATURE                    EG (energy/bonus)
  BurningSpin → GAMBLE                   RG (risk/gamble)
  RedBlackGamble → GAMBLE
```

> **Забележка:** Играта има **отделни FSM states** за free games на Inspired (`FreeGamesInspiredState`) и Astro/Ares (`FreeGamesAresState`). Основните разлики са в checkpoint reporting и phase info формата.

---

## 5. Recovery сравнение

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Persistence механизъм** | Memento файлове на disk | 8KB NVRAM буфер |
| **Recovery ID** | `gameCycleId` (от StartGameCycle) | `gameStepSeq` (sequence number) |
| **Recovery trigger** | `StartGameCycle(previousId)` с предишен ID | Автоматичен — resend на pending message |
| **Pending операции** | Token-based (RollbackStake при неуспех) | 3 типа pending messages (game_start, game_step, game_end) |
| **Какво се запазва** | Game state + gameCycleId + token | Пълен state + seq + pending msg bytes |
| **RNG error** | Error splash 5s → exit (без EndGameCycle) | Exit code 11 → bet автоматично върнат |
| **Rollback** | `RollbackStake(token)` за отмяна на stake | Няма — kernel обработва при exit code |

### Inspired Recovery

```
    [Рестарт след crash]
           │
           ▼
    Чете memento → извлича gameCycleId
           │
           ▼
    StartGameCycle(previousId)
    → Kernel възстановява game cycle
    → Играта продължава от последен checkpoint
```

### Astro Recovery

```
    [Рестарт след crash]
           │
           ▼
    Чете NVRAM → извлича state:
    - gameStepSeq
    - matchName
    - pendingMsg
           │
    ┌──────┴──────┐
    │  seq == 0   │ → Match не е започнал → чист старт
    │  seq > 0    │ → Проверка на step_seq_acked:
    │             │   - acked == seq → емулирай acked
    │             │   - acked < seq → resend pending msg
    │  seq == -1  │ → Match вече завършен → емулирай end acked
    └─────────────┘
```

---

## 6. Специфични разлики

### 6.1 Credit Handling

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Получаване на кредит** | `GetCredit(cb)` → callback с `stakeableCredit` | `ac_credit_changed` event с `credit_ce` |
| **Credit при AwardWinnings** | Автоматичен OnCreditChangedEvent от kernel | Credit change идва при `ac_game_end_acked` |
| **Начален кредит** | Blocking loop: `while (!receivedCreditInfo) ProcessCallbacks()` | `ac_credit_changed` при init |

### 6.2 Tax Handling

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Източник** | Kernel изпраща `OnTaxEvent` callback | Локално изчисление в OGAPIWrapperAstro |
| **Конфигурация** | Вградена в kernel | Четена при init: `PropertyNameMinTaxLimit`, `PropertyNameTaxPercent` |
| **Формат** | String от kernel | Локално форматирано съобщение |

### 6.3 Heartbeat / Main Loop

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Heartbeat** | `legionInterface->Heartbeat()` на 15s | Няма heartbeat |
| **Timeout** | 25s (ако не изпратиш — disconnect) | Няма timeout |
| **ProcessCallbacks** | 2 повиквания/frame (admin + buttons) | `ak2api_check_message()` 1 повикване/frame |

### 6.4 Buttons / Input

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Интерфейс** | `CabinetButtons_Interface_v1` с отделен `ProcessCallbacks` | `ac_key_down/up` messages |
| **Button формат** | Char pairs ('0'/'1') за previous/current state | AstroKeys enum → keyboard mapping |
| **Touch** | Не (Windows mouse events) | `ac_touch_pressed/released` messages |

### 6.5 Snapshot / Screen Capture

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Механизъм** | Не е имплементиран в OGAPIWrapperInspired | `ca_game_snapshot(monitor=0)` при game end |
| **Кога** | — | Автоматично след `ca_game_end` |

### 6.6 Suspend / Resume / Terminate

| Аспект | Inspired | Astro |
|--------|----------|-------|
| **Suspend** | `OnExitDeferredEvent` → exit при край на cycle | `ac_flow_suspend` → блокира game cycle, продължава rendering |
| **Resume** | Няма explicit resume | `ac_flow_resume` → продължава game cycle |
| **Terminate** | `Exiting(cb)` при error | `ac_flow_terminate` → graceful shutdown |

---

## 7. Известни workarounds в source code

### 7.1 Astro — Симулирани events

**Файл:** `OGAPIWrapperAstro.cpp`

OGAPIWrapperAstro симулира 4 OGAPI calls за съвместимост:
- `AskContinue` — винаги връща success
- `StartGameCycle` — генерира локален gameCycleId
- `CommitStake` — маркира като success
- `AwardWinnings` — изчислява tax локално, маркира success

Причина: AK2API протоколът няма еквиваленти на тези calls — те са специфични за OGAPI модела.

### 7.2 Astro — Credit change при AwardWinnings

**Файл:** `OGAPIWrapperAstro.cpp`, response handling

При `AwardWinnings` в Inspired, kernel изпраща `OnCreditChangedEvent` автоматично. В Astro, кредитът се актуализира при `ac_game_end_acked`. OGAPIWrapperAstro трябва да симулира `onCreditChange` при получаване на `eEndMatchAck` за да поддържа консистентен CommComponent interface.

### 7.3 Astro — RNG retry механизъм

**Файл:** `AstroEgt.cpp`, линии 610-631

AstroEgt автоматично resend-ва `ca_rng_request` ако не получи отговор в 500ms, до 3 опита. В Inspired няма такъв механизъм — timeout води директно до error splash.

### 7.4 Astro — Init flow workaround

**Файл:** `AstroEgt.cpp`

`initFlowIssueWorkaround = true` (винаги включен) — допълнително извикване на `ak2api_init_until_complete()` за edge case при startup.

### 7.5 Astro — Recovery startup delay

**Файл:** `AstroEgt.cpp`, линии 249, 264-267

3-frame изчакване след `ca_flow_start` преди обработка на pending messages — дава време на AstroKernel framework-а да се стабилизира.

### 7.6 Inspired — RNG range конверсия

**Файл:** `OGAPIWrapperInspired.cpp`

Inspired изисква конверсия на RNG ranges:
- `ConvertRngEgtToInspired()` — преди заявка
- `ConvertRngInspiredToEgt()` — при получаване на резултат

Astro не изисква такава конверсия — само прост modulo mapping.

### 7.7 Inspired — Fast button click handling

**Файл:** `OGAPIWrapperInspired.cpp`, линии 563-569

Специална обработка за много бързо натискане на бутон — ако press и release пристигнат в един frame, маркира като pressed за следващия frame.

---

## 8. Обобщителна таблица

| Категория | Inspired | Astro |
|-----------|----------|-------|
| **Протокол** | OGAPI (callback-based DLL) | AK2API (message-based) |
| **Реални kernel calls за 1 game cycle** | ~9 (AskContinue, StartGC, Reserve, RNG, SetCP, Commit, Award, EndGC, AskContinue) | ~4 (game_start, rng_request, game_step, game_end) |
| **Heartbeat** | Да (15s) | Не |
| **Recovery** | Memento файлове + gameCycleId | NVRAM + step_seq_acked |
| **Tax** | От kernel (external) | Локално изчисление |
| **RNG max на заявка** | 32 числа | 63 числа |
| **RNG timeout** | Error splash → exit | Exit code 11 → auto-return bet |
| **Range конверсия** | Да (EGT ↔ Inspired) | Не (прост modulo) |
| **Screenshot** | Не | Да (ca_game_snapshot) |
| **Сертификация** | Завършена | Предстои |
| **FSM states** | FreeGamesInspiredState | FreeGamesAresState |
| **Complexity** | По-висока (повече kernel round-trips) | По-ниска (по-малко calls, симулирани операции) |
