# Tutorial Part 2: Building a QML UI for Your Logos Module

This is Part 2 of the Logos module tutorial series. In [Part 1](tutorial-wrapping-c-library.md) you wrapped a C library as a Logos core module. Now you'll build a **QML user interface** that calls that module — first isolated with `nix run`, then packaged and loaded into `logos-basecamp`.

**What you'll build:** A `calc_ui` QML plugin with input fields and buttons that call `calc_module` methods (add, multiply, factorial, fibonacci) through the Logos bridge.

**What you'll learn:**

- How QML UI plugins work in the Logos platform
- The `logos.callModule()` bridge that connects QML to core modules
- The project structure and metadata for a QML plugin
- How to package and install your UI into `logos-basecamp`

**Prerequisites:**

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` with the shared library built (`.so` on Linux, `.dylib` on macOS in `logos-calc-module/lib/`)
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
- **Entry point** is defined by the required `"view"` field in `metadata.json` (for this tutorial it is `Main.qml`).

---

## Step 1: Scaffold

Use the QML module template from `logos-module-builder`:

```bash
mkdir logos-calc-ui && cd logos-calc-ui
nix flake init -t github:logos-co/logos-module-builder#ui-qml
git init && git add -A
```

> **Note:** The generated `flake.nix` uses an unpinned `logos-module-builder` URL. Replace it with the pinned version shown in [Step 4](#step-4-update-flakenix) to ensure reproducible builds.

This gives you:

```
logos-calc-ui/
├── flake.nix       # Nix build + nix run support
├── metadata.json   # Plugin metadata
└── Main.qml        # Your UI (starter template)
```

---

## Step 2: Update `metadata.json`

Replace the template contents with your plugin's details. The template may generate an extra `nix` section — keep it as-is, it's used by the builder:

```json
{
  "name": "calc_ui",
  "version": "1.0.0",
  "description": "Calculator UI - QML frontend for the calc_module",
  "type": "ui_qml",
  "view": "Main.qml",
  "dependencies": ["calc_module"],
  "category": "tools",
  "icon": "icons/calc.png",

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
echo "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAmElEQVR4nO3QMREAIBDAsFeEN3ziCWRkoEP2XmedfX82OkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAK0BOkBrgA7QGqADtAboAO0BN/SiO/PatoIAAAAASUVORK5CYII=" | base64 -d > icons/calc.png
```

The `view` field tells the host which QML file to load for the UI. The `dependencies` field tells the host to load `calc_module` before showing your UI.

> **Naming convention:** Each entry in `dependencies` must match the `name` field in that module's own `metadata.json`. When adding a dependency as a flake input, the **input attribute name** must also match the dependency name — e.g., `calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module"`. The URL can point to any repo, but the attribute name is how the builder resolves dependencies.

---

## Step 3: Write `Main.qml`

Replace the starter file with the calculator UI. This demonstrates two communication patterns:

1. **Direct calls** — `logos.callModule()` sends a request and returns the result immediately
2. **Event-based** — `logos.callModule()` fires-and-forgets, the module emits an event, and QML receives it via `logos.onModuleEvent()`

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property string result: ""
    property string errorText: ""
    property string versionFromEvent: ""

    // ── Event subscription ────────────────────────────────────
    // Subscribe to "versionReady" events pushed from calc_module.
    Component.onCompleted: {
        if (typeof logos !== "undefined" && logos.onModuleEvent)
            logos.onModuleEvent("calc_module", "versionReady")
    }

    Connections {
        target: typeof logos !== "undefined" ? logos : null
        function onModuleEventReceived(moduleName, eventName, data) {
            if (eventName === "versionReady")
                root.versionFromEvent = data[0]
        }
    }

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

        // ── Pattern 1: Direct call (request -> response) ──────
        Text {
            text: "Direct calls (logos.callModule -> returns result)"
            color: "#8b949e"
            font.pixelSize: 12
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
                onClicked: callTwoOp("add", inputA.text, inputB.text)
            }

            Button {
                text: "Multiply"
                onClicked: callTwoOp("multiply", inputA.text, inputB.text)
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

        // Direct call result
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

        // ── Pattern 2: Event-based (fire-and-forget -> event) ─
        Text {
            text: "Event-based (fire-and-forget call -> result via event)"
            color: "#8b949e"
            font.pixelSize: 12
        }

        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Button {
                text: "libcalc version (event)"
                onClicked: {
                    if (typeof logos !== "undefined" && logos.callModule)
                        logos.callModule("calc_module", "libVersionNotify", [])
                }
            }
        }

        // Event result
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: "#1a1a2d"
            radius: 8

            Text {
                anchors.centerIn: parent
                text: root.versionFromEvent.length > 0
                      ? ("Version (via event): " + root.versionFromEvent)
                      : "Press the event button — result arrives via event"
                color: "#7ab8ff"
                font.pixelSize: 15
            }
        }

        Item { Layout.fillHeight: true }
    }

    // ── Direct call helpers ───────────────────────────────────

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

