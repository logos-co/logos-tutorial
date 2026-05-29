# logos-tutorial

Tutorial series and reference documentation for building Logos modules.

## Start Here

**New to Logos?** Start with the developer guide -- it walks through creating, building, packaging, and running your first module:

- [Logos Developer Guide](logos-developer-guide.md)

## Next Tutorials

Step-by-step tutorials that build on each other. Each creates a working module you can run.

- **Part 1:** [Wrapping a C Library](outputs/tutorial-wrapping-c-library.md) -- build `calc_module`, a core module that wraps a C library (`libcalc`). Covers external library configuration, CMake integration, building, inspecting with `lm`, testing with `logoscore`, and packaging with `nix-bundle-lgx`.

- **Part 2:** [Building a QML UI App](outputs/tutorial-qml-ui-app.md) -- build `calc_ui`, a QML-only `ui_qml` module that calls `calc_module` through the `logos.callModule()` bridge. No compilation needed. Scaffold: `nix flake init -t ...#ui-qml`

- **Part 3:** [Building a C++ UI Module (Process-Isolated)](outputs/tutorial-cpp-ui-app.md) — build `calc_ui_cpp`, a `ui_qml` module with a C++ backend that runs in a separate `ui-host` process. Define the remote interface in a `.rep` file; the C++ backend inherits from the generated `SimpleSource`; QML accesses it via a typed replica using `logos.module()` and `QtRemoteObjects.watch()`. Scaffold: `nix flake init -t ...#ui-qml-backend`

- **logos-dev-boost:** _(⚠️ **EXPERIMENTAL — NOT READY**)_ [Scaffolding Modules with logos-dev-boost](tutorial-dev-boost.md) — use the `logos-dev-boost` CLI to auto-generate modules from C library directories. Wraps libcalc (source-only) and sqlcipher (pre-built `.so`), including integration tests that create encrypted databases. Covers `--type module`, `--type full-app`, and `--lib-dir`.

## Executable Tutorials

Tutorials have YAML specs in `tests/` that can be both **executed** (to verify they work) and used to **generate** the `.md` files. See [docs/spec.md](docs/spec.md) for the full format reference.

```bash
# Run a tutorial end-to-end (temp dir, deleted afterwards)
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --verbose

# Keep the build results in a directory of your choice (created if missing,
# never deleted). For a chained tutorial each part lands in its own subdir.
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml \
  --output-dir ./outputs --continue-on-fail

# Write a two-column HTML report: rendered tutorial on the left, the commands
# actually run and their output on the right. Open the file in a browser.
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml \
  --report ./tutorial-report.html --continue-on-fail

# Generate the .md tutorial from the YAML spec
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml

# Pin all GitHub URLs to a specific release tag
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --release tutorial-v2
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml --release tutorial-v2
```

### Where the results go

- `--output-dir DIR` — run into `DIR` and **keep it** (created if missing, never auto-deleted). This is the flag to use when you want to inspect or reuse the built modules. A tutorial with `requires:` (e.g. Part 3, which pulls in Parts 1 and 2) treats `DIR` as the chain root and writes each project into its own subdirectory:

  ```
  ./outputs/
  ├── logos-calc-module/    # Part 1 (built first via requires:)
  ├── logos-calc-ui/        # Part 2
  └── logos-calc-ui-cpp/    # Part 3
  ```

  A standalone spec (no `requires:`) is written directly into `DIR`.

- `--workdir DIR` — run into an **existing** directory. Unlike `--output-dir`, it does not create the directory, it is deleted on exit unless you add `--keep-workdir`, and it runs the spec **standalone** (prerequisite `requires:` chains are skipped). Prefer `--output-dir` for chained tutorials.

- Without either flag, a temp directory is created and deleted after the run (add `--keep-workdir` to preserve the temp dir).

### Reviewing what ran (`--report`)

`--report PATH` writes a self-contained HTML report with two columns per step:

- **left** — the rendered tutorial markdown (identical to the published `.md`),
- **right** — the command(s) actually executed at that step and their output, with a pass/fail badge.

It covers every step type (file writes, shell commands, `check_file`, and headless `ui_test` runs). Pair it with `--continue-on-fail` so the report captures the whole run instead of stopping at the first failure. CI publishes this report for every run — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

The `--release` flag (or the `release` field in the YAML) pins all `{release}` placeholders in GitHub URLs to a git tag, so `github:logos-co/repo{release}#output` becomes `github:logos-co/repo/tutorial-v2#output`. Set it to `""` or omit it for latest.

## Example Modules

Working module source code used by the tutorials:

| Directory | Module | Type | Tutorial |
|-----------|--------|------|----------|
| `logos-calc-module/` | `calc_module` | `core` (wraps libcalc) | Part 1 |
| `logos-calc-ui/` | `calc_ui` | `ui_qml` (QML-only) | Part 2 |
| `logos-calc-ui-cpp/` | `calc_ui_cpp` | `ui_qml` (C++ backend + QML view) | Part 3 |

## Regenerating the outputs

The `outputs/` directory (the rendered `.md` tutorials linked above, plus the built module source trees) is generated from the YAML specs. To regenerate it, run:

```bash
./run.sh
```

This:

1. **Runs** the full tutorial chain (Part 1 → 2 → 3) into `./outputs/`, executing every step so the result is verified, not just rendered. Each part lands in its own subdirectory (`outputs/logos-calc-module/`, `outputs/logos-calc-ui/`, `outputs/logos-calc-ui-cpp/`).
2. **Generates** the `.md` tutorial for every `tests/*.test.yaml` spec into `outputs/` (`tutorial-wrapping-c-library.md`, `tutorial-qml-ui-app.md`, `tutorial-cpp-ui-app.md`).
3. **Cleans** each output project so only the source remains — it removes the per-project `.git/` directories (each tutorial `git init`s its project), the nix out-link symlinks (`lm`, `logos`, `pm`, `result*`), build output (`modules/`), and compiled libraries (`*.dylib`, `*.so`).

> **Note:** the run requires [Nix with flakes](https://nixos.org/download.html) and pulls/builds real dependencies (Qt, the Logos SDK), so the first run is slow. On Linux, add `--continue-on-fail` to the `run` command in `run.sh` if a known-failing prerequisite step would otherwise stop the chain early.
