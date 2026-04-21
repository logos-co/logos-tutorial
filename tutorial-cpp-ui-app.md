# Tutorial Part 3: Building a C++ UI Module (Process-Isolated)

This is Part 3 of the Logos module tutorial series. In [Part 2](tutorial-qml-ui-app.md) you built a QML-only UI plugin. Now you'll build a **ui_qml module with a C++ backend** — the backend runs in a separate `ui-host` process while the QML view loads in the host app (basecamp / standalone).

**What you'll build:** A `calc_ui_cpp` module with:

- A `.rep` file defining the remote interface (slots + properties)
- A C++ backend plugin that inherits from the generated `SimpleSource` base class
- A QML view that calls the backend via a typed replica using `logos.watch()`
- Process isolation: backend crashes can't bring down the host app

**Why C++ backend over QML-only?**

|                   | QML-only (Part 2)                                                 | C++ backend (Part 3)                    |
| ----------------- | ----------------------------------------------------------------- | --------------------------------------- |
| Compilation       | None                                                              | CMake + Qt                              |
| Process isolation | No (QML runs in-process)                                          | Yes (C++ in separate `ui-host` process) |
| Backend calls     | `logos.callModule()` / `logos.callModuleAsync()` to other modules | `LogosModules` typed SDK in C++         |
| Type safety       | Args travel as `QVariant`                                         | C++ types preserved                     |
| QML ↔ backend     | Direct bridge                                                     | Qt Remote Objects (typed replica)       |
| `.rep` file       | Not needed                                                        | Required — defines the remote interface |

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` with the shared library built (`.so` on Linux, `.dylib` on macOS in `logos-calc-module/lib/`)
- Nix with flakes enabled

---

## Architecture

```
  logos-basecamp / logos-standalone-app
  ┌─────────────────────────────────────────────┐
  │                                             │
  │   QML View (Main.qml)                      │
  │     readonly property var backend:          │
  │       logos.module("calc_ui_cpp")           │
  │     logos.watch(backend.add(1,2))│
  │          │                                  │
  │          │  Qt Remote Objects (socket)      │
  └──────────┼──────────────────────────────────┘
             │
  ui-host process (separate)
  ┌──────────┼──────────────────────────────────┐
  │          ▼                                  │
  │   CalcUiCppPlugin (backend)                 │
  │     : CalcUiCppSimpleSource                 │
  │     : CalcUiCppViewPluginBase               │
  │     int add(int a, int b) {                 │
  │       return m_logos->calc_module.add(a,b); │
  │     }                                       │
  │          │                                  │
  │          │  LogosModules typed SDK           │
  │          ▼                                  │
  │   calc_module (loaded in ui-host)           │
  └─────────────────────────────────────────────┘
```

The `.rep` file declares the interface. At build time, Qt's `repc` compiler generates:

- **`CalcUiCppSimpleSource`** — base class the backend inherits from
- **`CalcUiCppReplica`** — typed replica the QML view uses
- **`calc_ui_cpp_replica_factory`** — separate plugin that the host loads to create typed replicas

---

## Step 1: Scaffold

```bash
mkdir logos-calc-ui-cpp && cd logos-calc-ui-cpp
nix flake init -t github:logos-co/logos-module-builder#ui-qml-backend
git init && git add -A
```

This creates the template. We'll customize it for our calculator.

---

## Step 2: metadata.json

```json
{
  "name": "calc_ui_cpp",
  "version": "1.0.0",
  "type": "ui_qml",
  "category": "tools",
  "description": "Calculator C++ UI — QML view with process-isolated backend",
  "main": "calc_ui_cpp_plugin",
  "view": "qml/Main.qml",
  "icon": "icons/calc.png",
  "dependencies": ["calc_module"],

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [] }
  }
}
```

Key fields:

- `"type": "ui_qml"` — tells the builder this is a QML view module
- `"main": "calc_ui_cpp_plugin"` — the backend Qt plugin library (without extension)
- `"view": "qml/Main.qml"` — the QML entry point
- `"dependencies": ["calc_module"]` — core modules the backend calls

---

## Step 3: The `.rep` File

Create `src/calc_ui_cpp.rep`:

```rep
class CalcUiCpp
{
    PROP(QString status READWRITE)

    SLOT(int add(int a, int b))
    SLOT(int multiply(int a, int b))
    SLOT(int factorial(int n))
    SLOT(int fibonacci(int n))
    SLOT(QString libVersion())
}
```

This is the **single source of truth** for the remote interface. `repc` generates:

- `rep_calc_ui_cpp_source.h` — `CalcUiCppSimpleSource` with virtual slots the backend overrides
- `rep_calc_ui_cpp_replica.h` — `CalcUiCppReplica` with typed methods and auto-synced properties

**PROP** values auto-sync from backend to QML replica. **SLOT** return values are delivered as `QRemoteObjectPendingReply` — use `logos.watch()` in QML to get them as JS Promises.

---

## Step 4: CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.14)
project(CalcUiCppPlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found. Set LOGOS_MODULE_BUILDER_ROOT.")
endif()

logos_module(
    NAME calc_ui_cpp
    REP_FILE src/calc_ui_cpp.rep
    SOURCES
        src/calc_ui_cpp_interface.h
        src/calc_ui_cpp_plugin.h
        src/calc_ui_cpp_plugin.cpp
)
```

