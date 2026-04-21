# Logos Module Developer Guide

A comprehensive guide to creating, building, testing, packaging, and distributing modules for the Logos platform.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Part 1: Creating a Module](#part-1-creating-a-module)
  - [1.1 Scaffold with logos-module-builder](#11-scaffold-with-logos-module-builder)
  - [1.2 Project Structure](#12-project-structure)
  - [1.3 The metadata.json Configuration](#13-the-metadatajson-configuration)
  - [1.4 Writing Module Code](#14-writing-module-code)
  - [1.5 Building Your Module](#15-building-your-module)
- [Part 2: Inspecting Your Module](#part-2-inspecting-your-module)
  - [2.1 The lm CLI Tool](#21-the-lm-cli-tool)
  - [2.2 The logos-module-viewer](#22-the-logos-module-viewer)
- [Part 3: Testing UI Modules](#part-3-testing-ui-modules)
  - [3.1 How It Works](#31-how-it-works)
  - [3.2 Writing Tests](#32-writing-tests)
  - [3.3 Running Tests](#33-running-tests)
- [Part 4: Packaging Your Module](#part-4-packaging-your-module)
  - [4.1 The LGX Package Format](#41-the-lgx-package-format)
  - [4.2 Building LGX Packages](#42-building-lgx-packages)
    - [Built-in Nix Derivation (Preferred)](#built-in-nix-derivation-preferred)
    - [Using nix bundle (Alternative)](#using-nix-bundle-alternative)
- [Part 5: Installing and Managing Modules](#part-5-installing-and-managing-modules)
  - [5.1 The lgpm CLI](#51-the-lgpm-cli)
  - [5.2 Installing from Local Files](#52-installing-from-local-files)
  - [5.3 Installing from a Registry](#53-installing-from-a-registry)
- [Part 6: Running Your Module](#part-6-running-your-module)
  - [6.1 Running with logoscore](#61-running-with-logoscore)
- [Part 7: Running in logos-basecamp](#part-7-running-in-logos-basecamp)
  - [7.1 Building logos-basecamp](#71-building-logos-basecamp)
  - [7.2 Module Types in logos-basecamp](#72-module-types-in-logos-basecamp)
- [Part 8: Inter-Module Communication](#part-8-inter-module-communication)
  - [8.1 The LogosAPI](#81-the-logosapi)
  - [8.2 The C++ SDK Code Generator](#82-the-c-sdk-code-generator)
  - [8.3 LogosResult](#83-logosresult)
  - [8.4 Communication Modes](#84-communication-modes)
- [Part 9: Advanced Topics](#part-9-advanced-topics)
  - [9.1 Tutorials](#91-tutorials)
  - [9.2 Module Dependencies](#92-module-dependencies)
- [Reference: Repository Map](#reference-repository-map)
- [Reference: CLI Tools Summary](#reference-cli-tools-summary)
- [Troubleshooting](#troubleshooting)

---

## Overview

The **Logos platform** is a modular application framework built in C++ on top of Qt 6. Applications are composed of dynamically loaded **modules** (plugins) that communicate via an IPC layer. The platform provides:

- **Process isolation** -- each module runs in its own host process (on desktop), communicating via Qt Remote Objects
- **Cross-platform support** -- macOS (arm64, x86_64) and Linux (arm64, x86_64)
- **A package format** (`.lgx`) for distributing modules with platform-specific variants
- **A desktop application shell** (`logos-basecamp`) with a sidebar, tabbed workspace, and plugin management UI
- **A CLI runtime** (`logoscore`) for running modules headlessly

## Architecture

```
+---------------------------------------------------------------+
|                     Application Layer                          |
|   logos-basecamp (Desktop GUI)  or  logoscore (CLI Runtime)        |
+---------------------------------------------------------------+
        |                    |                    |
        v                    v                    v
+---------------+  +------------------+  +------------------+
|  Module A     |  |  Module B        |  | Package Manager  |
| (logos_host)  |  | (logos_host)     |  | Module           |
+-------+-------+  +--------+---------+  +--------+---------+
        |                    |                     |
        |        Qt Remote Objects (IPC)           |
        +--------------------------------------------+
                             |
                    +--------v---------+
                    |    liblogos      |  (Core Runtime)
                    | logos-liblogos   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  logos-cpp-sdk   |  (SDK: LogosAPI,
                    |                  |   Code Generator,
                    |                  |   Types, IPC)
                    +------------------+
```

**Key components:**

| Component                    | Repository                                                                                | Role                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **logos-module-builder**     | [logos-co/logos-module-builder](https://github.com/logos-co/logos-module-builder)         | Scaffolding and build system for new modules              |
| **logos-module**             | [logos-co/logos-module](https://github.com/logos-co/logos-module)                         | Plugin loading/introspection library + `lm` CLI           |
| **logos-cpp-sdk**            | [logos-co/logos-cpp-sdk](https://github.com/logos-co/logos-cpp-sdk)                       | C++ SDK, types, IPC layer, code generator                 |
| **logos-liblogos**           | [logos-co/logos-liblogos](https://github.com/logos-co/logos-liblogos)                     | Core library (`logos_host`, `liblogos_core`)              |
| **logos-logoscore-cli**      | [logos-co/logos-logoscore-cli](https://github.com/logos-co/logos-logoscore-cli)           | Headless CLI runtime (`logoscore`)                        |
| **logos-package**            | [logos-co/logos-package](https://github.com/logos-co/logos-package)                       | LGX package format library + `lgx` CLI                    |
| **logos-package-manager**    | [logos-co/logos-package-manager](https://github.com/logos-co/logos-package-manager)       | Local package manager library + `lgpm` CLI                |
| **logos-package-downloader** | [logos-co/logos-package-downloader](https://github.com/logos-co/logos-package-downloader) | Online catalog browser + `lgpd` CLI                       |
| **logos-standalone-app**     | [logos-co/logos-standalone-app](https://github.com/logos-co/logos-standalone-app)         | Minimal shell for running/testing UI modules in isolation |
| **logos-basecamp**           | [logos-co/logos-basecamp](https://github.com/logos-co/logos-basecamp)                     | Desktop application shell                                 |

## Prerequisites

### Required

- **Nix** with flakes enabled. This is the primary build tool for the entire ecosystem. Install Nix from [nixos.org](https://nixos.org/download.html), then enable flakes:

  ```bash
  # If you need experimental features enabled per-command:
  nix --extra-experimental-features "nix-command flakes" <command>

  # Or enable globally in ~/.config/nix/nix.conf:
  experimental-features = nix-command flakes
  ```

### Recommended Knowledge

- C++ (C++17)
- Qt 6 basics (`QObject`, `Q_INVOKABLE`, `Q_PLUGIN_METADATA`, signals/slots)
- Basic CMake
- Basic Nix concepts (flakes, derivations)

---

## Part 1: Creating a Module

### 1.1 Scaffold with logos-module-builder

The fastest way to create a new module is using the **logos-module-builder** template:

```bash
# Create a new directory for your module
mkdir logos-my-module && cd logos-my-module

# Scaffold a minimal core module (no external dependencies)
nix flake init -t github:logos-co/logos-module-builder

# Or scaffold a module that wraps an external C/C++ library
nix flake init -t github:logos-co/logos-module-builder#with-external-lib

# For ui_qml modules with C++ backend (process-isolated)
nix flake init -t github:logos-co/logos-module-builder#ui-qml-backend

# For ui_qml modules (QML-only, no C++)
nix flake init -t github:logos-co/logos-module-builder#ui-qml
```

> **Note:** The generated `flake.nix` uses an unpinned `logos-module-builder` URL. For reproducible builds, pin it to a specific commit — see the `flake.nix` examples in [Section 3.2](#32-building-lgx-packages) and the [tutorials](tutorial-wrapping-c-library.md#23-flakenix--nix-build-config).

**Available templates:**

| Template            | Use Case                                              |
| ------------------- | ----------------------------------------------------- |
| `default`           | Minimal core module (C++ backend, no UI)              |
| `with-external-lib` | Core module wrapping an external C/C++ library        |
| `ui-qml-backend`    | ui_qml with C++ backend + QML view (process-isolated) |
| `ui-qml`            | ui_qml QML-only (in-process, no C++)                  |

The `ui-qml-backend` and `ui-qml` templates automatically enable `nix run` to launch and test your UI plugin in isolation without the full logos-basecamp shell. The standalone app runner is bundled with `logos-module-builder` — no extra flake input is needed. All module dependencies declared in `metadata.json` are auto-bundled from their LGX packages.

This generates a ready-to-build project with all the boilerplate handled for you.

### 1.2 Project Structure

> We will use the `default` template here (minimal core module).

After scaffolding, your module directory looks like this:

```
logos-my-module/
├── flake.nix              # Nix flake (build config, ~15 lines)
├── metadata.json          # Single source of truth: module metadata + build config (~30 lines)
├── CMakeLists.txt         # CMake build file (~25 lines)
└── src/
    ├── my_module_interface.h    # Qt interface definition
    ├── my_module_plugin.h       # Plugin header
    └── my_module_plugin.cpp     # Plugin implementation
```

The key insight: **logos-module-builder** reduces ~600 lines of configuration across 5+ files down to ~70 lines across 2-3 files. `metadata.json` serves as the single source of truth — it contains both the runtime metadata (embedded into the plugin binary by Qt) and the build configuration (read by the builder via the `nix` section).

The `CMakeLists.txt` is minimal -- it includes `LogosModule.cmake` (provided by the builder) and calls the `logos_module()` macro, which sets up the Qt plugin target, links the SDK, configures include paths, and handles code generation. You just list your source files. See the generated [`CMakeLists.txt`](https://github.com/logos-co/logos-module-builder/blob/master/templates/minimal-module/CMakeLists.txt) in the template.

### 1.3 The metadata.json Configuration

The `metadata.json` file is the single source of truth for your module. It is embedded into the plugin binary by Qt's `Q_PLUGIN_METADATA` macro (for runtime metadata), read by `logos-module-builder` to configure the Nix build, used by CMake to resolve external dependencies and link libraries (via the `nix` section), and used by `nix-bundle-lgx` to generate the LGX manifest. See the scaffolded [`metadata.json`](https://github.com/logos-co/logos-module-builder/blob/master/templates/minimal-module/metadata.json) in the template.

The full set of available fields:

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "My first Logos module",
  "icon": null,
  "main": "my_module_plugin",
  "dependencies": [],
  "include": [],

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

**Field reference:**

| Field                            | Required                               | Default            | Description                                                                                                                                                                                                                                                    |
| -------------------------------- | -------------------------------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`                           | Yes                                    | --                 | Module name (used for filenames and identifiers)                                                                                                                                                                                                               |
| `version`                        | No                                     | `1.0.0`            | Semantic version                                                                                                                                                                                                                                               |
| `type`                           | No                                     | `core`             | Module type (`core`, `ui`, `ui_qml`)                                                                                                                                                                                                                           |
| `category`                       | No                                     | `general`          | Category (general, network, chat, wallet, integration)                                                                                                                                                                                                         |
| `description`                    | No                                     | `"A Logos module"` | Human-readable description                                                                                                                                                                                                                                     |
| `icon`                           | No                                     | `null`             | Relative path to the module icon (used by UI modules). The build system includes it in the standalone app plugin directory.                                                                                                                                    |
| `main`                           | Yes (`core`/`ui`), optional (`ui_qml`) | --                 | Plugin entry point. For `core`/`ui` modules: plugin name without extension. For `ui_qml`: optional backend plugin name (omit if QML-only).                                                                                                                     |
| `view`                           | Yes (`ui_qml`)                         | --                 | Relative path to the QML entry file (e.g. `Main.qml`). Required for `ui_qml` modules.                                                                                                                                                                          |
| `dependencies`                   | No                                     | `[]`               | Other Logos module names this depends on. Each entry must match the `name` field in that dependency's `metadata.json`.                                                                                                                                         |
| `include`                        | No                                     | `[]`               | Additional files (e.g. shared libraries like `libwaku.so`, `libwaku.dylib`) to bundle alongside the plugin in the output.                                                                                                                                      |
| `nix.packages.build`             | No                                     | `[]`               | Nix packages for build time                                                                                                                                                                                                                                    |
| `nix.packages.runtime`           | No                                     | `[]`               | Nix packages for runtime                                                                                                                                                                                                                                       |
| `nix.external_libraries`         | No                                     | `[]`               | External C/C++ libraries to wrap. Each entry is an object — see [configuration reference](https://github.com/logos-co/logos-module-builder/blob/master/docs/configuration.md#nixexternal_libraries) for fields (`name`, `vendor_path`, `build_command`, etc.). |
| `nix.cmake.find_packages`        | No                                     | `[]`               | CMake `find_package()` calls                                                                                                                                                                                                                                   |
| `nix.cmake.extra_sources`        | No                                     | `[]`               | Additional source files to compile                                                                                                                                                                                                                             |
| `nix.cmake.extra_include_dirs`   | No                                     | `[]`               | Additional include directories                                                                                                                                                                                                                                 |
| `nix.cmake.extra_link_libraries` | No                                     | `[]`               | Additional libraries to link                                                                                                                                                                                                                                   |

### 1.4 Understanding the Module Code

The scaffolded source files form a standard **Qt plugin**. Browse the full source in the template:
[`src/`](https://github.com/logos-co/logos-module-builder/tree/master/templates/minimal-module/src) --
[`minimal_interface.h`](https://github.com/logos-co/logos-module-builder/blob/master/templates/minimal-module/src/minimal_interface.h) |
[`minimal_plugin.h`](https://github.com/logos-co/logos-module-builder/blob/master/templates/minimal-module/src/minimal_plugin.h) |
[`minimal_plugin.cpp`](https://github.com/logos-co/logos-module-builder/blob/master/templates/minimal-module/src/minimal_plugin.cpp)

Every Logos module must:

1. **Inherit from `QObject` and implement `PluginInterface`** -- the interface header declares pure-virtual methods; the plugin class implements them.
2. **Declare `Q_INTERFACES` and `Q_PLUGIN_METADATA`** -- this is how Qt discovers the plugin and embeds `metadata.json`.
3. **Mark callable methods with `Q_INVOKABLE`** -- any `Q_INVOKABLE` method is automatically discoverable by `lm`, callable by `logoscore -c`, and accessible from other modules via `LogosAPI`.

**Key rules:**

- Every `Q_INVOKABLE` method is discoverable and callable by other modules at runtime
- `initLogos(LogosAPI*)` is called by the host when your module is loaded -- store the pointer for later use
- The `eventResponse` signal is used for event forwarding between modules
- `name()` must match the `name` field in your `metadata.json`

### 1.5 Building Your Module

```bash
# Nix requires all source files to be tracked by git
git init && git add -A

# Build everything (library + generated SDK headers)
nix build

# Build just the plugin shared library (.so / .dylib)
nix build .#lib

# Build just the generated SDK headers (for other modules to use)
nix build .#include

# Enter the dev shell for manual CMake builds (see: https://nix.dev/tutorials/first-steps/dev-environment)
# The shell provides cmake, ninja, Qt, the Logos SDK, and all build dependencies.
nix develop
cmake -B build -GNinja && cmake --build build
```

**Build outputs:**

```
result/
├── lib/
│   └── my_module_plugin.so       # (or .dylib on macOS)
└── include/
    ├── my_module_api.h           # Generated type-safe wrapper header
    └── my_module_api.cpp         # Generated wrapper implementation
```

---

## Part 2: Inspecting Your Module

### 2.1 The `lm` CLI Tool

The **`lm`** tool (from `logos-module`) lets you inspect compiled module binaries without loading them into the full runtime. It reads metadata and enumerates methods via Qt's meta-object system.

#### Building lm

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

#### Viewing Metadata

```bash
# Human-readable metadata
./lm/bin/lm metadata ./result/lib/my_module_plugin.so

# JSON output
./lm/bin/lm metadata ./result/lib/my_module_plugin.so --json
```

Example JSON output:

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "description": "My first Logos module",
  "author": "",
  "type": "core",
  "dependencies": []
}
```

#### Viewing Methods

```bash
# Human-readable method list
./lm/bin/lm methods ./result/lib/my_module_plugin.so

# JSON output
./lm/bin/lm methods ./result/lib/my_module_plugin.so --json
```

Example JSON output:

```json
[
  {
    "name": "initLogos",
    "signature": "initLogos(LogosAPI*)",
    "returnType": "void",
    "isInvokable": true,
    "parameters": [{ "name": "logosAPIInstance", "type": "LogosAPI*" }]
  },
  {
    "name": "doSomething",
    "signature": "doSomething(QString)",
    "returnType": "QString",
    "isInvokable": true,
    "parameters": [{ "name": "input", "type": "QString" }]
  }
]
```

### 2.2 The logos-module-viewer

The **logos-module-viewer** is a graphical tool for inspecting loaded modules.

```bash
# Build the viewer
nix build 'github:logos-co/logos-module-viewer#app' --out-link ./logos-viewer

# Run it with your module
./logos-viewer/bin/logos-module-viewer -m ./result/lib/my_module_plugin.so
```

This opens a window showing the module's metadata, methods, and allows interactive method invocation.

---

## Part 3: Testing UI Modules

For `ui_qml` modules (both QML-only and C++ backend), `logos-module-builder` provides automatic integration testing using the [logos-qt-mcp](https://github.com/logos-co/logos-qt-mcp) QML inspector.

### 3.1 How It Works

The test infrastructure has three layers:

1. **QML Inspector** — a TCP server compiled into `logos-standalone-app` that exposes the QML object tree
2. **MCP Server** — a Node.js bridge that translates test commands into inspector calls
3. **Test Framework** — a JavaScript API for writing UI assertions (`expectTexts`, `click`, `waitFor`, etc.)

When you run `nix build .#integration-test`, the builder:

- Launches `logos-standalone-app` with your plugin in headless mode (`QT_QPA_PLATFORM=offscreen`)
- Connects to the QML inspector
- Runs all `.mjs` test files in your `tests/` directory

### 3.2 Writing Tests

Create `.mjs` files in `tests/`. Each file imports the test framework and defines test cases:

```javascript
import { resolve } from "node:path";

// CI sets LOGOS_QT_MCP automatically; for interactive use: nix build .#test-framework -o result-mcp
const root =
  process.env.LOGOS_QT_MCP ||
  new URL("../result-mcp", import.meta.url).pathname;
const { test, run } = await import(
  resolve(root, "test-framework/framework.mjs")
);

test("my_module: loads UI", async (app) => {
  await app.waitFor(
    async () => {
      await app.expectTexts(["Hello"]);
    },
    { timeout: 15000, interval: 500, description: "UI to load" },
  );
});

test("my_module: click button", async (app) => {
  await app.click("Submit");
  await app.expectTexts(["Result:"]);
});

run();
```

Key test APIs:

- `app.expectTexts(["text1", "text2"])` — assert text is visible in the UI
- `app.click("Button Text")` — find an element by text and click it
- `app.waitFor(fn, opts)` — retry an assertion until it passes or times out
- `app.screenshot()` — capture the current UI state

### 3.3 Running Tests

```bash
# Hermetic CI test (builds everything, no display needed)
nix build .#integration-test -L

# Interactive: build the test framework locally (one-time)
nix build .#test-framework -o result-mcp

# Start the app (inspector listens on localhost:3768)
nix run .

# Run tests against the running app (in another terminal)
node tests/ui-tests.mjs
```

Multiple test files in `tests/` are discovered and run automatically. You can organize tests by concern (e.g., `tests/smoke.mjs`, `tests/interactions.mjs`).

> **Note:** The integration test infrastructure requires `logos-standalone-app` with QML inspector support. This is provided automatically by `logos-module-builder` — no extra flake inputs needed.

---

## Part 4: Packaging Your Module

Before you can run your module with `logoscore` or install it into `logos-basecamp`, you need to package the build output into an `.lgx` package and install it into a `modules/` directory.

### 4.1 The LGX Package Format

Logos modules are distributed as **`.lgx` packages**. An LGX file is a gzip-compressed tar archive with a specific internal structure:

```
mymodule.lgx (tar.gz)
├── manifest.json          # Package metadata
├── variants/
│   ├── linux-amd64/
│   │   └── my_module_plugin.so
│   ├── darwin-arm64/
│   │   └── my_module_plugin.dylib
│   └── darwin-arm64-dev/
│       └── my_module_plugin.dylib
├── docs/                  # Optional
└── licenses/              # Optional
```

The **manifest.json** is auto-generated from your module's `metadata.json` by the bundler. It maps each variant to its main entry point.

### 4.2 Building LGX Packages

There are two ways to create `.lgx` packages. The preferred approach uses the built-in Nix derivation that comes with `logos-module-builder`. Alternatively, you can use the `nix bundle` command directly.

#### Built-in Nix Derivation (Preferred)

When your module uses `logos-module-builder`, LGX package outputs are automatically available as part of your flake (the builder includes `nix-bundle-lgx` internally):

```bash
# Dev variant (uses /nix/store references, for local development)
nix build .#lgx

# Portable variant (self-contained, all dependencies bundled)
nix build .#lgx-portable

```

This produces a `my_module-<version>.lgx` file in the `result/` directory.

This works because `logos-module-builder` includes `nix-bundle-lgx` as its own dependency and both `mkLogosModule` and `mkLogosQmlModule` automatically create the `lgx` and `lgx-portable` package outputs. No extra configuration is needed — it is part of the standard module template:

```nix
{
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

#### Using `nix bundle` (Alternative)

You can also create `.lgx` packages using the `nix bundle` command directly. This is useful if your module does not use `logos-module-builder`, or if you need the `dual` bundling mode (both dev and portable in a single `.lgx` file) which is only available via the `nix bundle` command:

```bash
# Dev variant
nix bundle --bundler github:logos-co/nix-bundle-lgx .#lib

# Portable variant
nix bundle --bundler github:logos-co/nix-bundle-lgx#portable .#lib

# Dual variant (both dev and portable in one .lgx file)
nix bundle --bundler github:logos-co/nix-bundle-lgx#dual .#lib
```

This produces a `my_module-<version>.lgx` file in the current directory.

**Bundling modes:**

| Mode         | Built-in Command              | `nix bundle` Command                      | Variant Created       | Use Case                                     |
| ------------ | ----------------------------- | ----------------------------------------- | --------------------- | -------------------------------------------- |
| **Dev**      | `nix build .#lgx`             | `nix bundle --bundler ...#default .#lib`  | `darwin-arm64-dev`    | Local development (requires Nix store)       |
| **Portable** | `nix build .#lgx-portable`    | `nix bundle --bundler ...#portable .#lib` | `darwin-arm64`        | Distribution (self-contained, no Nix needed) |
| **Dual**     | _(not available as built-in)_ | `nix bundle --bundler ...#dual .#lib`     | Both dev and portable | One package for both environments            |

**Variant naming:**

| Nix System       | Dev Variant        | Portable Variant |
| ---------------- | ------------------ | ---------------- |
| `aarch64-darwin` | `darwin-arm64-dev` | `darwin-arm64`   |
| `x86_64-darwin`  | `darwin-amd64-dev` | `darwin-amd64`   |
| `aarch64-linux`  | `linux-arm64-dev`  | `linux-arm64`    |
| `x86_64-linux`   | `linux-amd64-dev`  | `linux-amd64`    |

> **Important:** The variant type matters when installing into `logos-basecamp`. A dev build of basecamp expects dev variants, and a portable build expects portable variants. Use the `dual` bundler to produce packages that work with both.

---

## Part 5: Installing and Managing Modules

### 5.1 The `lgpm` CLI

The **`lgpm`** CLI (Logos Package Manager) installs, searches, and manages module packages. Installing a package extracts it into a `modules/` directory that `logoscore` and `logos-basecamp` can load from.

#### Building lgpm

```bash
nix build 'github:logos-co/logos-package-manager#cli' --out-link ./package-manager
```

#### Commands

`lgpm` manages **locally-available** `.lgx` packages. It does not download packages from the network — use `lgpd` (logos-package-downloader) for that.

```bash
# Install from a local .lgx file
./package-manager/bin/lgpm --modules-dir ./modules install --file ./my_module.lgx

# Install all .lgx files in a directory
./package-manager/bin/lgpm --modules-dir ./modules install --dir ./packages/

# List installed packages
./package-manager/bin/lgpm --modules-dir ./modules list

# Show installed package details
./package-manager/bin/lgpm --modules-dir ./modules info my_module
```

#### Global Options

| Option                    | Description                                 |
| ------------------------- | ------------------------------------------- |
| `--modules-dir <path>`    | Target directory for installed core modules |
| `--ui-plugins-dir <path>` | Target directory for UI plugins             |
| `--json`                  | Output in JSON format                       |
| `-h, --help`              | Show help                                   |

### 5.2 Installing from Local Files

```bash
# Install a locally built .lgx package into a modules/ directory
./package-manager/bin/lgpm --modules-dir ./modules install --file ./my_module-1.0.0.lgx
```

After installation, the `modules/` directory contains your extracted module:

```
modules/
└── my_module/
    ├── manifest.json
    ├── my_module_plugin.dylib   # (or .so on Linux)
    └── variant
```

### 5.3 Downloading and Installing from a Registry

To download packages from the online catalog and then install them locally, use `lgpd` (logos-package-downloader) followed by `lgpm`:

```bash
# Build lgpd
nix build 'github:logos-co/logos-package-downloader#cli' --out-link ./downloader

# Search for packages
./downloader/bin/lgpd search waku

# List all available packages
./downloader/bin/lgpd list

# Download a package
./downloader/bin/lgpd download my_module -o ./packages/

# Download from a specific release
./downloader/bin/lgpd --release v2.0.0 download my_module -o ./packages/

# Install the downloaded package locally
./package-manager/bin/lgpm --modules-dir ./modules install --file ./packages/my_module.lgx
```

`lgpd` handles the network side (browsing, searching, downloading), while `lgpm` handles local installation.

---

## Part 6: Running Your Module

Once your module is packaged and installed into a `modules/` directory (see Parts 3 and 4), you can run it with `logoscore`.

### 6.1 Running with `logoscore`

The **`logoscore`** CLI (from `logos-liblogos`) is a headless runtime that can load modules and invoke their methods from the command line.

#### Building logoscore

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

#### Daemon Mode

`logoscore` runs as a daemon that stays alive to host modules. Start it with `-D`:

```bash
# Start the daemon with a modules directory
./logos/bin/logoscore -D -m ./modules
```

Once the daemon is running, use commands from another terminal:

```bash
# Load a module
./logos/bin/logoscore load-module my_module

# Call a method on a loaded module
./logos/bin/logoscore call my_module doSomething hello

# List loaded modules
./logos/bin/logoscore list-modules --loaded

# Show module details
./logos/bin/logoscore module-info my_module

# Watch events from a module
./logos/bin/logoscore watch my_module

# Show daemon and module health
./logos/bin/logoscore status

# Stop the daemon
./logos/bin/logoscore stop
```

#### Inline Mode (Legacy)

For one-shot execution (load, call, exit), use the legacy inline flags:

```bash
# Load a module and call a method
./logos/bin/logoscore \
  -m ./modules \
  --load-modules my_module \
  -c "my_module.doSomething(hello)"

# Multiple sequential calls
./logos/bin/logoscore \
  -m ./modules \
  -l my_module \
  -c "my_module.init(@config.json)" \
  -c "my_module.start()"

# Exit immediately after calls complete
./logos/bin/logoscore \
  -m ./modules -l my_module \
  -c "my_module.doSomething(hello)" \
  --quit-on-finish
```

> **Note:** Without `-c` or `--quit-on-finish`, logoscore enters the Qt event loop and stays running (daemon behavior). Always use `-c` for one-shot execution.

**Inline mode flags:**

| Flag                               | Description                                          |
| ---------------------------------- | ---------------------------------------------------- |
| `-m, --modules-dir <dir>`          | Directory containing module libraries (repeatable)   |
| `-l, --load-modules <name1,name2>` | Comma-separated list of modules to load              |
| `-c "<module>.<method>(args)"`     | Call a method after loading (repeatable, sequential) |
| `--quit-on-finish`                 | Exit after all `-c` calls complete                   |
| `@file.json`                       | Pass a file's contents as a method argument          |

**Daemon commands:**

| Command                         | Description                      |
| ------------------------------- | -------------------------------- |
| `status`                        | Show daemon and module health    |
| `load-module <name>`            | Load a module into the daemon    |
| `unload-module <name>`          | Unload a module                  |
| `reload-module <name>`          | Reload (unload + load) a module  |
| `list-modules [--loaded]`       | List available or loaded modules |
| `module-info <name>`            | Show detailed module information |
| `call <module> <method> [args]` | Call a method on a loaded module |
| `watch <module> [--event]`      | Watch events from a module       |
| `stats`                         | Show module resource usage       |
| `stop`                          | Stop the daemon                  |

---

## Part 7: Running in logos-basecamp

### 7.1 Building logos-basecamp

logos-basecamp produces two binary variants:

- **development** (depends on `/nix/store`)
- **portable** (self-contained, used in distributed builds and `.app` bundles)

```bash
# Build the development version
nix build 'github:logos-co/logos-basecamp#app' --out-link ./logos-basecamp

# Run the dev binary
./logos-basecamp/bin/logos-basecamp

# Build the portable/distributed version
nix build 'github:logos-co/logos-basecamp#portable' --out-link ./logos-basecamp-portable

# Or build platform-specific distributions:
nix build 'github:logos-co/logos-basecamp#bin-bundle-dir'     # Flat directory bundle
nix build 'github:logos-co/logos-basecamp#bin-appimage'       # Linux AppImage
nix build 'github:logos-co/logos-basecamp#bin-macos-app'      # macOS .app bundle
```

> **Note:** When installing modules into logos-basecamp, the LGX variant type must match the build type. Dev builds of basecamp expect **dev** LGX variants (e.g., `darwin-arm64-dev`), while portable builds expect **portable** variants (e.g., `darwin-arm64`). Use the `dual` bundler (see [3.2](#32-bundling-with-nix-bundle-lgx)) to produce packages that work with both.

### 7.2 Module Types in logos-basecamp

The application supports three types of modules:

#### Core Modules (Backend)

These are non-UI modules that provide backend functionality. They run in isolated `logos_host` processes and communicate via Qt Remote Objects.

- Loaded via `logos_core_load_plugin()`
- Placed in the **modules directory** (`--modules-dir`)
- Have `"type": "core"` in metadata

#### ui_qml with C++ Backend (Process-Isolated)

These have `"type": "ui_qml"` with both `"main"` (backend plugin) and `"view"` (QML entry point) in `metadata.json`. The C++ backend runs in a separate `ui-host` process; the QML view loads in the host app.

The remote interface is defined in a **`.rep` file** (Qt Remote Objects definition):

```rep
class CalcUiCpp
{
    PROP(QString status READWRITE)    // auto-synced to QML replica
    SLOT(int add(int a, int b))       // callable from QML, returns via Promise
    SIGNAL(errorOccurred(QString msg)) // one-shot events
}
```

The `.rep` file is the **single source of truth** — `repc` generates:

- `CalcUiCppSimpleSource` — base class the C++ backend inherits
- `CalcUiCppReplica` — typed replica the QML view uses via `logos.module()`
- A separate `_replica_factory` plugin for typed remoting

The C++ plugin inherits from the generated source + `ViewPluginBase`:

```cpp
class CalcUiCppPlugin : public CalcUiCppSimpleSource,
                        public CalcUiCppInterface,
                        public CalcUiCppViewPluginBase { ... };
```

QML accesses the backend via a typed replica:

```qml
readonly property var backend: logos.module("calc_ui_cpp")
// Properties auto-sync:
Text { text: backend.status }
// Return values via Promise:
logos.watch(backend.add(1, 2), function(v) { ... })
```

- Scaffold: `nix flake init -t github:logos-co/logos-module-builder#ui-qml-backend`
- See [Tutorial Part 3](tutorial-cpp-ui-app.md) for a complete walkthrough

#### ui_qml QML-Only (In-Process)

These have `"type": "ui_qml"` with `"view"` but no `"main"` — pure QML, no C++ compilation, no process isolation:

- QML view loads directly in the host app (basecamp / standalone)
- No `.rep` file needed
- Call core modules via the `logos` bridge: `logos.callModule("module", "method", [args])`
- Network access denied, filesystem restricted to module directory
- Scaffold: `nix flake init -t github:logos-co/logos-module-builder#ui-qml`
- See [Tutorial Part 2](tutorial-qml-ui-app.md) for a complete walkthrough

---

## Part 8: Inter-Module Communication

### 8.1 The LogosAPI

Every module receives a `LogosAPI*` pointer when `initLogos()` is called. This is your gateway to communicating with other modules.

```cpp
void MyModulePlugin::initLogos(LogosAPI* logosAPIInstance)
{
    logosAPI = logosAPIInstance;

    // Get a client for calling another module
    LogosAPIClient* client = logosAPI->getClient("other_module");

    // Synchronous call (blocks until result is returned)
    QVariant result = client->invokeRemoteMethod(
        "other_module",  // target module name
        "someMethod",    // method name
        arg1, arg2       // arguments (up to 5 positional args)
    );

    // Async call (preferred -- non-blocking, result delivered via callback)
    client->invokeRemoteMethodAsync(
        "other_module",
        "someMethod",
        [](QVariant result) {
            // Handle result (called on the main thread)
            if (result.isValid()) {
                qDebug() << "Got result:" << result;
            }
        },
        arg1, arg2
    );
}
```

> **Prefer async calls.** Synchronous `invokeRemoteMethod` blocks the caller's thread until the remote module responds. Use `invokeRemoteMethodAsync` to avoid blocking, especially in UI modules.

### 8.2 The C++ SDK Code Generator

The `logos-cpp-generator` tool (from `logos-cpp-sdk`) inspects a compiled module and generates typed C++ wrapper classes, so you get compile-time type safety instead of raw `invokeRemoteMethod` calls.

#### Getting logos-cpp-generator

The generator is bundled with `logos-cpp-sdk`. It is automatically available:

- **In `nix develop`** -- the module dev shell includes the SDK on PATH
- **Build it directly:**
  ```bash
  nix build 'github:logos-co/logos-cpp-sdk#cpp-generator' --out-link ./cpp-gen
  ./cpp-gen/bin/logos-cpp-generator --help
  ```

#### Generating Wrappers

```bash
# Generate wrappers for a single module
logos-cpp-generator /path/to/my_module_plugin.so --output-dir ./generated

# Generate wrappers for all dependencies listed in metadata.json
logos-cpp-generator --metadata metadata.json --module-dir /path/to/modules --output-dir ./generated

# Generate only module files (no umbrella headers)
logos-cpp-generator /path/to/plugin.so --module-only --output-dir ./generated

# Generate only umbrella SDK files (assumes module files exist)
logos-cpp-generator --metadata metadata.json --general-only --output-dir ./generated
```

#### Using Generated Wrappers

After generation, you get typed wrapper classes with both synchronous and asynchronous methods:

```cpp
#include "logos_sdk.h"  // Umbrella header

// In your module's initLogos():
void MyModulePlugin::initLogos(LogosAPI* api) {
    logosAPI = api;

    // Create the typed SDK wrapper
    LogosModules* logos = new LogosModules(api);

    // Synchronous call (blocks until result)
    QString result = logos->other_module.doSomething("hello");

    // Async call (preferred -- non-blocking)
    logos->other_module.doSomethingAsync("hello", [](QVariant result) {
        qDebug() << "Got:" << result;
    });
}
```

The generated `LogosModules` struct provides a member for each module, with methods matching the module's `Q_INVOKABLE` methods. For every method `foo()`, an async variant `fooAsync()` is also generated that takes a callback parameter.

> **Prefer async wrappers.** Use `doSomethingAsync(...)` instead of `doSomething(...)` to avoid blocking the caller's thread. Synchronous calls can cause hangs if the target module is slow to respond.

### 8.3 LogosResult

Many module methods return `LogosResult` for structured success/error handling:

```cpp
LogosResult result = logos->my_module.someMethod();

if (result.success) {
    // Access the value
    QString value = result.getString();
    int number = result.getInt();
    bool flag = result.getBool();
    QVariantMap map = result.getMap();
    QVariantList list = result.getList();

    // Access nested values by key (for map results)
    QString name = result.getString("name");
    int count = result.getInt("count", 0);  // with default

    // Generic typed access
    auto custom = result.getValue<MyType>();
} else {
    // Access the error
    QString error = result.getError();
}
```

To return a `LogosResult` from your module:

```cpp
Q_INVOKABLE LogosResult MyModulePlugin::fetchData(const QString& id) {
    if (id.isEmpty()) {
        return {false, QVariant(), "ID cannot be empty"};
    }

    QVariantMap data;
    data["id"] = id;
    data["name"] = "Example";
    data["count"] = 42;
    return {true, data};
}
```

### 8.4 Communication Modes

The SDK supports two communication modes:

| Mode                 | Use Case                    | Mechanism                                 |
| -------------------- | --------------------------- | ----------------------------------------- |
| **Remote** (default) | Desktop apps                | Qt Remote Objects (IPC between processes) |
| **Local**            | Mobile apps, single-process | In-process `PluginRegistry`               |

Set the mode before creating any `LogosAPI` instances:

```cpp
// For mobile / embedded (all modules in one process)
LogosModeConfig::setMode(LogosMode::Local);

// For desktop (each module in its own process) -- this is the default
LogosModeConfig::setMode(LogosMode::Remote);
```

---

## Part 9: Advanced Topics

### 9.1 Tutorials

For hands-on walkthroughs of module development patterns, see the dedicated tutorials:

- **[Wrapping a C Library](tutorial-wrapping-c-library.md)** — create `calc_module` wrapping a vendored C library. Covers external library configuration in `metadata.json`.
- **[Building a QML UI App](tutorial-qml-ui-app.md)** — create `calc_ui`, a QML-only UI plugin that calls a core module via the `logos.callModule()` bridge.
- **[Building a C++ UI Module](tutorial-cpp-ui-app.md)** — build `calc_ui_cpp`, a C++ + QML view module that combines a QML frontend with a C++ backend. The backend exposes `Q_INVOKABLE` methods using the generated typed SDK; the QML view calls them via `logos.callModuleAsync()`.

### 9.2 Module Dependencies

Declare dependencies in your `metadata.json`:

```json
{
  "name": "my_module",
  "dependencies": ["package_manager", "waku_module"]
}
```

Each entry in `dependencies` must match the `name` field in that module's own `metadata.json`. When adding a dependency as a flake input, the **input attribute name** must also match the dependency name — e.g., `waku_module.url = "github:logos-co/logos-waku-module"`. The URL can point to any repo, but the attribute name is how the builder resolves dependencies.

When your module is installed via `lgpm`, its dependencies are automatically resolved and installed first. When loaded via `logos-basecamp`, core module dependencies are loaded before your module.

---

## Reference: Repository Map

| Repository                                                                       | What It Provides           | Key Outputs                                                                       |
| -------------------------------------------------------------------------------- | -------------------------- | --------------------------------------------------------------------------------- |
| [logos-module-builder](https://github.com/logos-co/logos-module-builder)         | Build system / scaffolding | `mkLogosModule`, `mkLogosQmlModule` Nix functions, `LogosModule.cmake`, templates |
| [logos-module](https://github.com/logos-co/logos-module)                         | Plugin introspection       | `liblogos_module.a` (static lib), `lm` (CLI)                                      |
| [logos-cpp-sdk](https://github.com/logos-co/logos-cpp-sdk)                       | SDK + code generator       | `LogosAPI`, `LogosResult`, `logos-cpp-generator`, `PluginInterface`               |
| [logos-liblogos](https://github.com/logos-co/logos-liblogos)                     | Core library               | `logos_host`, `liblogos_core`                                                     |
| [logos-logoscore-cli](https://github.com/logos-co/logos-logoscore-cli)           | Headless CLI runtime       | `logoscore` (CLI)                                                                 |
| [logos-package](https://github.com/logos-co/logos-package)                       | Package format             | `lgx` (CLI), `liblgx` (library)                                                   |
| [logos-package-manager](https://github.com/logos-co/logos-package-manager)       | Local package management   | `lgpm` (CLI)                                                                      |
| [logos-package-downloader](https://github.com/logos-co/logos-package-downloader) | Online catalog + downloads | `lgpd` (CLI)                                                                      |
| [logos-standalone-app](https://github.com/logos-co/logos-standalone-app)         | Minimal UI module runner   | `logos-standalone-app` (loads a single UI plugin for testing)                     |
| [logos-basecamp](https://github.com/logos-co/logos-basecamp)                     | Desktop app shell          | `LogosApp` (GUI), MDI workspace, plugin loader                                    |

## Reference: CLI Tools Summary

### `lm` -- Module Inspector

```bash
lm <plugin-file>                              # Show metadata + methods
lm metadata <plugin-file> [--json]            # View module metadata
lm methods <plugin-file> [--json]             # List Q_INVOKABLE methods
```

### `logoscore` -- Headless Runtime

```bash
# Daemon mode
logoscore -D -m <modules-dir>                 # Start daemon
logoscore load-module <name>                  # Load a module
logoscore call <module> <method> [args]       # Call a method
logoscore list-modules [--loaded]             # List modules
logoscore module-info <name>                  # Show module details
logoscore status                              # Daemon health
logoscore stop                                # Stop daemon

# Inline mode (legacy)
logoscore -m <dir> -l <name> -c "<module>.<method>(args)" [--quit-on-finish]
```

### `lgpm` -- Local Package Manager

```bash
./package-manager/bin/lgpm --modules-dir <path> install --file <path.lgx>   # Install from local .lgx file
./package-manager/bin/lgpm --modules-dir <path> install --dir <dir>         # Install all .lgx files in a directory
./package-manager/bin/lgpm --modules-dir <path> list                        # List installed packages
./package-manager/bin/lgpm --modules-dir <path> info <pkg>                  # Show installed package details
```

### `lgpd` -- Package Downloader

```bash
./downloader/bin/lgpd search <query>                       # Search packages by name/description
./downloader/bin/lgpd list [--category <cat>]              # List available packages
./downloader/bin/lgpd categories                           # List available categories
./downloader/bin/lgpd releases                             # List recent GitHub releases (up to 30)
./downloader/bin/lgpd info <pkg>                           # Show package details from catalog
./downloader/bin/lgpd download <pkg> [-o <dir>]            # Download .lgx package
./downloader/bin/lgpd --release <tag> download <pkg>       # Download from specific release
```

### `logos-cpp-generator` -- SDK Code Generator

```bash
logos-cpp-generator <plugin-file> [--output-dir <dir>] [--module-only]
logos-cpp-generator --metadata <metadata.json> --module-dir <dir> [--output-dir <dir>]
logos-cpp-generator --metadata <metadata.json> --general-only [--output-dir <dir>]
```

### `nix-bundle-lgx` -- LGX Bundler

```bash
# Preferred: built-in derivation (logos-module-builder includes nix-bundle-lgx)
nix build .#lgx                                                       # Dev variant
nix build .#lgx-portable                                              # Portable variant

# Alternative: nix bundle command
nix bundle --bundler github:logos-co/nix-bundle-lgx .#lib            # Dev variant
nix bundle --bundler github:logos-co/nix-bundle-lgx#portable .#lib   # Portable variant
nix bundle --bundler github:logos-co/nix-bundle-lgx#dual .#lib       # Both variants
```

---

## Troubleshooting

### "experimental features" error with Nix

If you see errors about experimental features, either pass the flag:

```bash
nix --extra-experimental-features "nix-command flakes" build
```

Or add to `~/.config/nix/nix.conf`:

```
experimental-features = nix-command flakes
```

### Module loads but LogosAPI is not available

This happens when running a module outside the full Logos runtime (e.g., in the module viewer). The `LogosAPI` is only available when the module is loaded by `logoscore` or `logos-basecamp`.

### Module not discovered by logos-basecamp

Check that:

1. The module binary is in the correct directory (modules dir for core, plugins dir for UI)
2. The `metadata.json` file is present alongside the binary
3. The `name` field in metadata matches the binary name (e.g., `my_module_plugin.so` for module named `my_module`)

### lgpm install fails

- Check your internet connection (lgpm fetches from GitHub Releases)
- Try specifying a release: `./package-manager/bin/lgpm --release v1.0.0 install my_module`
- For local files: `./package-manager/bin/lgpm install --file ./my_module.lgx`
- Check the target directory is writable: `./package-manager/bin/lgpm --modules-dir ./modules install my_module`

### Checking if a module loaded successfully

Use `logoscore` to verify your module loads and its methods are callable:

```bash
# Start daemon and load the module
./logos/bin/logoscore -D -m ./modules &

# Check if the module is listed as loaded
./logos/bin/logoscore list-modules --loaded

# Inspect the module
./logos/bin/logoscore module-info my_module

# Or use inline mode for a quick check
./logos/bin/logoscore -m ./modules -l my_module -c "my_module.greet(test)" --quit-on-finish
```

### UI module `nix run` fails to load dependencies

When running a UI module with `nix run`, the standalone app automatically bundles all module dependencies declared in `metadata.json`. If dependencies fail to load, check the following requirements:

**Requirements for auto-bundled dependencies:**

1. **Module type must be `"ui"` or use `mkLogosQmlModule`** — only UI modules get `apps.default` wired up with the standalone app.

2. **Dependencies must be listed in `metadata.json`** under the `"dependencies"` array:

   ```json
   {
     "name": "my_ui_module",
     "type": "ui",
     "dependencies": ["calc_module", "storage_module"]
   }
   ```

3. **Each dependency must have a matching flake input** — the flake input name must exactly match the dependency name in `metadata.json`:

   ```nix
   inputs = {
     logos-module-builder.url = "github:logos-co/logos-module-builder";
     calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
     storage_module.url = "github:logos-co/logos-storage-module";
   };
   ```

4. **Module names must be consistent** — the `"name"` field in each dependency's `metadata.json` must match its flake input name. The build system uses this name to locate the plugin binary (`{name}_plugin.so` / `{name}_plugin.dylib`).

**What changed (no more `logos-standalone-app` input):**

- `logos-standalone-app` is now bundled inside `logos-module-builder` — UI module flakes no longer need it as a separate input.
- No `logosStandalone` parameter is needed in `mkLogosQmlModule`, `mkLogosModule`, or `mkLogosQmlModule` calls.
- Dependencies (including transitive ones) are automatically resolved from the flake input tree, bundled as LGX packages at build time, and extracted into the modules directory at runtime.
- The standalone app uses `logos_core_load_plugin_with_dependencies()` which resolves the full transitive dependency graph via metadata.json files.

**Example C++ UI module `flake.nix` (view module — C++ backend + QML view):**

```nix
{
  description = "My UI module";
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };
  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

**Example QML UI module `flake.nix`:**

```nix
{
  description = "My QML UI module";
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_module.url = "github:logos-co/logos-tutorial?dir=logos-calc-module";
  };
  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosQmlModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

If the module doesn't appear, check:

1. The `modules/` directory contains a subdirectory for your module with `manifest.json` and the plugin binary
2. The variant in the manifest matches your platform (e.g., `darwin-arm64-dev` for dev builds on Apple Silicon)
3. Use `lm` to verify the plugin binary is a valid Qt plugin: `./lm/bin/lm ./modules/my_module/my_module_plugin.dylib`

### Capability module not found

logos-basecamp requires the `capability` module to be installed. It is bundled with basecamp and installed on first launch. If you see errors about it:

1. Check that the `modules/` and `plugins/` directories exist next to `bin/` and `lib/` in the basecamp build output
2. Check that the capability module was extracted to the modules directory
3. Verify the LGX variant type matches your basecamp build (dev variant for dev build, portable for portable build)

### LGX variant mismatch

If a module installs but fails to load, the variant type may not match:

- **Dev build** of logos-basecamp needs **dev** LGX variants (`darwin-arm64-dev`)
- **Portable build** needs **portable** variants (`darwin-arm64`)
- Use `nix build .#lgx` and `nix build .#lgx-portable` to produce each variant separately, or `nix bundle --bundler github:logos-co/nix-bundle-lgx#dual .#lib` for a single package with both variants

### Cross-platform builds

Build on each target platform separately to create `.lgx` packages:

```bash
# On each platform, the built-in derivation produces the correct variant automatically:
nix build .#lgx-portable

# Or using nix bundle for dual variant:
nix bundle --bundler github:logos-co/nix-bundle-lgx#dual .#lib

# Then merge platform-specific .lgx files into one:
./lgx/bin/lgx merge my_module-linux.lgx my_module-macos.lgx -o my_module.lgx
```
