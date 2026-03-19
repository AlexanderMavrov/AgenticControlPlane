# FSM-Kernel Communication Architecture

Този документ описва комуникацията между FSM state машината на играта и Kernel API-то (Playground, Inspired, Astro).

---

## 1. Основни понятия

### 1.1 Match (Мач)

**Match** е една игрална сесия, която започва с натискане на бутон "Start" и завършва когато играчът събере или загуби всички спечелени валути.

- Започва с: `RequestStartMatch(bet)`
- Завършва с: `RequestEndMatch(totalWin)`
- Съдържа: един или повече rounds
- Wallet: управлява спечелени и изразходвани валути в рамките на match-а

```
┌─────────────────────────────────────────────────────────────────┐
│                           MATCH                                 │
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │  Round 1 │ → │  Round 2 │ → │  Round 3 │ → │  Round N │      │
│  │  (Main)  │   │  (Free)  │   │  (Free)  │   │ (Gamble) │      │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘      │
│                                                                 │
│  Match Wallet: rewarded - consumed = available                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Round (Рунд)

**Round** е един spin/завъртане. Match-ът съдържа поне един round (Main), но може да има много (Free spins, Bonus rounds, Gamble).

Типове rounds:
- **Main** - основен spin, консумира кредити
- **Free** - безплатен spin, спечелен от Main
- **HoldAndSpin** - bonus round със задържане на символи
- **Wheel** - колело на късмета
- **Gamble** - рисков round (double-or-nothing)

Всеки round преминава през фази:
```
Starting → Reeling → Presenting → Ending
```

### 1.3 State (Състояние)

**State** е FSM състояние, което управлява конкретна фаза от играта. States са организирани йерархично:

```
Root
├── Idle                    # Чакане за игра
└── Match                   # Активна игра
    ├── MatchStarting       # Заявка към kernel за старт
    ├── MainRound          # Основен spin
    │   ├── MainRoundStarting
    │   ├── MainRoundReeling
    │   ├── MainRoundPresenting
    │   └── MainRoundEnding
    ├── FreeRound          # Free spins
    ├── HoldAndSpinRound   # Bonus round
    ├── WheelRound         # Колело
    ├── GambleRound        # Gamble
    ├── MatchTakeWin       # Събиране на печалба
    ├── MatchEnding        # Завършване на match
    └── MatchEndOutro      # Анимация след match
```

---

## 2. Архитектурни слоеве

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FSM STATES                                     │
│   IdleState, MatchStartingState, MainRoundStartingState, ...                │
│                                                                             │
│   - Реагира на user input (бутони)                                          │
│   - Управлява UI/View transitions                                           │
│   - Извиква IGameflow за kernel комуникация                                 │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IGameflow                                         │
│             (AlphaFamilyGameflow implementation)                            │
│                                                                             │
│   - Абстракция над kernel комуникацията                                     │
│   - Управлява match/round lifecycle                                         │
│   - Калкулира резултати с random числа                                      │
│   - Emits events: startMatchReply, startRoundReply, etc.                    │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      IKernelApi (Interface)                                 │
│                                                                             │
│   Methods:                          Events:                                 │
│   - RequestStartMatch()             - onStartMatchReply                     │
│   - RequestStartRound()             - onStartRoundReply                     │
│   - RequestRoundOutcome()           - onRoundOutcomeReply                   │
│   - RequestEndMatch()               - onEndMatchReply                       │
│   - RequestRandoms()                - onRandomsReply                        │
│   - RequestCashout()                - onCashoutEnd                          │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
     │ Playground  │    │   Inspired  │    │    Astro    │
     │ KernelApi   │    │  KernelApi  │    │  KernelApi  │
     │             │    │   (OGAPI)   │    │   (GDK)     │
     │  (Local)    │    │  (Remote)   │    │  (Remote)   │
     └─────────────┘    └─────────────┘    └─────────────┘
```

---

## 3. Communication Flow

