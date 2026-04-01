# Tutorial Part 3: Building a C++ UI Module

This is Part 3 of the Logos module tutorial series. In [Part 2](tutorial-qml-ui-app.md) you built a QML UI plugin. Now you'll build a **native C++ Qt widget plugin** that calls `calc_module` through a typed backend class.

**What you'll build:** A `calc_ui_cpp` C++ plugin with two options for the UI:

- **Option A — QML loaded from C++:** A `QQuickWidget` inside the plugin loading the same `Main.qml` as the QML plugin, with `CalcBackend` exposed as a context property — plus dev mode for editing QML without rebuilding
- **Option B — Pure Qt widget:** `QPushButton`, `QLineEdit`, `QLabel` wired directly to a backend class

**Why C++ over QML-only?**

| | QML plugin (Part 2) | C++ UI plugin (Part 3) |
|---|---|---|
| Compilation | No | Yes (CMake) |
| Backend calls | Via `logos.callModule()` IPC bridge | Via `LogosAPI*` directly in C++ |
| Type safety | Weak — all args travel as `QVariant` | Strong — C++ types preserved |
| Sandboxing | Yes | No |
| QML support | Native | Optional via `QQuickWidget` |

The C++ backend class provides type-safe calls via generated SDK wrappers — `int` arguments stay `int` all the way to the module without relying on runtime coercion.

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module`
- Nix with flakes enabled

---

## How It Works

```
+----------------------+      CalcBackend::add(3, 5)      +-------------------+
|   calc_ui_cpp        | --------------------------------> |   calc_module     |
|   C++ Qt plugin      |   LogosAPI* / invokeRemoteMethod |   C++ plugin      |
|   createWidget()     |                                  |   add(int, int)   |
+----------------------+                                  +-------------------+
        ^
        | loaded by
        v
  logos-standalone-app / logos-basecamp
```

The plugin implements `createWidget()` which returns a `QWidget*`. The widget is shown in the host app's window. A `CalcBackend` class holds `LogosAPI*` and makes typed calls to `calc_module`.

---

## Step 1: Scaffold

```bash
mkdir logos-calc-ui-cpp && cd logos-calc-ui-cpp
nix flake init -t github:logos-co/logos-module-builder/b6cf87d30e2995e023496fcfc7f06e8127c6ac5b#ui-module
git init && git add -A
```

This gives you:

```
logos-calc-ui-cpp/
├── flake.nix
├── metadata.json
├── CMakeLists.txt
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

```json
{
  "name": "calc_ui_cpp",
  "version": "1.0.0",
  "type": "ui",
  "category": "tools",
  "description": "Calculator C++ UI — widget frontend for calc_module",
  "main": "calc_ui_cpp_plugin",
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
        src/calc_backend.h
        src/calc_backend.cpp
)

find_package(Qt6 REQUIRED COMPONENTS Widgets)
target_link_libraries(calc_ui_cpp_module_plugin PRIVATE Qt6::Widgets)
```

