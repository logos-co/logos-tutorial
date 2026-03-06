# Tutorial: Wrapping a C Library as a Logos Module

This tutorial walks you through wrapping a C shared library (`.so` on Linux, `.dylib` on macOS) as a Logos module. By the end, you will have a module that compiles, loads, and responds to method calls via `logoscore`.

**What you'll build:** A `calc_module` that wraps a tiny C calculator library (`libcalc`), exposing arithmetic functions to the Logos platform.

**What you'll learn:**
- How a Logos module wraps a C library
- The role of each file in the module project
- How to build, inspect, and test your module
- How `logoscore` discovers, loads, and calls your module

## Prerequisites

- **Nix** with flakes enabled. Install from [nixos.org](https://nixos.org/download.html), then enable flakes globally:

  ```bash
  # Add to ~/.config/nix/nix.conf:
  experimental-features = nix-command flakes
  ```

- **A C compiler** (gcc or clang) for building the C library. Only needed if you're building the `.so`/`.dylib` yourself rather than using a pre-built library.

- Basic familiarity with C and C++.

---

## Step 1: Create the C Library

We'll create a minimal C library called `libcalc` with four arithmetic functions. In a real project, this would be whatever C library you want to wrap (e.g., a networking library, a crypto library, a codec).

### 1.1 Create the project directory

```bash
mkdir logos-calc-module && cd logos-calc-module
mkdir lib src
```

### 1.2 Write the C header

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

### 1.3 Write the C implementation

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

### 1.4 Build the shared library

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

You should see:

```
T calc_add
T calc_factorial
T calc_fibonacci
T calc_multiply
T calc_version
```

> **Wrapping a third-party library?** If you're wrapping an existing library (e.g., from a system package or a GitHub repo), you don't need to write the C code — just place the pre-built `.so`/`.dylib` and its header file in `lib/`.

---

## Step 2: Create the Logos Module

A Logos module is a **Qt plugin** that wraps your C library functions as `Q_INVOKABLE` methods. You need five files:

```
logos-calc-module/
├── flake.nix          # Nix build configuration (~10 lines)
├── module.yaml        # Module metadata and build settings (~20 lines)
├── CMakeLists.txt     # CMake build file (~20 lines)
├── metadata.json      # Runtime metadata (~10 lines)
├── lib/
│   ├── libcalc.h      # C library header
│   ├── libcalc.c      # C library source
│   └── libcalc.so     # Pre-built shared library
└── src/
    ├── calc_module_interface.h   # Interface declaration
    ├── calc_module_plugin.h      # Plugin header
    └── calc_module_plugin.cpp    # Plugin implementation (wrapping logic)
```

### 2.1 `module.yaml` — Module Configuration

This is the central configuration file. It tells `logos-module-builder` what to build and how.

```yaml
name: calc_module
version: 1.0.0
type: core
category: general
description: "Calculator module wrapping libcalc C library"

dependencies: []

nix_packages:
  build: []
  runtime: []

# This tells the builder that "libcalc" is a pre-built library in lib/
external_libraries:
  - name: calc
    vendor_path: "lib"

cmake:
  find_packages: []
  extra_sources: []
  extra_include_dirs:
    - lib
  extra_link_libraries: []
```

**Key fields explained:**

| Field | What it does |
|-------|-------------|
| `name` | Module name — must be a valid C identifier (used in filenames, method calls) |
| `external_libraries[].name` | Library name — the builder looks for `lib<name>.so` / `lib<name>.dylib` in the directory specified by `vendor_path` |
| `external_libraries[].vendor_path` | Where to find the pre-built library. `"lib"` means the `lib/` directory in your project root |
| `cmake.extra_include_dirs` | Added to the CMake include path so your C++ code can `#include "lib/libcalc.h"` |

### 2.2 `metadata.json` — Runtime Metadata

This file is embedded into the plugin binary by Qt's `Q_PLUGIN_METADATA` macro:

```json
{
  "name": "calc_module",
  "version": "1.0.0",
  "description": "Calculator module wrapping libcalc C library",
  "author": "",
  "type": "core",
  "category": "general",
  "main": "calc_module_plugin",
  "dependencies": []
}
```

### 2.3 `CMakeLists.txt` — Build File

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

# Define the module with its external library dependency
logos_module(
    NAME calc_module
    SOURCES
        src/calc_module_interface.h
        src/calc_module_plugin.h
        src/calc_module_plugin.cpp
    EXTERNAL_LIBS
        calc
)
```

**How `EXTERNAL_LIBS calc` works:** The `logos_module()` CMake function searches `lib/` for `libcalc.so` (Linux) or `libcalc.dylib` (macOS), links it to your plugin, and sets up RPATH so the library is found at runtime.

### 2.4 `flake.nix` — Nix Build Config

```nix
{
  description = "Calculator module - wraps libcalc C library for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    nixpkgs.follows = "logos-module-builder/nixpkgs";
  };

  outputs = { self, logos-module-builder, nixpkgs }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./module.yaml;
    };
}
```

That's it — `mkLogosModule` handles all the Nix complexity (fetching Qt, the SDK, the code generator, setting up include paths, etc.).

### 2.5 `src/calc_module_interface.h` — Interface Declaration

This declares the methods your module exposes. It inherits from `PluginInterface` (provided by the Logos C++ SDK).

```cpp
#ifndef CALC_MODULE_INTERFACE_H
#define CALC_MODULE_INTERFACE_H