### 3.1 Match Start Flow

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────────┐
│  IdleState   │     │MatchStarting │     │ AlphaFamily    │     │  KernelApi  │
│              │     │    State     │     │   Gameflow     │     │             │
└──────┬───────┘     └──────┬───────┘     └───────┬────────┘     └──────┬──────┘
       │                    │                     │                     │
       │ [StartGame Button] │                     │                     │
       │────────────────────>                     │                     │
       │ Transit<IMatch>    │                     │                     │
       │                    │                     │                     │
       │                    │ OnTransit()         │                     │
       │                    │ RequestStartMatch() │                     │
       │                    │─────────────────────>                     │
       │                    │                     │ RequestStartMatch(bet)
       │                    │                     │─────────────────────>
       │                    │                     │                     │
       │                    │                     │     [Kernel validates]
       │                    │                     │     [Deducts credit]
       │                    │                     │                     │
       │                    │                     │   onStartMatchReply │
       │                    │                     │<─────────────────────
       │                    │   startMatchReply   │                     │
       │                    │<─────────────────────                     │
       │                    │                     │                     │
       │                    │ Transit<IMainRound> │                     │
       │                    │                     │                     │
```

### 3.2 Round Calculation Flow (с RequestRandoms)

```
┌──────────────────┐     ┌────────────────┐     ┌─────────────┐
│ ReelRoundStarting│     │ AlphaFamily    │     │  KernelApi  │
│      State       │     │   Gameflow     │     │             │
└────────┬─────────┘     └───────┬────────┘     └──────┬──────┘
         │                       │                     │
         │ OnTransit()           │                     │
         │ RequestStartRound()   │                     │
         │───────────────────────>                     │
         │                       │ RequestStartRound() │
         │                       │─────────────────────>
         │                       │                     │
         │                       │  onStartRoundReply  │
         │                       │<─────────────────────
         │                       │                     │
         │                       │ CalculateRoundResult()
         │                       │ [Math needs randoms]│
         │                       │                     │
         │                       │ RequestRandoms(32)  │
         │                       │─────────────────────>
         │                       │                     │
         │                       │  onRandomsReply     │
         │                       │<─────────────────────
         │                       │                     │
         │                       │ CalculateRoundResult()
         │                       │ [Retry with randoms]│
         │                       │                     │
         │                       │ [If still need more]│
         │                       │ RequestRandoms(32)  │
         │                       │─────────────────────>
         │                       │        ...          │
         │                       │                     │
         │                       │ [Calculation done]  │
         │                       │ RequestRoundOutcome │
         │                       │─────────────────────>
         │                       │                     │
         │                       │ onRoundOutcomeReply │
         │                       │<─────────────────────
         │                       │                     │
         │   startRoundReply     │                     │
         │<───────────────────────                     │
         │                       │                     │
         │ Transit<Reeling>      │                     │
