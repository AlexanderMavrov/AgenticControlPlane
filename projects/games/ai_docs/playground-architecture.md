# Playground Integration Architecture

## Съдържание
1. [Обща диаграма](#обща-диаграма)
2. [Game Plugin структура](#game-plugin-структура)
3. [Стъпки при зареждане на игра](#стъпки-при-зареждане-на-игра)
4. [Класове и роли](#класове-и-роли)
5. [ModuleManager архитектура](#modulemanager-архитектура)
6. [Комуникация Game ↔ Kernel](#комуникация-game--kernel)
7. [Различни интеграции](#различни-интеграции)
8. [Пълен Pipeline: Burning Hot Coins](#пълен-pipeline-burning-hot-coins)

---

## Обща диаграма

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              LAUNCHER                                    │
│  ┌─────────────┐     ┌─────────────┐     ┌──────────────────────────┐    │
│  │ LauncherApp │────►│LauncherLobby│────►│ Module_PlaygroundGame-   │    │
│  │  (startup)  │     │  (UI/лоби)  │     │ Loader.json              │    │
│  └─────────────┘     └─────────────┘     └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                    loads module dynamically (step 2)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         KERNEL LAYER                                     │
│  ┌─────────────────────┐  creates   ┌─────────────────────┐              │
│  │ PlaygroundGameLoader│───────────►│  PlaygroundKernelApi│              │
│  │      (Module)       │            │   (Kernel impl)     │              │
│  └──────────┬──────────┘            └──────────┬──────────┘              │
│             │                                  ▲                         │
│             │ loads plugin (step 3)            │ reference               │
│             ▼                                  │                         │
│  ┌─────────────────────────────────────────────┴──────────┐              │
│  │              Game Plugin (.dll/.so)                    │              │
│  │  ┌───────────────────────────────────────────────────┐ │              │
│  │  │ PlaygroundBurningHotCoins.dll                     │ │              │
│  │  │  - EGT_REGISTER_CLASS(BurningHotCoinsFsm, ...)    │ │              │
│  │  │  - create_game() → creates PlaygroundGame         │ │              │
│  │  └───────────────────────────────────────────────────┘ │              │
│  └────────────────────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                    PlaygroundGame::LoadGame() (step 4)
                    loads ModuleManager_Playground.json
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          GAME LAYER (Modules)                            │
│                                                                          │
│  ┌────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │PlaygroundIntegration│  │ AlphaFamilyGameflow │  │ BurningHotCoins- │  │
│  │(IKernelIntegration) │  │    (Gameflow)       │  │ Fsm (FSM)        │  │
│  └────────────────────┘  └─────────────────────┘  └──────────────────┘   │
│                                                                          │
│  ┌────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │   VideoManager     │  │   ResourceManager   │  │ BurningHotCoins- │   │
│  │                    │  │                     │  │ View             │   │
│  └────────────────────┘  └─────────────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Game Plugin структура

### Какво е `PlaygroundBurningHotCoins.dll`?

Game Plugin-ът е **един DLL файл**, който съдържа:
1. Код на всички модули (static linked библиотеки)
2. Регистрация на модулите в ObjectFactoryRegistry
3. `create_game()` функция, която създава `PlaygroundGame`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PlaygroundBurningHotCoins.dll                        │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    STATIC LINKED LIBRARIES                         │ │
│  │                    (КОД, вграден в DLL-а)                          │ │
│  │                                                                    │ │
│  │  EgtPlaygroundGameStatic        ← PlaygroundGame клас              │ │
│  │  EgtPlaygroundIntegrationStatic ← PlaygroundIntegration клас       │ │
│  │  EgtBurningHotCoinsFsmStatic    ← BurningHotCoinsFsm клас          │ │
│  │  EgtBurningHotCoinsMathStatic   ← BurningHotCoinsMath клас         │ │
│  │  EgtBurningHotCoinsViewStatic   ← BurningHotCoinsView клас         │ │
│  │  EgtVideoManagerStatic          ← VideoManager клас                │ │
│  │  ... още 20+ библиотеки                                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    PlaygroundBurningHotCoins.cpp                   │ │
│  │                                                                    │ │
│  │  // Регистрира класовете в ObjectFactoryRegistry                   │ │
│  │  EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm)                   │ │
│  │  EGT_REGISTER_CLASS(IModule, PlaygroundIntegration)                │ │
│  │  ...                                                               │ │
│  │                                                                    │ │
│  │  // Експортира create_game()                                       │ │
│  │  extern "C" IPlaygroundGameApi* create_game(IPlaygroundKernelApi*) │ │
│  │  {                                                                 │ │
│  │      g_game = make_unique<PlaygroundGame>(*kernel, "burning_hot"); │ │
│  │      return g_game.get();                                          │ │
│  │  }                                                                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### CMakeLists.txt - какво се линква?

```cmake
# integration/playground/plugins/src/Egt/PlaygroundBurningHotCoins/CMakeLists.txt
egt_create_plugin(
    LINK_LIBRARIES
    # Playground core
    EgtPlaygroundGameStatic           # PlaygroundGame клас
    EgtPlaygroundIntegrationStatic    # PlaygroundIntegration модул
    EgtPlaygroundVideoStatic

    # Common modules
    EgtAlphaFamilyGameflowStatic      # Gameflow логика
    EgtVideoManagerStatic             # Video rendering
    EgtResourceManagerStatic          # Resource loading
    ...

    # Game-specific modules
    EgtBurningHotCoinsFsmStatic       # FSM на играта
    EgtBurningHotCoinsMathStatic      # Math логика
    EgtBurningHotCoinsViewStatic      # UI views
)
```

### Link-time vs Run-time: Два етапа

| Етап | Какво се случва | Резултат |
|------|-----------------|----------|
| **Link-time** (build) | CMake линква static libs | Кодът е **вграден** в DLL |
| **DLL Load** (runtime) | `EGT_REGISTER_CLASS` се изпълнява | ObjectFactoryRegistry **знае** за класовете |
| **create_game()** (runtime) | Създава `PlaygroundGame` | Една **инстанция** на PlaygroundGame |
| **ModuleManager** (runtime) | Създава модули от JSON | **Инстанции** на FSM, View, Math... |

### Пълен flow: От DLL до работещи модули

```
1. PlaygroundGameLoader зарежда DLL
   │  LoadLibrary("PlaygroundBurningHotCoins.dll")
   │
   │  При зареждане, static обектите се инициализират:
   │  EGT_REGISTER_CLASS(...) → ObjectFactoryRegistry се попълва
   │
   ▼
2. PlaygroundGameLoader извиква create_game()
   │
   │  create_game(kernel)
   │  {
   │      g_game = make_unique<PlaygroundGame>(*kernel, "burning_hot_coins");
   │      return g_game.get();
   │  }
   │
   │  ┌─────────────────────────────────────────────────────────┐
   │  │ PlaygroundGame е СЪЗДАДЕН, но модулите още НЕ СА!       │
   │  │ m_moduleManager = nullptr                               │
   │  └─────────────────────────────────────────────────────────┘
   │
   ▼
3. PlaygroundGameLoader извиква LoadGame()
   │
   │  PlaygroundGame::LoadGame("configs/burning_hot_coins")
   │  {
   │      // Създава ModuleManager
   │      m_moduleManager = make_shared<ModuleManager>();
   │
   │      // Чете JSON конфиг
   │      m_moduleManager->LoadConfig("ModuleManager_Playground.json");
   │
   │      // ЗА ВСЕКИ модул в JSON-а:
   │      // { "name": "BurningHotCoinsFsm", ... }
   │      //
   │      // ModuleManager пита ObjectFactoryRegistry:
   │      // "Можеш ли да създадеш IModule с име 'BurningHotCoinsFsm'?"
   │      // Registry: "Да, имам factory за това"
   │      //
   │      // CreateObjectByKey<IModule>("BurningHotCoinsFsm")
   │      // → Създава НОВА ИНСТАНЦИЯ на BurningHotCoinsFsm
   │
   │      m_moduleManager->Init();  // извиква Init() на всеки модул
   │  }
   │
   ▼
4. Резултат: Йерархия от обекти

   PlaygroundBurningHotCoins.dll (заредена в паметта)
       │
       └── g_game: PlaygroundGame (1 инстанция)
               │
               └── m_moduleManager: ModuleManager
                       │
                       ├── BurningHotCoinsFsm инстанция
                       ├── BurningHotCoinsMath инстанция
                       ├── BurningHotCoinsView инстанция
                       ├── PlaygroundIntegration инстанция
                       ├── VideoManager инстанция
                       └── ... още ~20 модула
```

### Връзката между CMake linking и ModuleManager

```
CMakeLists.txt                          PlaygroundBurningHotCoins.cpp
──────────────────                      ─────────────────────────────
EgtBurningHotCoinsFsmStatic    ───►     EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm)
(код е ВГРАДЕН в DLL)                   (регистрира FACTORY в registry)
                                                    │
                                                    ▼
                                        ModuleManager чете JSON:
                                        { "name": "BurningHotCoinsFsm" }
                                                    │
                                                    ▼
                                        CreateObjectByKey<IModule>("BurningHotCoinsFsm")
                                                    │
                                                    ▼
                                        new BurningHotCoinsFsm()  ← ИНСТАНЦИЯ!
```

### FAQ: Често задавани въпроси

**Q: Кой създава PlaygroundGame?**
- `create_game()` функцията в DLL-а
- Извиква се от `PlaygroundGameLoader`
- PlaygroundGame е **една инстанция**, която управлява целия game lifecycle

**Q: create_game() създава ли DLL-а?**
- **Не!** DLL-ът вече е зареден с `LoadLibrary()`
- `create_game()` създава **инстанция** на `PlaygroundGame` клас

**Q: DLL-ът държи модули ли?**
- DLL **съдържа кода** на модулите (static linked)
- Но **инстанциите** се създават по-късно от ModuleManager

**Q: Защо се линква BurningHotCoinsFsm в CMake И се създава от ModuleManager?**
- **CMake linking** = кодът на класа е в DLL-а (compile-time)
- **EGT_REGISTER_CLASS** = registry знае как да създаде инстанция (load-time)
- **ModuleManager** = създава реални инстанции по JSON конфиг (run-time)

**Q: Може ли един модул да е в DLL-а, но да не се зареди?**
- **Да!** Ако не е в JSON конфига, ModuleManager няма да го създаде
- Кодът е там, но няма инстанция

---

## Стъпки при зареждане на игра

### Пример: Burning Hot Coins с Playground kernel

### Стъпка 1: Стартиране на Launcher

```
LauncherApp стартира
    │
    ├── Зарежда своите модули от configs/launcher/modules/...
    │   (LauncherLobby, LauncherVideo, etc.)
    │
    └── Показва лоби UI с наличните игри
```

**LauncherApp** не зарежда kernel модул при стартиране - това става едва когато user избере игра.

### Стъпка 2: Избор на игра и зареждане на Kernel модул

Когато user кликне на "Burning Hot Coins":

```cpp
// LauncherLobby.cpp:1281-1309
void LauncherLobby::DoLoadGame(Ptr<GameInfo> gameInfo)
{
    // 1. Определя кой kernel да зареди
    const auto kernelType = gameInfo->GetKernelType();  // KernelType::Playground

    // 2. Намира конфига за kernel модула
    const auto cfgFileName = "Module_" + GameInfo::GetKernelModuleName(kernelType) + ".json";
    // → "Module_PlaygroundGameLoader.json"

    // 3. Зарежда kernel модула динамично
    auto& moduleManager = RuntimeGet<Game::IModuleManager>();
    moduleManager.LoadModule(GetRuntime(), moduleConfig);

    // 4. Извиква LoadGame
    gameModule->LoadGame(gameInfo);
}
```

**Как се указва кой Kernel да се използва?**
- `GameInfo::GetKernelType()` връща типа (Playground/Hat/Astro/Inspired)
- Това се определя от manifest файла на играта или от UI селекция
- `GetKernelModuleName()` map-ва типа към име на модул:
  - `Playground` → `"PlaygroundGameLoader"`
  - `Hat` → `"HatGameLoader"`
  - `Inspired` → `"InspiredGameLoader"`

### Стъпка 3: PlaygroundGameLoader създава Kernel и зарежда Game Plugin

```cpp
// PlaygroundGameLoader.cpp:78-136
void PlaygroundGameLoader::LoadGame(Ptr<GameInfo> gameInfo)
{
    // 1. СЪЗДАВА PlaygroundKernelApi
    m_kernelApi = std::make_shared<PlaygroundKernelApi>(*this);
    m_kernelApi->Init(config);

    // 2. ЗАРЕЖДА Game Plugin (.dll)
    // Path: plugins/PlaygroundBurningHotCoins.dll
    m_gamePlugin = PluginLoader().LoadPlugin(gamePluginPath);

    // 3. НАМИРА create_game symbol
    auto createGame = m_gamePlugin->Resolve("create_game");

    // 4. СЪЗДАВА PlaygroundGame чрез plugin-а
    m_gameApi = createGame(&*m_kernelApi);  // подава kernel референция

    // 5. СТАРТИРА играта
    m_gameApi->LoadGame(basePath);  // basePath = "playground/burning_hot_coins"
    m_gameApi->StartGame();
}
```

**Какво прави Game Plugin-ът?**

```cpp
// PlaygroundBurningHotCoins.cpp

// 1. РЕГИСТРИРА всички модули на играта в ObjectFactory
EGT_REGISTER_CLASS(IModule, PlaygroundIntegration);
EGT_REGISTER_CLASS(IModule, AlphaFamilyGameflow);
EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm);
EGT_REGISTER_CLASS(IModule, BurningHotCoinsMath);
EGT_REGISTER_CLASS(IModule, BurningHotCoinsView);
// ... много други модули

// 2. ЕКСПОРТИРА create_game функция
extern "C" IPlaygroundGameApi* create_game(IPlaygroundKernelApi* kernel)
{
    g_game = std::make_unique<PlaygroundGame>(*kernel, "burning_hot_coins");
    return g_game.get();
}
```

### Стъпка 4: PlaygroundGame зарежда модулите на играта

```cpp
// PlaygroundGame.cpp:28-58
bool PlaygroundGame::LoadGame(const std::string& basePath)
{
    SetBasePath(basePath);  // "playground/burning_hot_coins"

    // 1. Намира JSON конфига за модулите
    const auto jsonConfigPath = GetConfigPath() / "modules" / "ModuleManager_Playground.json";
    // → "configs/burning_hot_coins/modules/ModuleManager_Playground.json"

    // 2. Създава ModuleManager
    m_moduleManager = std::make_shared<ModuleManager>();
    m_moduleManager->LoadConfig(jsonConfigPath);

    // 3. Инициализира всички модули
    m_moduleManager->Init(...);
    m_moduleManager->PostInit();
}
```

**Какво съдържа ModuleManager_Playground.json?**

```json
{
  "include": [
    "../../alpha_family/modules/AlphaPlaygroundModules.json",  // PlaygroundIntegration, Gameflow...
    "../../alpha_family/modules/AlphaDebugModules.json",       // Debug tools
    "BurningHotCoinsModules.json",                             // FSM, Math, View за играта
    "BurningHotCoinsDebugModules.json"
  ],
  "modules": [
    { "override": true, "name": "VideoManager", "config": {...} }
  ]
}
```

**Йерархия на модулните конфиги:**
```
ModuleManager_Playground.json
├── AlphaPlaygroundModules.json
│   ├── AlphaGameModules.json
│   │   ├── VideoManager
│   │   ├── AudioManager
│   │   ├── ResourceManager
│   │   └── LoadingScreenView
│   ├── PlaygroundVideo
│   ├── PlaygroundIntegration     ◄── exposes IKernelIntegration
│   ├── AlphaFamilyGameflow       ◄── gameflow logic
│   └── AlphaFamilyBridge
│
├── AlphaDebugModules.json
│   ├── LogViewer
│   ├── GameFsmViewer
│   └── ...
│
└── BurningHotCoinsModules.json
    ├── BurningHotCoinsFsm        ◄── state machine
    ├── BurningHotCoinsMath
    ├── BurningHotCoinsView
    └── BurningHotCoinsInfoView
```

---

## Класове и роли

| Клас | Модул? | Създава се от | Роля |
|------|--------|---------------|------|
| **LauncherApp** | Не | OS (main) | Главно приложение, startup |
| **LauncherLobby** | Да | LauncherApp | UI лоби, избор на игра |
| **PlaygroundGameLoader** | **Да** | LauncherLobby | Зарежда игри, **държи** `PlaygroundKernelApi` |
| **PlaygroundKernelApi** | Не | PlaygroundGameLoader | Kernel имплементация - RNG, credit, match/round |
| **PlaygroundGame** | Не | Game Plugin | Game lifecycle, **държи референция** към kernel |
| **PlaygroundIntegration** | **Да** | ModuleManager | **Bridge** - expose-ва kernel към модулите |
| **AlphaFamilyGameflow** | **Да** | ModuleManager | Gameflow логика - свързва FSM с kernel |
| **BurningHotCoinsFsm** | **Да** | ModuleManager | State machine на конкретната игра |

### Кой какво държи?

```
PlaygroundGameLoader
    │
    ├── m_kernelApi: Ptr<PlaygroundKernelApi>     ← OWNERSHIP
    └── m_gameApi: UniquePtr<IPlaygroundGameApi>  ← OWNERSHIP
                          │
                          ▼
                   PlaygroundGame
                          │
                          └── m_kernel: IPlaygroundKernelApi&  ← REFERENCE only
```

---

## ModuleManager архитектура

### Множество ModuleManager инстанции

Системата използва **няколко независими ModuleManager-а**, всеки управляващ своя група модули:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LAUNCHER                                        │
│                                                                         │
│   LauncherApp                                                           │
│       │                                                                 │
│       └── m_moduleManager ─────► ModuleManager #1                       │
│                                    │                                    │
│                                    ├── LauncherLobby                    │
│                                    ├── LauncherVideo                    │
│                                    └── PlaygroundGameLoader ◄── модул!  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ creates (при избор на игра)
                                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         GAME (PlaygroundGame)                           │
│                                                                         │
│   PlaygroundGame                                                        │
│       │                                                                 │
│       └── m_moduleManager ─────► ModuleManager #2                       │
│                                    │                                    │
│                                    ├── PlaygroundIntegration            │
│                                    ├── AlphaFamilyGameflow              │
│                                    ├── BurningHotCoinsFsm               │
│                                    ├── VideoManager                     │
│                                    └── ...                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Споделен Runtime с ограничен достъп

Въпреки че има **отделни ModuleManager-и**, всички модули регистрират услуги в **един общ Runtime**.

Но: всеки модул получава **RuntimeAccess** - wrapper с permission маски:

```cpp
// ModuleManager.cpp:233-234
auto access = ResolveRuntimeAccessMasks(cfg);
runtime = RuntimeAccess(runtime, access.addRemove, access.readWrite, access.readOnly, cfg.name);
```

### Permission система

В JSON конфига всеки модул декларира какъв достъп му трябва:

```json
// BurningHotCoinsModules.json
{
  "name": "BurningHotCoinsFsm",
  "runtimeAccess": {
    "GameFsm": "rwx",                              // пълен достъп
    "GameMath,GameView,GameImport,GameDebug": "rw" // read-write
  }
}
```

**Permissions:**
- `r` - read only (`RuntimeGetConst`)
- `w` - read-write (`RuntimeGet`)
- `x` - add/remove (`RuntimeAdd`, `RuntimeRemove`)

**Категории** (дефинирани в интерфейсите):

| Категория | Описание | Примерни интерфейси |
|-----------|----------|---------------------|
| `GameFsm` | State machine | `IGameFsm`, `IGameState` |
| `GameMath` | Math/RNG | `IGameMath`, `IRngPreset` |
| `GameView` | Views/UI | `IGameView`, `IVideoManager` |
| `GameImport` | Imports | `IAppControl`, `IResourceManager` |
| `Integration` | Kernel integration | `IKernelIntegration`, `IKernelApi` |
| `GameDebug` | Debug tools | `IDebugOverlay`, `ILogViewer` |

### Пример: Защо FSM не може да достъпи Kernel директно

```json
// BurningHotCoinsFsm има:
"runtimeAccess": {
  "GameFsm": "rwx",
  "GameMath,GameView,GameImport,GameDebug": "rw"
}
// НЯМА "Integration" категория!

// AlphaFamilyGameflow има:
"runtimeAccess": {
  "Integration,GameMask": "rwx"  // има Integration
}
```

Ако `BurningHotCoinsFsm` се опита да извика:
```cpp
RuntimeGet<IKernelIntegration>()  // IKernelIntegration е в категория "Integration"
```

Ще получи **RuntimeAccessViolation** exception!

### Защо така?

1. **Изолация** - FSM не трябва да знае за kernel детайли
2. **Принудителна архитектура** - комуникацията минава през Gameflow
3. **Testability** - FSM може да се тества без реален kernel
4. **Security** - модулите не могат да манипулират неща извън scope-а си

### Диаграма на достъпа

```
┌────────────────────┐
│ BurningHotCoinsFsm │  runtimeAccess: GameFsm, GameMath, GameView...
└────────┬───────────┘
         │ RuntimeGet<IGameflowIntegration>() ✓ (GameMask включва това)
         ▼
┌────────────────────┐
│ AlphaFamilyGameflow│  runtimeAccess: Integration, GameMask
└────────┬───────────┘
         │ RuntimeGet<IKernelIntegration>() ✓ (има Integration)
         ▼
┌────────────────────────┐
│ PlaygroundIntegration  │  runtimeAccess: Integration, GameMask
└────────────────────────┘
```

---

## Комуникация Game ↔ Kernel

### Роля на PlaygroundIntegration

`PlaygroundIntegration` е **bridge/adapter** - не съдържа бизнес логика:

```cpp
// Модулите достъпват kernel-а така:
auto& integration = RuntimeGet<IKernelIntegration>();
integration.GetKernelApi().RequestRandoms(...);

// PlaygroundIntegration просто делегира:
IKernelApi& PlaygroundIntegration::GetKernelApi()
{
    auto& game = RuntimeGet<IPlaygroundGame>();
    return game.GetKernelApi();
}
```

**Кой използва PlaygroundIntegration?**
- `AlphaFamilyGameflow` - за всички kernel заявки
- `PlaygroundWallet`, `PlaygroundRecovery` - integration компоненти

**Кой НЕ минава през нея?**
- `PlaygroundGame` - има директна референция
- `PlaygroundGameLoader` - държи kernel-а

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
│ Playground-     │  Bridge                 │
│ Integration     │─────────────────────────┤
└────────┬────────┘                         │
         │ GetKernelApi()                   │
         ▼                                  │
┌─────────────────┐                         │
│ PlaygroundGame  │  Делегира               │
└────────┬────────┘                         │
         │ m_kernel reference               │
         ▼                                  │
┌─────────────────┐                         │
│ Playground-     │                         │
│ KernelApi       │  Обработва заявката     │
│                 │  RequestStartMatch()    │
│                 │  RequestRandoms()       │
└────────┬────────┘                         │
         │                                  │
         │ Events: onRandomsReply.Post()    │
         ▼                                  │
┌─────────────────┐                         │
│ AlphaFamily-    │  RegisterInstant()      │
│ Gameflow        │◄────────────────────────┤
└────────┬────────┘                         │
         │ roundEnded.Post()                │
         ▼                                  │
┌─────────────────┐                         │
│ BurningHotCoins-│  FSM получава резултат  │
│ Fsm             │◄────────────────────────┘
└─────────────────┘
```

### Конкретен пример: Spin

```cpp
// 1. FSM иска да започне рунд
// BurningHotCoinsFsm → AlphaFamilyGameflow
RuntimeGet<IGameflowIntegration>().StartRound(...);

// 2. Gameflow изпраща към kernel
// AlphaFamilyGameflow.cpp
void AlphaFamilyGameflow::StartRound(...)
{
    auto& kernel = RuntimeGet<IKernelIntegration>();
    kernel.GetKernelApi().RequestStartRound(otherBets, roundName);
}

// 3. Kernel обработва и връща резултат чрез event
// PlaygroundKernelApi.cpp
void PlaygroundKernelApi::ProcessClientMessage(StartRoundRequest request)
{
    // ... process ...
    SendKernelMessage(StartRoundReply{...});
}

// 4. Gameflow слуша за отговора
// AlphaFamilyGameflow.cpp (в Init)
RegisterInstant(events.onStartRoundReply, this, &OnKernelStartRoundReply);

// 5. Gameflow уведомява FSM
void AlphaFamilyGameflow::OnKernelStartRoundReply(...)
{
    roundStarted.Post(...);  // FSM слуша това
}
```

---

## Различни интеграции

| Integration | Kernel API | GameLoader | Game Plugin |
|-------------|------------|------------|-------------|
| **Playground** | `PlaygroundKernelApi` | `PlaygroundGameLoader` | `PlaygroundBurningHotCoins.dll` |
| **Inspired** | `InspiredEgt` | `InspiredGameLoader` | `InspiredRiseOfRa.dll` |
| **Astro** | `AstroKernelApi` | `AstroGameLoader` | `AstroXxx.dll` |
| **Hat** | `HatKernelApi` | `HatGameLoader` | `HatXxx.dll` |

Модулите на играта (FSM, Views) работят с `IKernelApi` интерфейс - не знаят коя интеграция се използва. Това позволява една игра да работи с различни платформи.

---

## Пълен Pipeline: Burning Hot Coins

### Файлова структура

```
games/
├── configs/
│   ├── launcher/modules/
│   │   ├── ModuleManager_Lobby.json          ← Launcher конфиг
│   │   └── Module_PlaygroundGameLoader.json  ← GameLoader конфиг
│   │
│   ├── alpha_family/modules/
│   │   ├── AlphaPlaygroundModules.json       ← Shared модули за Playground
│   │   ├── AlphaDebugModules.json            ← Debug модули
│   │   └── AlphaGameModules.json             ← Base game модули
│   │
│   └── burning_hot_coins/modules/
│       ├── ModuleManager_Playground.json     ← Game модул конфиг
│       ├── BurningHotCoinsModules.json       ← Game-specific модули
│       └── BurningHotCoinsDebugModules.json  ← Game debug модули
│
├── integration/playground/configs/
│   └── burning_hot_coins/
│       └── manifest.json                     ← Game manifest (id, gamePath)
│
└── plugins/
    └── PlaygroundBurningHotCoins.dll         ← Compiled game plugin
```

---

### ЕТАП 1: Стартиране на Launcher

```
┌─────────────────────────────────────────────────────────────────────────┐
│ OS стартира приложението                                                │
│                                                                         │
│ main() → LauncherApp::Init()                                            │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ КОНФИГ: configs/launcher/modules/ModuleManager_Lobby.json           │ │
│ │                                                                     │ │
│ │ Път: GetConfigPath() / "modules" / "ModuleManager_Lobby.json"       │ │
│ │      = "configs/launcher/modules/ModuleManager_Lobby.json"          │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ LauncherApp създава:                                                    │
│   m_moduleManager = make_shared<ModuleManager>()                        │
│   m_moduleManager->LoadConfig("ModuleManager_Lobby.json")               │
│   m_moduleManager->Init()                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ModuleManager_Lobby.json съдържа:                                       │
│                                                                         │
│ {                                                                       │
│   "modules": [                                                          │
│     { "name": "LauncherVideo", ... },                                   │
│     { "name": "LauncherVideoManager", "initAfter": ["LauncherVideo"] }, │
│     { "name": "ResourceManager", "initAfter": ["LauncherVideoManager"] },│
│     { "name": "LauncherLobby", "initAfter": ["ResourceManager"] },      │
│     { "name": "LauncherLobbyHelp", "initAfter": ["LauncherLobby"] }     │
│   ]                                                                     │
│ }                                                                       │
│                                                                         │
│ Къде живеят тези модули?                                                │
│ → В LauncherApp.exe (или в launcher DLL-и)                              │
│ → Регистрирани с EGT_REGISTER_CLASS в launcher кода                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ РЕЗУЛТАТ: Launcher ModuleManager #1                                     │
│                                                                         │
│ m_moduleManager                                                         │
│     ├── LauncherVideo инстанция                                         │
│     ├── LauncherVideoManager инстанция                                  │
│     ├── ResourceManager инстанция                                       │
│     ├── LauncherLobby инстанция        ← показва UI с игри              │
│     └── LauncherLobbyHelp инстанция                                     │
│                                                                         │
│ LauncherLobby сканира: integration/playground/configs/*/manifest.json   │
│ Намира: burning_hot_coins, rise_of_ra, nordic_rush, joker_reels_coins_10│
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 2: User избира Burning Hot Coins

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LauncherLobby::DoLoadGame(gameInfo)                                     │
│                                                                         │
│ gameInfo съдържа:                                                       │
│   - path: "integration/playground/configs/burning_hot_coins"            │
│   - kernelType: KernelType::Playground                                  │
│   - descriptor: manifest.json данни                                     │
│       - id: 2121                                                        │
│       - name: "burning_hot_coins"                                       │
│       - gamePath: "BurningHotCoins"  ← за plugin името                  │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ КОНФИГ: configs/launcher/modules/Module_PlaygroundGameLoader.json   │ │
│ │                                                                     │ │
│ │ Формиране на името:                                                 │ │
│ │   cfgFileName = "Module_" + GetKernelModuleName(Playground) + ".json" │
│ │                = "Module_PlaygroundGameLoader.json"                 │ │
│ │                                                                     │ │
│ │ Път: GetConfigPath() / "modules" / cfgFileName                      │ │
│ │    = "configs/launcher/modules/Module_PlaygroundGameLoader.json"    │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ LauncherLobby зарежда модула динамично:                                 │
│   RuntimeGet<IModuleManager>().LoadModule(runtime, moduleConfig)        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Module_PlaygroundGameLoader.json съдържа:                               │
│                                                                         │
│ {                                                                       │
│   "name": "PlaygroundGameLoader",                                       │
│   "runtimeAccess": { "GameView,GameImport,Integration,Kernel": "rwx" }, │
│   "config": {                                                           │
│     "windows": [{ "w": 1920, "h": 1080, ... }, ...]                     │
│   }                                                                     │
│ }                                                                       │
│                                                                         │
│ Къде живее PlaygroundGameLoader?                                        │
│ → В EgtKernelPlayground библиотека (линкната към Launcher)              │
│ → Регистриран с EGT_REGISTER_CLASS(IModule, PlaygroundGameLoader)       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ РЕЗУЛТАТ: Launcher ModuleManager #1 (обновен)                           │
│                                                                         │
│ m_moduleManager                                                         │
│     ├── LauncherVideo                                                   │
│     ├── LauncherVideoManager                                            │
│     ├── ResourceManager                                                 │
│     ├── LauncherLobby                                                   │
│     ├── LauncherLobbyHelp                                               │
│     └── PlaygroundGameLoader ← НОВО! динамично добавен                  │
│                                                                         │
│ След това: LauncherLobby извиква gameModule->LoadGame(gameInfo)         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 3: PlaygroundGameLoader зарежда Game Plugin

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PlaygroundGameLoader::LoadGame(gameInfo)                                │
│                                                                         │
│ 1. Създава PlaygroundKernelApi                                          │
│    m_kernelApi = make_shared<PlaygroundKernelApi>(*this)                │
│                                                                         │
│ 2. Определя plugin path от manifest:                                    │
│    gameDescriptor->gamePath = "BurningHotCoins"                         │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ PLUGIN: plugins/PlaygroundBurningHotCoins.dll                       │ │
│ │                                                                     │ │
│ │ Формиране на пътя:                                                  │ │
│ │   gamePluginPath = K::PlaygroundPluginsDir /                        │ │
│ │                    (K::PlaygroundPluginPrefix + gamePath)           │ │
│ │                  = "plugins" / ("Playground" + "BurningHotCoins")   │ │
│ │                  = "plugins/PlaygroundBurningHotCoins"              │ │
│ │                                                                     │ │
│ │ PluginLoader добавя разширение: .dll (Windows) / .so (Linux)        │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ 3. Зарежда plugin-а:                                                    │
│    m_gamePlugin = PluginLoader().LoadPlugin(gamePluginPath)             │
│    → LoadLibrary("plugins/PlaygroundBurningHotCoins.dll")               │
│    → При зареждане: EGT_REGISTER_CLASS изпълнява static регистрации     │
│                                                                         │
│ 4. Извиква create_game():                                               │
│    createGame = m_gamePlugin->Resolve("create_game")                    │
│    m_gameApi = createGame(&*m_kernelApi)                                │
│    → Създава PlaygroundGame инстанция                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PlaygroundBurningHotCoins.dll е зареден в паметта                       │
│                                                                         │
│ ObjectFactoryRegistry вече знае за:                                     │
│   - "PlaygroundIntegration" → factory                                   │
│   - "AlphaFamilyGameflow" → factory                                     │
│   - "BurningHotCoinsFsm" → factory                                      │
│   - "BurningHotCoinsMath" → factory                                     │
│   - "BurningHotCoinsView" → factory                                     │
│   - "VideoManager" → factory                                            │
│   - ... още ~25 модула                                                  │
│                                                                         │
│ g_game = PlaygroundGame инстанция (но модулите още НЕ са създадени!)    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ЕТАП 4: PlaygroundGame зарежда модулите

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PlaygroundGameLoader извиква:                                           │
│   m_gameApi->LoadGame(basePath)                                         │
│                                                                         │
│ basePath се формира:                                                    │
│   appDir / "playground" / gameDescriptor->name                          │
│   = "C:/games/playground/burning_hot_coins"                             │
│                                                                         │
│ (ако не съществува, се използва appDir директно)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PlaygroundGame::LoadGame(basePath)                                      │
│                                                                         │
│ 1. Сетва пътищата:                                                      │
│    m_basePath = basePath                                                │
│    m_configPath = basePath  (или специфичен config path)                │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ КОНФИГ: configs/burning_hot_coins/modules/ModuleManager_Playground.json│
│ │                                                                     │ │
│ │ Формиране на пътя:                                                  │ │
│ │   jsonConfigPath = GetConfigPath() / "modules" /                    │ │
│ │                    "ModuleManager_Playground.json"                  │ │
│ │                  = "configs/burning_hot_coins/modules/              │ │
│ │                     ModuleManager_Playground.json"                  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ 2. Създава ModuleManager:                                               │
│    m_moduleManager = make_shared<ModuleManager>()                       │
│    m_moduleManager->LoadConfig(jsonConfigPath)                          │
│    m_moduleManager->Init()                                              │
│    m_moduleManager->PostInit()                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ModuleManager_Playground.json съдържа:                                  │
│                                                                         │
│ {                                                                       │
│   "include": [                                                          │
│     "../../alpha_family/modules/AlphaPlaygroundModules.json",           │
│     "../../alpha_family/modules/AlphaDebugModules.json",                │
│     "BurningHotCoinsModules.json",                                      │
│     "BurningHotCoinsDebugModules.json"                                  │
│   ],                                                                    │
│   "modules": [                                                          │
│     { "override": true, "name": "VideoManager", "config": {...} },      │
│     { "name": "MessageBoardView", ... }                                 │
│   ]                                                                     │
│ }                                                                       │
│                                                                         │
│ Include файловете се резолват ОТНОСИТЕЛНО към текущия конфиг:           │
│   "../../alpha_family/modules/AlphaPlaygroundModules.json"              │
│   = "configs/alpha_family/modules/AlphaPlaygroundModules.json"          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ЙЕРАРХИЯ НА INCLUDE ФАЙЛОВЕТЕ:                                          │
│                                                                         │
│ ModuleManager_Playground.json                                           │
│ │                                                                       │
│ ├─► AlphaPlaygroundModules.json                                         │
│ │   │                                                                   │
│ │   ├─► AlphaGameModules.json                                           │
│ │   │   ├── VideoManager                                                │
│ │   │   ├── AudioManager                                                │
│ │   │   ├── ResourceManager                                             │
│ │   │   └── LoadingScreenView                                           │
│ │   │                                                                   │
│ │   ├── PlaygroundVideo                                                 │
│ │   ├── PlaygroundIntegration      ← bridge към kernel                  │
│ │   ├── AlphaFamilyGameflow        ← gameflow логика                    │
│ │   ├── AlphaFamilyBridge                                               │
│ │   ├── RecoveryManager                                                 │
│ │   ├── ResponsibleGamingManager                                        │
│ │   ├── LocalizationManager                                             │
│ │   └── MessageBoardManager                                             │
│ │                                                                       │
│ ├─► AlphaDebugModules.json                                              │
│ │   ├── LogViewer                                                       │
│ │   ├── GameFsmViewer                                                   │
│ │   ├── RngPresetManager                                                │
│ │   ├── GraphicsInspector                                               │
│ │   └── ScreenshotsManager                                              │
│ │                                                                       │
│ ├─► BurningHotCoinsModules.json                                         │
│ │   ├── BurningHotCoinsFsm         ← game state machine                 │
│ │   ├── BurningHotCoinsMath        ← math/RNG logic                     │
│ │   ├── BurningHotCoinsView        ← main game view                     │
│ │   └── BurningHotCoinsInfoView    ← info/help view                     │
│ │                                                                       │
│ └─► BurningHotCoinsDebugModules.json                                    │
│     └── AlphaFamilyMathRngPreset                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ РЕЗУЛТАТ: Game ModuleManager #2                                         │
│                                                                         │
│ PlaygroundGame                                                          │
│     │                                                                   │
│     └── m_moduleManager                                                 │
│             │                                                           │
│             ├── PlaygroundVideo инстанция                               │
│             ├── PlaygroundIntegration инстанция                         │
│             ├── AlphaFamilyGameflow инстанция                           │
│             ├── VideoManager инстанция                                  │
│             ├── AudioManager инстанция                                  │
│             ├── ResourceManager инстанция                               │
│             ├── BurningHotCoinsFsm инстанция                            │
│             ├── BurningHotCoinsMath инстанция                           │
│             ├── BurningHotCoinsView инстанция                           │
│             ├── BurningHotCoinsInfoView инстанция                       │
│             ├── LogViewer инстанция                                     │
│             └── ... (~25 модула общо)                                   │
│                                                                         │
│ Къде живеят тези модули?                                                │
│ → Кодът им е в PlaygroundBurningHotCoins.dll (static linked)            │
│ → Инстанциите се създават от ModuleManager чрез ObjectFactoryRegistry   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### ОБОБЩЕНИЕ: Двата ModuleManager-а

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              СИСТЕМА                                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ ModuleManager #1 (Launcher)                                       │  │
│  │ Конфиг: configs/launcher/modules/ModuleManager_Lobby.json         │  │
│  │ Собственик: LauncherApp                                           │  │
│  │                                                                   │  │
│  │ Модули:                                                           │  │
│  │   LauncherVideo, LauncherVideoManager, ResourceManager,           │  │
│  │   LauncherLobby, LauncherLobbyHelp,                               │  │
│  │   PlaygroundGameLoader (динамично добавен)                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                              │                                          │
│                              │ PlaygroundGameLoader зарежда DLL         │
│                              │ и създава PlaygroundGame                 │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ ModuleManager #2 (Game)                                           │  │
│  │ Конфиг: configs/burning_hot_coins/modules/ModuleManager_Playground│  │
│  │ Собственик: PlaygroundGame                                        │  │
│  │                                                                   │  │
│  │ Модули (от DLL-а):                                                │  │
│  │   PlaygroundIntegration, AlphaFamilyGameflow,                     │  │
│  │   BurningHotCoinsFsm, BurningHotCoinsMath, BurningHotCoinsView,   │  │
│  │   VideoManager, AudioManager, ResourceManager, LogViewer, ...     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Runtime (споделен)                                                │  │
│  │                                                                   │  │
│  │ Всички модули регистрират услуги тук:                             │  │
│  │   IGameModule* → PlaygroundGameLoader                             │  │
│  │   IKernelIntegration* → PlaygroundIntegration                     │  │
│  │   IGameFsm* → BurningHotCoinsFsm                                  │  │
│  │   IGameMath* → BurningHotCoinsMath                                │  │
│  │   ...                                                             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Таблица: Конфигурационни файлове

| Етап | Конфиг файл | Път | Какво зарежда |
|------|-------------|-----|---------------|
| **1. Launcher start** | `ModuleManager_Lobby.json` | `configs/launcher/modules/` | LauncherVideo, LauncherLobby, etc. |
| **2. Избор на kernel** | `Module_PlaygroundGameLoader.json` | `configs/launcher/modules/` | PlaygroundGameLoader модул |
| **3. Намиране на игра** | `manifest.json` | `integration/playground/configs/burning_hot_coins/` | Game metadata (id, gamePath) |
| **4. Game modules** | `ModuleManager_Playground.json` | `configs/burning_hot_coins/modules/` | Всички game модули |

### Таблица: Къде живеят модулите

| Модул | Executable/DLL | Регистрация |
|-------|----------------|-------------|
| LauncherLobby | `LauncherApp.exe` | В launcher кода |
| PlaygroundGameLoader | `EgtKernelPlayground.lib` (линкнат към Launcher) | В kernel кода |
| BurningHotCoinsFsm | `PlaygroundBurningHotCoins.dll` | `EGT_REGISTER_CLASS` в DLL |
| PlaygroundIntegration | `PlaygroundBurningHotCoins.dll` | `EGT_REGISTER_CLASS` в DLL |
| VideoManager | `PlaygroundBurningHotCoins.dll` | `EGT_REGISTER_CLASS` в DLL |