#include <QObject>
#include <QString>
#include "interface.h"

class CalcModuleInterface : public PluginInterface
{
public:
    virtual ~CalcModuleInterface() = default;

    Q_INVOKABLE virtual int add(int a, int b) = 0;
    Q_INVOKABLE virtual int multiply(int a, int b) = 0;
    Q_INVOKABLE virtual int factorial(int n) = 0;
    Q_INVOKABLE virtual int fibonacci(int n) = 0;
    Q_INVOKABLE virtual QString libVersion() = 0;
};

#define CalcModuleInterface_iid "org.logos.CalcModuleInterface"
Q_DECLARE_INTERFACE(CalcModuleInterface, CalcModuleInterface_iid)

#endif // CALC_MODULE_INTERFACE_H
```

**Rules for the interface:**
- Every method you want callable by other modules must be `Q_INVOKABLE` and `virtual`
- Supported parameter/return types: `int`, `bool`, `QString`, `QByteArray`, `QVariant`, `QJsonArray`, `QStringList`, `LogosResult`
- The interface ID string (e.g., `"org.logos.CalcModuleInterface"`) must be unique across all modules

### 2.6 `src/calc_module_plugin.h` — Plugin Header

This is the actual plugin class. It inherits from both `QObject` (for Qt's meta-object system) and your interface.

```cpp
#ifndef CALC_MODULE_PLUGIN_H
#define CALC_MODULE_PLUGIN_H

#include <QObject>
#include <QString>
#include "calc_module_interface.h"

// Include the C library header
#include "lib/libcalc.h"

class LogosAPI;

class CalcModulePlugin : public QObject, public CalcModuleInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcModuleInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcModuleInterface PluginInterface)

public:
    explicit CalcModulePlugin(QObject* parent = nullptr);
    ~CalcModulePlugin() override;

    // PluginInterface — required by every module
    QString name() const override { return "calc_module"; }
    QString version() const override { return "1.0.0"; }

    // Called by the Logos host when the module is loaded.
    // NOT marked override — it is invoked reflectively via QMetaObject.
    Q_INVOKABLE void initLogos(LogosAPI* api);

    // CalcModuleInterface — each wraps a libcalc C function
    Q_INVOKABLE int add(int a, int b) override;
    Q_INVOKABLE int multiply(int a, int b) override;
    Q_INVOKABLE int factorial(int n) override;
    Q_INVOKABLE int fibonacci(int n) override;
    Q_INVOKABLE QString libVersion() override;

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
};

#endif // CALC_MODULE_PLUGIN_H
```

**Critical details:**
- `Q_PLUGIN_METADATA(IID ... FILE "metadata.json")` — embeds the metadata into the binary
- `Q_INTERFACES(CalcModuleInterface PluginInterface)` — registers both interfaces with Qt's plugin system
- `initLogos` must be `Q_INVOKABLE` but **not** `override` — the base class `PluginInterface` does not declare it as virtual; the Logos host calls it reflectively via `QMetaObject::invokeMethod`
- `eventResponse` signal is required for event forwarding between modules
- `name()` must return the same string as the `name` field in `module.yaml` and `metadata.json`

### 2.7 `src/calc_module_plugin.cpp` — Plugin Implementation

This is where the wrapping happens. Each method calls the corresponding C function.

```cpp
#include "calc_module_plugin.h"
#include "logos_api.h"
#include <QDebug>

CalcModulePlugin::CalcModulePlugin(QObject* parent)
    : QObject(parent)
{
    qDebug() << "CalcModulePlugin: created";
}

