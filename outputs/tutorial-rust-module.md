# Tutorial: Writing a Module in Rust

Every tutorial so far wrote C++. This one writes **Rust**, and builds `calc_rust` — a core module that depends on `calc_module` from [Part 1](tutorial-wrapping-c-library.md) and calls it through the same generated, type-safe wrappers a C++ module gets.

The point is not that Rust is supported. It is that **the language is not part of the contract**. A module publishes a LIDL contract; consumers generate a typed client from it. Which language produced the contract, and which language consumes it, never comes up. `calc_rust` calls a C++ module here, and nothing in the Rust source says so.

Authoring is **Rust-first**: you write a `trait`, and the builder derives the `.lidl` from it. There is no `build.rs`, no committed contract to keep in sync with the code, and no SDK version to pin — the builder stages the same `logos-rust-sdk` its code generator came from, so generator and runtime cannot drift.

**What you'll build:** A `calc_rust` core module, written entirely in Rust, that:

- declares its API as a plain Rust `trait` — the builder derives the contract from it
- calls `calc_module` (a **C++** module) through the typed `modules().calc_module` client
- takes an `Option<String>` parameter, which is a real LIDL type (`?tstr`), not a sentinel
- emits a typed `summed` event from a companion `CalcRustModuleEvents` trait

Driven entirely from `logoscore` on the command line — no UI.

**What you'll learn:**

- How to scaffold a Rust module with `nix flake init -t ...#rust`
- How Rust-first authoring works — the `trait` is the contract, and `nix build .#lidl` shows you what was derived from it
- How `codegen.rust` in `metadata.json` points the builder at your crate and trait
- How a Rust module calls another module, including one written in C++, with `modules().<dep>`
- How typed events are declared in Rust (the `<Trait>Events` companion trait) and emitted with `emit_<name>`
- How `Option<T>` crosses the wire as a two-state optional rather than an empty string

## Prerequisites

- Completed [Part 1](tutorial-wrapping-c-library.md) — you have a working `calc_module` whose shared library is built (`libcalc.so`/`.dylib` in `logos-calc-module/lib/`). No other part is required.
- Nix with flakes enabled
- Basic familiarity with Rust. You do **not** need to install a Rust toolchain — the builder supplies one.

---

## Step 1: Scaffold the Rust Module

Create a new directory and initialise it from the **Rust** template:

`mkdir logos-calc-rust-module && cd logos-calc-rust-module`

### 1.1 Create the project from the Rust template

```bash
nix flake init -t github:logos-co/logos-module-builder#rust
```

Two Rust templates exist: `#rust` (this one) and `#rust-with-external-lib`, which is the Rust counterpart to Part 1 — a Rust module linking a C library.

### 1.2 Look at what you got

```bash
find . -type f -not -path './.git/*' | sort
```

```
./.gitignore
./CMakeLists.txt
./flake.nix
./metadata.json
./rust-lib/Cargo.lock
./rust-lib/Cargo.toml
./rust-lib/src/lib.rs
```

`flake.nix` and `CMakeLists.txt` are **identical to a C++ module's** — the builder compiles the crate to a staticlib and links it into the plugin alongside the generated glue, so there is nothing Rust-specific for either file to say. All of your code lives in `rust-lib/`.

Note `Cargo.lock` is **committed**. The crate depends on the SDK by path, at a directory the builder only stages during a build, so the lock cannot be resolved from a clean checkout — shipping it is what makes `nix build` work as the first command you run.

---

## Step 2: Configure the Module

Three files name the module and point the builder at the crate.

### 2.1 metadata.json

`interface: "cdylib"` is the Rust (and Nim) authoring path. `codegen.rust` tells the builder which crate to compile and — because we are authoring Rust-first — which `trait` to derive the contract from:

```json
{
  "name": "calc_rust",
  "display_name": "Rust Calculator",
  "version": "1.0.0",
  "type": "core",
  "interface": "cdylib",
  "category": "example",
  "description": "Statistics over calc_module, written in Rust",
  "main": "calc_rust_plugin",
  "dependencies": ["calc_module"],

  "codegen": {
    "rust": { "crate": "rust-lib", "trait": "CalcRustModule" }
  },

  "nix": {
    "packages": { "build": [], "runtime": [] },
    "external_libraries": [],
    "cmake": { "find_packages": [], "extra_sources": [], "extra_include_dirs": [], "extra_link_libraries": [] }
  }
}
```

| Field | Meaning |
|---|---|
| `interface: "cdylib"` | the Rust authoring path — your code compiles to a static library the generated glue calls through a C ABI |
| `codegen.rust.crate` | the crate directory, relative to the project root |
| `codegen.rust.trait` | **switches on Rust-first mode**: the `.lidl` is derived from this trait. Omit it and the builder expects a committed `codegen.lidl` instead |
| `codegen.rust.source` | which file holds the trait. Defaults to `src/lib.rs`, which is where ours is |
| `dependencies` | exactly as in any other module — `calc_module` here, whose language is not our concern |

