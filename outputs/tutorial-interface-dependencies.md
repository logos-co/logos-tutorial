# Tutorial: Dependency Interfaces — Bind a Module by Contract

This tutorial builds `calc_via_interface`, a **core module that depends on an *interface*, not a concrete module**. Instead of naming `calc_module` (from [Part 1](tutorial-wrapping-c-library.md)) as a dependency and getting a fixed `modules().calc_module` wrapper, it declares a small **`calculator` interface** — a list of methods and one event — and **binds that interface to a module name chosen at runtime**. Any module whose API is a *superset* of the interface can satisfy it; `calc_module` is one such provider. You drive the whole thing from `logoscore` on the command line.

**What you'll build:** A `calc_via_interface` core module that:

- declares a **`calculator` interface** in its own language (a pure-C++ header with a `logos_events:` block) — `interfaces/calculator.h`
- lists it under `metadata.json`'s `interface_dependencies` — and names **no concrete module** in `dependencies`
- **binds** the interface to a runtime-chosen module with `modules().bind_calculator("calc_module")`, then calls it through the usual type-safe wrappers — **synchronously** (`add`, `multiply`, `libVersion`), **asynchronously** (`fibonacciAsync` + callback), and via a typed **event** subscription (`onVersionReady`)
- proves the **no-validation** contract: binding to a module that does not satisfy the interface fails as an ordinary remote-call error — no crash

No Qt, no `LogosAPI`, no plugin boilerplate — one plain C++ class, plus a one-file interface contract.

**What you'll learn:**

- The difference between a concrete dependency (`dependencies`) and a dependency interface (`interface_dependencies`)
- How to declare an interface in pure C++ (methods + a `logos_events:` block) — or equivalently in `.lidl`
- How the generator turns an interface into a **bound** wrapper whose target module is a constructor argument, exposed as `modules().bind_<interface>(moduleName)`
- How to call a bound interface **synchronously** and **asynchronously**, and how to subscribe to its events — all type-safely
- Why binding is decoupled from loading, and what the "superset" / no-validation rule means in practice
- How to share one interface across repos via a flake input (the same wiring `dependencies` use)

## Prerequisites

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` whose shared library is built (`libcalc.so`/`.dylib` in `logos-calc-module/lib/`). This tutorial only needs `calc_module` as a *runtime* provider; it is never named at build time.
- Nix with flakes enabled
- Basic familiarity with C++

---

## Step 1: Scaffold the Module Project

Create a new directory and initialise it from the minimal module template:

`mkdir logos-calc-via-interface-module && cd logos-calc-via-interface-module`

### 1.1 Create the project from the template

```bash
nix flake init -t github:logos-co/logos-module-builder/0.2.0
```

This scaffolds a `flake.nix`, `metadata.json`, `CMakeLists.txt`, and a `src/` directory pre-wired for `logos-module-builder`. As in Part 1 we use the **pure-C++ (`interface: universal`) pattern**, so we replace the template's example `src/` files with our own plain `*_impl.h` / `*_impl.cpp`.

### 1.2 Remove the template's example sources

Delete the example Qt plugin the template ships — this tutorial supplies its own pure-C++ `src/` files:

```bash
rm -f src/minimal_interface.h src/minimal_plugin.h src/minimal_plugin.cpp
```

---

## Step 2: Declare the Interface

An **interface** is a method/event contract decoupled from any concrete module. You write it in the *same language as your module* — for a universal module that's a plain C++ header. It looks like an impl class, but you only declare signatures: the generator reads them to build a typed client.

Put it in an `interfaces/` directory:

### 2.1 `interfaces/calculator.h` — the contract

The `calculator` interface names four methods and one event. It is deliberately a **subset** of what `calc_module` exposes (which also has `factorial`, `libVersionNotify`, …) — that is the *superset rule*: a provider may expose more than the interface requires.

```cpp
#pragma once

