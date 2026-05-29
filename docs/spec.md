# Tutorial YAML Spec Format

This document describes the YAML format used by `tools/tutorial_runner.py` to define executable tutorials. Each `.test.yaml` file is the **single source of truth** — it drives both:

- **Execution** (`run`): steps are executed in a temp directory, commands run, outputs verified
- **Markdown generation** (`generate`): a `.md` tutorial is produced from the same YAML

## Quick example

```yaml
name: "My Tutorial"
output: my-tutorial.md
release: ""

intro: |
  One-paragraph description of what this tutorial covers.

what_you_build: "A short sentence describing the end result."

what_you_learn:
  - First learning objective
  - Second learning objective

prerequisites:
  - "**Nix** with flakes enabled."

sections:
  - title: "Set Up the Project"
    phase: scaffold
    text: |
      Intro paragraph for this section.
    steps:
      - title: "Create the directory"
        run: "mkdir -p my-project"

      - title: "Write the config"
        text: "Create `config.json`:"
        file:
          path: config.json
          language: json
          content: |
            { "name": "example" }

      - title: "Build"
        run: "nix build"
        expect_contains:
          - "Build successful"
```

## Top-level fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | yes | string | Tutorial title. Used as the `# heading` in generated markdown and in runner output. |
| `output` | no | string | Default output filename for `generate` (relative to the tutorial directory, e.g., `tutorial-wrapping-c-library.md`). Can be overridden with `-o`. |
| `project_name` | no | string | Directory name for this tutorial's project (e.g., `logos-calc-module`). Used when chaining tutorials via `requires:` — each tutorial runs in a subdirectory of a shared parent. Ignored when running standalone. |
| `requires` | no | list of strings | Paths to prerequisite `.test.yaml` specs (relative to the current spec). The runner executes each prerequisite first in a sibling subdirectory (named by its `project_name`), then runs the current tutorial. Prerequisites are resolved **transitively** — if A requires B and B requires C, the run order is C, B, A. Shared prerequisites run once (deduped), and circular `requires:` are reported as an error. This enables cross-tutorial references like `../logos-calc-module`. Requires `project_name` on both the current and prerequisite specs. |
| `intro` | no | string | Introductory paragraph(s). Rendered after the title in the markdown. Supports full markdown. |
| `what_you_build` | no | string | One-line summary prefixed with "**What you'll build:**" in the markdown. |
| `what_you_learn` | no | list of strings | Bullet list prefixed with "**What you'll learn:**". |
| `comparison` | no | string | Free-form markdown block rendered after the learning objectives (useful for comparison tables). |
| `prerequisites` | no | list of strings | Rendered as a bullet list under a prerequisites heading. Each item can contain markdown (code blocks, links, etc.). |
| `release` | no | string | Git tag applied to all `{release}` placeholders in GitHub URLs (e.g., `tutorial-v2`). See [Release tags](#release-tags). |
| `build_overrides` | no | map | Nix `--override-input` flags for the runner. Keys are input names, values are relative paths to local repos. Only affects execution, not generation. |
| `sections` | yes | list | The tutorial content. See below. |

## Sections

Each section becomes a `## heading` in the markdown. Sections with `step: true` get auto-numbered as "Step N: Title".

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `title` | yes | string | Section heading. |
| `step` | no | boolean | If `true`, this section is numbered as "Step N: Title" in markdown and gets a `---` separator after it (except the last section). Sections without `step` render as plain `## Title`. |
| `text` | no | string | Introductory prose rendered before the steps. Supports full markdown (tables, blockquotes, code blocks, etc.). |
| `steps` | no | list | Ordered list of steps. See below. |

Sections without `steps` are prose-only — the `text` is rendered as-is. This is useful for reference sections like "Troubleshooting" or "Common Patterns".

## Steps

Steps are the core building blocks. Each step can combine multiple fields. The rendering order in the generated markdown is:

1. `title` → `### heading`
2. `text` → prose paragraph
3. `file` → code block with file contents
4. `run` → bash code block
5. `post_text` → prose after the action
6. `extra_run` → additional command block (no heading)

A step without a `title` renders its content inline under the previous heading — useful for continuation content like "Then run:" followed by a code block.

### Step fields

#### `title` (string, optional)

Rendered as a `### heading` in the markdown. Steps without a title don't get a heading — their content flows under the previous step's heading.

#### `text` (string, optional)

Prose rendered before any action. Supports full markdown.

#### `file` (object, optional)

Writes a file to disk during execution and renders it as a code block in the markdown.

| Subfield | Type | Description |
|----------|------|-------------|
| `path` | string | Relative path within the project (e.g., `src/main.cpp`, `lib/libcalc.h`). |
| `content` | string | The file contents. |
| `language` | string | Syntax highlighting hint for the markdown code block. Auto-detected from extension if omitted (`.c` → `c`, `.h`/`.cpp` → `cpp`, `.json` → `json`, `.nix` → `nix`, etc.). |
| `encoding` | string | Set to `base64` for binary files. Renders as `*Binary file: \`path\`*` instead of a code block. |

**Runner behavior:** Creates parent directories and writes the file to disk.

**Generator behavior:** Renders ` ```language ` code block with the content.

#### `run` (string, optional)

A shell command to execute and display.

| Subfield | Type | Description |
|----------|------|-------------|
| (value) | string | The command to execute. Supports `{ext}` (expands to `so` or `dylib`) and `{shared_flags}` (expands to `-shared -fPIC` or `-dynamiclib`). |

**Runner behavior:** Expands platform placeholders, injects nix overrides if applicable, and runs the command. Checks exit code (0 = pass, non-zero = fail).

**Generator behavior:** Renders the command in a ` ```bash ` block. If `code_block` is present on the step, renders that instead (see below).

#### `code_block` (string, optional)

The exact content to show in the generated markdown, used **instead of** the `run` command. This is for cases where:

- The executed command differs from what readers should see (e.g., `&&`-chained commands displayed as separate lines)
- Platform-specific variants should be shown (Linux and macOS versions)
- The display should include comments, blank lines, or additional context

The runner ignores `code_block` — it only uses `run` for execution.

```yaml
- title: "Build the shared library"
  run: "cd lib && gcc {shared_flags} -o libcalc.{ext} libcalc.c && cd .."
  code_block: |
    cd lib

    # Linux
    gcc -shared -fPIC -o libcalc.so libcalc.c

    # macOS
    # gcc -shared -fPIC -o libcalc.dylib libcalc.c

    cd ..
```

#### `expect_contains` (list of strings, optional)

Assertions checked by the runner against command output. Not rendered in the markdown.

```yaml
run: "./lm/bin/lm metadata result/lib/calc_module_plugin.{ext}"
expect_contains:
  - "Name:         calc_module"
  - "Version:      1.0.0"
```

**Runner behavior:** Captures stdout+stderr, checks that every string appears in the output.

**Generator behavior:** Ignored — not rendered. Use `post_text` to show expected output to readers.

#### `check_file` (string, optional)

Verifies a file exists. Runner-only, not rendered in the markdown.

```yaml
- check_file: "result/lib/calc_module_plugin.{ext}"
```

**Runner behavior:** Expands `{ext}`, globs for the file, passes if found.

**Generator behavior:** Ignored — not rendered.

#### `ui_test` (object, optional)

Runs headless UI tests against a Qt app using [logos-qt-mcp](https://github.com/logos-co/logos-qt-mcp). The app is launched with `QT_QPA_PLATFORM=offscreen` (no display needed) and tests connect to the QML inspector to verify elements, click buttons, and check results.

Two modes:
- **Launch mode** (preferred): `launch` runs the app as a background process, tests connect to its inspector, app is killed when done. The `launch` command is rendered in the generated markdown.
- **Binary mode**: `build` + `binary` let the test framework manage the app via `--ci`. Not rendered in markdown.

| Subfield | Type | Description |
|----------|------|-------------|
| `launch` | string | Command to launch the app (e.g., `nix run .`). Launched as a background process with offscreen Qt. **Rendered** in generated markdown as a bash code block. |
| `build` | string | Command to build the app binary (binary mode only, not rendered). |
| `binary` | string | Path to the app binary or `nix-app` to auto-resolve from flake (binary mode only). |
| `qt_mcp` | string | Path to the logos-qt-mcp package, relative to workdir (e.g., `result-mcp`). Falls back to `--qt-mcp` CLI flag or `LOGOS_QT_MCP` env var. |
| `setup` | list of strings | Commands to run before testing (e.g., `nix build 'github:logos-co/logos-qt-mcp' -o result-mcp`). |
| `inspector_port` | integer | TCP port for the QML inspector (default: 3768). |
| `tests` | list of objects | Test actions to execute. See below. |

**Test actions:**

| Action | Fields | What it does |
|--------|--------|--------------|
| `click` | `target` | Find element by text and click it |
| `wait_for` | `texts`, `timeout` (ms, default 10000), `name` | Poll until all texts are visible |
| `expect_texts` | `texts` | Assert all texts are visible now |
| `set_text` | `find_by`, `find_value`, `value` | Find element by property and set its `text` property |
| `sleep` | `ms` | Wait a fixed duration |

Any action may also carry an optional **`screenshot`** field (a filename, e.g.
`screenshot: "result.png"`). After that action runs, the runner captures the
headless app via the qt-mcp `app.screenshot()` API and writes the PNG to an
`images/` directory next to the generated `.md` (`<output-dir>/images/`; temp
runs fall back to the workdir). The generator then embeds it inline in that
section as `![<name>](images/<file>.png)`, so screenshots appear in the
published tutorial with no extra markup. The `.png` extension is added if
omitted; the value is reduced to a basename.

The two-column HTML report (`--report`) inlines each captured screenshot as a
base64 `data:` URI, so the report stays a single self-contained file that
renders the screenshots even when served from GitHub Pages (where only the
`index.html` is published). If a capture is missing (e.g. its step failed), the
report falls back to the relative `images/<file>.png` link.

**Runner behavior (launch mode):** Runs setup commands, launches the app in the background with `QT_QPA_PLATFORM=offscreen`, waits for the QML inspector to be available, generates a `.mjs` test file, runs it, then kills the app. Reports pass/fail.

**Runner behavior (binary mode):** Runs setup + build, generates a `.mjs` test file, runs it via `node test.mjs --ci <binary> --verbose`. Reports pass/fail.

**Generator behavior:** In launch mode, `launch` is rendered as a ` ```bash ` code block. In binary mode, nothing is rendered. Use `text:` and `post_text:` for additional user-facing prose.

```yaml
# Launch mode (preferred) — what's shown is what's executed
- ui_test:
    launch: "nix run ."
    setup:
      - "nix build 'github:logos-co/logos-qt-mcp' -o result-mcp"
    qt_mcp: "result-mcp"
    tests:
      - name: "Title visible"
        action: wait_for
        texts: ["Logos Calculator"]
        timeout: 15000
      - name: "Enter number"
        action: set_text
        find_by: "placeholderText"
        find_value: "a"
        value: "3"
      - name: "Click Add"
        action: click
        target: "Add"
      - name: "Result shows 3"
        action: wait_for
        texts: ["3"]
        timeout: 10000
```

#### `post_text` (string, optional)

Prose rendered **after** the step's action (file, run). Supports full markdown including code blocks, tables, blockquotes.

Use this for:
- Expected output blocks
- Explanations of what just happened
- Callout boxes and tips

```yaml
- title: "View metadata"
  run: "./lm/bin/lm metadata result/lib/plugin.{ext}"
  post_text: |
    Output:

    ```
    Plugin Metadata:
    ================
    Name:         my_module
    Version:      1.0.0
    ```
```

#### `extra_run` (object, optional)

A continuation command rendered under the same step heading (no separate `###`). Useful when a step has two related commands (e.g., build then verify).

| Subfield | Type | Description |
|----------|------|-------------|
| `run` | string | Command to execute. |
| `code_block` | string | Display override (same as step-level `code_block`). |
| `post_text` | string | Prose after the extra command. |

```yaml
- title: "Build the shared library"
  run: "cd lib && gcc {shared_flags} -o libcalc.{ext} libcalc.c && cd .."
  code_block: |
    cd lib
    gcc -shared -fPIC -o libcalc.so libcalc.c
    cd ..
  post_text: "Verify the symbols are exported:"
  extra_run:
    run: "nm -gU lib/libcalc.{ext} | grep calc"
    code_block: |
      # Linux
      nm -D lib/libcalc.so | grep calc

      # macOS
      # nm -gU lib/libcalc.dylib | grep calc
    post_text: |
      You should see symbols marked with `T`.
```

## Platform placeholders

These placeholders are expanded at execution time by the runner and at generation time in rendered content:

| Placeholder | Linux | macOS |
|-------------|-------|-------|
| `{ext}` | `so` | `dylib` |
| `{shared_flags}` | `-shared -fPIC` | `-dynamiclib` |

Platform placeholders work in `run`, `check_file`, `extra_run.run`, and `file.content` fields. They are **not** expanded in `code_block`, `text`, or `post_text` — those are rendered verbatim.

When a command uses platform placeholders, provide a `code_block` showing both platform variants for the markdown.

## Release tags

The `release` field lets you pin all GitHub URLs to a specific git tag. This avoids updating every URL individually when you want all `nix build 'github:logos-co/...'` commands to use the same release.

Use the `{release}` placeholder in `run` commands, `code_block`, and `file.content`:

```yaml
release: "tutorial-v2"

sections:
  - title: "Set Up"
    steps:
      - run: "nix flake init -t github:logos-co/logos-module-builder{release}#with-external-lib"
      - run: "nix build 'github:logos-co/logos-module{release}#lm' --out-link ./lm"
```

When `release` is set to `"tutorial-v2"`, `{release}` expands to `/tutorial-v2`:

```bash
nix build 'github:logos-co/logos-module/tutorial-v2#lm' --out-link ./lm
```

When `release` is empty or omitted, `{release}` expands to nothing:

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

The `--release` CLI flag overrides the YAML field:

```bash
# Use a specific tag (overrides whatever is in the YAML)
python3 tools/tutorial_runner.py run spec.yaml --release tutorial-v3

# Generate markdown with a tag
python3 tools/tutorial_runner.py generate spec.yaml --release tutorial-v2

# Clear the tag even if the YAML sets one
python3 tools/tutorial_runner.py run spec.yaml --release ""
```

## Runner behavior

- Creates a fresh temp directory (or uses `--output-dir` / `--workdir`) — all files, builds, and commands happen there
- Walks sections and steps in order
- Executes `file`, `run`, `check_file`, `ui_test` actions
- Tracks pass/fail/skip counts
- **Stops on first failure** by default (use `--continue-on-fail` to override)
- Prints a summary report at the end (and an HTML report with `--report <path>`)
- By default the temp directory is **deleted** when the run finishes (use `--output-dir` or `--keep-workdir` to keep it)

### Working directory

The runner needs a directory to work in. There are four modes:

1. **Default (temp dir, auto-deleted):** A fresh `/tmp/tutorial-test-XXXXX/` is created and removed after the run.
2. **`--keep-workdir`:** Same temp dir, but it's kept after the run so you can inspect the results (built artifacts, installed modules, etc.).
3. **`--output-dir <dir>`:** Run into `<dir>` and **keep it** — created if missing, never auto-deleted. This is the mode to use when you want the finished tutorial output (built modules, `.lgx` packages, `result/` symlinks) in a known location. For a chained tutorial (`requires:`) `<dir>` becomes the chain root and each project lands in `<dir>/<project_name>/`; for a standalone spec the project is written directly into `<dir>`. The path is printed as `output : <dir>` at the end of the run.
4. **`--workdir <path>`:** Use an **existing** directory. It is never created for you, and it runs the spec **standalone** — `requires:` prerequisite chains are *not* run in this mode (the directory is used as the single project's workdir). Useful for re-running a spec against a previous build or for debugging. Note: unless `--keep-workdir` is also given, the directory is deleted on exit. Prefer `--output-dir` when you want a persistent, chain-aware output location.

The workdir path is printed at the top of every run:

```
  workdir  : /tmp/tutorial-test-abc123
```

### Tutorial chaining (`requires`)

When a spec has `requires:`, the runner creates a shared parent directory and runs each prerequisite before the main tutorial. Each tutorial gets its own subdirectory named by `project_name`:

```
# Part 2 requires Part 1:
requires:
  - tutorial-wrapping-c-library.test.yaml
project_name: logos-calc-ui
```

```
# Running Part 2 automatically runs Part 1 first:
python3 tools/tutorial_runner.py run tests/tutorial-qml-ui-app.test.yaml

# Resulting directory structure:
/tmp/tutorial-chain-XXXXX/
├── logos-calc-module/    # Part 1 (prerequisite)
└── logos-calc-ui/        # Part 2 (main)
```

Commands like `../logos-calc-module` in Part 2 resolve to Part 1's output. Results are cumulative — a failure in any tutorial stops the chain (unless `--continue-on-fail`).

`requires:` is resolved **transitively**. A spec only needs to declare its *direct* prerequisites; their prerequisites are pulled in automatically. For the three-part series, Part 3 can simply declare Part 2:

```
# Part 3 requires Part 2, which itself requires Part 1:
requires:
  - tutorial-qml-ui-app.test.yaml
project_name: logos-calc-ui-cpp
```

```
# Running Part 3 resolves the whole graph and runs in dependency order:
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml

# Resulting directory structure (Part 1 → Part 2 → Part 3):
/tmp/tutorial-chain-XXXXX/
├── logos-calc-module/    # Part 1 (transitive prerequisite, runs first)
├── logos-calc-ui/        # Part 2 (direct prerequisite, runs second)
└── logos-calc-ui-cpp/    # Part 3 (main, runs last)
```

The graph is walked depth-first in post-order, so a prerequisite always runs before the spec that needs it. A prerequisite shared by multiple specs runs only once, and a circular `requires:` chain is reported as an error rather than looping forever.

When running standalone (no `requires:`), `project_name` is ignored and the runner behaves as before.

### HTML execution report (`--report`)

`run --report <path>` writes a self-contained HTML report next to (or instead of) the console output. The report has **two columns per step**:

- **Left:** the step's rendered tutorial markdown — identical to what `generate` produces, so the report shows exactly what the reader sees.
- **Right:** the command(s) actually executed for that step and their captured output, each with a pass/fail badge and exit code.

It records every executed action type:

| Step type | Recorded on the right |
|-----------|-----------------------|
| `file`    | the path written and a pass/fail marker (contents already shown on the left) |
| `run` / `extra_run` | the expanded command, exit code, and combined stdout/stderr (both the command and its `(verify)` continuation appear) |
| `check_file` | the glob checked and which file matched |
| `ui_test` | the launch command, the list of UI test actions, and the framework output (plus the app log tail on failure) |

When a chain runs (`requires:`), every tutorial in the chain is included; a dropdown at the top switches between them. Markdown is rendered client-side via [marked.js](https://marked.js.org/) loaded from a CDN, so viewing the report needs network access on first open.

Pair `--report` with `--continue-on-fail` so the report captures the full run rather than stopping at the first failure. The CI workflow ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs with `--report` and publishes the result to GitHub Pages, linked from a PR comment.

### Live TUI (`--tui` / `--iterative`)

`run --tui` shows the same two-column view live in the terminal instead of (or in addition to) writing an HTML file. The left pane renders the current step's tutorial markdown; the right pane shows the command being executed and its output, updating as the run proceeds. Execution goes through the exact same handlers as a normal run, so behaviour is identical — only the presentation differs.

- **Auto mode (default):** steps execute back-to-back; failed steps pause briefly so they're readable.
- **`--iterative`:** the runner waits for a keypress before executing each step — **down arrow**, **right arrow**, or **space** to advance; **`q`** to quit. (Using `--iterative` without `--tui` is an error.)

`--tui` requires an interactive terminal (a TTY) and the [`rich`](https://github.com/Textualize/rich) package. `rich` is an **optional** dependency used only for the TUI; if it's not installed the runner prints an install hint and exits. All other functionality needs only `pyyaml`.

## Generator behavior

- Walks the same YAML structure
- Produces markdown with proper headings, code blocks, and prose
- Sections with `phase` get numbered as "Step 1:", "Step 2:", etc.
- Sections without `phase` get plain `## Title` headings
- `expect_contains` and `check_file` are not rendered (runner-only)
- `code_block` overrides the `run` value for display
- `file` content is rendered as a fenced code block with syntax highlighting
- Triple blank lines are collapsed to double

## File layout

```
repos/logos-tutorial/
├── tests/
│   └── tutorial-wrapping-c-library.test.yaml   # The spec
├── tools/
│   ├── tutorial_runner.py                       # Runner + generator
│   └── run-tutorial                             # Nix wrapper script
├── tutorial-wrapping-c-library.md               # Generated output
└── docs/
    └── spec.md                                  # This file
```

## Usage

```bash
# Run a tutorial (temp dir, auto-deleted)
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --verbose

# Run into a persistent output directory (created if missing, never deleted).
# For a chained tutorial each part lands in <dir>/<project_name>/.
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml \
  --output-dir ./outputs --continue-on-fail

# Keep the auto-generated temp directory for debugging
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --keep-workdir --verbose

# Re-run a spec standalone against an existing directory
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --workdir /tmp/my-tutorial-test --verbose

# Write a two-column HTML report (rendered tutorial + commands run and their output)
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml \
  --report ./tutorial-report.html --continue-on-fail

# Generate markdown
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml

# Generate to a specific file
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml -o my-output.md

# Use nix wrapper (ensures python3 + pyyaml are available)
./tools/run-tutorial run tests/tutorial-wrapping-c-library.test.yaml --verbose
```