> For Option A (QML inside the plugin) you will add `Quick QuickWidgets` and `qt_add_resources` — covered in [Step 7](#step-7-option-a--qml-loaded-from-c).

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

---

## Step 5: Plugin Header (`src/calc_ui_cpp_plugin.h`)

Replace the scaffolded plugin header. This header is the same for both Option A and Option B — only the `.cpp` implementation differs:

```cpp
#ifndef CALC_UI_CPP_PLUGIN_H
#define CALC_UI_CPP_PLUGIN_H

#include <QObject>
#include <QWidget>
#include <QVariantList>
#include "calc_ui_cpp_interface.h"

class LogosAPI;

class CalcUiCppPlugin : public QObject, public CalcUiCppInterface
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID CalcUiCppInterface_iid FILE "metadata.json")
    Q_INTERFACES(CalcUiCppInterface PluginInterface)

public:
    explicit CalcUiCppPlugin(QObject* parent = nullptr);
    ~CalcUiCppPlugin() override;

    QString name()    const override { return "calc_ui_cpp"; }
    QString version() const override { return "1.0.0"; }

    Q_INVOKABLE void initLogos(LogosAPI* api);

    Q_INVOKABLE QWidget* createWidget(LogosAPI* logosAPI = nullptr);
    Q_INVOKABLE void destroyWidget(QWidget* widget);

signals:
    void eventResponse(const QString& eventName, const QVariantList& args);

private:
    LogosAPI* m_logosAPI = nullptr;
};

#endif // CALC_UI_CPP_PLUGIN_H
```

---

## Step 6: Backend Class

The backend class is the key addition over the QML plugin. It holds a `LogosModules*` wrapper — a typed C++ SDK generated at build time from `metadata.json` — and exposes `Q_INVOKABLE` methods that call `calc_module` through it. Because the calls go through a generated typed class, argument types are preserved at compile time — no runtime coercion needed.

### How the generated SDK works

When `metadata.json` declares `"dependencies": ["calc_module"]` and `calc_module` is passed as a flake input via `flakeInputs`, the build system runs `logos-cpp-generator` before compilation. This produces:

- `logos_sdk.h` / `logos_sdk.cpp` — the `LogosModules` umbrella class with one typed member per dependency
- `calc_module_api.h` / `calc_module_api.cpp` — the per-module wrapper included by `logos_sdk.h`

`LogosModules` is constructed with a `LogosAPI*` and provides a member named after each declared dependency (snake_case). All IPC routing happens inside the generated code — your backend just calls methods directly:

```cpp
m_logos->calc_module.add(3, 5)   // typed: int add(int, int) over IPC
```

### `src/calc_backend.h`

```cpp
#ifndef CALC_BACKEND_H
#define CALC_BACKEND_H

#include <QObject>
#include <QString>
#include "logos_sdk.h"   // generated at build time from metadata.json dependencies

class LogosAPI;

class CalcBackend : public QObject
{
    Q_OBJECT

public:
    explicit CalcBackend(LogosAPI* api, QObject* parent = nullptr);

    Q_INVOKABLE int     add(int a, int b);
    Q_INVOKABLE int     multiply(int a, int b);
    Q_INVOKABLE int     factorial(int n);
    Q_INVOKABLE int     fibonacci(int n);
    Q_INVOKABLE QString libVersion();

private:
    LogosModules* m_logos;   // generated umbrella wrapper
};

#endif // CALC_BACKEND_H
```

### `src/calc_backend.cpp`

```cpp
#include "calc_backend.h"

CalcBackend::CalcBackend(LogosAPI* api, QObject* parent)
    : QObject(parent), m_logos(new LogosModules(api)) {}

int     CalcBackend::add(int a, int b)      { return m_logos->calc_module.add(a, b); }
int     CalcBackend::multiply(int a, int b) { return m_logos->calc_module.multiply(a, b); }
int     CalcBackend::factorial(int n)       { return m_logos->calc_module.factorial(n); }
int     CalcBackend::fibonacci(int n)       { return m_logos->calc_module.fibonacci(n); }
QString CalcBackend::libVersion()           { return m_logos->calc_module.libVersion(); }
```

`LogosModules` is constructed once with `LogosAPI*`. Each member (`calc_module`) is a generated proxy that routes calls to the corresponding module process over Qt Remote Objects IPC. No raw `invokeRemoteMethod`, no string method names, no manual `QVariant` unwrapping.

---

## Step 7: Option A — QML Loaded from C++

The plugin loads `src/qml/Main.qml` into a `QQuickWidget` and exposes `CalcBackend` as a QML context property. The QML is identical in structure to `logos-calc-ui/Main.qml` (Part 2), but calls `backend.*` methods directly instead of routing through the `logos.callModule()` IPC bridge — so argument types are preserved and there is no sandboxing overhead.

### 7.1 Add the QML file

Create `src/qml/Main.qml`. The structure mirrors `logos-calc-ui/Main.qml` exactly; the only difference is that buttons call `backend.*` methods directly instead of routing through `logos.callModule(...)`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // ── Title ──────────────────────────────────────────────
        Text {
            text: "Logos Calculator (C++ backend)"
            font.pixelSize: 20
            color: "#ffffff"
            Layout.alignment: Qt.AlignHCenter
        }

        // ── Two-operand operations ─────────────────────────────
        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField { id: inputA; placeholderText: "a"; Layout.preferredWidth: 80; validator: IntValidator {} }
            TextField { id: inputB; placeholderText: "b"; Layout.preferredWidth: 80; validator: IntValidator {} }

            Button {
                text: "Add"
                onClicked: root.result = String(backend.add(inputA.text, inputB.text))
            }
            Button {
                text: "Multiply"
                onClicked: root.result = String(backend.multiply(inputA.text, inputB.text))
            }
        }

        // ── Single-operand operations ──────────────────────────
        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            TextField { id: inputN; placeholderText: "n"; Layout.preferredWidth: 80; validator: IntValidator { bottom: 0 } }

            Button { text: "Factorial";       onClicked: root.result = String(backend.factorial(inputN.text)) }
            Button { text: "Fibonacci";       onClicked: root.result = String(backend.fibonacci(inputN.text)) }
            Button { text: "libcalc version"; onClicked: root.result = backend.libVersion() }
        }

        // ── Result display ─────────────────────────────────────
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

