# Tutorial: Concurrent Dispatch

By default a Logos module handles calls **one at a time**. Every method runs on the module's event loop, so you never think about thread-safety — and a handler that blocks stalls *every other caller* until it returns. For a module whose work is a slow download or a slow RPC, that is the wrong trade.

Setting **`"concurrency": "multi"`** in `metadata.json` opts a module into **concurrent dispatch**: each incoming call runs on its own worker. In exchange, **you** own thread-safety.

This tutorial builds two modules and *measures* the difference. Neither one is a UI, and neither depends on any earlier part.

| Module | Language | `concurrency` | Role |
|---|---|---|---|
| `calc_slow` | Rust | **`"multi"`** | a worker whose `work(ms)` blocks for `ms`, recording the peak number of calls in flight at once |
| `calc_fanout` | C++ | *(default `single`)* | an ordinary single-threaded module that fires several `work` calls **without waiting between them** |

The driver is single-threaded, yet it drives the worker concurrently — because concurrency is a property of the **callee**, not the caller. Then we flip one key in the worker's metadata and watch the same fan-out serialize.

**What you'll build:** Two composed modules that prove concurrent dispatch end-to-end: fire 4 calls at a `multi` worker and its observed peak overlap is **4**; change `"multi"` to `"single"` and the identical fan-out peaks at **1**.

**What you'll learn:**

- What `"concurrency": "multi"` does, and that it is a property of the module being called
- How the contract is enforced in Rust — `&self` and `Send + Sync`, so the compiler rejects a plain field mutation
- Why a `single` module needs no thread-safety at all, and pays nothing for the feature
- How to drive a module concurrently from an ordinary single-threaded module with the generated async caller
- The two caveats that bite — event ordering, and callers built against an older protocol

## Prerequisites

- Nix with flakes enabled
- Basic familiarity with Rust and C++. You do **not** need either toolchain installed — the builder supplies both.
- No earlier tutorial is required. If you have done [Part 1](tutorial-wrapping-c-library.md), nothing here reuses it.

---

## Step 1: Build the Tools

Both modules are driven from `logoscore`, and installed with `lgpm`. Create a working directory and build them first:

`mkdir logos-calc-concurrent && cd logos-calc-concurrent`

