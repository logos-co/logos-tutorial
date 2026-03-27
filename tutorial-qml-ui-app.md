# Tutorial Part 2: Building a QML UI for Your Logos Module

This is Part 2 of the Logos module tutorial series. In [Part 1](tutorial-wrapping-c-library.md) you wrapped a C library as a Logos core module. Now you'll build a **QML user interface** that calls that module — first isolated with `nix run`, then packaged and loaded into `logos-basecamp`.

**What you'll build:** A `calc_ui` QML plugin with input fields and buttons that call `calc_module` methods (add, multiply, factorial, fibonacci) through the Logos bridge.

**What you'll learn:**

- How QML UI plugins work in the Logos platform
- The `logos.callModule()` bridge that connects QML to core modules
- The project structure and metadata for a QML plugin
- How to package and install your UI into `logos-basecamp`

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module`
- Nix with flakes enabled (same as Part 1)
- Basic familiarity with QML (Qt's declarative UI language)

---

## How QML UI Plugins Work

Before writing code, let's understand the architecture:

```
+-------------------+     logos.callModule()      +-------------------+
|    calc_ui        | --------------------------> |   calc_module     |
|  Main.qml (QML)   |     IPC (Qt Remote Objects) |   C++ plugin      |
+-------------------+                             +-------------------+
        ^                                                  ^
        └──────────────── loaded by ───────────────────────┘
                     logos-basecamp / logos-standalone-app
```

Key points:

- **No compilation.** A QML plugin is just `.qml` files and a `metadata.json`.
- **Sandboxed.** No network access, no filesystem access outside the module directory.
- **The `logos` bridge** is injected by the host. Call core modules with `logos.callModule("module", "method", [args])`.
- **Entry point** is always `Main.qml`.

---

## Step 1: Scaffold

Use the QML module template from `logos-module-builder`:

```bash
mkdir logos-calc-ui && cd logos-calc-ui
nix flake init -t github:logos-co/logos-module-builder#ui-qml-module
git init && git add -A
```

This gives you:

```
logos-calc-ui/
├── flake.nix       # Nix build + nix run support
├── metadata.json   # Plugin metadata
└── Main.qml        # Your UI (starter template)
```

---

## Step 2: Update `metadata.json`

Replace the template contents with your plugin's details:

```json
{
  "name": "calc_ui",
  "version": "1.0.0",
  "description": "Calculator UI - QML frontend for the calc_module",
  "type": "ui_qml",
  "main": "Main.qml",
  "dependencies": ["calc_module"],
  "category": "tools",
  "icon": "icons/calc.png"
}
```

The `dependencies` field tells the host to load `calc_module` before showing your UI.

> **Naming convention:** Each entry in `dependencies` must match the `name` field in that module's own `metadata.json`. When adding a dependency as a flake input, the **input attribute name** must also match the dependency name — e.g., `calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module"`. The URL can point to any repo, but the attribute name is how the builder resolves dependencies.

---

## Step 3: Write `Main.qml`

