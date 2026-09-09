# Tutorial: Caller Identity

Some methods should not be open to everyone. A module that holds keys, or writes the facts other modules trust, needs to know **who is calling** before it acts.

It already does. By the time your handler runs, the caller has presented a token this module itself issued — so the identity is a fact the callee possesses, not something the caller can claim. You read it with `logos::currentCaller()`. It is **ambient**: it never appears in a `.lidl`, never becomes a parameter, and no method opts in.

This tutorial builds two modules — one with an open read surface and a guarded write surface, and one that calls it — and reads the identity from all three positions a call can come from.

**What you'll build:** `calc_guarded`, whose `setLimit` admits exactly one peer module and refuses everything else, and `calc_agent`, which is that peer. You watch the same guard answer `host`, `module calc_agent` and `unknown`, and see one of those three get through.

**What you'll learn:**

- How to read the caller with `logos::currentCaller()`, and what the five arms mean
- Why the identity is ambient rather than a parameter — and why that makes it unforgeable
- Why `unknown` is the fail-closed answer and is *in band*, not an error
- That a `logoscore call` arrives as the **host anchor** — so a host-gated surface is open to anyone at the CLI
- The two ways a build can silently read `unknown` forever

## Prerequisites

- Nix with flakes enabled
- Basic familiarity with C++
- No earlier tutorial is required.

---

## Step 1: Build the Tools

`mkdir logos-calc-guarded && cd logos-calc-guarded`