// A DEPENDENCY INTERFACE: a method/event contract that names no
// module. Any module whose API is a superset of this can satisfy
// it; the consumer binds it to a concrete module name at runtime.
//
// Written in the module's own language (pure C++). The generator
// reads the public methods + the `logos_events:` block and emits a
// BOUND wrapper class `Calculator` whose target module name is a
// runtime constructor argument — not baked in.
//
// Types are std (int64_t / std::string) because the consuming
// module is `interface: "universal"`; the bound wrapper inherits
// that api-style.

#include <cstdint>
#include <string>

// Defines the `logos_events` token (expands to `public`) so this
// header is valid C++ on its own, not only as generator input.
#include <logos_module_context.h>

class ICalculator {
public:
    int64_t add(int64_t a, int64_t b);
    int64_t multiply(int64_t a, int64_t b);
    int64_t fibonacci(int64_t n);
    std::string libVersion();

logos_events:
    // Emitted by the provider; the consumer subscribes through the
    // bound wrapper's generated onVersionReady(...) accessor.
    void versionReady(const std::string& version);
};
```

A few things to notice:

- The class name (`ICalculator`) and method signatures are all the generator needs — no `LogosAPI`, no Qt, no reference to any concrete module. The one include (`logos_module_context.h`) just defines the `logos_events` token so the header is valid C++ on its own.
- `logos_events:` (like Qt's `signals:`) marks event declarations. The generator turns each into a typed `on<Event>(callback)` subscriber on the bound wrapper.
- You could write the exact same contract as a `.lidl` file instead — `interfaces/calculator.lidl` with `method add(a: int, b: int) -> int` … `event versionReady(version: tstr)`. The `.h` form is shown here because it matches a universal module's own language.

---

## Step 3: Configure the Module

Three config files declare the module, point it at the interface, and tell CMake how to build it. The key contrast with [Composing Modules](tutorial-composing-modules.md): there is **no concrete module** in `dependencies`.

### 3.1 `metadata.json` — declare the interface dependency

`interface_dependencies` lists the contracts this module binds at runtime. Each entry gives the interface `name` and the `file` that defines it (and, for a `.h` file, the `impl_class` whose signatures define the contract). `dependencies` stays **empty** — we never name `calc_module` at build time.

```json
{
  "name": "calc_via_interface",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Binds a calculator interface to a module chosen at runtime",
  "main": "calc_via_interface_plugin",
  "interface": "universal",
  "dependencies": [],
  "interface_dependencies": [
    { "name": "calculator", "file": "interfaces/calculator.h", "impl_class": "ICalculator" }
  ],

  "nix": {
    "packages": {
      "build": [],
      "runtime": []
    },
    "external_libraries": [],
    "cmake": {
      "find_packages": [],
      "extra_sources": [],
      "extra_include_dirs": [],
      "extra_link_libraries": []
    }
  }
}
```

| Field                    | What it does                                                                                                                  |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `interface`              | `"universal"` — pure C++ impl, the builder generates the Qt plugin glue                                                        |
| `dependencies`           | `[]` — **no concrete module** is named at build time                                                                          |
| `interface_dependencies` | `[{ name, file, impl_class }]` — the builder generates the bound wrapper `Calculator` + the `modules().bind_calculator(...)` factory |

For a `.h` interface the `impl_class` field is required (the class whose signatures define the contract). For a `.lidl` interface, omit it. To pull an interface from **another repo**, add an `"input"` field naming a flake input — covered in the final step.

### 3.2 `CMakeLists.txt` — list your sources

You list only your plain C++ files. The generated interface wrapper and plugin glue are compiled automatically.

```cmake
cmake_minimum_required(VERSION 3.14)
project(CalcViaInterfacePlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_via_interface
    SOURCES
        src/calc_via_interface_impl.h
        src/calc_via_interface_impl.cpp
)
```

`NAME` must match `name` in `metadata.json` (`calc_via_interface`). No module dependency to wire here — the interface file is local to this repo.

### 3.3 `flake.nix` — no module inputs needed

Because there is no concrete dependency, the only input is the builder itself. (Contrast with Composing Modules, which had to add a `calc_module.url` input.)

```nix
{
  description = "Core module that binds a calculator interface at runtime";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/0.2.0";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

`flakeInputs = inputs` hands the builder everything it needs. It reads `interface_dependencies` from `metadata.json`, resolves the local `interfaces/calculator.h`, and runs `logos-cpp-generator` to emit the bound `Calculator` wrapper into `generated_code/`.

---

## Step 4: Write the Module Class

The module is one plain C++ class inheriting `LogosModuleContext` — that base gives it `modules()`, through which the generated `bind_calculator(name)` factory is reachable. Each method takes the **provider module name** as its first argument, so we can bind to different modules at runtime from `logoscore`.

### 4.1 `src/calc_via_interface_impl.h` — the class

Every `public` method becomes callable over IPC. They fall into three groups: synchronous binds, an asynchronous bind, and an event subscription.

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>  // LogosModuleContext base → modules()

// Binds the `calculator` interface (interfaces/calculator.h) to a
// module name chosen at runtime and calls it through the generated,
// type-safe bound wrapper. It names no concrete module of its own —
// the provider is whatever string you pass in.
class CalcViaInterfaceImpl : public LogosModuleContext {
public:
    CalcViaInterfaceImpl() = default;
    ~CalcViaInterfaceImpl() = default;

    // ── Synchronous binds ──────────────────────────────────────
    // Bind `calculator` to `provider`, then call it. The module
    // name appears only at bind time, never on the call.
    int64_t     sumVia(const std::string& provider, int64_t a, int64_t b);
    int64_t     productVia(const std::string& provider, int64_t a, int64_t b);
    std::string versionVia(const std::string& provider);

    // ── Asynchronous bind ──────────────────────────────────────
    // Fire calculator.fibonacci(n) asynchronously against `provider`
    // and return immediately ("queued"). Read the reply later with
    // lastFib().
    std::string startFibVia(const std::string& provider, int64_t n);
    int64_t     lastFib() const;

    // ── Event subscription ─────────────────────────────────────
    // Subscribe to the interface's `versionReady` event on
    // `provider` via the generated onVersionReady(...) accessor.
    std::string watchVersion(const std::string& provider);
    std::string lastVersion() const;

private:
    int64_t     m_lastFib = -1;
    std::string m_lastVersion;
};
```

The provider name is a plain `std::string` parameter — that is the whole "bind at runtime" idea. The same handle code works for any module that satisfies `calculator`.

### 4.2 `src/calc_via_interface_impl.cpp` — the implementation

The `.cpp` includes the generated `logos_sdk.h` (which defines `LogosModules` and the `bind_calculator` factory), so the bind/call sites live here rather than in the header the generator parses.

```cpp
#include "calc_via_interface_impl.h"

// Generated at build time by logos-cpp-generator. Because
// metadata.json lists `interface_dependencies`, LogosModules gains a
// `bind_calculator(moduleName)` factory returning the bound
// `Calculator` wrapper. Included only in the .cpp so the impl header
// the generator parses stays free of generated types.
#include "logos_sdk.h"

// ── Synchronous binds ───────────────────────────────────────────────

int64_t CalcViaInterfaceImpl::sumVia(const std::string& provider,
                                     int64_t a, int64_t b) {
    // Bind once, then call normally — no module name on the call.
    // Every generated method also takes an optional trailing
    // logos::CallError* — the explicit way to tell a failed remote
    // call apart from a legitimate result (without it, a failed
    // call returns the type's default and only logs a warning).
    auto calc = modules().bind_calculator(provider);
    logos::CallError err;
    const int64_t sum = calc.add(a, b, &err);
    if (!err.ok()) return -1;  // e.g. the bound module isn't loaded
    return sum;
}

int64_t CalcViaInterfaceImpl::productVia(const std::string& provider,
                                         int64_t a, int64_t b) {
    return modules().bind_calculator(provider).multiply(a, b);
}

std::string CalcViaInterfaceImpl::versionVia(const std::string& provider) {
    return modules().bind_calculator(provider).libVersion();
}

// ── Asynchronous bind ────────────────────────────────────────────────

std::string CalcViaInterfaceImpl::startFibVia(const std::string& provider,
                                              int64_t n) {
    // The generated async overload is `<method>Async(args...,
    // callback, timeout)`. It returns immediately; the reply lands in
    // the callback on this module's event loop. The bound handle is a
    // temporary, but the call is registered on the LogosAPI-owned
    // client and the callback captures `this`, so it outlives it.
    modules().bind_calculator(provider).fibonacciAsync(n,
        [this](int64_t value) { m_lastFib = value; });
    return "queued";
}

int64_t CalcViaInterfaceImpl::lastFib() const {
    return m_lastFib;
}

// ── Event subscription ───────────────────────────────────────────────

std::string CalcViaInterfaceImpl::watchVersion(const std::string& provider) {
    // onVersionReady(...) is generated from the interface's
    // `logos_events:` block; the callback's arg type matches the event.
    bool ok = modules().bind_calculator(provider).onVersionReady(
        [this](const std::string& version) { m_lastVersion = version; });
    return ok ? "ok" : "failed";
}

std::string CalcViaInterfaceImpl::lastVersion() const {
    return m_lastVersion;
}
```

Everything flows through `modules().bind_calculator(provider)` — the factory the builder generated from `interface_dependencies`. There is no `modules().calc_module`, because `calc_module` is never a build-time dependency. The bound `Calculator` exposes the same typed sync/async/event API the name-baked wrappers do; the only difference is the target module is chosen when you bind.

---

## Step 5: Build the Module

### 5.1 Add a `.gitignore` and init the repo

Nix flakes require a git repository, and only tracked files are visible — so `interfaces/calculator.h` must be committed for the generator to find it. Exclude build artifacts first:

```text
# Nix build output
result
result-*

# CMake build directory
build/
```

Initialise the repo and stage the files (including `interfaces/`):

```bash
git init && git add -A
```

### 5.2 Build

For a universal module with an interface dependency, this is where `logos-cpp-generator` runs over both `src/calc_via_interface_impl.h` (plugin glue) and `interfaces/calculator.h` (the bound `Calculator` wrapper + `bind_calculator` factory), emitting everything under `generated_code/`:

```bash
nix build
```

### 5.3 Check the output

```bash
ls -la result/lib/
```

You should see your plugin (extension depends on platform):

```
calc_via_interface_plugin.so     # Linux
calc_via_interface_plugin.dylib  # macOS
```

---

## Step 6: Inspect the Module

Use `lm` to confirm the public API made it into the binary — and, tellingly, that there is **no module dependency**.

### 6.1 Build `lm`

```bash
nix build 'github:logos-co/logos-module/0.2.0#lm' --out-link ./lm
```

### 6.2 View metadata — note the empty dependency list

```bash
./lm/bin/lm metadata result/lib/calc_via_interface_plugin.so    # Linux
./lm/bin/lm metadata result/lib/calc_via_interface_plugin.dylib  # macOS
```

```
Plugin Metadata:
================
Name:         calc_via_interface
Version:      1.0.0
Description:  Binds a calculator interface to a module chosen at runtime
Type:         core
Dependencies:
```

`Dependencies:` is empty — the module is coupled to the `calculator` *contract*, not to any module.

### 6.3 List methods

```bash
./lm/bin/lm methods result/lib/calc_via_interface_plugin.so    # Linux
./lm/bin/lm methods result/lib/calc_via_interface_plugin.dylib  # macOS
```

Every `public` method is here. `int64_t` shows up as `int` and `std::string` as `QString` — the wire types the generated glue exposes.

---

## Step 7: Run it with `logoscore`

Now the payoff: run `calc_via_interface` and bind its `calculator` interface to the real `calc_module` from Part 1. We use the `logoscore` **daemon** (`-D`) so module processes stay alive between `call` commands — needed for the async reply and the event subscription to survive from one call to the next. (Same daemon flow as [Part 1](tutorial-wrapping-c-library.md#step-6-test-with-logoscore) and [Composing Modules](tutorial-composing-modules.md#run-it-with-logoscore).)

### 7.1 Build the runtime and package both modules

Build `logoscore` and the package manager, then install **both** modules into a `modules/` directory. `calc_via_interface` comes from this project; `calc_module` from your Part 1 checkout — it is the *provider* we bind to, even though this module never declared it:

```bash
nix build 'github:logos-co/logos-logoscore-cli/0.2.0' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager/0.2.0#cli' --out-link ./pm
```

```bash
mkdir -p modules
```

### 7.2 Install calc_via_interface

```bash
nix build '.#lgx' --out-link result-iface-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-iface-lgx/*.lgx
```

### 7.3 Install calc_module (the runtime provider)

Make sure `calc_module`'s shared library is built (from [Part 1](tutorial-wrapping-c-library.md#15-build-the-shared-library)), then package and install it:

```bash
# Build libcalc if needed (Part 1, Step 1.5):
cd ../logos-calc-module/lib
gcc -shared -fPIC -o libcalc.so libcalc.c     # Linux
# gcc -shared -fPIC -o libcalc.dylib libcalc.c  # macOS
cd -
```

```bash
nix build 'path:../logos-calc-module#lgx' --out-link result-calc-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-calc-lgx/*.lgx
```

`modules/` now holds `calc_via_interface/` and `calc_module/`. Neither knows about the other at build time — they meet only at runtime, through the interface.

### 7.4 Start the daemon and load both modules

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
sleep 4
```

Load the provider and the consumer. The consumer declares no dependency, so we load `calc_module` explicitly:

```bash
./logos/bin/logoscore load-module calc_module
```

```bash
./logos/bin/logoscore load-module calc_via_interface
```

### 7.5 Bind and call synchronously

`sumVia` / `productVia` / `versionVia` each bind `calculator` to the module name you pass, then call through the bound wrapper. Bind to `calc_module`:

```bash
./logos/bin/logoscore call calc_via_interface sumVia calc_module 3 5
```

```bash
./logos/bin/logoscore call calc_via_interface productVia calc_module 3 5
```

```bash
./logos/bin/logoscore call calc_via_interface versionVia calc_module
```

`sumVia(calc_module, 3, 5) = 8`, `productVia(calc_module, 3, 5) = 15`, and `versionVia(calc_module) = "1.0.0"` — all through `modules().bind_calculator("calc_module")`, with `calc_module` chosen at call time.

### 7.6 Bind and call asynchronously

`startFibVia` fires `calculator.fibonacci(n)` asynchronously against the bound module and returns `"queued"`. The reply arrives on the daemon's event loop; `lastFib()` reads it. With `n = 20`, `fib(20) = 6765`:

```bash
./logos/bin/logoscore call calc_via_interface startFibVia calc_module 20
```

```bash
sleep 1
```

```bash
./logos/bin/logoscore call calc_via_interface lastFib
```

The bound wrapper's generated `fibonacciAsync(..., callback)` delivered `6765` to the callback after `startFibVia` had already returned — the typed **async** path, over a runtime-bound interface.

### 7.7 Subscribe to a bound interface event

`watchVersion` subscribes to the interface's `versionReady` event on the bound module. `calc_module.libVersionNotify()` makes `calc_module` emit it, and `lastVersion()` reads what the typed callback captured:

```bash
./logos/bin/logoscore call calc_via_interface watchVersion calc_module
```

```bash
./logos/bin/logoscore call calc_module libVersionNotify
```

```bash
sleep 1
```

```bash
./logos/bin/logoscore call calc_via_interface lastVersion
```

`watchVersion` registered the callback via the generated `onVersionReady(...)`; the event fired in between; `lastVersion()` returned `1.0.0` — a typed event subscription on a runtime-bound interface.

### 7.8 Bind to a non-satisfying module (the no-validation rule)

Binding does **not** validate that the target satisfies the interface — there is no build-time coupling to check against. A bad bind isn't caught at bind time; it surfaces when you **call** through it — no crash, and the daemon keeps serving. `sumVia` checks the wrapper's `logos::CallError` out-parameter (see its implementation above) and returns `-1` when the inner call fails; on a transport that fails slowly the outer call may instead time out (`RPC_FAILED` / `"status":"error"`). Either way `calc_module` keeps answering (we keep going with `|| true` so the tour continues):

```bash
./logos/bin/logoscore call calc_via_interface sumVia no_such_module 3 5 2>&1 || true
```

The bound `no_such_module` couldn't be resolved, so the inner `add` call failed — exactly like any other call to an absent module. No crash, no conformance check. Because `sumVia` passes a `logos::CallError*`, it *sees* the failure (`err.code == "object_unavailable"`) and maps it to its own error convention; a call without the out-parameter would get the type's default value plus a warning in the module log. Swapping providers is just changing the string: `sumVia calc_module 3 5` returns `8`; `sumVia no_such_module 3 5` fails. **Any** module that really exposes `add`/`multiply`/`fibonacci`/`libVersion`/`versionReady` satisfies `calculator` and slots in unchanged.

```bash
./logos/bin/logoscore stop
```

That completes the tour: a single interface, bound at runtime to a concrete module, driven type-safely for sync calls, async calls, and events — with no build-time dependency on the provider.

---

## Step 8: Share an Interface Across Repos

So far `interfaces/calculator.h` lived in this repo. To let *several* modules depend on the **same** contract, move it to its own repo (or a provider repo that publishes the interface it implements) and pull it in as a flake input — exactly how concrete `dependencies` are wired.

Add an `"input"` field to the `interface_dependencies` entry, naming a flake input, with `file` relative to that input's root:

```json
"interface_dependencies": [
  { "name": "calculator", "input": "calc_interfaces", "file": "interfaces/calculator.h", "impl_class": "ICalculator" }
]
```

and declare the matching input in `flake.nix` (the input attribute name must equal the `input` value):

```nix
inputs = {
  logos-module-builder.url = "github:logos-co/logos-module-builder/0.2.0";
  calc_interfaces.url      = "github:your-org/logos-calc-interfaces";
};
```

The builder resolves `calc_interfaces` to a store path, hands the generator the resolved file, and emits the same bound `Calculator` wrapper — only the *source* of the contract moved. Nothing in `src/` changes. (In a workspace, run `ws sync-graph` after editing flake inputs.)

That's the full picture. An interface is a contract you can keep local or share across repos; a module binds it to whatever provider it's given at runtime; and the generated, type-safe wrappers make the bound calls feel exactly like calling a concrete dependency — minus the coupling.

---

## Recap

| Concept                          | In the code                                              | Seen via `logoscore`                                |
| -------------------------------- | -------------------------------------------------------- | --------------------------------------------------- |
| Interface declaration            | `interfaces/calculator.h` (methods + `logos_events:`)    | —                                                   |
| Declared, not depended-on        | `interface_dependencies` set, `dependencies: []`         | `lm metadata` shows empty `Dependencies:`           |
| Bind at runtime                  | `modules().bind_calculator(provider)`                    | provider is a `call` argument                       |
| Typed **sync** call              | `sumVia` / `productVia` / `versionVia`                   | `8`, `15`, `1.0.0`                                  |
| Typed **async** call             | `startFibVia` → `fibonacciAsync(..., cb)`                | `queued`, then `6765`                               |
| Typed **event** subscription     | `watchVersion` → `onVersionReady(cb)`                    | captured payload `1.0.0`                            |
| No-validation / superset rule    | bind to any module name                                  | `calc_module` → `8`; `no_such_module` → RPC error   |
| Share across repos               | `interface_dependencies[].input` + flake input           | —                                                   |

The interface coupled `calc_via_interface` to a *contract*, never to `calc_module`. Any module exposing that contract can be bound in its place — at runtime, by name.

**Next:** see [Composing Modules](tutorial-composing-modules.md) for the concrete-dependency counterpart (`modules().calc_module`), or give this module a UI with [Part 2 (QML-only)](tutorial-qml-ui-app.md) / [Part 3 (C++ backend)](tutorial-cpp-ui-app.md).