### 1.1 Build logoscore and the package manager

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager' --out-link ./pm
```

---

## Step 2: The Concurrent Worker (`calc_slow`)

A Rust module that blocks on purpose, and counts how many callers it is serving at any moment.

`mkdir slow-worker && cd slow-worker`

### 2.1 Scaffold it

```bash
mkdir slow-worker && cd slow-worker
nix flake init -t github:logos-co/logos-module-builder#rust
```

If the Rust scaffold is new to you, [Writing a Module in Rust](tutorial-rust-module.md) walks through it properly. Everything below is the part that differs.

### 2.2 metadata.json — one key is the whole feature

```json
{
  "name": "calc_slow",
  "display_name": "Slow Worker",
  "version": "1.0.0",
  "type": "core",
  "interface": "cdylib",
  "concurrency": "multi",
  "category": "example",
  "description": "A deliberately slow worker that records how many calls overlap",
  "main": "calc_slow_plugin",
  "dependencies": [],

  "codegen": { "rust": { "crate": "rust-lib", "trait": "CalcSlowModule" } },

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

`"concurrency": "multi"` is the only line that makes this module concurrent. Its default is `"single"`, and a `single` module is completely unchanged by the feature's existence — it pays no overhead.

The optional `"max_workers"` caps the pool. Left out, the runtime sizes it.

### 2.3 The module logic

`work` blocks. Around the block it maintains two counters, so the module can report the highest overlap it ever saw:

```
//! calc_slow — a worker that blocks, and counts how many callers it serves at once.

use std::sync::atomic::{AtomicI64, Ordering};

/// `concurrency: "multi"` changes this trait's shape: the receiver is `&self`,
/// not `&mut self`, and the bound is `Send + Sync`. That is not a style
/// choice — the generated dispatch shares one instance behind an `Arc`, so
/// a `&mut self` handler does not compile.
pub trait CalcSlowModule: Send + Sync + 'static {
    /// Blocks for `ms` milliseconds, then returns `ms`.
    fn work(&self, ms: i64) -> i64;

    /// The highest number of `work` calls that were ever in flight at once.
    fn peak(&self) -> i64;

    /// `&self` here too — in `multi` mode every hook loses `&mut`.
    fn on_context_ready(&self, _ctx: &RustModuleContext) {}
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

/// Both counters are atomics because `&self` gives no other way to mutate
/// them. A plain `i64` field here would be a compile error, which is the
/// point: the thread-safety obligation cannot be forgotten.
#[derive(Default)]
struct SlowWorker {
    in_flight: AtomicI64,
    max_seen: AtomicI64,
}

impl CalcSlowModule for SlowWorker {
    fn work(&self, ms: i64) -> i64 {
        let now = self.in_flight.fetch_add(1, Ordering::SeqCst) + 1;
        self.max_seen.fetch_max(now, Ordering::SeqCst);
        std::thread::sleep(std::time::Duration::from_millis(ms.max(0) as u64));
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
        ms
    }

    fn peak(&self) -> i64 {
        self.max_seen.load(Ordering::SeqCst)
    }
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<SlowWorker>();
}
```

> **The compiler enforces the contract.** Write `fn work(&mut self, ...)` in a `multi` module and the build fails with `error[E0596]: cannot borrow data in an Arc as mutable`. You cannot opt into concurrency and forget to make your state safe — retrofitting `multi` onto a module written around `&mut self` is a refactor, not a flag.
>
> In C++ (`interface: "universal"` or `"cdylib"`) **nothing enforces it**. Your impl's methods simply may run concurrently; guard shared members with `std::atomic` or `std::mutex` yourself. The `LogosModuleContext` accessors and the event-emit path are already thread-safe.

### 2.4 Name the crate and build

```bash
sed -i 's/^name = "minimal_rust"$/name = "calc_slow"/' rust-lib/Cargo.toml rust-lib/Cargo.lock
git init && git add -A
nix build
```

---

## Step 3: The Ordinary Driver (`calc_fanout`)

A plain C++ module with **no `concurrency` key at all**. Its own handlers are dispatched one at a time and it needs no thread-safety — yet it is what drives the worker concurrently.

`cd .. && mkdir fanout-driver && cd fanout-driver`

### 3.1 Scaffold it

```bash
mkdir fanout-driver && cd fanout-driver
nix flake init -t github:logos-co/logos-module-builder

# The template ships an example minimal_impl class; this tutorial
# supplies its own.
rm -f src/minimal_impl.h src/minimal_impl.cpp
```

### 3.2 metadata.json — a dependency, and no concurrency key

```json
{
  "name": "calc_fanout",
  "display_name": "Fan-out Driver",
  "version": "1.0.0",
  "type": "core",
  "category": "example",
  "description": "An ordinary single-threaded module that drives calc_slow concurrently",
  "main": "calc_fanout_plugin",
  "interface": "universal",
  "dependencies": ["calc_slow"],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

### 3.3 The module logic

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// An ORDINARY module: no "concurrency" key, so its own handlers are
// dispatched one at a time and it needs no thread-safety. It still drives
// calc_slow concurrently, because concurrency is a property of the CALLEE.
class CalcFanoutImpl : public LogosModuleContext {
public:
    CalcFanoutImpl() = default;
    ~CalcFanoutImpl() = default;

    /// Fires `n` calls to calc_slow.work(ms) without waiting between them,
    /// and returns immediately. Replies land later, on this module's own
    /// event loop.
    std::string fanOut(int64_t n, int64_t ms);

    /// How many of those replies have come back so far.
    int64_t repliesSeen() const;

private:
    int64_t m_replies = 0;
};
```

```cpp
#include "calc_fanout_impl.h"

#include <string>

// Generated at build time. Defines `LogosModules` with one typed accessor
// per metadata.json dependency — here `calc_slow`, a Rust module. Included
// only in the .cpp, so the header the generator parses stays free of it.
#include "logos_sdk.h"

std::string CalcFanoutImpl::fanOut(int64_t n, int64_t ms) {
    for (int64_t i = 0; i < n; ++i) {
        // The generated async caller returns immediately; the reply is
        // delivered to the callback on this module's event loop. Because
        // we never wait, all n calls are in flight at once.
        modules().calc_slow.workAsync(ms, [this](int64_t) { ++m_replies; });
    }
    return "fired " + std::to_string(n);
}

int64_t CalcFanoutImpl::repliesSeen() const {
    return m_replies;
}
```

`workAsync` is the generated async overload — `<method>Async(args..., callback)`. It returns immediately, so the loop fires all `n` calls before any of them has replied. **The synchronous `work(ms)` would not do this**: it would block the driver's own event loop on each call in turn, and the fan-out would serialize no matter what the worker is set to.

Nothing here mentions Rust. `calc_slow` is a dependency like any other, and the typed client was generated from its published contract.

### 3.4 CMakeLists.txt and flake.nix

```
cmake_minimum_required(VERSION 3.14)
project(CalcFanoutPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_fanout
    SOURCES
        src/calc_fanout_impl.h
        src/calc_fanout_impl.cpp
)
```

```nix
{
  description = "calc_fanout - drives a concurrent worker from a single-threaded module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_slow.url = "path:/path/to/slow-worker";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

The input attribute name must match the dependency name in `metadata.json` — that is how the builder resolves it. The placeholder URL is replaced on the next line.

### 3.5 Build it

```bash
git init && git add -A
nix flake update --override-input calc_slow path:../slow-worker
git add flake.lock
nix build
```

---

## Step 4: Measure the Overlap

Install both modules and drive them from a `logoscore` daemon.

### 4.1 Install both modules

```bash
nix build 'path:./slow-worker#lgx' --out-link worker-lgx
./pm/bin/lgpm --modules-dir ./modules install --file worker-lgx/*.lgx
```

```bash
nix build 'path:./fanout-driver#lgx' --out-link driver-lgx
./pm/bin/lgpm --modules-dir ./modules install --file driver-lgx/*.lgx
```

### 4.2 Start the daemon and load both

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

```bash
./logos/bin/logoscore load-module calc_slow
```

```bash
./logos/bin/logoscore load-module calc_fanout
```

### 4.3 Fan out four two-second calls

Four calls, two seconds of blocking each. Serialized that is eight seconds; overlapped it is two:

```bash
./logos/bin/logoscore call calc_fanout fanOut 4 2000
```

```json
{"method":"fanOut","module":"calc_fanout","result":"fired 4","status":"ok"}
```

The call returned at once — `fanOut` never waited for a reply. Give the work time to finish, then ask the worker what it saw:

```bash
sleep 4
```

```bash
./logos/bin/logoscore call calc_slow peak
```

```json
{"method":"peak","module":"calc_slow","result":4,"status":"ok"}
```

**Four calls were in flight at once.** All four replies came back too:

```bash
./logos/bin/logoscore call calc_fanout repliesSeen
```

---

## Step 5: Take the Key Away

Now the control. Change `"multi"` to `"single"` in the worker's metadata and nothing else about the experiment — same driver, same fan-out, same call.

The trait has to change with it, because the two modes have different shapes: `single` hands your handler a `&mut self`, so the `Send + Sync` bound is no longer required either. That coupling is the feature, not an inconvenience — the mode you declare is the mode the compiler holds you to.

### 5.1 Flip the key

```json
{
  "name": "calc_slow",
  "display_name": "Slow Worker",
  "version": "1.0.0",
  "type": "core",
  "interface": "cdylib",
  "concurrency": "single",
  "category": "example",
  "description": "A deliberately slow worker that records how many calls overlap",
  "main": "calc_slow_plugin",
  "dependencies": [],

  "codegen": { "rust": { "crate": "rust-lib", "trait": "CalcSlowModule" } },

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

### 5.2 Follow it in the trait

Three receivers become `&mut self`, and the `Sync` bound goes. The atomics can stay exactly as they are — they are simply no longer load-bearing:

```
//! calc_slow — the SINGLE-dispatch control for the same experiment.

use std::sync::atomic::{AtomicI64, Ordering};

/// `single` is the default mode: handlers run one at a time on the module's
/// event loop, so the receiver is `&mut self` and no `Sync` is needed.
pub trait CalcSlowModule: Send + 'static {
    /// Blocks for `ms` milliseconds, then returns `ms`.
    fn work(&mut self, ms: i64) -> i64;

    /// The highest number of `work` calls that were ever in flight at once.
    fn peak(&mut self) -> i64;

    fn on_context_ready(&mut self, _ctx: &RustModuleContext) {}
}

include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

#[derive(Default)]
struct SlowWorker {
    in_flight: AtomicI64,
    max_seen: AtomicI64,
}

impl CalcSlowModule for SlowWorker {
    fn work(&mut self, ms: i64) -> i64 {
        let now = self.in_flight.fetch_add(1, Ordering::SeqCst) + 1;
        self.max_seen.fetch_max(now, Ordering::SeqCst);
        std::thread::sleep(std::time::Duration::from_millis(ms.max(0) as u64));
        self.in_flight.fetch_sub(1, Ordering::SeqCst);
        ms
    }

    fn peak(&mut self) -> i64 {
        self.max_seen.load(Ordering::SeqCst)
    }
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<SlowWorker>();
}
```

### 5.3 Rebuild, reinstall, re-measure

```bash
./logos/bin/logoscore stop

(cd slow-worker && git add -A && nix build)
rm -rf modules/calc_slow
nix build 'path:./slow-worker#lgx' --out-link worker-lgx
./pm/bin/lgpm --modules-dir ./modules install --file worker-lgx/*.lgx
```

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

```bash
./logos/bin/logoscore load-module calc_slow
```

```bash
./logos/bin/logoscore load-module calc_fanout
```

### 5.4 The same fan-out, serialized

```bash
./logos/bin/logoscore call calc_fanout fanOut 4 2000
```

Eight seconds of work this time, not two, so wait longer before reading the counter:

```bash
sleep 12
```

```bash
./logos/bin/logoscore call calc_slow peak
```

```json
{"method":"peak","module":"calc_slow","result":1,"status":"ok"}
```

**Peak 1.** The driver still fired all four at once — and all four still completed:

```bash
./logos/bin/logoscore call calc_fanout repliesSeen
```

Same driver, same calls, same replies. One metadata key decided whether they overlapped.

```bash
./logos/bin/logoscore stop
```

---

## Recap

| | `single` (default) | `multi` |
|---|---|---|
| Dispatch | one call at a time, on the event loop | each call on its own worker |
| Rust receiver | `&mut self` | **`&self`**, bound `Send + Sync` |
| Rust state | plain fields | interior mutability (`Mutex`, `RwLock`, `Atomic*`) — enforced by the compiler |
| C++ | nothing to do | handlers may run concurrently; guard shared members yourself |
| Measured peak | **1** | **4** |

**Reach for `multi` when a handler blocks** — a slow network round-trip, a long download — and one caller waiting should not mean all of them waiting. A module whose methods return promptly gains nothing from it.

**Decide early.** Retrofitting `multi` onto a module written around `&mut self` is a refactor. A module that expects to block is easier to write against `&self` from its first commit.

### How it works, and its limits

`multi` is realized **entirely by the code generator** — there is no new transport and no change to the provider/host ABI. A `multi` module's generated glue does not block in its dispatch entry point: it hands the handler to a worker, returns a small *pending* marker, and pushes the real result back as a completion event when the worker finishes. The consumer side awaits that completion transparently. Because the host merely forwards the marker and the completion, **an existing daemon or app loads and runs a `multi` module unmodified** — this is logos-protocol **0.2**, an additive minor bump.

Three caveats:

1. A `single` module is unchanged and pays **zero** overhead.
2. Events your handlers emit are delivered safely, but their order **relative to method replies is not guaranteed**. Do not rely on "event X always arrives before method Y returns".
3. A *caller* built against logos-protocol < 0.2 sees the raw pending marker instead of the result. Rebuild callers against ≥ 0.2 — which stays compatible with every existing module.

Related: [Writing a Module in Rust](tutorial-rust-module.md) covers Rust authoring properly; [Composing Modules](tutorial-composing-modules.md) covers the async caller, events and persistence from the C++ side.