```

### 3.3 Complete Match Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE MATCH LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IDLE STATE                                                                 │
│  ══════════                                                                 │
│  • Показва последен резултат                                                │
│  • Чака StartGame бутон                                                     │
│  • Чете кредит синхронно: GetCredit()                                       │
│       │                                                                     │
│       │ [StartGame Button]                                                  │
│       ▼                                                                     │
│  MATCH STARTING                                                             │
│  ══════════════                                                             │
│  • Kernel: RequestStartMatch(bet)                                           │
│  • Kernel дедуктира кредит                                                  │
│  • Reply: approved/rejected                                                 │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ROUND LOOP (повтаря се за Main, Free, Bonus rounds)                 │    │
│  │                                                                     │    │
│  │  ROUND STARTING                                                     │    │
│  │  ══════════════                                                     │    │
│  │  • Kernel: RequestStartRound()                                      │    │
│  │  • Gameflow: CalculateRoundResult()                                 │    │
│  │  • Kernel: RequestRandoms() (итеративно, докато има достатъчно)     │    │
│  │  • Kernel: RequestRoundOutcome(win)                                 │    │
│  │  • Reply съдържа RoundResult                                        │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  ROUND REELING                                                      │    │
│  │  ═════════════                                                      │    │
│  │  • Визуализира въртенето на барабаните                              │    │
│  │  • Показва fake reels докато чака резултат                          │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  ROUND PRESENTING                                                   │    │
│  │  ════════════════                                                   │    │
│  │  • Показва печеливши линии                                          │    │
│  │  • Анимира печалби                                                  │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  ROUND ENDING                                                       │    │
│  │  ════════════                                                       │    │
│  │  • Gameflow: RequestEndRound()                                      │    │
│  │  • Прехвърля награди към match wallet                               │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  [Next round?] ─────────────────────────────────────────────────┐   │    │
│  │       │                                                         │   │    │
│  │       │ YES (има Free/Bonus/Gamble)                             │   │    │
│  │       └─────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                     │
│       │ NO (няма повече rounds)                                             │
│       ▼                                                                     │
│  MATCH TAKE WIN                                                             │
│  ══════════════                                                             │
│  • Показва опция за Gamble или Take Win                                     │
│       │                                                                     │
│       ▼                                                                     │
│  MATCH ENDING                                                               │
│  ════════════                                                               │
│  • Kernel: RequestEndMatch(totalWin)                                        │
│  • Kernel добавя печалбата към кредита                                      │
│       │                                                                     │
│       ▼                                                                     │
│  MATCH END OUTRO                                                            │
│  ═══════════════                                                            │
│  • Финална анимация                                                         │
│       │                                                                     │
│       ▼                                                                     │
│  IDLE STATE  ◄───────────────────────────────────────────────────────────   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. State Transitions

### 4.1 FSM State Hierarchy

```
                                   ┌───────────┐
                                   │   Root    │
                                   └─────┬─────┘
                          ┌──────────────┴──────────────┐
                          ▼                             ▼
                   ┌───────────┐                 ┌───────────┐
                   │   Idle    │◄────────────────│   Match   │
                   └───────────┘                 └─────┬─────┘
                                                       │
              ┌────────────┬────────────┬──────────────┼──────────────┐
              ▼            ▼            ▼              ▼              ▼
       ┌────────────┐┌──────────┐┌───────────┐┌─────────────┐┌────────────┐
       │MatchStarting││MainRound ││ FreeRound ││HoldAndSpin  ││MatchEnding │
       └────────────┘└────┬─────┘└───────────┘│    Round    │└────────────┘
                          │                   └─────────────┘
         ┌────────────────┼────────────────┬────────────────┐
         ▼                ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ Starting │───►│ Reeling  │───►│Presenting│───►│  Ending  │
   └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 4.2 State Reactions

Всеки State може да реагира по няколко начина:

```cpp
Reaction OnEvent()
{
    // 1. Transit - премини към нов state
    return Transit<IMainRound>();

    // 2. Forward - препрати събитието към parent states
    return Forward();

    // 3. Discard - изяж събитието без действие
    return Discard();
}
```

---

## 5. Kernel API Interface

### 5.1 Requests (Game → Kernel)

| Method | Описание | Playground | Inspired | Astro |
|--------|----------|------------|----------|-------|
| `RequestStartMatch(bet)` | Започни match, удържи bet | Sync | OGAPI | GDK |
| `RequestStartRound()` | Започни round | Sync | OGAPI | GDK |
| `RequestRandoms(count)` | Заяви random числа | Local RNG | OGAPI | GDK |
| `RequestRoundOutcome(win)` | Докладвай резултат | Sync | OGAPI | GDK |
| `RequestEndMatch(totalWin)` | Завърши match, добави win | Sync | OGAPI | GDK |
| `RequestCashout()` | Изплати кредита | Sync | OGAPI | GDK |

### 5.2 Events (Kernel → Game)

| Event | Описание |
|-------|----------|
| `onStartMatchReply(success)` | Match approved/rejected |
| `onStartRoundReply()` | Round started |
| `onRandomsReply(randoms)` | Random numbers received |
| `onRoundOutcomeReply()` | Result acknowledged |
| `onEndMatchReply(netWin)` | Match ended, final win |
| `creditChanged(credit)` | Credit balance changed |

---

## 6. Playground vs Real Integrations

### 6.1 Playground (Development)

- **Sync operations**: Всички заявки се изпълняват веднага
- **Local RNG**: Random числа от локален engine
- **No network**: Няма мрежова комуникация
- **Persistence**: Локален файл (nvram)

### 6.2 Inspired/Astro (Production)

