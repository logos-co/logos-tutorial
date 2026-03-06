# Tutorial Part 2: Building a QML UI App for Your Logos Module

This is Part 2 of the Logos module tutorial series. In [Part 1](tutorial-wrapping-c-library.md), you wrapped a C library (`libcalc`) as a Logos module. Now you'll build a **QML user interface** that calls that module from inside the Logos desktop app.

**What you'll build:** A `calc_ui` QML app with input fields, buttons, and a result display that calls `calc_module` methods (add, multiply, factorial, fibonacci) through the Logos bridge.

**What you'll learn:**

- How QML UI plugins work in the Logos platform
- The `logos.callModule()` bridge that connects QML to core modules
- The project structure and metadata for a QML plugin
- How to build, install, and run your UI inside `logos-app`

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module`
- Nix with flakes enabled (same as Part 1)
- Basic familiarity with QML (Qt's declarative UI language)

---

## How QML UI Plugins Work

Before writing code, let's understand the architecture:

```
+--------------------+       logos.callModule()       +--------------------+
|    calc_ui         | -----------------------------> |   calc_module      |
|    (QML, sandboxed)|       IPC (Qt Remote Objects)  |   (C++ plugin)     |
|    Main.qml        |                                |   wraps libcalc.so |
+--------------------+                                +--------------------+
        ^                                                      ^
        |  loaded by                                           |  loaded by
        v                                                      v
+---------------------------------------------------------------+
|                        logos-app                               |
|   QML sandbox engine        |        logos_host process       |
+---------------------------------------------------------------+
```

Key points:

1. **QML plugins are pure QML** — no C++ compilation needed. You write `.qml` files and a `metadata.json`.
2. **QML plugins are sandboxed** — no network access, no filesystem access outside the module directory.
3. **The `logos` bridge** is injected by the host. You call core modules with `logos.callModule("module_name", "method", [args])`.
4. **The entry point** is always `Main.qml`. The host loads this file into a sandboxed QML engine.

---

## Step 1: Create the Project

The project structure is minimal:

```
logos-calc-ui/
├── Main.qml          # The UI (your only code file)
├── metadata.json     # Plugin metadata
├── flake.nix         # Nix build config
└── icons/
    └── calc.png      # Tab icon (optional)
```

### 1.1 Create the directory

```bash
mkdir logos-calc-ui && cd logos-calc-ui
mkdir icons
```

### 1.2 Add an icon (optional)

Place a PNG icon at `icons/calc.png`. This appears in the `logos-app` sidebar. If you don't have one, the app will use a default icon.

---

## Step 2: Write `metadata.json`

This tells `logos-app` what your plugin is and how to load it.

```json
{
  "name": "calc_ui",
  "version": "1.0.0",
  "description": "Calculator UI - QML frontend for the calc_module",
  "author": "",
  "type": "ui_qml",
  "pluginType": "qml",
  "main": "Main.qml",
  "dependencies": ["calc_module"],
  "category": "tools",
  "capabilities": [],
  "icon": "icons/calc.png"
}
```

**Key fields explained:**


| Field          | What it does                                                        |
| -------------- | ------------------------------------------------------------------- |
| `type`         | Must be `"ui_qml"` for QML UI plugins                               |
| `pluginType`   | Must be `"qml"`                                                     |
| `main`         | Entry point QML file — always `"Main.qml"`                          |
| `dependencies` | Core modules this UI needs. `logos-app` loads these before your UI. |
| `category`     | Groups plugins in the sidebar (e.g., `"tools"`, `"misc"`)           |
| `icon`         | Path to the sidebar icon, relative to the plugin directory          |


**Compare with `calc_module`'s metadata** (from Part 1):

```json
{
  "name": "calc_module",
  "type": "core",
  "main": "calc_module_plugin",
  ...
}
```

The core module has `"type": "core"` and `"main"` points to a compiled plugin binary. The QML UI has `"type": "ui_qml"` and `"main"` points to a `.qml` file. Different types, same metadata format.

---

## Step 3: Write `Main.qml`

This is the entire UI. We'll build it in sections.

### 3.1 Scaffold

Create `Main.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    // State
    property string result: ""
    property string errorText: ""

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        // Title
        Text {
            text: "Logos Calculator"
            font.pixelSize: 20
            font.weight: Font.DemiBold
            color: "#1f2328"
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: "QML frontend for the calc_module (libcalc C library)"
            font.pixelSize: 13
            color: "#57606a"
            Layout.alignment: Qt.AlignHCenter
        }

        // ... sections go here ...

        // Push everything up
        Item { Layout.fillHeight: true }
    }

    // ... helper functions go here ...
}
```

The root `Item` with a `ColumnLayout` is the standard pattern. Two properties track the result and any error.

### 3.2 The Logos bridge function

This is the most important part — the function that calls your core module. Add this at the bottom of the `Item`, after the `ColumnLayout`:

```qml
    function callModule(method, args) {
        root.errorText = ""
        root.result = ""

        // The logos object is injected by the host at runtime.
        // It won't exist if you open Main.qml in a standalone QML viewer.
        if (typeof logos === "undefined" || !logos.callModule) {
            root.errorText = "Logos bridge not available (run inside logos-app)"
            return
        }

        var res = logos.callModule("calc_module", method, args)
        root.result = String(res)
    }