`REP_FILE` tells `logos_module()` to:

1. Run `repc` to generate source/replica headers
2. Generate `LogosViewPluginBase` (typed remoting base class)
3. Build a separate `calc_ui_cpp_replica_factory` shared library

---

## Step 5: C++ Backend Plugin

### `src/calc_ui_cpp_plugin.h`

```cpp
#pragma once

#include <QString>
#include <QVariantList>
#include "calc_ui_cpp_interface.h"
#include "LogosViewPluginBase.h"
#include "rep_calc_ui_cpp_source.h"

class LogosAPI;
class LogosModules;

class CalcUiCppPlugin : public CalcUiCppSimpleSource,
                        public CalcUiCppInterface,
                        public CalcUiCppViewPluginBase
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcUiCppInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    // Slots from .rep — override the generated virtuals
    int add(int a, int b) override;
    int multiply(int a, int b) override;
    int factorial(int n) override;
    int fibonacci(int n) override;
    QString libVersion() override;

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
    LogosModules* m_logos = nullptr;
};
```

Three base classes:

- **`CalcUiCppSimpleSource`** — generated from `.rep`, provides the typed source for Qt Remote Objects
- **`CalcUiCppInterface`** — standard Logos plugin interface (`name()`, `version()`)
- **`CalcUiCppViewPluginBase`** — generated, provides `setBackend()` and `enableRemoting()`

### `src/calc_ui_cpp_plugin.cpp`

```cpp
#include "calc_ui_cpp_plugin.h"
#include "logos_api.h"
#include "logos_sdk.h"

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent)
    : CalcUiCppSimpleSource(parent) {}

CalcUiCppPlugin::~CalcUiCppPlugin() { delete m_logos; }

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
    m_logos = new LogosModules(api);
    // Register this object as the Remote Objects source
    setBackend(this);
}

int CalcUiCppPlugin::add(int a, int b)
{
    return m_logos->calc_module.add(a, b);
}

int CalcUiCppPlugin::multiply(int a, int b)
{
    return m_logos->calc_module.multiply(a, b);
}

int CalcUiCppPlugin::factorial(int n)
{
    return m_logos->calc_module.factorial(n);
}

int CalcUiCppPlugin::fibonacci(int n)
{
    return m_logos->calc_module.fibonacci(n);
}

QString CalcUiCppPlugin::libVersion()
{
    return m_logos->calc_module.libVersion();
}
```

Key points:

- Constructor calls `CalcUiCppSimpleSource(parent)` — not `QObject(parent)`
- `initLogos()` calls `setBackend(this)` to register with the Remote Objects host
- Slots return values directly — they travel back to the QML replica via Qt Remote Objects
- `m_logos->calc_module.add(a, b)` uses the generated typed SDK (type-safe, no QVariant)

---

## Step 6: QML View

Create `src/qml/Main.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts


Item {
    id: root

    property string result: ""
    property string errorText: ""

    // Typed replica of the backend running in ui-host
    readonly property var backend: logos.module("calc_ui_cpp")

    // "status" property from the .rep — auto-synced via Qt Remote Objects
    readonly property string status: backend ? backend.status : ""

    function callCalc(method, args) {
        if (!backend) {
            root.errorText = "Backend not available"
            return
        }
        root.errorText = ""
        root.result = "..."
        // logos.watch() wraps the pending reply in a JS Promise
        logos.watch(backend[method].apply(backend, args),
            function(value) { root.result = String(value) },
            function(error) { root.errorText = String(error) }
        )
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Text {
            text: "Calculator (C++ backend)"
            font.pixelSize: 20
            color: "#ffffff"
        }

        RowLayout {
            spacing: 12

            TextField {
                id: inputA; placeholderText: "a"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }
            TextField {
                id: inputB; placeholderText: "b"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }
            Button {
                text: "Add"
                onClicked: root.callCalc("add", [parseInt(inputA.text) || 0,
                                                  parseInt(inputB.text) || 0])
            }
            Button {
                text: "Multiply"
                onClicked: root.callCalc("multiply", [parseInt(inputA.text) || 0,
                                                       parseInt(inputB.text) || 0])
            }
        }

        Rectangle {
            Layout.fillWidth: true; height: 56
            color: root.errorText ? "#3d1a1a" : "#1a2d1a"
            radius: 8
            Text {
                anchors.centerIn: parent
                text: root.errorText || root.result || "Press a button"
                color: root.errorText ? "#f85149" : "#56d364"
                font.pixelSize: 15
            }
        }

        Text {
            text: "Backend status: " + root.status
            color: "#8b949e"; font.pixelSize: 13
        }
    }
}
```

Key patterns:

- `logos.module("calc_ui_cpp")` — gets the typed replica (auto-synced properties)
- `backend.status` — PROP from `.rep`, updates automatically
- `logos.watch(backend.add(1, 2), ...)` — SLOT return value as JS Promise
- ``— required for`logos.watch()`

---