### 7.2 Update `CMakeLists.txt`

Add `Quick` and `QuickWidgets`, and embed the QML as a Qt resource:

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
        src/calc_backend.h
        src/calc_backend.cpp
)

find_package(Qt6 REQUIRED COMPONENTS Widgets Quick QuickWidgets)
target_link_libraries(calc_ui_cpp_module_plugin PRIVATE
    Qt6::Widgets
    Qt6::Quick
    Qt6::QuickWidgets
)

qt_add_resources(calc_ui_cpp_module_plugin "qml_resources"
    PREFIX "/"
    FILES
        src/qml/Main.qml
)
```

### 7.3 `createWidget()` — load QML

Replace `calc_ui_cpp_plugin.cpp` with:

```cpp
#include "calc_ui_cpp_plugin.h"
#include "calc_backend.h"
#include "logos_api.h"
#include <QDebug>
#include <QDir>
#include <QQuickWidget>
#include <QQmlContext>
#include <QUrl>

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : QObject(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() {}

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
}

QWidget* CalcUiCppPlugin::createWidget(LogosAPI* logosAPI)
{
    auto* backend = new CalcBackend(logosAPI);

    auto* quickWidget = new QQuickWidget();
    quickWidget->setResizeMode(QQuickWidget::SizeRootObjectToView);
    quickWidget->rootContext()->setContextProperty("backend", backend);

    // Dev mode: set QML_PATH to the directory containing Main.qml to load
    // from the filesystem without rebuilding. Example: export QML_PATH=$PWD/src/qml
    QString devSource = qgetenv("QML_PATH");
    QUrl qmlUrl = devSource.isEmpty()
        ? QUrl("qrc:/src/qml/Main.qml")
        : QUrl::fromLocalFile(QDir(devSource).filePath("Main.qml"));

    quickWidget->setSource(qmlUrl);

    if (quickWidget->status() == QQuickWidget::Error) {
        qWarning() << "CalcUiCppPlugin: failed to load QML";
        for (const auto& e : quickWidget->errors())
            qWarning() << e.toString();
    }

    return quickWidget;
}

void CalcUiCppPlugin::destroyWidget(QWidget* widget)
{
    delete widget;
}
```

### 7.4 Dev Mode

When `QML_PATH` is set, the plugin loads `Main.qml` from disk instead of the embedded resource. You can edit QML layout, styling, and property bindings without a Nix rebuild — just restart the app to pick up changes.

```bash
# Run with dev mode enabled
QML_PATH=$PWD/src/qml \
  nix run . 
