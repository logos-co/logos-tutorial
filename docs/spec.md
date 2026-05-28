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
| `intro` | no | string | Introductory paragraph(s). Rendered after the title in the markdown. Supports full markdown. |
| `what_you_build` | no | string | One-line summary prefixed with "**What you'll build:**" in the markdown. |
| `what_you_learn` | no | list of strings | Bullet list prefixed with "**What you'll learn:**". |
| `comparison` | no | string | Free-form markdown block rendered after the learning objectives (useful for comparison tables). |
| `prerequisites` | no | list of strings | Rendered as a bullet list under a `## Prerequisites` heading. Each item can contain markdown (code blocks, links, etc.). |
| `release` | no | string | Git tag applied to all `{release}` placeholders in GitHub URLs (e.g., `tutorial-v2`). See [Release tags](#release-tags). |
| `build_overrides` | no | map | Nix `--override-input` flags for the runner. Keys are input names, values are relative paths to local repos. Only affects execution, not generation. |
| `sections` | yes | list | The tutorial content. See below. |

## Sections

Each section becomes a `## heading` in the markdown. Sections with a `phase` get auto-numbered as "Step N: Title".

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `title` | yes | string | Section heading. |
| `phase` | no | string | Groups the section for selective execution. One of: `scaffold`, `files`, `build`, `inspect`, `logoscore`, `basecamp`. Sections with a phase are numbered as "Step N" in markdown. Sections without a phase render as plain `## Title`. |
| `text` | no | string | Introductory prose rendered before the steps. Supports full markdown (tables, blockquotes, code blocks, etc.). |
| `steps` | no | list | Ordered list of steps. See below. |

Sections without `steps` are prose-only — the `text` is rendered as-is. This is useful for reference sections like "Troubleshooting" or "Common Patterns".

## Steps

Steps are the core building blocks. Each step can combine multiple fields. The rendering order in the generated markdown is:

1. `title` → `### heading`
2. `text` → prose paragraph
3. `scaffold` → bash code block (template init)
4. `file` → code block with file contents
5. `run` → bash code block
6. `post_text` → prose after the action
7. `extra_run` → additional command block (no heading)

A step without a `title` renders its content inline under the previous heading — useful for continuation content like "Then run:" followed by a code block.

### Step fields

#### `title` (string, optional)

Rendered as a `### heading` in the markdown. Steps without a title don't get a heading — their content flows under the previous step's heading.

#### `text` (string, optional)

Prose rendered before any action. Supports full markdown.

#### `scaffold` (object, optional)

Initializes a project from a Nix flake template.

| Subfield | Type | Description |
|----------|------|-------------|
| `template` | string | The flake template URL (e.g., `github:logos-co/logos-module-builder#with-external-lib`). |
| `code_block` | string | The exact bash content to show in the markdown. If omitted, just the `nix flake init -t <template>` command is shown. |

**Runner behavior:** Executes `nix flake init -t <template>` in the working directory.

**Generator behavior:** Renders `code_block` (or a default `nix flake init` command) inside a ` ```bash ` block.

```yaml
scaffold:
  template: "github:logos-co/logos-module-builder#with-external-lib"
  code_block: |
    # For a module that wraps an external C library:
    mkdir logos-calc-module && cd logos-calc-module
    nix flake init -t github:logos-co/logos-module-builder#with-external-lib

    # Or for a plain module (no external library):
    # nix flake init -t github:logos-co/logos-module-builder
```

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

#### `code_block` (string, optional, on step or scaffold)

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

#### `post_text` (string, optional)

Prose rendered **after** the step's action (file, run, scaffold). Supports full markdown including code blocks, tables, blockquotes.

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

Use the `{release}` placeholder in `run` commands, `code_block`, `scaffold.template`, `scaffold.code_block`, and `file.content`:

```yaml
release: "tutorial-v2"

sections:
  - title: "Set Up"
    steps:
      - scaffold:
          template: "github:logos-co/logos-module-builder{release}#with-external-lib"
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

## Phases

Phases let you run parts of a tutorial selectively:

```bash
# Run only the scaffold and files phases
python3 tools/tutorial_runner.py run spec.yaml --phase scaffold,files

# Run everything
python3 tools/tutorial_runner.py run spec.yaml
```

| Phase | Typical content |
|-------|----------------|
| `scaffold` | Template initialization |
| `files` | Writing source files |
| `build` | Git init, nix build |
| `inspect` | Using `lm` to inspect the module |
| `logoscore` | Testing with the logoscore CLI |
| `basecamp` | UI testing with logos-basecamp (reserved for future use) |

Sections without a `phase` always run.

## Runner behavior

- Creates a fresh temp directory (or uses `--workdir`) — all files, builds, and commands happen there
- Walks sections and steps in order
- Executes `scaffold`, `file`, `run`, `check_file` actions
- Tracks pass/fail/skip counts
- **Stops on first failure** by default (use `--continue-on-fail` to override)
- Prints a summary report at the end
- By default the temp directory is **deleted** when the run finishes

### Working directory

The runner needs a directory to work in. There are three modes:

1. **Default (temp dir, auto-deleted):** A fresh `/tmp/tutorial-test-XXXXX/` is created and removed after the run.
2. **`--keep-workdir`:** Same temp dir, but it's kept after the run so you can inspect the results (built artifacts, installed modules, etc.).
3. **`--workdir <path>`:** Use your own directory. It is never deleted. Useful for re-running specific phases against a previous build or for debugging.

The workdir path is printed at the top of every run:

```
  workdir  : /tmp/tutorial-test-abc123
```

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
# Run a tutorial (all phases)
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --verbose

# Run specific phases
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --phase scaffold,files,build

# Run into a specific directory (kept after run, useful for inspecting results)
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --workdir /tmp/my-tutorial-test --verbose

# Keep the auto-generated temp directory for debugging
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --keep-workdir --verbose

# Re-run just the logoscore phase against a previous build
python3 tools/tutorial_runner.py run tests/tutorial-wrapping-c-library.test.yaml --workdir /tmp/my-tutorial-test --phase logoscore --verbose

# Generate markdown
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml

# Generate to a specific file
python3 tools/tutorial_runner.py generate tests/tutorial-wrapping-c-library.test.yaml -o my-output.md

# Use nix wrapper (ensures python3 + pyyaml are available)
./tools/run-tutorial run tests/tutorial-wrapping-c-library.test.yaml --verbose
```
