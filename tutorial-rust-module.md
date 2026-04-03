# Tutorial: Building a Logos Module in Rust (or Any Language)

This tutorial walks through creating a **Logos module written in pure Rust** — with zero hand-written C++ code. Everything the Logos runtime needs (the Qt plugin, the interface, the dispatch layer) is auto-generated at build time from a plain C header.

While this tutorial uses Rust, the same pattern works for **any language** that can compile to a C-compatible static library: Go, Zig, Nim, C, or anything else with C FFI support. The key insight is that Logos modules are Qt plugins, but you never have to write Qt code yourself — the `logos-cpp-generator` tool does it for you.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [How It Works (The Big Picture)](#how-it-works-the-big-picture)
- [Step 1: Create the Project Structure](#step-1-create-the-project-structure)
- [Step 2: Write the Rust Library](#step-2-write-the-rust-library)
- [Step 3: Write the C Header](#step-3-write-the-c-header)
- [Step 4: Configure the Module (metadata.json)](#step-4-configure-the-module-metadatajson)
- [Step 5: Configure the Nix Build (flake.nix)](#step-5-configure-the-nix-build-flakenix)
- [Step 6: Configure CMake (CMakeLists.txt)](#step-6-configure-cmake-cmakeliststxt)
- [Step 7: Build the Module](#step-7-build-the-module)
- [Step 8: Inspect and Test](#step-8-inspect-and-test)
- [Under the Hood: What Gets Generated](#under-the-hood-what-gets-generated)
- [Adapting This Pattern to Other Languages](#adapting-this-pattern-to-other-languages)
- [Reference: Type Mappings](#reference-type-mappings)
- [Reference: Naming Conventions](#reference-naming-conventions)
- [Troubleshooting](#troubleshooting)

---

## Overview

A traditional Logos module is a C++/Qt plugin. The developer writes:
- An interface header with `Q_INVOKABLE` virtual methods
- A plugin class implementing that interface
- CMake + Nix build configuration

This is powerful but requires C++ knowledge, even when the actual logic is written in another language. The `--from-c-header` feature of `logos-cpp-generator` eliminates this requirement. You write your logic in any language, export C functions with a naming convention, and the entire Qt plugin layer is auto-generated.

**What you write:**

| File | Language | Purpose |
|------|----------|---------|
| `rust-lib/src/lib.rs` | Rust | Your module logic |
| `rust-lib/include/rust_calc.h` | C | Declares exported functions |
| `metadata.json` | JSON | Module name, version, build config |
| `flake.nix` | Nix | Build orchestration |
| `CMakeLists.txt` | CMake | Links generated plugin + your library |

**What gets auto-generated at build time:**

| File | Purpose |
|------|---------|
| `rust_calc_module_plugin.h` | Qt interface + plugin class with `Q_INVOKABLE` methods |
| `rust_calc_module_plugin.cpp` | Implementation that calls your C functions |
| `rust_calc_module.lidl` | LIDL interface definition (for documentation) |

**Zero hand-written C++ in your repository.**

---

## Prerequisites

- A working [logos-workspace](https://github.com/logos-co/logos-workspace) checkout with Nix installed
- The `ws` CLI on your PATH: `export PATH="/path/to/workspace/scripts:$PATH"`
- For Rust modules: `cargo` and `rustc` (provided automatically by Nix during build)
- Basic familiarity with Logos modules (read the [Developer Guide](logos-developer-guide.md) first)

---

## How It Works (The Big Picture)

The build pipeline has four stages:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  Stage 1: Compile your language                                          │
│  ─────────────────────────────                                           │
│  Rust/Go/Zig/etc. source  ──→  Static C library (.a)                    │
│                                                                          │
│  Stage 2: Auto-generate Qt plugin                                        │
│  ────────────────────────────────                                        │
│  C header + metadata.json  ──→  logos-cpp-generator --from-c-header      │
│                             ──→  Qt plugin .h/.cpp + LIDL file           │
│                                                                          │
│  Stage 3: Compile the plugin                                             │
│  ───────────────────────────                                             │
│  Generated .h/.cpp + static lib  ──→  CMake + Qt MOC  ──→  .so plugin   │
│                                                                          │
│  Stage 4: Package                                                        │
│  ────────────────                                                        │
│  Plugin .so  ──→  Logos module (loadable by logoscore / Basecamp)        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

The critical link is the **C header**. It serves as a language-neutral contract between your code and the Logos plugin system. The `logos-cpp-generator` reads this header, detects functions matching a naming convention (`prefix_methodname`), and generates a complete Qt plugin that calls those functions.

---

## Step 1: Create the Project Structure

Create a new directory for your module and set up the file structure:

```bash
mkdir -p logos-rust-calc-module/rust-lib/src
mkdir -p logos-rust-calc-module/rust-lib/include
cd logos-rust-calc-module
```

Your final directory structure will look like this:

```
logos-rust-calc-module/
├── metadata.json              # Module configuration (~20 lines)
├── flake.nix                  # Nix build orchestration (~25 lines)
├── CMakeLists.txt             # CMake build (~30 lines)
├── .gitignore                 # Ignore build artifacts
└── rust-lib/                  # Your Rust code (this could be go-lib/, zig-lib/, etc.)
    ├── Cargo.toml             # Rust package config
    ├── Cargo.lock             # Dependency lock file
    ├── src/
    │   └── lib.rs             # Module logic in pure Rust
    └── include/
        └── rust_calc.h        # C header declaring exported functions
```

> **No `src/` directory with C++ files.** Unlike a traditional Logos module, there are no hand-written `.h` or `.cpp` files. The Qt plugin code is generated automatically during the build.

Create the `.gitignore`:

```
result
result-*
build/
.deps/
lib/
generated_code/
rust-lib/target/
```

---

## Step 2: Write the Rust Library

### 2.1 Configure Cargo

Create `rust-lib/Cargo.toml`:

```toml
[package]
name = "rust_calc"
version = "1.0.0"
edition = "2021"

[lib]
crate-type = ["staticlib"]
```

**Key setting:** `crate-type = ["staticlib"]` tells Cargo to produce a `.a` static archive (e.g., `librust_calc.a`) instead of a Rust-native `.rlib`. This static archive can be linked into the C++/Qt plugin by the standard system linker.

> **No external dependencies.** This example has zero crate dependencies, which means `cargo build` works in the Nix sandbox without network access. If your module needs external crates, you'll need to use `rustPlatform.buildRustPackage` in Nix instead of calling `cargo` directly in `preConfigure` — see [Adapting This Pattern to Other Languages](#adapting-this-pattern-to-other-languages).

### 2.2 Write the module logic

Create `rust-lib/src/lib.rs`:

```rust
use std::os::raw::c_char;

#[no_mangle]
pub extern "C" fn rust_calc_add(a: i64, b: i64) -> i64 {
    a + b
}

#[no_mangle]
pub extern "C" fn rust_calc_subtract(a: i64, b: i64) -> i64 {
    a - b
}

#[no_mangle]
pub extern "C" fn rust_calc_multiply(a: i64, b: i64) -> i64 {
    a * b
}

#[no_mangle]
pub extern "C" fn rust_calc_divide(a: i64, b: i64) -> i64 {
    if b == 0 {
        -1
    } else {
        a / b
    }
}

#[no_mangle]
pub extern "C" fn rust_calc_factorial(n: i64) -> i64 {
    if n < 0 {
        return -1;
    }
    if n <= 1 {
        return 1;
    }
    let mut result: i64 = 1;
    for i in 2..=n {
        result = match result.checked_mul(i) {
            Some(v) => v,
            None => return -1, // overflow
        };
    }
    result
}

#[no_mangle]
pub extern "C" fn rust_calc_fibonacci(n: i64) -> i64 {
    if n < 0 {
        return -1;
    }
    if n == 0 {
        return 0;
    }
    if n == 1 {
        return 1;
    }
    let (mut a, mut b) = (0i64, 1i64);
    for _ in 2..=n {
        let next = match a.checked_add(b) {
            Some(v) => v,
            None => return -1, // overflow
        };
        a = b;
        b = next;
    }
    b
}

#[no_mangle]
pub extern "C" fn rust_calc_version() -> *const c_char {
    b"1.0.0\0".as_ptr() as *const c_char
}
```

**Critical rules for exported functions:**

1. **`#[no_mangle]`** — Prevents Rust from mangling the function name. Without this, the linker would see something like `_ZN10rust_calc3add17h8f3e4a5b2c1d0e9fE` instead of `rust_calc_add`.

2. **`pub extern "C"`** — Uses the C calling convention (argument passing, return values, stack layout). This is what makes the function callable from C/C++ code.

3. **Naming convention: `{prefix}_{method}`** — All functions share a common prefix (`rust_calc_`). The generator strips this prefix to derive the Logos method name. So `rust_calc_add` becomes method `add`, `rust_calc_factorial` becomes `factorial`, etc.

4. **C-compatible types only** — Parameters and return types must be representable in C. Use `i64` (not `isize`), `*const c_char` (not `&str`), `bool`, `f64`, etc. See [Reference: Type Mappings](#reference-type-mappings) for the full list.

5. **No panics across FFI** — A Rust panic that crosses the FFI boundary is undefined behavior. Use `checked_mul` / `checked_add` instead of operators that might overflow-panic in debug builds.

### 2.3 Generate the lock file

Create `rust-lib/Cargo.lock`. For a crate with no dependencies, this is trivial:

```toml
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 3

[[package]]
name = "rust_calc"
version = "1.0.0"
```

If you have a Rust toolchain installed locally, you can generate this automatically with `cd rust-lib && cargo generate-lockfile`.

### 2.4 (Optional) Add Rust tests

You can add standard Rust tests in the same `lib.rs` file:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(rust_calc_add(2, 3), 5);
        assert_eq!(rust_calc_add(-1, 1), 0);
    }

    #[test]
    fn test_factorial() {
        assert_eq!(rust_calc_factorial(0), 1);
        assert_eq!(rust_calc_factorial(5), 120);
        assert_eq!(rust_calc_factorial(-1), -1);
    }

    #[test]
    fn test_fibonacci() {
        assert_eq!(rust_calc_fibonacci(10), 55);
    }

    #[test]
    fn test_version() {
        let v = unsafe { std::ffi::CStr::from_ptr(rust_calc_version()) };
        assert_eq!(v.to_str().unwrap(), "1.0.0");
    }
}
```

Run locally with `cd rust-lib && cargo test` (requires a local Rust toolchain).

---

## Step 3: Write the C Header

Create `rust-lib/include/rust_calc.h`:

```c
#ifndef RUST_CALC_H
#define RUST_CALC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int64_t rust_calc_add(int64_t a, int64_t b);
int64_t rust_calc_subtract(int64_t a, int64_t b);
int64_t rust_calc_multiply(int64_t a, int64_t b);
int64_t rust_calc_divide(int64_t a, int64_t b);
int64_t rust_calc_factorial(int64_t n);
int64_t rust_calc_fibonacci(int64_t n);
const char* rust_calc_version(void);

#ifdef __cplusplus
}
#endif

#endif /* RUST_CALC_H */
```

**This is the most important file in the project.** It serves as the bridge between your language and the Logos plugin system. The `logos-cpp-generator --from-c-header` tool reads this file to determine:

- **What methods your module exposes** — each function declaration becomes a `Q_INVOKABLE` method
- **The parameter types** — `int64_t` maps to `int` in the Qt interface, `const char*` maps to `QString`
- **The return types** — same mappings apply
- **The method names** — derived by stripping the prefix (`rust_calc_`) from the function name

**Requirements for the C header:**

| Requirement | Why |
|-------------|-----|
| `#ifdef __cplusplus` / `extern "C"` guards | The header is included by generated C++ code |
| One function declaration per line, ending with `;` | The parser processes line-by-line |
| Functions use the naming convention `{prefix}_{method}(...)` | The prefix is stripped to get the Logos method name |
| `(void)` for functions with no parameters | Distinguishes from missing parameter list |
| Only C-compatible types | Must be representable in both your language and C++ |

> **Automation option:** For Rust, you can use [cbindgen](https://github.com/mozilla/cbindgen) to auto-generate this header from your Rust source. For Go, `cgo` generates headers automatically. For this tutorial, we write it manually since it's only 7 functions.

---

## Step 4: Configure the Module (metadata.json)

Create `metadata.json` in the project root:

```json
{
  "name": "rust_calc_module",
  "version": "1.0.0",
  "description": "Calculator module implemented in pure Rust",
  "author": "Logos Core Team",
  "type": "core",
  "interface": "universal",
  "category": "general",
  "main": "rust_calc_module_plugin",
  "dependencies": [],
  "include": [],
  "capabilities": [],
  "nix": {
    "external_libraries": [],
    "packages": {
      "build": ["cargo", "rustc"],
      "runtime": []
    },
    "cmake": {
      "find_packages": [],
      "extra_include_dirs": ["lib"]
    }
  }
}
```

**Key fields explained:**

| Field | What it does |
|-------|-------------|
| `name` | Module identifier — used as the prefix base. Must be a valid C identifier (letters, digits, underscores). |
| `main` | The Qt plugin class name. By convention: `{name}_plugin`. |
| `type` | Module type: `"core"` for backend logic, `"ui"` for Qt widgets. |
| `nix.packages.build` | Nix packages added to the build environment. `["cargo", "rustc"]` ensures the Rust toolchain is available during `preConfigure`. For Go, you'd use `["go"]`. For Zig, `["zig"]`. |
| `nix.cmake.extra_include_dirs` | Directories added to the C++ include path. `["lib"]` makes the C header (copied to `lib/` during build) visible to the generated plugin code. |

> **Prefix derivation:** The generator auto-derives the function prefix from the module name. For `"name": "rust_calc_module"`, it strips the `_module` suffix and adds `_`, giving prefix `rust_calc_`. You can override this with a `"c_prefix"` field in the `nix` section, or with the `--prefix` CLI flag.

---

## Step 5: Configure the Nix Build (flake.nix)

Create `flake.nix`:

```nix
{
  description = "Calculator module implemented in pure Rust for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
      preConfigure = ''
        echo "=== Building Rust calculator library ==="
        export HOME=$TMPDIR
        export CARGO_HOME=$TMPDIR/cargo
        mkdir -p $CARGO_HOME
        pushd rust-lib
        cargo build --release --offline 2>&1
        popd

        mkdir -p lib
        cp rust-lib/target/release/librust_calc.a lib/
        cp rust-lib/include/rust_calc.h lib/

        echo "=== Auto-generating Qt plugin from C header ==="
        logos-cpp-generator --from-c-header rust-lib/include/rust_calc.h \
          --metadata metadata.json \
          --backend qt \
          --c-header-include rust_calc.h \
          --output-dir ./generated_code
      '';
    };
}
```

**What `preConfigure` does — step by step:**

1. **Build the Rust library** — `cargo build --release --offline` compiles `lib.rs` into `rust-lib/target/release/librust_calc.a`. The `--offline` flag prevents Cargo from trying to access the network (blocked in the Nix sandbox). The `--release` flag enables optimizations.

2. **Stage build artifacts** — Copies the static library and C header to `lib/`, where CMake expects to find them.

3. **Auto-generate the Qt plugin** — Runs `logos-cpp-generator --from-c-header` which:
   - Parses the C header to discover exported functions
   - Reads `metadata.json` for the module name, version, and description
   - Generates `rust_calc_module_plugin.h` (Qt interface + plugin class)
   - Generates `rust_calc_module_plugin.cpp` (implementation calling C functions)
   - Generates `rust_calc_module.lidl` (LIDL interface definition)

**Generator CLI flags:**

| Flag | Purpose |
|------|---------|
| `--from-c-header <path>` | Path to the C header file to parse |
| `--metadata <path>` | Path to metadata.json (provides module name, version) |
| `--backend qt` | Generate Qt/PluginInterface-style plugin code |
| `--c-header-include <name>` | The `#include` path used in generated code (just the filename) |
| `--output-dir <path>` | Where to write generated files |
| `--prefix <prefix>` | (Optional) Override the auto-derived function prefix |

> **Timing of `preConfigure`:** This hook runs after the module builder's own setup (which generates `logos_sdk.cpp` and other SDK files) but before CMake configuration. By the time CMake runs, `generated_code/` contains both the SDK files and your auto-generated plugin files.

---

## Step 6: Configure CMake (CMakeLists.txt)

Create `CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.14)
project(RustCalcModulePlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found. Set LOGOS_MODULE_BUILDER_ROOT.")
endif()

configure_file(${CMAKE_CURRENT_SOURCE_DIR}/metadata.json
               ${CMAKE_CURRENT_BINARY_DIR}/metadata.json COPYONLY)

logos_module(
    NAME rust_calc_module
    SOURCES
        generated_code/rust_calc_module_plugin.h
        generated_code/rust_calc_module_plugin.cpp
    INCLUDE_DIRS
        ${CMAKE_CURRENT_SOURCE_DIR}/lib
        ${CMAKE_CURRENT_SOURCE_DIR}/generated_code
)

# Link the Rust static library
find_library(LIBRUST_CALC
    NAMES librust_calc.a rust_calc
    PATHS ${CMAKE_CURRENT_SOURCE_DIR}/lib
    NO_DEFAULT_PATH
)

if(LIBRUST_CALC)
    target_link_libraries(rust_calc_module_module_plugin PRIVATE ${LIBRUST_CALC})
    # Rust static libraries need pthread and dl on Linux
    if(NOT APPLE)
        target_link_libraries(rust_calc_module_module_plugin PRIVATE pthread dl)
    endif()
else()
    message(FATAL_ERROR "Rust calculator library (librust_calc.a) not found in lib/")
endif()
```

**Key points:**

- **SOURCES** reference the generated files in `generated_code/`, not hand-written source files.
- **INCLUDE_DIRS** adds both `lib/` (where the C header lives) and `generated_code/` (where the generated plugin header lives).
- **find_library** locates the Rust static archive. The `logos_module()` macro's built-in `EXTERNAL_LIBS` option only finds shared libraries (`.so`/`.dylib`), so we manually link the static `.a` file.
- **pthread and dl** are required on Linux because the Rust standard library (statically linked into `librust_calc.a`) depends on them for threading and dynamic loading.
- **Target name convention:** The `logos_module()` macro creates a target named `{NAME}_module_plugin` — so for `NAME rust_calc_module`, the target is `rust_calc_module_module_plugin`.

---

## Step 7: Build the Module

### 7.1 Initialize Git

Nix flakes require all source files to be tracked by Git:

```bash
git init
git add -A
git commit -m "initial commit"
```

### 7.2 Build

From the workspace root:

```bash
ws build logos-rust-calc-module --local logos-cpp-sdk
```

> **Why `--local logos-cpp-sdk`?** The `--from-c-header` feature is in the local `logos-cpp-sdk` source. Once this feature is merged upstream, the `--local` flag won't be needed.

The first build takes a few minutes (compiling Qt, the SDK, Rust, etc.). Subsequent builds are fast thanks to Nix caching.

Expected output:

```
Local overrides:
  * logos-cpp-sdk → path:/workspace/repos/logos-cpp-sdk

Building logos-rust-calc-module...
OK   logos-rust-calc-module
```

### 7.3 Standalone build (without workspace)

If your module is a standalone repo (not part of the workspace), build directly with Nix:

```bash
cd logos-rust-calc-module
nix build
```

---

## Step 8: Inspect and Test

### 8.1 Inspect with `lm`

Use the `lm` tool to verify the module's metadata and methods:

```bash
lm result/lib/rust_calc_module_plugin.so
```

Expected output:

```
Plugin Metadata:
================
Name:         rust_calc_module
Version:      1.0.0
Description:  Calculator module implemented in pure Rust
Author:       Logos Core Team
Type:         core
Dependencies: (none)

Plugin Methods:
===============

void initLogos(LogosAPI* logosAPIInstance)
  Signature: initLogos(LogosAPI*)
  Invokable: yes

int add(int a, int b)
  Signature: add(int,int)
  Invokable: yes

int subtract(int a, int b)
  Signature: subtract(int,int)
  Invokable: yes

int multiply(int a, int b)
  Signature: multiply(int,int)
  Invokable: yes

int divide(int a, int b)
  Signature: divide(int,int)
  Invokable: yes

int factorial(int n)
  Signature: factorial(int)
  Invokable: yes

int fibonacci(int n)
  Signature: fibonacci(int)
  Invokable: yes

QString libVersion()
  Signature: libVersion()
  Invokable: yes
```

Every `extern "C"` function from your C header appears as a `Q_INVOKABLE` method. Notice that `rust_calc_version` became `libVersion` — the generator automatically renames methods that conflict with `PluginInterface` reserved names (`name`, `version`, `initLogos`).

### 8.2 Test with logoscore

To test the module at runtime with `logoscore`, you need to create a module directory with a `manifest.json` (this is what `logoscore` uses for module discovery):

```bash
mkdir -p modules/rust_calc_module
cp result/lib/rust_calc_module_plugin.so modules/rust_calc_module/

# Create manifest.json for logoscore discovery
cat > modules/rust_calc_module/manifest.json << 'EOF'
{
  "name": "rust_calc_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Calculator module implemented in pure Rust",
  "main": { "linux-x86_64-dev": "rust_calc_module_plugin.so" },
  "manifestVersion": "0.1.0",
  "dependencies": []
}
EOF
```

> **Platform key:** Adjust the key in `"main"` to match your platform: `linux-x86_64-dev`, `linux-arm64-dev`, `darwin-arm64-dev`, or `darwin-x86_64-dev`.

Then call methods:

```bash
logoscore --modules-dir ./modules \
  -l rust_calc_module \
  -c "rust_calc_module.add(2,3)" \
  --quit-on-finish
```

Expected output:

```
Method call successful. Result: 5
```

Try other methods:

```bash
logoscore --modules-dir ./modules -l rust_calc_module \
  -c "rust_calc_module.factorial(10)" --quit-on-finish
# → Result: 3628800

logoscore --modules-dir ./modules -l rust_calc_module \
  -c "rust_calc_module.fibonacci(10)" --quit-on-finish
# → Result: 55

logoscore --modules-dir ./modules -l rust_calc_module \
  -c "rust_calc_module.libVersion()" --quit-on-finish
# → Result: 1.0.0
```

For more on testing with logoscore, see the [Developer Guide -- Running with logoscore](logos-developer-guide.md#51-running-with-logoscore).

---

## Under the Hood: What Gets Generated

When `logos-cpp-generator --from-c-header` runs, it produces three files. Understanding what they contain helps you debug issues and adapt the pattern to other languages.

### Generated LIDL file (`rust_calc_module.lidl`)

This is a human-readable interface definition derived from your C header:

```
module rust_calc_module {
  version "1.0.0"
  description "Calculator module implemented in pure Rust"
  category "general"
  depends []

  method add(a: int, b: int) -> int
  method subtract(a: int, b: int) -> int
  method multiply(a: int, b: int) -> int
  method divide(a: int, b: int) -> int
  method factorial(n: int) -> int
  method fibonacci(n: int) -> int
  method libVersion() -> tstr
}
```

The LIDL file is generated for documentation and is not used during the build. It provides a language-neutral description of your module's API. The type `tstr` means "text string" (maps to `QString` in Qt, `std::string` in C++, `const char*` in C).

### Generated plugin header (`rust_calc_module_plugin.h`)

This is a complete Qt plugin header with two classes:

```cpp
// AUTO-GENERATED by logos-cpp-generator --from-c-header -- do not edit
#pragma once

#include <QObject>
#include <QString>
#include <QVariant>
#include <QVariantList>
#include "interface.h"
#include "logos_api.h"

extern "C" {
#include "rust_calc.h"      // ← Your C header
}

// Interface class — declares the module's API as pure virtual methods
class RustCalcModuleInterface : public PluginInterface {
public:
    virtual ~RustCalcModuleInterface() = default;
    Q_INVOKABLE virtual int add(int a, int b) = 0;
    Q_INVOKABLE virtual int subtract(int a, int b) = 0;
    Q_INVOKABLE virtual int multiply(int a, int b) = 0;
    Q_INVOKABLE virtual int divide(int a, int b) = 0;
    Q_INVOKABLE virtual int factorial(int n) = 0;
    Q_INVOKABLE virtual int fibonacci(int n) = 0;
    Q_INVOKABLE virtual QString libVersion() = 0;
};

Q_DECLARE_INTERFACE(RustCalcModuleInterface, "org.logos.RustCalcModuleInterface")

// Plugin class — the actual Qt plugin that logoscore loads
class RustCalcModulePlugin : public QObject, public RustCalcModuleInterface {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.logos.RustCalcModuleInterface" FILE "metadata.json")
    Q_INTERFACES(RustCalcModuleInterface PluginInterface)

public:
    explicit RustCalcModulePlugin(QObject* parent = nullptr);
    ~RustCalcModulePlugin() override;

    QString name() const override { return QStringLiteral("rust_calc_module"); }
    QString version() const override { return QStringLiteral("1.0.0"); }

    Q_INVOKABLE void initLogos(LogosAPI* logosAPIInstance);

    Q_INVOKABLE int add(int a, int b) override;
    Q_INVOKABLE int subtract(int a, int b) override;
    // ... (one method per C function)

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);
};
```

**How the Qt plugin system works:**

- `Q_OBJECT` enables Qt's meta-object system (signals, slots, runtime reflection)
- `Q_PLUGIN_METADATA` embeds `metadata.json` into the `.so` binary at compile time
- `Q_INTERFACES` declares which interfaces the plugin implements
- `Q_INVOKABLE` makes methods discoverable at runtime — this is how `logoscore` and `lm` find your methods
- Qt's MOC (Meta-Object Compiler) processes this header during the build to generate the reflection tables

### Generated plugin source (`rust_calc_module_plugin.cpp`)

This is the implementation — each method is a one-liner that calls your C function:

```cpp
// AUTO-GENERATED by logos-cpp-generator --from-c-header -- do not edit
#include "rust_calc_module_plugin.h"
#include <QDebug>

RustCalcModulePlugin::RustCalcModulePlugin(QObject* parent)
    : QObject(parent)
{
    qDebug() << "RustCalcModulePlugin: created";
}

// ...

int RustCalcModulePlugin::add(int a, int b)
{
    return static_cast<int>(rust_calc_add(static_cast<int64_t>(a), static_cast<int64_t>(b)));
}

int RustCalcModulePlugin::factorial(int n)
{
    return static_cast<int>(rust_calc_factorial(static_cast<int64_t>(n)));
}

QString RustCalcModulePlugin::libVersion()
{
    return QString::fromUtf8(rust_calc_version());
}
```

**Type conversions at the boundary:**

The generated code handles type conversion between Qt types (used by the plugin interface) and C types (used by your functions):

| Direction | Qt type | C type | Conversion |
|-----------|---------|--------|------------|
| Parameter (Qt → C) | `int` | `int64_t` | `static_cast<int64_t>(param)` |
| Parameter (Qt → C) | `QString` | `const char*` | `param.toUtf8().constData()` |
| Return (C → Qt) | `int64_t` | `int` | `static_cast<int>(result)` |
| Return (C → Qt) | `const char*` | `QString` | `QString::fromUtf8(result)` |
| Pass-through | `double` | `double` | No conversion needed |
| Pass-through | `bool` | `bool` | No conversion needed |

---

## Adapting This Pattern to Other Languages

The Rust-specific parts of this tutorial are limited to **Step 2** (writing the library) and the `cargo build` line in **Step 5** (the `preConfigure` hook). Everything else — the C header, metadata.json, CMakeLists.txt, and the generator — is language-agnostic.

### Go module

```
go-lib/
├── main.go           # Module logic with //export directives
├── go.mod
└── include/
    └── my_module.h   # Generated by cgo or written manually
```

In `metadata.json`, change build packages:

```json
"nix": {
  "packages": {
    "build": ["go"]
  }
}
```

In `flake.nix`, change the `preConfigure` build step:

```nix
preConfigure = ''
  export HOME=$TMPDIR
  export GOPATH=$TMPDIR/go
  export GOCACHE=$TMPDIR/go-cache
  mkdir -p $GOPATH $GOCACHE
  cd go-lib
  CGO_ENABLED=1 go build -buildmode=c-archive -o libmy_module.a .
  cd ..
  mkdir -p lib
  cp go-lib/libmy_module.a lib/
  cp go-lib/include/my_module.h lib/

  logos-cpp-generator --from-c-header go-lib/include/my_module.h \
    --metadata metadata.json --backend qt \
    --c-header-include my_module.h --output-dir ./generated_code
'';
```

### Zig module

```
zig-lib/
├── src/
│   └── lib.zig       # Module logic with export functions
├── build.zig
└── include/
    └── my_module.h   # Written manually
```

In `metadata.json`:

```json
"nix": {
  "packages": {
    "build": ["zig"]
  }
}
```

In `flake.nix`:

```nix
preConfigure = ''
  cd zig-lib
  zig build -Doptimize=ReleaseFast
  cd ..
  mkdir -p lib
  cp zig-lib/zig-out/lib/libmy_module.a lib/
  cp zig-lib/include/my_module.h lib/

  logos-cpp-generator --from-c-header zig-lib/include/my_module.h \
    --metadata metadata.json --backend qt \
    --c-header-include my_module.h --output-dir ./generated_code
'';
```

### C module (simplest case)

For a plain C library, you don't even need a separate build step — just compile directly:

```nix
preConfigure = ''
  mkdir -p lib
  gcc -c -O2 -fPIC my_lib.c -o lib/libmy_module.o
  ar rcs lib/libmy_module.a lib/libmy_module.o
  cp my_lib.h lib/

  logos-cpp-generator --from-c-header my_lib.h \
    --metadata metadata.json --backend qt \
    --c-header-include my_lib.h --output-dir ./generated_code
'';
```

### The universal recipe

Regardless of language, the steps are always:

1. **Compile** your language to a static library (`.a` / `.lib`)
2. **Copy** the static library and C header to `lib/`
3. **Run** `logos-cpp-generator --from-c-header` to generate the Qt plugin
4. **CMake** links the generated plugin code with your static library

---

## Reference: Type Mappings

### C header → LIDL → Qt plugin

| C type | LIDL type | Qt type | Notes |
|--------|-----------|---------|-------|
| `int64_t` | `int` | `int` | 64-bit in C, 32-bit in Qt interface |
| `int32_t`, `int` | `int` | `int` | |
| `uint64_t` | `uint` | `int` | Unsigned in C, signed in Qt |
| `uint32_t`, `unsigned int` | `uint` | `int` | |
| `double`, `float` | `float64` | `double` | |
| `bool`, `_Bool` | `bool` | `bool` | |
| `const char*`, `char*` | `tstr` | `QString` | Converted via `QString::fromUtf8` |
| `void` | `void` | `void` | |
| Anything else | `any` | `QVariant` | Fallback — avoid if possible |

### Rust → C type recommendations

| Rust type | C type to use | LIDL type |
|-----------|---------------|-----------|
| `i64` | `int64_t` | `int` |
| `i32` | `int32_t` | `int` |
| `u64` | `uint64_t` | `uint` |
| `f64` | `double` | `float64` |
| `bool` | `bool` | `bool` |
| `*const c_char` | `const char*` | `tstr` |
| `()` (unit) | `void` | `void` |

---

## Reference: Naming Conventions

### Function prefix

The generator strips the function prefix to derive method names:

| C function | Prefix | Logos method |
|------------|--------|-------------|
| `rust_calc_add` | `rust_calc_` | `add` |
| `rust_calc_factorial` | `rust_calc_` | `factorial` |
| `mymod_do_thing` | `mymod_` | `do_thing` |

### Prefix auto-derivation

If you don't specify `--prefix`, the generator derives it from the module name in `metadata.json`:

1. Take the `name` field (e.g., `"rust_calc_module"`)
2. Strip `_module` suffix if present → `"rust_calc"`
3. Append `_` → `"rust_calc_"`

Override with `--prefix my_custom_prefix_` or by adding `"c_prefix": "my_prefix_"` to the `nix` section of `metadata.json`.

### Reserved names

These method names conflict with `PluginInterface` built-in methods and are automatically renamed:

| C function | Would-be method | Actual method |
|------------|-----------------|---------------|
| `prefix_name` | `name` (reserved) | `libName` |
| `prefix_version` | `version` (reserved) | `libVersion` |
| `prefix_initLogos` | `initLogos` (reserved) | `libInitLogos` |

The generated implementation correctly maps back to the original C function name when calling it.

### Functions that are skipped

Functions in the C header that **don't** start with the prefix are silently ignored. This means you can have internal helper functions in the same header without them appearing as module methods.

---

## Troubleshooting

### `cargo build` fails with network errors

The Nix sandbox blocks network access. If your Rust project has external crate dependencies, `cargo build --offline` will fail because it can't download them.

**Solution:** Use `rustPlatform.buildRustPackage` in a separate Nix derivation that pre-fetches crates, then pass the built library to the module via `preConfigure`. See the [logos-accounts-module](https://github.com/logos-co/logos-accounts-module) for an example of this pattern with Go.

### No methods appear in `lm` output

The generator didn't find any functions matching your prefix. Check:

1. Your C header has function declarations ending with `;`
2. Function names start with the expected prefix (check with `--prefix` or the auto-derived prefix)
3. The header is being read during build (add `cat` commands in `preConfigure` to verify)

### `CMake Error: Cannot find source file: generated_code/..._plugin.h`

The generator didn't run or failed silently. Add error checking to `preConfigure`:

```nix
preConfigure = ''
  logos-cpp-generator --from-c-header ... || { echo "Generator failed!"; exit 1; }
  test -f ./generated_code/my_module_plugin.h || { echo "Plugin header not generated!"; exit 1; }
'';
```

### Linker errors: `undefined reference to rust_calc_add`

The Rust static library wasn't linked. Check:

1. `find_library` in CMakeLists.txt can find `librust_calc.a` in `lib/`
2. The `target_link_libraries` line references the correct target (`{name}_module_plugin`)
3. The `preConfigure` actually copies the `.a` file to `lib/`

### Linker errors: `undefined reference to pthread_create` (or `dlsym`, etc.)

The Rust standard library needs system libraries. Add to CMakeLists.txt:

```cmake
if(NOT APPLE)
    target_link_libraries(my_module_module_plugin PRIVATE pthread dl)
endif()
```

### Method returns wrong type / crashes

Check the type mapping between your language and the C header. Common mistakes:

- Using `size_t` instead of `uint64_t` (platform-dependent size)
- Returning a stack-allocated string pointer (dangling pointer after function returns)
- Integer overflow in Rust panicking across FFI boundary (use `checked_*` operations)

---

*For more on the Logos module system, see the [Developer Guide](logos-developer-guide.md). For wrapping existing C libraries (where you write C++ directly), see [Tutorial: Wrapping a C Library](tutorial-wrapping-c-library.md).*
