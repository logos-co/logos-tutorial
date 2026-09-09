# Tutorial: Optional Dependencies and the Module Registry

A module can name what it talks to in three ways, and they differ in **who picks the module** and **who guarantees it is running** — not in how you call it:

| Field | Module chosen | Loader behaviour | Reached as |
| --- | --- | --- | --- |
| `dependencies` | at build time | auto-loaded; a failure to load one fails this module | `modules().<name>` |
| `optional_dependencies` | at build time | never required, never a load failure | `modules().<name>` |
| `interface_dependencies` | at **runtime**, by you | never loaded | `modules().bind_<iface>(name)` |

[Composing Modules](tutorial-composing-modules.md) covers the first and [Dependency Interfaces](tutorial-interface-dependencies.md) the third. This tutorial covers the middle one — and the module you reach for once you have it.

`optional_dependencies` is concrete, so you get the same typed wrapper a required dependency gives you. What you give up is the guarantee: nothing brings it up, nothing fails when it is missing, and it is **not bundled** into your package — which is usually the reason to reach for it, because a required dependency drags its whole runtime closure into every consumer of *your* module, including users who will never install it.

What you take on in exchange is having to ask. `modules_state` is the module that answers: a read-only registry of every module the host knows about, and a typed event when one changes state.

**What you'll build:** `calc_observer`, a core module with **two** optional dependencies — `calc_module` from [Part 1](tutorial-wrapping-c-library.md), and `modules_state`. You run it three times: with `calc_module` never installed, with it installed and running, and with it pulled out from under a live `calc_observer`.

**What you'll learn:**

- How `optional_dependencies` differs from `dependencies` — and how to see that it is not bundled
- How to tell "not running" from "running, and it said no" with `object_unavailable`
- Why an optional call needs a deadline of your own
- How to read the host's registry with `list_modules`, `module_record` and `is_ready`
- Why `null` from `module_record` is an answer and not a failure, and how `absent` differs from `unloaded`
- How to subscribe to `module_state_changed` and watch a dependency disappear without going down with it

