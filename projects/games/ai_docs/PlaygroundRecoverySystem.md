# Recovery система на Playground интеграцията

## Съдържание

1. [Общ преглед](#1-общ-преглед)
2. [Архитектура](#2-архитектура)
3. [Структури на данните](#3-структури-на-данните)
4. [Save и Load механизми](#4-save-и-load-механизми)
5. [Конкретни примери](#5-конкретни-примери)
6. [Ключови файлове](#6-ключови-файлове)

---

## 1. Общ преглед

Recovery системата осигурява **персистентност на състоянието** на играта при неочаквано прекъсване (crash, рестарт, загуба на захранване). Целта е играчът да продължи от точката, в която е бил, без загуба на финансови данни или визуално състояние.

### Как работи накратко

Всички recovery данни от **всички модули** се съхраняват в един общ контейнер — `RecoveryManagerState`. Този контейнер съдържа map от записи, като **всеки модул** записва под свой уникален hash ключ. При save, **целият контейнер** се сериализира в бинарен формат и се изпраща към kernel **с едно единствено извикване**. При load — обратният процес.

```
┌────────────────────────────────────────────────────────────────────────┐
│                    КАКВО СЕ ЗАПИСВА В KERNEL                           │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   RecoveryManagerState                                                 │
│   └── records: map<uint64_t, AnyData>                                  │
│       │                                                                │
│       ├── [hash("PlaygroundRecoveryState")]                            │
│       │       └── gameStateRecoveryData (FSM състояние)                │
│       │                                                                │
│       └── [hash("AlphaFamilyGameflowState")]                           │
│               ├── match (бизнес логика на мач)                         │
│               └── round (бизнес логика на рунд)                        │
│                                                                        │
│   ═══════════════════════════ SAVE ══════════════════════════════════  │
│           PackIData(m_nvram)  →  std::vector<uint8_t>                  │
│                                       │                                │
│                               kernel.SaveState()                       │
│                                                                        │
│   ═══════════════════════════ LOAD ══════════════════════════════════  │
│           kernel.RecoverState()  →  std::vector<uint8_t>               │
│                                       │                                │
│                               UnpackIData(m_nvram)                     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

**Към момента в codebase-а има точно 2 модула**, които регистрират recovery данни:

| Модул | Регистриран state тип | Какво записва |
|-------|-----------------------|---------------|
| **PlaygroundRecovery** | `PlaygroundRecoveryState` | FSM състояние (в кой екран е играта) |
| **AlphaFamilyGameflow** | `AlphaFamilyGameflowState` | Бизнес логика (bet, wallet, round result) |

И двата модула записват в **един и същ** `m_nvram.records` map, но под **различни** hash ключове. Когато `SaveState()` бъде извикан, **и двата записа** се сериализират и записват **атомарно** с едно kernel извикване.

---

## 2. Архитектура

### 2.1 Слоеве и компоненти

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              GAME LAYER                                 │
│                        (game/libs/src/Egt/)                             │
│                                                                         │
│    ┌─────────────┐                                                      │
│    │   GameFsm   │  ← Имплементира IGameState                           │
│    │             │  ← НЕ знае за RecoveryManager                        │
│    └──────┬──────┘                                                      │
│           │ SerializeIfModified() → RecoveryData                        │
│           │ DeserializeGameState() ← RecoveryData                       │
├───────────┼─────────────────────────────────────────────────────────────┤
│           │            INTEGRATION LAYER                                │
│           ▼       (integration/plugins/src/Egt/)                        │
│                                                                         │
│    ┌──────────────────┐      ┌────────────────────────┐                 │
│    │PlaygroundRecovery│      │ AlphaFamilyGameflow    │                 │
│    │                  │      │                        │                 │
│    │ Взима FSM данни  │      │ Записва директно       │                 │
│    │ чрез IGameState  │      │ чрез State()           │                 │
│    └────────┬─────────┘      └───────────┬────────────┘                 │
│             │                            │                              │
│             └────────────┬───────────────┘                              │
│                          ▼                                              │
│    ┌────────────────────────────────────────────────────────────────┐   │
│    │                      RecoveryManager                           │   │
│    │  m_nvram.records: map<hash, AnyData>  ← ВСИЧКИ данни           │   │
│    │  m_touchId / m_savedId: dirty tracking                         │   │
│    │                                                                │   │
│    │  SaveState(): PackIData(m_nvram) → kernel (АТОМАРНО)           │   │
│    │  LoadState(): kernel → UnpackIData(m_nvram)                    │   │
│    └────────────────────────┬───────────────────────────────────────┘   │
│                              │                                          │
│                              ▼                                          │
│    ┌────────────────────────────────────────────────────────────────┐   │
│    │                        IKernelApi                              │   │
│    │  SaveState(GameState) / RecoverState() → GameState             │   │
│    └────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 RecoveryManager — централен persistence manager

RecoveryManager е **единственият компонент**, който комуникира с kernel за запис/четене. Държи **всички** recovery данни от **всички** модули в едно хранилище — `m_nvram`.

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.h

class RecoveryManager {
private:
    RecoveryManagerConfig m_config;   // Конфигурация (празна в момента)
    RecoveryManagerState m_nvram;     // ГЛАВНОТО ХРАНИЛИЩЕ — map с ВСИЧКИ модули
    MonotonicId m_touchId = {};       // Брояч за промени (++при всяка модификация)
    MonotonicId m_savedId = {};       // Стойността на m_touchId при последния save
    std::string m_label;              // Описание за текущото състояние
};
```

`RecoveryManagerState` е контейнерът, който се сериализира целият:

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.data.h

struct RecoveryManagerState : Data<RecoveryManagerState>
{
    std::map<uint64_t, AnyData> records;  // hash(TypeName) → данни на модула
};
```

**AnyData** е type-erased контейнер — може да държи данни от всякакъв тип, наследяващ `Data<T>`. Вътрешно съдържа `Ptr<IData> data` (shared pointer). Може да се създаде с `CreateEmpty<T>()` или да се достъпи с `Cast<T>()`, като Cast проверява type hash за безопасност.

**Как работи `SaveState()`:**

```cpp
// integration/plugins/src/Egt/RecoveryManager/RecoveryManager.cpp

void RecoveryManager::SaveState(std::string label)
{
    assert(m_savedId <= m_touchId);
    ReturnIf(m_savedId == m_touchId);       // Ако няма промени → SKIP

    m_label = std::move(label);

    IKernelApi::GameState gameState;
    gameState.id = m_touchId;
    gameState.label = m_label;
    gameState.data = DataTools::PackIData(m_nvram);   // Сериализира ЦЕЛИЯ m_nvram

    auto& kernel = RuntimeGet<IKernelIntegration>();
    kernel.GetKernelApi().SaveState(std::move(gameState));  // Изпраща към kernel
    m_savedId = m_touchId;                  // Маркира "всичко е записано"
}
```

`PackIData(m_nvram)` сериализира **целия** `m_nvram` (JSON → binary):
- Обхожда `m_nvram.records` map-а
- Сериализира **всяко** AnyData поле (PlaygroundRecoveryState, AlphaFamilyGameflowState и др.)
- Връща `std::vector<uint8_t>` — един бинарен blob с всичко

**Kernel получава `IKernelApi::GameState`:**

```cpp
// integration/libs/src/Egt/KernelApi/IKernelApi.h

struct GameState
{
    uint64_t id = 0;           // Версия на състоянието
    std::string label;         // Четимо описание (напр. "Main:Spin")
    std::vector<uint8_t> data; // Бинарни данни от PackIData(m_nvram)
};
```

**Touch ID механизъм** — оптимизация за избягване на излишни saves:

| Събитие | m_touchId | m_savedId | Действие |
|---------|-----------|-----------|----------|
| Init (fresh) | 0 | 0 | — |
| Модул извика State() | 1 | 0 | `TouchState()` → `m_touchId++` |
| `SaveState()` извикан | 1 | 1 | touchId != savedId → записва, `m_savedId = m_touchId` |
| `SaveState()` (без промени) | 1 | 1 | touchId == savedId → **SKIP** |
| Нов State() call | 2 | 1 | `TouchState()` → `m_touchId++` |

### 2.3 RecoveryState\<T\> — template за регистриране на модул

`RecoveryState<T>` е базов клас (private наследяване), който дава на модула възможност да записва и чете свой тип данни `T` в `m_nvram.records`.

```cpp
// integration/libs/src/Egt/Integration/Recovery/RecoveryState.h

template <typename T>
class RecoveryState
{
private:
    IRecoveryManager* m_manager;  // Указател към RecoveryManager
    Ptr<T> m_state;               // Сочи ДИРЕКТНО към данните в m_nvram.records[hash(T)]

public:
    void InitRecoveryState(RuntimeAccess runtime)
    {
        m_manager = &runtime.Get<IRecoveryManager>();
        const auto id = StaticData<T>::GetStaticTypeHash();  // Уникален hash за типа T
        auto& record = m_manager->Record(id);                // Взима/създава запис в map-а

        if (record.IsEmpty())
            m_state = record.CreateEmpty<T>();  // Fresh start: нов празен обект
        else
            m_state = record.Cast<T>();         // Recovery: cast от заредените данни
    }

    T& State()                 { TouchState(); return *m_state; }  // Маркира dirty + достъп
    const T& ConstState() const { return *m_state; }               // Само четене, без dirty

    MonotonicId TouchState()   { return m_manager->TouchState(); } // ++m_touchId
};
```

**Как `m_state` сочи директно в map-а на RecoveryManager:**

`m_state` е `Ptr<T>` (`std::shared_ptr<T>`). Той сочи към **същия обект**, към който сочи `AnyData::data` (`Ptr<IData>`) вътре в `m_nvram.records[hash(T)]`:

```
RecoveryManager::m_nvram.records
    │
    └── [hash(T)] → AnyData                       (в map-а)
                        └── data: Ptr<IData>  ──┐
                                                │  същият обект в паметта
RecoveryState<T>::m_state: Ptr<T>  ─────────────┘
```

При `InitRecoveryState()`:
- `record.CreateEmpty<T>()` създава `shared_ptr<T>`, записва го в `record.data` и връща **същия** pointer
- `record.Cast<T>()` прави `static_pointer_cast<T>(record.data)` — отново **същият** обект

Затова когато модулът пише `State().match.emplace()`, промяната е **директно в map-а** на RecoveryManager — без копиране. Всяка промяна през `State()` автоматично:
1. Инкрементира `m_touchId` в RecoveryManager (маркира dirty)
2. Модифицира данните **директно в map-а** (чрез shared pointer)

**Достъпът е типизиран** — всеки модул вижда само своя тип `T`. PlaygroundRecovery **не може** да достъпи AlphaFamilyGameflowState и обратно.

### 2.4 Текущи модули, използващи RecoveryState\<T\>

Към момента в codebase-а има **точно 2 модула**, регистрирани чрез `RecoveryState<T>`:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    МОДУЛИ С RECOVERY STATE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. PlaygroundRecovery : private RecoveryState<PlaygroundRecoveryState> │
│     ├── Файл: integration/playground/.../PlaygroundRecovery.h           │
│     ├── Отговорност: пази FSM състоянието                               │
│     ├── State тип: PlaygroundRecoveryState                              │
│     │   └── gameStateRecoveryData: RecoveryData (FSM snapshot)          │
│     └── Допълнителна роля: имплементира IRecovery интерфейса,           │
│         извиква SaveState() и служи като мост между GameFsm и           │
│         RecoveryManager                                                 │
│                                                                         │
│  2. AlphaFamilyGameflow : private RecoveryState<AlphaFamilyGameflowState>│
│     ├── Файл: integration/plugins/.../AlphaFamilyGameflow.h             │
│     ├── Отговорност: пази бизнес логиката (bet, wallet, round)          │
│     ├── State тип: AlphaFamilyGameflowState                             │
│     │   ├── match: optional<AlphaFamilyGameflowMatch>                   │
│     │   └── round: optional<AlphaFamilyGameflowRound>                   │
│     └── НЕ извиква SaveState() — само маркира промени чрез State()      │
│                                                                         │
│  Забележка: Другите интеграции (Inspired, Astro, HAT) имат skeleton     │
│  IRecovery имплементации, но НЕ използват RecoveryState<T> template.    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.5 Кой какво записва

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         КОЙ КАКВО ЗАПИСВА                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GameFsm (Game layer)                                                   │
│  └── НЕ записва директно в RecoveryManager. Вместо това предоставя      │
│      SerializeIfModified(), която връща RecoveryData при промяна.        │
│      FSM управлява ВИЗУАЛНОТО състояние на играта:                       │
│      ├── В кой state (екран) е играта: Idle, Spin, Win, BetConfirm...  │
│      ├── NVRAM данни на всеки state: позиции на барабани, текущи         │
│      │   анимации, показвани стойности и др.                             │
│      └── Сериализира се като MachineImplSerializeStorage:                │
│          ├── leafStateHash — hash на текущия leaf state                  │
│          └── nvramsByState — map<stateHash, vector<AnyData>>             │
│                                                                         │
│  PlaygroundRecovery (Integration layer)                                 │
│  └── Взима FSM данни чрез GameFsm.SerializeIfModified()                 │
│      и ги съхранява в State().gameStateRecoveryData.                    │
│      ЕДИНСТВЕНИЯТ модул, който извиква recoveryManager.SaveState().     │
│                                                                         │
│  AlphaFamilyGameflow (Integration layer)                                │
│  └── Записва ДИРЕКТНО бизнес данни чрез State().match / State().round.  │
│      НЕ извиква SaveState() — само маркира данните като dirty.          │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════    │
│  При SaveState() се записва ЦЕЛИЯТ m_nvram.records map НАВЕДНЪЖ.        │
│  Т.е. ЕДИН kernel call запазва ЕДНОВРЕМЕННО и FSM данните               │
│  (PlaygroundRecoveryState) и бизнес данните (AlphaFamilyGameflowState). │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Структури на данните

### 3.1 RecoveryData — FSM recovery пакет

`RecoveryData` е структурата, която **GameFsm** използва за сериализация/десериализация на FSM състоянието. Тя **не е** директно в `m_nvram.records` — вместо това е **поле вътре** в `PlaygroundRecoveryState`.

```cpp
// game/libs/src/Egt/Game/RuntimeImport/IRecovery.data.h

using MonotonicId = uint64_t;  // Монотонно растящ брояч (версия)

struct RecoveryData : Data<RecoveryData>
{
    MonotonicId id = 0;     // Версия на FSM данните (за dirty check)
    std::string label;      // Четимо описание на FSM състоянието
    AnyData data;           // Сериализирано FSM състояние (MachineImplSerializeStorage)
};
```

**Полета на RecoveryData:**

| Поле | Тип | Описание | Кой го задава |
|------|-----|----------|---------------|
| `id` | `uint64_t` | Версия на FSM snapshot-а. Инкрементира се при всяка FSM промяна. Използва се за оптимизация — ако `id` не се е променило, FSM не се сериализира повторно. | `GameFsm::TouchState()` чрез `IRecovery::TouchGameState()` |
| `label` | `std::string` | Кратко описание на текущото FSM състояние. Примери: `"Main:Idle"`, `"Main:Spin"`, `"Main:Win"`. Този label се предава до kernel при save (вж. веригата по-долу). | `GameFsm::SerializeIfModified()` чрез `m_machine->DumpShort()` |
| `data` | `AnyData` | Цялото сериализирано FSM дърво — съдържа `MachineImplSerializeStorage` (вж. 3.2). Това е blob-ът, от който FSM може да се възстанови напълно. | `m_machine->SerializeRecoveryData()` |

**Как `label` стига от FSM до kernel — пълната верига:**

```
GameFsm::SerializeIfModified()
    result.label = m_machine->DumpShort()        ← FSM генерира label (напр. "Main:Spin")
        │
        ▼
PlaygroundRecovery::OnRecoverySavePoint()
    State().gameStateRecoveryData = newData       ← label се записва в RecoveryData
        │
        ▼
    recoveryManager.SaveState(ConstState().gameStateRecoveryData.label)
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                              Взима label от RecoveryData и го подава като аргумент
        │
        ▼
RecoveryManager::SaveState(std::string label)
    m_label = label
    gameState.label = m_label                    ← Записва в IKernelApi::GameState
        │
        ▼
    kernel.GetKernelApi().SaveState(gameState)   ← Kernel получава label-а
```

**Кой създава RecoveryData:**

`GameFsm::SerializeIfModified()` е единственият създател. Функцията се извиква от `PlaygroundRecovery::OnRecoverySavePoint()` при всеки frame:

```cpp
// game/libs/src/Egt/Game/Fsm/GameFsm.cpp

std::optional<RecoveryData> GameFsm::SerializeIfModified(MonotonicId prevId) const
{
    ReturnIf(prevId == m_recoveryDataId, {});  // Няма промяна → nullopt

    RecoveryData result;
    result.id = m_recoveryDataId;                      // Текуща версия
    result.label = m_machine->DumpShort();             // "Main:Spin" и т.н.
    result.data = m_machine->SerializeRecoveryData();  // FSM blob
    return result;
}
```

**Кой консумира RecoveryData:**

`GameFsm::Init()` при стартиране — получава RecoveryData от `IRecovery::DeserializeGameState()` и възстановява FSM от `data` полето:

```cpp
// game/libs/src/Egt/Game/Fsm/GameFsm.cpp

auto recoveryData = recovery.DeserializeGameState();  // → RecoveryData

if (!recoveryData.data.IsEmpty())
    m_machine->InitFull(GetRuntime(), std::move(recoveryData.data));  // Recovery
else
    m_machine->InitFull(GetRuntime(), {});  // Fresh start
```

**Как RecoveryData.id се инкрементира — пълната верига:**

```
FSM промяна (state transition / NVRAM update)
    │
    ▼
m_machine→SetRecoveryDataDirtyCallback()     ← регистриран при Init()
    │
    ▼
GameFsm::TouchState()
    │
    ▼
IRecovery::TouchGameState()                  ← имплементиран от PlaygroundRecovery
    │
    ▼
RecoveryState<T>::TouchState()
    │
    ▼
RecoveryManager::TouchState()  →  return ++m_touchId;
    │
    ▼
m_recoveryDataId = върнатата стойност        ← GameFsm пази локално копие
```

### 3.2 MachineImplSerializeStorage — FSM вътрешна структура

Това е конкретният тип данни вътре в `RecoveryData.data`. Съдържа всичко необходимо за възстановяване на FSM.

```cpp
// game/libs/src/Egt/Fsm/MachineImpl.data.h

struct MachineImplSerializeStorage : Data<MachineImplSerializeStorage>
{
    uint64_t leafStateHash;                                    // Hash на leaf state-а
    std::map<uint64_t, std::vector<AnyData>> nvramsByState;    // NVRAM данни за всеки state
};
```

| Поле | Описание |
|------|----------|
| `leafStateHash` | Идентифицира **в кой state** от FSM дървото е била играта (напр. "Spin", "Win", "Idle"). При recovery FSM навигира директно до този state. |
| `nvramsByState` | Map от state hash → списък с NVRAM данни. Всеки FSM state може да има собствени persistent данни (позиции на барабани, текуща анимация, и т.н.). |

### 3.3 PlaygroundRecoveryState — обвивка за FSM данни

```cpp
// integration/playground/.../PlaygroundRecovery.data.h

struct PlaygroundRecoveryState : Data<PlaygroundRecoveryState>
{
    Game::RecoveryData gameStateRecoveryData;  // Единственото поле
};
```

Това е state типът, регистриран от PlaygroundRecovery чрез `RecoveryState<PlaygroundRecoveryState>`. Съдържа само едно поле — `RecoveryData`, който пък съдържа целия FSM snapshot.

**Къде се намира в m_nvram:**

`m_nvram.records[hash("PlaygroundRecoveryState")]` → `AnyData` → вътре е `PlaygroundRecoveryState` → вътре е `RecoveryData` → вътре е `MachineImplSerializeStorage`.

### 3.4 AlphaFamilyGameflowState — бизнес логика

```cpp
// integration/plugins/.../AlphaFamilyGameflow.data.h

struct AlphaFamilyGameflowState : Data<AlphaFamilyGameflowState>
{
    std::optional<AlphaFamilyGameflowMatch> match;  // Текущ мач (ако има)
    std::optional<AlphaFamilyGameflowRound> round;  // Текущ рунд (ако има)
};

struct AlphaFamilyGameflowMatch
{
    int64_t creditBet = 0;                            // Залог в кредити
    bool kernelStarted = false;                        // Kernel потвърдил ли е мача
    std::vector<ConsecutiveRoundInfo> consecutives;    // Free spins/bonus round info
    Wallet wallet;                                     // rewarded & consumed currencies
};

struct AlphaFamilyGameflowRound
{
    RoundInput input;                        // Входни данни за рунда (тип, залог)
    std::optional<RoundResult> result;       // Math резултат (ако вече е изчислен)
    bool kernelStarted = false;              // Kernel потвърдил ли е рунда
    bool kernelOutcome = false;              // Kernel потвърдил ли е изхода
    bool kernelGamble = false;               // Kernel потвърдил ли е gamble
};
```

**Къде се намира в m_nvram:**

`m_nvram.records[hash("AlphaFamilyGameflowState")]` → `AnyData` → вътре е `AlphaFamilyGameflowState`.

### 3.5 Сравнение на двата типа данни

| Аспект | PlaygroundRecoveryState | AlphaFamilyGameflowState |
|--------|------------------------|--------------------------|
| **Отговаря на** | "В кой екран е играта?" | "Колко пари има играчът?" |
| **Съдържа** | FSM дърво, leaf state, NVRAM | Bet, wallet, round result, kernel flags |
| **Управлява се от** | PlaygroundRecovery (чрез GameFsm) | AlphaFamilyGameflow |
| **Вложена структура** | RecoveryData → MachineImplSerializeStorage | match/round (flat) |
| **Как се маркира dirty** | `State().gameStateRecoveryData = newData` | `State().match.emplace()`, `State().round = ...` |

---

## 4. Save и Load механизми

### 4.1 Save Flow — кой извиква SaveState() и кога

**Само `PlaygroundRecovery::OnRecoverySavePoint()`** извиква `SaveState()`. Това е **единственото място** в целия codebase, което тригерира запис.

```cpp
// integration/playground/.../PlaygroundRecovery.cpp

void PlaygroundRecovery::OnRecoverySavePoint()
{
    // Стъпка 1: Взимане на FSM данни (ако са променени)
    auto& gameState = RuntimeGet<IGameState>();
    if (auto newData = gameState.SerializeIfModified(ConstState().gameStateRecoveryData.id))
    {
        State().gameStateRecoveryData = std::move(*newData);   // m_touchId++
    }

    // Стъпка 2: Запис на ВСИЧКИ данни (ЕДИНСТВЕНИЯТ SaveState() call!)
    auto& recoveryManager = RuntimeGet<IRecoveryManager>();
    recoveryManager.SaveState(ConstState().gameStateRecoveryData.label);
}
```

**Стъпка 1** — `SerializeIfModified()`:
- Извиква `GameFsm::SerializeIfModified(prevId)`
- Ако FSM не се е променило (prevId == текущо) → връща `nullopt` → нищо не се записва в state
- Ако FSM се е променило → връща нов `RecoveryData` с актуален FSM snapshot
- `State().gameStateRecoveryData = newData` маркира PlaygroundRecoveryState като dirty (`m_touchId++`)

**Стъпка 2** — `SaveState()`:
- Проверява `m_touchId != m_savedId`
- Ако са равни → **SKIP** (нито FSM, нито Gameflow данните са се променили)
- Ако са различни → сериализира **ЦЕЛИЯ** `m_nvram.records` с `PackIData()` и изпраща към kernel

**AlphaFamilyGameflow НЕ извиква SaveState():**

```cpp
// AlphaFamilyGameflow.cpp — пример

void AlphaFamilyGameflow::RequestStartMatch(...)
{
    State().match.emplace();          // ← Само m_touchId++, НЕ SaveState()!
    State().match->creditBet = bet;   // ← Само m_touchId++
}

void AlphaFamilyGameflow::RequestEndMatch(...)
{
    State().match = {};               // ← Само m_touchId++, match → nullopt
    State().round = {};               // ← Само m_touchId++
}
```

Gameflow модулът само маркира данните. Реалният запис се случва **по-късно**, при следващия save point.

### 4.2 Пълна картина: Timeline на един frame

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TIMELINE НА ЕДИН FRAME                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ══════════════════════════════════════════════════════════════════    │
│   ФАЗА 1: GAME LOGIC (между recoverySavePoint events)                   │
│   ══════════════════════════════════════════════════════════════════    │
│                                                                         │
│   AlphaFamilyGameflow (при user input или kernel reply):                │
│       State().match.emplace()     → m_touchId++ (маркира dirty)         │
│       State().round.emplace()     → m_touchId++                         │
│       State().match->wallet = ... → m_touchId++                         │
│       НЕ извиква SaveState()                                            │
│                                                                         │
│   GameFsm (при state transitions):                                      │
│       Transit("Idle" → "Spin")    → m_recoveryDataId++ (вътрешен)       │
│       Update NVRAM data           → m_recoveryDataId++                  │
│       НЕ извиква SaveState()                                            │
│                                                                         │
│   ══════════════════════════════════════════════════════════════════    │
│   ФАЗА 2: SAVE POINT (край на frame)                                    │
│   ══════════════════════════════════════════════════════════════════    │
│                                                                         │
│   PlaygroundGame::Update():                                             │
│       recoverySavePoint.Post()  ← Тригерира save check                  │
│           │                                                             │
│           ▼                                                             │
│   PlaygroundRecovery::OnRecoverySavePoint():                            │
│       │                                                                 │
│       ├─► GameFsm.SerializeIfModified(lastId)                           │
│       │       ├─► Сравнява lastId с m_recoveryDataId                    │
│       │       ├─► Ако различни → сериализира FSM, връща RecoveryData    │
│       │       └─► Ако еднакви → връща nullopt (няма FSM промени)        │
│       │                                                                 │
│       ├─► State().gameStateRecoveryData = newData  (ако има)            │
│       │       └─► m_touchId++ (маркира PlaygroundRecoveryState dirty)   │
│       │                                                                 │
│       └─► recoveryManager.SaveState(label)                              │
│               │                                                         │
│               ├─► m_touchId == m_savedId?  → SKIP (нищо не е dirty)     │
│               │                                                         │
│               └─► m_touchId != m_savedId?  → ЗАПИСВА:                   │
│                       PackIData(m_nvram) сериализира АТОМАРНО:          │
│                       ┌──────────────────────────────────────────┐      │
│                       │ PlaygroundRecoveryState (FSM snapshot)   │      │
│                       │ AlphaFamilyGameflowState (match/round)   │      │
│                       └──────────────────────────────────────────┘      │
│                       kernel.SaveState(бинарен blob)                    │
│                       m_savedId = m_touchId                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Save Flow обобщение

| Компонент | Какво прави | Кога | Извиква SaveState()? |
|-----------|-------------|------|----------------------|
| **AlphaFamilyGameflow** | `State().match = ...`, `State().round = ...` | При бизнес събития | НЕ |
| **GameFsm** | Променя FSM state/NVRAM | При state transitions | НЕ |
| **PlaygroundRecovery** | Събира FSM данни + `SaveState()` | Всеки frame (save point) | **ДА — единственият** |
| **RecoveryManager** | `PackIData()` на **целия** m_nvram + kernel write | Когато е извикан | — (passive) |

**Извод:** Всички модули само **маркират** промени (`m_touchId++`). **Един-единствен** handler (`OnRecoverySavePoint`) проверява дали има dirty данни и записва **всичко атомарно** — и FSM, и Gameflow, и каквото друго е регистрирано.

### 4.4 Load Flow (при стартиране)

**Редът на инициализация е критичен** — PlaygroundRecovery е **първият** компонент (коментар в кода: "Recovery should be first").

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LOAD FLOW                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════    │
│  СТЪПКА 1: PlaygroundRecovery::Init()  ← ПЪРВИ компонент!               │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                         │
│   recoveryManager.LoadState()                                           │
│       │                                                                 │
│       ├─► kernel.GetKernelApi().RecoverState()                          │
│       │       └─► Връща GameState { id, label, data (binary) }          │
│       │                                                                 │
│       ├─► m_savedId = gameState.id                                      │
│       │   m_touchId = m_savedId          ← Синхронизирани!              │
│       │   m_label = gameState.label                                     │
│       │                                                                 │
│       └─► DataTools::UnpackIData(m_nvram, gameState.data)               │
│               └─► m_nvram.records се попълва от бинарните данни         │
│                   (и двата записа — PlaygroundRecoveryState и           │
│                    AlphaFamilyGameflowState — се възстановяват)         │
│                                                                         │
│   InitRecoveryState(GetRuntime())                                       │
│       │                                                                 │
│       ├─► id = hash("PlaygroundRecoveryState")                          │
│       ├─► record = m_manager->Record(id)  ← търси в m_nvram.records     │
│       │                                                                 │
│       ├─► record НЕ е празен (RECOVERY):                                │
│       │       m_state = record.Cast<PlaygroundRecoveryState>()          │
│       │       └─► m_state вече съдържа gameStateRecoveryData!           │
│       │                                                                 │
│       └─► record Е празен (FRESH START):                                │
│               m_state = record.CreateEmpty<>()                          │
│               TouchState() → m_touchId++                                │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════    │
│  СТЪПКА 2: AlphaFamilyGameflow::Init()                                  │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                         │
│   InitRecoveryState(GetRuntime())                                       │
│       └─► Същият механизъм: record.Cast<AlphaFamilyGameflowState>()     │
│           └─► match/round от предишна сесия са достъпни!                │
│                                                                         │
│   RecoverRoundRng()                                                     │
│       │                                                                 │
│       ├─► Проверка: има ли round в ConstState()?                        │
│       │                                                                 │
│       ├─► Ако round->kernelStarted && !round->kernelOutcome:            │
│       │       └─► RNG engine се пресъздава (празен)                     │
│       │           (volatile данни НЕ се записват в recovery)            │
│       │                                                                 │
│       └─► Иначе: нищо допълнително                                      │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════    │
│  СТЪПКА 3: GameFsm::Init()                                              │
│  ═══════════════════════════════════════════════════════════════════    │
│                                                                         │
│   recovery.DeserializeGameState()                                       │
│       └─► Връща ConstState().gameStateRecoveryData                      │
│           └─► RecoveryData { id, label, data: AnyData }                 │
│                                                                         │
│   Проверка: recoveryData.data.IsEmpty()?                                │
│       │                                                                 │
│       ├─► НЕ е празен (RECOVERY):                                       │
│       │       m_machine->InitFull(runtime, recoveryData.data)           │
│       │       └─► FSM десериализира MachineImplSerializeStorage:        │
│       │           ├── leafStateHash → намира предишния leaf state       │
│       │           └── nvramsByState → зарежда NVRAM за всеки state      │
│       │           └─► FSM се възстановява в точния state                │
│       │                                                                 │
│       └─► Празен (FRESH START):                                         │
│               m_machine->InitFull(runtime, {})                          │
│               └─► FSM стартира от начално състояние                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Recovery сценарии при зареждане на AlphaFamilyGameflowState:**

| Заварено състояние | match | round | Какво се случва |
|-------------------|-------|-------|-----------------|
| Idle (няма игра) | nullopt | nullopt | Нормален старт |
| Match стартиран | {...} | nullopt | Продължава от match, чака round |
| Round in progress | {...} | {..., result: {...}} | Продължава round, math е вече изчислен |
| Round чака kernel | {...} | {..., kernelStarted, !kernelOutcome} | RNG engine се пресъздава |

### 4.5 Презаписване и "триене"

**Презаписване:** `SaveState()` винаги записва **ПЪЛЕН snapshot** на целия `m_nvram` — не частичен update. Всеки save заменя предишното състояние изцяло.

**"Триене" на данни:** Records никога не се премахват от map-а. Вместо това optional полетата стават `std::nullopt`:

```cpp
// EndMatch — "изтрива" match и round
State().match = {};  // match = std::nullopt, но записът в m_nvram.records остава
State().round = {};  // round = std::nullopt
```

При recovery, ако match и round са `nullopt`, играта знае, че е била в Idle.

**Жизнен цикъл на snapshot-ите:**

| Frame | Действие | match | round | Snapshot |
|-------|----------|-------|-------|----------|
| 1 | StartMatch | {...} | nullopt | #1 |
| 50 | StartRound | {...} | {...} | #2 |
| 100 | EndRound | {...} | nullopt | #3 |
| 150 | EndMatch | nullopt | nullopt | #4 |

При crash на Frame 75 → Recovery зарежда snapshot #2 → играта продължава от round in progress.

---

## 5. Конкретни примери

### 5.1 След StartMatch(bet=100)

```
m_nvram.records (записани АТОМАРНО при един SaveState() call):
│
├── [hash("PlaygroundRecoveryState")]  →  AnyData
│       └── PlaygroundRecoveryState:
│               └── gameStateRecoveryData: RecoveryData
│                       id: 5
│                       label: "Main:BetConfirm"
│                       data: MachineImplSerializeStorage
│                           leafStateHash: hash("BetConfirm")
│                           nvramsByState: {...}
│
└── [hash("AlphaFamilyGameflowState")]  →  AnyData
        └── AlphaFamilyGameflowState:
                match:
                    creditBet: 100
                    kernelStarted: true
                    wallet: { rewarded: {MainSpinEnergy: 100}, consumed: {} }
                round: nullopt
```

### 5.2 По време на Round (печалба 500)

```
m_nvram.records (записани АТОМАРНО при един SaveState() call):
│
├── [hash("PlaygroundRecoveryState")]  →  AnyData
│       └── PlaygroundRecoveryState:
│               └── gameStateRecoveryData: RecoveryData
│                       id: 12
│                       label: "Main:Spin"
│                       data: MachineImplSerializeStorage
│                           leafStateHash: hash("Spin")
│                           nvramsByState: {reelPositions, ...}
│
└── [hash("AlphaFamilyGameflowState")]  →  AnyData
        └── AlphaFamilyGameflowState:
                match:
                    creditBet: 100
                    wallet: { rewarded: {Credits: 500, ...}, consumed: {MainSpinEnergy: 100} }
                round:
                    input: { roundType: Main }
                    result: { rewards: {Credits: 500} }  ← Вече изчислен!
                    kernelOutcome: true

CRASH ТУК → Recovery зарежда ЦЕЛИЯ m_nvram от kernel
         → PlaygroundRecoveryState + AlphaFamilyGameflowState се възстановяват
         → FSM се възстановява в "Spin" (от RecoveryData.data)
         → round.result вече е готов, няма ново RNG
         → Играта продължава от показване на резултата
```

---

## 6. Ключови файлове

| Файл | Роля |
|------|------|
| `integration/libs/src/Egt/Integration/Recovery/RecoveryState.h` | Template за регистриране на модул в recovery системата |
| `integration/libs/src/Egt/Integration/Runtime/IRecoveryManager.h` | Интерфейс на RecoveryManager |
| `integration/plugins/src/Egt/RecoveryManager/RecoveryManager.cpp` | Централен persistence manager (SaveState/LoadState) |
| `integration/plugins/src/Egt/RecoveryManager/RecoveryManager.data.h` | RecoveryManagerState, RecoveryManagerConfig |
| `integration/playground/.../PlaygroundRecovery.cpp` | Playground recovery компонент (единственият SaveState caller) |
| `integration/playground/.../PlaygroundRecovery.data.h` | PlaygroundRecoveryState |
| `integration/plugins/.../AlphaFamilyGameflow/AlphaFamilyGameflow.cpp` | Gameflow бизнес логика |
| `integration/plugins/.../AlphaFamilyGameflow/AlphaFamilyGameflow.data.h` | AlphaFamilyGameflowState, Match, Round |
| `game/libs/src/Egt/Game/RuntimeImport/IRecovery.h` | IRecovery интерфейс + RecoveryData struct |
| `game/libs/src/Egt/Game/RuntimeImport/IRecovery.data.h` | RecoveryData, MonotonicId дефиниции |
| `game/libs/src/Egt/Game/RuntimeExport/IGameState.h` | IGameState интерфейс (SerializeIfModified) |
| `game/libs/src/Egt/Game/Fsm/GameFsm.cpp` | FSM сериализация/десериализация |
| `game/libs/src/Egt/Fsm/MachineImpl.data.h` | MachineImplSerializeStorage |
| `integration/libs/src/Egt/KernelApi/IKernelApi.h` | IKernelApi::GameState, SaveState/RecoverState |
