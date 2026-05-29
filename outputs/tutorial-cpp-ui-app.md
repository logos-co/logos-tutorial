# Tutorial Part 3: Building a C++ UI Module (Process-Isolated)

This is Part 3 of the Logos module tutorial series. In [Part 2](tutorial-qml-ui-app.md) you built a QML-only UI plugin. Now you'll build a **ui_qml module with a C++ backend** — the backend runs in a separate `ui-host` process while the QML view loads in the host app (basecamp / standalone).

**What you'll build:** A `calc_ui_cpp` module with:

- A `.rep` file defining the remote interface (slots)
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

## Prerequisites

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

## Step 1: Scaffold

Create a new directory and initialise it from the C++ backend UI template:

`mkdir logos-calc-ui-cpp && cd logos-calc-ui-cpp`

```bash
nix flake init -t github:logos-co/logos-module-builder#ui-qml-backend
```

This creates the template. We'll customize it for our calculator.

```bash
git init && git add -A
```

---

## Step 2: `metadata.json`

Replace the template contents with your plugin's details:

```json
{
  "name": "calc_ui_cpp",
  "version": "1.0.0",
  "type": "ui_qml",
  "category": "tools",
  "description": "Calculator C++ UI — QML view with process-isolated backend for calc_module",
  "main": "calc_ui_cpp_plugin",
  "view": "qml/Main.qml",
  "icon": "icons/calc.png",
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

Create the icon directory and add a placeholder icon (displayed in the `logos-basecamp` sidebar when the module is loaded):

```bash
mkdir -p icons
# Copy any PNG here — or generate a 64×64 placeholder:
echo "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAmElEQVR4nO3QMREAIBDAsFeEN3ziCWRkoEP2XmedfX82OkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAO0BN/SiO/PatoIAAAAASUVORK5CYII=" | base64 -d > icons/calc.png
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
    SLOT(int add(int a, int b))
    SLOT(int multiply(int a, int b))
    SLOT(int factorial(int n))
    SLOT(int fibonacci(int n))
    SLOT(QString libVersion())
}
```

This is the **single source of truth** for the remote interface. `repc` generates:

- `rep_calc_ui_cpp_source.h` — `CalcUiCppSimpleSource` with virtual slots the backend overrides
- `rep_calc_ui_cpp_replica.h` — `CalcUiCppReplica` with typed methods

**SLOT** return values are delivered as `QRemoteObjectPendingReply` — use `logos.watch()` in QML to get them as JS Promises. You can also declare **PROP** entries (e.g. `PROP(QString status READWRITE)`) which auto-sync from the backend to the QML replica.

---

## Step 4: Interface header

The scaffolded template creates a set of `ui_example` files (`src/ui_example.rep`, `src/ui_example_interface.h`, `src/ui_example_plugin.{h,cpp}`). We replace them with `calc_ui_cpp` equivalents, so remove the example sources first — leaving them around with mismatched class/IID names just invites build errors or plugin-load failures at runtime:

```bash
rm -f src/ui_example.rep src/ui_example_interface.h src/ui_example_plugin.h src/ui_example_plugin.cpp
```

Now create `src/calc_ui_cpp_interface.h`:

```cpp
#ifndef CALC_UI_CPP_INTERFACE_H
#define CALC_UI_CPP_INTERFACE_H

#include <QObject>
#include <QString>
#include "interface.h"

class CalcUiCppInterface : public PluginInterface
{
public:
    virtual ~CalcUiCppInterface() = default;
};

#define CalcUiCppInterface_iid "org.logos.CalcUiCppInterface"
Q_DECLARE_INTERFACE(CalcUiCppInterface, CalcUiCppInterface_iid)

#endif // CALC_UI_CPP_INTERFACE_H
```

Your plugin header should then include `calc_ui_cpp_interface.h` and use:

- `Q_PLUGIN_METADATA(IID CalcUiCppInterface_iid FILE "metadata.json")`
- `Q_INTERFACES(CalcUiCppInterface)`

If the interface filename or IID symbol doesn't match, you'll typically get build errors (missing header/symbol) or plugin-load failures at runtime.

---

## Step 5: `CMakeLists.txt`

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
2. Generate `CalcUiCppViewPluginBase` (typed remoting base class)
3. Build a separate `calc_ui_cpp_replica_factory` shared library

---

## Step 6: C++ Backend Plugin

### 6.1 `src/calc_ui_cpp_plugin.h`

```cpp
#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QString>
#include <QVariantList>
#include "calc_ui_cpp_interface.h"
#include "LogosViewPluginBase.h"
#include "rep_calc_ui_cpp_source.h"