The UI demonstrates two communication patterns:

- **Green section (direct calls):** `logos.callModule("calc_module", "libVersion", [])` sends a request to `calc_module` and returns the result synchronously. Simple request/response.

- **Blue section (event-based):** `logos.callModule("calc_module", "libVersionNotify", [])` calls the module but ignores the return value. Instead, the module emits a `"versionReady"` event via `eventResponse`, and the QML receives it through the `logos.onModuleEvent()` subscription set up in `Component.onCompleted`.

The `logos` object is injected by the host at runtime.

---

## Step 4: Update `flake.nix`

The template already has everything wired up. Update the description and add `calc_module` as a dependency input:

```nix
{
  description = "Calculator QML UI Plugin for Logos - frontend for calc_module";

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

The input attribute name (`calc_module`) must match the dependency name in `metadata.json`.

The `calc_module.url` can be either:

- **`github:`** — fetches from a remote GitHub repo. Use this for CI or when `calc_module` has been published.
- **`path:`** — points to a local directory on disk. Use this during development when both repos live side by side (e.g., `path:../logos-calc-module`).

> **Important:** Whichever URL scheme you use, `calc_module` must be built with its shared library (`.so` on Linux, `.dylib` on macOS) present in `lib/`. If the library is missing, the nix build will fail with linker errors. See [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library) for build instructions.

`mkLogosQmlModule` handles everything — it stages QML files, metadata, and icons into a plugin directory, bundles all module dependencies (direct and transitive) from their LGX packages, and automatically wires up `apps.default` so `nix run .` launches the UI in a standalone window with all required backend modules self-contained. `flakeInputs = inputs` passes all inputs so that dependencies declared in `metadata.json` are resolved automatically.

> **Tip:** Even if `flake.nix` uses a `github:` URL, you can override it at build time with `--override-input calc_module path:../logos-calc-module` to use your local checkout without editing `flake.nix`. This is covered in [Step 5.2](#52-full-functionality-with-modules).

---

## Step 5: Test with `nix run`

### 5.1 UI only (layout preview)

```bash
git add -A
nix flake update   # regenerate flake.lock to match the pinned inputs in flake.nix
git add flake.lock
nix run .
```

The app opens immediately. No modules are loaded, so clicking buttons shows "Logos bridge not available" — but you can verify the layout and styling look correct.

### 5.2 Full functionality (with modules)

The standalone app automatically bundles and loads all module dependencies declared in `metadata.json`. To test with your local `calc_module` from Part 1, you first need to make sure it has been built and its shared library (`.so` on Linux, `.dylib` on macOS) is present.

#### Ensure `calc_module` is built

Go back to your `logos-calc-module` directory and verify the shared library exists:

```bash
ls ../logos-calc-module/lib/libcalc.so    # Linux
ls ../logos-calc-module/lib/libcalc.dylib  # macOS
```

If the file is missing, build it first (as covered in [Part 1, Step 1.5](tutorial-wrapping-c-library.md#15-build-the-shared-library)):

```bash
cd ../logos-calc-module/lib
gcc -shared -fPIC -o libcalc.so libcalc.c     # Linux
# gcc -shared -fPIC -o libcalc.dylib libcalc.c  # macOS
cd ../../logos-calc-ui
```

Also make sure the module itself builds successfully:

```bash
cd ../logos-calc-module
git add -A
nix build
cd ../logos-calc-ui
```

The `nix build` produces `result/lib/calc_module_plugin.so` (or `.dylib`), which is the compiled Qt plugin. The `lib/libcalc.so` (or `.dylib`) inside the source tree is the underlying C library that gets linked in during the build.

#### Option A: Use `--override-input` (quick, no flake.nix edits)

If your `flake.nix` points to a `github:` URL, you can override it at build time to use your local checkout:

```bash
nix run . --override-input calc_module path:../logos-calc-module
```

This tells nix to resolve the `calc_module` flake input from your local directory instead of from the remote URL. Any changes you've made to `calc_module` locally (including the built `.so`/`.dylib` in `lib/`) are picked up immediately — no need to push to GitHub first.

#### Option B: Set `path:` in `flake.nix` (persistent local development)

If you're iterating on both repos side by side, you can point the flake input directly to your local `calc_module` checkout. In `flake.nix`, change:

```nix
# From remote:
calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
# To local:
calc_module.url = "path:../logos-calc-module";
```

Then run normally without overrides:

```bash
nix flake update   # re-lock with the local path
git add flake.lock
nix run .
```

This is convenient when you always want to build against the local copy. Switch back to `github:` when you're ready to pin to a published version.

#### Option C: Pin to the remote repo

If `calc_module` has been pushed to the remote repository (with the `.so`/`.dylib` committed in `lib/`), the `github:` URL in `flake.nix` already points to it. A plain `nix run .` fetches and builds `calc_module` from the remote:

```bash
nix run .
```

> **Important:** The remote repo must contain the built `.so`/`.dylib` in `lib/` (or the nix build must produce it). If the shared library is missing, the `calc_module` build will fail with linker errors.

Whichever option you choose, clicking **Add**, **Multiply**, **Factorial**, or **Fibonacci** now calls the real module.

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

Create `.lgx` packages for both dev and portable variants. Use `--out-link` to avoid overwriting the `result` symlink:

```bash
# Package calc_module (from Part 1)
cd ../logos-calc-module
nix build '.#lgx' --out-link result-lgx
nix build '.#lgx-portable' --out-link result-lgx-portable

