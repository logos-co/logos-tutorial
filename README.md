# logos-tutorial

Tutorial series and reference documentation for building Logos modules.

## Start Here

**New to Logos?** Start with the developer guide -- it walks through creating, building, packaging, and running your first module:

- [Logos Developer Guide](logos-developer-guide.md)

## Next Tutorials

Step-by-step tutorials that build on each other. Each creates a working module you can run.

- **Part 1:** [Wrapping a C Library](tutorial-wrapping-c-library.md) -- build `calc_module`, a core module that wraps a C library (`libcalc`). Covers external library configuration, CMake integration, building, inspecting with `lm`, testing with `logoscore`, and packaging with `nix-bundle-lgx`.

- **Part 2:** [Building a QML UI App](tutorial-qml-ui-app.md) -- build `calc_ui`, a QML-only UI plugin that calls `calc_module` through the `logos.callModule()` bridge. No compilation needed.

- **Part 3:** [Building a C++ UI Module](tutorial-cpp-ui-app.md) -- build `calc_ui_cpp`, a native C++ Qt widget plugin with typed backend calls to `calc_module` via `LogosAPI*`.

## Example Modules

Working module source code used by the tutorials:

| Directory | Module | Type | Tutorial |
|-----------|--------|------|----------|
| `logos-calc-module/` | `calc_module` | Core (wraps libcalc) | Part 1 |
| `logos-calc-ui/` | `calc_ui` | QML UI | Part 2 |
| `logos-calc-cpp-ui/` | `calc_ui_cpp` | C++ UI | Part 3 |
