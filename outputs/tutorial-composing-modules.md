# Tutorial: Composing Modules with the Module Context

This tutorial builds `calc_aggregator`, a **core module that depends on another module** (`calc_module` from [Part 1](tutorial-wrapping-c-library.md)). It does no arithmetic of its own — instead it *composes* `calc_module`'s primitives into a single call, and along the way showcases everything the SDK's `LogosModuleContext` base class gives a universal module. There is no UI: you drive the whole thing from `logoscore` on the command line.

**What you'll build:** A `calc_aggregator` core module that, through the `LogosModuleContext` base class:

- reads the three host-injected properties — `modulePath()`, `instanceId()`, `instancePersistencePath()`
- persists state in its per-instance data directory (a run counter that survives restarts), wired up in the `onContextReady()` hook
- calls `calc_module` with the generated, type-safe `modules().calc_module` wrappers — **synchronously** (five calls composed into one `computeReport`) and **asynchronously** (`fibonacciAsync` with a callback)
- subscribes to `calc_module`'s `versionReady` **event** with a typed callback

No Qt, no `LogosAPI`, no plugin boilerplate — one plain C++ class, exactly like Part 1.

**What you'll learn:**

- How one module declares another as a dependency (`metadata.json` + `flake.nix` input)
- How `LogosModuleContext` exposes `modulePath` / `instanceId` / `instancePersistencePath` to a universal module
- How to use the per-instance persistence directory for durable state, set up in `onContextReady()`
- How `modules().<dep>` gives you typed **sync** and **async** callers — no raw `LogosAPI`, no `QVariant`
- How to subscribe to another module's `logos_events:` with a typed callback
- How to load two modules in `logoscore` and chain calls to observe events and async replies

