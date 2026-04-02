# Tutorial Part 3: Building a C++ UI Module

This is Part 3 of the Logos module tutorial series. In [Part 2](tutorial-qml-ui-app.md) you built a QML UI plugin. Now you'll build a **C++ view module plugin** that provides `Q_INVOKABLE` methods called from QML via `logos.callModuleAsync()`.

**What you'll build:** A `calc_ui_cpp` view module plugin with:

- A QML view (`Main.qml`) declared in `metadata.json` via the `"view"` field
- `Q_INVOKABLE` C++ methods that call `calc_module` through the generated typed SDK
- QML that calls those methods asynchronously via `logos.callModuleAsync("calc_ui_cpp", ...)`

**Why C++ over QML-only?**

| | QML plugin (Part 2) | C++ UI plugin (Part 3) |
|---|---|---|
| Compilation | No | Yes (CMake) |
| Backend calls | Via `logos.callModule()` IPC bridge to other modules | Via `LogosModules` typed SDK in C++ |
| Type safety | Weak — all args travel as `QVariant` | Strong — C++ types preserved |
| QML view | Declared via `"view"` in metadata | Same — declared via `"view"` in metadata |

The C++ plugin provides type-safe calls via generated SDK wrappers — `int` arguments stay `int` all the way to the module without relying on runtime coercion. The QML view calls back into the plugin's own methods via `logos.callModuleAsync()`.

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module`
- Nix with flakes enabled

---

## How It Works

```
+--------------------+  logos.callModuleAsync()  +--------------------+
|   Main.qml         | -----------------------> |   calc_ui_cpp      |
|   (QML view)       |                          |   C++ plugin       |
+--------------------+                          |   add(int, int)    |
                                                |   multiply(...)    |
                                                +--------------------+
                                                         |
                                          LogosModules   |  typed SDK call
                                                         v
                                                +--------------------+
                                                |   calc_module      |
                                                |   C++ plugin       |
                                                |   add(int, int)    |
                                                +--------------------+
```

The plugin declares a `"view": "qml/Main.qml"` in `metadata.json`. The host app loads this QML view and provides a `logos` context object. QML calls `logos.callModuleAsync("calc_ui_cpp", "add", [3, 5], callback)` which invokes the plugin's `Q_INVOKABLE add(int, int)` method. That method in turn calls `calc_module` through the generated `LogosModules` typed SDK.

---

## Step 1: Scaffold

```bash
mkdir logos-calc-ui-cpp && cd logos-calc-ui-cpp
nix flake init -t github:logos-co/logos-module-builder/tutorial-v1#ui-module
git init && git add -A
```

> **Note:** The generated `flake.nix` uses an unpinned `logos-module-builder` URL. Replace it with the pinned version shown in [Step 9](#step-9-flakenix) to ensure reproducible builds.

This gives you:

```
logos-calc-ui-cpp/
├── flake.nix
├── metadata.json
├── CMakeLists.txt
├── interfaces/
│   └── IComponent.h
└── src/
    ├── ui_example_interface.h
    ├── ui_example_plugin.h
    └── ui_example_plugin.cpp
```

Rename the source files to match your module:

```bash
mv src/ui_example_interface.h src/calc_ui_cpp_interface.h
mv src/ui_example_plugin.h    src/calc_ui_cpp_plugin.h
mv src/ui_example_plugin.cpp  src/calc_ui_cpp_plugin.cpp
```

---

## Step 2: `metadata.json`

`metadata.json` is the single source of truth — it contains both the runtime metadata (embedded into the plugin binary by Qt) and the build configuration (read by `logos-module-builder` via the `nix` section).

The `"view"` field tells the host app which QML file to load as the module's UI. The path is relative to the module's install directory.

```json
{
  "name": "calc_ui_cpp",
  "version": "1.0.0",
  "type": "ui",
  "category": "tools",
  "description": "Calculator C++ UI — widget frontend for calc_module",
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

Create the icon directory and add a placeholder icon. The icon is displayed in the `logos-basecamp` sidebar when the module is loaded:

```bash
mkdir -p icons
# Copy any PNG here — or generate a 64×64 placeholder:
echo "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAeklEQVR4nO3PUQkAIBTAwFfPdtazjSH8OITBAtxm7fN1wwUNaEEDWtCAFjSgBQ1oQQNa0IAWNKAFDWhBA1rQgBY0oAUNaEEDWtCAFjSgBQ1oQQNa0IAWNKAFDWhBA1rQgBY0oAUNaEEDWtCAFjSgBQ1oQQNa0IAWPHYBic8hlloAWpEAAAAASUVORK5CYII=" | base64 -d > icons/calc.png
```

> **Naming convention:** Each entry in `dependencies` must match the `name` field in that module's own `metadata.json`. When adding a dependency as a flake input, the **input attribute name** must also match — e.g., `calc_module.url = "github:logos-co/logos-tutorial/tutorial-v1?dir=logos-calc-module"`. The URL can point to any repo, but the attribute name is how the builder resolves dependencies.

---

## Step 3: `CMakeLists.txt`

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
    SOURCES
        src/calc_ui_cpp_interface.h
        src/calc_ui_cpp_plugin.h
        src/calc_ui_cpp_plugin.cpp
)
```

No extra `find_package` or `target_link_libraries` needed — the view module pattern uses the host app's QML engine, so the plugin itself does not need Qt Quick or Qt Widgets dependencies.

---

## Step 4: Interface Header (`src/calc_ui_cpp_interface.h`)

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

The template also scaffolds `interfaces/IComponent.h` — the widget interface that `logos-basecamp` uses to load C++ UI plugins. You don't need to modify this file:

```cpp
// interfaces/IComponent.h (scaffolded by the template — do not modify)
#pragma once