# Package the QML UI plugin
cd ../logos-calc-ui
nix build '.#lgx' --out-link result-lgx
nix build '.#lgx-portable' --out-link result-lgx-portable
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

Install your modules using `lgpm`. First, set `BASECAMP_DIR` to your platform's path:

```bash
# macOS:
BASECAMP_DIR="$HOME/Library/Application Support/Logos/LogosBasecampDev"

# Linux:
BASECAMP_DIR="$HOME/.local/share/Logos/LogosBasecampDev"
```

```bash
# Build lgpm CLI
nix build 'github:logos-co/logos-package-manager#cli' --out-link ./pm

# Install core module
./pm/bin/lgpm --modules-dir "$BASECAMP_DIR/modules" \
  install --file ../logos-calc-module/result-lgx/*.lgx

# Install UI plugin
./pm/bin/lgpm --ui-plugins-dir "$BASECAMP_DIR/plugins" \
  install --file result-lgx/*.lgx

# Launch basecamp -- your modules appear alongside the built-in ones
./basecamp-result/bin/logos-basecamp
```

### 7.3 Portable basecamp build (optional)

The dev build above depends on nix store paths at runtime. For a self-contained portable build that works without nix:

```bash
# Build portable basecamp (bundles all Qt frameworks/libraries)
nix build 'github:logos-co/logos-basecamp#bin-bundle-dir' -o basecamp-portable

# Launch once to preinstall bundled modules
./basecamp-portable/bin/logos-basecamp
```

The portable build uses a different data directory (`LogosBasecamp` instead of `LogosBasecampDev`). Set `BASECAMP_DIR` to your platform's path:

```bash
# macOS:
BASECAMP_DIR="$HOME/Library/Application Support/Logos/LogosBasecamp"

# Linux:
BASECAMP_DIR="$HOME/.local/share/Logos/LogosBasecamp"
```

Install your modules using the **portable** `.lgx` variants:

```bash
# Install core module (use portable variant)
./pm/bin/lgpm --modules-dir "$BASECAMP_DIR/modules" \
  install --file ../logos-calc-module/result-lgx-portable/*.lgx

# Install UI plugin (use portable variant)
./pm/bin/lgpm --ui-plugins-dir "$BASECAMP_DIR/plugins" \
  install --file result-lgx-portable/*.lgx

# Launch
./basecamp-portable/bin/logos-basecamp
```

> **Important:** Portable basecamp requires portable `.lgx` variants (`result-lgx-portable`), and the dev build requires dev variants (`result-lgx`). Mixing them will cause loading failures.

### 7.4 Install via logos-basecamp UI

Instead of using `lgpm` on the command line, you can install modules through the basecamp UI:

1. Launch `logos-basecamp`
2. Go to **Package Manager**
3. Click **Install from file**
4. Select `../logos-calc-module/result-lgx/*.lgx` — installs `calc_module`
5. Repeat for `result-lgx/*.lgx` — installs `calc_ui`

The "Calculator UI" tab appears in the sidebar. Clicking it loads your `Main.qml`.

### 7.5 Live reloading with `logos-standalone-app`

For rapid iteration on QML without rebuilding, set `QML_PATH` to your QML source directory:

```bash
QML_PATH=$PWD nix run .
```

Edit `Main.qml`, close and re-run — changes appear immediately without `nix build`. When `QML_PATH` is set, the plugin loads QML files from the filesystem instead of from Qt resources, so your edits are picked up on each launch.

> This does not work with `logos-basecamp`. Basecamp loads QML plugins from its own data directory, so changes to your source files are not reflected until you rebuild and reinstall the `.lgx` package.

