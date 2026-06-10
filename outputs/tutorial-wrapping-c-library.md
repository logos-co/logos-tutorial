# Tutorial: Wrapping a C Library as a Logos Module

This tutorial walks you through wrapping a C shared library (`.so` on Linux, `.dylib` on macOS) as a Logos module. By the end, you will have a module that compiles, loads, and responds to method calls via `logoscore`.

**What you'll build:** A `calc_module` that wraps a tiny C calculator library (`libcalc`), exposing arithmetic functions to the Logos platform. You write a single **plain C++ class** — no Qt, no plugin boilerplate — and the build system generates the Qt plugin around it.

**What you'll learn:**

- {'How a Logos module wraps a C library using the pure-C++ (`interface': 'universal`) pattern'}
- The role of each file in the module project
- Which C++ types the code generator maps onto the wire (`std::string`, `int64_t`, `bool`, …)
- How to emit events from a plain C++ class with `logos_events:`
- How to build, inspect, and unit-test your module (with the Logos Test Framework)
- How `logoscore` discovers, loads, and calls your module

## Prerequisites

- **Nix** with flakes enabled. Install from [nixos.org](https://nixos.org/download.html), then enable flakes:

```bash
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
```

Verify: `nix flake --help >/dev/null 2>&1 && echo "Flakes enabled"`

- **A C compiler** (gcc or clang) for building the C library. Only needed if you're building the `.so`/`.dylib` yourself rather than using a pre-built library.
- Basic familiarity with C and C++.

---

## Step 1: Scaffold the Module Project

Before writing any C code, scaffold the Logos module project using the official template. This gives you the correct `flake.nix`, `metadata.json`, directory structure, and build configuration out of the box.

### 1.1 Create the project using the module builder template

For a module that wraps an external C library:

`mkdir logos-calc-module && cd logos-calc-module`

```bash
nix flake init -t github:logos-co/logos-module-builder#with-external-lib

# Or for a plain module (no external library):
# nix flake init -t github:logos-co/logos-module-builder
```

This generates skeleton files (`flake.nix`, `metadata.json`, `CMakeLists.txt`, and a `src/` directory) pre-configured for the logos-module-builder. You then customize them for your specific library.

> **Heads up — the template is the older Qt-plugin style.** As of this writing, `nix flake init` scaffolds a hand-written Qt plugin (`*_interface.h` + `*_plugin.h` + `*_plugin.cpp`). This tutorial uses the newer and simpler **pure-C++ pattern** instead: you write one plain `*_impl.h` / `*_impl.cpp` class with no Qt in it, set `"interface": "universal"` in `metadata.json`, and the build generates the Qt plugin wrapper for you. So in the steps below we **replace** the template's `src/` files entirely. We still use `nix flake init` to get the `flake.nix` / `CMakeLists.txt` skeleton and directory layout.

> **Note:** The generated `flake.nix` uses an unpinned `logos-module-builder` URL. Replace it with the pinned version shown in the flake.nix step below to ensure reproducible builds.

> **Alternative approach:** You can also create the C library as a separate project, build it there, then copy the resulting `.so`/`.dylib` and header files into the module's `lib/` directory. This can be cleaner for larger libraries with their own build systems.

### 1.2 Remove the template's example sources

The `with-external-lib` template ships an example Qt plugin (`external_lib_*`). Delete those files — this tutorial supplies its own pure-C++ `src/` files:

```bash
rm -f src/external_lib_interface.h src/external_lib_plugin.h src/external_lib_plugin.cpp
```

---

## Step 2: Write the C Library

Create the C library that your module will wrap. Place the header and implementation in the `lib/` directory.

### 2.1 Create the lib directory

```bash
mkdir -p lib
```

### 2.2 Write the C header

Create `lib/libcalc.h`:

```c
#ifndef LIBCALC_H
#define LIBCALC_H

#ifdef __cplusplus
extern "C" {
#endif

/** Add two integers. */
int calc_add(int a, int b);

/** Multiply two integers. */
int calc_multiply(int a, int b);

/** Compute factorial of n (n must be >= 0). Returns -1 on error. */
int calc_factorial(int n);

/** Compute the nth Fibonacci number (n must be >= 0). Returns -1 on error. */
int calc_fibonacci(int n);

/** Return the library version string. Caller must NOT free. */
const char* calc_version(void);

#ifdef __cplusplus
}
#endif

#endif /* LIBCALC_H */
```

The `extern "C"` block is essential — it prevents C++ name mangling so the Logos module can find the symbols.

### 2.3 Write the C implementation

Create `lib/libcalc.c`:

```c
#include "libcalc.h"

int calc_add(int a, int b)
{
    return a + b;
}

int calc_multiply(int a, int b)
{
    return a * b;
}

int calc_factorial(int n)
{
    if (n < 0) return -1;
    if (n <= 1) return 1;
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int calc_fibonacci(int n)
{
    if (n < 0) return -1;
    if (n == 0) return 0;
    if (n == 1) return 1;
    int a = 0, b = 1;
    for (int i = 2; i <= n; i++) {
        int tmp = a + b;
        a = b;
        b = tmp;
    }
    return b;
}

const char* calc_version(void)
{
    return "1.0.0";
}
```

### 2.4 Build the shared library

```bash
cd lib

# Linux
gcc -shared -fPIC -o libcalc.so libcalc.c

# macOS
# gcc -shared -fPIC -o libcalc.dylib libcalc.c

cd ..
```

Verify the symbols are exported:

```bash
# Linux
nm -D lib/libcalc.so | grep calc

# macOS
# nm -gU lib/libcalc.dylib | grep calc
```

You should see each symbol marked with `T` (text/code section). Addresses will vary:

```
0000000000001139 T calc_add
0000000000001179 T calc_factorial
00000000000011f5 T calc_fibonacci
0000000000001159 T calc_multiply
0000000000001299 T calc_version
```

> **Wrapping a third-party library?** If you're wrapping an existing library (e.g., from a system package or a GitHub repo), you don't need to write the C code — just place the pre-built `.so`/`.dylib` and its header file in `lib/`.

---

## Step 3: Configure the Logos Module

Now write the files that turn your C library into a Logos module. With the **pure-C++ (`universal`) pattern** you only hand-write a single C++ class — `metadata.json`, `CMakeLists.txt`, and `flake.nix` tell the build system the rest, and `logos-cpp-generator` synthesizes the Qt plugin wrapper.

After this step your project will look like this:

| File                          | Role                                                              |
| ----------------------------- | ----------------------------------------------------------------- |
| `metadata.json`               | Module metadata + nix build settings (note `interface: universal`)|
| `CMakeLists.txt`              | Lists your impl source files                                      |
| `flake.nix`                   | Nix build (description, dependency inputs)                        |
| `src/calc_module_impl.h`      | Plain C++ class declaration — **no Qt**                           |
| `src/calc_module_impl.cpp`    | Implementation: each method calls the C library                   |

```
logos-calc-module/
├── flake.nix          # Nix build configuration (~10 lines)
├── metadata.json      # Module metadata, build settings, and runtime config
├── CMakeLists.txt     # CMake build file
├── lib/
│   ├── libcalc.h      # C library header
│   └── libcalc.c      # C library source (compiled by CMake)
└── src/
    ├── calc_module_impl.h     # Plain C++ class (no Qt, no plugin macros)
    └── calc_module_impl.cpp   # Implementation (wrapping logic)
```

> **Where did the `*_interface.h` / `*_plugin.h` / `*_plugin.cpp` files go?** The older pattern made you hand-write a Qt `QObject` plugin, an abstract interface, and the `Q_INVOKABLE` / `Q_PLUGIN_METADATA` boilerplate. With `interface: universal`, the generator derives all of that from your plain class — so those three files no longer exist in your source tree. They are emitted into `generated_code/` at build time.

### 3.1 `metadata.json` — Module Configuration

> **Edit:** Set `name`, `description`, `main`, add `"interface": "universal"`, and declare your library under `nix.external_libraries`.

This is the single source of truth for your module. It is embedded into the generated plugin binary (for runtime metadata via `lm`), read by `logos-module-builder` to configure the Nix build, used by CMake to resolve and link external libraries (via the `nix` section), and used by `nix-bundle-lgx` to generate the LGX manifest.

```json
{
  "name": "calc_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Calculator module wrapping libcalc C library",
  "main": "calc_module_plugin",
  "interface": "universal",
  "dependencies": [],

  "nix": {
    "packages": {
      "build": [],
      "runtime": []
    },
    "external_libraries": [
      {
        "name": "calc",
        "vendor_path": "lib"
      }
    ],
    "cmake": {
      "find_packages": [],
      "extra_sources": [],
      "extra_include_dirs": ["lib"],
      "extra_link_libraries": []
    }
  }
}
```

**Key fields explained:**

| Field                          | What it does                                                                                                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `name`                         | Module name — must be a valid C identifier (used in filenames, method calls)                                                                                                                                       |
| `main`                         | The generated plugin's name, `<name>_plugin`. You don't write this file; the builder produces `calc_module_plugin.so` / `.dylib`                                                                                   |
| `interface`                    | `"universal"` selects the pure-C++ pattern. The builder runs `logos-cpp-generator --from-header` over `src/calc_module_impl.h` and emits the Qt plugin glue, so you never touch Qt directly                        |
| `nix.external_libraries`       | Declares C/C++ libraries vendored in the repo. Each entry has a `name` (the CMake target) and `vendor_path` (directory with the source/binary). The build compiles the library and links it into the plugin        |
| `nix.cmake.extra_include_dirs` | Added to the include path so your C++ code can `#include "lib/libcalc.h"`                                                                                                                                          |

### 3.2 `CMakeLists.txt` — Build File

> **Edit:** Set `project()` name, `NAME`, the `SOURCES` (your two impl files), and `EXTERNAL_LIBS`.

For a universal module you list only your plain C++ source files. The generated glue (`generated_code/*.cpp`) is picked up automatically by `LogosModule.cmake` — you don't reference it here.

```cmake
cmake_minimum_required(VERSION 3.14)
project(CalcModulePlugin LANGUAGES CXX)

# Include the Logos Module CMake helper (provided by logos-module-builder)
if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

# Define the module with its external library dependency.
# Because metadata.json sets `interface: universal`, the builder runs
# logos-cpp-generator over src/calc_module_impl.h before configuring,
# and LogosModule.cmake compiles the generated glue automatically.
logos_module(
    NAME calc_module
    SOURCES
        src/calc_module_impl.h
        src/calc_module_impl.cpp
    EXTERNAL_LIBS
        calc
)
```

You **must** keep these in sync with `metadata.json`:

- **`NAME`** — your module name (must match `name` in `metadata.json`, e.g., `calc_module`)
- **`SOURCES`** — your impl files (`src/calc_module_impl.h`, `src/calc_module_impl.cpp`)
- **`EXTERNAL_LIBS`** — external libraries to link (must match `nix.external_libraries[].name` in `metadata.json`)

The `if/elseif/else` block above it is boilerplate — don't change it.

> **Common mistake:** If `NAME` doesn't match `name` in `metadata.json`, the build may succeed but the install phase fails because it looks for `<name>_plugin.so`/`.dylib` based on `metadata.json`.

**How `EXTERNAL_LIBS calc` works:** `logos_module()` searches `lib/` for `libcalc.so` (Linux) / `libcalc.dylib` (macOS), links it to your plugin, and sets up RPATH so the library is found at runtime.

### 3.3 `flake.nix` — Nix Build Config

Change `description`. Add flake inputs here if your module depends on other modules or fetches a library from source.

```nix
{
  description = "Calculator module - wraps libcalc C library for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

That's it — `mkLogosModule` handles all the Nix complexity (fetching Qt, the SDK, the code generator, running `logos-cpp-generator --from-header`, setting up include paths, etc.). `configFile` points to `metadata.json` (the single source of truth) and `flakeInputs = inputs` passes all flake inputs to the builder so that dependencies declared in `metadata.json` are resolved automatically.

> **Naming flake inputs:** When adding module dependencies, the flake input attribute name **must match** the `name` field in that dependency's `metadata.json`. For example, if you depend on a module whose `metadata.json` has `"name": "waku_module"`, your flake input must be `waku_module.url = "github:logos-co/logos-waku-module"`.

### 3.4 `src/calc_module_impl.h` — The Module Class

This is the **only interface you write**, and it's plain C++ — no `QObject`, no `Q_INVOKABLE`, no plugin macros, no Qt headers at all. Every `public` method becomes a method other modules (and `logoscore`) can call. The code generator parses this header as text to derive the wire signatures, so keep it to the supported types (see the table below).

We also inherit `LogosModuleContext` so the class can emit events (the `logos_events:` block) and, if needed later, call other modules — without ever touching the raw `LogosAPI`.

```cpp
#pragma once

#include <cstdint>
#include <string>

#include <logos_module_context.h>  // LogosModuleContext base + `logos_events:`

// Include the C library header (extern "C" already in the header).
extern "C" {
    #include "lib/libcalc.h"
}

class CalcModuleImpl : public LogosModuleContext {
public:
    CalcModuleImpl() = default;
    ~CalcModuleImpl() = default;

    // ── Public API — every method here is callable over IPC ──────────
    // The generator maps C++ types onto the wire automatically:
    //   int64_t  ↔ int      std::string ↔ QString      bool ↔ bool
    //
    // A doc comment directly above a method becomes that method's
    // `description` in the module's method introspection — surfaced
    // by `lm`, `logoscore module-info`, and Basecamp's Methods list.
    // Use `///` (one or more lines) or a `/** ... */` block; the
    // comment's line breaks are preserved. (Plain `//` comments like
    // this block are ignored, so they never leak into the API.)

    /// Adds two integers and returns the sum.
    int64_t add(int64_t a, int64_t b);

    /// Multiplies two integers and returns the product.
    int64_t multiply(int64_t a, int64_t b);

    // A multi-line description: consecutive `///` lines keep their breaks.
    /// Computes the factorial n! of a non-negative integer.
    /// Defined as n * (n-1) * ... * 1, with 0! = 1.
    int64_t factorial(int64_t n);

    /// Returns the nth Fibonacci number (0-indexed).
    int64_t fibonacci(int64_t n);

    // A `/** ... */` block comment works too (line breaks preserved).
    /**
     * Returns the version string of the wrapped libcalc C library.
     * Read straight from the linked native library, not metadata.json.
     */
    std::string libVersion();

    /// Looks up the library version and emits it as a `versionReady`
    /// event instead of returning it. Used by the QML tutorial (Part 2).
    void libVersionNotify();

    // ── Events ───────────────────────────────────────────────────────
    // Declared like Qt signals. The generator emits the body (in
    // calc_module_events.cpp) that routes the typed args to subscribers
    // via the host's `eventResponse` mechanism. QML subscribes with
    // logos.onModuleEvent("calc_module", "versionReady").
    //
    // A `///` doc comment documents the event too — it surfaces as the
    // event's `description` alongside methods (`lm events`, `logoscore
    // module-info`, and Basecamp's Interface screen).
logos_events:
    /// Emitted by libVersionNotify() once the library version is known.
    /// Carries the version string read from libcalc.
    void versionReady(const std::string& version);
};
```

**Rules for the impl class:**

- It's a normal C++ class. Any `public` method is exposed; `private` members and helpers are not.
- **Supported parameter/return types** (what the generator can translate):

  | C++ type                    | On the wire (Qt)   |
  | --------------------------- | ------------------ |
  | `void`                      | `void`             |
  | `bool`                      | `bool`             |
  | `int64_t`                   | `int`              |
  | `uint64_t`                  | `uint`             |
  | `double`                    | `double`           |
  | `std::string`               | `QString`          |
  | `std::vector<std::string>`  | `QStringList`      |
  | `std::vector<uint8_t>`      | `QByteArray`       |
  | `LogosMap` / `LogosList`    | `QVariantMap` / `QVariantList` (from `<logos_json.h>`) |
  | `StdLogosResult`            | `LogosResult` (from `<logos_result.h>`) — `{ success, value, error }` |

- Use `int64_t` for integers (not `int`) — that's the type the parser recognizes.
- **Document methods with `///`.** A doc comment (`///` or `/** … */`) directly above a method becomes its `description` in the module's introspection, surfaced by `lm`, `logoscore module-info`, and Basecamp. Plain `//` comments are ignored, so only intentional docs are exposed — you'll see this in action in Step 5.
- Events are declared in a `logos_events:` section. The token is recognized by the generator before preprocessing; under a normal compile it just expands to `public`.

### 3.5 `src/calc_module_impl.cpp` — Implementation

Each method calls the corresponding C function and converts the result. No Qt types appear anywhere — you work in plain C++ and the generated glue handles the wire conversion.

```cpp
#include "calc_module_impl.h"

int64_t CalcModuleImpl::add(int64_t a, int64_t b)
{
    return calc_add(static_cast<int>(a), static_cast<int>(b));
}

int64_t CalcModuleImpl::multiply(int64_t a, int64_t b)
{
    return calc_multiply(static_cast<int>(a), static_cast<int>(b));
}

int64_t CalcModuleImpl::factorial(int64_t n)
{
    return calc_factorial(static_cast<int>(n));
}

int64_t CalcModuleImpl::fibonacci(int64_t n)
{
    return calc_fibonacci(static_cast<int>(n));
}

std::string CalcModuleImpl::libVersion()
{
    return std::string(calc_version());
}

void CalcModuleImpl::libVersionNotify()
{
    // Emit the event declared in `logos_events:`. When the module is
    // loaded by a host, this reaches every subscriber. When the class
    // is constructed outside a host (e.g. in unit tests), it is a
    // safe no-op.
    versionReady(std::string(calc_version()));
}
```

**The wrapping pattern** is always the same:

1. Call the C function (convert `int64_t` → `int` for libcalc's `int` API)
2. Convert the C result to a C++ type if needed (e.g., `const char*` → `std::string`)
3. Return it — the generated glue marshals it onto the wire

Notice what you **didn't** write: no `initLogos`, no `Q_INVOKABLE`, no `name()`/`version()` (read from `metadata.json`), no signal declaration. The generator produces all of it from the header.

---

## Step 4: Build the Module

### 4.1 Initialize the Git repo

Nix flakes require a git repository.

Before staging files, create a `.gitignore` to exclude build artifacts:

```text
# Nix build output
result
result-*

# CMake build directory
build/
```

Then initialise the repo:

```bash
git init
```

```bash
git add -A
```

```bash
nix flake update
```

```bash
git add flake.lock
```

### 4.2 Build the plugin library

Build just the plugin library (`.so` / `.dylib`):

```bash
nix build '.#lib'
```

> **Quoting matters:** Use `'.#lib'` (with quotes) rather than bare `nix build .#lib`. Some shells (especially zsh) may interpret the `#` as a comment character.

The first build takes a while (5–15 minutes) as Nix downloads Qt, the Logos SDK, and other dependencies. Subsequent builds are fast due to caching.

### 4.3 Build the full package

Build everything (library + generated SDK headers). For a `universal` module this is also where `logos-cpp-generator --from-header` runs over `src/calc_module_impl.h` to produce the Qt plugin glue under `generated_code/` before CMake compiles it:

```bash
nix build
```

### 4.4 Inspect the output

```bash
ls -la result/lib/
```

You should see two files (extensions depend on your platform):

```
# Linux
calc_module_plugin.so   # Your Logos module plugin
libcalc.so              # The C library (copied alongside)

# macOS
calc_module_plugin.dylib
libcalc.dylib
```

Both library files are placed together so the plugin can find the C library at runtime via RPATH.

---

## Step 5: Inspect the Module

Use the `lm` CLI tool (from `logos-module`) to inspect the compiled module binary.

### 5.1 Build the `lm` tool

The `lm` CLI inspects compiled module binaries. Build it from the `logos-module` repo:

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

### 5.2 View metadata

```bash
# Linux
./lm/bin/lm metadata result/lib/calc_module_plugin.so

# macOS
./lm/bin/lm metadata result/lib/calc_module_plugin.dylib
```

Output:

```
Plugin Metadata:
================
Name:         calc_module
Version:      1.0.0
Description:  Calculator module wrapping libcalc C library
Author:
Type:         core
Dependencies: (none)
```

### 5.3 List methods

```bash
# Linux
./lm/bin/lm methods result/lib/calc_module_plugin.so

# macOS
./lm/bin/lm methods result/lib/calc_module_plugin.dylib
```

Output — each method you declared, with its doc comment as a
`Description`. A single-line comment renders inline; a multi-line
comment (`factorial`'s two `///` lines, `libVersion`'s `/** ... */`
block, and `libVersionNotify`'s two `///` lines) keeps its line breaks:

```
Plugin Methods:
===============

int add(int a, int b)
  Signature: add(int,int)
  Invokable: yes
  Description: Adds two integers and returns the sum.

int multiply(int a, int b)
  Signature: multiply(int,int)
  Invokable: yes
  Description: Multiplies two integers and returns the product.

int factorial(int n)
  Signature: factorial(int)
  Invokable: yes
  Description:
    Computes the factorial n! of a non-negative integer.
    Defined as n * (n-1) * ... * 1, with 0! = 1.

int fibonacci(int n)
  Signature: fibonacci(int)
  Invokable: yes
  Description: Returns the nth Fibonacci number (0-indexed).

QString libVersion()
  Signature: libVersion()
  Invokable: yes
  Description:
    Returns the version string of the wrapped libcalc C library.
    Read straight from the linked native library, not metadata.json.

void libVersionNotify()
  Signature: libVersionNotify()
  Invokable: yes
  Description:
    Looks up the library version and emits it as a `versionReady`
    event instead of returning it. Used by the QML tutorial (Part 2).
```

Three things to notice:

- **Signatures are Qt-typed** (`int`, `QString`) even though you wrote `int64_t` / `std::string`. That's the generated glue: `lm` reports the wire types the synthesized Qt plugin exposes, so `int64_t add(int64_t, int64_t)` shows up as `add(int,int)`.
- **Each `Description` is your doc comment**, carried through the module's method introspection. Plain `//` comments (like the type-mapping note in the header) are deliberately ignored, so only intentional docs surface; an undocumented method simply omits it.
- **Line breaks are preserved** — a single-line comment renders inline; a multi-line comment (`factorial`, `libVersion`, `libVersionNotify`) keeps its breaks. The same descriptions appear in `logoscore module-info` and Basecamp's Methods list.

### 5.4 JSON output

For scripting and CI, use `--json`:

```bash
# Linux
./lm/bin/lm methods result/lib/calc_module_plugin.so --json

# macOS
./lm/bin/lm methods result/lib/calc_module_plugin.dylib --json
```

```json
[
    {
        "description": "Adds two integers and returns the sum.",
        "isInvokable": true,
        "name": "add",
        "parameters": [
            { "name": "a", "type": "int" },
            { "name": "b", "type": "int" }
        ],
        "returnType": "int",
        "signature": "add(int,int)"
    },
    ...
]
```

The `description` field is the method's doc comment. A multi-line
comment is carried verbatim with embedded `\n` (e.g. `factorial`:
`"Computes the factorial n! of a non-negative integer.\nDefined as
n * (n-1) * ... * 1, with 0! = 1."`). Methods without a doc comment
omit the field.

### 5.5 List events

Events (your `logos_events:` block) are part of the module's API too, and
are introspectable the same way — `lm events` lists each event with its
signature and `///` description:

```bash
# Linux
./lm/bin/lm events result/lib/calc_module_plugin.so

# macOS
./lm/bin/lm events result/lib/calc_module_plugin.dylib
```

```
Plugin Events:
==============

void versionReady(QString version)
  Signature: versionReady(QString)
  Description:
    Emitted by libVersionNotify() once the library version is known.
    Carries the version string read from libcalc.
```

Events have no return type (they're fire-and-forget). Running `lm`
with no subcommand prints metadata, methods, **and** events together.
The same event docs appear in `logoscore module-info` and Basecamp's
Interface screen.

---

## Step 6: Test with `logoscore`

### 6.1 Build logoscore

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

### 6.2 Set up the modules directory

`logoscore` expects modules in subdirectories, each with a `manifest.json`. Rather than copying files and writing the manifest manually, use the Nix derivation to create an LGX package and install it with the package manager:

```bash
nix build '.#lgx'
```

```bash
nix build 'github:logos-co/logos-package-manager#cli' --out-link ./pm
```

```bash
mkdir -p modules
```

```bash
./pm/bin/lgpm --modules-dir ./modules install --file result/*.lgx
```

This extracts the plugin, external libraries, and manifest into the correct directory structure:

```
modules/calc_module/
├── calc_module_plugin.dylib   # (or .so on Linux)
├── libcalc.dylib              # (or .so on Linux)
├── manifest.json              # Auto-generated by lgx
└── variant                    # Platform variant identifier
```

### 6.3 Start the daemon and load the module

Start the daemon and load `calc_module`:

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
sleep 3
```

```bash
./logos/bin/logoscore load-module calc_module
```

### 6.4 Inspect methods and events

`module-info` lists each method **and event** with its signature and the doc-comment description you wrote — the same docs `lm` showed, here straight from the module's introspection:

```bash
./logos/bin/logoscore module-info calc_module
```

```
Name:          calc_module
Version:       v1.0.0
Status:        loaded
PID:           48213
Uptime:        3s

Methods:
  add(a: int, b: int) -> int
      Adds two integers and returns the sum.
  multiply(a: int, b: int) -> int
      Multiplies two integers and returns the product.
  factorial(n: int) -> int
      Computes the factorial n! of a non-negative integer.
      Defined as n * (n-1) * ... * 1, with 0! = 1.
  fibonacci(n: int) -> int
      Returns the nth Fibonacci number (0-indexed).
  libVersion() -> QString
      Returns the version string of the wrapped libcalc C library.
      Read straight from the linked native library, not metadata.json.
  libVersionNotify() -> void
      Looks up the library version and emits it as a `versionReady`
      event instead of returning it. Used by the QML tutorial (Part 2).

Events:
  versionReady(version: QString)
      Emitted by libVersionNotify() once the library version is known.
      Carries the version string read from libcalc.
```

Methods and events both show their doc comments (multi-line ones keep
their line breaks). An undocumented method or event still appears, just
without the indented description.

### 6.5 Call methods

Now call them:

```bash
./logos/bin/logoscore call calc_module add 3 5
```

```bash
./logos/bin/logoscore call calc_module factorial 5
```

```bash
./logos/bin/logoscore call calc_module fibonacci 10
```

```bash
./logos/bin/logoscore call calc_module libVersion
```

```bash
./logos/bin/logoscore stop
```

> For the full daemon/client workflow and other logoscore options, see the [Developer Guide -- Running with logoscore](logos-developer-guide.md#61-running-with-logoscore).

**What happens under the hood:**

1. `logoscore` scans `./modules/` for subdirectories containing `manifest.json`
2. It finds `calc_module` and extracts metadata from the plugin binary
3. It spawns a `logos_host` process that loads `calc_module_plugin.so` (the generated wrapper around your impl class)
4. `logos_host` calls `initLogos()` on the generated plugin, providing a `LogosAPI*` for inter-module communication
5. The call command is parsed: module name `calc_module`, method `add`, args `[3, 5]`
6. `logoscore` sends the call to `logos_host` via Qt Remote Objects (IPC)
7. The generated glue converts the args and invokes `CalcModuleImpl::add(3, 5)`, which calls `calc_add(3, 5)` from libcalc
8. The result is returned via IPC to `logoscore`

You'll see debug output like:

```
Debug: Found plugin: "./modules/calc_module/calc_module_plugin.so"
Debug: Plugin Metadata:
Debug:  - Name: "calc_module"
Debug:  - Version: "1.0.0"
Debug:  - Description: "Calculator module wrapping libcalc C library"
Debug: Loading plugin: "calc_module" in separate process
Debug: Executing call: "calc_module" . "add" with 2 params
Method call successful. Result: ...
```

---

## Step 7: Unit-test the Module

Because your module is a plain C++ class, you can unit-test it **directly** — no Qt, no running host, no IPC. The [Logos Test Framework](https://github.com/logos-co/logos-test-framework) adds two things on top of that: a tiny test runner (`LOGOS_TEST` / `LOGOS_ASSERT_*`) and **link-time mocking of your C library**, so each test can make `calc_add`, `calc_factorial`, … return whatever it wants and assert how your wrapper behaves.

You wire it up by pointing `mkLogosModule` at a `tests/` directory in `flake.nix`, then writing the test files. `nix build .#unit-tests` builds and runs them.

### 7.1 Enable tests in `flake.nix`

Add a `tests` block to the `mkLogosModule` call. `mockCLibs` lists the external libraries to replace with link-time mocks (so tests don't need the real `libcalc`):

```nix
{
  description = "Calculator module - wraps libcalc C library for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
      tests = {
        dir = ./tests;
        mockCLibs = [ "calc" ];
      };
    };
}
```

### 7.2 `tests/CMakeLists.txt` — wire up the test binary

The test harness configures and builds `tests/` as its own CMake project, so it needs a `tests/CMakeLists.txt`. It includes `LogosTest` (provided by the framework) and calls `logos_test()`, listing your impl source, the test sources, and the C-library mock:

```cmake
cmake_minimum_required(VERSION 3.14)
project(CalcModuleTests LANGUAGES CXX)

include(LogosTest)

logos_test(
    NAME calc_module_tests
    MODULE_SOURCES
        ../src/calc_module_impl.cpp
        mocks/calc_module_events_stub.cpp
    TEST_SOURCES
        main.cpp
        test_calc.cpp
    MOCK_C_SOURCES
        mocks/mock_libcalc.cpp
)
```

- **`MODULE_SOURCES`** — your impl `.cpp` (compiled into the test binary, not the real plugin), plus the events stub explained below
- **`TEST_SOURCES`** — the runner entry point plus your `test_*.cpp` files
- **`MOCK_C_SOURCES`** — the link-time replacement for libcalc, so the real library is never linked

`logos_test()` automatically puts the repo root and `../src` on the include path, so `#include "calc_module_impl.h"` and `#include "lib/libcalc.h"` both resolve.

### 7.3 `tests/mocks/calc_module_events_stub.cpp` — stub the event method

In a normal build, `logos-cpp-generator` emits `calc_module_events.cpp` containing the body of every `logos_events:` method (e.g. `versionReady`). The test harness runs the generator in a reduced mode that does **not** emit that file, so `libVersionNotify()` — which calls `versionReady(...)` — would fail to link. Provide a tiny no-op stub for unit tests:

```cpp
// Stub bodies for the impl's `logos_events:` methods.
// In the real build the codegen generates calc_module_events.cpp with
// bodies that route through LogosModuleContext. The test build skips
// that codegen, so we provide no-op stubs to satisfy the linker.
#include "calc_module_impl.h"

void CalcModuleImpl::versionReady(const std::string&) {}
```

If you add more events to `logos_events:`, add a matching no-op line here. (A module with no events doesn't need this stub at all.)

### 7.4 Test runner entry point

Create `tests/main.cpp` — one line pulls in the framework's `main()`:

```cpp
#include <logos_test.h>

LOGOS_TEST_MAIN()
```

### 7.5 Mock the C library

When building tests, the real `libcalc` is **not** linked. Instead you provide functions with the same signatures backed by the framework's mock store. Each one records that it was called and returns a value the test set up. Create `tests/mocks/mock_libcalc.cpp`:

```cpp
// Link-time replacement for libcalc. Each function records the call
// and returns whatever the active test configured via mockCFunction().
#include <logos_clib_mock.h>

extern "C" {
    #include "lib/libcalc.h"
}

extern "C" int calc_add(int a, int b) {
    LOGOS_CMOCK_RECORD("calc_add");
    return LOGOS_CMOCK_RETURN(int, "calc_add");
}

extern "C" int calc_multiply(int a, int b) {
    LOGOS_CMOCK_RECORD("calc_multiply");
    return LOGOS_CMOCK_RETURN(int, "calc_multiply");
}

extern "C" int calc_factorial(int n) {
    LOGOS_CMOCK_RECORD("calc_factorial");
    return LOGOS_CMOCK_RETURN(int, "calc_factorial");
}

extern "C" int calc_fibonacci(int n) {
    LOGOS_CMOCK_RECORD("calc_fibonacci");
    return LOGOS_CMOCK_RETURN(int, "calc_fibonacci");
}

extern "C" const char* calc_version(void) {
    LOGOS_CMOCK_RECORD("calc_version");
    return LOGOS_CMOCK_RETURN_STRING("calc_version");
}
```

`LOGOS_CMOCK_RECORD(name)` logs the call; `LOGOS_CMOCK_RETURN(type, name)` / `LOGOS_CMOCK_RETURN_STRING(name)` hand back the value the test set with `mockCFunction(...).returns(...)`.

### 7.6 Write the tests

Create `tests/test_calc.cpp`. Each `LOGOS_TEST` constructs your impl directly, configures the C-function return values, calls a method, and asserts. `LogosTestContext` resets the mock store between tests:

```cpp
#include <logos_test.h>
#include "calc_module_impl.h"

LOGOS_TEST(add_forwards_to_calc_add) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_add").returns(8);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.add(3, 5), 8);
    LOGOS_ASSERT(t.cFunctionCalled("calc_add"));
}

LOGOS_TEST(multiply_forwards_to_calc_multiply) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_multiply").returns(42);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.multiply(6, 7), 42);
    LOGOS_ASSERT(t.cFunctionCalled("calc_multiply"));
}

LOGOS_TEST(factorial_returns_mocked_value) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_factorial").returns(120);

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.factorial(5), 120);
}

LOGOS_TEST(libVersion_converts_cstring_to_string) {
    auto t = LogosTestContext("calc_module");
    t.mockCFunction("calc_version").returns("1.0.0");

    CalcModuleImpl calc;
    LOGOS_ASSERT_EQ(calc.libVersion(), std::string("1.0.0"));
}
```

A few things worth calling out:

- The tests construct `CalcModuleImpl` like any class — no Qt, no host, no `initLogos`. That's the payoff of the pure-C++ pattern.
- `libVersionNotify()` is safe to call here too: its `versionReady(...)` event resolves to the no-op stub you added, so it won't crash and simply does nothing in the test process.
- `LOGOS_ASSERT_EQ`, `LOGOS_ASSERT`, `LOGOS_ASSERT_TRUE/FALSE`, `LOGOS_ASSERT_NE/GT/GE/LT` are all available from `<logos_test.h>`.

### 7.7 Run the tests

Track the new files (nix only sees git-tracked files), then build and run:

```bash
git add tests/ flake.nix
```

```bash
nix build '.#unit-tests' -L
```

The build compiles your impl (`src/calc_module_impl.cpp`) against the mock library and the test sources, then runs every `LOGOS_TEST`. A passing run ends with a summary line; a failed assertion prints the file/line and fails the build.

> **From the workspace?** You can also run `ws test logos-calc-module` (after `ws sync-graph` picks up the new tests). See the workspace `CLAUDE.md`.

---

## Package for Distribution (Optional)

The LGX package created in Step 5.2 is a **local** package — its libraries still reference `/nix/store` paths, so it only works on the machine that built it. To create a **portable** package that can be distributed to other machines:

```bash
nix build '.#lgx-portable'
```

Portable LGX packages are fully self-contained with no `/nix/store` references at runtime. These are the packages used by the Logos App Package Manager UI and published to [logos-modules](https://github.com/logos-co/logos-modules) releases.

To create both dev and portable variants (the dev variant works with local `nix build` of basecamp; the portable variant works with standalone basecamp builds), use `--out-link` to avoid overwriting the `result` symlink:

```bash
nix build '.#lgx' --out-link result-lgx
nix build '.#lgx-portable' --out-link result-lgx-portable
```

> For more bundling options (standalone bundler syntax, cross-platform packaging), see the [Developer Guide — Bundling with nix-bundle-lgx](logos-developer-guide.md#32-bundling-with-nix-bundle-lgx).

To install a portable package on another machine:

```bash
nix build 'github:logos-co/logos-package-manager#cli' --out-link ./pm
./pm/bin/lgpm --modules-dir ./modules install --file result-lgx-portable/*.lgx
```

> **Note:** Local builds of `logoscore` / `logos-basecamp` (via `nix build`) expect **local** `.lgx` packages. Portable builds (via `nix build '.#bin-bundle-dir'`, `.#bin-appimage`, or `.#bin-macos-app`) expect **portable** `.lgx` packages. See the [logos-basecamp README](https://github.com/logos-co/logos-basecamp/blob/master/README.md) for details.

## Common Wrapping Patterns

All of these are plain C++ — the impl class holds whatever state it needs as private members, and methods use std types. No Qt appears anywhere.

### Wrapping C functions with opaque pointers

Many C libraries use opaque pointers (handles) for state management:

```c
// C API
typedef struct db_ctx db_ctx_t;
db_ctx_t* db_open(const char* path);
int db_get(db_ctx_t* ctx, const char* key, char* buf, int buf_len);
void db_close(db_ctx_t* ctx);
```

Store the handle as a private member of your impl class:

```cpp
class DbModuleImpl : public LogosModuleContext
{
public:
    bool open(const std::string& path) {
        m_ctx = db_open(path.c_str());
        return m_ctx != nullptr;
    }

    std::string get(const std::string& key) {
        if (!m_ctx) return {};
        char buf[4096];
        int len = db_get(m_ctx, key.c_str(), buf, sizeof(buf));
        if (len < 0) return {};
        return std::string(buf, len);
    }

    ~DbModuleImpl() { if (m_ctx) db_close(m_ctx); }

private:
    db_ctx_t* m_ctx = nullptr;   // private — not exposed over IPC
};
```

### Wrapping C callbacks → events

C libraries often use callbacks for async operations:

```c
typedef void (*event_cb)(int code, const char* msg, void* user_data);
void lib_set_callback(void* ctx, event_cb cb, void* user_data);
```

Use a static function as the callback, passing `this` as `user_data`, and forward into a declared event:

```cpp
class MyImpl : public LogosModuleContext
{
public:
    void startListening() {
        lib_set_callback(m_ctx, &MyImpl::c_callback, this);
    }

logos_events:
    void libEvent(int64_t code, const std::string& message);

private:
    static void c_callback(int code, const char* msg, void* user_data) {
        auto* self = static_cast<MyImpl*>(user_data);
        self->libEvent(code, std::string(msg ? msg : ""));
    }
    void* m_ctx = nullptr;
};
```

Calling the declared event (`libEvent(...)`) routes the typed args to subscribers — you never touch Qt signals or `QVariantList` yourself.

### Wrapping C libraries that allocate strings

If the C library returns allocated strings that must be freed:

```cpp
std::string getData() {
    char* c_str = lib_get_data(m_ctx);   // Library allocates
    std::string result = c_str ? c_str : "";
    lib_free_string(c_str);              // Library deallocates
    return result;
}
```

### Type conversion reference (C ↔ impl class)

In the impl class you work entirely in std/C++ types — the generated glue handles the Qt/wire side. These are the conversions you write between the C library and your method signatures:

| C type                 | Impl type                  | C → impl                  | impl → C                   |
| ---------------------- | -------------------------- | ------------------------- | -------------------------- |
| `const char*`          | `std::string`              | `std::string(c_str)`      | `s.c_str()`                |
| `const char*` (binary) | `std::vector<uint8_t>`     | `{data, data + len}`      | `v.data()`, `v.size()`     |
| `int`                  | `int64_t`                  | direct (widen)            | `static_cast<int>(n)`      |
| `bool` / `int`         | `bool`                     | `result != 0`             | direct                     |
| `void*`                | (store as private member)  | —                         | —                          |

> Use `int64_t` (not `int`) in the public signatures — that's the integer type the generator recognizes. Narrow to the C library's `int` inside the method, as the calc example does.

## Advanced: Wrapping a Library from a Flake Input

Instead of pre-building the library and placing it in `lib/`, you can have Nix fetch and build it from source. This is useful for libraries hosted on GitHub.

### flake.nix with external library input

```nix
{
  description = "Module wrapping libfoo from GitHub";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # Fetch the library source (non-flake)
    libfoo-src = {
      url = "github:example/libfoo";
      flake = false;
    };
  };

  outputs = inputs@{ logos-module-builder, libfoo-src, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;

      # Pass the fetched source to the builder
      externalLibInputs = {
        foo = libfoo-src;
      };
    };
}
```

### metadata.json for flake input

```json
{
  "name": "foo_module",
  "version": "1.0.0",
  "type": "core",
  "description": "Module wrapping libfoo",
  "main": "foo_module_plugin",
  "interface": "universal",
  "dependencies": [],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [
      {
        "name": "foo",
        "flake_input": "github:example/libfoo",
        "build_command": "make shared",
        "output_pattern": "build/libfoo.*"
      }
    ],
    "cmake": {
      "find_packages": [],
      "extra_sources": [],
      "extra_include_dirs": ["lib"],
      "extra_link_libraries": []
    }
  }
}
```

**Key difference:** The `externalLibInputs` key in flake.nix (`foo`) must match the `name` field in `nix.external_libraries` (`foo`). The builder will:

1. Clone the source from the flake input
2. Run `build_command` (`make shared`)
3. Search for output files matching `output_pattern`
4. Copy the resulting `.so`/`.dylib` and headers to `lib/`
5. Proceed with the normal module build

### For Go libraries

If the external library is written in Go with C bindings (`cgo`), set `go_build: true` in the `nix.external_libraries` entry within `metadata.json`:

```json
{
  "nix": {
    "external_libraries": [
      {
        "name": "mygolib",
        "flake_input": "github:example/mygolib",
        "go_build": true,
        "output_pattern": "libmygolib.*"
      }
    ]
  }
}
```

Setting `go_build: true` enables the Go toolchain and sets `CGO_ENABLED=1`.

## Real-World Example: logos-libp2p-module

The [logos-libp2p-module](https://github.com/logos-co/logos-libp2p-module) is a production module that wraps the `nim-libp2p` library (compiled to a C shared library). Key files:

- `**flake.nix**` — Uses `externalLibInputs` to fetch the nim-libp2p C bindings from a GitHub flake
- `**metadata.json**` — Declares `nim_libp2p` as an external library with `go_build: false` in the `nix` section
- `**src/*_impl.cpp**` — Wraps ~40 C functions (`libp2p_new`, `libp2p_start`, `libp2p_connect`, `libp2p_dial`, `libp2p_gossipsub_subscribe`, etc.) as plain public methods
- `**tests/**` — test suite that exercises every wrapped function with the Logos Test Framework

It follows the exact same pattern as this tutorial, just at a larger scale.

## Troubleshooting

### A method doesn't show up in `lm` / can't be called

The generator only exposes `public` methods on the impl class whose parameter and return types it recognizes. If a method is missing:

1. Make sure it's in the `public:` section (not `private:`).
2. Use supported types only — notably `int64_t` (not `int`), `std::string` (not `char*` or `QString`), `std::vector<std::string>`, `bool`, `double`, `LogosMap`/`LogosList`, `StdLogosResult`. See the type table in [Step 3](#step-3-configure-the-logos-module).
3. Keep the signature on as few lines as the parser expects — one declaration per method.

### Build error: unknown type / generator can't parse a method

The `--from-header` parser reads your `*_impl.h` as text. Pulling Qt types or unusual templates into a *public method signature* will confuse it. Keep Qt out of the impl header entirely, and move any helper that needs exotic types into the `private:` section or the `.cpp`.

### Library not found at runtime

```
Cannot load library calc_module_plugin.so: libcalc.so: cannot open shared object file
```

**Fix:** Ensure `libcalc.so` / `libcalc.dylib` is in the same directory as the plugin. The build system sets RPATH to `$ORIGIN` (Linux) / `@loader_path` (macOS) so the plugin looks for libraries in its own directory.

### Events never reach subscribers

If you emit an event (e.g. `versionReady(...)`) but a QML view or another module never receives it:

1. The event must be declared in a `logos_events:` section of the impl header, and your class must inherit `LogosModuleContext`.
2. The event only fires when the module is loaded by a host (logoscore / basecamp). Constructed standalone (unit tests), emission is a safe no-op — that's expected.
3. The subscriber must use the exact event name string, e.g. `logos.onModuleEvent("calc_module", "versionReady")`.

### Plugin not discovered by logoscore

**Check:**

1. The module is in a **subdirectory** of the modules dir (e.g., `modules/calc_module/`)
2. The subdirectory contains a `manifest.json` with a valid `main` object
3. The platform key in `main` matches your OS/arch (e.g., `linux-aarch64`, `darwin-arm64`)

### `nix build .#lib` does nothing or fails silently

Some shells (notably zsh) treat `#` as a comment character. Always quote the flake reference:

```bash
# Correct
nix build '.#lib'

# May fail in zsh
nix build .#lib
```

### First build is slow

The first `nix build` downloads Qt 6, the Logos C++ SDK, the code generator, and other dependencies. This is a one-time cost — subsequent builds use the Nix cache and are fast (usually under 30 seconds).

### Symbol not found errors

If you get "undefined symbol" errors for your C library functions:

1. Verify the `.so`/`.dylib` is in `lib/` before building
2. Verify the header has `extern "C"` guards
3. Check the symbols are exported: `nm -D lib/libcalc.so | grep calc`