> The trait **name is not free**. The generated scaffold looks for the module `name` in PascalCase with `Module` appended unless it already ends in it: `calc_rust` → `CalcRustModule`.

### 2.2 Name the crate

The template's crate is still called `minimal_rust`. Rename it in both files — the lock records the root package too, and editing both keeps them consistent without re-resolving:

```bash
sed -i 's/^name = "minimal_rust"$/name = "calc_rust"/' rust-lib/Cargo.toml rust-lib/Cargo.lock
```

The resulting `rust-lib/Cargo.toml`:

```toml
[package]
name = "calc_rust"
version = "1.0.0"
edition = "2021"

# Standalone crate — the empty table keeps cargo from adopting any
# workspace it finds in a parent directory.
[workspace]

[lib]
crate-type = ["staticlib"]

[dependencies]
serde_json = "1"
# Staged by the builder from the same logos-rust-sdk revision its code
# generator comes from, so there is no generator/runtime skew to manage.
logos-rust-sdk = { path = "../logos-rust-sdk-src" }
```

You never add `logos-rust-sdk` yourself, and there is no version to choose: it is a path dependency the builder materialises.

### 2.3 Declare the dependency as a flake input

Add `calc_module` to `flake.nix`. The **input attribute name must equal the dependency name** in `metadata.json` — that is how the builder resolves it:

```nix
{
  description = "calc_rust - a Logos module written in Rust";

  # Identical to a C++ module's inputs: the builder provides both the code
  # generator and the logos-rust-sdk source the crate links, so there is no
  # logos-rust-sdk input to keep in sync here.
  inputs = {
    logos-module-builder.url = "github:logos-co/logos-module-builder";
    calc_module.url = "path:/path/to/your/calc_module";
  };

  outputs = inputs@{ logos-module-builder, ... }:
    logos-module-builder.lib.mkLogosModule {
      src = ./.;
      configFile = ./metadata.json;
      flakeInputs = inputs;
    };
}
```

The placeholder URL is replaced in Step 4 by `nix flake update --override-input`, which resolves your Part 1 checkout to an absolute path and records it in `flake.lock`.

---

## Step 3: Write the Module

Everything is one file. The trait declares the contract; the `impl` is the module.

### 3.1 rust-lib/src/lib.rs

```
//! calc_rust — statistics over `calc_module`, written in Rust.
//!
//! Rust-FIRST authoring: the trait below IS the contract. The builder derives
//! the `.lidl` from it, generates the C-ABI scaffold around it, and compiles
//! this crate to a staticlib.

/// The trait name is derived from `name` in metadata.json: PascalCase, plus
/// `Module` unless it already ends in it — `calc_rust` -> `CalcRustModule`.
pub trait CalcRustModule: Send + 'static {
    /// Sums a JSON array of integers by folding it through `calc_module.add`,
    /// so every addition crosses the language boundary.
    fn sum_all(&mut self, values_json: String) -> i64;

    /// Reports the version of the C library `calc_module` wraps.
    fn backend_version(&mut self) -> String;

    /// Describes the last sum. An omitted `label` is the empty option, not an
    /// empty string — `Option<T>` is a real LIDL type, spelled `?tstr`.
    fn describe(&mut self, label: Option<String>) -> String;

    fn on_context_ready(&mut self, _ctx: &RustModuleContext) {}
}

/// Typed events — the Rust analog of the C++ `logos_events:` section. Each
/// method becomes an `emit_<name>` free function.
pub trait CalcRustModuleEvents {
    fn summed(&self, total: i64, terms: i64);
}

// The builder injects the generated scaffold here — `install`,
// `RustModuleContext`, `context()`, `modules()` and the `emit_*` emitters.
include!(concat!(env!("CARGO_MANIFEST_DIR"), "/generated/provider_gen.rs"));

#[derive(Default)]
struct CalcRust {
    last_total: i64,
    last_terms: i64,
}

impl CalcRustModule for CalcRust {
    fn sum_all(&mut self, values_json: String) -> i64 {
        let values: Vec<i64> = serde_json::from_str(&values_json).unwrap_or_default();

        // modules().calc_module is the typed client the builder generated from
        // calc_module's published contract. It is a C++ module; nothing here
        // says so.
        let mut total = 0i64;
        for v in &values {
            total = modules().calc_module.add(total, *v).unwrap_or(total);
        }

        self.last_total = total;
        self.last_terms = values.len() as i64;
        emit_summed(total, self.last_terms);
        total
    }

    fn backend_version(&mut self) -> String {
        modules()
            .calc_module
            .lib_version()
            .unwrap_or_else(|e| format!("unavailable: {e:?}"))
    }

    fn describe(&mut self, label: Option<String>) -> String {
        let label = label.unwrap_or_else(|| "last sum".to_string());
        format!("{}: {} over {} terms", label, self.last_total, self.last_terms)
    }
}

#[no_mangle]
pub extern "Rust" fn logos_module_install() {
    install::<CalcRust>();
}
```