## Step 7: flake.nix

```nix
{
  description = "Calculator C++ UI plugin — QML view with process-isolated backend";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # Option A: point to a remote repo (for CI or when calc_module is published)
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";

    # Option B: point to your local checkout (for local development)
    # calc_module.url = "path:../logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

The `calc_module` input attribute name must match the dependency name in `metadata.json`. The URL can be:

- **`github:`** — fetches from a remote GitHub repo. Use for CI or when `calc_module` is published.
- **`path:`** — points to a local directory on disk (e.g., `path:../logos-calc-module`). Use during local development.

> **Important:** Whichever URL scheme you use, `calc_module` must be built with its shared library (`.so` on Linux, `.dylib` on macOS) present in `lib/`. If it's missing, the nix build will fail with linker errors. See [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library).

`mkLogosQmlModule` handles everything: compiles the C++ backend (because `main` is set), bundles the QML view, generates LGX packages, and wires up `nix run`.

---

## Step 8: Build and Run

First, make sure your local `calc_module` is built and its `.so`/`.dylib` is present in `lib/` (see [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library)):

```bash
ls ../logos-calc-module/lib/libcalc.so    # Linux
ls ../logos-calc-module/lib/libcalc.dylib  # macOS
```

Then build and run. Choose the approach that matches your `flake.nix` setup:

```bash
git add -A

# If flake.nix uses path:../logos-calc-module — just run directly:
nix run

# If flake.nix uses github: — override to use your local checkout:
nix run --override-input calc_module path:../logos-calc-module

# Or from the workspace:
./scripts/ws run logos-calc-ui-cpp --local logos-calc-ui-cpp logos-calc-module
```

---

## Step 9: How the Pieces Connect

1. `nix build` → compiles the C++ plugin + replica factory, bundles QML view
2. `nix run` → launches `logos-standalone-app` which:
   - Loads `calc_module` (dependency)
   - Spawns a `ui-host` child process with `calc_ui_cpp_plugin.so`
   - `ui-host` calls `initLogos()` → `setBackend(this)` → `enableRemoting(host)`
   - Backend is now accessible over a local socket
3. Host app loads `calc_ui_cpp_replica_factory.dylib` → creates a typed replica
4. QML gets the replica via `logos.module("calc_ui_cpp")`
5. `backend.add(1, 2)` → Qt Remote Objects sends call to ui-host → backend runs → returns result
6. `backend.status` auto-syncs whenever the backend calls `setStatus(...)`

---

## Step 10: UI Integration Tests (Optional)

Add automated UI tests using the [logos-qt-mcp](https://github.com/logos-co/logos-qt-mcp) test framework. Just create `.mjs` files in `tests/` and `logos-module-builder` auto-wires `nix build .#integration-test`.

Create `tests/ui-tests.mjs`:

```javascript
import { resolve } from "node:path";

// CI sets LOGOS_QT_MCP automatically; for interactive use: nix build .#test-framework -o result-mcp
const root =
  process.env.LOGOS_QT_MCP ||
  new URL("../result-mcp", import.meta.url).pathname;
const { test, run } = await import(
  resolve(root, "test-framework/framework.mjs")
);

test("calc_ui_cpp: loads and shows title", async (app) => {
  await app.waitFor(
    async () => {
      await app.expectTexts(["UI Example (C++ backend)"]);
    },
    { timeout: 15000, interval: 500, description: "UI to load" },
  );
});

test("calc_ui_cpp: shows connection status", async (app) => {
  await app.expectTexts(["Connecting to backend..."]);
});

test("calc_ui_cpp: add button visible", async (app) => {
  await app.expectTexts(["Add"]);
});

run();
```

```bash
git add tests/

# Hermetic CI test
nix build .#integration-test -L

# Interactive
nix build .#test-framework -o result-mcp
nix run .                     # app with inspector on :3768
node tests/ui-tests.mjs       # in another terminal
```

---

## Comparison: .rep Interface Patterns

| Pattern          | .rep declaration                     | Backend C++                                 | QML usage                                                              |
| ---------------- | ------------------------------------ | ------------------------------------------- | ---------------------------------------------------------------------- |
| **Return value** | `SLOT(int add(int a, int b))`        | `int add(...) override { return ...; }`     | `logos.watch(backend.add(1,2), cb)`                                    |
| **Property**     | `PROP(QString status READWRITE)`     | `setStatus("Ready")` (inherited)            | `backend.status` (auto-syncs)                                          |
| **Signal**       | `SIGNAL(errorOccurred(QString msg))` | `emit errorOccurred("fail")`                | `Connections { target: backend; function onErrorOccurred(msg) {...} }` |
| **Model**        | (use Q_PROPERTY on backend)          | `Q_PROPERTY(QAbstractItemModel* items ...)` | `logos.model("calc_ui_cpp", "items")`                                  |

---

## Next Steps

- Add more `.rep` properties/signals for richer UI state
- Use `logos.model()` for list views backed by `QAbstractItemModel`
- Package as `.lgx` for distribution: `nix build .#lgx`
- See [logos-package-manager-ui](https://github.com/logos-co/logos-package-manager-ui) for a production example