Replace the starter file with the calculator UI:

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
            text: "Logos Calculator"
            font.pixelSize: 20
            font.weight: Font.DemiBold
            color: "#ffffff"
            Layout.alignment: Qt.AlignHCenter
        }

        // ── Two-operand operations ─────────────────────────────
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
                onClicked: callTwoOp("add", inputA.text, inputB.text)
            }

            Button {
                text: "Multiply"
                onClicked: callTwoOp("multiply", inputA.text, inputB.text)
            }
        }

        // ── Single-operand operations ──────────────────────────
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
                onClicked: callOneOp("factorial", inputN.text)
            }

            Button {
                text: "Fibonacci"
                onClicked: callOneOp("fibonacci", inputN.text)
            }

            Button {
                text: "libcalc version"
                onClicked: callModule("libVersion", [])
            }
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

    // ── Logos bridge helpers ───────────────────────────────────

    function callModule(method, args) {
        root.errorText = ""
        root.result = ""

        if (typeof logos === "undefined" || !logos.callModule) {
            root.errorText = "Logos bridge not available"
            return
        }

        root.result = String(logos.callModule("calc_module", method, args))
    }

    function callTwoOp(method, a, b) {
        if (a === "" || b === "") { root.errorText = "Enter values for a and b"; return }
        callModule(method, [parseInt(a), parseInt(b)])
    }

    function callOneOp(method, n) {
        if (n === "") { root.errorText = "Enter a value for n"; return }
        callModule(method, [parseInt(n)])
    }
}
```

The `logos` object is injected by the host at runtime. The `callModule` helper checks for it and routes calls through the IPC bridge to `calc_module`.

---

## Step 4: Update `flake.nix`

The template already has everything wired up. Update the description and add `calc_module` as a dependency input:

```nix
{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";  # must match dependency name in metadata.json
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

`mkLogosQmlModule` handles everything — it stages QML files, metadata, and icons into a plugin directory, bundles all module dependencies (direct and transitive) from their LGX packages, and automatically wires up `apps.default` so `nix run .` launches the UI in a standalone window with all required backend modules self-contained. `flakeInputs = inputs` passes all inputs so that dependencies declared in `metadata.json` are resolved automatically — note that the input attribute name (`calc_module`) must match the dependency name.

---

## Step 5: Test with `nix run`

### 5.1 UI only (layout preview)

```bash
git add -A
nix run .
```

The app opens immediately. No modules are loaded, so clicking buttons shows "Logos bridge not available" — but you can verify the layout and styling look correct.

### 5.2 Full functionality (with modules)

To test actual calls to `calc_module`, you need a modules directory with `calc_module` installed via `lgpm`. The `capability_module` is loaded automatically by the standalone app. Do this once:

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm
mkdir -p modules

# Bundle and install calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx'
cd ../logos-calc-ui
./pm/bin/lgpm --modules-dir ./modules install --file ../logos-calc-module/result/*.lgx
```

Then run with the modules directory:

```bash
nix run . -- --modules-dir ./modules
```

Clicking **Add**, **Multiply**, **Factorial**, or **Fibonacci** now calls the real module.

---

## Step 6: Using the Logos Design System

`logos-basecamp` has `logos-design-system` on its QML import path. You can use its themed components directly without any extra setup in your module.

```qml
import Logos.Theme 1.0
import Logos.Controls 1.0
```

Replace the plain `Button` and `TextField` with the styled equivalents:

```qml
// Instead of Button:
LogosButton {
    text: "Add"
    onClicked: callTwoOp("add", inputA.text, inputB.text)
}

// Instead of TextField:
LogosTextField {
    id: inputA
    placeholderText: "a"
}

// Use theme colors instead of hardcoded hex values:
Rectangle {
    color: Theme.palette.backgroundSecondary
    // ...
    Text { color: Theme.palette.text }
}
```

Available components: `LogosButton`, `LogosTextField`, `LogosText`, `LogosTabButton`.

Available theme tokens via `Theme.palette`:
- Colors: `background`, `backgroundSecondary`, `backgroundMuted`, `text`, `textMuted`, `border`, `overlayOrange`
- Spacing: `Theme.spacing.radiusSmall`, `Theme.spacing.radiusXlarge`
- Typography: `Theme.typography.secondaryText`, `Theme.typography.weightMedium`

---

## Step 7: Load in `logos-basecamp`

### 7.1 Bundle as LGX packages

Create `.lgx` packages using the dual variant (includes both dev and portable variants, so they work with any basecamp build):

```bash
# Package calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx-dual'

# Package the QML UI plugin
cd ../logos-calc-ui
nix build '.#lgx-dual'
```

> For more bundling options (standalone bundler syntax, cross-platform packaging), see the [Developer Guide — Bundling with nix-bundle-lgx](logos-developer-guide.md#32-bundling-with-nix-bundle-lgx).

### 7.2 Build and run logos-basecamp

Build logos-basecamp, launch it once to preinstall its bundled modules, then install your modules.

> **Note:** `logos-basecamp` does not accept `--modules-dir` or `--ui-plugins-dir` CLI flags. It manages its own data directory and preinstalls bundled modules (main_ui, package_manager, etc.) on first launch.

```bash
# Build logos-basecamp
nix build 'github:logos-co/logos-basecamp' -o basecamp-result

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
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm

# Install core module
./pm/bin/lgpm --modules-dir BASECAMP_DIR/modules \
  install --file ../logos-calc-module/result/*.lgx

# Install UI plugin
./pm/bin/lgpm --modules-dir BASECAMP_DIR/plugins \
  install --file result/*.lgx

# Launch basecamp -- your modules appear alongside the built-in ones
./basecamp-result/bin/logos-basecamp
```

### 7.3 Install via logos-basecamp UI

Instead of using `lgpm` on the command line, you can install modules through the basecamp UI:

1. Launch `logos-basecamp`
2. Go to **Package Manager**
3. Click **Install from file**
4. Select `../logos-calc-module/result/*.lgx` -- installs `calc_module`
5. Repeat for `result/*.lgx` -- installs `calc_ui`

The "Calculator UI" tab appears in the sidebar. Clicking it loads your `Main.qml`.

### 7.4 Live reloading with `logos-standalone-app`

For rapid iteration on QML without rebuilding, set `QML_PATH` to your QML source directory:

```bash
QML_PATH=$PWD/src/qml nix run .
```

Edit `Main.qml`, close and re-run — changes appear immediately without `nix build`. When `QML_PATH` is set, the plugin loads QML files from the filesystem instead of from Qt resources, so your edits are picked up on each launch.

> This does not work with `logos-basecamp`. Basecamp loads QML plugins from its own data directory, so changes to your source files are not reflected until you rebuild and reinstall the `.lgx` package.

### 7.5 Testing without any runtime

You can open `Main.qml` in any QML viewer (e.g., `qml` from Qt) to test the layout. The `logos` bridge won't be available, so clicking buttons will show "Logos bridge not available" -- but you can verify the layout and styling work correctly.

```bash
# If you have Qt installed
qml Main.qml
```

---

## Known Limitations

### QML-to-C++ type coercion: `int` parameters called as `QString`

When calling C++ module methods from QML via `logos.callModule()`, all arguments are passed as strings. If the target method expects `int`, `bool`, or other non-string types, the call will fail with:

```
QMetaObject::invokeMethod: No such method CalcModulePlugin::add(QString,QString)
Candidates are:
    add(int,int)
```

**Workaround:** Define your C++ methods to accept `QString` parameters and convert inside the implementation:

```cpp
// Instead of:  Q_INVOKABLE int add(int a, int b);
// Use:
Q_INVOKABLE QString add(const QString& a, const QString& b) {
    return QString::number(a.toInt() + b.toInt());
}
```

This ensures the QML bridge can match the method signature. Methods that already use `QString` parameters work without any changes.

### QML changes not appearing after rebuild

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

## Recap

| | Core Module (Part 1) | QML UI Plugin (Part 2) |
|---|---|---|
| Language | C++ | QML / JavaScript |
| Files | `.cpp`, `.h`, `CMakeLists.txt`, `metadata.json` | `Main.qml`, `metadata.json` |
| Compilation | Yes (CMake → `.so`) | No (file copy) |
| `metadata.type` | `"core"` | `"ui_qml"` |
| Test command | `logoscore -m ./result/lib -l calc_module` | `nix run .` |
| Calls other modules | Via `LogosAPI*` (C++) | Via `logos.callModule()` (JS) |

---

## What's Next

- **Add more methods** to `calc_module` and call them from QML
- **Use Logos Design System** styled components for consistent look and feel
- **Build a C++ UI module** for cases where QML sandboxing is too restrictive — see [Developer Guide](logos-developer-guide.md), Section 7.2
