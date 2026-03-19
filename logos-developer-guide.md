# Logos Module Developer Guide

A comprehensive guide to creating, building, testing, packaging, and distributing modules for the Logos platform.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Part 1: Creating a Module](#part-1-creating-a-module)
  - [1.1 Scaffold with logos-module-builder](#11-scaffold-with-logos-module-builder)
  - [1.2 Project Structure](#12-project-structure)
  - [1.3 The module.yaml Configuration](#13-the-moduleyaml-configuration)
  - [1.4 Writing Module Code](#14-writing-module-code)
  - [1.5 Building Your Module](#15-building-your-module)
- [Part 2: Inspecting and Testing Your Module](#part-2-inspecting-and-testing-your-module)
  - [2.1 The lm CLI Tool](#21-the-lm-cli-tool)
  - [2.2 Running with logoscore](#22-running-with-logoscore)
  - [2.3 The logos-module-viewer](#23-the-logos-module-viewer)
- [Part 3: Packaging Your Module](#part-3-packaging-your-module)
  - [3.1 The LGX Package Format](#31-the-lgx-package-format)
  - [3.2 Creating a Package with lgx](#32-creating-a-package-with-lgx)
  - [3.3 Verifying Packages](#33-verifying-packages)
- [Part 4: Installing and Managing Modules](#part-4-installing-and-managing-modules)
  - [4.1 The lgpm CLI](#41-the-lgpm-cli)
  - [4.2 Installing from Local Files](#42-installing-from-local-files)
  - [4.3 Installing from a Registry](#43-installing-from-a-registry)
- [Part 5: Running in logos-basecamp](#part-5-running-in-logos-basecamp)
  - [5.1 Building logos-basecamp](#51-building-logos-basecamp)
  - [5.2 Module Types in logos-basecamp](#52-module-types-in-logos-basecamp)
  - [5.3 Development Mode](#53-development-mode)
- [Part 6: Inter-Module Communication](#part-6-inter-module-communication)
  - [6.1 The LogosAPI](#61-the-logosapi)
  - [6.2 The C++ SDK Code Generator](#62-the-c-sdk-code-generator)
  - [6.3 LogosResult](#63-logosresult)
  - [6.4 Communication Modes](#64-communication-modes)
- [Part 7: Advanced Topics](#part-7-advanced-topics)
  - [7.1 Wrapping External Libraries](#71-wrapping-external-libraries)
  - [7.2 UI Modules (C++ Widgets)](#72-ui-modules-c-widgets)
  - [7.3 UI Modules (QML)](#73-ui-modules-qml)
  - [7.4 Module Dependencies](#74-module-dependencies)
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
| **logos-liblogos** | [logos-co/logos-liblogos](https://github.com/logos-co/logos-liblogos) | Core runtime (`logoscore`, `logos_host`, `liblogos_core`) |
| **logos-package** | [logos-co/logos-package](https://github.com/logos-co/logos-package) | LGX package format library + `lgx` CLI |
| **logos-package-manager-module** | [logos-co/logos-package-manager-module](https://github.com/logos-co/logos-package-manager-module) | Package manager module + `lgpm` CLI |
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

# Scaffold a minimal module (no external dependencies)
nix flake init -t github:logos-co/logos-module-builder

# Or scaffold a module that wraps an external C/C++ library
nix flake init -t github:logos-co/logos-module-builder#with-external-lib
```

This generates a ready-to-build project with all the boilerplate handled for you.

### 1.2 Project Structure

After scaffolding, your module directory looks like this:

```
logos-my-module/
├── flake.nix              # Nix flake (build config, ~15 lines)
├── module.yaml            # Declarative module configuration (~30 lines)
├── CMakeLists.txt         # CMake build file (~25 lines)
├── metadata.json          # Auto-generated at build time from module.yaml
└── src/
    ├── my_module_interface.h    # Qt interface definition
    ├── my_module_plugin.h       # Plugin header
    └── my_module_plugin.cpp     # Plugin implementation
```

The key insight: **logos-module-builder** reduces ~600 lines of configuration across 5+ files down to ~70 lines across 2-3 files.

### 1.3 The module.yaml Configuration

The `module.yaml` file is the central configuration for your module:

```yaml
name: my_module
version: 1.0.0
type: core
category: general
description: "My first Logos module"
dependencies: []

# Nix packages needed at build/runtime (optional)
nix_packages:
  build: []
  runtime: []

# CMake configuration (optional)
cmake:
  find_packages: []
  extra_sources: []
  extra_include_dirs: []
  extra_link_libraries: []
```

**Field reference:**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | Yes | -- | Module name (used for filenames and identifiers) |
| `version` | No | `1.0.0` | Semantic version |
| `type` | No | `core` | Module type |
| `category` | No | `general` | Category (general, network, chat, wallet, integration) |
| `description` | No | `"A Logos module"` | Human-readable description |
| `dependencies` | No | `[]` | Other Logos module names this depends on |
| `nix_packages.build` | No | `[]` | Nix packages for build time |
| `nix_packages.runtime` | No | `[]` | Nix packages for runtime |
| `cmake.find_packages` | No | `[]` | CMake `find_package()` calls |
| `cmake.extra_sources` | No | `[]` | Additional source files to compile |
| `cmake.extra_include_dirs` | No | `[]` | Additional include directories |
| `cmake.extra_link_libraries` | No | `[]` | Additional libraries to link |

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
- `name()` must match the `name` field in your `module.yaml` / `metadata.json`

### 1.5 Building Your Module

```bash
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
│   └── my_module_plugin.so   # (or .dylib on macOS)
├── include/
│   └── ...                    # Generated SDK headers
└── share/
    └── metadata.json          # Runtime metadata
```

---

## Part 2: Inspecting and Testing Your Module

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

### 2.2 Running with `logoscore`

The **`logoscore`** CLI (from `logos-liblogos`) is a headless runtime that can load modules and invoke their methods from the command line.

#### Building logoscore

```bash
nix build 'github:logos-co/logos-liblogos' --out-link ./logos
```

#### Running a Module

```bash
# Load a module from a directory
./logos/bin/logoscore \
  -m ./modules \
  --load-modules my_module

# Load a module and call a method
./logos/bin/logoscore \
  -m ./modules \
  --load-modules my_module \
  -c "my_module.doSomething(hello)"

# Load a module and call a method with a JSON config file
./logos/bin/logoscore \
  -m ./modules \
  --load-modules my_module \
  -c "my_module.configure(@config.json)"
```

**Flags:**

| Flag | Description |
|------|-------------|
| `-m <dir>` | Directory containing module libraries |
| `--load-modules <name1,name2>` | Comma-separated list of modules to load |
| `-c "<module>.<method>(args)"` | Command to execute after loading |
| `@file.json` | Pass a JSON file as a method argument |

### 2.3 The logos-module-viewer

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

### 3.1 The LGX Package Format

Logos modules are distributed as **`.lgx` packages**. An LGX file is a gzip-compressed tar archive with a specific internal structure:

```
manifest.json           # Package metadata (required)
manifest.cose           # Optional cryptographic signature
variants/               # Platform-specific builds (required)
  linux-x86_64/
    my_module_plugin.so
  darwin-arm64/
    my_module_plugin.dylib
docs/                   # Optional documentation
licenses/               # Optional license files
```

The **manifest.json** declares the package name, version, and maps each variant to its main entry point (the shared library file):

```json
{
  "name": "my_module",
  "version": "1.0.0",
  "description": "My first Logos module",
  "author": "Developer Name",
  "type": "core",
  "category": "general",
  "manifestVersion": "0.1",
  "main": {
    "linux-x86_64": "my_module_plugin.so",
    "darwin-arm64": "my_module_plugin.dylib"
  },
  "dependencies": []
}
```

### 3.2 Creating a Package with `lgx`

The **`lgx`** CLI tool (from `logos-package`) creates and manages LGX packages.

#### Building lgx

```bash
nix build 'github:logos-co/logos-package#lgx' --out-link ./lgx
```

#### Creating a New Package

```bash
# Create an empty package skeleton
./lgx/bin/lgx create my_module.lgx --name my_module
```

#### Adding Platform Variants

```bash
# Add a single-file variant (the library binary)
./lgx/bin/lgx add-variant my_module.lgx \
  --variant linux-x86_64 \
  --files ./result/lib/my_module_plugin.so

# Add a macOS variant
./lgx/bin/lgx add-variant my_module.lgx \
  --variant darwin-arm64 \
  --files ./result-macos/lib/my_module_plugin.dylib

# Add a directory variant (if your module has multiple files)
./lgx/bin/lgx add-variant my_module.lgx \
  --variant linux-x86_64 \
  --files ./result/lib/ \
  --main my_module_plugin.so
```

**Variant naming convention:** `<os>-<arch>` (lowercase). Common variants:

| Variant | Platform |
|---------|----------|
| `linux-x86_64` | Linux Intel/AMD 64-bit |
| `linux-arm64` | Linux ARM 64-bit |
| `darwin-arm64` | macOS Apple Silicon |
| `darwin-x86_64` | macOS Intel |

#### Removing a Variant

```bash
./lgx/bin/lgx remove-variant my_module.lgx --variant linux-x86_64
```

#### Listing Package Contents

```bash
./lgx/bin/lgx list my_module.lgx
```

#### Extracting a Package

```bash
# Extract a specific variant
./lgx/bin/lgx extract my_module.lgx --variant linux-x86_64 --output ./extracted/

# Extract all variants
./lgx/bin/lgx extract my_module.lgx --all --output ./extracted/
```

### 3.3 Verifying Packages

```bash
./lgx/bin/lgx verify my_module.lgx
```

This checks:
- Package structure is valid (manifest.json exists, variants/ directory exists)
- Manifest fields are present and valid
- Every variant listed in `main` has a corresponding directory and file
- Every variant directory has a corresponding `main` entry
- No forbidden files (symlinks, special files) are present
- All paths are valid (no `..` traversal, no absolute paths)

---

## Part 4: Installing and Managing Modules

### 4.1 The `lgpm` CLI

The **`lgpm`** CLI (Logos Package Manager) installs, searches, and manages module packages.

#### Building lgpm

```bash
nix build 'github:logos-co/logos-package-manager-module#cli' --out-link ./package-manager
```

#### Commands

```bash
# Search for packages
lgpm search waku

# List all available packages
lgpm list

# List only installed packages
lgpm list --installed

# List packages in a category
lgpm list --category networking

# Show package details
lgpm info my_module

# List available categories
lgpm categories

# Install a package (with dependency resolution)
lgpm install my_module

# Install multiple packages
lgpm install my_module another_module

# Install from a local .lgx file
lgpm install --file ./my_module.lgx
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
# Install a locally built .lgx package
./package-manager/bin/lgpm --modules-dir ./modules install --file ./my_module.lgx
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

## Part 5: Running in logos-basecamp

### 5.1 Building logos-basecamp

```bash
# Build the full application
nix build 'github:logos-co/logos-basecamp#app' --out-link ./logos-basecamp

# Run it
./logos-basecamp/bin/logos-basecamp

# Or build platform-specific distributions:
nix build 'github:logos-co/logos-basecamp#bin-appimage'     # Linux AppImage
nix build 'github:logos-co/logos-basecamp#bin-macos-app'     # macOS .app bundle
nix build 'github:logos-co/logos-basecamp#bin-macos-dmg'     # macOS DMG
```

### 5.2 Module Types in logos-basecamp

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

### 5.3 Development Mode

For rapid iteration on QML UI modules, use the development mode launcher:

```bash
# Build once
nix build 'github:logos-co/logos-basecamp'

# Run with live QML reloading (edits to .qml files take effect immediately)
./run-dev.sh
```

This sets `QML_UI` to point to the source directory and disables QML caching, so you can edit QML files and see changes without rebuilding.

---

## Part 6: Inter-Module Communication

### 6.1 The LogosAPI

Every module receives a `LogosAPI*` pointer when `initLogos()` is called. This is your gateway to communicating with other modules.

```cpp
void MyModulePlugin::initLogos(LogosAPI* logosAPIInstance)
{
    logosAPI = logosAPIInstance;

    // Get a client for calling another module
    LogosAPIClient* client = logosAPI->getClient("other_module");

    // Call a method on that module
    QVariant result = client->invokeRemoteMethod(
        "other_module",  // target module name
        "someMethod",    // method name
        arg1, arg2       // arguments (up to 5 positional args)
    );
}
```

### 6.2 The C++ SDK Code Generator

The `logos-cpp-generator` tool (from `logos-cpp-sdk`) inspects a compiled module and generates typed C++ wrapper classes, so you get compile-time type safety instead of raw `invokeRemoteMethod` calls.

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

After generation, you get typed wrapper classes:

```cpp
#include "logos_sdk.h"  // Umbrella header

// In your module's initLogos():
void MyModulePlugin::initLogos(LogosAPI* api) {
    logosAPI = api;

    // Create the typed SDK wrapper
    LogosModules* logos = new LogosModules(api);

    // Call other modules with type safety
    QString result = logos->other_module.doSomething("hello");
    bool ok = logos->core_manager.loadPlugin("another_module");
}
```

The generated `LogosModules` struct provides a member for each module, with methods matching the module's `Q_INVOKABLE` methods.

### 6.3 LogosResult

Many module methods return `LogosResult` for structured success/error handling:

```cpp
LogosResult result = logos->my_module.someMethod();

if (result.success) {
    // Access the value
    QString value = result.getString();
    int number = result.getInt();
    QVariantMap map = result.getMap();
    QVariantList list = result.getList();

    // Access nested values
    QString name = result.getString("name");
    int count = result.getInt("count", 0);  // with default
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

### 6.4 Communication Modes

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

## Part 7: Advanced Topics

### 7.1 Wrapping External Libraries

To create a module that wraps an external C/C++ library, use the external library template:

```bash
nix flake init -t github:logos-co/logos-module-builder#with-external-lib
```

Then configure the external library in `module.yaml`:

```yaml
name: my_wrapper_module
version: 1.0.0
description: "Wraps libfoo for Logos"

external_libraries:
  - name: libfoo
    flake_input: "github:example/libfoo"
    output_pattern: "lib/libfoo.*"

# Or for a vendored library:
external_libraries:
  - name: libfoo
    vendor_path: "vendor/libfoo"
    build_command: "make"
    output_pattern: "build/lib/libfoo.*"

# Or for a Go library:
external_libraries:
  - name: libfoo
    vendor_path: "vendor/libfoo"
    go_build: true
    output_pattern: "libfoo.*"
```

The builder handles downloading, building, and linking the external library into your module.

### 7.2 UI Modules (C++ Widgets)

To create a module with a native Qt widget UI:

1. Implement the `IComponent` interface
2. Set `"type": "ui"` in your metadata
3. Return a `QWidget*` from `createWidget()`

`IComponent.h` is not part of the SDK — each UI module vendors its own copy in `interfaces/IComponent.h`:

```cpp
// interfaces/IComponent.h  (copy verbatim into your module)
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

Expose it via `INCLUDE_DIRS` in your `CMakeLists.txt`:

```cmake
logos_module(
    NAME my_ui_module
    SOURCES src/my_ui_plugin.h src/my_ui_plugin.cpp
    INCLUDE_DIRS ${CMAKE_CURRENT_SOURCE_DIR}/interfaces
)
```

Then implement the plugin:

```cpp
#include <IComponent.h>

class MyUIPlugin : public QObject, public IComponent
{
    Q_OBJECT
    Q_INTERFACES(IComponent)
    Q_PLUGIN_METADATA(IID IComponent_iid FILE "metadata.json")

public:
    Q_INVOKABLE QWidget* createWidget(LogosAPI* logosAPI = nullptr) override {
        auto* widget = new QWidget();
        // Build your UI here
        return widget;
    }

    void destroyWidget(QWidget* widget) override {
        delete widget;
    }
};
```

### 7.3 UI Modules (QML)

For a QML-based UI module, create a directory with:

```
my_qml_module/
├── manifest.json
├── metadata.json
└── Main.qml
```

**manifest.json:**
```json
{
  "type": "ui_qml",
  "main": "Main.qml",
  "name": "my_qml_module",
  "version": "1.0.0"
}
```

**Main.qml:**
```qml
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    width: 400
    height: 300

    Button {
        text: "Call Core Module"
        onClicked: {
            // logos bridge is injected by the host
            var result = logos.callModule("my_module", "doSomething", ["hello"])
            console.log("Result:", result)
        }
    }
}
```

QML modules are sandboxed: no network access, no filesystem access outside the module directory.

### 7.4 Module Dependencies

Declare dependencies in your `module.yaml`:

```yaml
name: my_module
dependencies:
  - package_manager
  - waku_module
```

Or in `metadata.json`:

```json
{
  "name": "my_module",
  "dependencies": ["package_manager", "waku_module"]
}
```

When your module is installed via `lgpm`, its dependencies are automatically resolved and installed first. When loaded via `logos-basecamp`, core module dependencies are loaded before your module.

---

## Reference: Repository Map

| Repository | What It Provides | Key Outputs |
|------------|-----------------|-------------|
| [logos-module-builder](https://github.com/logos-co/logos-module-builder) | Build system / scaffolding | `mkLogosModule` Nix function, `LogosModule.cmake`, templates |
| [logos-module](https://github.com/logos-co/logos-module) | Plugin introspection | `liblogos_module.a` (static lib), `lm` (CLI) |
| [logos-cpp-sdk](https://github.com/logos-co/logos-cpp-sdk) | SDK + code generator | `LogosAPI`, `LogosResult`, `logos-cpp-generator`, `PluginInterface` |
| [logos-liblogos](https://github.com/logos-co/logos-liblogos) | Core runtime | `logoscore` (CLI), `logos_host`, `liblogos_core` |
| [logos-package](https://github.com/logos-co/logos-package) | Package format | `lgx` (CLI), `liblgx` (library) |
| [logos-package-manager-module](https://github.com/logos-co/logos-package-manager-module) | Package management | `lgpm` (CLI), `package_manager_plugin` |
| [logos-basecamp](https://github.com/logos-co/logos-basecamp) | Desktop app shell | `LogosApp` (GUI), MDI workspace, plugin loader |

## Reference: CLI Tools Summary

### `lm` -- Module Inspector

```bash
lm metadata <plugin-file> [--json]    # View module metadata
lm methods <plugin-file> [--json]     # List Q_INVOKABLE methods
```

### `logoscore` -- Headless Runtime

```bash
logoscore -m <modules-dir> --load-modules <name> [-c "<module>.<method>(args)"]
```

### `lgx` -- Package Tool

```bash
lgx create <output.lgx> --name <name>                  # Create empty package
lgx add-variant <pkg.lgx> --variant <name> --files <path> [--main <file>]
lgx remove-variant <pkg.lgx> --variant <name>
lgx list <pkg.lgx>                                      # List contents
lgx verify <pkg.lgx>                                    # Validate structure
lgx extract <pkg.lgx> --variant <name> --output <dir>   # Extract
```

### `lgpm` -- Package Manager

```bash
lgpm search <query>                          # Search packages
lgpm list [--category <cat>] [--installed]   # List packages
lgpm install <pkg> [pkgs...]                 # Install with dependency resolution
lgpm install --file <path.lgx>               # Install local file
lgpm info <pkg>                              # Package details
lgpm categories                              # List categories
```

### `logos-cpp-generator` -- SDK Code Generator

```bash
logos-cpp-generator <plugin-file> [--output-dir <dir>] [--module-only]
logos-cpp-generator --metadata <metadata.json> --module-dir <dir> [--output-dir <dir>]
logos-cpp-generator --metadata <metadata.json> --general-only [--output-dir <dir>]
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
- Try specifying a release: `lgpm --release v1.0.0 install my_module`
- For local files: `lgpm install --file ./my_module.lgx`
- Check the target directory is writable: `lgpm --modules-dir ./modules install my_module`

### Cross-platform builds

Build on each target platform separately, then add each binary as a variant to the same `.lgx` package:

```bash
# On Linux x86_64:
nix build .#lib
lgx add-variant my_module.lgx --variant linux-x86_64 --files ./result/lib/my_module_plugin.so

# On macOS arm64:
nix build .#lib
lgx add-variant my_module.lgx --variant darwin-arm64 --files ./result/lib/my_module_plugin.dylib
```
