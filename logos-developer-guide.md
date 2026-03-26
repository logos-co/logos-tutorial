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
- [Part 3: Packaging Your Module](#part-3-packaging-your-module)
  - [3.1 The LGX Package Format](#31-the-lgx-package-format)
  - [3.2 Building LGX Packages](#32-building-lgx-packages)
    - [Built-in Nix Derivation (Preferred)](#built-in-nix-derivation-preferred)
    - [Using nix bundle (Alternative)](#using-nix-bundle-alternative)
- [Part 4: Installing and Managing Modules](#part-4-installing-and-managing-modules)
  - [4.1 The lgpm CLI](#41-the-lgpm-cli)
  - [4.2 Installing from Local Files](#42-installing-from-local-files)
  - [4.3 Installing from a Registry](#43-installing-from-a-registry)
- [Part 5: Running Your Module](#part-5-running-your-module)
  - [5.1 Running with logoscore](#51-running-with-logoscore)
- [Part 6: Running in logos-basecamp](#part-6-running-in-logos-basecamp)
  - [6.1 Building logos-basecamp](#61-building-logos-basecamp)
  - [6.2 Module Types in logos-basecamp](#62-module-types-in-logos-basecamp)
- [Part 7: Inter-Module Communication](#part-7-inter-module-communication)
  - [7.1 The LogosAPI](#71-the-logosapi)
  - [7.2 The C++ SDK Code Generator](#72-the-c-sdk-code-generator)
  - [7.3 LogosResult](#73-logosresult)
  - [7.4 Communication Modes](#74-communication-modes)
- [Part 8: Advanced Topics](#part-8-advanced-topics)
  - [8.1 Tutorials](#81-tutorials)
  - [8.2 Module Dependencies](#82-module-dependencies)
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

| Component | Repository | Role |
|-----------|-----------|------|
| **logos-module-builder** | [logos-co/logos-module-builder](https://github.com/logos-co/logos-module-builder) | Scaffolding and build system for new modules |
| **logos-module** | [logos-co/logos-module](https://github.com/logos-co/logos-module) | Plugin loading/introspection library + `lm` CLI |
| **logos-cpp-sdk** | [logos-co/logos-cpp-sdk](https://github.com/logos-co/logos-cpp-sdk) | C++ SDK, types, IPC layer, code generator |
| **logos-liblogos** | [logos-co/logos-liblogos](https://github.com/logos-co/logos-liblogos) | Core library (`logos_host`, `liblogos_core`) |
| **logos-logoscore-cli** | [logos-co/logos-logoscore-cli](https://github.com/logos-co/logos-logoscore-cli) | Headless CLI runtime (`logoscore`) |
| **logos-package** | [logos-co/logos-package](https://github.com/logos-co/logos-package) | LGX package format library + `lgx` CLI |
| **logos-package-manager-module** | [logos-co/logos-package-manager-module](https://github.com/logos-co/logos-package-manager-module) | Package manager module + `lgpm` CLI |
| **logos-standalone-app** | [logos-co/logos-standalone-app](https://github.com/logos-co/logos-standalone-app) | Minimal shell for running/testing UI modules in isolation |
| **logos-basecamp** | [logos-co/logos-basecamp](https://github.com/logos-co/logos-basecamp) | Desktop application shell |

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

# For UI modules (C++ Qt widget with logos-standalone-app runner)
nix flake init -t github:logos-co/logos-module-builder#ui-module

# For QML UI modules (with logos-standalone-app runner)
nix flake init -t github:logos-co/logos-module-builder#ui-qml-module
```

**Available templates:**

| Template | Use Case |
|----------|----------|
| `default` | Minimal core module (C++ backend, no UI) |
| `with-external-lib` | Core module wrapping an external C/C++ library |
| `ui-module` | C++ Qt widget UI module with `logos-standalone-app` runner |
| `ui-qml-module` | QML-based UI module with `logos-standalone-app` runner |

The `ui-module` and `ui-qml-module` templates include `logos-standalone-app` as an input, enabling `nix run` to launch and test your UI plugin in isolation without the full logos-basecamp shell.

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

The `CMakeLists.txt` is minimal -- it includes `LogosModule.cmake` (provided by the builder) and calls the `logos_module()` macro, which sets up the Qt plugin target, links the SDK, configures include paths, and handles code generation. You just list your source files:

```cmake
cmake_minimum_required(VERSION 3.14)
project(MyModulePlugin LANGUAGES CXX)

if(DEFINED ENV{LOGOS_MODULE_BUILDER_ROOT})
    include($ENV{LOGOS_MODULE_BUILDER_ROOT}/cmake/LogosModule.cmake)
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/cmake/LogosModule.cmake")
    include(cmake/LogosModule.cmake)
else()
    message(FATAL_ERROR "LogosModule.cmake not found")
endif()

logos_module(
    NAME my_module
    SOURCES
        src/my_module_interface.h
        src/my_module_plugin.h
        src/my_module_plugin.cpp
)
```

### 1.3 The metadata.json Configuration

The `metadata.json` file is the single source of truth for your module. It is embedded into the plugin binary by Qt's `Q_PLUGIN_METADATA` macro (for runtime metadata), read by `logos-module-builder` to configure the Nix build, used by CMake to resolve external dependencies and link libraries (via the `nix` section), and used by `nix-bundle-lgx` to generate the LGX manifest.

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "type": "core",
  "category": "general",
  "description": "My first Logos module",
  "main": "my_module_plugin",
  "dependencies": [],

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

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | -- | Module name (used for filenames and identifiers) |
| `version` | No | `1.0.0` | Semantic version |
| `type` | No | `core` | Module type (`core`, `ui`, `ui_qml`) |
| `category` | No | `general` | Category (general, network, chat, wallet, integration) |
| `description` | No | `"A Logos module"` | Human-readable description |
| `main` | Yes | -- | Plugin entry point (plugin name for core/ui, `Main.qml` for QML) |
| `dependencies` | No | `[]` | Other Logos module names this depends on. Each entry must match the `name` field in that dependency's `metadata.json`. |
| `nix.packages.build` | No | `[]` | Nix packages for build time |
| `nix.packages.runtime` | No | `[]` | Nix packages for runtime |
| `nix.external_libraries` | No | `[]` | External C/C++ libraries to link |
| `nix.cmake.find_packages` | No | `[]` | CMake `find_package()` calls |
| `nix.cmake.extra_sources` | No | `[]` | Additional source files to compile |
| `nix.cmake.extra_include_dirs` | No | `[]` | Additional include directories |
| `nix.cmake.extra_link_libraries` | No | `[]` | Additional libraries to link |

### 1.4 Writing Module Code

A Logos module is a **Qt plugin**. It must:

1. Inherit from `QObject` and implement the `PluginInterface`
2. Declare an interface with `Q_INTERFACES`
3. Embed metadata with `Q_PLUGIN_METADATA`
4. Mark callable methods with `Q_INVOKABLE`

#### The Interface Header (`src/my_module_interface.h`)

```cpp
#pragma once

#include <QtPlugin>
#include <QString>
#include <interface.h>  // From logos-cpp-sdk: provides PluginInterface

class MyModuleInterface : public PluginInterface
{
public:
    virtual ~MyModuleInterface() {}

    // Declare your module's public methods here
    virtual QString doSomething(const QString& input) = 0;
    virtual int compute(int a, int b) = 0;
};

#define MyModuleInterface_iid "com.logos.MyModuleInterface"
Q_DECLARE_INTERFACE(MyModuleInterface, MyModuleInterface_iid)
```

#### The Plugin Header (`src/my_module_plugin.h`)

```cpp
#pragma once

#include <QObject>
#include "my_module_interface.h"

class MyModulePlugin : public QObject, public MyModuleInterface
{
    Q_OBJECT
    Q_INTERFACES(MyModuleInterface PluginInterface)
    Q_PLUGIN_METADATA(IID MyModuleInterface_iid FILE "metadata.json")

public:
    explicit MyModulePlugin(QObject* parent = nullptr);
    ~MyModulePlugin();

    // PluginInterface
    QString name() const override { return "my_module"; }
    QString version() const override { return "1.0.0"; }

    // Your methods -- mark with Q_INVOKABLE for remote access
    Q_INVOKABLE void initLogos(LogosAPI* logosAPIInstance);
    Q_INVOKABLE QString doSomething(const QString& input) override;
    Q_INVOKABLE int compute(int a, int b) override;

signals:
    // For event forwarding to other modules
    void eventResponse(const QString& eventName, const QVariantList& data);
};
```

#### The Plugin Implementation (`src/my_module_plugin.cpp`)

```cpp
#include "my_module_plugin.h"
#include <QDebug>

MyModulePlugin::MyModulePlugin(QObject* parent) : QObject(parent)
{
    qDebug() << "MyModulePlugin: created";
}

MyModulePlugin::~MyModulePlugin()
{
    qDebug() << "MyModulePlugin: destroyed";
}

void MyModulePlugin::initLogos(LogosAPI* logosAPIInstance)
{
    // Store the API pointer for inter-module communication
    logosAPI = logosAPIInstance;
    qDebug() << "MyModulePlugin: LogosAPI initialized";
}

QString MyModulePlugin::doSomething(const QString& input)
{
    return "Processed: " + input;
}

int MyModulePlugin::compute(int a, int b)
{
    return a + b;
}
```

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

# Enter the development shell (provides cmake, ninja, Qt, etc.)
nix develop

# Inside the dev shell, you can also build directly with CMake:
cmake -B build -GNinja
cmake --build build
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
    "parameters": [
      { "name": "logosAPIInstance", "type": "LogosAPI*" }
    ]
  },
  {
    "name": "doSomething",
    "signature": "doSomething(QString)",
    "returnType": "QString",
    "isInvokable": true,
    "parameters": [
      { "name": "input", "type": "QString" }
    ]
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

## Part 3: Packaging Your Module

Before you can run your module with `logoscore` or install it into `logos-basecamp`, you need to package the build output into an `.lgx` package and install it into a `modules/` directory.

### 3.1 The LGX Package Format

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

### 3.2 Building LGX Packages

There are two ways to create `.lgx` packages. The preferred approach uses the built-in Nix derivation that comes with `logos-module-builder`. Alternatively, you can use the `nix bundle` command directly.

#### Built-in Nix Derivation (Preferred)

When your module's `flake.nix` includes `nix-bundle-lgx` as an input (which all `logos-module-builder` templates do by default), LGX package outputs are automatically available as part of your flake:

```bash
# Dev variant (uses /nix/store references, for local development)
nix build .#lgx

# Portable variant (self-contained, all dependencies bundled)
nix build .#lgx-portable

# Dual variant (both dev and portable in one .lgx file)
nix build .#lgx-dual
```

This produces a `my_module-<version>.lgx` file in the `result/` directory.

This works because `logos-module-builder.lib.mkLogosModule` detects the `nix-bundle-lgx` input in your `flakeInputs` and automatically creates the `lgx`, `lgx-portable`, and `lgx-dual` package outputs. No extra configuration is needed — it is part of the standard module template:

```nix
{
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

#### Using `nix bundle` (Alternative)

You can also create `.lgx` packages using the `nix bundle` command directly. This is useful if your module does not use `logos-module-builder` or if you need the `dual` bundling mode (both dev and portable in a single `.lgx` file):

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

| Mode | Built-in Command | `nix bundle` Command | Variant Created | Use Case |
|------|-----------------|---------------------|----------------|----------|
| **Dev** | `nix build .#lgx` | `nix bundle --bundler ...#default .#lib` | `darwin-arm64-dev` | Local development (requires Nix store) |
| **Portable** | `nix build .#lgx-portable` | `nix bundle --bundler ...#portable .#lib` | `darwin-arm64` | Distribution (self-contained, no Nix needed) |
| **Dual** | `nix build .#lgx-dual` | `nix bundle --bundler ...#dual .#lib` | Both dev and portable | One package for both environments |

**Variant naming:**

| Nix System | Dev Variant | Portable Variant |
|-----------|------------|-----------------|
| `aarch64-darwin` | `darwin-arm64-dev` | `darwin-arm64` |
| `x86_64-darwin` | `darwin-amd64-dev` | `darwin-amd64` |
| `aarch64-linux` | `linux-arm64-dev` | `linux-arm64` |
| `x86_64-linux` | `linux-amd64-dev` | `linux-amd64` |

> **Important:** The variant type matters when installing into `logos-basecamp`. A dev build of basecamp expects dev variants, and a portable build expects portable variants. Use the `dual` bundler to produce packages that work with both.

---

## Part 4: Installing and Managing Modules

### 4.1 The `lgpm` CLI

The **`lgpm`** CLI (Logos Package Manager) installs, searches, and manages module packages. Installing a package extracts it into a `modules/` directory that `logoscore` and `logos-basecamp` can load from.

#### Building lgpm

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./package-manager
```

#### Commands

```bash
# Search for packages
./package-manager/bin/lgpm search waku

# List all available packages
./package-manager/bin/lgpm list

# List only installed packages
./package-manager/bin/lgpm list --installed

# List packages in a category
./package-manager/bin/lgpm list --category networking

# Show package details
./package-manager/bin/lgpm info my_module

# List available categories
./package-manager/bin/lgpm categories

# Install a package (with dependency resolution)
./package-manager/bin/lgpm --modules-dir ./modules install my_module

# Install multiple packages
./package-manager/bin/lgpm --modules-dir ./modules install my_module another_module

# Install from a local .lgx file
./package-manager/bin/lgpm --modules-dir ./modules install --file ./my_module.lgx
```

#### Global Options

| Option | Description |
|--------|-------------|
| `--modules-dir <path>` | Target directory for installed core modules |
| `--ui-plugins-dir <path>` | Target directory for UI plugins |
| `--release <tag>` | GitHub release tag to use (default: `latest`) |
| `--json` | Output in JSON format |
| `-h, --help` | Show help |

### 4.2 Installing from Local Files

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

### 4.3 Installing from a Registry

```bash
# Install a published package (lgpm fetches from GitHub Releases)
./package-manager/bin/lgpm --modules-dir ./modules install my_module

# Install from a specific release
./package-manager/bin/lgpm --modules-dir ./modules --release v2.0.0 install my_module
```

The package manager automatically:
1. Resolves transitive dependencies
2. Downloads the correct platform variant for your OS/architecture
3. Extracts the LGX package
4. Copies the library to the target directory

---

## Part 5: Running Your Module

Once your module is packaged and installed into a `modules/` directory (see Parts 3 and 4), you can run it with `logoscore`.

### 5.1 Running with `logoscore`

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

| Flag | Description |
|------|-------------|
| `-m, --modules-dir <dir>` | Directory containing module libraries (repeatable) |
| `-l, --load-modules <name1,name2>` | Comma-separated list of modules to load |
| `-c "<module>.<method>(args)"` | Call a method after loading (repeatable, sequential) |
| `--quit-on-finish` | Exit after all `-c` calls complete |
| `@file.json` | Pass a file's contents as a method argument |

**Daemon commands:**

| Command | Description |
|---------|-------------|
| `status` | Show daemon and module health |
| `load-module <name>` | Load a module into the daemon |
| `unload-module <name>` | Unload a module |
| `reload-module <name>` | Reload (unload + load) a module |
| `list-modules [--loaded]` | List available or loaded modules |
| `module-info <name>` | Show detailed module information |
| `call <module> <method> [args]` | Call a method on a loaded module |
| `watch <module> [--event]` | Watch events from a module |
| `stats` | Show module resource usage |
| `stop` | Stop the daemon |

---

## Part 6: Running in logos-basecamp

### 6.1 Building logos-basecamp

logos-basecamp produces two binary variants:

- **`logos-basecamp`** -- development build (shell wrapper that sets Qt environment variables, depends on `/nix/store`)
- **`LogosBasecamp`** -- portable binary (self-contained, used in distributed builds and `.app` bundles)

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

### 6.2 Module Types in logos-basecamp

The application supports three types of modules:

#### Core Modules (Backend)

These are non-UI modules that provide backend functionality. They run in isolated `logos_host` processes and communicate via Qt Remote Objects.

- Loaded via `logos_core_load_plugin()`
- Placed in the **modules directory** (`--modules-dir`)
- Have `"type": "core"` in metadata

#### C++ UI Modules (Native Widgets)

These provide native Qt widget UIs. They implement the `IComponent` interface:

```cpp
class IComponent {
public:
    virtual ~IComponent() = default;
    virtual QWidget* createWidget(LogosAPI* logosAPI = nullptr) = 0;
    virtual void destroyWidget(QWidget* widget) = 0;
};
```

- Loaded via `QPluginLoader`
- Placed in the **plugins directory** (`--ui-plugins-dir`)
- Their widget appears as a tab in the MDI workspace

#### QML UI Modules (Sandboxed)

These provide QML-based UIs in a sandboxed environment:

- Have `"type": "ui_qml"` in their manifest
- Entry point is `Main.qml`
- Network access is denied
- Filesystem access is restricted to the module's own directory
- Can call core modules via the `logos` bridge: `logos.callModule("module", "method", [args])`

---

## Part 7: Inter-Module Communication

### 7.1 The LogosAPI

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

### 7.2 The C++ SDK Code Generator

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

### 7.3 LogosResult

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

### 7.4 Communication Modes

The SDK supports two communication modes:

| Mode | Use Case | Mechanism |
|------|----------|-----------|
| **Remote** (default) | Desktop apps | Qt Remote Objects (IPC between processes) |
| **Local** | Mobile apps, single-process | In-process `PluginRegistry` |

Set the mode before creating any `LogosAPI` instances:

```cpp
// For mobile / embedded (all modules in one process)
LogosModeConfig::setMode(LogosMode::Local);

// For desktop (each module in its own process) -- this is the default
LogosModeConfig::setMode(LogosMode::Remote);
```

---

## Part 8: Advanced Topics

### 8.1 Tutorials

For hands-on walkthroughs of module development patterns, see the dedicated tutorials:

- **[Wrapping a C Library](tutorial-wrapping-c-library.md)** — create `calc_module` wrapping a vendored C library. Covers external library configuration in `metadata.json`.
- **[Building a QML UI App](tutorial-qml-ui-app.md)** — create `calc_ui`, a QML-only UI plugin that calls a core module via the `logos.callModule()` bridge.
- **[Building a C++ UI Module](tutorial-cpp-ui-app.md)** — create `calc_ui_cpp`, a native C++ Qt widget plugin using `LogosAPI*` and the generated SDK.

### 8.2 Module Dependencies

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

| Repository | What It Provides | Key Outputs |
|------------|-----------------|-------------|
| [logos-module-builder](https://github.com/logos-co/logos-module-builder) | Build system / scaffolding | `mkLogosModule` Nix function, `LogosModule.cmake`, templates |
| [logos-module](https://github.com/logos-co/logos-module) | Plugin introspection | `liblogos_module.a` (static lib), `lm` (CLI) |
| [logos-cpp-sdk](https://github.com/logos-co/logos-cpp-sdk) | SDK + code generator | `LogosAPI`, `LogosResult`, `logos-cpp-generator`, `PluginInterface` |
| [logos-liblogos](https://github.com/logos-co/logos-liblogos) | Core library | `logos_host`, `liblogos_core` |
| [logos-logoscore-cli](https://github.com/logos-co/logos-logoscore-cli) | Headless CLI runtime | `logoscore` (CLI) |
| [logos-package](https://github.com/logos-co/logos-package) | Package format | `lgx` (CLI), `liblgx` (library) |
| [logos-package-manager-module](https://github.com/logos-co/logos-package-manager-module) | Package management | `lgpm` (CLI), `package_manager_plugin` |
| [logos-standalone-app](https://github.com/logos-co/logos-standalone-app) | Minimal UI module runner | `logos-standalone-app` (loads a single UI plugin for testing) |
| [logos-basecamp](https://github.com/logos-co/logos-basecamp) | Desktop app shell | `LogosApp` (GUI), MDI workspace, plugin loader |

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

### `lgpm` -- Package Manager

```bash
./package-manager/bin/lgpm search <query>                          # Search packages
./package-manager/bin/lgpm list [--category <cat>] [--installed]   # List packages
./package-manager/bin/lgpm install <pkg> [pkgs...]                 # Install with dependency resolution
./package-manager/bin/lgpm install --file <path.lgx>               # Install local file
./package-manager/bin/lgpm info <pkg>                              # Package details
./package-manager/bin/lgpm categories                              # List categories
```

### `logos-cpp-generator` -- SDK Code Generator

```bash
logos-cpp-generator <plugin-file> [--output-dir <dir>] [--module-only]
logos-cpp-generator --metadata <metadata.json> --module-dir <dir> [--output-dir <dir>]
logos-cpp-generator --metadata <metadata.json> --general-only [--output-dir <dir>]
```

### `nix-bundle-lgx` -- LGX Bundler

```bash
# Preferred: built-in derivation (when using logos-module-builder with nix-bundle-lgx input)
nix build .#lgx                                                       # Dev variant
nix build .#lgx-portable                                              # Portable variant
nix build .#lgx-dual                                                  # Both variants

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

### Build fails finding Qt

Ensure you're building inside the Nix environment:

```bash
nix develop   # Enter dev shell with all dependencies
cmake -B build -GNinja && cmake --build build
```

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

If the module doesn't appear, check:
1. The `modules/` directory contains a subdirectory for your module with `manifest.json` and the plugin binary
2. The variant in the manifest matches your platform (e.g., `darwin-arm64-dev` for dev builds on Apple Silicon)
3. Use `lm` to verify the plugin binary is a valid Qt plugin: `./lm/bin/lm ./modules/my_module/my_module_plugin.dylib`

### Capability module not found

logos-basecamp requires the `capability` module to be installed. It is bundled as a preinstall `.lgx` package and installed on first launch. If you see errors about it:

1. Check that the preinstall directory exists: `ls ./logos-basecamp/preinstall/`
2. Check that the capability module was extracted to the modules directory
3. Verify the LGX variant type matches your basecamp build (dev variant for dev build, portable for portable build)

### LGX variant mismatch

If a module installs but fails to load, the variant type may not match:

- **Dev build** of logos-basecamp needs **dev** LGX variants (`darwin-arm64-dev`)
- **Portable build** needs **portable** variants (`darwin-arm64`)
- Use `nix build .#lgx` and `nix build .#lgx-portable` to produce each variant separately, `nix build .#lgx-dual` for a single package with both, or `nix bundle --bundler github:logos-co/nix-bundle-lgx#dual .#lib` via the standalone bundler

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