### 1.1 Build logoscore and the package manager

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager' --out-link ./pm
```

---

## Step 2: The Guarded Module (`calc_guarded`)

`mkdir guarded && cd guarded`

### 2.1 Scaffold it

```bash
mkdir guarded && cd guarded
nix flake init -t github:logos-co/logos-module-builder
rm -f src/minimal_impl.h src/minimal_impl.cpp
```

### 2.2 metadata.json

Nothing here declares the guard. Caller identity is not configured — it is always available to a module built with generated glue:

```json
{
  "name": "calc_guarded",
  "display_name": "Guarded Calculator",
  "version": "1.0.0",
  "type": "core",
  "category": "example",
  "description": "An open read surface and a caller-gated write surface",
  "main": "calc_guarded_plugin",
  "interface": "universal",
  "dependencies": [],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

### 2.3 src/calc_guarded_impl.h

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

// Two surfaces with two different audiences. The read surface is open;
// the write surface admits exactly one peer module.
class CalcGuardedImpl : public LogosModuleContext {
public:
    /// Reports who the caller is, as this module sees them.
    std::string whoIsCalling();

    /// Guarded: only calc_agent may change the limit.
    std::string setLimit(int64_t n);

    /// Open to everyone.
    int64_t limit();

    /// What currentCaller() answered during onContextReady().
    std::string startupCaller();

    void onContextReady() override;

private:
    int64_t m_limit = 10;
    std::string m_startupCaller;
};
```

### 2.4 src/calc_guarded_impl.cpp

```cpp
#include "calc_guarded_impl.h"

#include <logos_caller.h>

namespace {
// The five arms. `Host` deliberately carries no name — see the recap.
std::string describe(const logos::LogosCaller& c) {
    switch (c.kind) {
        case logos::CallerKind::Host:     return "host";
        case logos::CallerKind::Module:   return "module " + c.name;
        case logos::CallerKind::Derived:  return "derived " + c.parent + "/" + c.leaf;
        case logos::CallerKind::Operator: return "operator " + c.name;
        default:                          return "unknown";
    }
}
}

std::string CalcGuardedImpl::whoIsCalling() {
    return describe(logos::currentCaller());
}

std::string CalcGuardedImpl::setLimit(int64_t n) {
    const logos::LogosCaller caller = logos::currentCaller();

    // isModule(name) ignores the instance, so a restarted calc_agent is
    // still calc_agent. Anything that is not that module — including the
    // host, and including `unknown` — falls through and is refused.
    if (!caller.isModule("calc_agent"))
        return "refused: " + describe(caller);

    m_limit = n;
    return "ok";
}

int64_t CalcGuardedImpl::limit() { return m_limit; }

void CalcGuardedImpl::onContextReady() {
    // No inbound dispatch is in flight during startup, so there is no caller
    // to report. That answer is `unknown`, in band and fail-closed.
    m_startupCaller = describe(logos::currentCaller());
}

std::string CalcGuardedImpl::startupCaller() { return m_startupCaller; }
```

The gate is one line, and it is **structural**: authority is what the caller *is*, not what it knows. There is no shared secret to distribute, rotate or leak, and no `callerName` argument a caller could fill in with a name that is not theirs.

Note the shape of the refusal. `if (!caller.isModule("calc_agent"))` fails **closed** — every arm the code did not think about, including `unknown` and including an arm from a protocol newer than this build, lands on the refusal path. Written the other way round (`if (caller.isSomething()) refuse;`) it would fail open.

### 2.5 CMakeLists.txt and build

```
cmake_minimum_required(VERSION 3.14)
project(CalcGuardedPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_guarded
    SOURCES
        src/calc_guarded_impl.h
        src/calc_guarded_impl.cpp
)
```

```bash
git init && git add -A
nix build
```

---

## Step 3: The Peer Module (`calc_agent`)

A module that calls the guarded one, so we can see what the guard sees when the caller is a peer rather than a person at a terminal.

`cd .. && mkdir agent && cd agent`

### 3.1 Scaffold it

```bash
mkdir agent && cd agent
nix flake init -t github:logos-co/logos-module-builder
rm -f src/minimal_impl.h src/minimal_impl.cpp
```

### 3.2 metadata.json

```json
{
  "name": "calc_agent",
  "display_name": "Calc Agent",
  "version": "1.0.0",
  "type": "core",
  "category": "example",
  "description": "Calls calc_guarded, so the guard sees a module rather than the host",
  "main": "calc_agent_plugin",
  "interface": "universal",
  "dependencies": ["calc_guarded"],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

The name in `dependencies` is `calc_agent`'s own declaration of who it talks to. It is **not** what makes the guard admit it — the name the guard reads comes from the token the host minted, not from this file.

### 3.3 The module logic

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>

class CalcAgentImpl : public LogosModuleContext {
public:
    /// Asks calc_guarded who IT thinks is calling.
    std::string askWhoIsCalling();

    /// Forwards a setLimit through, so the guard sees a module.
    std::string forwardSetLimit(int64_t n);
};
```

```cpp
#include "calc_agent_impl.h"

#include "logos_sdk.h"

std::string CalcAgentImpl::askWhoIsCalling() {
    return modules().calc_guarded.whoIsCalling();
}

std::string CalcAgentImpl::forwardSetLimit(int64_t n) {
    return modules().calc_guarded.setLimit(n);
}
```

Neither method says who it is. The **origin** every outbound call carries is baked in by the generated scaffold from this module's own contract name, before any of your code runs — so a module cannot announce itself as something else.

### 3.4 CMakeLists.txt, flake.nix and build

```
cmake_minimum_required(VERSION 3.14)
project(CalcAgentPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME calc_agent
    SOURCES
        src/calc_agent_impl.h
        src/calc_agent_impl.cpp
)
```

```nix
{
  description = "calc_agent - the peer calc_guarded admits";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_guarded.url = "path:/path/to/guarded";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

```bash
git init && git add -A
nix flake update --override-input calc_guarded path:../guarded
git add flake.lock
nix build
```

---

## Step 4: Ask the Guard Who Is Calling

### 4.1 Install both and start the daemon

```bash
nix build 'path:./guarded#lgx' --out-link g-lgx
./pm/bin/lgpm --modules-dir ./modules install --file g-lgx/*.lgx
```

```bash
nix build 'path:./agent#lgx' --out-link a-lgx
./pm/bin/lgpm --modules-dir ./modules install --file a-lgx/*.lgx
```

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

```bash
./logos/bin/logoscore load-module calc_agent
```

Loading `calc_agent` brings `calc_guarded` up with it — it is a required dependency.

### 4.2 From the command line

```bash
./logos/bin/logoscore call calc_guarded whoIsCalling
```

```json
{"method":"whoIsCalling","module":"calc_guarded","result":"host","status":"ok"}
```

**`host`** — not `operator`. Your `logoscore call` was relayed by the daemon, and it arrives under the host anchor. Worth knowing before you gate anything on `isHost()`: on this path, that is a gate anyone with access to the CLI passes.

### 4.3 From another module

```bash
./logos/bin/logoscore call calc_agent askWhoIsCalling
```

```json
{"method":"askWhoIsCalling","module":"calc_agent","result":"module calc_agent","status":"ok"}
```

The same method, a different answer. `calc_agent` did not pass a name — the guard read it off the call.

### 4.4 From no call at all

```bash
./logos/bin/logoscore call calc_guarded startupCaller
```

```json
{"method":"startupCaller","module":"calc_guarded","result":"unknown","status":"ok"}
```

`onContextReady()` runs at startup, with no inbound dispatch in flight, so there is no caller and the answer is **`unknown`**. That is not an error and not a missing value — it is one of the five arms, and it is the one everything unrecognised also lands on.

---

## Step 5: Watch the Gate Work

### 5.1 The command line is refused

```bash
./logos/bin/logoscore call calc_guarded setLimit 99
```

```json
{"method":"setLimit","module":"calc_guarded","result":"refused: host","status":"ok"}
```

Refused, and the refusal **names what the caller actually was**. A guard that just says "no" leaves you unable to tell a genuine rejection from a build that reads `unknown` for a reason you have not found yet.

### 5.2 The peer module is admitted

```bash
./logos/bin/logoscore call calc_agent forwardSetLimit 42
```

```bash
./logos/bin/logoscore call calc_guarded limit
```

```json
{"method":"limit","module":"calc_guarded","result":42,"status":"ok"}
```

Same method, same daemon, same second — and the value changed only for the caller the guard admits. `limit()` stayed open to everyone throughout.

```bash
./logos/bin/logoscore stop
```

---

## Recap

| Arm | Carries | Seen when |
|---|---|---|
| `Host` | **nothing** | the runtime itself — including a relayed `logoscore call` |
| `Module` | `name`, optional `instance` | one module calling another |
| `Derived` | `parent`, `leaf` | a call from a derived identity, e.g. a UI plugin under its module |
| `Operator` | `name` | a named operator token |
| `Unknown` | — | everything else |

**`Host` has no name, ever.** Not an oversight: `"core"` and `"capability_module"` hold the same token value under two keys, so a name there would be a coin flip presented as a fact. If you need to admit the runtime, ask `isHost()` — do not go looking for which part of it called.

**`Unknown` is fail-closed and in band.** It covers an unnamed caller, a document this build cannot read, an arm from a newer protocol, and *no dispatch in flight on this thread* — a spawned worker, a timer, `onContextReady`, an event emission. Handle it on the refusal path, never as an error.

**The identity is valid for one dispatch, on the dispatching thread.** A handler that needs it later must copy it at the top; reading it from a thread you spawned answers `Unknown`.

**You are not checking a claim.** An unauthorized call never reaches your handler at all — the identity you read is a byproduct of the authorization that already happened, which is why there is nothing for a caller to spoof.

### Two ways to read `unknown` forever

1. **A legacy `Q_INVOKABLE` Qt plugin.** The handler body runs in the plugin image with no generated glue, so nothing pushes the identity in. `interface: "universal"` and `"cdylib"` modules — everything in this tutorial series — are fine.
2. **A mispinned build.** A plugin generated below logos-protocol 0.6 has no caller machinery at all: every call reads `unknown` while the module still compiles, links and loads. Nothing warns you, which is exactly why a refusal should name what it saw.

In Rust the same surface is `logos_rust_sdk::current_caller()`, returning
`Unknown | HostAnchor | Module{name, instance} | Derived{parent, leaf} | Operator{name}`,
with `is_module(name)`, `identity()` for a map key and `describe_for_human()` for a log line.

A real gate built exactly this way is `modules_state`, whose read surface is open to every module and whose ingest surface admits the host only — see [Optional Dependencies and the Module Registry](tutorial-modules-state.md).
