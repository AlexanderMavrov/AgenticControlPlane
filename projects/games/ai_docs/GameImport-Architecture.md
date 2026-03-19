# GameImport Architecture

## Съдържание

1. [Преглед: Два слоя абстракция](#преглед-два-слоя-абстракция)
2. [GameImport vs IKernelIntegration](#gameimport-vs-ikernelintegration)
3. [GameImport интерфейси](#gameimport-интерфейси)
4. [RuntimeCategory и контрол на достъпа](#runtimecategory-и-контрол-на-достъпа)
5. [Реализация: Playground](#реализация-playground)
6. [Реализация: Astro](#реализация-astro)
7. [Реализация: Inspired](#реализация-inspired)
8. [Сравнение между реализациите](#сравнение-между-реализациите)

---

## Преглед: Два слоя абстракция

Архитектурата разделя достъпа до данни и операции в **два отделни слоя**, за да осигури **платформена независимост на FSM**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                FSM / Game                                   │
│                                                                             │
│   RuntimeCategory::GameImport                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  IWallet, ILimits, IRecovery, IHwButtons, IResponsibleGaming        │   │
│   │                                                                     │   │
│   │  → СТАТИЧНИ данни и EXTERNAL събития                                │   │
│   │  → FSM не знае откъде идват данните                                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   FSM НЯМА достъп до Integration категорията!                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Абстракция
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                          Integration / Gameflow                             │
│                                                                             │
│   RuntimeCategory::Integration                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  IKernelIntegration, IGameflowIntegration                           │   │
│   │                                                                     │   │
│   │  → ДИНАМИЧНИ операции (request-reply pattern)                       │   │
│   │  → Само Gameflow комуникира с Kernel                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                              Kernel / Framework                             │
│                                                                             │
│   RuntimeCategory::Kernel                                                   │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  IKernelApi, PlaygroundKernelApi, AstroEgt, InspiredKernelApi       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## GameImport vs IKernelIntegration

### Ключова разлика

| Характеристика | GameImport | IKernelIntegration |
|----------------|------------|-------------------|
| **Тип данни** | Статични данни, външни събития | Динамични операции |
| **Pattern** | Query/Event | Request-Reply |
| **Достъп** | FSM (всички state-ове) | Само Gameflow |
| **RuntimeCategory** | `GameImport` (1 << 3) | `Integration` (1 << 10) |
| **Познание за Kernel** | Няма | Директен достъп |

### GameImport: Статични данни и External събития

```cpp
// FSM state достъпва данни - НЕ знае откъде идват
void IdleState::InitCurrentBet()
{
    const auto credit = RuntimeGetConst<IWallet>().GetCredit();    // Колко е credit?
    const auto limits = RuntimeGetConst<ILimits>().GetBetLimits(); // Какви са лимитите?
}

// FSM слуша събития - НЕ знае кой ги генерира
void IdleState::Init()
{
    ReactOn(RuntimeGetConst<IWallet::Events>().onCreditChanged, &IdleState::OnCreditChanged);
    ReactOn(RuntimeGetConst<IStartGameHwButton::Events>().buttonPressedEvent, &IdleState::OnStartPressed);
}
```

### IKernelIntegration: Динамични операции

```cpp
// САМО Gameflow прави request-reply операции с Kernel
void AlphaFamilyGameflow::RequestStartMatch(const StartMatchRequest& request)
{
    auto& kernel = RuntimeGet<IKernelIntegration>();  // Integration category
    kernel.GetKernelApi().RequestStartMatch(bet);     // Request към Kernel
}

// Gameflow слуша replies и ги превежда в Game events
void AlphaFamilyGameflow::Init(...)
{
    auto& events = kernel.GetKernelApiEvents();
    RegisterInstant(events.onStartMatchReply, this, &AlphaFamilyGameflow::OnKernelStartMatchReply);
    RegisterInstant(events.onRandomsReply, this, &AlphaFamilyGameflow::OnKernelRandomsReply);
}
```

### Защо са разделени?

**Платформена независимост:** FSM кодът е **един и същ** за Playground, Astro и Inspired.

```cpp
// Този код работи на ВСЯКА платформа без промяна
void IdleState::OnCashoutHwButtonPressed()
{
    const auto credit = RuntimeGet<IWallet>().GetCredit();
    if (credit > 0)
    {
        RuntimeGet<IWallet>().StartCashout();
    }
}
```

FSM не знае:
- Дали credit идва от Playground симулатор, Astro SDK или Inspired protocol
- Как се изпълнява StartCashout() на различните платформи
- Каква е комуникацията с реалния хардуер

---

## GameImport интерфейси

Всички интерфейси се намират в `game/libs/src/Egt/Game/RuntimeImport/`.

### IWallet

**Роля:** Абстракция на credit/cashout операции.

```cpp
class IWallet
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual int64_t GetCredit() const = 0;  // Колко е текущият credit?
    virtual void StartCashout() = 0;        // Започни cashout

    struct Events
    {
        Core::Event<TransactionInfo> onCreditChanged;  // Credit се промени
        Core::Event<> onCashoutStart;                  // Cashout започна
        Core::Event<bool> onCashoutEnd;                // Cashout завърши
    };
};
```

### ILimits

**Роля:** Абстракция на bet limits и win capping.

```cpp
class ILimits
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual BetLimits GetBetLimits() const = 0;   // Min/Max bet
    virtual WinCapping GetWinCapping() const = 0; // Win cap

    struct Events {};  // Празно - лимитите рядко се променят runtime
};
```

### IRecovery

**Роля:** Абстракция на game state persistence.

```cpp
class IRecovery
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual MonotonicId TouchGameState() = 0;           // Маркира state за запис
    virtual RecoveryData DeserializeGameState() const = 0; // Възстановява state

    struct Events {};
};
```

### IHwButtons (HwButtons.h)

**Роля:** Абстракция на хардуерни бутони.

```cpp
class IStartGameHwButton : public IHwButton
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameFsm;

    struct Events : public IHwButton::Events
    {
        Core::Event<> buttonPressedEvent;  // Бутонът е натиснат
        Core::Event<bool> enabledChanged;
        Core::Event<bool> focusedChanged;
    };
};

// Същата структура за:
// IChangeBetHwButton, IMaxBetHwButton, IAutoPlayHwButton,
// IInfoScreenHwButton, ICashoutHwButton, IExitHwButton
```

### IResponsibleGaming

**Роля:** Абстракция на regulatory limits (отговорна игра).

```cpp
class IResponsibleGaming
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual bool IsResponsibleGamingSetupEnable() = 0;
    virtual void OpenResponsibleGamingSetupView() = 0;
    virtual bool CheckResponsibleGamingCreditLimit(int64_t) = 0;

    struct Events
    {
        Core::Event<> responsibleGamingWarning;
        Core::Event<> responsibleGamingCashout;
    };
};
```

### IBridge

**Роля:** Комуникация между viewports (main view ↔ info view).

```cpp
class IBridge
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual Ptr<BridgeEndpoint> GetMainViewClient() = 0;
    virtual Ptr<BridgeEndpoint> GetMainViewServer() = 0;
    virtual Ptr<BridgeEndpoint> GetInfoViewClient() = 0;
    virtual Ptr<BridgeEndpoint> GetInfoViewServer() = 0;

    struct Events {};
};
```

### IAppControl

**Роля:** Системни пътища и application control.

```cpp
class IAppControl
{
public:
    static constexpr auto RuntimeCategory = RuntimeCategory::GameImport;

    virtual Fs::path GetBasePath() const = 0;
    virtual Fs::path GetResourcePath() const = 0;
    virtual Fs::path GetConfigPath() const = 0;
    virtual Fs::path GetStoragePath() const = 0;

    virtual bool ExitGracefully() = 0;
    virtual void ForceExit(int errorCode, std::string errorMessage) = 0;

    struct Events
    {
        Core::Event<> processBegin;
        Core::Event<> processEnd;
        Core::Event<> drawBegin;
        Core::Event<> drawEnd;
    };
};
```

---

## RuntimeCategory и контрол на достъпа

### Категории

```cpp
// game/libs/src/Egt/Game/RuntimeCategory.h
namespace RuntimeCategory
{
    constexpr uint32_t GameFsm = 1 << 0;      // FSM state-ове
    constexpr uint32_t GameMath = 1 << 1;     // Math модули
    constexpr uint32_t GameView = 1 << 2;     // View модули
    constexpr uint32_t GameImport = 1 << 3;   // GameImport интерфейси
    constexpr uint32_t GameDebug = 1 << 4;    // Debug интерфейси
    constexpr uint32_t GameMask = GameFsm | GameMath | GameView | GameImport | GameDebug;

    constexpr uint32_t Integration = 1 << 10; // Integration интерфейси
    constexpr uint32_t IntegrationView = 1 << 11;
    constexpr uint32_t IntegrationDebug = 1 << 12;

    constexpr uint32_t Kernel = 1 << 20;      // Kernel интерфейси
}
```

### Достъп по роля

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│  Модул                    runtimeAccess                   Достъп до           │
│  ───────────────────────────────────────────────────────────────────────────  │
│                                                                               │
│  BurningHotCoinsFsm       GameFsm: rwx                    IStartGameHwButton  │
│                           GameMath,GameView: rw           IWallet, ILimits    │
│                           GameImport: rw                  (четене)            │
│                                                                               │
│  AlphaFamilyGameflow      Integration,GameMask: rwx       IKernelIntegration  │
│                                                           IWallet, ILimits    │
│                                                           IGameflowIntegration│
│                                                                               │
│  BurningHotCoinsView      GameView: rwx                   IVideoManager       │
│                           GameDebug: rw                   ❌ IWallet          │
│                           (НЕ включва GameImport!)        ❌ ILimits          │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Реализация: Playground

### Архитектурен подход: Компоненти с Event-based комуникация

Playground използва **отделни компоненти**, които **слушат Kernel events** и ги **препращат** като GameImport events.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PlaygroundIntegration                                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ m_components: vector<PlaygroundComponent>                           │    │
│  │                                                                     │    │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐     │    │
│  │  │ PlaygroundWallet │ │ PlaygroundLimits │ │ PlaygroundInput  │     │    │
│  │  │ ──────────────── │ │ ──────────────── │ │ ──────────────── │     │    │
│  │  │ impl: IWallet    │ │ impl: ILimits    │ │ impl: HwButtons  │     │    │
│  │  │                  │ │                  │ │                  │     │    │
│  │  │ m_kernel ────────┼─┼──────────────────┼─┤                  │     │    │
│  │  │ (слуша events)   │ │                  │ │                  │     │    │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    │ слуша events.creditChanged
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PlaygroundKernelApi (отделен модул в kernel/)                               │
│                                                                             │
│  • Симулира casino server                                                   │
│  • Генерира events при промяна на credit                                    │
│  • Request-reply pattern с IPC-like комуникация                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Базов клас: PlaygroundComponent

```cpp
class PlaygroundComponent : public BaseModule
{
public:
    explicit PlaygroundComponent(PlaygroundIntegration&, std::string name);

protected:
    PlaygroundIntegration& m_playground;
    const std::string m_name;
    IPlaygroundKernelApi* m_kernel = nullptr;  // ← Достъп до Kernel
};
```

### Примери: PlaygroundWallet

```cpp
// PlaygroundWallet.cpp
bool PlaygroundWallet::Init(GameCore::RuntimeAccess runtime, const Core::Json& config)
{
    RuntimeAdd<IWallet>(this);
    RuntimeAdd<IWallet::Events>(this);

    // Слуша Kernel events
    auto& events = m_kernel->GetEvents();
    RegisterInstant(events.creditChanged, this, &PlaygroundWallet::OnCreditChanged);
    RegisterInstant(events.onCashoutEnd, this, &PlaygroundWallet::OnCashoutEnd);

    return true;
}

int64_t PlaygroundWallet::GetCredit() const
{
    return m_kernel->GetCurrentCredit();  // ← Делегира към Kernel
}

void PlaygroundWallet::StartCashout()
{
    m_kernel->RequestCashout();  // ← Изпраща request към Kernel
    onCashoutStart.Post();
}

// Kernel event → GameImport event
void PlaygroundWallet::OnCreditChanged(uint64_t credit)
{
    TransactionInfo ti;
    ti.newCreditTotal = int64_t(credit);
    onCreditChanged.Post(std::move(ti));  // ← Препраща като IWallet event
}
```

### Event Pipeline: Playground

```
Kernel                      Component                     FSM
  │                            │                           │
  │ events.creditChanged       │                           │
  │───────────────────────────►│                           │
  │                            │                           │
  │                            │ OnCreditChanged()         │
  │                            │ onCreditChanged.Post(ti)  │
  │                            │──────────────────────────►│
  │                            │                           │
  │                            │                           │ OnCreditChanged(ti)
  │                            │                           │ UpdateCreditBar()
```

---

## Реализация: Astro

### Архитектурен подход: Компоненти с локално състояние

Astro използва **отделни компоненти** с **локално състояние**, които **не слушат** Kernel events, а **директно** управляват данните.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ AstroIntegration                                                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Компоненти (и в m_components, и като отделни полета)                │    │
│  │                                                                     │    │
│  │  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐     │    │
│  │  │ AstroWallet      │ │ AstroLimits      │ │ AstroInput       │     │    │
│  │  │ ──────────────── │ │ ──────────────── │ │ ──────────────── │     │    │
│  │  │ impl: IWallet    │ │ impl: ILimits    │ │ impl: HwButtons  │     │    │
│  │  │                  │ │                  │ │                  │     │    │
│  │  │ m_credit (local) │ │ m_betLimits(local│ │                  │     │    │
│  │  │ НЕ слуша events  │ │ m_winCapping     │ │                  │     │    │
│  │  └──────────────────┘ └──────────────────┘ └──────────────────┘     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ m_astroEgt (AstroEgt) ← Kernel е ВГРАДЕН в Integration              │    │
│  │ • Директен достъп до Astro SDK (ak2api)                             │    │
│  │ • Синхронни операции                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Базов клас: AstroComponent

```cpp
class AstroComponent : public BaseModule
{
public:
    virtual void Draw(video_ctrl::draw_list& drawList);  // ← Има Draw метод

protected:
    AstroIntegration& m_astro;
    const std::string m_name;
    // Няма m_kernel - достъпва се през m_astro.GetKernelApi()
};
```

### Примери: AstroWallet

```cpp
// AstroWallet.cpp
AstroWallet::AstroWallet(AstroIntegration& astro)
    : AstroComponent(astro, "Wallet")
    , m_credit(DefaultStartingCredits)  // ← Локално състояние!
{
}

bool AstroWallet::Init(GameCore::RuntimeAccess runtime, const Core::Json& config)
{
    RuntimeAdd<IWallet>(this);
    RuntimeAdd<IWallet::Events>(this);
    // НЕ слуша Kernel events!
    return true;
}

int64_t AstroWallet::GetCredit() const
{
    return m_astro.GetKernelApi().GetCurrentCredit();  // ← Синхронно четене
}

void AstroWallet::StartCashout()
{
    // НЕ изпраща request към Kernel - управлява локално
    CompleteTransaction(TransactionType::Cashout, m_credit);
}

void AstroWallet::CompleteTransaction(TransactionType type, int64_t amount)
{
    // Променя локално състояние
    switch (type)
    {
        case TransactionType::Cashout: m_credit -= amount; break;
        case TransactionType::CashIn: m_credit += amount; break;
    }

    TransactionInfo ti;
    ti.transactionType = type;
    ti.transactionAmount = amount;
    ti.newCreditTotal = m_credit;

    onCreditChanged.Post(std::move(ti));  // ← Генерира event директно
}
```

### AstroLimits - Локални стойности

```cpp
// AstroLimits.cpp
bool AstroLimits::Init(GameCore::RuntimeAccess runtime, const Core::Json& config)
{
    RuntimeAdd<ILimits>(this);
    RuntimeAdd<ILimits::Events>(this);

    // Инициализира локално
    m_betLimits.minBet = 10;
    m_betLimits.maxBet = 10'000;
    m_winCapping.capping = 500'000;

    return true;
}

BetLimits AstroLimits::GetBetLimits() const
{
    return m_betLimits;  // ← Връща локална стойност
}
```

### Event Pipeline: Astro

```
FSM                         Component                     Kernel
  │                            │                           │
  │ StartCashout()             │                           │
  │───────────────────────────►│                           │
  │                            │                           │
  │                            │ CompleteTransaction()     │
  │                            │ m_credit -= amount        │
  │                            │ onCreditChanged.Post(ti)  │
  │                            │                           │
  │◄───────────────────────────│                           │
  │ OnCreditChanged(ti)        │                           │
  │ UpdateCreditBar()          │                           │
```

### Защо Astro е различно?

1. **Kernel е вграден** - AstroEgt е член на AstroIntegration, не отделен модул
2. **Синхронни операции** - Astro SDK предоставя синхронен достъп
3. **Локално състояние** - Компонентите управляват данни локално
4. **Директни getter-и** - AstroIntegration има getter за всеки компонент

```cpp
class AstroIntegration {
public:
    const AstroWallet& GetWallet() const { return *m_wallet; }
    AstroWallet& GetWallet() { return *m_wallet; }
    // ...
private:
    Ptr<AstroWallet> m_wallet;    // Директен pointer
    Ptr<AstroLimits> m_limits;    // Директен pointer
    std::vector<Ptr<AstroComponent>> m_components;  // И в списъка
};
```

---

## Реализация: Inspired

### Архитектурен подход: Монолитен

Inspired използва **монолитен подход** - самият Integration клас имплементира GameImport интерфейсите.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ InspiredIntegration                                                         │
│                                                                             │
│  implements: IWallet, ILimits, IRecovery, IResponsibleGaming                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Данните са ДИРЕКТНО в класа:                                        │    │
│  │                                                                     │    │
│  │   int64_t m_credit;                                                 │    │
│  │   BetLimits m_betLimits;                                            │    │
│  │   WinCapping m_winCapping;                                          │    │
│  │   RecoveryData m_recoveryData;                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Единственият компонент:                                             │    │
│  │  ┌──────────────────┐                                               │    │
│  │  │ InspiredInput    │ ← Само Input е отделен компонент              │    │
│  │  │ impl: HwButtons  │                                               │    │
│  │  └──────────────────┘                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ m_inspiredEgt (IInspiredKernelApi)                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Пример: InspiredIntegration

```cpp
class InspiredIntegration
    : public BaseModule
    , public IKernelIntegration
    , public IWallet           // ← Директно имплементира
    , public IWallet::Events
    , public ILimits           // ← Директно имплементира
    , public ILimits::Events
    , public IRecovery         // ← Директно имплементира
    , public IResponsibleGaming
{
private:
    int64_t m_credit;          // ← Данните са тук
    BetLimits m_betLimits;
    WinCapping m_winCapping;

    Ptr<InspiredInput> m_input; // ← Единственият компонент
};

// InspiredIntegration::Init()
bool InspiredIntegration::Init(...)
{
    RuntimeAdd<IWallet>(this);      // ← Добавя СЕБЕ СИ
    RuntimeAdd<ILimits>(this);
    RuntimeAdd<IRecovery>(this);
    RuntimeAdd<IResponsibleGaming>(this);
}
```

---

## Сравнение между реализациите

### Архитектурен подход

| Аспект | Playground | Astro | Inspired |
|--------|------------|-------|----------|
| **Подход** | Компонентен | Хибриден | Монолитен |
| **Компоненти** | 6 отделни | 5 отделни | 1 (само Input) |
| **Wallet/Limits** | Компоненти | Компоненти | В Integration |
| **Kernel location** | Отделен модул | Вграден | Вграден |

### Управление на данни

| Аспект | Playground | Astro | Inspired |
|--------|------------|-------|----------|
| **Credit източник** | KernelApi | Локален m_credit | Локален m_credit |
| **Слуша Kernel events** | ✅ Да | ❌ Не | ❌ Не |
| **Event генериране** | Препраща | Локално | Локално |
| **Синхронност** | Async | Sync | Sync |

### Достъп до компоненти

| Аспект | Playground | Astro | Inspired |
|--------|------------|-------|----------|
| **Getter методи** | ❌ Няма | ✅ GetWallet() | N/A |
| **m_kernel в компонент** | ✅ Да | ❌ Не | N/A |
| **Draw() метод** | ❌ Не | ✅ Да | ✅ Да |

### Визуална диаграма

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PLAYGROUND (Event-based)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Integration                              KernelApi (отделен)               │
│  ┌──────────────┐                         ┌──────────────┐                  │
│  │ Components   │   слуша events          │ Playground   │                  │
│  │ Wallet ◄─────┼─────────────────────────┤ KernelApi    │                  │
│  │ Limits       │                         │              │                  │
│  └──────────────┘                         └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      ASTRO (Локално състояние)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Integration                                                                │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │ Components (с m_credit, m_betLimits)                        │            │
│  │ ┌────────────┐ ┌────────────┐                               │            │
│  │ │ Wallet     │ │ Limits     │                               │            │
│  │ │ m_credit   │ │ m_betLimits│     ┌──────────────┐          │            │
│  │ └────────────┘ └────────────┘     │ AstroEgt     │ вграден  │            │
│  │                                   │ (KernelApi)  │          │            │
│  │                                   └──────────────┘          │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     INSPIRED (Монолитен)                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Integration (САМА имплементира IWallet, ILimits, ...)                      │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                                                             │            │
│  │   m_credit, m_betLimits, m_winCapping                       │            │
│  │   (всичко директно в класа)                                 │            │
│  │                                                             │            │
│  │   ┌────────────┐          ┌──────────────┐                  │            │
│  │   │ Input      │          │ InspiredEgt  │ вграден          │            │
│  │   └────────────┘          │ (KernelApi)  │                  │            │
│  │   (единствен              └──────────────┘                  │            │
│  │    компонент)                                               │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Ключови принципи

1. **GameImport е за СТАТИЧНИ данни и EXTERNAL събития**
   - Query: `GetCredit()`, `GetBetLimits()`
   - Events: `onCreditChanged`, `buttonPressedEvent`

2. **IKernelIntegration е за ДИНАМИЧНИ операции**
   - Request-Reply: `RequestStartMatch()`, `RequestRandoms()`
   - Само Gameflow има достъп

3. **FSM е платформено независим**
   - Един и същ код за Playground, Astro, Inspired
   - Не знае откъде идват данните

4. **Компонентите са адаптери**
   - Превеждат Kernel interface към GameImport interface
   - Всяка платформа има собствена имплементация

5. **Access Control чрез RuntimeCategory**
   - FSM вижда само GameImport
   - Gameflow вижда Integration
   - Kernel е изолиран