```

> **What still requires a rebuild:**
> - Changes to `.cpp` / `.h` files (backend logic, plugin interface)
> - Changes to `CMakeLists.txt` or `metadata.json`
>
> **What does not require a rebuild:**
> - Any `.qml` change — layout, styling, property bindings, JS logic

---

## Step 8: Option B — Pure Qt Widget

The plugin creates a standard Qt widget using layouts and connects button clicks to the backend. No QML, no additional Qt modules — just `Qt6::Widgets`.

Replace `src/calc_ui_cpp_plugin.cpp` with:

### `src/calc_ui_cpp_plugin.cpp`

```cpp
#include "calc_ui_cpp_plugin.h"
#include "calc_backend.h"
#include "logos_api.h"
#include <QDebug>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>

CalcUiCppPlugin::CalcUiCppPlugin(QObject* parent) : QObject(parent) {}
CalcUiCppPlugin::~CalcUiCppPlugin() {}

void CalcUiCppPlugin::initLogos(LogosAPI* api)
{
    m_logosAPI = api;
}

QWidget* CalcUiCppPlugin::createWidget(LogosAPI* logosAPI)
{
    auto* backend = new CalcBackend(logosAPI);

    auto* widget  = new QWidget();
    auto* layout  = new QVBoxLayout(widget);
    layout->setContentsMargins(24, 24, 24, 24);
    layout->setSpacing(16);

    // ── Title ──────────────────────────────────────────────────
    auto* title = new QLabel("Logos Calculator (C++)");
    title->setAlignment(Qt::AlignHCenter);
    layout->addWidget(title);

    // ── Two-operand row ────────────────────────────────────────
    auto* twoOpRow = new QHBoxLayout();
    auto* inputA   = new QLineEdit(); inputA->setPlaceholderText("a"); inputA->setMaximumWidth(80);
    auto* inputB   = new QLineEdit(); inputB->setPlaceholderText("b"); inputB->setMaximumWidth(80);
    auto* addBtn   = new QPushButton("Add");
    auto* mulBtn   = new QPushButton("Multiply");
    twoOpRow->addWidget(inputA);
    twoOpRow->addWidget(inputB);
    twoOpRow->addWidget(addBtn);
    twoOpRow->addWidget(mulBtn);
    twoOpRow->addStretch();
    layout->addLayout(twoOpRow);

    // ── Single-operand row ─────────────────────────────────────
    auto* oneOpRow = new QHBoxLayout();
    auto* inputN   = new QLineEdit(); inputN->setPlaceholderText("n"); inputN->setMaximumWidth(80);
    auto* facBtn   = new QPushButton("Factorial");
    auto* fibBtn   = new QPushButton("Fibonacci");
    auto* verBtn   = new QPushButton("libcalc version");
    oneOpRow->addWidget(inputN);
    oneOpRow->addWidget(facBtn);
    oneOpRow->addWidget(fibBtn);
    oneOpRow->addWidget(verBtn);
    oneOpRow->addStretch();
    layout->addLayout(oneOpRow);

    // ── Result display ─────────────────────────────────────────
    auto* resultLabel = new QLabel("Enter values and press a button");
    resultLabel->setAlignment(Qt::AlignHCenter);
    layout->addWidget(resultLabel);

    layout->addStretch();

    // ── Wire up buttons ────────────────────────────────────────
    auto show = [resultLabel](const QString& v) { resultLabel->setText(v); };

    QObject::connect(addBtn, &QPushButton::clicked, [=] {
        show(QString::number(backend->add(inputA->text().toInt(), inputB->text().toInt())));
    });
    QObject::connect(mulBtn, &QPushButton::clicked, [=] {
        show(QString::number(backend->multiply(inputA->text().toInt(), inputB->text().toInt())));
    });
    QObject::connect(facBtn, &QPushButton::clicked, [=] {
        show(QString::number(backend->factorial(inputN->text().toInt())));
    });
    QObject::connect(fibBtn, &QPushButton::clicked, [=] {
        show(QString::number(backend->fibonacci(inputN->text().toInt())));
    });
    QObject::connect(verBtn, &QPushButton::clicked, [=] {
        show(backend->libVersion());
    });

    return widget;
}

