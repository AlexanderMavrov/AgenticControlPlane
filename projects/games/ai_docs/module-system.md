# Module System Architecture

## Съдържание
1. [Две ключови системи](#две-ключови-системи)
2. [ObjectFactoryRegistry](#objectfactoryregistry)
3. [Runtime](#runtime)
4. [Как работят заедно](#как-работят-заедно)
5. [ModuleManager](#modulemanager)
6. [RuntimeAccess и permissions](#runtimeaccess-и-permissions)
7. [Ownership и lifecycle](#ownership-и-lifecycle)

---

## Две ключови системи

Системата използва два отделни registry-та с различни цели:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ObjectFactoryRegistry (глобален)                     │
│                                                                         │
│   Цел: "Знам КАК да създам обект по име (string)"                       │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────┐          │
│   │  "BurningHotCoinsFsm" → factory → new BurningHotCoinsFsm │          │
│   │  "PlaygroundIntegration" → factory → new Playground...   │          │
│   │  "VideoManager" → factory → new VideoManager             │          │
│   └──────────────────────────────────────────────────────────┘          │
│                                                                         │
│   Регистрация: EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm)          │
│   Използване: CreateObjectByKey<IModule>("BurningHotCoinsFsm")          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         Runtime (per-game instance)                     │
│                                                                         │
│   Цел: "Държа ИНСТАНЦИИ на услуги за достъп от модули"                  │
│                                                                         │
│   ┌──────────────────────────────────────────────────────────┐          │
│   │  IGameFsm* → &burningHotCoinsFsmInstance                 │          │
│   │  IKernelIntegration* → &playgroundIntegrationInstance    │          │
│   │  IVideoManager* → &videoManagerInstance                  │          │
│   └──────────────────────────────────────────────────────────┘          │
│                                                                         │
│   Регистрация: RuntimeAdd<IGameFsm>(this)  // в Init() на модула        │
│   Използване: RuntimeGet<IGameFsm>()                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### Сравнение

| | ObjectFactoryRegistry | Runtime |
|---|---|---|
| **Какво държи** | Factory функции (как да създадем) | Инстанции (живи обекти) |
| **Ключ** | String (`"BurningHotCoinsFsm"`) | Type (`IGameFsm*`) |
| **Scope** | Глобален (singleton) | Per-game (може много) |
| **Регистрация** | `EGT_REGISTER_CLASS` (static) | `RuntimeAdd<T>()` (в Init) |
| **Достъп** | `CreateObjectByKey<T>()` | `RuntimeGet<T>()` |

---

## ObjectFactoryRegistry

### Какво е?

Глобален singleton, който map-ва string имена към factory функции. Позволява създаване на обекти по име, без да знаем конкретния тип compile-time.

### Регистрация

```cpp
// PlaygroundBurningHotCoins.cpp - при зареждане на DLL
EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm)
EGT_REGISTER_CLASS(IModule, BurningHotCoinsView)
EGT_REGISTER_CLASS(IModule, PlaygroundIntegration)
```

Макросът `EGT_REGISTER_CLASS` се разгръща до:

```cpp
// Създава static обект, който се инициализира при зареждане на DLL
static const ObjectFactoryRegistrator<BurningHotCoinsFsm, IModule>
    s_BurningHotCoinsFsm_objectFactoryRegistrator("BurningHotCoinsFsm");

// Конструкторът регистрира factory-то
ObjectFactoryRegistrator::ObjectFactoryRegistrator(const std::string& key)
{
    auto& registry = ObjectFactoryRegistry::GetInstance();
    registry.RegisterFactory<T, BaseT>(m_key);  // "BurningHotCoinsFsm" → factory
}
```

### Използване

```cpp
// ModuleManager създава модул по име от JSON конфиг
auto iModule = CreateFirstObjectByKey<IModule>("BurningHotCoinsFsm");
// → Връща нова инстанция на BurningHotCoinsFsm
```

### Защо е нужен?

- JSON конфигурацията съдържа само string имена на модули
- Позволява dynamic loading на модули без compile-time зависимости
- Plugin архитектура - DLL регистрира класовете си при зареждане

---

## Runtime

### Какво е?

Service locator pattern - централно място където модулите регистрират своите инстанции като услуги. Други модули могат да ги достъпят по интерфейс тип.

### Регистрация

```cpp
// В Init() метода на модула
bool BurningHotCoinsFsm::Init(RuntimeAccess runtime, const Json& config)
{
    // Регистрира this като имплементация на IGameFsm
    RuntimeAdd<IGameFsm>(this);
    RuntimeAdd<IGameFsm::Events>(this);
    return true;
}

// В Deinit() - премахва регистрацията
void BurningHotCoinsFsm::Deinit()
{
    RuntimeRemove<IGameFsm>();
    RuntimeRemove<IGameFsm::Events>();
}
```

### Използване

```cpp
// Друг модул достъпва FSM-а
void AlphaFamilyGameflow::SomeMethod()
{
    auto& fsm = RuntimeGet<IGameFsm>();
    fsm.DoSomething();
}
```

### Защо е нужен?

- Decoupling - модулите не знаят конкретни типове, работят с интерфейси
- Testability - може да се inject-нат mock имплементации
- Lifecycle management - регистрация/дерегистрация при Init/Deinit

---

## Как работят заедно

Пълният flow при зареждане на модул:

```
1. DLL се зарежда
   │
   ▼
2. Static инициализация - EGT_REGISTER_CLASS
   │  ObjectFactoryRegistry: "BurningHotCoinsFsm" → factory
   ▼
3. ModuleManager чете JSON конфиг
   │  { "name": "BurningHotCoinsFsm", ... }
   ▼
4. ModuleManager създава модул по име
   │  auto module = CreateObjectByKey<IModule>("BurningHotCoinsFsm");
   ▼
5. ModuleManager извиква Init()
   │  module->Init(runtimeAccess, config);
   ▼
6. Модулът се регистрира в Runtime
   │  RuntimeAdd<IGameFsm>(this);
   ▼
7. Други модули могат да го използват
      RuntimeGet<IGameFsm>().DoSomething();
```

### Пример с код

```cpp
// ========== СТЪПКА 1-2: При зареждане на DLL ==========
// PlaygroundBurningHotCoins.cpp

// Static регистрация - изпълнява се при LoadLibrary()
EGT_REGISTER_CLASS(IModule, BurningHotCoinsFsm)
// Сега ObjectFactoryRegistry знае: "BurningHotCoinsFsm" → може да се създаде


// ========== СТЪПКА 3-5: ModuleManager зарежда модули ==========
// ModuleManager.cpp

bool ModuleManager::LoadModule(RuntimeAccess runtime, ModuleConfig cfg)
{
    // Стъпка 4: Създава модул по име
    auto iModule = CreateFirstObjectByKey<IModule>(cfg.name);

    // Стъпка 5: Инициализира го
    iModule->Init(runtime, cfg.config);

    m_modules.push_back({cfg, runtime, iModule});
}


// ========== СТЪПКА 6: Модулът се регистрира в Runtime ==========
// BurningHotCoinsFsm.cpp

bool BurningHotCoinsFsm::Init(RuntimeAccess runtime, const Json& config)
{
    // Запазва runtime за по-късно
    SetRuntime(runtime);

    // Регистрира се като IGameFsm
    RuntimeAdd<IGameFsm>(this);

    return true;
}


// ========== СТЪПКА 7: Друг модул го използва ==========
// AlphaFamilyGameflow.cpp

void AlphaFamilyGameflow::OnSpinPressed()
{
    // Достъпва FSM-а през Runtime
    auto& fsm = RuntimeGet<IGameFsm>();
    fsm.StartSpin();
}
```

---

## ModuleManager

### Множество инстанции

Системата има **няколко ModuleManager-а** с различни отговорности:

```
LauncherApp
    │
    └── m_moduleManager ─────► ModuleManager #1
                                 │
                                 ├── LauncherLobby
                                 ├── LauncherVideo
                                 └── PlaygroundGameLoader
                                         │
                                         │ creates
                                         ▼
                                   PlaygroundGame
                                         │
                                         └── m_moduleManager ─────► ModuleManager #2
                                                                      │
                                                                      ├── PlaygroundIntegration
                                                                      ├── AlphaFamilyGameflow
                                                                      ├── BurningHotCoinsFsm
                                                                      └── VideoManager
```

### Споделен Runtime

Въпреки отделните ModuleManager-и, всички модули споделят **един Runtime**:

```cpp
// Launcher модул
RuntimeAdd<IGameModule>(this);

// Game модул може да го достъпи
auto& gameModule = RuntimeGet<IGameModule>();
```

---

## RuntimeAccess и permissions

### Ограничен достъп

Всеки модул получава `RuntimeAccess` - wrapper с permission маски:

```cpp
// ModuleManager.cpp
auto access = ResolveRuntimeAccessMasks(cfg);
runtime = RuntimeAccess(runtime, access.addRemove, access.readWrite, access.readOnly, cfg.name);
```

### JSON конфигурация

```json
{
  "name": "BurningHotCoinsFsm",
  "runtimeAccess": {
    "GameFsm": "rwx",
    "GameMath,GameView,GameImport,GameDebug": "rw"
  }
}
```

### Permissions

| Permission | Описание | Методи |
|------------|----------|--------|
| `r` | Read only | `RuntimeGetConst()`, `RuntimeTryGetConst()` |
| `w` | Read-write | `RuntimeGet()`, `RuntimeTryGet()` |
| `x` | Add/remove | `RuntimeAdd()`, `RuntimeRemove()` |

### Категории

Всеки интерфейс принадлежи към категория:

```cpp
// IGameFsm.h
class IGameFsm
{
public:
    static constexpr RuntimeCategoryMask RuntimeCategory = RuntimeCategories::GameFsm;
    // ...
};
```

| Категория | Примерни интерфейси |
|-----------|---------------------|
| `GameFsm` | `IGameFsm`, `IGameState` |
| `GameMath` | `IGameMath`, `IRngPreset` |
| `GameView` | `IGameView`, `IVideoManager` |
| `Integration` | `IKernelIntegration`, `IKernelApi` |

### Защо?

```json
// FSM няма достъп до Integration
"BurningHotCoinsFsm": { "runtimeAccess": { "GameFsm": "rwx", "GameMath": "rw" } }

// Gameflow има достъп до Integration
"AlphaFamilyGameflow": { "runtimeAccess": { "Integration": "rwx" } }
```

Ако FSM се опита да достъпи kernel директно:

```cpp
// BurningHotCoinsFsm.cpp
RuntimeGet<IKernelIntegration>()  // RuntimeAccessViolation!
```

Това **принуждава** правилната архитектура: FSM → Gameflow → Integration → Kernel

---

## Ownership и lifecycle

### Къде се съхраняват модулите?

Модулите се държат на **две места**, но с различни типове pointer-и:

| Място | Тип | Ownership |
|-------|-----|-----------|
| **ModuleManager** | `shared_ptr<IModule>` | ✅ Притежава модула |
| **Runtime** | `T*` (raw pointer) | ❌ Само референция |

### ModuleManager - държи `shared_ptr`

```cpp
// ModuleManager.h
struct Module
{
    ModuleConfig cfg;
    GameCore::RuntimeAccess runtime;
    Ptr<IModule> iModule;  // ← shared_ptr<IModule> - OWNERSHIP тук!
};

Modules m_modules;  // vector<Module>
```

### Runtime - държи raw pointer

Когато модул извика `RuntimeAdd<T>(this)`:

```cpp
// RuntimeAccess.h
template <runtime_interface T>
void RuntimeAccess::Add(T* impl, Src src)
{
    // ... permission check ...
    m_runtime->Add<T*>(impl);  // ← Добавя T* (raw pointer)
}
```

Runtime е просто lookup таблица:

```cpp
// Runtime.h
std::unordered_map<std::type_index, Any> m_objects;
// typeid(IWallet*) → Any { IWallet* }  ← raw pointer
// typeid(ILimits*) → Any { ILimits* }  ← raw pointer
```

### Визуализация

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ModuleManager                                                               │
│                                                                             │
│  m_modules: vector<Module>                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Module {                                                             │   │
│  │   cfg: ModuleConfig                                                  │   │
│  │   runtime: RuntimeAccess                                             │   │
│  │   iModule: shared_ptr<IModule> ─────────────────┐                   │   │
│  │ }                                                │                   │   │
│  └──────────────────────────────────────────────────┼───────────────────┘   │
└─────────────────────────────────────────────────────┼───────────────────────┘
                                                      │
                                                      │ shared_ptr (ownership)
                                                      ▼
                                    ┌─────────────────────────────────────────┐
                                    │ PlaygroundIntegration                   │
                                    │   └─► PlaygroundWallet (компонент)      │
                                    │         │                               │
                                    │         │ RuntimeAdd<IWallet>(this)     │
                                    │         │                               │
                                    └─────────┼───────────────────────────────┘
                                              │
                                              │ raw pointer (IWallet*)
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Runtime                                                                     │
│                                                                             │
│  m_objects: unordered_map<type_index, Any>                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ typeid(IWallet*) → Any { IWallet* }  ← raw pointer                  │   │
│  │ typeid(ILimits*) → Any { ILimits* }  ← raw pointer                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Защо raw pointer в Runtime?

1. **Performance** - няма overhead от reference counting при достъп
2. **Простота** - Runtime е само lookup, не управлява lifetime
3. **Единствен owner** - ModuleManager контролира кога модулът се унищожава

### Важно: Cleanup при Deinit

Тъй като Runtime държи raw pointer-и, модулът **трябва** да извика `RuntimeRemove<>()` преди да бъде унищожен:

```cpp
void PlaygroundWallet::Deinit()
{
    // 1. Премахва raw pointer-а от Runtime
    RuntimeRemove<IWallet>();
    RuntimeRemove<IWallet::Events>();

    // 2. Base class cleanup
    PlaygroundComponent::Deinit();
}

// 3. След това ModuleManager унищожава shared_ptr-а
//    → деструкторът на PlaygroundWallet се извиква
```

**Ако не извикаш `RuntimeRemove<>()`**, в Runtime остава **dangling pointer** - pointer към вече освободена памет!

### Lifecycle диаграма

```
                  ModuleManager                          Runtime
                       │                                    │
    LoadModule()       │                                    │
         │             │                                    │
         ▼             │                                    │
    ┌─────────┐        │                                    │
    │ new     │        │                                    │
    │ Module  │────────┼──► shared_ptr<IModule>             │
    └─────────┘        │        │                           │
                       │        │                           │
    Init()             │        ▼                           │
         │             │   ┌─────────┐                      │
         └─────────────┼───┤ module  │                      │
                       │   │ .Init() │                      │
                       │   └────┬────┘                      │
                       │        │                           │
                       │        │ RuntimeAdd<T>(this)       │
                       │        └───────────────────────────┼──► T* stored
                       │                                    │
         ...           │        ...                         │
                       │                                    │
    Deinit()           │   ┌─────────┐                      │
         │             │   │ module  │                      │
         └─────────────┼───┤.Deinit()│                      │
                       │   └────┬────┘                      │
                       │        │                           │
                       │        │ RuntimeRemove<T>()        │
                       │        └───────────────────────────┼──► T* removed
                       │                                    │
    UnloadModule()     │        │                           │
         │             │        ▼                           │
         └─────────────┼──► shared_ptr.reset()              │
                       │        │                           │
                       │        ▼                           │
                       │   ~Module() called                 │
                       │                                    │
```
