# Recovery система на Playground интеграцията

## Съдържание

1. [Какво е Recovery и защо е нужно](#1-какво-е-recovery-и-защо-е-нужно)
2. [Какво се записва](#2-какво-се-записва)
3. [Къде се записва — RecoveryManager](#3-къде-се-записва--recoverymanager)
4. [Как модулите се регистрират — RecoveryState\<T\>](#4-как-модулите-се-регистрират--recoverystatet)
5. [Кога и как се записва (Save)](#5-кога-и-как-се-записва-save)
6. [Кога и как се зарежда (Load)](#6-кога-и-как-се-зарежда-load)
7. [Пример от край до край](#7-пример-от-край-до-край)
8. [Ключови файлове](#8-ключови-файлове)

---

## 1. Какво е Recovery и защо е нужно

При неочаквано прекъсване (crash, рестарт, загуба на захранване) играчът трябва да продължи **от точката, в която е бил** — без загуба на пари и без повторно генериране на резултати. Recovery системата решава точно този проблем: периодично записва състоянието на играта, за да може при рестарт да го възстанови.

---

## 2. Какво се записва

Играта има **два вида състояние**, които трябва да оцелеят при crash:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ВИЗУАЛНО СЪСТОЯНИЕ (FSM)              БИЗНЕС СЪСТОЯНИЕ (Gameflow)     │
│   "В кой екран е играта?"               "Колко пари има играчът?"       │
│                                                                         │
│   ┌────────────────────────┐            ┌────────────────────────┐      │
│   │ Текущ FSM state:       │            │ match:                 │      │
│   │   Idle, Spin, Win...   │            │   creditBet: 100       │      │
│   │                        │            │   wallet: {...}        │      │
│   │ NVRAM данни:           │            │                        │      │
│   │   позиции на барабани  │            │ round:                 │      │
│   │   текущи анимации      │            │   result: {win: 500}   │      │
│   │   показвани стойности  │            │   kernelOutcome: true  │      │
│   └────────────────────────┘            └────────────────────────┘      │
│                                                                         │
│   Управлява: GameFsm                   Управлява: AlphaFamilyGameflow   │
│   Записва: PlaygroundRecovery          Записва: AlphaFamilyGameflow     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Визуално състояние — PlaygroundRecoveryState

Това е **FSM snapshot** — в кой state (екран) е играта и какви данни има всеки state.

```cpp
// integration/playground/.../PlaygroundRecovery.data.h
struct PlaygroundRecoveryState : Data<PlaygroundRecoveryState>
{
    Game::RecoveryData gameStateRecoveryData;  // Единственото поле — FSM пакет
};
```

Вътре стои `RecoveryData` — пакет, който GameFsm създава при сериализация:

```cpp
// game/libs/src/Egt/Game/RuntimeImport/IRecovery.data.h
struct RecoveryData : Data<RecoveryData>
{
    MonotonicId id = 0;     // Версия (за dirty check — "променило ли се е от последния save?")
    std::string label;      // Четимо описание: "Main:Idle", "Main:Spin", "Main:Win"
    AnyData data;           // Сериализирано FSM дърво (MachineImplSerializeStorage)
};
```

А вътре в `data` стои FSM дървото:

```cpp
// game/libs/src/Egt/Fsm/MachineImpl.data.h
struct MachineImplSerializeStorage : Data<MachineImplSerializeStorage>
{
    uint64_t leafStateHash;                                  // В кой state е бил FSM
    std::map<uint64_t, std::vector<AnyData>> nvramsByState;  // NVRAM данни по state
};
```

Пълната верига на влагане:

```
m_nvram.records[hash("PlaygroundRecoveryState")]
    └── AnyData
        └── PlaygroundRecoveryState
            └── gameStateRecoveryData: RecoveryData
                ├── id: 12
                ├── label: "Main:Spin"
                └── data: AnyData
                    └── MachineImplSerializeStorage
                        ├── leafStateHash: hash("Spin")
                        └── nvramsByState: { hash("Spin") → [reelPositions, ...] }
```

### 2.2 Бизнес състояние — AlphaFamilyGameflowState

Това е финансово/протоколно състояние — залог, портфейл, резултат от рунд, потвърждения от kernel.

```cpp
// integration/plugins/.../AlphaFamilyGameflow.data.h
struct AlphaFamilyGameflowState : Data<AlphaFamilyGameflowState>
{
    std::optional<AlphaFamilyGameflowMatch> match;  // Текущ мач (ако има)
    std::optional<AlphaFamilyGameflowRound> round;  // Текущ рунд (ако има)
};

struct AlphaFamilyGameflowMatch
{
    int64_t creditBet = 0;
    bool kernelStarted = false;
    std::vector<ConsecutiveRoundInfo> consecutives;  // Free spins/bonus info
    Wallet wallet;                                    // rewarded & consumed currencies
};

struct AlphaFamilyGameflowRound
{
    RoundInput input;                      // Входни данни (тип рунд, залог)
    std::optional<RoundResult> result;     // Math резултат (ако вече е изчислен)
    bool kernelStarted = false;            // Kernel потвърдил ли е рунда
    bool kernelOutcome = false;            // Kernel потвърдил ли е изхода
    bool kernelGamble = false;             // Kernel потвърдил ли е gamble
};
```

Тук няма влагане — директно в map-а:

```
m_nvram.records[hash("AlphaFamilyGameflowState")]
    └── AnyData
        └── AlphaFamilyGameflowState
            ├── match: { creditBet: 100, wallet: {...}, ... }
            └── round: { input: {...}, result: {win: 500}, ... }
```

Когато мач или рунд приключи, съответното optional поле става `nullopt`. Records никога не се премахват от map-а — при recovery, ако match и round са `nullopt`, играта знае, че е била в Idle.

---

## 3. Къде се записва — RecoveryManager

И двата вида данни живеят в **един общ контейнер** — `RecoveryManagerState`. RecoveryManager е единственият компонент, който комуникира с kernel.

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.h
class RecoveryManager {
private:
    RecoveryManagerConfig m_config;   // Конфигурация (празна в момента)
    RecoveryManagerState m_nvram;     // ГЛАВНОТО ХРАНИЛИЩЕ
    MonotonicId m_touchId = {};       // Брояч за промени (++при всяка модификация)
    MonotonicId m_savedId = {};       // Стойността на m_touchId при последния save
    std::string m_label;              // Описание (напр. "Main:Spin")
};
```

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.data.h
struct RecoveryManagerState : Data<RecoveryManagerState>
{
    std::map<uint64_t, AnyData> records;  // hash(TypeName) → данни на модула
};
```

Целият `m_nvram` се записва и чете като един blob:

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  m_nvram.records                                                     │
│  ├── [hash("PlaygroundRecoveryState")]  → FSM snapshot               │
│  └── [hash("AlphaFamilyGameflowState")] → match/round данни          │
│                                                                      │
│          │ SAVE                                  │ LOAD              │
│          ▼                                       ▼                   │
│  PackIData(m_nvram) → binary blob       binary blob → UnpackIData()  │
│          │                                       │                   │
│          ▼                                       ▼                   │
│  kernel.SaveState(GameState)            kernel.RecoverState()        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

`AnyData` е type-erased контейнер — вътрешно държи `Ptr<IData> data` (shared pointer). Поддържа `CreateEmpty<T>()` и `Cast<T>()` (с type hash проверка за безопасност).

Kernel получава структура `IKernelApi::GameState`:

```cpp
// integration/libs/src/Egt/KernelApi/IKernelApi.h
struct GameState
{
    uint64_t id = 0;           // Версия на състоянието (m_touchId)
    std::string label;         // Четимо описание (напр. "Main:Spin")
    std::vector<uint8_t> data; // Бинарни данни — ЦЕЛИЯТ m_nvram сериализиран
};
```

### 3.1 Dirty tracking — TouchID механизъм

RecoveryManager следи дали има промени чрез два брояча:

- **`m_touchId`** — инкрементира се при **всяка** модификация от който и да е модул
- **`m_savedId`** — стойността на `m_touchId` към момента на последния успешен save

При `SaveState()`: ако `m_touchId == m_savedId` → нищо не се записва (SKIP). Това предотвратява излишни kernel извиквания.

| Събитие | m_touchId | m_savedId | Действие |
|---------|-----------|-----------|----------|
| Init (fresh) | 0 | 0 | — |
| Модул извика `State()` | 1 | 0 | `m_touchId++` |
| `SaveState()` извикан | 1 | 1 | Записва, `m_savedId = m_touchId` |
| `SaveState()` (без промени) | 1 | 1 | **SKIP** |
| Нов `State()` call | 2 | 1 | `m_touchId++` |

---

## 4. Как модулите се регистрират — RecoveryState\<T\>

За да записва данни в RecoveryManager, модулът наследява private `RecoveryState<T>`:

```cpp
// integration/libs/src/Egt/Integration/Recovery/RecoveryState.h
template <typename T>
class RecoveryState
{
private:
    IRecoveryManager* m_manager;
    Ptr<T> m_state;              // shared_ptr<T> → сочи в m_nvram.records

public:
    void InitRecoveryState(RuntimeAccess runtime)
    {
        m_manager = &runtime.Get<IRecoveryManager>();
        const auto id = StaticData<T>::GetStaticTypeHash();
        auto& record = m_manager->Record(id);

        if (record.IsEmpty())
            m_state = record.CreateEmpty<T>();   // Fresh start
        else
            m_state = record.Cast<T>();          // Recovery — данните вече са заредени
    }

    T& State()                 { TouchState(); return *m_state; }   // Маркира dirty + достъп
    const T& ConstState() const { return *m_state; }                // Само четене
    MonotonicId TouchState()   { return m_manager->TouchState(); }  // ++m_touchId
};
```

**Как `m_state` сочи директно в map-а:**

`m_state` и `AnyData::data` вътре в `m_nvram.records[hash(T)]` сочат към **един и същ обект** в паметта:

```
RecoveryManager::m_nvram.records
    └── [hash(T)] → AnyData
                        └── data: Ptr<IData>  ──┐
                                                │  същият обект
RecoveryState<T>::m_state: Ptr<T>  ─────────────┘
```

Затова `State().match.emplace()` модифицира данните **директно в map-а** — без копиране. Достъпът е типизиран — всеки модул вижда само своя тип `T` и не може да достъпи данните на друг модул.

### 4.1 Текущи модули

Към момента в codebase-а има **точно 2 модула**, регистрирани чрез `RecoveryState<T>`:

| # | Модул | State тип | Записва | Извиква SaveState()? |
|---|-------|-----------|---------|----------------------|
| 1 | **PlaygroundRecovery** | `PlaygroundRecoveryState` | FSM snapshot (чрез GameFsm) | **ДА — единственият** |
| 2 | **AlphaFamilyGameflow** | `AlphaFamilyGameflowState` | Бизнес данни (match/round) | НЕ — само маркира dirty |

PlaygroundRecovery има допълнителна роля: имплементира `IRecovery` интерфейса и служи като мост между GameFsm (Game layer) и RecoveryManager (Integration layer).

Другите интеграции (Inspired, Astro, HAT) имат skeleton `IRecovery` имплементации, но не използват `RecoveryState<T>`.

---

## 5. Кога и как се записва (Save)

### 5.1 Кой извиква SaveState()

**Само `PlaygroundRecovery::OnRecoverySavePoint()`** — това е единственото място в целия codebase, което тригерира запис. Извиква се от `PlaygroundGame::Update()` чрез event `recoverySavePoint.Post()` при **всеки frame**.

```cpp
// integration/playground/.../PlaygroundRecovery.cpp
void PlaygroundRecovery::OnRecoverySavePoint()
{
    // Стъпка 1: Проверява дали FSM се е променил
    auto& gameState = RuntimeGet<IGameState>();
    if (auto newData = gameState.SerializeIfModified(ConstState().gameStateRecoveryData.id))
    {
        State().gameStateRecoveryData = std::move(*newData);  // m_touchId++
    }

    // Стъпка 2: Записва ВСИЧКИ данни от m_nvram (ако нещо е dirty)
    auto& recoveryManager = RuntimeGet<IRecoveryManager>();
    recoveryManager.SaveState(ConstState().gameStateRecoveryData.label);
}
```

**Стъпка 1** проверява FSM-а чрез `SerializeIfModified(prevId)`. Ако FSM не се е променил — връща `nullopt` и нищо не се записва. Ако се е променил — GameFsm пакетира FSM дървото в `RecoveryData` и PlaygroundRecovery го записва в своя state.

**Стъпка 2** извиква `RecoveryManager::SaveState()`, който проверява `m_touchId != m_savedId`. Ако нито FSM, нито Gameflow данни са се променили — SKIP. Ако нещо е dirty — сериализира **целия** `m_nvram` и го изпраща към kernel.

### 5.2 Какво правят другите модули

Нито GameFsm, нито AlphaFamilyGameflow извикват `SaveState()`. Те само маркират данните като dirty:

```cpp
// AlphaFamilyGameflow — при бизнес събития
State().match.emplace();          // m_touchId++ — маркира dirty
State().match->creditBet = bet;   // m_touchId++

// GameFsm — при state transitions
Transit("Idle" → "Spin");        // вътрешен dirty flag → m_recoveryDataId++
```

Реалният запис идва по-късно, в края на frame-а, когато `OnRecoverySavePoint()` провери и запише всичко наведнъж.

### 5.3 Как label стига до kernel

`label` описва текущия FSM state (напр. `"Main:Spin"`). Веригата:

```
GameFsm: m_machine->DumpShort()  →  "Main:Spin"
    ▼
RecoveryData.label = "Main:Spin"
    ▼
PlaygroundRecovery: State().gameStateRecoveryData = newData
    ▼
recoveryManager.SaveState( ConstState().gameStateRecoveryData.label )
    ▼
RecoveryManager: gameState.label = "Main:Spin"  →  kernel.SaveState(gameState)
```

### 5.4 Как RecoveryData.id се инкрементира

Когато FSM промени състоянието си, тригерира верига от callbacks:

```
FSM промяна (state transition / NVRAM update)
    ▼
m_machine callback (SetRecoveryDataDirtyCallback)
    ▼
GameFsm::TouchState()
    ▼
IRecovery::TouchGameState()              ← PlaygroundRecovery
    ▼
RecoveryState<T>::TouchState()
    ▼
RecoveryManager::TouchState()  →  ++m_touchId
    ▼
m_recoveryDataId = върнатата стойност    ← GameFsm пази локално копие
```

При `SerializeIfModified(prevId)`: ако `prevId == m_recoveryDataId` → FSM не се е променил → `nullopt`. Иначе се сериализира.

### 5.5 SaveState() имплементация

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.cpp
void RecoveryManager::SaveState(std::string label)
{
    assert(m_savedId <= m_touchId);
    ReturnIf(m_savedId == m_touchId);        // Няма промени → SKIP

    m_label = std::move(label);

    IKernelApi::GameState gameState;
    gameState.id = m_touchId;
    gameState.label = m_label;
    gameState.data = DataTools::PackIData(m_nvram);  // Сериализира ЦЕЛИЯ m_nvram

    auto& kernel = RuntimeGet<IKernelIntegration>();
    kernel.GetKernelApi().SaveState(std::move(gameState));
    m_savedId = m_touchId;                   // Всичко е записано
}
```

`PackIData(m_nvram)` сериализира целия `m_nvram.records` map — и двата записа (PlaygroundRecoveryState + AlphaFamilyGameflowState) се пакетират в един бинарен blob и се изпращат с едно kernel извикване.

### 5.6 Пълен timeline на един frame

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ФАЗА 1: GAME LOGIC (между save points)                                │
│                                                                         │
│   AlphaFamilyGameflow:                                                  │
│       State().match.emplace()     → m_touchId++                         │
│       State().round.emplace()     → m_touchId++                         │
│                                                                         │
│   GameFsm:                                                              │
│       Transit("Idle" → "Spin")    → m_recoveryDataId++                  │
│                                                                         │
│   ФАЗА 2: SAVE POINT (край на frame)                                    │
│                                                                         │
│   PlaygroundGame::Update()                                              │
│       └─► recoverySavePoint.Post()                                      │
│               │                                                         │
│               ▼                                                         │
│   PlaygroundRecovery::OnRecoverySavePoint()                             │
│       ├─► GameFsm.SerializeIfModified(lastId)                           │
│       │       └─► Променен? → RecoveryData / Непроменен? → nullopt      │
│       │                                                                 │
│       ├─► State().gameStateRecoveryData = newData (ако има)             │
│       │                                                                 │
│       └─► recoveryManager.SaveState(label)                              │
│               └─► m_touchId != m_savedId?                               │
│                   ├─► ДА → PackIData(m_nvram) → kernel.SaveState()      │
│                   └─► НЕ → SKIP                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.7 Презаписване и "триене"

`SaveState()` винаги записва **пълен snapshot** — не частичен update. Всеки save заменя предишния изцяло.

"Триене" на данни не съществува в буквален смисъл. Optional полетата стават `nullopt`:

```cpp
State().match = {};  // match → nullopt, но записът в m_nvram.records остава
State().round = {};  // round → nullopt
```

---

## 6. Кога и как се зарежда (Load)

При стартиране на играта модулите се инициализират в определен ред. **PlaygroundRecovery е първият** компонент (коментар в кода: "Recovery should be first"), защото всички останали зависят от заредените recovery данни.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  СТЪПКА 1: PlaygroundRecovery::Init()                                   │
│                                                                         │
│   recoveryManager.LoadState()                                           │
│       ├─► kernel.RecoverState() → GameState { id, label, binary data }  │
│       ├─► m_savedId = m_touchId = gameState.id  (синхронизирани)        │
│       └─► UnpackIData(m_nvram, data)                                    │
│               └─► m_nvram.records се попълва                            │
│                   (PlaygroundRecoveryState + AlphaFamilyGameflowState)  │
│                                                                         │
│   InitRecoveryState(GetRuntime())                                       │
│       └─► record.Cast<PlaygroundRecoveryState>()                        │
│           └─► m_state вече съдържа gameStateRecoveryData                │
│       (Ако record е празен → fresh start, CreateEmpty)                  │
│                                                                         │
│  СТЪПКА 2: AlphaFamilyGameflow::Init()                                  │
│                                                                         │
│   InitRecoveryState(GetRuntime())                                       │
│       └─► record.Cast<AlphaFamilyGameflowState>()                       │
│           └─► match/round от предишна сесия са достъпни                 │
│                                                                         │
│   RecoverRoundRng()                                                     │
│       └─► Ако round->kernelStarted && !round->kernelOutcome:            │
│               └─► RNG engine се пресъздава (празен)                     │
│                   (volatile данни НЕ се записват в recovery)            │
│                                                                         │
│  СТЪПКА 3: GameFsm::Init()                                              │
│                                                                         │
│   recovery.DeserializeGameState()                                       │
│       └─► Връща RecoveryData от PlaygroundRecoveryState                 │
│                                                                         │
│   recoveryData.data.IsEmpty()?                                          │
│       ├─► НЕ → m_machine->InitFull(runtime, recoveryData.data)          │
│       │       └─► FSM десериализира MachineImplSerializeStorage         │
│       │           └─► Възстановява се в точния leaf state + NVRAM       │
│       └─► ДА → m_machine->InitFull(runtime, {})                         │
│               └─► FSM стартира от начално състояние                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**LoadState() имплементация:**

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.cpp
void RecoveryManager::LoadState()
{
    auto& kernel = RuntimeGet<IKernelIntegration>();
    auto gameState = kernel.GetKernelApi().RecoverState();

    m_savedId = gameState.id;
    m_touchId = m_savedId;                          // Синхронизирани — няма pending промени
    m_label = std::move(gameState.label);
    DataTools::UnpackIData(m_nvram, gameState.data); // Binary → m_nvram.records
}
```

**Recovery сценарии при зареждане:**

| match | round | Какво се случва |
|-------|-------|-----------------|
| nullopt | nullopt | Нормален старт — играта е била Idle |
| {...} | nullopt | Match е стартиран, чака се round |
| {...} | {..., result: {...}} | Round in progress, math е вече изчислен — продължава от резултата |
| {...} | {..., kernelStarted, !kernelOutcome} | Round чака kernel — RNG engine се пресъздава |

---

## 7. Пример от край до край

Играч натиска Spin с bet=100. Следваме данните от StartMatch до crash и recovery.

### Frame 1: StartMatch

AlphaFamilyGameflow записва бизнес данни:
```cpp
State().match.emplace();            // m_touchId: 0→1
State().match->creditBet = 100;     // m_touchId: 1→2
State().match->kernelStarted = true;
```

GameFsm преминава в BetConfirm state → `m_recoveryDataId++`

В края на frame-а `OnRecoverySavePoint()` записва snapshot #1:

```
m_nvram.records:
├── [PlaygroundRecoveryState]
│       └── RecoveryData { id: 3, label: "Main:BetConfirm", data: FSM blob }
│
└── [AlphaFamilyGameflowState]
        ├── match: { creditBet: 100, kernelStarted: true, wallet: {...} }
        └── round: nullopt
```

### Frame 50: StartRound + Math резултат

```cpp
State().round.emplace();                    // m_touchId++
State().round->input = { roundType: Main };
State().round->result = { win: 500 };       // Math вече изчислен!
State().round->kernelOutcome = true;
```

GameFsm преминава в Spin → `m_recoveryDataId++`

Snapshot #2:
```
m_nvram.records:
├── [PlaygroundRecoveryState]
│       └── RecoveryData { id: 8, label: "Main:Spin", data: FSM blob }
│
└── [AlphaFamilyGameflowState]
        ├── match: { creditBet: 100, wallet: { rewarded: {Credits: 500}, consumed: {Energy: 100} } }
        └── round: { input: {Main}, result: {win: 500}, kernelOutcome: true }
```

### Frame 75: CRASH

Захранването спира. Последният записан snapshot е #2.

### Рестарт: Recovery

**Стъпка 1:** `RecoveryManager::LoadState()` чете binary blob от kernel, `UnpackIData()` възстановява `m_nvram.records` с двата записа.

**Стъпка 2:** `AlphaFamilyGameflow::InitRecoveryState()` → `Cast<AlphaFamilyGameflowState>()` → match и round са достъпни с всичките си данни. `round->result` вече е изчислен — **няма ново RNG**.

**Стъпка 3:** `GameFsm::Init()` → `DeserializeGameState()` → получава `RecoveryData` → `InitFull()` с `MachineImplSerializeStorage` → FSM се възстановява в **"Spin"** state с NVRAM данни (позиции на барабани и т.н.).

**Резултат:** Играта продължава от показване на резултата от spin-а. Играчът не забелязва прекъсването.

---

## 8. Ключови файлове

### Recovery инфраструктура

| Файл | Роля |
|------|------|
| `integration/libs/src/Egt/Integration/Recovery/RecoveryState.h` | Template за регистриране на модул |
| `integration/libs/src/Egt/Integration/Runtime/IRecoveryManager.h` | Интерфейс на RecoveryManager |
| `integration/plugins/src/Egt/RecoveryManager/RecoveryManager.cpp` | SaveState / LoadState имплементация |
| `integration/plugins/src/Egt/RecoveryManager/RecoveryManager.data.h` | RecoveryManagerState, Config |
| `integration/libs/src/Egt/KernelApi/IKernelApi.h` | IKernelApi::GameState, SaveState/RecoverState |

### Playground recovery

| Файл | Роля |
|------|------|
| `integration/playground/.../PlaygroundRecovery.cpp` | Единственият SaveState caller + IRecovery мост |
| `integration/playground/.../PlaygroundRecovery.data.h` | PlaygroundRecoveryState |

### Gameflow

| Файл | Роля |
|------|------|
| `integration/plugins/.../AlphaFamilyGameflow/AlphaFamilyGameflow.cpp` | Бизнес логика (match/round) |
| `integration/plugins/.../AlphaFamilyGameflow/AlphaFamilyGameflow.data.h` | AlphaFamilyGameflowState, Match, Round |

### Game layer (FSM)

| Файл | Роля |
|------|------|
| `game/libs/src/Egt/Game/RuntimeImport/IRecovery.data.h` | RecoveryData, MonotonicId |
| `game/libs/src/Egt/Game/RuntimeExport/IGameState.h` | IGameState (SerializeIfModified) |
| `game/libs/src/Egt/Game/Fsm/GameFsm.cpp` | FSM сериализация/десериализация |
| `game/libs/src/Egt/Fsm/MachineImpl.data.h` | MachineImplSerializeStorage |
