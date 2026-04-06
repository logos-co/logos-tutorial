# WebAssembly Modules in Logos

This document describes how WebAssembly (WASM) modules work in the Logos platform — how to build one, how the runtime loads and executes it, and what changes were made across the codebase to enable WASM support.

## Table of Contents

- [Overview](#overview)
- [How It Works (Architecture)](#how-it-works-architecture)
  - [Process Model](#process-model)
  - [IPC: Transparent to Callers](#ipc-transparent-to-callers)
  - [Type System](#type-system)
  - [Export Discovery](#export-discovery)
  - [Authentication](#authentication)
- [Tutorial: Building a WASM Calculator Module](#tutorial-building-a-wasm-calculator-module)
  - [Prerequisites](#prerequisites)
  - [Step 1: Create the Project Structure](#step-1-create-the-project-structure)
  - [Step 2: Write the Rust Guest Code](#step-2-write-the-rust-guest-code)
  - [Step 3: Configure the Module (metadata.json)](#step-3-configure-the-module-metadatajson)
  - [Step 4: Create the Package Manifest (manifest.json)](#step-4-create-the-package-manifest-manifestjson)
  - [Step 5: Write the Nix Build (flake.nix)](#step-5-write-the-nix-build-flakenix)
  - [Step 6: Build](#step-6-build)
  - [Step 7: Test with logoscore](#step-7-test-with-logoscore)
  - [Step 8: Package with lgx](#step-8-package-with-lgx)
- [Calling a WASM Module from Another Module](#calling-a-wasm-module-from-another-module)
- [Cross-Repo Changes That Enable WASM Support](#cross-repo-changes-that-enable-wasm-support)
  - [logos-liblogos](#logos-liblogos)
  - [logos-cpp-sdk](#logos-cpp-sdk)
  - [logos-package-manager](#logos-package-manager)
  - [logos-logoscore-cli](#logos-logoscore-cli)
- [Reference](#reference)
  - [Type Mappings](#type-mappings)
  - [Function Signature Requirements](#function-signature-requirements)
  - [Filtered Exports](#filtered-exports)
  - [Platform Variant Names](#platform-variant-names)
- [Limitations and Future Work](#limitations-and-future-work)
- [Troubleshooting](#troubleshooting)

---

## Overview

A traditional Logos module is a C++/Qt plugin — a `.so` or `.dylib` compiled with CMake, linked against Qt 6, and loaded via `QPluginLoader`. This works well but requires C++ and Qt knowledge.

**WASM modules are a simpler alternative.** You write pure computation in Rust (or any language that compiles to `wasm32-unknown-unknown`), export plain C functions, and the Logos runtime loads the `.wasm` binary directly via [Wasmtime](https://wasmtime.dev/). No C++, no Qt, no CMake, no code generation.

> **Note on naming:** Despite the document title, Logos does **not** use [Extism](https://extism.org/). The runtime uses Wasmtime directly with raw C ABI exports (`extern "C"` + `#[no_mangle]`). Extism's PDK and host SDK are not involved. Functions take and return scalar numeric types — not Extism-style input/output buffers.

**What you write:**

| File | Purpose |
|------|---------|
| `wasm-guest/src/lib.rs` | Your module logic in Rust |
| `wasm-guest/Cargo.toml` | Rust build config |
| `metadata.json` | Module name, version, type |
| `manifest.json` | Package manifest for module discovery |
| `flake.nix` | Nix build orchestration |

**What you don't write:** No C++ source, no Qt headers, no CMakeLists.txt, no C header, no generated code.

**Comparison with native Qt modules:**

| | Native Qt Module | WASM Module |
|---|---|---|
| Language | C++ (or any language via C FFI + code generator) | Rust (or any language targeting wasm32) |
| Build system | CMake + Nix + logos-module-builder | Cargo + Nix (no CMake) |
| Output | `.so` / `.dylib` Qt plugin | `.wasm` binary |
| Host process | `logos_host` | `logos_host_wasm` |
| Runtime | QPluginLoader + Qt MOC | Wasmtime |
| IPC | Qt Remote Objects | Qt Remote Objects (same) |
| Types | Full Qt type system (QString, QVariantMap, etc.) | Scalars only (i32, i64, f32, f64) |
| Inter-module calls | Yes, via LogosAPI | Yes, via LogosAPI (same) |
| File size | ~100KB–1MB+ | ~15KB for a calculator |

---

## How It Works (Architecture)

### Process Model

Every module — native or WASM — runs in its own process for isolation. The core process (`logoscore`) spawns a host process for each module:

```
logoscore (main process)
├── logos_host "capability_module" "/path/to/capability_module_plugin.so"
├── logos_host "chat_module" "/path/to/chat_module_plugin.so"
└── logos_host_wasm "wasm_calc_module" "/path/to/wasm_calc_module.wasm"
                       ↑                     ↑
                   --name arg            --path arg
```

When `logoscore` detects a `.wasm` file (by extension), it spawns `logos_host_wasm` instead of `logos_host`. The WASM host process:

1. **Receives an auth token** via a local Unix socket (`logos_token_<module_name>`)
2. **Loads the `.wasm` binary** using the Wasmtime C API — compiles it to native code, creates an engine/store/instance
3. **Discovers exported functions** by iterating module exports and caching their type signatures
4. **Registers on the IPC bus** via `LogosAPI::getProvider()->registerObject()` — making it callable by any other module
5. **Enters the Qt event loop** to serve remote method calls

### IPC: Transparent to Callers

From the caller's perspective, WASM modules are **indistinguishable from native modules**. The same Qt Remote Objects transport layer carries method calls between processes. A native C++ module calling a WASM module looks exactly like calling any other module:

```cpp
// This works identically whether "wasm_calc_module" is a .so or a .wasm
LogosAPIClient* client = logosAPI->getClient("wasm_calc_module");
QVariant result = client->invokeRemoteMethod("wasm_calc_module", "add", 3, 5);
// result == QVariant(8)
```

The call path is:

```
Caller module (any process)
    → Qt Remote Objects (IPC)
        → logos_host_wasm process
            → ModuleProxy::callRemoteMethod()
                → WasmProviderObject::callMethod()
                    → QVariant args → wasmtime_val_t conversion
                        → wasmtime_func_call()
                            → WASM function executes
                        → wasmtime_val_t result → QVariant conversion
                    ← returns QVariant
                ← returns to ModuleProxy
            ← serialized back over IPC
        ← received by caller
    ← QVariant result
```

### Type System

WASM modules support four scalar types. Each maps bidirectionally between WASM, Rust, Qt, and `logoscore -c` argument auto-detection:

| WASM Type | Rust Type | Qt/QVariant Type | logoscore -c auto-detect |
|-----------|-----------|------------------|--------------------------|
| `i32` | `i32` | `int` | Integer literals (small) |
| `i64` | `i64` | `qlonglong` | Integer literals |
| `f32` | `f32` | `float` (stored as `double`) | Decimal literals |
| `f64` | `f64` | `double` | Decimal literals |
| (void) | `()` | `QVariant(true)` | — |

**Conversion rules in `WasmProviderObject::callMethod()`:**

- Incoming `QVariant` args are converted using `toInt()`, `toLongLong()`, `toFloat()`, or `toDouble()` based on the WASM function's declared parameter types
- Return values are converted back: `i32` → `QVariant(int)`, `i64` → `QVariant(qlonglong)`, `f32`/`f64` → `QVariant(double)`
- Void functions (no return value) return `QVariant(true)`

### Export Discovery

When a `.wasm` module is loaded, `WasmProviderObject::discoverExports()` iterates all module exports and registers every exported function — except internal/WASI bookkeeping symbols:

**Skipped exports:**
- `memory`, `_start`, `_initialize`
- `__data_end`, `__heap_base`, `__indirect_function_table`
- Any name starting with `__` (double underscore)

Everything else becomes a callable method. The parameter count and types are read from the function's Wasmtime type signature and cached in a `QHash<QString, WasmFunc>`.

### Authentication

WASM modules use the same token-based authentication as native modules:

1. `logoscore` spawns `logos_host_wasm` with `--name` and `--path` args
2. `logos_host_wasm` creates a `QLocalServer` on socket `logos_token_<name>`
3. `logoscore` connects and sends a UUID auth token
4. The WASM host saves the token for `"core"` and `"capability_module"`
5. All subsequent IPC calls include the token, validated by `ModuleProxy`

---

## Tutorial: Building a WASM Calculator Module

This walks through building the `logos-wasm-calc-module` — a calculator with `add`, `subtract`, `multiply`, `divide`, `factorial`, and `fibonacci` functions.

### Prerequisites

- A working [logos-workspace](https://github.com/logos-co/logos-workspace) checkout with Nix installed
- The `ws` CLI on your PATH: `export PATH="/path/to/workspace/scripts:$PATH"`
- Rust and Cargo (provided automatically by Nix during build)

### Step 1: Create the Project Structure

```bash
mkdir -p logos-wasm-calc-module/wasm-guest/src
cd logos-wasm-calc-module
```

Your final directory structure:

```
logos-wasm-calc-module/
├── metadata.json          # Module metadata
├── manifest.json          # Package manifest for discovery
├── flake.nix              # Nix build
├── flake.lock             # (auto-generated by nix)
├── .gitignore
└── wasm-guest/            # Rust source
    ├── Cargo.toml
    ├── Cargo.lock
    └── src/
        └── lib.rs         # Module logic
```

Create `.gitignore`:

```
result
result-*
wasm-guest/target/
```

### Step 2: Write the Rust Guest Code

#### 2.1 Configure Cargo

Create `wasm-guest/Cargo.toml`:

```toml
[package]
name = "wasm_calc"
version = "1.0.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[profile.release]
opt-level = "s"
lto = true
```

**Key settings:**

- **`crate-type = ["cdylib"]`** — produces a C-compatible dynamic library. For `wasm32-unknown-unknown`, this means a `.wasm` binary with exported functions.
- **`opt-level = "s"`** — optimize for size. WASM binaries are small; this keeps them minimal (~16KB for a calculator).
- **`lto = true`** — link-time optimization strips unused code, critical for WASM where every byte counts.

> **No external dependencies.** This example has zero crate dependencies, so `cargo build --offline` works in the Nix sandbox. If you need crates, you'll need to use `rustPlatform.buildRustPackage` instead of calling `cargo` directly.

#### 2.2 Write the Module Logic

Create `wasm-guest/src/lib.rs`:

```rust
// Each exported function becomes a callable method in the Logos module.
// Functions use the C ABI and are exported with #[no_mangle] so Wasmtime
// can discover them by name.

#[no_mangle]
pub extern "C" fn add(a: i64, b: i64) -> i64 {
    a + b
}

#[no_mangle]
pub extern "C" fn subtract(a: i64, b: i64) -> i64 {
    a - b
}

#[no_mangle]
pub extern "C" fn multiply(a: i64, b: i64) -> i64 {
    a * b
}

#[no_mangle]
pub extern "C" fn divide(a: i64, b: i64) -> i64 {
    if b == 0 { -1 } else { a / b }
}

#[no_mangle]
pub extern "C" fn factorial(n: i64) -> i64 {
    if n < 0 { return -1; }
    let mut result: i64 = 1;
    for i in 1..=n {
        result = result.checked_mul(i).unwrap_or(-1);
        if result < 0 { return -1; }
    }
    result
}

#[no_mangle]
pub extern "C" fn fibonacci(n: i64) -> i64 {
    if n < 0 { return -1; }
    if n <= 1 { return n; }
    let (mut a, mut b) = (0i64, 1i64);
    for _ in 2..=n {
        let next = a.checked_add(b).unwrap_or(-1);
        if next < 0 { return -1; }
        a = b;
        b = next;
    }
    b
}
```

**Rules for exported functions:**

1. **`#[no_mangle]`** — prevents Rust name mangling so Wasmtime finds the function by its plain name
2. **`pub extern "C"`** — uses the C calling convention (standard for WASM exports)
3. **Scalar types only** — parameters and return values must be `i32`, `i64`, `f32`, or `f64`
4. **No panics across FFI** — use `checked_*` operations and return error values instead of panicking. A panic in WASM becomes a trap, which the host logs as an error and returns `QVariant()` (empty).

### Step 3: Configure the Module (metadata.json)

Create `metadata.json`:

```json
{
  "name": "wasm_calc_module",
  "version": "1.0.0",
  "description": "Calculator module implemented as WebAssembly",
  "author": "Logos Core Team",
  "type": "core",
  "category": "general",
  "main": "wasm_calc_module_plugin",
  "dependencies": []
}
```

This file follows the same schema as native modules. The `type` must be `"core"` for the package manager to discover it as a module (vs. a UI plugin).

### Step 4: Create the Package Manifest (manifest.json)

Create `manifest.json`:

```json
{
  "name": "wasm_calc_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Calculator module implemented as WebAssembly",
  "author": "Logos Core Team",
  "main": "wasm_calc_module.wasm",
  "manifestVersion": "0.1.0",
  "dependencies": []
}
```

**The `main` field** tells the package manager which file to load. For WASM modules, this is the `.wasm` filename. It can be either:

- A **string** (simplest) — the `.wasm` filename, used on all platforms
- An **object** mapping platform variants to filenames (useful if you have different builds per platform, though WASM is typically architecture-independent):

```json
"main": {
  "linux-x86_64": "wasm_calc_module.wasm",
  "linux-arm64": "wasm_calc_module.wasm",
  "darwin-arm64": "wasm_calc_module.wasm",
  "darwin-x86_64": "wasm_calc_module.wasm"
}
```

The string form is preferred for WASM since the same binary runs everywhere.

### Step 5: Write the Nix Build (flake.nix)

Create `flake.nix`:

```nix
{
  description = "Calculator module as WebAssembly — loadable by logoscore via logos_host_wasm";

  inputs = {
    logos-nix.url = "github:logos-co/logos-nix";
    nixpkgs.follows = "logos-nix/nixpkgs";
    nix-bundle-lgx.url = "github:logos-co/nix-bundle-lgx";
    logos-package.url = "github:logos-co/logos-package";
    nix-bundle-dir.url = "github:logos-co/nix-bundle-dir";
  };

  outputs = { self, nixpkgs, logos-nix, nix-bundle-lgx, logos-package, nix-bundle-dir }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);
    in {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };

          # Stage 1: Compile Rust to .wasm
          wasmLib = pkgs.stdenv.mkDerivation {
            pname = "wasm-calc";
            version = "1.0.0";
            src = ./wasm-guest;

            nativeBuildInputs = [ pkgs.cargo pkgs.rustc pkgs.lld ];

            buildPhase = ''
              runHook preBuild
              export HOME=$TMPDIR
              export CARGO_HOME=$TMPDIR/cargo
              mkdir -p $CARGO_HOME
              cargo build --target wasm32-unknown-unknown --release --offline 2>&1
              runHook postBuild
            '';

            installPhase = ''
              runHook preInstall
              mkdir -p $out/lib
              cp target/wasm32-unknown-unknown/release/wasm_calc.wasm $out/lib/
              runHook postInstall
            '';
          };

          # Stage 2: Create module directory with canonical naming
          moduleLib = (pkgs.runCommand "logos-wasm_calc_module-module-lib-1.0.0" {} ''
            mkdir -p $out/lib
            cp ${wasmLib}/lib/wasm_calc.wasm $out/lib/wasm_calc_module.wasm
          '') // { src = ./.; version = "1.0.0"; };

          bundleLgx = nix-bundle-lgx.bundlers.${system}.default;
        in {
          default = moduleLib;
          lib = moduleLib;
          wasm = wasmLib;
          lgx = bundleLgx moduleLib;
        }
      );
    };
}
```

**Build pipeline:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Stage 1: Compile Rust → WASM                                        │
│  ────────────────────────────                                        │
│  wasm-guest/src/lib.rs  ──→  cargo build --target wasm32-unknown-    │
│                               unknown --release                      │
│                          ──→  wasm_calc.wasm (~16KB)                 │
│                                                                      │
│  Stage 2: Package as module                                          │
│  ───────────────────────────                                         │
│  wasm_calc.wasm  ──→  renamed to wasm_calc_module.wasm               │
│                  ──→  placed in lib/ directory                        │
│                                                                      │
│  Stage 3 (optional): Bundle as .lgx                                  │
│  ──────────────────────────────────                                  │
│  module lib/  ──→  nix-bundle-lgx  ──→  wasm_calc_module.lgx        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Key points:**

- The Rust target `wasm32-unknown-unknown` ships with every Rust compiler — no additional sysroot or WASI SDK needed
- `--offline` works because there are no external crate dependencies
- `lld` is included as a linker (Cargo uses it for WASM targets)
- The module name in the output (`wasm_calc_module.wasm`) must match the `main` field in `manifest.json`

### Step 6: Build

```bash
# Initialize git (nix flakes require tracked files)
git init
git add -A

# Build
nix build

# Check the output
ls -la result/lib/
# -r-xr-xr-x 1 ... 15945 ... wasm_calc_module.wasm

file result/lib/wasm_calc_module.wasm
# WebAssembly (wasm) binary module version 0x1 (MVP)
```

### Step 7: Test with logoscore

To test, you need two things:

1. A `logoscore` build that includes `logos_host_wasm` (the WASM host binary)
2. The module installed in the directory layout the package manager expects

#### 7.1 Build logoscore with WASM support

The `logos_host_wasm` binary is built by `logos-liblogos` when Wasmtime is available (it's a build dependency). Build `logoscore` with the local `logos-liblogos`:

```bash
nix build path:./repos/logos-logoscore-cli#cli \
  --override-input logos-liblogos path:./repos/logos-liblogos \
  -o /tmp/logoscore-result
```

Verify `logos_host_wasm` is in the closure:

```bash
WASM_HOST=$(nix-store -qR /tmp/logoscore-result \
  | xargs -I{} sh -c 'test -f {}/bin/logos_host_wasm && echo {}/bin/logos_host_wasm' 2>/dev/null \
  | head -1)
echo "WASM host: $WASM_HOST"
```

#### 7.2 Set up the module directory

The package manager expects each module in a subdirectory with a `manifest.json`:

```bash
mkdir -p /tmp/test-modules/wasm_calc_module
cp result/lib/wasm_calc_module.wasm /tmp/test-modules/wasm_calc_module/
cp manifest.json /tmp/test-modules/wasm_calc_module/
```

Resulting structure:

```
/tmp/test-modules/
└── wasm_calc_module/
    ├── manifest.json
    └── wasm_calc_module.wasm
```

#### 7.3 Run with logoscore

```bash
LOGOS_HOST_WASM_PATH="$WASM_HOST" /tmp/logoscore-result/bin/logoscore \
  -m /tmp/test-modules \
  -l wasm_calc_module \
  -c "wasm_calc_module.add(3, 5)" \
  -c "wasm_calc_module.multiply(6, 7)" \
  -c "wasm_calc_module.factorial(10)" \
  -c "wasm_calc_module.fibonacci(20)" \
  --quit-on-finish
```

Expected output:

```
Method call successful. Result: 8
Method call successful. Result: 42
Method call successful. Result: 3628800
Method call successful. Result: 6765
```

> **Why `LOGOS_HOST_WASM_PATH`?** The logoscore-cli flake.nix currently sets `LOGOS_HOST_PATH` for native modules but does not yet set `LOGOS_HOST_WASM_PATH`. The plugin launcher looks for the WASM host binary in three places: (1) the `LOGOS_HOST_WASM_PATH` env var, (2) next to the `logoscore` binary, (3) `../bin/` relative to the modules directory. Until the flake is fixed, the env var is the simplest workaround.

Use `-v` for verbose output to debug loading issues:

```bash
LOGOS_HOST_WASM_PATH="$WASM_HOST" /tmp/logoscore-result/bin/logoscore -v \
  -m /tmp/test-modules -l wasm_calc_module \
  -c "wasm_calc_module.add(3, 5)" --quit-on-finish
```

### Step 8: Package with lgx

```bash
lgx create wasm_calc_module
lgx add wasm_calc_module.lgx -v linux-x86_64 -f result/lib/wasm_calc_module.wasm
lgx add wasm_calc_module.lgx -v darwin-arm64 -f result/lib/wasm_calc_module.wasm
lgx verify wasm_calc_module.lgx
```

Or use the Nix-based bundler (builds the `.lgx` automatically):

```bash
nix build .#lgx
```

---

## Calling a WASM Module from Another Module

WASM modules participate in the same IPC system as native modules. From any Qt module with a `LogosAPI*` pointer:

```cpp
// Raw call (works from any module — native or WASM)
LogosAPIClient* client = logosAPI->getClient("wasm_calc_module");
QVariant result = client->invokeRemoteMethod("wasm_calc_module", "add", 10, 20);
qDebug() << result; // QVariant(qlonglong, 30)

// Check for errors
if (!result.isValid()) {
    qWarning() << "Call failed (unknown method, timeout, or WASM trap)";
}
```

From `logoscore -c` (command line):

```bash
logoscore -m /path/to/modules \
  -l wasm_calc_module,my_other_module \
  -c "wasm_calc_module.add(10, 20)"
```

The caller does not need to know whether the target module is a `.so` plugin or a `.wasm` binary. The IPC transport and authentication are identical.

---

## Cross-Repo Changes That Enable WASM Support

WASM module support required changes across five repositories. This section describes each change in detail.

### logos-liblogos

The bulk of the implementation. Three new files and two modified files.

#### New: `src/logos_host_wasm/logos_host_wasm.cpp`

The WASM host process entry point — analogous to `logos_host` (which loads native Qt plugins). The `main()` function:

1. **Parses arguments** via CLI11: `--name <module_name> --path <wasm_file>`
2. **Receives an auth token** by creating a `QLocalServer` on socket `logos_token_<name>` and waiting up to 10 seconds for the core process to connect and send a UUID
3. **Instantiates `WasmProviderObject`** with the `.wasm` path
4. **Registers on IPC** via `LogosAPI::getProvider()->registerObject(name, wasmProvider)`, which wraps the provider in a `ModuleProxy` and publishes it on the Qt Remote Objects bus
5. **Saves auth tokens** for `"core"` and `"capability_module"` in `TokenManager`
6. **Enters the Qt event loop** to serve incoming remote method calls indefinitely

#### New: `src/logos_host_wasm/wasm_provider_object.h`

Declares `WasmProviderObject`, which inherits `LogosProviderObject` (from logos-cpp-sdk). Key members:

```cpp
class WasmProviderObject : public LogosProviderObject {
    // Each discovered WASM function
    struct WasmFunc {
        wasmtime_func_t func;       // function handle
        wasm_functype_t* type;      // parameter/return type info
        int paramCount;
        int resultCount;
    };

    wasm_engine_t* m_engine;            // Wasmtime engine (manages compilation)
    wasmtime_store_t* m_store;          // Wasmtime store (execution state)
    wasmtime_module_t* m_module;        // compiled module
    wasmtime_instance_t m_instance;     // instantiated module
    QHash<QString, WasmFunc> m_functions;  // exported functions cache
};
```

#### New: `src/logos_host_wasm/wasm_provider_object.cpp`

The implementation, with four key sections:

**`loadModule()`** — Reads the `.wasm` binary, creates a Wasmtime engine, compiles the module to native code, creates a store (no WASI — pure computation), and instantiates the module via a linker. Error handling covers both compilation errors and instantiation traps.

**`discoverExports()`** — Iterates all module exports via `wasmtime_instance_export_nth()`. For each exported function (skipping internal symbols like `memory`, `_start`, `__heap_base`, etc.), it reads the function's type signature, counts parameters and results, and caches the handle in `m_functions`.

**`callMethod()`** — Looks up the function by name, converts `QVariant` arguments to `wasmtime_val_t` based on declared parameter types (i32/i64/f32/f64), calls the function via `wasmtime_func_call()`, and converts the result back to `QVariant`. Handles both errors and runtime traps gracefully.

**`getMethods()`** — Returns a `QJsonArray` describing all exported functions with their names, parameter types, return types, and signatures. This is what `lm` and other introspection tools use (though `lm` currently only works with Qt plugins, not `.wasm` files).

#### Modified: `src/logos_core/plugin_launcher.cpp`

Added WASM detection and host binary resolution:

```cpp
// In PluginLauncher::launch():
bool isWasm = pluginPath.endsWith(".wasm", Qt::CaseInsensitive);
QString hostPath = isWasm
    ? resolveLogosHostWasmPath(pluginsDirs)
    : resolveLogosHostPath(pluginsDirs);
```

Added `resolveLogosHostWasmPath()` which uses `resolveHostBinary("logos_host_wasm", "LOGOS_HOST_WASM_PATH", pluginsDirs)` — checking the env var, then the application directory, then `../bin/` relative to the plugins directory.

#### Modified: `src/logos_core/plugin_registry.cpp`

Added special handling for `.wasm` files during module discovery. When the package manager returns a module whose `mainFilePath` ends in `.wasm`, the registry skips `QPluginLoader` introspection (which would fail on a WASM binary) and registers it directly from manifest metadata:

```cpp
if (mainFilePath.endsWith(".wasm", Qt::CaseInsensitive)) {
    PluginInfo info;
    info.path = mainFilePath;
    // Parse dependencies from manifest JSON
    if (mod.contains("dependencies") && mod["dependencies"].is_array()) {
        for (const auto& dep : mod["dependencies"])
            info.dependencies.append(QString::fromStdString(dep.get<std::string>()));
    }
    m_plugins.insert(name, info);
    continue;  // skip Qt plugin processing
}
```

#### Modified: `src/CMakeLists.txt`

Conditional build of `logos_host_wasm` when Wasmtime is available:

```cmake
find_library(WASMTIME_LIBRARY NAMES wasmtime)
find_path(WASMTIME_INCLUDE_DIR NAMES wasmtime.h)

if(WASMTIME_LIBRARY AND WASMTIME_INCLUDE_DIR)
    add_executable(logos_host_wasm
        logos_host_wasm/logos_host_wasm.cpp
        logos_host_wasm/wasm_provider_object.h
        logos_host_wasm/wasm_provider_object.cpp
    )
    target_link_libraries(logos_host_wasm PRIVATE
        Qt6::Core Qt6::RemoteObjects Qt6::Network
        logos_sdk CLI11::CLI11 ${WASMTIME_LIBRARY}
    )
endif()
```

The `logos_host_wasm` target is also conditionally added to the install targets in the top-level `CMakeLists.txt`.

#### Modified: `nix/default.nix`

Added `pkgs.wasmtime` to `buildInputs` so the Wasmtime C library and headers are available during CMake configuration.

### logos-cpp-sdk

#### `cpp/logos_provider_object.h`

This file defines `LogosProviderObject` — the abstract base class that `WasmProviderObject` extends. It was not modified for WASM support; the existing interface was sufficient:

```cpp
class LogosProviderObject {
public:
    virtual QVariant callMethod(const QString& methodName, const QVariantList& args) = 0;
    virtual bool informModuleToken(const QString& moduleName, const QString& token) = 0;
    virtual QJsonArray getMethods() = 0;
    virtual void setEventListener(EventCallback callback) = 0;
    virtual void init(void* apiInstance) = 0;
    virtual QString providerName() const = 0;
    virtual QString providerVersion() const = 0;
};
```

The key design decision was that `LogosProviderObject` is **not Qt-specific** — it uses `QVariant` for data but doesn't require `Q_OBJECT`, MOC, or `QPluginLoader`. This made it possible to implement a Wasmtime-backed provider without any changes to the SDK.

### logos-package-manager

#### `src/package_manager_lib.cpp`

No WASM-specific changes were needed. The `scanInstalledByTypes()` function already works generically:

1. Scans module directories for subdirectories containing `manifest.json`
2. Reads the `main` field and resolves it to a file path (trying platform variants)
3. Returns the resolved `mainFilePath` — the registry then checks the extension

The `.wasm` extension handling happens entirely in `logos-liblogos` (plugin_registry.cpp). The package manager is extension-agnostic.

### logos-logoscore-cli

#### `flake.nix`

The logoscore-cli flake wraps the binary with environment variables via `qtWrapperArgs`:

```nix
qtWrapperArgs = [
  "--set LOGOS_HOST_PATH ${liblogos}/bin/logos_host"
];
```

**Missing:** A corresponding `--set LOGOS_HOST_WASM_PATH ${liblogos}/bin/logos_host_wasm` entry. This is why the `LOGOS_HOST_WASM_PATH` environment variable must be set manually when testing. This is a known gap that should be fixed.

---

## Reference

### Type Mappings

| WASM | Rust | C | Qt (QVariant) | getMethods() string |
|------|------|---|---------------|---------------------|
| `i32` | `i32` | `int32_t` | `int` | `"int"` |
| `i64` | `i64` | `int64_t` | `qlonglong` | `"qlonglong"` |
| `f32` | `f32` | `float` | `double` (via `float`) | `"float"` |
| `f64` | `f64` | `double` | `double` | `"double"` |
| (none) | `()` | `void` | `QVariant(true)` | `"void"` |

### Function Signature Requirements

For a function to be discoverable by the Logos WASM host:

| Requirement | Example |
|-------------|---------|
| `#[no_mangle]` attribute | Prevents Rust name mangling |
| `pub extern "C"` | C calling convention |
| Scalar parameter types | `i32`, `i64`, `f32`, `f64` only |
| Scalar or void return type | Same four types, or no return |
| No panics across FFI | Use `checked_*` or return error values |

**Valid:**
```rust
#[no_mangle] pub extern "C" fn add(a: i64, b: i64) -> i64 { a + b }
#[no_mangle] pub extern "C" fn pi() -> f64 { std::f64::consts::PI }
#[no_mangle] pub extern "C" fn noop() { }
```

**Invalid (will not work):**
```rust
// String parameters — not supported
pub extern "C" fn greet(name: *const c_char) -> *const c_char { ... }

// Struct return — not a scalar type
pub extern "C" fn get_point() -> Point { ... }
```

### Filtered Exports

These export names are automatically skipped during discovery:

| Export | Reason |
|--------|--------|
| `memory` | WASM linear memory (not a function) |
| `_start` | WASI entry point |
| `_initialize` | WASI initialization |
| `__data_end` | WASM data segment boundary |
| `__heap_base` | WASM heap start |
| `__indirect_function_table` | WASM function table |
| `__*` (any double-underscore prefix) | Internal/compiler-generated symbols |

### Platform Variant Names

The package manager tries these variant names in order when resolving `manifest.json` `main` entries:

| Platform | Primary | Alias | Dev variant |
|----------|---------|-------|-------------|
| Linux x86_64 | `linux-x86_64` | `linux-amd64` | `linux-x86_64-dev` |
| Linux ARM64 | `linux-aarch64` | `linux-arm64` | `linux-aarch64-dev` |
| macOS ARM64 | `darwin-arm64` | `aarch64-darwin` | `darwin-arm64-dev` |
| macOS x86_64 | `darwin-x86_64` | `x86_64-darwin` | `darwin-x86_64-dev` |

For WASM modules, the binary is architecture-independent, so a simple string `main` field is preferred over per-variant entries.

---

## Limitations and Future Work

| Limitation | Details |
|------------|---------|
| **Scalars only** | No string, map, list, or complex type support. Functions can only take and return `i32`, `i64`, `f32`, `f64`. |
| **No WASI** | Modules target `wasm32-unknown-unknown` (pure computation). No filesystem, network, or clock access from WASM. |
| **No `lm` support** | The `lm` module inspector uses `QPluginLoader` and cannot introspect `.wasm` files. Use `logoscore -v` to see discovered methods. |
| **No module-builder template** | `logos-module-builder` has templates for native C++ modules but no WASM template yet. WASM modules must be structured manually. |
| **`LOGOS_HOST_WASM_PATH` workaround** | The `logoscore-cli` flake.nix doesn't set this env var yet. Must be set manually or the binary placed next to `logoscore`. |
| **No events** | `WasmProviderObject` has an `EventCallback` but WASM functions are synchronous and cannot emit events. |
| **Single return value** | WASM functions can return at most one value. Multi-return WASM is not yet supported. |

---

## Troubleshooting

### "Module not found in known plugins: wasm_calc_module"

The package manager didn't discover the module. Check:

1. The module directory structure is correct: `<modules-dir>/<module_name>/manifest.json` + `.wasm` file
2. `manifest.json` has `"type": "core"` (not `"ui"` or other types)
3. The `main` field in `manifest.json` matches the actual `.wasm` filename
4. The `.wasm` file actually exists at the resolved path

### "logos_host_wasm not found"

The WASM host binary isn't where the plugin launcher expects it. Fix:

```bash
# Find it in the nix store
WASM_HOST=$(nix-store -qR /path/to/logoscore-result \
  | xargs -I{} sh -c 'test -f {}/bin/logos_host_wasm && echo {}/bin/logos_host_wasm' 2>/dev/null \
  | head -1)

# Set the env var
export LOGOS_HOST_WASM_PATH="$WASM_HOST"
```

Or build `logos-liblogos` directly and point to it:

```bash
cd repos/logos-liblogos && nix build .#logos-liblogos
export LOGOS_HOST_WASM_PATH="$(pwd)/result/bin/logos_host_wasm"
```

### "WasmProviderObject: compile error"

The `.wasm` binary is invalid or uses unsupported features. Check:

- Built with `--target wasm32-unknown-unknown` (not `wasm32-wasi`)
- The `crate-type` is `["cdylib"]`, not `["rlib"]` or `["lib"]`
- No unsupported WASM proposals are used (the default Wasmtime config is used)

### "WasmProviderObject: call trap"

A runtime trap during function execution. Common causes:

- **Integer overflow** — use `checked_mul()`, `checked_add()`, etc.
- **Division by zero** — WASM traps on `i32.div_s` / `i64.div_s` with zero divisor
- **Unreachable** — Rust `panic!()` compiles to `unreachable` in WASM, which traps
- **Stack overflow** — deep recursion in WASM hits the stack limit

### "Method call returned invalid result"

The method call failed — the module isn't loaded, the method doesn't exist, or IPC timed out. Run with `-v` to see the full debug log.

### Build fails with "cargo build --offline" error

Your Rust code has external crate dependencies. Either:

1. Remove the dependencies (if possible)
2. Use `rustPlatform.buildRustPackage` in your `flake.nix` with a `cargoHash` instead of calling `cargo` directly