Four things are worth naming.

**The trait is the contract.** Its methods become the module's API and its `///` comments become the contract's descriptions — the same text `lm` and `logoscore module-info` show. `on_context_ready` is defaulted, so it is framework plumbing rather than part of the API.

**`modules().calc_module` is generated from a published contract, not from a build.** Every call returns `Result<T, LogosError>`, because a call to another module can fail in ways a local function cannot. `calc_module`'s C++ `libVersion()` is `lib_version()` here — method names are converted to Rust's convention on the way in.

**`Option<String>` is a real optional.** It becomes `?tstr` on the wire — two states, present or absent, rather than a string that is empty by convention. A caller that omits the argument and one that passes `""` are distinguishable.

**`include!` replaces `build.rs`.** The builder writes `generated/provider_gen.rs` before compiling, so the scaffold — `install`, `RustModuleContext`, `context()`, `modules()`, `emit_summed` — is a plain source file you can read.

---

## Step 4: Build the Module

### 4.1 Track the files

Nix only sees files tracked by git:

```bash
git init && git add -A
```

### 4.2 Lock the dependency and build

Point `calc_module` at your Part 1 checkout. `--override-input` resolves the relative path to an absolute one and records it in `flake.lock`, replacing the placeholder:

```bash
nix flake update --override-input calc_module path:../logos-calc-module
```

```bash
git add flake.lock
```

Now build. This compiles the crate, derives the contract from your trait, generates the scaffold and the typed `modules().calc_module` client, and links the lot into a plugin:

```bash
nix build
```

### 4.3 Check the output

```bash
ls -la result/lib/
```

```
calc_rust_plugin.so     # Linux
calc_rust_plugin.dylib  # macOS
```

A Rust module produces the same artifact a C++ one does. Nothing downstream — `lm`, `lgx`, `lgpm`, `logoscore`, basecamp — can tell the difference, which is the point.

---

## Step 5: Read the Contract the Builder Derived

In Rust-first authoring you never write the contract by hand, so it is worth looking at what your trait produced. Every module publishes it as a cheap flake output:

### 5.1 Build the LIDL output

```bash
nix build .#lidl --out-link result-lidl
```

```bash
cat result-lidl/*.lidl
```

```
module calc_rust {
  version "1.0.0"
  depends []

  method sum_all(values_json: tstr) -> int description "Sums a JSON array of integers by folding it through `calc_module.add`,\nso every addition crosses the language boundary."
  method backend_version() -> tstr description "Reports the version of the C library `calc_module` wraps."
  method describe(label: ? tstr) -> tstr description "Describes the last sum. An omitted `label` is the empty option, not an\nempty string — `Option<T>` is a real LIDL type, spelled `?tstr`."

  event summed(total: int, terms: int)
}
```

Your `i64` became `int`, your `String` became `tstr`, and your `Option<String>` became **`? tstr`** — the optional slot. The `///` comments came across as `description`, which is why they are worth writing.

This file is what a *consumer* generates its client from. It is also why building `calc_rust` did not build `calc_module`: the builder read `calc_module`'s published contract, not its source.

---

## Step 6: Inspect the Module

`lm` reads the compiled plugin. It has no idea the module is Rust:

### 6.1 Build lm

```bash
nix build 'github:logos-co/logos-module#lm' --out-link ./lm
```

### 6.2 View metadata

```bash
./lm/bin/lm metadata result/lib/calc_rust_plugin.so     # Linux
./lm/bin/lm metadata result/lib/calc_rust_plugin.dylib  # macOS
```

```
Plugin Metadata:
================
Name:         calc_rust
Display name: Rust Calculator
Version:      1.0.0
Description:  Statistics over calc_module, written in Rust
Type:         core
Protocol:     0.9.0
Dependencies: calc_module
```

`Protocol` is stamped in by the build, not authored — it records which logos-protocol the plugin was generated against.

### 6.3 View methods

```bash
./lm/bin/lm methods result/lib/calc_rust_plugin.so     # Linux
./lm/bin/lm methods result/lib/calc_rust_plugin.dylib  # macOS
```

Two details in this listing. `describe` takes a `QVariant` rather than a `QString`, which is how the optional survives the Qt boundary — a `QVariant` can be empty, a `QString` can only be `""`. And `name()` / `version()` are there without appearing in your trait: the generator injects them, because every module must answer them and no author should have to write them.