```

**How `logos.callModule()` works:**

```
logos.callModule(moduleName, methodName, argsArray)
                    │            │           │
                    │            │           └── JavaScript array of arguments
                    │            └── Method name on the module (e.g., "add")
                    └── Module name from metadata.json (e.g., "calc_module")
```

The call is synchronous from QML's perspective. Under the hood, `logos-app` routes it via IPC to the `logos_host` process running `calc_module`, which calls `CalcModulePlugin::add()`, which calls `calc_add()` from libcalc. The result comes back through the same chain.

### 3.3 Helper functions for different arities

Add these below `callModule`:

```qml
    function callTwoOp(method, a, b) {
        if (a === "" || b === "") {
            root.errorText = "Enter values for both a and b"
            return
        }
        callModule(method, [parseInt(a), parseInt(b)])
    }

    function callOneOp(method, n) {
        if (n === "") {
            root.errorText = "Enter a value for n"
            return
        }
        callModule(method, [parseInt(n)])
    }

    function callNoArg(method) {
        callModule(method, [])
    }
```

These handle input validation and type conversion. `parseInt()` converts the text field strings to integers before passing them to the module.

### 3.4 Two-operand section (add, multiply)

Add this inside the `ColumnLayout`, after the subtitle text:

```qml
        // Two-operand section
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: twoOpColumn.implicitHeight + 32
            color: "#f6f8fa"
            radius: 8
            border.color: "#d1d9e0"
            border.width: 1

            ColumnLayout {
                id: twoOpColumn
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Two-operand operations"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: "#1f2328"
                }

                RowLayout {
                    spacing: 12
                    Layout.fillWidth: true

                    TextField {
                        id: inputA
                        placeholderText: "a"
                        Layout.preferredWidth: 100
                        validator: IntValidator {}
                    }

                    TextField {
                        id: inputB
                        placeholderText: "b"
                        Layout.preferredWidth: 100
                        validator: IntValidator {}
                    }

                    Button {
                        text: "Add"
                        onClicked: callTwoOp("add", inputA.text, inputB.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#1a7f37" : "#238636"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Multiply"
                        onClicked: callTwoOp("multiply", inputA.text, inputB.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#1a7f37" : "#238636"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
```

Each `Button` calls `callTwoOp()` with the method name and the text from the two input fields. The `IntValidator` on each `TextField` restricts input to integers.

### 3.5 Single-operand section (factorial, fibonacci)

Add this after the two-operand section:

```qml
        // Single-operand section
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: oneOpColumn.implicitHeight + 32
            color: "#f6f8fa"
            radius: 8
            border.color: "#d1d9e0"
            border.width: 1

            ColumnLayout {
                id: oneOpColumn
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Single-operand operations"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: "#1f2328"
                }

                RowLayout {
                    spacing: 12
                    Layout.fillWidth: true

                    TextField {
                        id: inputN
                        placeholderText: "n"
                        Layout.preferredWidth: 100
                        validator: IntValidator { bottom: 0 }
                    }

                    Button {
                        text: "Factorial"
                        onClicked: callOneOp("factorial", inputN.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#0a58ca" : "#0969da"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Fibonacci"
                        onClicked: callOneOp("fibonacci", inputN.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#0a58ca" : "#0969da"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
```

Note `IntValidator { bottom: 0 }` — factorial and fibonacci are only defined for non-negative integers. The blue button colors (`#0969da`) visually distinguish these from the green two-operand buttons.

### 3.6 Version button and result display

Add these after the single-operand section:

```qml
        // Version button
        Button {
            text: "Get libcalc version"
            onClicked: callNoArg("libVersion")

            background: Rectangle {
                implicitWidth: 160
                implicitHeight: 36
                color: parent.pressed ? "#32383f" : "#24292f"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: "#ffffff"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        // Result display
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: root.errorText.length > 0 ? "#fff1f0" : "#dafbe1"
            radius: 8
            border.color: root.errorText.length > 0 ? "#ffcdd2" : "#adf0b9"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4

                Text {
                    text: root.errorText.length > 0 ? "Error" : "Result"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: root.errorText.length > 0 ? "#cf222e" : "#116329"
                }

                Text {
                    text: root.errorText.length > 0 ? root.errorText
                            : (root.result.length > 0 ? root.result
                                                      : "Press a button above")
                    font.pixelSize: 16
                    font.weight: Font.Medium
                    color: root.errorText.length > 0 ? "#cf222e" : "#1f2328"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
        }
```

The result display switches between a green success box and a red error box based on whether `errorText` is set.

### 3.7 The complete file

Here is the complete `Main.qml` with all sections assembled:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    // State
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
            color: "#1f2328"
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: "QML frontend for the calc_module (libcalc C library)"
            font.pixelSize: 13
            color: "#57606a"
            Layout.alignment: Qt.AlignHCenter
        }

        // ── Two-operand section ────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: twoOpColumn.implicitHeight + 32
            color: "#f6f8fa"
            radius: 8
            border.color: "#d1d9e0"
            border.width: 1

            ColumnLayout {
                id: twoOpColumn
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Two-operand operations"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: "#1f2328"
                }

                RowLayout {
                    spacing: 12
                    Layout.fillWidth: true

                    TextField {
                        id: inputA
                        placeholderText: "a"
                        Layout.preferredWidth: 100
                        validator: IntValidator {}
                    }

                    TextField {
                        id: inputB
                        placeholderText: "b"
                        Layout.preferredWidth: 100
                        validator: IntValidator {}
                    }

                    Button {
                        text: "Add"
                        onClicked: callTwoOp("add", inputA.text, inputB.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#1a7f37" : "#238636"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Multiply"
                        onClicked: callTwoOp("multiply", inputA.text, inputB.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#1a7f37" : "#238636"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // ── Single-operand section ─────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: oneOpColumn.implicitHeight + 32
            color: "#f6f8fa"
            radius: 8
            border.color: "#d1d9e0"
            border.width: 1

            ColumnLayout {
                id: oneOpColumn
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                Text {
                    text: "Single-operand operations"
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: "#1f2328"
                }

                RowLayout {
                    spacing: 12
                    Layout.fillWidth: true

                    TextField {
                        id: inputN
                        placeholderText: "n"
                        Layout.preferredWidth: 100
                        validator: IntValidator { bottom: 0 }
                    }

                    Button {
                        text: "Factorial"
                        onClicked: callOneOp("factorial", inputN.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#0a58ca" : "#0969da"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Fibonacci"
                        onClicked: callOneOp("fibonacci", inputN.text)

                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 36
                            color: parent.pressed ? "#0a58ca" : "#0969da"
                            radius: 6
                        }
                        contentItem: Text {
                            text: parent.text
                            color: "#ffffff"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // ── Info section ───────────────────────────────────────
        Button {
            text: "Get libcalc version"
            onClicked: callNoArg("libVersion")

            background: Rectangle {
                implicitWidth: 160
                implicitHeight: 36
                color: parent.pressed ? "#32383f" : "#24292f"
                radius: 6
            }
            contentItem: Text {
                text: parent.text
                color: "#ffffff"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        // ── Result display ─────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 64
            color: root.errorText.length > 0 ? "#fff1f0" : "#dafbe1"
            radius: 8
            border.color: root.errorText.length > 0 ? "#ffcdd2" : "#adf0b9"
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4

                Text {
                    text: root.errorText.length > 0 ? "Error" : "Result"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    color: root.errorText.length > 0 ? "#cf222e" : "#116329"
                }

                Text {
                    text: root.errorText.length > 0 ? root.errorText
                            : (root.result.length > 0 ? root.result
                                                      : "Press a button above")
                    font.pixelSize: 16
                    font.weight: Font.Medium
                    color: root.errorText.length > 0 ? "#cf222e" : "#1f2328"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
        }

        // Push everything up
        Item { Layout.fillHeight: true }
    }

    // ── Helper functions ───────────────────────────────────────

    function callModule(method, args) {
        root.errorText = ""
        root.result = ""

        if (typeof logos === "undefined" || !logos.callModule) {
            root.errorText = "Logos bridge not available (run inside logos-app)"
            return
        }

        var res = logos.callModule("calc_module", method, args)
        root.result = String(res)
    }

    function callTwoOp(method, a, b) {
        if (a === "" || b === "") {
            root.errorText = "Enter values for both a and b"
            return
        }
        callModule(method, [parseInt(a), parseInt(b)])
    }

    function callOneOp(method, n) {
        if (n === "") {
            root.errorText = "Enter a value for n"
            return
        }
        callModule(method, [parseInt(n)])
    }

    function callNoArg(method) {
        callModule(method, [])
    }
}
```

---

## Step 4: Write `flake.nix`

QML plugins don't need compilation — the Nix build just copies files to the output. But we still use a flake so the build process is consistent with core modules and the plugin can be consumed by other Nix expressions.

```nix
{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

  inputs = {
    logos-cpp-sdk.url = "github:logos-co/logos-cpp-sdk";
    nixpkgs.follows = "logos-cpp-sdk/nixpkgs";
  };

  outputs = { self, nixpkgs, logos-cpp-sdk }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f {
        pkgs = import nixpkgs { inherit system; };
      });
    in
    {
      packages = forAllSystems ({ pkgs }: let
        plugin = pkgs.stdenv.mkDerivation {
          pname = "logos-calc-ui-plugin";
          version = "1.0.0";
          src = ./.;

          dontUnpack = false;
          phases = [ "unpackPhase" "installPhase" ];

          installPhase = ''
            runHook preInstall

            dest="$out/lib"
            mkdir -p "$dest/icons"

            cp $src/Main.qml    "$dest/Main.qml"
            cp $src/metadata.json "$dest/metadata.json"

            # Copy icon if present
            if [ -f "$src/icons/calc.png" ]; then
              cp $src/icons/calc.png "$dest/icons/calc.png"
            fi

            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "Calculator QML UI Plugin for Logos";
            platforms = platforms.unix;
          };
        };
      in {
        default = plugin;
        lib = plugin;
      });
    };
}
```

**Compared to a core module's `flake.nix`** (from Part 1), this is much simpler:


|              | Core module (`calc_module`)              | QML UI (`calc_ui`)          |
| ------------ | ---------------------------------------- | --------------------------- |
| Builder      | `logos-module-builder.lib.mkLogosModule` | Plain `stdenv.mkDerivation` |
| Compilation  | CMake → C++ → `.so` plugin               | No compilation — file copy  |
| Dependencies | Qt, Logos SDK, CMake, C compiler         | None                        |
| Build time   | Minutes (first build)                    | Seconds                     |


---

## Step 5: Build the Plugin

### 5.1 Initialize the Git repo

Nix flakes require a git repository:

```bash
cd logos-calc-ui
git init
git add -A
git commit -m "Initial commit"
```

### 5.2 Build with Nix

```bash
nix build
```

This completes in seconds since there's no compilation — it just copies files.

### 5.3 Inspect the output

```bash
ls -la result/lib/
```

```
Main.qml
metadata.json
icons/
```

That's it. A QML plugin is just its source files packaged for installation.

---

## Step 6: Run in `logos-app`

### 6.1 Build `logos-app`

```bash
nix build 'github:logos-co/logos-app#app' --out-link ./logos-app
```

### 6.2 Set up the modules directory

NOTE: this is wrong

You need both the core module (from Part 1) and the QML UI plugin:

```bash
# Core module — goes in the modules directory
mkdir -p modules/calc_module
cp ../logos-calc-module/result/lib/calc_module_plugin.so modules/calc_module/
cp ../logos-calc-module/result/lib/libcalc.so modules/calc_module/
```

Create `modules/calc_module/manifest.json` (same as Part 1):

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

```bash
# QML UI plugin — goes in the ui-plugins directory
mkdir -p ui-plugins/calc_ui
cp result/lib/Main.qml ui-plugins/calc_ui/
cp result/lib/metadata.json ui-plugins/calc_ui/
cp -r result/lib/icons ui-plugins/calc_ui/
```

### 6.3 Launch

```bash
./logos-app/bin/logos-app \
  --modules-dir ./modules \
  --ui-plugins-dir ./ui-plugins
```

You should see:

1. The `logos-app` window opens with a sidebar
2. "Calculator UI" appears as a tab (with your icon if you provided one)
3. Click the tab to see your QML interface
4. Enter numbers and click **Add**, **Multiply**, **Factorial**, or **Fibonacci**
5. The result appears in the green result box

### 6.4 What happens when you click "Add"

Here's the full chain when you enter `3` and `5` and click **Add**:

```
1. QML: Button.onClicked → callTwoOp("add", "3", "5")
2. QML: callTwoOp() → callModule("add", [3, 5])
3. QML: logos.callModule("calc_module", "add", [3, 5])
4. logos-app: Routes call via IPC to logos_host process
5. logos_host: QMetaObject::invokeMethod(plugin, "add", 3, 5)
6. C++: CalcModulePlugin::add(3, 5) → calc_add(3, 5)
7. C: Returns 8
8. Back through the chain → QML: root.result = "8"
9. QML: Result box displays "8"
```

---

## Step 7: Development Workflow

### 7.1 Live reloading

For rapid iteration, use development mode. This watches your QML source files and reloads on change:

```bash
# Point QML_UI at your source directory
QML_UI=$(pwd) ./logos-app/bin/logos-app \
  --modules-dir ./modules \
  --ui-plugins-dir ./ui-plugins
```

Edit `Main.qml`, save, and the UI updates without rebuilding.

### 7.2 Debugging

Since QML plugins are sandboxed, you can't use `console.log()` to write to the terminal in production. But in development mode, `console.log()` output appears in the terminal where you launched `logos-app`.

Add debug logging to your bridge function:

```qml
function callModule(method, args) {
    console.log("callModule:", method, JSON.stringify(args))
    // ...
    var res = logos.callModule("calc_module", method, args)
    console.log("result:", res)
    root.result = String(res)
}
```

### 7.3 Testing without `logos-app`

You can open `Main.qml` in any QML viewer (e.g., `qml` from Qt) to test the layout. The `logos` bridge won't be available, so clicking buttons will show "Logos bridge not available" — but you can verify the layout and styling work correctly.

```bash
# If you have Qt installed
qml Main.qml
```

---

## Step 8: Package for Distribution (Optional)

### 8.1 Build the `lgx` tool

```bash
nix build 'github:logos-co/logos-package#lgx' --out-link ./lgx
```

### 8.2 Create a package

```bash
# Create an LGX package
./lgx/bin/lgx create calc_ui --name calc_ui

# Add the variant (QML is platform-independent, but LGX still needs a variant)
./lgx/bin/lgx add calc_ui.lgx \
  --variant linux-aarch64 \
  --files result/lib/ --main Main.qml

# Add the variant on/for Mac
./lgx/bin/lgx add calc_ui.lgx \
  --variant darwin-arm64  \
  --files result/lib/ --main Main.qml

# Verify
./lgx/bin/lgx verify calc_ui.lgx
```

### 8.3 Install on another machine

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./pm
./pm/bin/lgpm --modules-dir ./ui-plugins install --file calc_ui.lgx
```

---

## Recap: Core Module vs. QML UI Plugin


|                         | Core Module (Part 1)                          | QML UI Plugin (Part 2)            |
| ----------------------- | --------------------------------------------- | --------------------------------- |
| **Language**            | C++ (wrapping C)                              | QML (JavaScript + declarative UI) |
| **Files**               | `.cpp`, `.h`, `CMakeLists.txt`, `module.yaml` | `Main.qml` only                   |
| **Compilation**         | Yes (CMake → shared library)                  | No (file copy)                    |
| **metadata `type`**     | `"core"`                                      | `"ui_qml"`                        |
| **metadata `main`**     | `"calc_module_plugin"` (binary)               | `"Main.qml"` (source file)        |
| **Runs in**             | `logos_host` process                          | Sandboxed QML engine              |
| **Network access**      | Yes                                           | No (sandboxed)                    |
| **Filesystem access**   | Yes                                           | Own directory only (sandboxed)    |
| **Calls other modules** | Via `LogosAPI`* (C++)                         | Via `logos.callModule()` (JS)     |
| **Nix builder**         | `mkLogosModule`                               | Plain `mkDerivation`              |
| **Build time**          | Minutes (first build)                         | Seconds                           |


---

## What's Next

You now have a complete two-layer Logos application:

```
libcalc (C library)
  └── calc_module (Logos core module, wraps libcalc)
        └── calc_ui (QML UI, calls calc_module via bridge)
```

From here you could:

- **Add more methods** to `calc_module` and expose them in the UI
- **Call multiple modules** — a QML UI can call any loaded core module, not just one
- **Use the Logos Design System** — the [logos-design-system](https://github.com/logos-co/logos-design-system) QML library provides styled components for a consistent look
- **Add inter-module events** — core modules can emit events via `eventResponse` signals, and QML UIs can listen for them
- **Build a C++ UI module** — for cases where QML sandboxing is too restrictive, you can build a native Qt widget plugin (see the [Developer Guide](logos-developer-guide.md), Section 7.2)

