# Astro Integration Architecture

## Съдържание
1. [Ключови разлики от Playground](#ключови-разлики-от-playground)
2. [Диаграма на зависимостите](#диаграма-на-зависимостите)
3. [Компоненти и роли](#компоненти-и-роли)
4. [Пълен Pipeline: Burning Hot Coins за Astro](#пълен-pipeline-burning-hot-coins-за-astro)
5. [Комуникация FSM ↔ Kernel](#комуникация-fsm--kernel)
6. [Комуникация с Astro GDK](#комуникация-с-astro-gdk)

---

## Ключови разлики от Playground

| Аспект | Playground | Astro |
|--------|------------|-------|
| **Entry point** | `LauncherApp.exe` зарежда DLL | `AstroBurningHotCoins.exe` е самостоятелен |
| **Launcher** | Да (UI за избор на игра) | **Няма** - директно изпълнение |
| **Game Plugin** | `.dll` зареден динамично | Вграден в `.exe` (static linked) |
| **Kernel creation** | `PlaygroundGameLoader` създава `PlaygroundKernelApi` | `AstroIntegration` създава `AstroEgt` |
| **External system** | Няма (симулация) | **Astro GDK** (реален cabinet) |
| **Main loop** | `PlaygroundGame::Update()` | `AstroGame::Run()` (blocking loop) |

---

## Диаграма на зависимостите

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ASTRO CABINET SYSTEM                             │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     Astro GDK (External)                        │    │
│  │  - ak2api.h (API към cabinet)                                   │    │
│  │  - RNG, Credit, Touch, Buttons, Atmosphere                      │    │
│  │  - NVRAM persistence                                            │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                 │                                       │
│                                 │ IPC / Shared Memory                   │
│                                 ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              AstroBurningHotCoins.exe                           │    │
│  │                                                                 │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │                      main()                               │  │    │
│  │  │  AstroGame game("burning_hot_coins");                     │  │    │
│  │  │  return game.Run();                                       │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                           │                                     │    │
│  │                           ▼                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │                    AstroGame                              │  │    │
│  │  │  - Създава Runtime                                        │  │    │
│  │  │  - Създава ModuleManager                                  │  │    │
│  │  │  - Main loop (Process/Draw)                               │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                           │                                     │    │
│  │                           │ loads modules                       │    │
│  │                           ▼                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │                  ModuleManager                            │  │    │
│  │  │  ├── AstroVideo                                           │  │    │
│  │  │  ├── AstroIntegration ──────┐                             │  │    │
│  │  │  │      │                   │                             │  │    │
│  │  │  │      └── AstroEgt ◄──────┘ creates & owns              │  │    │
│  │  │  │           (IKernelApi impl)                            │  │    │
│  │  │  ├── AlphaFamilyGameflow                                  │  │    │
│  │  │  ├── BurningHotCoinsFsm                                   │  │    │
│  │  │  ├── BurningHotCoinsMath                                  │  │    │
│  │  │  ├── BurningHotCoinsView                                  │  │    │
│  │  │  └── ...                                                  │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │                                                                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Собственост и създаване

```
OS стартира AstroBurningHotCoins.exe
         │
         ▼
main() създава AstroGame("burning_hot_coins")    ← НА СТЕКА
         │
         │ AstroGame::Run()
         ▼
AstroGame създава:
    ├── Runtime (нов)
    └── ModuleManager
              │
              │ ModuleManager::Init() създава модули:
              ▼
         AstroIntegration (модул)
              │
              │ AstroIntegration::Init() създава:
              ▼
         AstroEgt (kernel impl)    ← OWNERSHIP в AstroIntegration
              │
              │ AstroEgt::InitAstro()
              ▼
         Връзка с Astro GDK (ak2api_init)
```

---

## Компоненти и роли

| Компонент | Тип | Роля |
|-----------|-----|------|
| **AstroBurningHotCoins.exe** | Executable | Самостоятелно приложение за Astro cabinet |
| **AstroGame** | Клас (не модул) | Entry point, main loop, държи Runtime и ModuleManager |
| **AstroIntegration** | **Модул** | Bridge към kernel, **създава и държи** `AstroEgt` |
| **AstroEgt** | Клас (не модул) | **Kernel имплементация** - комуникира с Astro GDK |
| **AlphaFamilyGameflow** | **Модул** | Gameflow логика (същият като в Playground) |
| **BurningHotCoinsFsm** | **Модул** | Game state machine (същият като в Playground) |

### Разлика в Kernel ownership

```
PLAYGROUND:                              ASTRO:
───────────                              ──────
PlaygroundGameLoader                     AstroIntegration (модул!)
    │                                        │
    └── m_kernelApi (Ptr)                    └── m_astroEgt (shared_ptr)
            │                                        │
            ▼                                        ▼
    PlaygroundKernelApi                       AstroEgt
    (standalone class)                        (IKernelApi impl)
```

**Ключова разлика:** В Astro, `AstroIntegration` е модул, който **сам създава** kernel-а (`AstroEgt`) в своя `Init()`. В Playground, kernel-ът се създава от `PlaygroundGameLoader` (който също е модул, но в Launcher-а).

---

## Пълен Pipeline: Burning Hot Coins за Astro

### Файлова структура

```
games/
├── configs/
│   ├── alpha_family/modules/
│   │   ├── AlphaAstroModules.json        ← Astro-specific shared modules
│   │   ├── AlphaDebugModules.json
│   │   └── AlphaGameModules.json
│   │
│   └── burning_hot_coins/modules/
│       ├── ModuleManager_Astro.json      ← Game module config for Astro
│       ├── BurningHotCoinsModules.json
│       └── BurningHotCoinsDebugModules.json
│
└── bin/  (или build output)
    └── AstroBurningHotCoins.exe          ← Standalone executable
```

---

### ЕТАП 1: OS стартира executable

```
┌─────────────────────────────────────────────────────────────────────────┐
│ OS стартира: AstroBurningHotCoins.exe                                   │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ main() в AstroBurningHotCoins.cpp                                   │ │
│ │                                                                     │ │
│ │ int main(int argc, char* argv[])                                    │ │
│ │ {                                                                   │ │
│ │     auto game = AstroGame("burning_hot_coins");                     │ │
│ │     return game.Run();    ← blocking call, main loop вътре          │ │
│ │ }                                                                   │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ При компилация (static linking), EXE-то съдържа:                        │
│   - EgtAstroGameStatic           ← AstroGame клас                       │
│   - EgtAstroIntegrationStatic    ← AstroIntegration, AstroEgt           │
│   - EgtBurningHotCoinsFsmStatic  ← FSM                                  │
│   - EgtBurningHotCoinsMathStatic ← Math                                 │
│   - EgtBurningHotCoinsViewStatic ← View                                 │
│   - ... 25+ static библиотеки                                           │
│                                                                         │
│ EGT_REGISTER_CLASS се изпълнява при стартиране:                         │
│   → ObjectFactoryRegistry знае за всички модули                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 2: AstroGame инициализация

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AstroGame::Run()                                                        │
│                                                                         │
│ 1. Определя base path:                                                  │
│    m_basePath = Core::Library::GetApplicationDir()                      │
│    // напр. "C:/games/" или където е exe-то                             │
│                                                                         │
│ 2. Създава Runtime:                                                     │
│    SetRuntime(RuntimeAccess(make_shared<Runtime>(), "AstroGame"))       │
│                                                                         │
│ 3. Регистрира се в Runtime:                                             │
│    RuntimeAdd<IAppControl>(this)                                        │
│    RuntimeAdd<IAppControl::Events>(this)                                │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ КОНФИГ: configs/burning_hot_coins/modules/ModuleManager_Astro.json  │ │
│ │                                                                     │ │
│ │ Формиране на пътя:                                                  │ │
│ │   jsonConfigPath = GetConfigPath() / "modules" /                    │ │
│ │                    "ModuleManager_Astro.json"                       │ │
│ │                                                                     │ │
│ │ GetConfigPath() = m_basePath / "configs" / m_gameFolder             │ │
│ │                 = "C:/games/configs/burning_hot_coins"              │ │
│ │                                                                     │ │
│ │ Пълен път: "C:/games/configs/burning_hot_coins/modules/             │ │
│ │             ModuleManager_Astro.json"                               │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ 4. Създава ModuleManager:                                               │
│    m_moduleManager = make_shared<ModuleManager>()                       │
│    m_moduleManager->LoadConfig(jsonConfigPath)                          │
│    m_moduleManager->Init(GetRuntime(), {})                              │
│    m_moduleManager->PostInit()                                          │
│    m_moduleManager->Start()                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 3: Зареждане на модули

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ModuleManager_Astro.json съдържа:                                       │
│                                                                         │
│ {                                                                       │
│   "include": [                                                          │
│     "../../alpha_family/modules/AlphaAstroModules.json",                │
│     "../../alpha_family/modules/AlphaDebugModules.json",                │
│     "BurningHotCoinsModules.json",                                      │
│     "BurningHotCoinsDebugModules.json"                                  │
│   ],                                                                    │
│   "modules": [                                                          │
│     { "override": true, "name": "VideoManager", "config": {...} },      │
│     { "override": true, "name": "BurningHotCoinsInfoView", ... }        │
│   ]                                                                     │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ЙЕРАРХИЯ НА INCLUDE ФАЙЛОВЕТЕ:                                          │
│                                                                         │
│ ModuleManager_Astro.json                                                │
│ │                                                                       │
│ ├─► AlphaAstroModules.json                                              │
│ │   │                                                                   │
│ │   ├─► AlphaGameModules.json                                           │
│ │   │   ├── VideoManager                                                │
│ │   │   ├── AudioManager                                                │
│ │   │   ├── ResourceManager                                             │
│ │   │   └── LoadingScreenView                                           │
│ │   │                                                                   │
│ │   ├── AstroVideo             ← Astro-specific video                   │
│ │   ├── AstroIntegration       ← СЪЗДАВА AstroEgt вътре!                │
│ │   ├── AlphaFamilyGameflow    ← същият като в Playground               │
│ │   ├── RecoveryManager                                                 │
│ │   ├── ResponsibleGamingManager                                        │
│ │   ├── LocalizationManager                                             │
│ │   └── MessageBoardManager                                             │
│ │                                                                       │
│ ├─► AlphaDebugModules.json                                              │
│ │   ├── LogViewer                                                       │
│ │   ├── GameFsmViewer                                                   │
│ │   └── ...                                                             │
│ │                                                                       │
│ ├─► BurningHotCoinsModules.json                                         │
│ │   ├── BurningHotCoinsFsm     ← същият като в Playground               │
│ │   ├── BurningHotCoinsMath    ← същият като в Playground               │
│ │   ├── BurningHotCoinsView    ← същият като в Playground               │
│ │   └── BurningHotCoinsInfoView                                         │
│ │                                                                       │
│ └─► BurningHotCoinsDebugModules.json                                    │
│     └── AlphaFamilyMathRngPreset                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 4: AstroIntegration създава AstroEgt

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Когато ModuleManager създава AstroIntegration:                          │
│                                                                         │
│ AstroIntegration::Init(runtime, config)                                 │
│ {                                                                       │
│     // 1. Регистрира се като IKernelIntegration                         │
│     RuntimeAdd<IKernelIntegration>(this);                               │
│     RuntimeAdd<IKernelIntegration::Events>(this);                       │
│                                                                         │
│     // 2. СЪЗДАВА AstroEgt (kernel имплементация)                       │
│     m_astroEgt = make_shared<AstroEgt>();                               │
│                                                                         │
│     // 3. ИНИЦИАЛИЗИРА Astro GDK                                        │
│     m_astroEgt->InitAstro(AstroInitData());                             │
│     //    └── ak2api_init()                                             │
│     //    └── ak2api_init_until_complete()                              │
│     //    └── Връзка с Astro cabinet е установена!                      │
│                                                                         │
│     // 4. Създава компоненти                                            │
│     m_input = make_shared<AstroInput>(*this);                           │
│     m_wallet = make_shared<AstroWallet>(*this);                         │
│     m_recovery = make_shared<AstroRecovery>(*this);                     │
│     m_limits = make_shared<AstroLimits>(*this);                         │
│ }                                                                       │
│                                                                         │
│ IKernelApi& AstroIntegration::GetKernelApi()                            │
│ {                                                                       │
│     return *m_astroEgt;   // ← Директно връща AstroEgt                  │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 5: Main Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AstroGame::Run() - Main Loop                                            │
│                                                                         │
│ while (!m_exitPending)                                                  │
│ {                                                                       │
│     // 1. Process всички модули                                         │
│     processBegin.Post();                                                │
│     m_moduleManager->Process();                                         │
│         │                                                               │
│         ├── AstroIntegration::Process()                                 │
│         │       │                                                       │
│         │       └── m_astroEgt->StartMainLoopTick()                     │
│         │               │                                               │
│         │               ├── Tools::SyncNvram()                          │
│         │               └── Tools::DownloadIncommingMsg()  ← от GDK     │
│         │                       └── _processIncommingMsg()              │
│         │                                                               │
│         ├── AlphaFamilyGameflow::Process()                              │
│         ├── BurningHotCoinsFsm::Process()                               │
│         └── ...                                                         │
│     processEnd.Post();                                                  │
│                                                                         │
│     // 2. PostProcess                                                   │
│     postProcessBegin.Post();                                            │
│     m_moduleManager->PostProcess();                                     │
│         │                                                               │
│         └── AstroIntegration::PostProcess()                             │
│                 │                                                       │
│                 └── m_astroEgt->EndMainLoopTick()                       │
│                         │                                               │
│                         ├── Tools::SaveAsyncToNvram()  ← persist state  │
│                         └── _processPendingMessage()   ← към GDK        │
│     postProcessEnd.Post();                                              │
│                                                                         │
│     // 3. Draw                                                          │
│     drawBegin.Post();                                                   │
│     draw.Post();                                                        │
│     drawImGuiBegin.Post();                                              │
│     m_moduleManager->ImGuiDraw();                                       │
│     drawImGuiEnd.Post();                                                │
│     drawEnd.Post();                                                     │
│ }                                                                       │
│                                                                         │
│ // След loop-а                                                          │
│ m_moduleManager->Stop();                                                │
│ Shutdown();                                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Комуникация FSM ↔ Kernel

### Роля на AstroIntegration

`AstroIntegration` е **bridge** между game модулите и `AstroEgt` (kernel):

```cpp
// Модулите достъпват kernel-а така:
auto& integration = RuntimeGet<IKernelIntegration>();
integration.GetKernelApi().RequestRandoms(...);

// AstroIntegration директно връща AstroEgt:
IKernelApi& AstroIntegration::GetKernelApi()
{
    return *m_astroEgt;  // m_astroEgt е създаден в Init()
}
```

**Кой използва AstroIntegration?**
- `AlphaFamilyGameflow` - за всички kernel заявки
- `AstroWallet`, `AstroRecovery`, `AstroInput` - integration компоненти

### Пълен път на комуникация: FSM → Kernel → FSM

```
┌─────────────────┐
│ BurningHotCoins-│  User натиска SPIN
│ Fsm             │─────────────────────────┐
└────────┬────────┘                         │
         │ startRound.Post()                │
         ▼                                  │
┌─────────────────┐                         │
│ AlphaFamily-    │  Gameflow логика        │
│ Gameflow        │─────────────────────────┤
└────────┬────────┘                         │
         │                                  │
         │ RuntimeGet<IKernelIntegration>() │
         ▼                                  │
┌─────────────────┐                         │
│ Astro-          │  Bridge (модул)         │
│ Integration     │─────────────────────────┤
└────────┬────────┘                         │
         │ GetKernelApi() → m_astroEgt      │
         ▼                                  │
┌─────────────────┐                         │
│ AstroEgt        │                         │
│ (IKernelApi)    │  Kernel имплементация   │
│                 │                         │
└────────┬────────┘                         │
         │                                  │
         │ ak2msg_ca_game_start             │
         │ (към Astro GDK)                  │
         ▼                                  │
┌─────────────────┐                         │
│  ASTRO CABINET  │  External system        │
│     (GDK)       │                         │
└────────┬────────┘                         │
         │                                  │
         │ ac_game_start_acked              │
         │ (от Astro GDK)                   │
         ▼                                  │
┌─────────────────┐                         │
│ AstroEgt        │  Получава отговор       │
│                 │  events.onStartMatch-   │
│                 │  Reply.Post()           │
└────────┬────────┘                         │
         │                                  │
         │ RegisterInstant()                │
         ▼                                  │
┌─────────────────┐                         │
│ AlphaFamily-    │  Получава event         │
│ Gameflow        │◄────────────────────────┤
└────────┬────────┘                         │
         │ matchStarted.Post()              │
         ▼                                  │
┌─────────────────┐                         │
│ BurningHotCoins-│  FSM получава резултат  │
│ Fsm             │◄────────────────────────┘
└─────────────────┘
```

### Сравнение: Playground vs Astro

```
PLAYGROUND:                              ASTRO:
───────────                              ──────

FSM                                      FSM
 │                                        │
 ▼                                        ▼
AlphaFamilyGameflow                      AlphaFamilyGameflow
 │                                        │
 │ RuntimeGet<IKernelIntegration>()       │ RuntimeGet<IKernelIntegration>()
 ▼                                        ▼
PlaygroundIntegration                    AstroIntegration
 │                                        │
 │ GetKernelApi()                         │ GetKernelApi()
 │   └── RuntimeGet<IPlaygroundGame>()    │   └── return *m_astroEgt
 │       .GetKernelApi()                  │
 ▼                                        ▼
PlaygroundGame                           AstroEgt
 │                                        │
 │ m_kernel reference                     │ ak2api calls
 ▼                                        ▼
PlaygroundKernelApi                      ASTRO GDK (cabinet)
 │                                        │
 │ (симулация)                            │ (реален hardware)
 ▼                                        ▼
Локална обработка                        Cabinet процесор
```

### Ключова разлика в ownership

| Аспект | Playground | Astro |
|--------|------------|-------|
| **Kernel създаден от** | `PlaygroundGameLoader` | `AstroIntegration` |
| **Kernel държан от** | `PlaygroundGameLoader` | `AstroIntegration` |
| **Integration достъпва kernel чрез** | `RuntimeGet<IPlaygroundGame>()` | Директна член-променлива |
| **Kernel комуникира с** | Нищо (локална симулация) | Astro GDK (external) |

### Конкретен пример: Spin Request

```cpp
// 1. FSM иска да започне мач
// BurningHotCoinsFsm.cpp
void BurningHotCoinsFsm::OnSpinPressed()
{
    RuntimeGet<IGameflowIntegration>().RequestStartMatch(currentBet, "main");
}

// 2. Gameflow препраща към kernel
// AlphaFamilyGameflow.cpp
void AlphaFamilyGameflow::RequestStartMatch(uint64_t bet, const Name& name)
{
    auto& kernel = RuntimeGet<IKernelIntegration>().GetKernelApi();
    kernel.RequestStartMatch(bet, name);  // → AstroEgt::RequestStartMatch()
}

// 3. AstroEgt изпраща към cabinet
// AstroEgt.cpp
void AstroEgt::RequestStartMatch(uint64_t bet, const Name& name)
{
    StateMutable().matchName = name;
    StateMutable().matchInitialBet = bet;

    // Създава Astro съобщение
    ak2msg_ca_game_start gameStartMsg;
    gameStartMsg.bet_ce = bet;
    gameStartMsg.bool_max_bet = (bet == m_initData.gameMaxBet) ? 1 : 0;

    // Запазва в NVRAM и изпраща
    _saveAndSendMsg(gameStartMsg, "ca_game_start");
}

// 4. Cabinet отговаря (асинхронно, в следващ tick)
// AstroEgt::StartMainLoopTick() обработва входящи съобщения
void AstroEgt::_processIncommingMsg()
{
    // ...
    case Core::Crc("ac_game_start_acked"):
    {
        const auto& msg = AstroMsg<ak2msg_ac_game_start_acked>(msgBuff);

        // Изпраща event към listeners
        events.onStartMatchReply.Post(msg.bool_enabled == 1, State().matchName);
    }
    // ...
}

// 5. Gameflow получава event-а
// AlphaFamilyGameflow.cpp (регистриран в Init)
void AlphaFamilyGameflow::OnKernelStartMatchReply(bool enabled, const Name& name)
{
    // Уведомява FSM
    matchStarted.Post(enabled, name);
}

// 6. FSM получава резултата и продължава
// BurningHotCoinsFsm.cpp (слуша matchStarted)
void BurningHotCoinsFsm::OnMatchStarted(bool enabled, const Name& name)
{
    if (enabled)
    {
        // Преход към следващо състояние
        TransitionTo<SpinningState>();
    }
}
```

### Диаграма на event flow

```
                    REQUEST PATH                      RESPONSE PATH
                    ────────────                      ─────────────
                         │                                 ▲
   ┌─────────────────────┼─────────────────────────────────┼──────────────┐
   │ FSM                 │                                 │              │
   │                     │ StartMatch()                    │ matchStarted │
   └─────────────────────┼─────────────────────────────────┼──────────────┘
                         │                                 │
   ┌─────────────────────┼─────────────────────────────────┼──────────────┐
   │ Gameflow            │                                 │              │
   │                     │ RequestStartMatch()             │ OnKernel-    │
   │                     │                                 │ StartMatch-  │
   │                     │                                 │ Reply()      │
   └─────────────────────┼─────────────────────────────────┼──────────────┘
                         │                                 │
   ┌─────────────────────┼─────────────────────────────────┼──────────────┐
   │ AstroIntegration    │                                 │              │
   │                     │ GetKernelApi()                  │ (events      │
   │                     │                                 │  forwarded)  │
   └─────────────────────┼─────────────────────────────────┼──────────────┘
                         │                                 │
   ┌─────────────────────┼─────────────────────────────────┼──────────────┐
   │ AstroEgt            │                                 │              │
   │                     │ _saveAndSendMsg()               │ events.on-   │
   │                     │                                 │ StartMatch-  │
   │                     │                                 │ Reply.Post() │
   └─────────────────────┼─────────────────────────────────┼──────────────┘
                         │                                 │
   ┌─────────────────────┼─────────────────────────────────┼──────────────┐
   │ Astro GDK           │                                 │              │
   │                     │ ca_game_start                   │ ac_game_     │
   │                     ▼                                 │ start_acked  │
   │              ═══════════════                   ═══════════════       │
   │              │  CABINET   │ ───────────────► │  RESPONSE  │          │
   │              ═══════════════                   ═══════════════       │
   └──────────────────────────────────────────────────────────────────────┘
```

---

## Комуникация с Astro GDK

### AstroEgt като мост към cabinet-а

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          GAME LAYER                                     │
│                                                                         │
│  BurningHotCoinsFsm                                                     │
│         │                                                               │
│         │ RuntimeGet<IGameflowIntegration>().StartRound()               │
│         ▼                                                               │
│  AlphaFamilyGameflow                                                    │
│         │                                                               │
│         │ RuntimeGet<IKernelIntegration>().GetKernelApi()               │
│         ▼                                                               │
│  AstroIntegration::GetKernelApi()                                       │
│         │                                                               │
│         │ return *m_astroEgt                                            │
│         ▼                                                               │
│  AstroEgt (IKernelApi implementation)                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Astro GDK API calls
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ASTRO GDK LAYER                                  │
│                                                                         │
│  AstroEgt методи                    →    Astro GDK функции              │
│  ─────────────────                       ──────────────────             │
│  RequestStartMatch()                →    ak2msg_ca_game_start           │
│  RequestRandoms()                   →    ak2msg_ca_rng_request          │
│  RequestRoundOutcome()              →    ak2msg_ca_game_step            │
│  RequestEndMatch()                  →    ak2msg_ca_game_end             │
│  RequestCashout()                   →    ak2msg_ca_credit_payout        │
│                                                                         │
│  Incoming messages (от cabinet):                                        │
│  ───────────────────────────────                                        │
│  ac_game_start_acked               →    events.onStartMatchReply        │
│  ac_rng_result                     →    events.onRandomsReply           │
│  ac_game_step_acked                →    events.onRoundOutcomeReply      │
│  ac_game_end_acked                 →    events.onEndMatchReply          │
│  ac_credit_changed                 →    events.creditChanged            │
│  ac_key_down/up                    →    events.buttonDown/Up            │
│  ac_touch_pressed/released         →    events.touchPressed/Released    │
│  ac_flow_suspend/resume            →    events.suspendRequested         │
│  ac_flow_terminate                 →    events.terminateRequested       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Пример: Spin flow с Astro

```cpp
// 1. FSM иска да започне мач
// BurningHotCoinsFsm → AlphaFamilyGameflow
RuntimeGet<IGameflowIntegration>().RequestStartMatch(bet, "main");

// 2. Gameflow изпраща към kernel
// AlphaFamilyGameflow.cpp
void AlphaFamilyGameflow::RequestStartMatch(uint64_t bet, const Name& name)
{
    auto& kernel = RuntimeGet<IKernelIntegration>().GetKernelApi();
    kernel.RequestStartMatch(bet, name);
}

// 3. AstroEgt изпраща към Astro GDK
// AstroEgt.cpp
void AstroEgt::RequestStartMatch(uint64_t bet, const Name& name)
{
    StateMutable().matchName = name;
    StateMutable().matchInitialBet = bet;

    ak2msg_ca_game_start gameStartMsg;
    gameStartMsg.bet_ce = bet;
    gameStartMsg.bool_max_bet = (bet == m_initData.gameMaxBet) ? 1 : 0;

    _saveAndSendMsg(gameStartMsg, "ca_game_start");
    // → Съобщението отива към Astro cabinet
}

// 4. Cabinet отговаря (в следващ tick)
// AstroEgt::_processIncommingMsg()
case Core::Crc("ac_game_start_acked"):
{
    const auto& msg = AstroMsg<ak2msg_ac_game_start_acked>(msgBuff);
    events.onStartMatchReply.Post(msg.bool_enabled == 1, State().matchName);
    // → Event се получава от AlphaFamilyGameflow
}

// 5. Gameflow уведомява FSM
// AlphaFamilyGameflow слуша onStartMatchReply
void AlphaFamilyGameflow::OnStartMatchReply(bool enabled, const Name& name)
{
    matchStarted.Post(enabled, name);  // FSM слуша това
}
```

---

## Обобщение: Сравнение на Pipeline-ите

```
PLAYGROUND:                              ASTRO:
═══════════                              ══════

OS → LauncherApp.exe                     OS → AstroBurningHotCoins.exe
        │                                        │
        ▼                                        ▼
LauncherApp                              main()
        │                                        │
        ▼                                        ▼
ModuleManager #1 (Launcher)              AstroGame
        │                                        │
        │ loads                                  │ creates
        ▼                                        ▼
PlaygroundGameLoader (модул)             ModuleManager (единствен!)
        │                                        │
        │ creates                                │ loads
        ├──► PlaygroundKernelApi                 │
        │                                        ▼
        │ loads DLL                      AstroIntegration (модул)
        ▼                                        │
PlaygroundBurningHotCoins.dll                    │ creates
        │                                        ▼
        │ create_game()                  AstroEgt (kernel)
        ▼                                        │
PlaygroundGame                                   │ connects to
        │                                        ▼
        │ creates                        Astro GDK (cabinet)
        ▼
ModuleManager #2 (Game)
        │
        │ loads
        ▼
PlaygroundIntegration (модул)
        │
        │ delegates to
        ▼
PlaygroundGame.GetKernelApi()
```

### Таблица: Къде живеят модулите

| Модул | Playground | Astro |
|-------|------------|-------|
| BurningHotCoinsFsm | `PlaygroundBurningHotCoins.dll` | `AstroBurningHotCoins.exe` |
| AlphaFamilyGameflow | `PlaygroundBurningHotCoins.dll` | `AstroBurningHotCoins.exe` |
| Kernel Integration | `PlaygroundIntegration` (в DLL) | `AstroIntegration` (в EXE) |
| Kernel Implementation | `PlaygroundKernelApi` (от GameLoader) | `AstroEgt` (от AstroIntegration) |

### Таблица: Config файлове

| Етап | Playground | Astro |
|------|------------|-------|
| Launcher modules | `ModuleManager_Lobby.json` | **N/A** |
| Game Loader | `Module_PlaygroundGameLoader.json` | **N/A** |
| Game modules | `ModuleManager_Playground.json` | `ModuleManager_Astro.json` |
| Shared Astro/Playground | `AlphaPlaygroundModules.json` | `AlphaAstroModules.json` |
