# logos-tutorial

Tutorial series and reference documentation for building Logos modules.

## Start Here

**New to Logos?** Start with the developer guide -- it walks through creating, building, packaging, and running your first module:

- [Logos Developer Guide](logos-developer-guide.md)

## Next Tutorials

Step-by-step tutorials that build on each other. Each creates a working module you can run.

- **Part 1:** [Wrapping a C Library](tutorial-wrapping-c-library.md) -- build `calc_module`, a core module that wraps a C library (`libcalc`). Covers external library configuration, CMake integration, building, inspecting with `lm`, testing with `logoscore`, and packaging with `nix-bundle-lgx`.

- **Part 2:** [Building a QML UI App](tutorial-qml-ui-app.md) -- build `calc_ui`, a QML-only `ui_qml` module that calls `calc_module` through the `logos.callModule()` bridge. No compilation needed. Scaffold: `nix flake init -t ...#ui-qml`

- **Part 3:** [Building a C++ UI Module (Process-Isolated)](tutorial-cpp-ui-app.md) — build `calc_ui_cpp`, a `ui_qml` module with a C++ backend that runs in a separate `ui-host` process. Define the remote interface in a `.rep` file; the C++ backend inherits from the generated `SimpleSource`; QML accesses it via a typed replica using `logos.module()` and `QtRemoteObjects.watch()`. Scaffold: `nix flake init -t ...#ui-qml-backend`

## Example Modules

Working module source code used by the tutorials:

| Directory | Module | Type | Tutorial |
|-----------|--------|------|----------|
| `logos-calc-module/` | `calc_module` | `core` (wraps libcalc) | Part 1 |
| `logos-calc-ui/` | `calc_ui` | `ui_qml` (QML-only) | Part 2 |
| `logos-calc-ui-cpp/` | `calc_ui_cpp` | `ui_qml` (C++ backend + QML view) | Part 3 |

## Running Tutorial Tests

The `tests/` directory contains automated tutorial verification tests. Each test replays a tutorial from scratch — scaffolding, writing files, building, inspecting, and optionally verifying in Logos Basecamp.

### Prerequisites

- Nix with flakes enabled
- `yq` (YAML processor) and `nodejs` — provided via `nix-shell -p yq-go nodejs`
- For basecamp UI tests: a built `LogosBasecamp` binary and `logos-qt-mcp` package

### Quick Start

```bash
# Run a single tutorial test (scaffold + files + build + inspect phases)
nix-shell -p yq-go nodejs --run "./tests/run-tutorial-test.sh tests/tutorial-wrapping-c-library.test.yaml"

# Run with a specific working directory (must exist)
mkdir -p /tmp/tutorial-test
nix-shell -p yq-go nodejs --run "./tests/run-tutorial-test.sh tests/tutorial-wrapping-c-library.test.yaml --workdir /tmp/tutorial-test"

# Run specific phases only
nix-shell -p yq-go nodejs --run "./tests/run-tutorial-test.sh tests/tutorial-qml-ui-app.test.yaml --phase scaffold,files,build"

# Verbose output
nix-shell -p yq-go nodejs --run "./tests/run-tutorial-test.sh tests/tutorial-wrapping-c-library.test.yaml --verbose"
```

### Running with Basecamp UI Verification

To test that a tutorial's module works in Logos Basecamp, provide the basecamp binary and qt-mcp framework:

```bash
# First, build basecamp and qt-mcp from the logos-basecamp repo
cd /path/to/logos-basecamp
nix build -o result-basecamp
nix build '.#logos-qt-mcp' -o result-mcp

# Then run the tutorial test with basecamp phase
cd /path/to/logos-tutorial
mkdir -p /tmp/tutorial-test
nix-shell -p yq-go nodejs --run "./tests/run-tutorial-test.sh tests/tutorial-wrapping-c-library.test.yaml \
  --workdir /tmp/tutorial-test \
  --basecamp-bin /path/to/logos-basecamp/result-basecamp/bin/LogosBasecamp \
  --qt-mcp /path/to/logos-basecamp/result-mcp \
  --verbose"
```

### Available Test Specs

| Test File | Tutorial | Phases |
|-----------|----------|--------|
| `tests/tutorial-wrapping-c-library.test.yaml` | Part 1: Wrapping a C Library | scaffold, files, build, inspect, logoscore, basecamp |
| `tests/tutorial-qml-ui-app.test.yaml` | Part 2: QML UI App | scaffold, files, build, inspect, basecamp |
| `tests/tutorial-cpp-ui-app.test.yaml` | Part 3: C++ UI Module | scaffold, files, build, inspect, basecamp |

### Options

| Flag | Description |
|------|-------------|
| `--workdir <path>` | Working directory (must exist; default: creates temp dir) |
| `--phase <phases>` | Comma-separated phases to run (default: all) |
| `--basecamp-bin <path>` | Path to LogosBasecamp binary |
| `--qt-mcp <path>` | Path to logos-qt-mcp package |
| `--verbose` | Show detailed output |

### Notes

- The `logoscore` phase requires the `logoscore` CLI to be on PATH (provided by the workspace `scripts/` directory)
- The basecamp phase runs in offscreen mode (`QT_QPA_PLATFORM=offscreen`) — no display required
- Tests use a temporary directory by default; pass `--workdir` to preserve build artifacts for debugging
- UI tutorial tests (`tutorial-qml-ui-app`, `tutorial-cpp-ui-app`) automatically install their core module dependencies before launching basecamp