### 7.6 Testing without any runtime

You can open `Main.qml` in any QML viewer (e.g., `qml` from Qt) to test the layout.

#### Install

You'll need to have QML and any included modules (`QtQuick` and submodules `Controls`, and `Layout`).

Eg, to simply install on linux (apt package manager):

```bash
sudo apt install qml-qt6 qml6-module-qtquick qml6-module-qtquick-controls qml6-module-qtquick-layouts
```

#### Viewing the QML

The `logos` bridge won't be available, so clicking buttons will show "Logos bridge not available" -- but you can verify the layout and styling work correctly.

```bash
# If you have Qt and included modules installed
# macOS:
qml Main.qml

# Linux:
qml6 Main.qml
```

---

## Step 8: UI Integration Tests (Optional)

You can add automated UI tests that verify your QML plugin renders correctly. The test infrastructure is built into `logos-module-builder` — just add `.mjs` test files to a `tests/` directory and you get `nix build .#integration-test` for free.

Tests use the [logos-qt-mcp](https://github.com/logos-co/logos-qt-mcp) test framework, which connects to the QML inspector inside `logos-standalone-app` and can find elements, click buttons, verify text, and take screenshots.

### 8.1 Create a test file

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

test("calc_ui: loads and shows title", async (app) => {
  await app.waitFor(
    async () => {
      await app.expectTexts(["Calculator"]);
    },
    { timeout: 15000, interval: 500, description: "calc_ui to load" },
  );
});

test("calc_ui: add button visible", async (app) => {
  await app.expectTexts(["Add"]);
});

test("calc_ui: click add and check result", async (app) => {
  await app.click("Add");
  // Verify the result appears (depends on your UI)
  await app.waitFor(
    async () => {
      await app.expectTexts(["Result:"]);
    },
    { timeout: 5000, interval: 500, description: "result to appear" },
  );
});

run();
```

### 8.2 Run the tests

```bash
git add tests/

# Hermetic CI test (builds everything, runs headless)
nix build .#integration-test -L

# Interactive: build test framework, run against a running app
nix build .#test-framework -o result-mcp
nix run .          # start the app with inspector on :3768
node tests/ui-tests.mjs  # in another terminal
```

The `integration-test` output launches `logos-standalone-app` with `QT_QPA_PLATFORM=offscreen` (no display needed), connects to the QML inspector, and runs all `.mjs` files in `tests/`.

You can have multiple test files (e.g., `tests/smoke.mjs`, `tests/interactions.mjs`) — they are all discovered and run automatically.

---

## Known Limitations

### QML-to-C++ type coercion

When calling C++ module methods from QML via `logos.callModule()`, arguments are passed through IPC as `QVariant` values. The runtime automatically coerces mismatched types to match the target method signature — for example, a `double` sent from QML will be converted to `int` if the method expects `int`, and numeric strings will be converted to their numeric types.

This means you can define methods with their natural parameter types (`int`, `bool`, `double`, etc.) and calls from QML will work without manual conversion:

```cpp
// This works — the runtime coerces arguments automatically
Q_INVOKABLE int add(int a, int b) { return a + b; }
```

> **Note:** Type coercion uses `QVariant::convert()`, which rounds (not truncates) when converting `double` to `int` — e.g., `3.7` becomes `4`.

### QML changes not appearing after rebuild

Qt caches compiled QML on disk. If you update your `Main.qml`, rebuild and reinstall the `.lgx`, but the old UI still appears, the cache is stale. Fix by disabling the cache before launching:

```bash
QML_DISABLE_DISK_CACHE=1 ./basecamp-result/bin/logos-basecamp
```

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

## Recap

|                     | Core Module (Part 1)                            | QML UI Plugin (Part 2)        |
| ------------------- | ----------------------------------------------- | ----------------------------- |
| Language            | C++                                             | QML / JavaScript              |
| Files               | `.cpp`, `.h`, `CMakeLists.txt`, `metadata.json` | `Main.qml`, `metadata.json`   |
| Compilation         | Yes (CMake → `.so`)                             | No (file copy)                |
| `metadata.type`     | `"core"`                                        | `"ui_qml"`                    |
| Test command        | `logoscore -m ./result/lib -l calc_module`      | `nix run .`                   |
| Calls other modules | Via `LogosAPI*` (C++)                           | Via `logos.callModule()` (JS) |

---

## What's Next

- **Add more methods** to `calc_module` and call them from QML
- **Use Logos Design System** styled components for consistent look and feel
- **Build a C++ UI module** for cases where QML sandboxing is too restrictive — see [Developer Guide](logos-developer-guide.md), Section 7.2