class LogosAPI;
class LogosModules;

// Inherits CalcUiCppSimpleSource (generated from calc_ui_cpp.rep) so
// enableRemoting() can publish the typed source and QML replicas get
// auto-synced properties + callable slots.
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

    // Slots from calc_ui_cpp.rep — return values directly. The QML replica
    // receives QRemoteObjectPendingReply; use logos.watch() in QML to get the value.
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

#endif // CALC_UI_CPP_PLUGIN_H
```

Three base classes:

- **`CalcUiCppSimpleSource`** — generated from `.rep`, provides the typed source for Qt Remote Objects
- **`CalcUiCppInterface`** — standard Logos plugin interface (`name()`, `version()`)
- **`CalcUiCppViewPluginBase`** — generated, provides `setBackend()` and `enableRemoting()`

### 6.2 `src/calc_ui_cpp_plugin.cpp`

```cpp
#include "calc_ui_cpp_plugin.h"
#include "logos_api.h"
#include "logos_sdk.h"

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : CalcUiCppSimpleSource(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() { delete m_logos; }

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    if (m_logos) return;
    m_logosAPI = api;
    m_logos = new LogosModules(api);
    // Register this object as the Remote Objects source so the QML replica
    // can see its properties and call its slots.
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

## Step 7: QML View

Create `src/qml/Main.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

    // Typed replica of the backend running in ui-host (generated from calc_ui_cpp.rep).
    readonly property var backend: logos.module("calc_ui_cpp")

    // logos.watch() delivers the result of a replica slot call via callbacks.
    // No QtRemoteObjects import needed — the bridge handles it.
    function callCalc(method, args) {
        if (!backend) {
            root.errorText = "Backend not available"
            return
        }
        root.errorText = ""
        root.result = "..."
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
            text: "Logos Calculator (C++ backend)"
            font.pixelSize: 20
            color: "#ffffff"
            Layout.alignment: Qt.AlignHCenter
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputA
                placeholderText: "a"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            TextField {
                id: inputB
                placeholderText: "b"
                Layout.preferredWidth: 80
                validator: IntValidator {}
            }

            Button {
                text: "Add"
                onClicked: root.callCalc("add", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
            }

            Button {
                text: "Multiply"
                onClicked: root.callCalc("multiply", [parseInt(inputA.text) || 0, parseInt(inputB.text) || 0])
            }
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField {
                id: inputN
                placeholderText: "n"
                Layout.preferredWidth: 80
                validator: IntValidator { bottom: 0 }
            }

            Button {
                text: "Factorial"
                onClicked: root.callCalc("factorial", [parseInt(inputN.text) || 0])
            }

            Button {
                text: "Fibonacci"
                onClicked: root.callCalc("fibonacci", [parseInt(inputN.text) || 0])
            }

            Button {
                text: "libcalc version"
                onClicked: root.callCalc("libVersion", [])
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: root.errorText.length > 0 ? "#3d1a1a" : "#1a2d1a"
            radius: 8

            Text {
                anchors.centerIn: parent
                text: root.errorText.length > 0 ? root.errorText
                        : (root.result.length > 0 ? root.result : "Enter values and press a button")
                color: root.errorText.length > 0 ? "#f85149" : "#56d364"
                font.pixelSize: 15
            }
        }

        Item { Layout.fillHeight: true }
    }
}
```

Key patterns:

- `logos.module("calc_ui_cpp")` — gets the typed replica (auto-synced properties)
- `logos.watch(backend.add(1, 2), ...)` — SLOT return value as JS Promise
- The `logos` object is injected by the host at runtime — no `QtRemoteObjects` import needed

---

## Step 8: Use the Logos Design System in your QML

The QML you load above runs inside the host (`logos-basecamp` / `logos-standalone-app`), which already has `logos-design-system` on the QML import path. Use its themed components rather than rolling your own visuals — your module gets the polished look automatically as the design system evolves.

```qml
import Logos.Theme
import Logos.Controls
import Logos.Icons        // optional shared icon assets

LogosButton {
    text: qsTr("Add")
    onClicked: root.callCalc("add", [parseInt(inputA.text) || 0,
                                     parseInt(inputB.text) || 0])
}

LogosTextField {
    id: inputA
    placeholderText: qsTr("a")
}

Rectangle {
    color: Theme.palette.backgroundSecondary
    radius: Theme.spacing.radiusSmall
    LogosText { text: qsTr("Result"); color: Theme.palette.text }
}
```

**Discover what's available** by running the storybook:

```bash
cd repos/logos-design-system && nix run
```

The sidebar splits components into:

- **Controls** — designed per Figma, production-ready (`LogosButton`, `LogosBadge`, `LogosCheckbox`, `LogosComboBox`, `LogosIconButton`, `LogosPaginator`, `LogosSearchBar`, `LogosTabBar`, `LogosTable`, `LogosText`, `LogosTextField`, `LogosToolTip`, …).
- **Controls (not designed)** — placeholders with stable APIs but unstyled visuals (`LogosDialog`, `LogosDrawer`, `LogosScrollView`, `LogosSpinner`, `LogosTextArea`, `LogosSwitch`, …). You can ship with them; they'll get the polished look applied later without you having to change your QML.

**Theme tokens** (use these instead of hex literals or magic font sizes):

- `Theme.palette.*` — `background`, `backgroundSecondary`, `surface`, `text`, `textSecondary`, `border`, `primary`, `success`, `warning`, `error`, `info`, `hover`, `pressed`, …
- `Theme.spacing.*` — `tiny`, `small`, `medium`, `large`, `xlarge`, `xxlarge`, `radiusSmall`, `radiusMedium`, `radiusLarge`
- `Theme.typography.*` — `pageTitleText` (36), `titleText` (30), `panelTitleText` (24), `subtitleText` (16), `primaryText` (14), `secondaryText` (12); `weightRegular` / `weightMedium` / `weightBold`; `publicSans`
- `Logos.Icons.LogosIcons.*` — `arrowLeft`, `arrowRight`, `refresh`, `install`, `trash`, `more`, `search`, …

**Feedback and contributions**

Feel free to report bugs, file feature requests, or contribute components / theme tokens upstream — all welcome at `logos-co/logos-design-system`. The same fix lifts every consumer, so upstreaming is the most impactful path. If you can sketch the public API you'd like to use in a feature request, it makes review and implementation much faster.

---

## Step 9: `flake.nix`

The template already wires everything up. Update the description and point `calc_module` at your dependency:

```nix
{
  description = "Calculator C++ UI plugin for Logos - QML view with process-isolated backend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";

    # Points at your local calc_module checkout. This is a placeholder —
    # you lock it to your actual path in the next step with
    # `nix flake update --override-input` (see "Lock and build" below).
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

The `calc_module` input attribute name must match the dependency name in `metadata.json`.

The placeholder `path:/path/to/your/calc_module` is **not** meant to be edited by hand — Nix won't let a `flake.nix` input use a relative path like `../logos-calc-module` (it's evaluated from a sandboxed copy, so `..` escapes it). Instead you point it at your real checkout **once** via `--override-input` in the next step, which records the resolved absolute path in `flake.lock`. After that, plain `nix run` / `nix build` use the locked path with no override needed.

- **`path:`** (used here) — a local directory on disk. Best for developing `calc_module` and its UI side by side, no network.
- **`github:`** — fetches `calc_module` from a remote repo instead (for CI, or once it's published to its own repo), e.g. `calc_module.url = "github:your-org/your-calc-module";`.

> **Important:** Whichever URL scheme you use, `calc_module` must be built with its shared library (`.so` on Linux, `.dylib` on macOS) present in `lib/`. If it's missing, the nix build will fail with linker errors. See [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library).

`mkLogosQmlModule` handles everything: compiles the C++ backend (because `main` is set), bundles the QML view, generates LGX packages, and wires up `nix run`.

---

## Step 10: Build and Run

First, make sure your local `calc_module` is built and its shared library is present in `lib/` (see [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library)):

### 10.1 Ensure `calc_module` is built

```bash
ls ../logos-calc-module/lib/libcalc.so    # Linux
ls ../logos-calc-module/lib/libcalc.dylib  # macOS
```

If the file is missing, build it first (as covered in [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library)):

```bash
cd ../logos-calc-module/lib
gcc -shared -fPIC -o libcalc.so libcalc.c     # Linux
# gcc -shared -fPIC -o libcalc.dylib libcalc.c  # macOS
cd ../../logos-calc-ui-cpp
```

### 10.2 Lock and build

Stage your files, then lock `calc_module` to your local Part 1 checkout. The `--override-input` resolves `../logos-calc-module` to an absolute path and records it in `flake.lock`, replacing the placeholder from `flake.nix`:

```bash
git add -A
```

```bash
nix flake update --override-input calc_module path:../logos-calc-module
```

```bash
git add flake.lock
```

Now that the lock pins the real path, plain `nix run` works — no override needed on subsequent commands:

```bash
nix run
```

### 10.3 Launch and verify the UI

Launch the app and confirm the view loads with all of its controls. The backend runs in a separate `ui-host` process; clicking **Add** sends the call over Qt Remote Objects and the result comes back through `logos.watch()`.

```bash
nix run .
```

The result `8` comes from `calc_module.add(3, 5)` executed in the C++ backend — proof the full path (QML replica → Qt Remote Objects → ui-host backend → typed SDK → `calc_module`) works end to end.

---

## Step 11: Live reloading QML with `DEV_QML_PATH`

For QML iteration, point `DEV_QML_PATH` at the directory that contains your view entry's **basename** (from `metadata.json` `"view"`). This tutorial sets `"view": "qml/Main.qml"`, so the directory must contain `Main.qml` (here: `src/qml/`):

```bash
DEV_QML_PATH=$PWD/src/qml nix run .
```

When `DEV_QML_PATH` is set, `logos-standalone-app` loads QML from your source tree at runtime instead of the installed copy — so edits to `Main.qml` (and any QML under that tree) are picked up on the next relaunch without you having to re-sync files.

**Important — what this does *not* skip.** `nix run` always re-evaluates the flake and rehashes the source tree before launching. By default `src = ./.` includes every tracked file, including `*.qml` — so:

- **Any source change, including QML edits, rebuilds the plugin** before the app starts. `DEV_QML_PATH` only kicks in *after* the build is done; it doesn't shortcut the rebuild itself.
- **C++ / `.rep` / `metadata.json` / CMake changes** rebuild as normal.
- The flake-evaluation overhead on each `nix run` is fixed and unavoidable while invoking through nix.

For the absolute fastest loop (no nix involvement after the first build), do the build once and run the resulting binary directly:

```bash
# Build once — populates result/ in the nix store
nix build .

# Subsequent runs: invoke the bundled standalone wrapper directly,
# skipping nix entirely. DEV_QML_PATH still redirects QML loading.
DEV_QML_PATH=$PWD/src/qml ./result/bin/run-logos-standalone-ui
```

(Adjust the binary name to whatever `ls result/bin/` shows on your build.)

> **Naming:** Only `DEV_QML_PATH` is honored by `logos-standalone-app`. See `repos/logos-standalone-app/README.md`.

> This does not work with `logos-basecamp` — Basecamp loads QML plugins from its own install tree, so source edits are not picked up until you rebuild and reinstall the `.lgx`.

---

## Step 12: How the Pieces Connect

1. `nix build` → compiles the C++ plugin + replica factory, bundles QML view
2. `nix run` → launches `logos-standalone-app` which:
   - Loads `calc_module` (dependency)
   - Spawns a `ui-host` child process with `calc_ui_cpp_plugin.so`
   - `ui-host` calls `initLogos()` → `setBackend(this)` → `enableRemoting(host)`
   - Backend is now accessible over a local socket
3. Host app loads `calc_ui_cpp_replica_factory.dylib` → creates a typed replica
4. QML gets the replica via `logos.module("calc_ui_cpp")`
5. `backend.add(1, 2)` → Qt Remote Objects sends call to ui-host → backend runs → returns result

---

## Step 13: UI Integration Tests

Add automated UI tests using the [logos-qt-mcp](https://github.com/logos-co/logos-qt-mcp) test framework. Just create `.mjs` files in `tests/` and `logos-module-builder` auto-wires `nix build .#integration-test`.

Tests connect to the QML inspector inside `logos-standalone-app` and can find elements, click buttons, verify text, and take screenshots.

### 13.1 Create a test file

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
      await app.expectTexts(["Logos Calculator (C++ backend)"]);
    },
    { timeout: 15000, interval: 500, description: "UI to load" },
  );
});

test("calc_ui_cpp: operation buttons visible", async (app) => {
  await app.expectTexts(["Add", "Multiply", "Factorial", "Fibonacci"]);
});

run();
```

### 13.2 Run the tests

```bash
git add tests/
```

```bash
# Hermetic CI test
nix build .#integration-test -L
```

The `integration-test` output launches `logos-standalone-app` with `QT_QPA_PLATFORM=offscreen` (no display needed), connects to the QML inspector, and runs all `.mjs` files in `tests/`.

To run tests interactively (against an already-running app):

```bash
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

## Next Steps

- Add more `.rep` properties/signals for richer UI state
- Use `logos.model()` for list views backed by `QAbstractItemModel`
- Package as `.lgx` for distribution: `nix build .#lgx`
- **Use the Logos Design System** in your QML — see [Step 8](#step-8-use-the-logos-design-system-in-your-qml). Browse components in the storybook (`cd repos/logos-design-system && nix run`); file issues at `logos-co/logos-design-system`.
- See [logos-package-manager-ui](https://github.com/logos-co/logos-package-manager-ui) for a production example