CalcModulePlugin::~CalcModulePlugin()
{
    qDebug() << "CalcModulePlugin: destroyed";
}

void CalcModulePlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
    qDebug() << "CalcModulePlugin: LogosAPI initialized";
}

int CalcModulePlugin::add(int a, int b)
{
    // Call the C library function
    int result = calc_add(a, b);
    qDebug() << "CalcModulePlugin::add" << a << "+" << b << "=" << result;
    return result;
}

int CalcModulePlugin::multiply(int a, int b)
{
    int result = calc_multiply(a, b);
    qDebug() << "CalcModulePlugin::multiply" << a << "*" << b << "=" << result;
    return result;
}

int CalcModulePlugin::factorial(int n)
{
    int result = calc_factorial(n);
    qDebug() << "CalcModulePlugin::factorial" << n << "! =" << result;
    return result;
}

int CalcModulePlugin::fibonacci(int n)
{
    int result = calc_fibonacci(n);
    qDebug() << "CalcModulePlugin::fibonacci fib(" << n << ") =" << result;
    return result;
}

QString CalcModulePlugin::libVersion()
{
    const char* ver = calc_version();
    QString result = QString::fromUtf8(ver);
    qDebug() << "CalcModulePlugin::libVersion" << result;
    return result;
}
```

**The wrapping pattern** is always the same:
1. Call the C function with the arguments
2. Convert the C result to a Qt type if needed (e.g., `const char*` → `QString`)
3. Return the Qt type

---

## Step 3: Build the Module

### 3.1 Initialize the Git repo

Nix flakes require a git repository:

```bash
cd logos-calc-module
git init
git add -A
git commit -m "Initial commit"
```

### 3.2 Build with Nix

```bash
# Build just the plugin library (.so / .dylib)
nix build .#lib

# Build everything (library + generated SDK headers)
nix build
```

The first build takes a while (5-15 minutes) as Nix downloads Qt, the Logos SDK, and other dependencies. Subsequent builds are fast due to caching.

### 3.3 Inspect the output

```bash
ls -la result/lib/
```

You should see two files:

```
calc_module_plugin.so   # Your Logos module plugin
libcalc.so              # The C library (copied alongside)
```

Both files are placed together so the plugin can find the C library at runtime via RPATH.

---

## Step 4: Inspect the Module

### 4.1 Build the `lm` tool

The `lm` CLI tool (from `logos-module`) inspects compiled module binaries:

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

### 4.2 View metadata

```bash
./lm/bin/lm metadata result/lib/calc_module_plugin.so
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

### 4.3 List methods

```bash
./lm/bin/lm methods result/lib/calc_module_plugin.so
```

Output:

```
Plugin Methods:
===============

void eventResponse(QString eventName, QVariantList args)
  Signature: eventResponse(QString,QVariantList)
  Invokable: no

void initLogos(LogosAPI* api)
  Signature: initLogos(LogosAPI*)
  Invokable: yes

int add(int a, int b)
  Signature: add(int,int)
  Invokable: yes

int multiply(int a, int b)
  Signature: multiply(int,int)
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

All five wrapping methods are visible and invokable. The `initLogos` method is automatically called by the Logos host when loading the module.

### 4.4 JSON output

For scripting and CI, use `--json`:

```bash
./lm/bin/lm methods result/lib/calc_module_plugin.so --json
```

```json
[
    {
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

---

## Step 5: Test with `logoscore`

### 5.1 Build logoscore

```bash
nix build 'github:logos-co/logos-liblogos' --out-link ./logos
```

### 5.2 Set up the modules directory

`logoscore` expects modules in subdirectories, each with a `manifest.json`:

```bash
mkdir -p modules/calc_module
cp result/lib/calc_module_plugin.so modules/calc_module/
cp result/lib/libcalc.so modules/calc_module/
```

Create `modules/calc_module/manifest.json`:

```json
{
  "name": "calc_module",
  "version": "1.0.0",
  "description": "Calculator module wrapping libcalc C library",
  "type": "core",
  "main": {
    "linux-aarch64": "calc_module_plugin.so",
    "linux-x86_64": "calc_module_plugin.so",
    "darwin-arm64": "calc_module_plugin.dylib",
    "darwin-x86_64": "calc_module_plugin.dylib"
  },
  "dependencies": []
}
```

The `main` object maps platform variant names to the plugin filename. `logoscore` uses this to find the right binary for your OS and architecture.

### 5.3 Call methods

```bash
# Call add(3, 5)
./logos/bin/logoscore \
  -m ./modules \
  --load-modules calc_module \
  -c "calc_module.add(3, 5)"

# Call factorial(5)
./logos/bin/logoscore \
  -m ./modules \
  --load-modules calc_module \
  -c "calc_module.factorial(5)"

# Call fibonacci(10)
./logos/bin/logoscore \
  -m ./modules \
  --load-modules calc_module \
  -c "calc_module.fibonacci(10)"

# Call libVersion()
./logos/bin/logoscore \
  -m ./modules \
  --load-modules calc_module \
  -c "calc_module.libVersion()"
```

**What happens under the hood:**

1. `logoscore` scans `./modules/` for subdirectories containing `manifest.json`
2. It finds `calc_module` and extracts metadata from the plugin binary
3. It spawns a `logos_host` process that loads `calc_module_plugin.so`
4. `logos_host` calls `initLogos()` on the plugin, providing a `LogosAPI*` for inter-module communication
5. The `-c` command is parsed: module name `calc_module`, method `add`, args `[3, 5]`
6. `logoscore` sends the call to `logos_host` via Qt Remote Objects (IPC)
7. `logos_host` invokes `CalcModulePlugin::add(3, 5)` which calls `calc_add(3, 5)` from libcalc
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

## Step 6: Package for Distribution (Optional)

### 6.1 Build the `lgx` tool

```bash
nix build 'github:logos-co/logos-package#lgx' --out-link ./lgx
```

### 6.2 Create a package

```bash
# Create an empty LGX package
./lgx/bin/lgx create calc_module.lgx --name calc_module

# Add the Linux variant
./lgx/bin/lgx add-variant calc_module.lgx \
  --variant linux-aarch64 \
  --files result/lib/

# Verify the package
./lgx/bin/lgx verify calc_module.lgx
```

On another machine, install with the Logos Package Manager:

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm
./pm/bin/lgpm --modules-dir ./modules install --file calc_module.lgx
```

---

## Common Wrapping Patterns

### Wrapping C functions with opaque pointers

Many C libraries use opaque pointers (handles) for state management:

```c
// C API
typedef struct db_ctx db_ctx_t;
db_ctx_t* db_open(const char* path);
int db_get(db_ctx_t* ctx, const char* key, char* buf, int buf_len);
void db_close(db_ctx_t* ctx);
```

Store the handle in your plugin class:

```cpp
class DbModulePlugin : public QObject, public DbModuleInterface
{
    // ...
private:
    db_ctx_t* m_ctx = nullptr;

public:
    Q_INVOKABLE bool open(const QString& path) {
        m_ctx = db_open(path.toUtf8().constData());
        return m_ctx != nullptr;
    }

    Q_INVOKABLE QString get(const QString& key) {
        if (!m_ctx) return QString();
        char buf[4096];
        int len = db_get(m_ctx, key.toUtf8().constData(), buf, sizeof(buf));
        if (len < 0) return QString();
        return QString::fromUtf8(buf, len);
    }

    ~DbModulePlugin() {
        if (m_ctx) db_close(m_ctx);
    }
};
```

### Wrapping C callbacks

C libraries often use callbacks for async operations:

```c
typedef void (*event_cb)(int code, const char* msg, void* user_data);
void lib_set_callback(void* ctx, event_cb cb, void* user_data);
```

Use a static method as the callback, passing `this` as `user_data`:

```cpp
class MyPlugin : public QObject, public MyInterface
{
    // ...
    static void c_callback(int code, const char* msg, void* user_data) {
        auto* self = static_cast<MyPlugin*>(user_data);
        // Forward to Qt signal (thread-safe)
        emit self->eventResponse("lib_event",
            QVariantList() << code << QString::fromUtf8(msg));
    }

    Q_INVOKABLE void startListening() {
        lib_set_callback(m_ctx, c_callback, this);
    }
};
```

### Wrapping C libraries that allocate strings

If the C library returns allocated strings that must be freed:

```cpp
Q_INVOKABLE QString getData() {
    char* c_str = lib_get_data(m_ctx);  // Library allocates
    QString result = QString::fromUtf8(c_str);
    lib_free_string(c_str);              // Library deallocates
    return result;
}
```

### String conversion reference

| C type | Qt type | C → Qt | Qt → C |
|--------|---------|--------|--------|
| `const char*` | `QString` | `QString::fromUtf8(c_str)` | `str.toUtf8().constData()` |
| `const char*` (binary) | `QByteArray` | `QByteArray(data, len)` | `ba.data()`, `ba.size()` |
| `int` | `int` | direct | direct |
| `bool` / `int` | `bool` | `result != 0` | direct |
| `void*` | (store in member) | — | — |

---

## Advanced: Wrapping a Library from a Flake Input

Instead of pre-building the library and placing it in `lib/`, you can have Nix fetch and build it from source. This is useful for libraries hosted on GitHub.

### flake.nix with external library input

```nix
{
  description = "Module wrapping libfoo from GitHub";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    nixpkgs.follows = "logos-module-builder/nixpkgs";

    # Fetch the library source (non-flake)
    libfoo-src = {
      url = "github:example/libfoo";
      flake = false;
    };
  };

  outputs = { self, logos-module-builder, nixpkgs, libfoo-src }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./module.yaml;

      # Pass the fetched source to the builder
      externalLibInputs = {
        foo = libfoo-src;
      };
    };
}
```

### module.yaml for flake input

```yaml
name: foo_module
version: 1.0.0
type: core
description: "Module wrapping libfoo"