void CalcUiCppPlugin::destroyWidget(QWidget* widget)
{
    delete widget;
}
```

---

## Step 9: `flake.nix`

Since `metadata.json` declares `"type": "ui"`, `mkLogosModule` automatically wires up `apps.default` (i.e. `nix run`) for free — no manual `apps` block or `logosStandalone` parameter required. The standalone app runner is bundled with `logos-module-builder`.

**Important — `flakeInputs`:** Because `metadata.json` declares `"dependencies": ["calc_module"]`, the build system runs `logos-cpp-generator` before compiling your C++ sources. The generator introspects `calc_module`'s built plugin to produce `logos_sdk.h` / `logos_sdk.cpp` (and per-module `calc_module_api.h` / `calc_module_api.cpp`). These are the files your backend includes as `#include "logos_sdk.h"`. For this to work, `calc_module` must be available as a built Nix package at code-generation time — that is what `flakeInputs` provides (the builder discovers dependency inputs by matching their names against the `dependencies` array in `metadata.json`). Without it, the build fails with `'logos_sdk.h' file not found`.

```nix
{
  description = "Calculator C++ UI plugin for Logos - widget frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder/b6cf87d30e2995e023496fcfc7f06e8127c6ac5b";
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

## Step 10: Build and Test

### 10.1 Build

```bash
git add -A
nix build --override-input calc_module path:../logos-calc-module
```

Inspect the output with `lm` (the module inspector from `logos-module`):

```bash
nix build 'github:logos-co/logos-module/337223f2a72710d8052ca750510cd25d33e05047#lm' --out-link ./lm-cli

# Linux
./lm-cli/bin/lm ./result/lib/calc_ui_cpp_plugin.so

# macOS
# ./lm-cli/bin/lm ./result/lib/calc_ui_cpp_plugin.dylib
```

You should see `createWidget` and `destroyWidget` in the methods list.

### 10.2 UI only (layout preview)

```bash
nix run . --override-input calc_module path:../logos-calc-module
```

The widget opens. No backend connected yet, so button clicks will silently return 0 (CalcBackend logs a warning when `calc_module` is not connected).

> **When do you need `--override-input`?** `calc_module.url` in `flake.nix` points to the published GitHub URL. If your local `logos-calc-module` has unpushed changes or differs from what is on GitHub, you must use `--override-input calc_module path:../logos-calc-module` so nix uses your local copy. If your `calc_module` is already pushed and matches the GitHub URL, you can run `nix build` / `nix run` without the override. This is the same mechanism `ws build --local` / `ws build --auto-local` uses throughout the workspace.

### 10.3 Full functionality (with modules)

The `capability_module` is loaded automatically by the standalone app. You only need to install `calc_module`:

```bash
nix build 'github:logos-co/logos-package-manager/e5c25989861f4487c3dc8c7b3bc0062bcbc3221f#cli' --out-link ./pm
mkdir -p modules