## Prerequisites

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` whose shared library is built (`libcalc.so`/`.dylib` in `logos-calc-module/lib/`). This tutorial only needs `calc_module`; the UI tutorials (Parts 2–3) are not required.
- Nix with flakes enabled
- Basic familiarity with C++

---

## Step 1: Scaffold the Module Project

Create a new directory and initialise it from the minimal module template:

`mkdir logos-calc-aggregator-module && cd logos-calc-aggregator-module`

### 1.1 Create the project from the template

```bash
nix flake init -t github:logos-co/logos-module-builder
```

This scaffolds a `flake.nix`, `metadata.json`, `CMakeLists.txt`, and a `src/` directory pre-wired for `logos-module-builder`. As in Part 1 we use the newer **pure-C++ (`interface: universal`) pattern**, so we replace the template's example `src/` files with a single plain `*_impl.h` / `*_impl.cpp` class.

### 1.2 Remove the template's example sources

The minimal template ships an example Qt plugin (`minimal_*`). Delete those — this tutorial supplies its own pure-C++ `src/` files:

```bash
rm -f src/minimal_interface.h src/minimal_plugin.h src/minimal_plugin.cpp
```

---

## Step 2: Configure the Module

Three small config files declare the module, its dependency on `calc_module`, and how to build it.

### 2.1 `metadata.json` — declare the dependency

The one field that matters here is `dependencies`: listing `calc_module` tells the builder to read `calc_module`'s published LIDL interface contract and generate a typed wrapper for it — without building `calc_module` itself. The dependency name **must match** `calc_module`'s own `metadata.json` `name`.

```json
{
  "name": "calc_aggregator",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Composes calc_module and showcases LogosModuleContext",
  "main": "calc_aggregator_plugin",
  "interface": "universal",
  "dependencies": ["calc_module"],

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

| Field          | What it does                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------- |
| `interface`    | `"universal"` — you write one plain C++ class; the builder generates the Qt plugin glue                       |
| `dependencies` | `["calc_module"]` — the builder generates `modules().calc_module`, a typed wrapper with sync/async/event APIs |

Unlike Part 1, there is no `external_libraries` entry — this module wraps no C library, it depends on another **module**.

### 2.2 `CMakeLists.txt` — list your sources

For a universal module you list only your plain C++ files. The generated dependency glue is compiled automatically.

```cmake
cmake_minimum_required(VERSION 3.14)
project(CalcAggregatorPlugin LANGUAGES CXX)

# Include the Logos Module CMake helper (provided by logos-module-builder)
if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_aggregator
    SOURCES
        src/calc_aggregator_impl.h
        src/calc_aggregator_impl.cpp
)
```

`NAME` must match `name` in `metadata.json` (`calc_aggregator`). No `EXTERNAL_LIBS` here — the only dependency is another module, resolved via `metadata.json` + `flake.nix`, not CMake.

### 2.3 `flake.nix` — add the dependency input

Declare `calc_module` as a flake input. The input attribute name **must match** the dependency name in `metadata.json`. The `path:/path/to/your/calc_module` value is a placeholder — you lock it to your real Part 1 checkout in the build step with `--override-input` (Nix won't accept a relative `../` path written directly into `flake.nix`).

```nix
{
  description = "Aggregator core module - composes calc_module and showcases LogosModuleContext";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # The module this one depends on. Placeholder path — locked to your
    # real checkout in the build step via `--override-input`.
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

`flakeInputs = inputs` hands every input (including `calc_module`) to the builder, which resolves the `calc_module` dependency declared in `metadata.json` and runs `logos-cpp-generator` to emit the typed wrapper.

---

## Step 3: Write the Module Class

The whole module is one plain C++ class that inherits `LogosModuleContext`. Inheriting that base is what unlocks the context getters (`modulePath()` / `instanceId()` / `instancePersistencePath()`), the `onContextReady()` hook, and `modules()` — typed access to declared dependencies. No Qt anywhere.

### 3.1 `src/calc_aggregator_impl.h` — the class

Every `public` method becomes callable over IPC. The methods fall into four groups: the context getters, the persistence demo, the sync/async composition of `calc_module`, and the event subscription.

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_json.h>            // LogosMap (QVariantMap on the wire)
#include <logos_module_context.h>  // LogosModuleContext base class

// A core module that depends on calc_module. It does no arithmetic of
// its own — it *composes* calc_module's primitives and showcases what
// the SDK's LogosModuleContext base class gives a universal module:
//
//   • modulePath()              — where the plugin was loaded from
//   • instanceId()              — host-assigned, stable per persistence dir
//   • instancePersistencePath() — per-instance writable data directory
//   • onContextReady()          — one-time setup hook
//   • modules()                 — typed access to declared dependencies
//                                 (sync callers, async callers, events)
//
// Because metadata.json sets "interface": "universal", the builder
// generates the Qt plugin wrapper from this plain class.
class CalcAggregatorImpl : public LogosModuleContext {
public:
    CalcAggregatorImpl() = default;
    ~CalcAggregatorImpl() = default;

    // ── The three host-injected context properties ─────────────────

    /// Directory the plugin file was loaded from (modulePath()).
    std::string moduleDir() const;

    /// Host-assigned instance ID (instanceId()).
    std::string instanceID() const;

    /// True iff the host populated a non-empty instance ID. A bool
    /// return distinguishes "host wired it" from the empty-string
    /// default a plain string getter can't tell apart over the CLI.
    bool hasInstanceID() const;

    /// Per-instance writable data directory (instancePersistencePath()).
    std::string persistenceDir() const;

    /// Increments a counter stored under persistenceDir() and returns
    /// the new value. The persistence dir is host-owned and durable, so
    /// the count keeps climbing across restarts — it is loaded back in
    /// onContextReady().
    int64_t bumpRunCount();

    // ── Compose calc_module: five sync calls into one result ───────

    /// Runs add / multiply / factorial / fibonacci / libVersion on
    /// calc_module and returns them as a single map. One call here
    /// fans out to five typed, synchronous cross-module calls.
    LogosMap computeReport(int64_t a, int64_t b, int64_t n);

    // ── Compose calc_module: an async call ─────────────────────────

    /// Fires calc_module.fibonacci(n) *asynchronously* and returns
    /// right away ("queued"). The reply lands later in a callback that
    /// stashes it; read it back with asyncResult().
    std::string startAsyncFibonacci(int64_t n);

    /// The most recent value delivered by startAsyncFibonacci()'s
    /// callback, or -1 if none has arrived yet.
    int64_t asyncResult() const;

    // ── Subscribe to a calc_module event ───────────────────────────

    /// Subscribes to calc_module's `versionReady` event with a typed
    /// callback. Returns "ok" once registered. Trigger it by calling
    /// calc_module.libVersionNotify().
    std::string subscribeVersion();

    /// The last version string delivered by the versionReady
    /// subscription, or empty until one fires.
    std::string lastVersionEvent() const;

protected:
    // One-time hook the framework fires once the context getters above
    // are populated, before any method dispatch — the canonical place
    // for setup that needs the persistence path.
    void onContextReady() override;

private:
    int64_t     m_runCount = 0;
    int64_t     m_asyncResult = -1;
    std::string m_lastVersionEvent;
    bool        m_subscribed = false;
};
```

A few things to notice:

- The class inherits **`LogosModuleContext`** — that's the opt-in that gives it the context getters and `modules()`.
- `onContextReady()` is `protected` (an override of the base hook), so it is **not** exposed over IPC — only the `public` methods are.
- `hasInstanceID()` returns `bool` on purpose: the CLI prints a `Result:` line for any string (even empty), so a boolean is the unambiguous way to assert "the host populated the ID".

### 3.2 `src/calc_aggregator_impl.cpp` — the implementation

The `.cpp` includes the generated `logos_sdk.h` (which defines `LogosModules`) — that's why the cross-module calls live here and not in the header the generator parses. Each group of methods maps one-to-one onto the bullets in the class comment.

```cpp
#include "calc_aggregator_impl.h"

#include <fstream>

// Generated at build time by logos-cpp-generator. Defines `LogosModules`
// with one std-typed accessor per metadata.json dependency — here
// `calc_module`. Included only in the .cpp so the impl header the
// generator parses stays free of Qt and codegen types.
#include "logos_sdk.h"

namespace {
// The run-count file lives inside the host-provisioned persistence dir.
// An empty dir means the module was constructed outside a host (e.g. a
// unit test) — treat that as "nothing to persist".
std::string runCountPath(const std::string& dir) {
    return dir.empty() ? std::string() : dir + "/runcount.txt";
}
}  // namespace

void CalcAggregatorImpl::onContextReady() {
    // The three context getters are populated now. Load any previously
    // persisted run count so bumpRunCount() continues across restarts.
    const std::string path = runCountPath(instancePersistencePath());
    if (path.empty()) return;
    std::ifstream in(path);
    if (in) in >> m_runCount;
}

// ── Context getters — thin pass-throughs to the SDK base class ──────

std::string CalcAggregatorImpl::moduleDir() const {
    return modulePath();
}

std::string CalcAggregatorImpl::instanceID() const {
    return instanceId();
}

bool CalcAggregatorImpl::hasInstanceID() const {
    return !instanceId().empty();
}

std::string CalcAggregatorImpl::persistenceDir() const {
    return instancePersistencePath();
}

int64_t CalcAggregatorImpl::bumpRunCount() {
    ++m_runCount;
    const std::string path = runCountPath(instancePersistencePath());
    if (!path.empty()) {
        std::ofstream out(path, std::ios::trunc);
        out << m_runCount;
    }
    return m_runCount;
}

// ── Sync composition: five calls into one map ───────────────────────

LogosMap CalcAggregatorImpl::computeReport(int64_t a, int64_t b, int64_t n) {
    // modules().calc_module is the generated, std-typed wrapper for the
    // `calc_module` dependency — no raw LogosAPI, no QVariant. Five
    // synchronous calls, composed into one map the caller gets back.
    auto& calc = modules().calc_module;
    LogosMap report;
    report["sum"]        = calc.add(a, b);
    report["product"]    = calc.multiply(a, b);
    report["factorial"]  = calc.factorial(n);
    report["fibonacci"]  = calc.fibonacci(n);
    report["libVersion"] = calc.libVersion();
    return report;
}

// ── Async composition: fire now, read the reply later ───────────────

std::string CalcAggregatorImpl::startAsyncFibonacci(int64_t n) {
    // The generated async overload is `<method>Async(args...,
    // callback, timeout = Timeout())`. It returns immediately; the
    // reply is delivered to the callback on this module's event loop.
    modules().calc_module.fibonacciAsync(n, [this](int64_t value) {
        m_asyncResult = value;
    });
    return "queued";
}

int64_t CalcAggregatorImpl::asyncResult() const {
    return m_asyncResult;
}

// ── Event subscription on a dependency ──────────────────────────────

std::string CalcAggregatorImpl::subscribeVersion() {
    if (m_subscribed) return "ok";
    // Typed subscriber generated from calc_module's `logos_events:`
    // versionReady(const std::string&). The accessor is `on` + the
    // capitalized event name; the callback's arg types match the event.
    m_subscribed = modules().calc_module.onVersionReady(
        [this](const std::string& version) {
            m_lastVersionEvent = version;
        });
    return m_subscribed ? "ok" : "failed";
}

std::string CalcAggregatorImpl::lastVersionEvent() const {
    return m_lastVersionEvent;
}
```

That's the entire module. The three capabilities the SDK base class enables are all here:

1. **Context properties** — `moduleDir()`, `instanceID()`, `persistenceDir()` just return the base getters; `bumpRunCount()` + `onContextReady()` show the persistence dir used for real, durable state.
2. **Typed dependency calls** — `computeReport()` uses the **sync** wrappers (`calc.add(...)`, …); `startAsyncFibonacci()` uses the **async** wrapper (`fibonacciAsync(..., callback)`).
3. **Typed event subscription** — `subscribeVersion()` registers a callback on `calc_module`'s `versionReady` event via the generated `onVersionReady(...)` accessor.

---

## Step 4: Build the Module

### 4.1 Add a `.gitignore` and init the repo

Nix flakes require a git repository. Exclude build artifacts first:

```text
# Nix build output
result
result-*

# CMake build directory
build/
```

Initialise the repo and stage the files:

```bash
git init && git add -A
```

### 4.2 Make sure `calc_module` is built

The dependency must be built with its shared library present in `lib/` (from [Part 1](tutorial-wrapping-c-library.md#15-build-the-shared-library)). Verify it:

```bash
ls ../logos-calc-module/lib/libcalc.so    # Linux
ls ../logos-calc-module/lib/libcalc.dylib  # macOS
```

If it is missing, build it (as in Part 1, Step 1.5):

```bash
cd ../logos-calc-module/lib
gcc -shared -fPIC -o libcalc.so libcalc.c     # Linux
# gcc -shared -fPIC -o libcalc.dylib libcalc.c  # macOS
cd -
```

### 4.3 Lock the dependency and build

Lock `calc_module` to your local Part 1 checkout. `--override-input` resolves `../logos-calc-module` to an absolute path and records it in `flake.lock`, replacing the placeholder in `flake.nix`:

```bash
nix flake update --override-input calc_module path:../logos-calc-module
```

```bash
git add flake.lock
```

Now build the full package. For a universal module with a dependency, this is where `logos-cpp-generator` runs over both `src/calc_aggregator_impl.h` and `calc_module`'s published LIDL contract, emitting the plugin glue **and** the typed `modules().calc_module` wrapper under `generated_code/` — note `calc_module`'s own plugin is not built here, only its LIDL is read:

```bash
nix build
```

### 4.4 Check the output

```bash
ls -la result/lib/
```

You should see your plugin (extension depends on platform):

```
calc_aggregator_plugin.so     # Linux
calc_aggregator_plugin.dylib  # macOS
```

---

## Step 5: Inspect the Module

Use `lm` to confirm the dependency and the public API made it into the binary.

### 5.1 Build `lm`

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

### 5.2 View metadata — note the dependency

```bash
./lm/bin/lm metadata result/lib/calc_aggregator_plugin.so    # Linux
./lm/bin/lm metadata result/lib/calc_aggregator_plugin.dylib  # macOS
```

```
Plugin Metadata:
================
Name:         calc_aggregator
Version:      1.0.0
Description:  Composes calc_module and showcases LogosModuleContext
Author:
Type:         core
Dependencies: calc_module
```

`Dependencies: calc_module` confirms the link the builder used to generate the typed wrapper.

### 5.3 List methods

```bash
./lm/bin/lm methods result/lib/calc_aggregator_plugin.so    # Linux
./lm/bin/lm methods result/lib/calc_aggregator_plugin.dylib  # macOS
```

Every `public` method on the impl is here — `int64_t` shows up as `int`, `std::string` as `QString`, and `LogosMap` (from `computeReport`) as `QVariantMap`, because `lm` reports the wire types the generated glue exposes.

---

## Step 6: Run it with `logoscore`

Now the payoff: run `calc_aggregator` **and** its `calc_module` dependency under `logoscore` and exercise every capability. We use the `logoscore` **daemon** (`-D`) — it keeps each module's process alive between `call` commands, so an event subscription registered by one call is still active when a later call triggers it, and an async reply lands before the call that reads it. (This is the same daemon flow as [Part 1](tutorial-wrapping-c-library.md#step-6-test-with-logoscore).)

### 6.1 Build the runtime and package both modules

Build `logoscore` and the package manager, then install **both** modules into a `modules/` directory `logoscore` can scan. The aggregator comes from this project; `calc_module` from your Part 1 checkout:

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager#cli' --out-link ./pm
```

```bash
mkdir -p modules
```

### 6.2 Install calc_aggregator

```bash
nix build '.#lgx' --out-link result-aggregator-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-aggregator-lgx/*.lgx
```

### 6.3 Install calc_module (the dependency)

```bash
nix build 'path:../logos-calc-module#lgx' --out-link result-calc-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-calc-lgx/*.lgx
```

`modules/` now holds `calc_aggregator/` and `calc_module/`, each with its plugin, libraries, and `manifest.json`.

### 6.4 Create a persistence directory and start the daemon

The host only provisions a per-instance persistence path when you pass `--persistence-path`. Create a directory for it — we reuse the **same** directory across restarts so the instance ID (and therefore the persisted state) is stable:

```bash
mkdir -p calc-data
```

Start `logoscore` as a background daemon, pointed at the modules directory and the persistence directory:

```bash
./logos/bin/logoscore -D -m ./modules --persistence-path ./calc-data &
```

```bash
sleep 4
```

Load both modules. The daemon keeps each module's process alive between `call` commands, which is what lets an event subscription (or an async reply) survive from one call to the next:

```bash
./logos/bin/logoscore load-module calc_module
```

```bash
./logos/bin/logoscore load-module calc_aggregator
```

### 6.5 Read the context properties

`moduleDir()` / `hasInstanceID()` / `persistenceDir()` return the values the host stamped onto the module. We can't predict the absolute path, but `moduleDir()` must contain the module name:

```bash
./logos/bin/logoscore call calc_aggregator moduleDir
```

`hasInstanceID()` returns a bool, so a non-empty instance ID shows as `"result":true` — an unambiguous signal the host populated `instanceId()` (a plain string getter would read as empty either way):

```bash
./logos/bin/logoscore call calc_aggregator hasInstanceID
```

```bash
./logos/bin/logoscore call calc_aggregator persistenceDir
```

- `moduleDir()` → the directory the plugin loaded from (contains `calc_aggregator`)
- `hasInstanceID()` → `"result":true` — the host populated `instanceId()`
- `persistenceDir()` → a path under your `calc-data/` directory, namespaced by module name and instance ID

### 6.6 Compose calc_module synchronously

`computeReport(a, b, n)` fans out to five typed `calc_module` calls and returns them as one map. With `a=3, b=5, n=10`:

```bash
./logos/bin/logoscore call calc_aggregator computeReport 3 5 10
```

One call, five composed results:

```json
{"method":"computeReport","module":"calc_aggregator","result":{"factorial":3628800,"fibonacci":55,"libVersion":"1.0.0","product":15,"sum":8},"status":"ok"}
```

`sum = 3+5`, `product = 3*5`, `factorial = 10!`, `fibonacci = fib(10)`, and `libVersion` read straight from `calc_module` — all through the generated `modules().calc_module` sync wrappers.

### 6.7 Compose calc_module asynchronously

`startAsyncFibonacci(n)` fires `calc_module.fibonacciAsync(n)` and returns `"queued"` immediately. The reply arrives on the daemon's event loop; the next call, `asyncResult()`, reads what the callback stashed. With `n=20`, `fib(20) = 6765`:

```bash
./logos/bin/logoscore call calc_aggregator startAsyncFibonacci 20
```

```bash
sleep 1
```

```bash
./logos/bin/logoscore call calc_aggregator asyncResult
```

`startAsyncFibonacci` returned before the answer existed; by the time `asyncResult()` runs, the async callback has fired and stored `6765`. That's the typed **async** caller — same wrapper, `<method>Async(..., callback)`.

### 6.8 Subscribe to a calc_module event

The typed event subscription. `subscribeVersion()` registers the callback, `calc_module.libVersionNotify()` makes `calc_module` emit its `versionReady` event, and `lastVersionEvent()` reads what the subscription captured. Because the daemon keeps both modules loaded, the event fires between the calls:

```bash
./logos/bin/logoscore call calc_aggregator subscribeVersion
```

```bash
./logos/bin/logoscore call calc_module libVersionNotify
```

```bash
sleep 1
```

```bash
./logos/bin/logoscore call calc_aggregator lastVersionEvent
```

`subscribeVersion()` returned `ok`; the event fired in between; `lastVersionEvent()` returned `1.0.0` — the payload `calc_module` emitted, delivered to the typed callback you registered with `modules().calc_module.onVersionReady(...)`.

### 6.9 Persist state across a restart

`bumpRunCount()` increments a counter saved in the persistence directory. Call it twice — `1`, then `2`:

```bash
./logos/bin/logoscore call calc_aggregator bumpRunCount
```

```bash
./logos/bin/logoscore call calc_aggregator bumpRunCount
```

Now stop the daemon and start a **brand-new** one against the same persistence directory. `onContextReady()` loads the persisted `2` from disk, so the next bump is `3`:

```bash
./logos/bin/logoscore stop
```

```bash
sleep 2
```

```bash
./logos/bin/logoscore -D -m ./modules --persistence-path ./calc-data &
```

```bash
sleep 4
```

```bash
./logos/bin/logoscore load-module calc_aggregator
```

```bash
./logos/bin/logoscore call calc_aggregator bumpRunCount
```

The count survived a full process restart — proof the persistence directory is host-owned and durable, and that `onContextReady()` is the right place to rehydrate per-instance state.

```bash
./logos/bin/logoscore stop
```

That completes the tour: context properties, durable persistence, sync **and** async typed dependency calls, and a typed event subscription — every capability of `LogosModuleContext`, driven entirely from `logoscore`.

---

## Recap

| Capability                       | In the code                                              | Seen via `logoscore`                                |
| -------------------------------- | -------------------------------------------------------- | --------------------------------------------------- |
| `modulePath()`                   | `moduleDir()`                                            | path contains `calc_aggregator`                     |
| `instanceId()`                   | `instanceID()` / `hasInstanceID()`                       | `"result":true`                                     |
| `instancePersistencePath()`      | `persistenceDir()` + `bumpRunCount()` + `onContextReady` | counter climbs `1 → 2 → 3` across a restart         |
| Typed **sync** dependency call   | `computeReport()` → `calc.add(...)`, …                  | one map of five composed results                    |
| Typed **async** dependency call  | `startAsyncFibonacci()` → `fibonacciAsync(..., cb)`     | `queued`, then `6765`                               |
| Typed **event** subscription     | `subscribeVersion()` → `onVersionReady(cb)`             | captured payload `1.0.0` after the event fires      |

Everything flowed through `modules().calc_module`, the wrapper the builder generated from the `calc_module` dependency — no raw `LogosAPI`, no `QVariant`, no Qt in your code.

**Next:** give this module a UI by following [Part 2 (QML-only)](tutorial-qml-ui-app.md) or [Part 3 (C++ backend)](tutorial-cpp-ui-app.md), or package it for distribution with `nix build '.#lgx-portable'` (see [Part 1 — Package for Distribution](tutorial-wrapping-c-library.md#package-for-distribution-optional)).