## Prerequisites

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` whose shared library is built (`libcalc.so`/`.dylib` in `logos-calc-module/lib/`). No other part is required.
- Nix with flakes enabled
- Basic familiarity with C++

---

## Step 1: Scaffold the Module Project

`mkdir logos-calc-observer-module && cd logos-calc-observer-module`

### 1.1 Create the project from the template

```bash
nix flake init -t github:logos-co/logos-module-builder
```

### 1.2 Remove the template's example class

The minimal template ships an example `minimal_impl` class. Delete it — this tutorial supplies its own `src/` files:

```bash
rm -f src/minimal_impl.h src/minimal_impl.cpp
```

---

## Step 2: Configure the Module

### 2.1 metadata.json — note the empty `dependencies`

```json
{
  "name": "calc_observer",
  "display_name": "Calc Observer",
  "version": "1.0.0",
  "type": "core",
  "category": "example",
  "description": "Uses optional dependencies and reads the host's module registry",
  "main": "calc_observer_plugin",
  "interface": "universal",
  "dependencies": [],
  "optional_dependencies": ["modules_state", "calc_module"],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

`dependencies` is empty and stays empty. Three things follow from putting both names under `optional_dependencies` instead, and all of them are about lifetime:

- the loader **never brings one up**, and never fails a load because one is missing;
- unloading one **does not** take its dependents down;
- neither is **bundled** — consumers of `calc_observer` do not inherit their runtime closures.

A name may not appear in `dependencies` or `interface_dependencies` as well; `modules()` has one member per name, so the build refuses the ambiguity.

### 2.2 CMakeLists.txt

```
cmake_minimum_required(VERSION 3.14)
project(CalcObserverPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_observer
    SOURCES
        src/calc_observer_impl.h
        src/calc_observer_impl.cpp
)
```

### 2.3 flake.nix

Each optional name still needs a flake input — the **contract** has to come from somewhere. But nothing is *built* from it: only the dependency's published `.lidl` is read. A name that publishes no contract is refused at build time rather than quietly falling back to building it, which would defeat the point.

```nix
{
  description = "calc_observer - optional dependencies and the module registry";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    modules_state.url = "github:logos-co/logos-modules-state-module";
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

---

## Step 3: Write the Module

### 3.1 src/calc_observer_impl.h

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// A module with two OPTIONAL dependencies. Both names are concrete, so both
// get the same typed modules().<name> wrapper a required dependency gets —
// but nothing loads them, nothing fails if they are missing, and neither is
// bundled into this module's package.
class CalcObserverImpl : public LogosModuleContext {
public:
    CalcObserverImpl() = default;
    ~CalcObserverImpl() = default;

    // ── An optional dependency you can live without ──────────────────

    /// Adds two numbers via calc_module, or says why it could not.
    std::string tryAdd(int64_t a, int64_t b);

    // ── Reading the host's own registry ──────────────────────────────

    /// How many modules the host knows about, loaded or not.
    int64_t knownModules();

    /// One module's lifecycle state, or "absent" when the host has never
    /// heard of it.
    std::string stateOf(const std::string& name);

    /// Whether the host considers a module up and usable.
    bool ready(const std::string& name);

    /// Subscribes to modules_state's transition event.
    std::string watchTransitions();

    /// The last transition the subscription saw.
    std::string lastTransition();

private:
    std::string m_lastTransition = "(none)";
};
```

### 3.2 src/calc_observer_impl.cpp

```cpp
#include "calc_observer_impl.h"

#include "logos_sdk.h"

std::string CalcObserverImpl::tryAdd(int64_t a, int64_t b) {
    // Bound the call. A module that is not running costs the full protocol
    // deadline before it fails, and this one is optional by definition.
    logos::CallError err;
    int64_t sum = modules().calc_module.add(a, b, &err, /*timeout_ms=*/1500);

    // "not there" and "there, and it said no" are different answers. Code
    // that cannot tell them apart eventually treats a sick dependency as a
    // missing one.
    if (err.code == "object_unavailable")
        return "calc_module is not running";
    if (!err.ok())
        return "calc_module failed: " + err.code;

    return std::to_string(sum);
}

int64_t CalcObserverImpl::knownModules() {
    auto listing = modules().modules_state.list_modules();

    // `partial` is an honest short answer, not a health flag: it is true when
    // the host's last scan skipped something. A silently short list would be
    // worse than a flagged one.
    if (listing.partial)
        return -1;

    return static_cast<int64_t>(listing.modules.size());
}

std::string CalcObserverImpl::stateOf(const std::string& name) {
    LogosMap record = modules().modules_state.module_record(name);

    // Null is the empty optional — the host's view does not contain this
    // module. It is NOT a failed call, and it is the only spelling of
    // "absent": no record ever carries that as a state.
    if (record.is_null())
        return "absent";

    return record.value("state", "unknown");
}

bool CalcObserverImpl::ready(const std::string& name) {
    return modules().modules_state.is_ready(name);
}

std::string CalcObserverImpl::watchTransitions() {
    // The optional event parameters arrive as LogosMap, which is how an
    // absent value stays distinguishable from an empty one.
    modules().modules_state.onModule_state_changed(
        [this](const std::string& module,
               const LogosMap&, const LogosMap&,
               const std::string& oldState,
               const std::string& newState,
               const LogosMap&, uint64_t) {
            m_lastTransition = module + ": " + oldState + " -> " + newState;
        });
    return "subscribed";
}

std::string CalcObserverImpl::lastTransition() {
    return m_lastTransition;
}
```

Three things about the registry surface are worth pinning down.

**`list_modules()` returns a typed struct**, not JSON — `modules`, `partial` and `seq`, generated from the contract's record types. `module_record()` returns a `LogosMap` because its return type is an *optional* record, and null is how the empty option crosses the wire.

**The six record states are `unloaded`, `loading`, `loaded`, `ready`, `stopping`, `error`.** There is a seventh, `absent`, which appears **only in events** — a module that is absent is simply not in the listing, and `module_record` answers null. One spelling for "not there", not two.

**Treat an unrecognised state as "not loaded", never as an error.** That rule is normative. `record.value("state", "unknown")` above returns whatever the host said; a consumer that switched on a closed set and threw would break on the day a new state is introduced.

---

## Step 4: Build the Module

### 4.1 Track the files and lock the inputs

```bash
git init && git add -A
```

```bash
nix flake update --override-input calc_module path:../logos-calc-module
```

```bash
git add flake.lock
```

```bash
nix build
```

### 4.2 Package it, and see what is *not* in the box

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager' --out-link ./pm
```

```bash
nix build '.#lgx' --out-link obs-lgx
./pm/bin/lgpm --modules-dir ./modules install --file obs-lgx/*.lgx
```

```bash
ls modules/
```

```
calc_observer
```

One module. A **required** dependency would be sitting next to it, because installing a package installs what it needs to run. Optional ones are not the package's problem — something else owns their lifetime.

---

## Step 5: Run With the Dependency Missing

`calc_module` is built, but it was never installed into `modules/`. Start the daemon and load `calc_observer` anyway.

### 5.1 Start the daemon

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

### 5.2 Load it — and watch the skip get reported

```bash
./logos/bin/logoscore load-module calc_observer
```

```json
{"dependencies_loaded":[],"module":"calc_observer",
 "optional_skipped":[{"module":"calc_module","named_by":"calc_observer","reason":"not_installed"}],
 "status":"ok","version":"1.0.0"}
```

**`"status":"ok"`.** A missing optional dependency is not a load failure — but it is not silent either: the skip is reported, with the reason and who asked for it. A required dependency in the same position would have failed the load outright.

Note `modules_state` is not in the skip list. It ships with the runtime and is already there.

### 5.3 Ask the module what it can see

```bash
./logos/bin/logoscore call calc_observer tryAdd 3 4
```

```json
{"method":"tryAdd","module":"calc_observer","result":"calc_module is not running","status":"ok"}
```

That answer came from `err.code == "object_unavailable"` — and after 1500 ms, not the protocol's full default. The deadline is the point: an absent module is the case that costs you the whole budget.

```bash
./logos/bin/logoscore call calc_observer stateOf calc_module
```

```json
{"method":"stateOf","module":"calc_observer","result":"absent","status":"ok"}
```

`absent` — the host has never heard of it. Remember that spelling; it is about to change.

```bash
./logos/bin/logoscore call calc_observer ready calc_module
```

```bash
./logos/bin/logoscore call calc_observer knownModules
```

The listing is not empty even now — the runtime's own modules are in it.

---

## Step 6: Install the Dependency and Try Again

Nothing about `calc_observer` changes. Only its surroundings do.

### 6.1 Install calc_module and restart the daemon

```bash
nix build 'path:../logos-calc-module#lgx' --out-link calc-lgx
./pm/bin/lgpm --modules-dir ./modules install --file calc-lgx/*.lgx
```

```bash
# Wait for it to actually be gone — a daemon that is still shutting
# down will refuse the next one, and you will keep talking to the old
# one without noticing.
./logos/bin/logoscore stop
while ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

### 6.2 Load it again

```bash
./logos/bin/logoscore load-module calc_observer
```

```json
{"dependencies_loaded":["calc_module"],"module":"calc_observer","status":"ok","version":"1.0.0"}
```

No skip list this time. An optional dependency that *is* installed gets loaded along with its dependant — "optional" governs whether it is **required**, not whether it is wanted.

### 6.3 The same three questions

```bash
./logos/bin/logoscore call calc_observer tryAdd 3 4
```

```bash
./logos/bin/logoscore call calc_observer stateOf calc_module
```

```bash
./logos/bin/logoscore call calc_observer ready calc_module
```

`ready` is the state where the module is loaded **and** has published its object. `loaded` comes earlier — the host owns the process, but there may be nothing to call yet. That gap is why the predicate is spelled `is_ready` and not `isLoaded`.

> **Read its limit.** `is_ready` answers *the host's* view, not "a call from me will succeed" — that additionally needs a per-caller handshake this module cannot know about, so the predicate goes true a few hundred milliseconds early. Treat a **yes** as reliable and a **no** as a hint, never the other way round.

```bash
./logos/bin/logoscore call calc_observer stateOf nope
```

A name the host has never heard of is still `absent`, of course.

---

## Step 7: Take the Dependency Away Again

The last thing an optional dependency has to survive is disappearing while you are running.

### 7.1 Subscribe to the registry's event

```bash
./logos/bin/logoscore call calc_observer watchTransitions
```

```bash
./logos/bin/logoscore call calc_observer lastTransition
```

### 7.2 Unload calc_module out from under it

```bash
./logos/bin/logoscore unload-module calc_module
```

```json
{"dependents_unloaded":[],"module":"calc_module","status":"ok"}
```

**`"dependents_unloaded":[]`** — `calc_observer` is still running. Had this been a required dependency, it would have gone down with it. That is the whole bargain: you gave up the guarantee, and in return nothing else's lifetime is chained to yours.

```bash
sleep 2
```

```bash
./logos/bin/logoscore call calc_observer lastTransition
```

```json
{"method":"lastTransition","module":"calc_observer","result":"calc_module: stopping -> unloaded","status":"ok"}
```

The typed subscription saw the transition as a **pair** — where it came from and where it went. A consumer that only cares that something went away reads `new_state`; one that cares whether it was orderly reads both.

### 7.3 `unloaded` is not `absent`

```bash
./logos/bin/logoscore call calc_observer stateOf calc_module
```

```json
{"method":"stateOf","module":"calc_observer","result":"unloaded","status":"ok"}
```

Compare that with Step 5, where the same call answered `absent`. **`unloaded` means known and installed but not running; `absent` means the host has never heard of it.** An installer can act on the first and not the second, which is why they are not the same word.

```bash
./logos/bin/logoscore call calc_observer tryAdd 3 4
```

And the call fails the same way it did at the start — bounded, named, and survivable.

```bash
./logos/bin/logoscore stop
```

---

## Recap

| | `dependencies` | `optional_dependencies` |
|---|---|---|
| Typed wrapper | `modules().<name>` | **the same** |
| Auto-loaded | yes | only if installed |
| Missing at load | load fails | `"status":"ok"` + a reported skip |
| Unloading it | takes dependents down | dependents keep running |
| In your `.lgx` | bundled | not bundled |

**Reach for it when the guarantee costs more than it is worth** — a heavyweight module you can work without, whose closure you do not want to push onto everyone who installs you.

**Pay for it by asking.** Bound every optional call with a deadline of your own, and separate `object_unavailable` from a real failure. When you need a positive answer rather than a fast one, `modules_state` has the host's own view.

### The registry surface

| Call | Answers |
|---|---|
| `list_modules()` | every module the host knows, with `partial` and a listing-level `seq` |
| `module_record(name)` | one record, or **null** — the empty optional, not a failure |
| `is_ready(name)` | loaded **and** published, from the host's point of view |
| `module_state_changed` | every applied transition, as an old/new pair |

Its read surface is open to every module. Its ingest surface — `note_transition` and `apply_snapshot` — is not: those write the facts everyone else trusts, so they admit the **host only**. [Caller Identity](tutorial-caller-identity.md) is how a module draws a line like that of its own.
