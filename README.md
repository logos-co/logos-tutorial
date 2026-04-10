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