#include <QObject>
#include <QWidget>
#include <QtPlugin>

class LogosAPI;

class IComponent {
public:
    virtual ~IComponent() = default;
    virtual QWidget* createWidget(LogosAPI* logosAPI = nullptr) = 0;
    virtual void destroyWidget(QWidget* widget) = 0;
};

#define IComponent_iid "com.logos.component.IComponent"
Q_DECLARE_INTERFACE(IComponent, IComponent_iid)
```

---

## Step 5: Plugin Header (`src/calc_ui_cpp_plugin.h`)

The plugin exposes `Q_INVOKABLE` methods that the QML view calls via `logos.callModuleAsync()`. Each method delegates to `calc_module` through the generated `LogosModules` typed SDK.

```cpp
#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QObject>
#include <QString>
#include <QVariantList>
#include <IComponent.h>
#include "calc_ui_cpp_interface.h"

class LogosAPI;
class LogosModules;

class CalcUiCppPlugin : public QObject, public CalcUiCppInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID IComponent_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface PluginInterface IComponent)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    Q_INVOKABLE int add(int a, int b);
    Q_INVOKABLE int multiply(int a, int b);
    Q_INVOKABLE int factorial(int n);
    Q_INVOKABLE int fibonacci(int n);
    Q_INVOKABLE QString libVersion();

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
    LogosModules* m_logos = nullptr;
};

