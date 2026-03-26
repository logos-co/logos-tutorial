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

## Step 1: Scaffold the Module Project

Before writing any C code, scaffold the Logos module project using the official template. This gives you the correct `flake.nix`, `metadata.json`, directory structure, and build configuration out of the box.

### 1.1 Create the project using the module builder template

```bash
# For a module that wraps an external C library:
mkdir logos-calc-module && cd logos-calc-module
nix flake init -t github:logos-co/logos-module-builder#with-external-lib

# Or for a plain module (no external library):
# nix flake init -t github:logos-co/logos-module-builder
```

This generates the skeleton files (`flake.nix`, `metadata.json`, `CMakeLists.txt`, etc.) pre-configured for the logos-module-builder. You then customize them for your specific library.

> **Alternative approach:** You can also create the C library as a separate project, build it there, then copy the resulting `.so`/`.dylib` and header files into the module's `lib/` directory. This can be cleaner for larger libraries with their own build systems.

### 1.2 Create the lib directory

```bash
mkdir -p lib 
```

### 1.3 Write the C header

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

### 1.4 Write the C implementation

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

### 1.5 Build the shared library

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

## Step 2: Configure the Logos Module

The template from Step 1.1 generated skeleton files with placeholder names (`external_lib`, `example_lib`). Now rename and customize them for your library. You need to edit **every generated file**:

| File | What to change |
|------|---------------|
| `metadata.json` | Module name, description, library name, include dirs |
| `CMakeLists.txt` | Project name, module name, source filenames, library name |
| `flake.nix` | Description (and dependency inputs if needed) |
| `src/*.h`, `src/*.cpp` | Rename files, replace class/method names, add your wrapping logic |

After renaming and editing, your project should look like this:

```
logos-calc-module/
├── flake.nix          # Nix build configuration (~10 lines)
├── metadata.json      # Module metadata, build settings, and runtime config (~25 lines)
├── CMakeLists.txt     # CMake build file (~20 lines)
├── lib/
│   ├── libcalc.h      # C library header
│   ├── libcalc.c      # C library source
│   └── libcalc.so     # Pre-built shared library
└── src/
    ├── calc_module_interface.h   # Interface declaration
    ├── calc_module_plugin.h      # Plugin header
    └── calc_module_plugin.cpp    # Plugin implementation (wrapping logic)
```

### 2.1 `metadata.json` — Module Configuration

> **Edit:** Change `name`, `description`, `main`, `nix.external_libraries[].name`, and `nix.cmake.extra_include_dirs` to match your module and library.

This is the single source of truth for your module. It is embedded into the plugin binary by Qt's `Q_PLUGIN_METADATA` macro (for runtime metadata), read by `logos-module-builder` to configure the Nix build, used by CMake to resolve external dependencies and link libraries (via the `nix` section), and used by `nix-bundle-lgx` to generate the LGX manifest.

```json
{
  "name": "calc_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "Calculator module wrapping libcalc C library",
  "main": "calc_module_plugin",
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


| Field                                       | What it does                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                                      | Module name — must be a valid C identifier (used in filenames, method calls)                                                                                                                                                                                                                                        |
| `nix.external_libraries[].name`             | Library name **without the `lib` prefix** — the builder looks for `lib<name>.so` / `lib<name>.dylib` in the directory specified by `vendor_path`. So `name: calc` matches the file `libcalc.so` / `libcalc.dylib`. This follows the standard Unix library naming convention where `-lcalc` links against `libcalc`. |
| `nix.external_libraries[].vendor_path`      | Where to find the pre-built library. `"lib"` means the `lib/` directory in your project root                                                                                                                                                                                                                        |
| `nix.cmake.extra_include_dirs`              | Added to the CMake include path so your C++ code can `#include "lib/libcalc.h"`                                                                                                                                                                                                                                     |

### 2.2 `CMakeLists.txt` — Build File

> **Edit:** Change `project()` name, `NAME`, `SOURCES` filenames, and `EXTERNAL_LIBS` to match your module and library.

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

The template generates this with default names (e.g., `external_lib`). You **must** update:

- **`project()`** — rename to match your module (e.g., `CalcModulePlugin`)
- **`NAME`** — your module name (must match `name` in `metadata.json`, e.g., `calc_module`)
- **`SOURCES`** — your renamed source files
- **`EXTERNAL_LIBS`** — names of external libraries to link (must match `nix.external_libraries[].name` in `metadata.json`)

The `if/elseif/else` block above it is boilerplate — don't change it.

> **Common mistake:** If `NAME` doesn't match `name` in `metadata.json`, the build will succeed but the install phase will fail because it looks for `<name>_plugin.dylib` based on `metadata.json`.