- **Async operations**: Всички заявки са асинхронни
- **Remote RNG**: Random числа от сертифициран сървър
- **Network protocol**: OGAPI/GDK протокол
- **Persistence**: Server-side state management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PLAYGROUND (Development)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Game ──► PlaygroundKernelApi ──► Local RNG + Local State                   │
│                 │                                                           │
│                 └──► Immediate response (no network)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          INSPIRED/ASTRO (Production)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Game ──► InspiredEgt/AstroEgt ──► OGAPI/GDK ──► Cabinet Controller         │
│                 │                                      │                    │
│                 └──────────────────────────────────────┘                    │
│                          Async response (network)                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Key Files Reference

| File | Описание |
|------|----------|
| `game/alpha_family/libs/.../Idle/Idle.cpp` | Idle state implementation |
| `game/alpha_family/libs/.../MatchStarting/MatchStarting.cpp` | Match start logic |
| `game/alpha_family/libs/.../ReelRound/ReelRoundStarting.cpp` | Round start logic |
| `integration/plugins/.../AlphaFamilyGameflow.cpp` | Gameflow + kernel comm |
| `integration/libs/.../IKernelApi.h` | Kernel API interface |
| `kernel/libs/.../PlaygroundKernelApi.cpp` | Playground implementation |

---

## 8. Code Examples

### 8.1 IdleState - Starting a Match

```cpp
// game/alpha_family/libs/src/Egt/AlphaFamilyStatesLibrary/Idle/Idle.cpp

Reaction IdleState::OnStartGameHwButtonPressed()
{
    ReturnUnless(CanStartMatch(), Discard());
    return Transit<IMatch>();  // Преход към Match state
}

bool IdleState::CanStartMatch() const
{
    auto bet = Parent<IBetManager>().GetCurrentBet();
    auto credit = RuntimeGetConst<IWallet>().GetCredit();
    ReturnIf(bet > credit, false);
    return true;
}
```

### 8.2 MatchStartingState - Kernel Communication

```cpp
// game/alpha_family/libs/src/Egt/AlphaFamilyStatesLibrary/Match/MatchStarting/MatchStarting.cpp

void MatchStartingState::OnTransit(bool isStartup, bool isRecovery)
{
    AttachCallbacks();
    if (!isRecovery)
    {
        RequestStartMatch();  // Заявка към kernel
    }
}

void MatchStartingState::RequestStartMatch()
{
    StartMatchRequest request;
    request.bet = Parent<IBetManager>().GetInitialBet();
    RuntimeGet<IGameflow>().RequestStartMatch(request);
}

Reaction MatchStartingState::OnStartMatchReply(StartMatchReply reply)
{
    if (!reply.approved)
    {
        return Transit<IIdle>();  // Отказан match
    }
    return Transit<IMainRound>();  // Одобрен - започни Main round
}
```

### 8.3 AlphaFamilyGameflow - Random Numbers Loop

```cpp
// integration/plugins/src/Egt/AlphaFamilyGameflow/AlphaFamilyGameflow.cpp

void AlphaFamilyGameflow::CalculateRoundResult()
{
    auto& rng = GetRoundRng();

    auto resultOrError = std::visit(/* math calculation */, round.input);

    if (auto error = std::get_if<RoundError>(&resultOrError))
    {
        if (error->code == RoundErrorCode::InsufficientRandomBits)
        {
            // Няма достатъчно random bits - заяви още
            auto& kernel = RuntimeGet<IKernelIntegration>();
            kernel.GetKernelApi().RequestRandoms(32, 0);
            return;  // Ще се извика отново при OnKernelRandomsReply
        }
    }

    // Успешна калкулация - докладвай резултата
    kernel.GetKernelApi().RequestRoundOutcome(creditWin, description, otherWins);
}

void AlphaFamilyGameflow::OnKernelRandomsReply(Randoms randoms, uint32_t maxValue, Name name)
{
    // Добави новите random числа към engine-а
    auto& numbers = volatileRngNumbers.value();
    for (auto& value : randoms)
    {
        numbers.push_back(value);
    }

    // Пробвай отново калкулацията
    CalculateRoundResult();
}
```