external_libraries:
  - name: foo
    flake_input: "github:example/libfoo"
    build_command: "make shared"
    output_pattern: "build/libfoo.*"

cmake:
  extra_include_dirs:
    - lib
```

**Key difference:** The `externalLibInputs` key in flake.nix (`foo`) must match the `name` field in `external_libraries` (`foo`). The builder will:
1. Clone the source from the flake input
2. Run `build_command` (`make shared`)
3. Search for output files matching `output_pattern`
4. Copy the resulting `.so`/`.dylib` and headers to `lib/`
5. Proceed with the normal module build

### For Go libraries

If the external library is written in Go with C bindings (`cgo`):

```yaml
external_libraries:
  - name: mygolib
    flake_input: "github:example/mygolib"
    go_build: true
    output_pattern: "libmygolib.*"
```

Setting `go_build: true` enables the Go toolchain and sets `CGO_ENABLED=1`.

---

## Real-World Example: logos-libp2p-module

The [logos-libp2p-module](https://github.com/logos-co/logos-libp2p-module) is a production module that wraps the `nim-libp2p` library (compiled to a C shared library). Key files:

- **`flake.nix`** — Uses `externalLibInputs` to fetch the nim-libp2p C bindings from a GitHub flake
- **`module.yaml`** — Declares `nim_libp2p` as an external library with `go_build: false`
- **`src/plugin.cpp`** — Wraps ~40 C functions (`libp2p_new`, `libp2p_start`, `libp2p_connect`, `libp2p_dial`, `libp2p_gossipsub_subscribe`, etc.) as `Q_INVOKABLE` methods
- **`tests/`** — Qt test suite that exercises every wrapped function

It follows the exact same pattern as this tutorial, just at a larger scale.

---

## Troubleshooting

### `initLogos` marked 'override', but does not override

```
error: 'void MyPlugin::initLogos(LogosAPI*)' marked 'override', but does not override
```

**Fix:** Remove the `override` keyword from `initLogos`. The base `PluginInterface` class does not declare it as virtual. The Logos host calls it reflectively via `QMetaObject::invokeMethod`. Declare it as:

```cpp
Q_INVOKABLE void initLogos(LogosAPI* api);  // No override!
```

### Library not found at runtime

```
Cannot load library calc_module_plugin.so: libcalc.so: cannot open shared object file
```

**Fix:** Ensure `libcalc.so` is in the same directory as `calc_module_plugin.so`. The build system sets RPATH to `$ORIGIN` (Linux) / `@loader_path` (macOS) so the plugin looks for libraries in its own directory.

### Plugin not discovered by logoscore

**Check:**
1. The module is in a **subdirectory** of the modules dir (e.g., `modules/calc_module/`)
2. The subdirectory contains a `manifest.json` with a valid `main` object
3. The platform key in `main` matches your OS/arch (e.g., `linux-aarch64`, `darwin-arm64`)

### First build is slow

The first `nix build` downloads Qt 6, the Logos C++ SDK, the code generator, and other dependencies. This is a one-time cost — subsequent builds use the Nix cache and are fast (usually under 30 seconds).

### Symbol not found errors

If you get "undefined symbol" errors for your C library functions:
1. Verify the `.so`/`.dylib` is in `lib/` before building
2. Verify the header has `extern "C"` guards
3. Check the symbols are exported: `nm -D lib/libcalc.so | grep calc`