**How `EXTERNAL_LIBS calc` works:** The `logos_module()` CMake function searches `lib/` for `libcalc.so` (Linux) or `libcalc.dylib` (macOS), links it to your plugin, and sets up RPATH so the library is found at runtime.

### 2.3 `flake.nix` — Nix Build Config

> **Edit:** Change `description`. Add flake inputs here if your module depends on other modules or fetches a library from source (see [Advanced: Wrapping a Library from a Flake Input](#advanced-wrapping-a-library-from-a-flake-input)).

```nix
{
  description = "Calculator module - wraps libcalc C library for Logos";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    nix-bundle-lgx.url = "github:logos-co/nix-bundle-lgx";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

That's it — `mkLogosModule` handles all the Nix complexity (fetching Qt, the SDK, the code generator, setting up include paths, etc.). Note that `configFile` points to `metadata.json` (the single source of truth) and `flakeInputs = inputs` passes all flake inputs to the builder so that dependencies declared in `metadata.json` are resolved automatically.

> **Naming flake inputs:** When adding module dependencies, the flake input attribute name **must match** the `name` field in that dependency's `metadata.json`. For example, if you depend on a module whose `metadata.json` has `"name": "waku_module"`, your flake input must be `waku_module.url = "github:logos-co/logos-waku-module"`. The URL can point to any repo, but the attribute name is how the builder resolves dependencies.

### 2.4 `src/calc_module_interface.h` — Interface Declaration

> **Edit:** Rename from `external_lib_interface.h`. Replace the class name, interface ID, include guard, and declare your module's methods as `Q_INVOKABLE virtual` pure-virtual functions.

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

### 2.5 `src/calc_module_plugin.h` — Plugin Header

> **Edit:** Rename from `external_lib_plugin.h`. Replace class name, interface references, `name()`/`version()` return values, and declare your `Q_INVOKABLE` wrapper methods. Add `#include` for your C library header.

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

};

#endif // CALC_MODULE_PLUGIN_H
```

**Critical details:**

- `Q_PLUGIN_METADATA(IID ... FILE "metadata.json")` — embeds the metadata into the binary
- `Q_INTERFACES(CalcModuleInterface PluginInterface)` — registers both interfaces with Qt's plugin system
- `initLogos` must be `Q_INVOKABLE` but **not** `override` — the base class `PluginInterface` does not declare it as virtual; the Logos host calls it reflectively via `QMetaObject::invokeMethod`
- `eventResponse` signal is required for event forwarding between modules
- `name()` must return the same string as the `name` field in `metadata.json`
- **No `m_logosAPI` member variable** — the `LogosAPI`* pointer is stored in the global `logosAPI` variable defined in `liblogos`, not in a class member. See the `initLogos` implementation below.

### 2.6 `src/calc_module_plugin.cpp` — Plugin Implementation

> **Edit:** Rename from `external_lib_plugin.cpp`. Replace the placeholder implementations with actual calls to your C library functions.

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
    // IMPORTANT: Use the global `logosAPI` variable from liblogos, NOT a class member.
    // `logosAPI` is defined in the Logos SDK headers and is used by the API
    // internally. Storing the pointer in a local `m_logosAPI` member will NOT work.
    logosAPI = api;
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
2. Convert the C result to a Qt type if needed (e.g., `const char`* → `QString`)
3. Return the Qt type

---

## Step 3: Build the Module

### 3.1 Initialize the Git repo

Nix flakes require a git repository:

```bash
cd logos-calc-module
git init
git add -A
```

### 3.2 Build with Nix

```bash
# Build just the plugin library (.so / .dylib)
nix build '.#lib'

# Build everything (library + generated SDK headers)
nix build
```

> **Quoting matters:** Use `'.#lib'` (with quotes) rather than bare `nix build .#lib`. Some shells (especially zsh) may interpret the `#` as a comment character, causing the command to silently build the wrong thing or fail.

The first build takes a while (5-15 minutes) as Nix downloads Qt, the Logos SDK, and other dependencies. Subsequent builds are fast due to caching.

### 3.3 Inspect the output

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

## Step 4: Inspect the Module

### 4.1 Build the `lm` tool

The `lm` CLI tool (from `logos-module`) inspects compiled module binaries:

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

### 4.2 View metadata

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

### 4.3 List methods

```bash
# Linux
./lm/bin/lm methods result/lib/calc_module_plugin.so

# macOS
./lm/bin/lm methods result/lib/calc_module_plugin.dylib
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
# Linux
./lm/bin/lm methods result/lib/calc_module_plugin.so --json

# macOS
./lm/bin/lm methods result/lib/calc_module_plugin.dylib --json
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
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

### 5.2 Set up the modules directory

`logoscore` expects modules in subdirectories, each with a `manifest.json`. Rather than copying files and writing the manifest manually, use the Nix derivation to create an LGX package and install it with the package manager:

```bash
# Bundle the module into an LGX package
nix build '.#lgx'

# Install it into a modules directory using the Logos Package Manager
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm
mkdir -p modules
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

### 5.3 Call methods

Start the daemon and call methods:

```bash
# Start logoscore daemon with modules directory
./logos/bin/logoscore -D -m ./modules &

# Load the module
./logos/bin/logoscore load-module calc_module

# Call methods
./logos/bin/logoscore call calc_module add 3 5
./logos/bin/logoscore call calc_module factorial 5
./logos/bin/logoscore call calc_module fibonacci 10
./logos/bin/logoscore call calc_module libVersion

# Stop the daemon when done
./logos/bin/logoscore stop
```

> For inline (legacy) mode and other logoscore options, see the [Developer Guide -- Running with logoscore](logos-developer-guide.md#51-running-with-logoscore).

  **What happens under the hood:**

1. `logoscore` scans `./modules/` for subdirectories containing `manifest.json`
2. It finds `calc_module` and extracts metadata from the plugin binary
3. It spawns a `logos_host` process that loads `calc_module_plugin.so`
4. `logos_host` calls `initLogos()` on the plugin, providing a `LogosAPI*` for inter-module communication
5. The call command is parsed: module name `calc_module`, method `add`, args `[3, 5]`
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

The LGX package created in Step 5.2 is a **local** package — its libraries still reference `/nix/store` paths, so it only works on the machine that built it. To create a **portable** package that can be distributed to other machines:

```bash
nix build '.#lgx-portable'
```

Portable LGX packages are fully self-contained with no `/nix/store` references at runtime. These are the packages used by the Logos App Package Manager UI and published to [logos-modules](https://github.com/logos-co/logos-modules) releases.

To create a **dual** package containing both dev and portable variants (works with any basecamp build):

```bash
nix build '.#lgx-dual'
```

> For more bundling options (standalone bundler syntax, cross-platform packaging), see the [Developer Guide — Bundling with nix-bundle-lgx](logos-developer-guide.md#32-bundling-with-nix-bundle-lgx).

To install a portable package on another machine:

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm
./pm/bin/lgpm --modules-dir ./modules install --file calc_module.lgx
```

> **Note:** Local builds of `logoscore` / `logos-basecamp` (via `nix build`) expect **local** `.lgx` packages. Portable builds (via `nix build '.#bin-bundle-dir'`, `.#bin-appimage`, or `.#bin-macos-app`) expect **portable** `.lgx` packages. See the [logos-basecamp README](https://github.com/logos-co/logos-basecamp/blob/master/README.md) for details.

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


| C type                 | Qt type           | C → Qt                     | Qt → C                     |
| ---------------------- | ----------------- | -------------------------- | -------------------------- |
| `const char*`          | `QString`         | `QString::fromUtf8(c_str)` | `str.toUtf8().constData()` |
| `const char*` (binary) | `QByteArray`      | `QByteArray(data, len)`    | `ba.data()`, `ba.size()`   |
| `int`                  | `int`             | direct                     | direct                     |
| `bool` / `int`         | `bool`            | `result != 0`              | direct                     |
| `void*`                | (store in member) | —                          | —                          |


---

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

---

## Real-World Example: logos-libp2p-module

The [logos-libp2p-module](https://github.com/logos-co/logos-libp2p-module) is a production module that wraps the `nim-libp2p` library (compiled to a C shared library). Key files:

- `**flake.nix**` — Uses `externalLibInputs` to fetch the nim-libp2p C bindings from a GitHub flake
- `**metadata.json**` — Declares `nim_libp2p` as an external library with `go_build: false` in the `nix` section
- `**src/plugin.cpp**` — Wraps ~40 C functions (`libp2p_new`, `libp2p_start`, `libp2p_connect`, `libp2p_dial`, `libp2p_gossipsub_subscribe`, etc.) as `Q_INVOKABLE` methods
- `**tests/**` — Qt test suite that exercises every wrapped function

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

**Fix:** Ensure `libcalc.so` / `libcalc.dylib` is in the same directory as the plugin. The build system sets RPATH to `$ORIGIN` (Linux) / `@loader_path` (macOS) so the plugin looks for libraries in its own directory.

### `initLogos` stores API pointer in wrong variable

If inter-module calls or API features silently fail, check that `initLogos` assigns to the **global** `logosAPI` variable (defined in the Logos SDK / liblogos), not to a class member like `m_logosAPI`:

```cpp
// CORRECT — uses the global variable from liblogos
void MyPlugin::initLogos(LogosAPI* api)
{
    logosAPI = api;
}

// WRONG — stores in a local member, API calls won't work
void MyPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
}
```

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