#endif // CALC_UI_CPP_PLUGIN_H
```

---

## Step 6: Plugin Implementation (`src/calc_ui_cpp_plugin.cpp`)

Each `Q_INVOKABLE` method delegates to `calc_module` via the generated `LogosModules` typed SDK. The `initLogos()` method is called by the host and provides the `LogosAPI*` used to construct `LogosModules`.

```cpp
#include "calc_ui_cpp_plugin.h"
#include "logos_api.h"
#include "logos_sdk.h"

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : QObject(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() { delete m_logos; }

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
    m_logos = new LogosModules(api);
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

### How the generated SDK works

When `metadata.json` declares `"dependencies": ["calc_module"]` and `calc_module` is passed as a flake input via `flakeInputs`, the build system runs `logos-cpp-generator` before compilation. This produces:

- `logos_sdk.h` / `logos_sdk.cpp` — the `LogosModules` umbrella class with one typed member per dependency
- `calc_module_api.h` / `calc_module_api.cpp` — the per-module wrapper included by `logos_sdk.h`

`LogosModules` is constructed with a `LogosAPI*` and provides a member named after each declared dependency (snake_case). All IPC routing happens inside the generated code — your plugin just calls methods directly:

```cpp
m_logos->calc_module.add(3, 5)   // typed: int add(int, int) over IPC
```

---

## Step 7: QML View (`src/qml/Main.qml`)

Create the QML view file. The `logos` context object is provided by the host app and exposes `callModuleAsync()` for cross-process method calls.

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

    function callCalc(method, args) {
        root.result = "..."
        root.errorText = ""
        logos.callModuleAsync("calc_ui_cpp", method, args, function(r) {
            root.result = r
        })
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
                onClicked: root.callCalc("add", [parseInt(inputA.text), parseInt(inputB.text)])
            }

            Button {
                text: "Multiply"
                onClicked: root.callCalc("multiply", [parseInt(inputA.text), parseInt(inputB.text)])
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
                onClicked: root.callCalc("factorial", [parseInt(inputN.text)])
            }

            Button {
                text: "Fibonacci"
                onClicked: root.callCalc("fibonacci", [parseInt(inputN.text)])
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

The key difference from Part 2's QML-only plugin: here the QML calls `logos.callModuleAsync("calc_ui_cpp", ...)` which routes to this plugin's own `Q_INVOKABLE` methods. Those methods then call `calc_module` through the typed C++ SDK — so you get type safety on the backend while keeping the QML view pattern.

---

## Step 8: `flake.nix`

Since `metadata.json` declares `"type": "ui"`, `mkLogosModule` automatically wires up `apps.default` (i.e. `nix run`) for free — no manual `apps` block or `logosStandalone` parameter required. The standalone app runner is bundled with `logos-module-builder`.

**Important — `flakeInputs`:** Because `metadata.json` declares `"dependencies": ["calc_module"]`, the build system runs `logos-cpp-generator` before compiling your C++ sources. The generator introspects `calc_module`'s built plugin to produce `logos_sdk.h` / `logos_sdk.cpp` (and per-module `calc_module_api.h` / `calc_module_api.cpp`). These are the files your plugin includes as `#include "logos_sdk.h"`. For this to work, `calc_module` must be available as a built Nix package at code-generation time — that is what `flakeInputs` provides (the builder discovers dependency inputs by matching their names against the `dependencies` array in `metadata.json`). Without it, the build fails with `'logos_sdk.h' file not found`.

```nix
{
  description = "Calculator C++ UI plugin for Logos - widget frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/tutorial-v1";
    calc_module.url = "github:logos-co/logos-tutorial/tutorial-v1?dir=logos-calc-module";
  };

  outputs = inputs@{ logos-module-builder, calc_module, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

Because `metadata.json` declares `"type": "ui"`, `mkLogosModule` automatically wires up `apps.default`. It stages the compiled plugin alongside `metadata.json` and any icon files into a Nix store directory, bundles all module dependencies (direct and transitive) from their LGX packages, then produces a shell script that calls `logos-standalone-app` with that directory — exactly what `nix run` executes. All required backend modules are self-contained; no external setup is needed.

---

## Step 9: Build and Test

### 9.1 Build

```bash
git add -A
nix flake update
git add flake.lock
nix build --override-input calc_module path:../logos-calc-module
```

Inspect the output with `lm` (the module inspector from `logos-module`):

```bash
nix build 'github:logos-co/logos-module/tutorial-v1#lm' --out-link ./lm-cli

# Linux
./lm-cli/bin/lm ./result/lib/calc_ui_cpp_plugin.so

# macOS
# ./lm-cli/bin/lm ./result/lib/calc_ui_cpp_plugin.dylib
```

You should see `add`, `multiply`, `factorial`, `fibonacci`, and `libVersion` in the methods list.

### 9.2 UI only (layout preview)

```bash
nix run .
```

The view opens. No backend connected yet, so button clicks will show "..." while waiting for a response.

> **When do you need `--override-input`?** `calc_module.url` in `flake.nix` points to the published GitHub URL. If your local `logos-calc-module` has unpushed changes or differs from what is on GitHub, you must use `--override-input calc_module path:../logos-calc-module` so nix uses your local copy. If your `calc_module` is already pushed and matches the GitHub URL, you can run `nix build` / `nix run` without the override. This is the same mechanism `ws build --local` / `ws build --auto-local` uses throughout the workspace.

### 9.3 Full functionality (with modules)

The standalone app automatically bundles and loads all module dependencies declared in `metadata.json`. To test with your local `calc_module` from Part 1:

```bash
nix run . --override-input calc_module path:../logos-calc-module
```

Clicking **Add**, **Multiply**, **Factorial**, or **Fibonacci** now calls the real module.

> **When do you need `--override-input`?** `calc_module.url` in `flake.nix` points to the published GitHub URL. If your local `logos-calc-module` has unpushed changes or differs from what is on GitHub, you must use `--override-input calc_module path:../logos-calc-module` so nix uses your local copy. If your `calc_module` is already pushed and matches the GitHub URL, you can run `nix build` / `nix run` without the override. This is the same mechanism `ws build --local` / `ws build --auto-local` uses throughout the workspace.

---

## Step 10: Load in `logos-basecamp`

### 10.1 Create LGX packages

Use `--out-link` to avoid overwriting the `result` symlink:

```bash
# Package calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx' --out-link result-lgx
nix build '.#lgx-portable' --out-link result-lgx-portable

# Package the C++ UI plugin
cd ../logos-calc-ui-cpp
nix build '.#lgx' --out-link result-lgx
nix build '.#lgx-portable' --out-link result-lgx-portable
```

> For more bundling options (standalone bundler syntax, cross-platform packaging), see the [Developer Guide — Bundling with nix-bundle-lgx](logos-developer-guide.md#32-bundling-with-nix-bundle-lgx).

### 10.2 Build and run logos-basecamp

Build logos-basecamp, launch it once to preinstall its bundled modules, then install your modules.

> **Note:** `logos-basecamp` does not accept `--modules-dir` or `--ui-plugins-dir` CLI flags. It manages its own data directory and preinstalls bundled modules (main_ui, package_manager, etc.) on first launch.

```bash
# Build logos-basecamp
nix build 'github:logos-co/logos-basecamp/tutorial-v1' -o basecamp-result

# Launch once to preinstall bundled modules, then close it
./basecamp-result/bin/logos-basecamp
```

Basecamp creates its data directory on first launch. To find where it is, check the log output for `plugins directory` or look for the directory that contains `modules/` and `plugins/` subdirectories:

```bash
# macOS (typical path, may vary):
ls ~/Library/Application\ Support/Logos/

# Linux (typical path, may vary):
ls ~/.local/share/Logos/
```

The dev build directory is named `LogosBasecampDev` (portable builds use `LogosBasecamp`).

Install your modules using `lgpm`. First, set `BASECAMP_DIR` to your platform's path:

```bash
# macOS:
BASECAMP_DIR="$HOME/Library/Application Support/Logos/LogosBasecampDev"

# Linux:
BASECAMP_DIR="$HOME/.local/share/Logos/LogosBasecampDev"
```

```bash
# Build lgpm CLI
nix build 'github:logos-co/logos-package-manager/tutorial-v1#cli' --out-link ./pm

# Install core module
./pm/bin/lgpm --modules-dir "$BASECAMP_DIR/modules" \
  install --file ../logos-calc-module/result-lgx/*.lgx

# Install UI plugin
./pm/bin/lgpm --ui-plugins-dir "$BASECAMP_DIR/plugins" \
  install --file result-lgx/*.lgx

# Launch basecamp -- your modules appear alongside the built-in ones
./basecamp-result/bin/logos-basecamp
```

### 10.3 Install via logos-basecamp UI

Instead of using `lgpm` on the command line, you can install modules through the basecamp UI:

1. Launch `logos-basecamp`
2. Go to **Package Manager**
3. Click **Install from file**
4. Select `../logos-calc-module/result-lgx/*.lgx` — installs `calc_module`
5. Repeat for `result-lgx/*.lgx` — installs `calc_ui_cpp`

The "Calculator" tab appears in the sidebar.

---

## Known Limitations

### UI module not loading or basecamp behaving unexpectedly

When switching between portable and dev builds of basecamp, or running multiple basecamp instances, the data directory can get into a bad state (stale modules, mixed variants, corrupted preinstall). Clear it and let basecamp re-preinstall on next launch:

```bash
# Remove basecamp's data directory
# macOS:
rm -rf ~/Library/Application\ Support/Logos/LogosBasecampDev

# Linux:
rm -rf ~/.local/share/Logos/LogosBasecampDev

# Relaunch — basecamp will re-preinstall its bundled modules
./basecamp-result/bin/logos-basecamp
```

Then reinstall your custom modules.

---

## Recap: Three Module Types

| | Core (Part 1) | QML UI (Part 2) | C++ UI (Part 3) |
|---|---|---|---|
| Language | C++ | QML / JS | C++ (+ QML view) |
| Compilation | Yes | No | Yes |
| Backend calls | Exposed via `Q_INVOKABLE` | `logos.callModuleAsync()` IPC | `LogosModules` typed SDK in C++ |
| QML view | — | Declared via `"view"` in metadata | Same — declared via `"view"` in metadata |
| Type safety | Strong | Weak (QVariant/QString) | Strong |
| Async support | — | `logos.callModuleAsync()` | `logos.callModuleAsync()` from QML to plugin |
| Template | `#default` | `#ui-qml-module` | `#ui-module` |

## What's Next

- **Generated type-safe wrappers** — instead of raw `invokeRemoteMethod`, use `logos-cpp-generator` to generate a typed `CalcModuleClient` class. See [Developer Guide](logos-developer-guide.md) Section 6.2
- **Events** — core modules emit `eventResponse` signals; connect to them from your plugin class via `LogosAPIClient`
- **Use the Logos Design System** in QML — `import Logos.Theme` and `import Logos.Controls` are available when running inside `logos-basecamp`