---

## Step 7: Run it with `logoscore`

Now run `calc_rust` and its `calc_module` dependency together. We use the `logoscore` **daemon** (`-D`) so both modules stay alive between commands, which is what lets an event subscription registered by one command still be listening when a later one triggers it.

### 7.1 Build logoscore and the package manager

```bash
nix build 'github:logos-co/logos-logoscore-cli' --out-link ./logos
```

```bash
nix build 'github:logos-co/logos-package-manager' --out-link ./pm
```

### 7.2 Install both modules

Package each module as a `.lgx` and install it into a `modules/` directory `logoscore` can scan. `calc_rust` comes from this project, `calc_module` from your Part 1 checkout:

```bash
nix build '.#lgx' --out-link result-rust-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-rust-lgx/*.lgx
```

```bash
nix build 'path:../logos-calc-module#lgx' --out-link result-calc-lgx
./pm/bin/lgpm --modules-dir ./modules install --file result-calc-lgx/*.lgx
```

### 7.3 Start the daemon and load both modules

```bash
./logos/bin/logoscore -D -m ./modules &
```

```bash
# Wait until the daemon is accepting commands
until ./logos/bin/logoscore status >/dev/null 2>&1; do sleep 0.3; done
```

```bash
./logos/bin/logoscore load-module calc_module
```

```bash
./logos/bin/logoscore load-module calc_rust
```

### 7.4 Call across the language boundary

`sum_all` folds the array through `calc_module.add` — four Rust-to-C++ calls for four terms:

```bash
./logos/bin/logoscore call calc_rust sum_all '[3,5,10,20]'
```

```json
{"method":"sum_all","module":"calc_rust","result":38,"status":"ok"}
```

`backend_version` reaches further still — through `calc_module` into the C library it wraps, so the string crosses two language boundaries on the way back:

```bash
./logos/bin/logoscore call calc_rust backend_version
```

```json
{"method":"backend_version","module":"calc_rust","result":"1.0.0","status":"ok"}
```

### 7.5 Pass — and omit — the optional

`describe` takes `Option<String>`. Omit it and the module sees `None`:

```bash
./logos/bin/logoscore call calc_rust describe
```

```json
{"method":"describe","module":"calc_rust","result":"last sum: 38 over 4 terms","status":"ok"}
```

Supply it and the module sees `Some("totals")`:

```bash
./logos/bin/logoscore call calc_rust describe totals
```

```json
{"method":"describe","module":"calc_rust","result":"totals: 38 over 4 terms","status":"ok"}
```

Two calls, two different values, one signature. Nothing here is a sentinel.

### 7.6 Watch the typed event

`sum_all` calls `emit_summed(...)`, which routes the typed payload to every subscriber. `logoscore watch` is one:

```bash
# In one terminal
./logos/bin/logoscore watch calc_rust --event summed

# In another
./logos/bin/logoscore call calc_rust sum_all '[7,8,9]'
```

The watcher prints:

```json
{"data":{"arg0":24,"arg1":3},"event":"summed","module":"calc_rust","timestamp":"..."}
```

`arg0` is the total and `arg1` the number of terms, in the order the `CalcRustModuleEvents` trait declares them.

### 7.7 Stop the daemon

```bash
./logos/bin/logoscore stop
```

---

## Recap

| What | Where it lives |
|---|---|
| The contract | the `CalcRustModule` trait — the builder derives the `.lidl` from it |
| Typed events | the `CalcRustModuleEvents` companion trait; emitted with `emit_<name>` |
| Calling another module | `modules().<dep>.<method>()`, returning `Result<T, LogosError>` |
| Optional arguments | `Option<T>`, which is `?T` on the wire |
| The generated scaffold | `rust-lib/generated/provider_gen.rs`, pulled in with `include!` |
| The SDK | a path dependency the builder stages — no version to pin, no `build.rs` |

Two things generalise beyond this tutorial.

**The contract is the boundary, not the language.** `calc_rust` consumed a C++ module without knowing it, and a C++ consumer would consume `calc_rust` the same way — the [Composing Modules](tutorial-composing-modules.md) tutorial's `calc_aggregator` needs no change to call this one beyond swapping the dependency name.

**Building a consumer does not build its dependencies.** The builder read `calc_module`'s published `.lidl`. That is why a Rust module can depend on a C++ module without a C++ toolchain entering its build, and why adding a dependency does not inherit its compile time.

Next: [Composing Modules](tutorial-composing-modules.md) does the same job from C++ and covers the module context, persistence and async calls; [Dependency Interfaces](tutorial-interface-dependencies.md) removes the concrete module name from the picture entirely.
