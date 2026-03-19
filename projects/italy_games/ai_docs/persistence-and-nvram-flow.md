# Persistence & NVRAM Flow — Astro Integration

**Дата:** 2026-03-11
**Проект:** italy_games / Astro (Sisal)

---

## Архитектурна диаграма — пълен път на данните

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FSM State Handler                               │
│  (напр. ReelingSubstate::react(OnRandomNumbersEvent))                   │
│                                                                         │
│  1. mainGameScene.SetGameResults(result)                                │
│     └── GameData мутира: figures, wins, bonus triggers                  │
│                                                                         │
│  2. SaveGameState<ReelingSubstate>(eGameData)                           │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │  GameFsm::SaveGameState<FsmState>(flags)                │            │
│  │                                                         │            │
│  │  ┌─ OpenTransaction() ─────────────────────────┐        │            │
│  │  │                                              │        │            │
│  │  │  if (eGameData)                              │        │            │
│  │  │    GameData::Save2()  ──────────────┐        │        │            │
│  │  │                                     │        │        │            │
│  │  │  if (eFreeGameData)                 │        │        │            │
│  │  │    FreeGamesData::Save2() ──────────┤        │        │            │
│  │  │                                     │        │        │            │
│  │  │  if (eGambleGameData)               │  Всички пишат   │            │
│  │  │    GambleData::Save2()  ────────────┤  в един и същ   │            │
│  │  │                                     │  StreamPersistance│           │
│  │  │  if (eTakeCoinsGameData)            │  ::m_stream      │            │
│  │  │    TakeCoinsData::Save2() ──────────┤  (различни      │            │
│  │  │                                     │   сектори)      │            │
│  │  │  if (eShinyCashGameData)            │                 │            │
│  │  │    ShinyCashData::Save2() ──────────┤                 │            │
│  │  │                                     │                 │            │
│  │  │  m_stateRecovery.SaveState<T>() ────┘                 │            │
│  │  │    └── записва САМО string:                           │            │
│  │  │        typeid(ReelingSubstate).name()                 │            │
│  │  │        в сектор "sd"                                  │            │
│  │  │                                              │        │            │
│  │  └─ CloseTransaction() ────────────────────────┘        │            │
│  │       └── m_isChanged = true                            │            │
│  └─────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Main Loop (AstroMain.h)                        │
│                                                                         │
│  while (!exitRequested)                                                 │
│  {                                                                      │
│      StartMainLoopTick();    // sync NVRAM, process incoming msgs       │
│                                                                         │
│      game.Update(dt);        // FSM runs, може да извика SaveGameState  │
│                                                                         │
│      if (streamPersistance.IsChanged())     ◄── m_isChanged == true     │
│      {                                                                  │
│          bytes = streamPersistance.Dump();  // извлича ВСИЧКИ сектори   │
│          AstroEgt::SaveState(storage);      // gameState = bytes        │
│      }                                                                  │
│                                                                         │
│      EndMainLoopTick();                                                 │
│      │                                                                  │
│      └── if (m_newState)                                                │
│          {                                                              │
│              SaveAsyncToNvram(AstroEgtState);  // async запис           │
│              _processPendingMessage();                                   │
│              │                                                          │
│              └── SyncNvram();     // блокира до завършване               │
│                  SendMsgBuff();   // СЛЕД sync: изпраща msg             │
│          }                                                              │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Структура на данните в NVRAM (матрьошка)

```
NVRAM (8192 bytes / 8KB)
│
└── AstroEgtState (сериализиран чрез DataTools::PackIData)
    │
    ├── gameStepSeq: int         ← текущ sequence number на game step
    ├── pendingMsg: vector<u8>   ← сериализиранo ca_game_start/step/end (чака ack)
    ├── isCurrentRoundGamble: bool
    ├── matchName: string        ← име на текущия match
    ├── roundName: string        ← име на текущия round
    ├── matchInitialBet: u64     ← начален залог
    │
    └── gameState: AnyData (= vector<u8>)  ← BLOB от StreamPersistance::Dump()
        │
        ├── [Header]
        │   ├── sector count: u16
        │   ├── sector "gd": {id, offset, length}    ← GameData
        │   ├── sector "ggd": {id, offset, length}   ← GambleData
        │   ├── sector "fgd": {id, offset, length}   ← FreeGamesData
        │   ├── sector "tcd": {id, offset, length}   ← TakeCoinsData
        │   ├── sector "scd": {id, offset, length}   ← ShinyCashData
        │   ├── sector "sd": {id, offset, length}    ← StateData (State ID)
        │   └── header CRC32
        │
        ├── [Sector "gd" — GameData]
        │   ├── betPerLine, selectedLines, winMoney, winBonusMoney
        │   ├── freeGamesCount, bonusGamesCount
        │   ├── reelPositions[], figureResults[][]
        │   ├── contentStatusInProgress, giveCreditConfirmed
        │   ├── commitTakeCreditReqWait, waitingForRng
        │   ├── matchPhaseTypes[], gameExitRequest
        │   ├── serialRecoveryAttemp, ...
        │   └── sector CRC32
        │
        ├── [Sector "ggd" — GambleData]
        │   ├── gamblePick, gambleAttempts
        │   ├── currentWin, ...
        │   └── sector CRC32
        │
        ├── [Sector "fgd" — FreeGamesData]
        │   ├── extendedSymbol, freeGamesPlayed
        │   ├── totalWinInFG, ...
        │   └── sector CRC32
        │
        ├── [Sector "sd" — StateData]         ◄── САМО ЕДИН STRING!
        │   ├── m_id: "struct ReelingSubstate"
        │   └── sector CRC32
        │
        └── ... (други сектори)
```

---

## Кога се записва какво — timeline

```
Време ──────────────────────────────────────────────────────────────►

│ game.Update() │ IsChanged? │ SaveState │ EndMainLoopTick │
│ (FSM runs)    │  check     │ to struct │  NVRAM write    │

Случай A: FSM handler извика SaveGameState<T>(eGameData)
─────────────────────────────────────────────────────────
  │                                                      │
  ├─ OpenTransaction()                                   │
  ├─ GameData::Save2() ──► stream сектор "gd"            │
  ├─ StateRecovery::SaveState<T>() ──► stream сектор "sd"│
  ├─ CloseTransaction() ──► m_isChanged = true           │
  │                                                      │
  │              IsChanged()==true ──► Dump() ──► SaveState(storage)
  │                                        ──► AstroEgtState.gameState = bytes
  │                                                      │
  │                                  m_newState==true ──► SaveAsyncToNvram()
  │                                                  ──► SyncNvram()
  │                                                  ──► SendMsgBuff() (ако има pending)


Случай B: Директен Save2() (без SaveGameState)
───────────────────────────────────────────────
  │                                                      │
  ├─ GameData::Save2() ──► stream сектор "gd"            │
  │  └── CloseOStream() ──► CloseTransactionStream()     │
  │       └── m_isChanged = true                         │
  │  (State ID НЕ се обновява!)                          │
  │                                                      │
  │              IsChanged()==true ──► Dump() ──► ...     │
  │              (по-нататък същото като Случай A)        │


Случай C: Astro protocol msg (без PersistanceMemory)
─────────────────────────────────────────────────────
  │                                                      │
  ├─ RequestStartMatch() / RequestRoundOutcome() / ...   │
  │  └── StateMutable().pendingMsg = packed msg           │
  │       └── m_newState = true                          │
  │                                                      │
  │  (StreamPersistance НЕ е засегната!)                 │
  │                                                      │
  │                                  m_newState==true ──► SaveAsyncToNvram()
  │                                                      │
  │  (NVRAM записва целия AstroEgtState                  │
  │   включително gameState от последния Dump)            │
```

---

## PersistantClass — механизъм на сериализация

```
                    PersistantClass<GameData>("gd")
                              │
                              │ Save2()
                              ▼
                    ┌─────────────────────┐
                    │ 1. GetOStream()     │ ← PersistanceMemory дава локален buffer
                    │    = BytesWriter    │
                    │                     │
                    │ 2. Write(bw)        │ ← Сериализира ВСИЧКИ SerializableProperty:
                    │    - m_betPerLine   │    int, string, vector, enum, array...
                    │    - m_winMoney     │    чрез BytesWriter (binary формат)
                    │    - m_freeGames    │
                    │    - ...            │
                    │                     │
                    │ 3. CloseOStream(id) │ ← Записва buffer в StreamPersistance
                    │    - CRC32          │    ::m_stream, сектор "gd"
                    │    - ReallocSector  │    (преоразмерява ако трябва)
                    │    - Write to stream│
                    └─────────────────────┘

                    PersistantClass<StateData>("sd")
                              │
                              │ Save2()
                              ▼
                    ┌─────────────────────┐
                    │ 1. GetOStream()     │
                    │                     │
                    │ 2. Write(bw)        │ ← Сериализира САМО:
                    │    - m_id: string   │    "struct ReelingSubstate"
                    │                     │
                    │ 3. CloseOStream(id) │ ← Записва в сектор "sd"
                    └─────────────────────┘
```

---

## Транзакционен механизъм

```
SaveGameState<ReelingSubstate>(eGameData | eGambleGameData)
│
├── OpenTransaction()
│   └── s_transactionIsOpen = true
│
├── GameData::Save2()
│   └── CloseOStream("gd")
│       ├── s_transactionInAction = true  (първи Save в транзакцията)
│       ├── записва в stream
│       └── НЕ извиква CloseTransactionStream()   ◄── защото сме в транзакция
│
├── GambleData::Save2()
│   └── CloseOStream("ggd")
│       ├── s_transactionInAction вече е true
│       ├── записва в stream
│       └── НЕ извиква CloseTransactionStream()
│
├── StateRecovery::SaveState<ReelingSubstate>()
│   └── m_stateData.Save2()
│       └── CloseOStream("sd")
│           ├── записва State ID в stream
│           └── НЕ извиква CloseTransactionStream()
│
└── CloseTransaction()
    ├── s_persistanceStream->CloseTransactionStream()
    │   └── m_isChanged = true     ◄── СЕГА чак main loop ще види промяната
    ├── s_transactionInAction = false
    └── s_transactionIsOpen = false


Без транзакция (директен Save2):
│
├── GameData::Save2()
│   └── CloseOStream("gd")
│       ├── s_transactionIsOpen == false
│       ├── записва в stream
│       └── CloseTransactionStream()     ◄── веднага m_isChanged = true
│
└── (State ID НЕ се обновява)
```

---

## Какво НЕ се персистира

```
FSM State обекти (boost::statechart states):
┌──────────────────────────────────────┐
│ ReelingSubstate                      │
│   m_currentTime = 0.f       ← НЕ    │  ← Транзиентни!
│   m_reelingTime = 0.7f      ← НЕ    │     Създават се наново
│   m_rngTimeout = 8.f        ← НЕ    │     при transit<T>()
│   m_randomReceived = false   ← НЕ    │     с default стойности.
│   m_setContent = false       ← НЕ    │
│   m_committedTakeCredit = false ← НЕ │     Разчитат на GameData
└──────────────────────────────────────┘     за recovery.

При recovery:
  1. StateRecovery::GetStateId() → "struct ReelingSubstate"
  2. transit<ReelingSubstate>() → НОВ обект с defaults
  3. ReelingSubstate конструкторът чете от GameData
     (bet, outcome, waitingForRng, etc.)
```

---

## Два типа Save — сравнение

```
┌──────────────────────────┬────────────────────────────┐
│  SaveGameState<T>(flags) │  Директен Save2()          │
├──────────────────────────┼────────────────────────────┤
│  Транзакция: ДА          │  Транзакция: НЕ            │
│  State ID: записва се    │  State ID: НЕ се променя   │
│  GameData: по flags      │  GameData: записва се      │
│  Атомарност: всичко      │  Атомарност: само           │
│    заедно                │    един сектор              │
│  Кога: при смяна на      │  Кога: при промяна само    │
│    FSM state или         │    на данни, без смяна     │
│    критични данни        │    на state                │
│  Пример:                 │  Пример:                   │
│    SaveGameState          │    GetGameData().Save2()   │
│    <Reeling>(eGameData)  │    в CommComponent или     │
│                          │    PayGameResults          │
└──────────────────────────┴────────────────────────────┘
```

---

## AstroEgtState — пълна структура

```cpp
struct AstroEgtState : Data<AstroEgtState>
{
    int gameStepSeq = 0;              // Sequence number: 0=start, N=step, -1=end
    std::vector<uint8_t> pendingMsg;  // Серализирано ca_game_start/step/end
    bool isCurrentRoundGamble = false;
    std::string matchName;            // Текущ match ("main")
    std::string roundName;            // Текущ round
    uint64_t matchInitialBet = 0;     // Начален залог

    AnyData gameState;                // ← BLOB от StreamPersistance::Dump()
};                                    //    съдържа ВСИЧКИ PersistantClass сектори
```

**Връзка с транзакциите:** Няма директна. `AstroEgtState` не знае за `PersistanceMemory` транзакции. Тя получава готови байтове чрез `SaveState()` и записва целия си state в NVRAM чрез `SaveAsyncToNvram()`.

**Кога се мутира `AstroEgtState`:**
- `StateMutable().pendingMsg = ...` — при `_saveAndSendMsg()` (protocol layer)
- `StateMutable().gameStepSeq = ...` — при `RequestRoundOutcome()`, `RequestEndMatch()`
- `StateMutable().gameState = ...` — при `SaveState(storage)` (от main loop)
- Всяко `StateMutable()` вдига `m_newState = true` → NVRAM запис при следващия tick

---

*Генериран на 2026-03-11 въз основа на изходен код от italy_games и анализ на persistence архитектурата.*