# Bundle and install calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx'
cd ../logos-calc-ui-cpp
./pm/bin/lgpm --modules-dir ./modules install --file ../logos-calc-module/result/*.lgx

nix run . --override-input calc_module path:../logos-calc-module -- --modules-dir ./modules
```

---

## Step 11: Load in `logos-basecamp`

### 11.1 Create LGX packages

```bash
# Package calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx'
nix build '.#lgx-portable'

# Package the C++ UI plugin
cd ../logos-calc-ui-cpp
nix build '.#lgx'
nix build '.#lgx-portable'
```

> For more bundling options (standalone bundler syntax, cross-platform packaging), see the [Developer Guide — Bundling with nix-bundle-lgx](logos-developer-guide.md#32-bundling-with-nix-bundle-lgx).

### 11.2 Build and run logos-basecamp

Build logos-basecamp, launch it once to preinstall its bundled modules, then install your modules.

> **Note:** `logos-basecamp` does not accept `--modules-dir` or `--ui-plugins-dir` CLI flags. It manages its own data directory and preinstalls bundled modules (main_ui, package_manager, etc.) on first launch.

```bash
# Build logos-basecamp
nix build 'github:logos-co/logos-basecamp/70169584a44d954f638e34842bcfebf741e6bcfe' -o basecamp-result

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

Install your modules using `lgpm` (substitute `BASECAMP_DIR` with the actual path you found above):

```bash
# Build lgpm CLI
nix build 'github:logos-co/logos-package-manager/e5c25989861f4487c3dc8c7b3bc0062bcbc3221f#cli' --out-link ./pm

# Install core module
./pm/bin/lgpm --modules-dir BASECAMP_DIR/modules \
  install --file ../logos-calc-module/result/*.lgx

# Install UI plugin
./pm/bin/lgpm --modules-dir BASECAMP_DIR/plugins \
  install --file result/*.lgx

# Launch basecamp -- your modules appear alongside the built-in ones
./basecamp-result/bin/logos-basecamp
```

### 11.3 Install via logos-basecamp UI

Instead of using `lgpm` on the command line, you can install modules through the basecamp UI:

1. Launch `logos-basecamp`
2. Go to **Package Manager**
3. Click **Install from file**
4. Select `../logos-calc-module/result/*.lgx` — installs `calc_module`
5. Repeat for `result/*.lgx` — installs `calc_ui_cpp`

The "Calculator" tab appears in the sidebar.

---

## Known Limitations

### QML changes not appearing after rebuild (Option A only)

Qt caches compiled QML on disk. If you update your `Main.qml`, rebuild and reinstall the `.lgx`, but the old UI still appears, the cache is stale. Fix by disabling the cache before launching:

```bash
QML_DISABLE_DISK_CACHE=1 ./basecamp-result/bin/logos-basecamp
```

### UI module not loading or basecamp behaving unexpectedly

When switching between portable and dev builds of basecamp, or running multiple basecamp instances, the data directory can get into a bad state (stale modules, mixed variants, corrupted preinstall). Clear it and let basecamp re-preinstall on next launch:

```bash
# Remove basecamp's data directory (find yours under Application Support or .local/share)
# macOS (typical):
rm -rf ~/Library/Application\ Support/Logos/LogosBasecampDev
# Linux (typical):
# rm -rf ~/.local/share/Logos/LogosBasecampDev

# Relaunch — basecamp will re-preinstall its bundled modules
./basecamp-result/bin/logos-basecamp
```

Then reinstall your custom modules.

---

## Recap: Three Module Types

| | Core (Part 1) | QML UI (Part 2) | C++ UI (Part 3) |
|---|---|---|---|
| Language | C++ | QML / JS | C++ (+ optional QML) |
| Compilation | Yes | No | Yes |
| Backend calls | Exposed via `Q_INVOKABLE` | `logos.callModule()` IPC | `LogosAPI*` → `invokeRemoteMethod()` |
| Type safety | Strong | Weak (QVariant/QString) | Strong |
| Async support | — | `logos.callModuleAsync()` | `LogosAPIClient::invokeRemoteMethodAsync()` |
| Sandboxed | No | Yes | No |
| QML support | — | Native | Via `QQuickWidget` |
| Template | `#default` | `#ui-qml-module` | `#ui-module` |

## What's Next

- **Generated type-safe wrappers** — instead of raw `invokeRemoteMethod`, use `logos-cpp-generator` to generate a typed `CalcModuleClient` class. See [Developer Guide](logos-developer-guide.md) Section 6.2
- **Events** — core modules emit `eventResponse` signals; connect to them from your backend class via `LogosAPIClient`
- **Use the Logos Design System** in Option B QML — `import Logos.Theme` and `import Logos.Controls` are available when running inside `logos-basecamp`
