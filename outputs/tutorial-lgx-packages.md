# Tutorial: Producing, Merging and Signing LGX Packages

An `.lgx` can hold several platform variants of one package. This walkthrough
produces two packages, merges them, inspects and extracts the result, then
signs it and checks its publisher against a local keyring.

The payloads here are small text fixtures, so you can learn the archive tools
on any machine without compiling for another platform. They are **not loadable
plugins**. For real modules, use the builder outputs described below: `lgx add`
packages files but does not compile code, resolve shared libraries, or make a
Nix-dependent binary portable.

**What you'll build:** A multi-variant package signed with a disposable tutorial key.

**What you'll learn:**

- Produce dev and portable packages with the module builder
- Use create, add, manifest, extract, remove, merge and verify
- Generate a key, sign the final archive and inspect its signature
- Distinguish package integrity, a valid signature and a trusted publisher

## Prerequisites

- Nix with flakes enabled
- A fresh directory: `mkdir logos-lgx-packages && cd logos-lgx-packages`

---

## Produce packages from a real module

In the [C++ module](tutorial-wrapping-c-library.md) or
[Rust module](tutorial-rust-module.md) project, these outputs package your
compiled module, its metadata and canonical LIDL assets:

```bash
nix build .#lgx --out-link result-lgx
nix build .#lgx-portable --out-link result-lgx-portable
```

`result-lgx/` contains a dev package (for example `darwin-arm64-dev`) that
needs the Nix store. `result-lgx-portable/` contains a portable package
(for example `darwin-arm64`) with its runtime libraries bundled. Build on
each target platform and collect those `.lgx` files before merging.
Linux x86-64 variants use `linux-amd64`; Apple Silicon uses `darwin-arm64`.
Windows is cross-built on Linux with
`nix build .#packages.x86_64-windows.lgx-portable`.

Copy packages out of the read-only build output before signing or editing
them, for example `cp result-lgx-portable/*.lgx ./release.lgx` followed by
`chmod u+w release.lgx`. The builder does not supply your publisher key;
signing is a separate step after the final merge.

## Step 1: Create and populate two packages

```bash
nix build 'github:logos-co/logos-package#lgx' --out-link ./lgx
```

```bash
./lgx/bin/lgx --help
```

### 1.1 `linux/payload.txt`

```
Tutorial payload for Linux.
```

### 1.2 `darwin/payload.txt`

```
Tutorial payload for macOS.
```

### 1.3 `assets/README.txt`

```
Shared package asset, stored once outside the variants.
```

```bash
set -eu
./lgx/bin/lgx create tutorial_package
cp tutorial_package.lgx linux.lgx
cp tutorial_package.lgx darwin.lgx
./lgx/bin/lgx add linux.lgx -v linux-amd64 -f ./linux --main payload.txt --assets ./assets
./lgx/bin/lgx add darwin.lgx -v darwin-arm64 -f ./darwin --main payload.txt --assets ./assets

```

`create` takes a **package name**, without `.lgx`, and creates
`<name>.lgx`. Both copies retain the same package identity and version.
For a directory payload, `--main` is relative to that directory. A
single-file payload can omit `--main`. `--assets` adds shared files at
`assets/`, outside the platform variants.

Adding an existing variant **replaces the entire variant**. Use `-y`
only when that replacement is intended. `lgx add --help` lists the
available options, including `--view` for QML entry points.

```bash
./lgx/bin/lgx verify linux.lgx
```

---

## Step 2: Merge, inspect and extract

```bash
./lgx/bin/lgx merge linux.lgx darwin.lgx -o release.lgx
```

All package metadata must agree; variant-specific `main` entries may
differ. Shared asset paths deduplicate only when their bytes match.
Different bytes at the same asset path fail the merge.

Duplicate variants fail by default. `--skip-duplicates` keeps the
**first** copy, so use it only when that selection is intentional.
A merge creates a fresh package and does not preserve input signatures;
sign the merged output.

```bash
./lgx/bin/lgx manifest release.lgx
```

```bash
set -eu
./lgx/bin/lgx manifest release.lgx --json > manifest.json
tar -tzf release.lgx

```

`manifest --json` emits the original manifest bytes for tooling.
`tar -tzf` lists archive entries; there is no `lgx list` command.

```bash
./lgx/bin/lgx extract release.lgx -v linux-amd64 -o extracted
```

```bash
cmp linux/payload.txt extracted/linux-amd64/payload.txt
```

### 2.1 Try an intentional duplicate

```bash
set -eu
if ./lgx/bin/lgx merge linux.lgx linux.lgx -o duplicate.lgx > duplicate.log 2>&1; then
  echo 'ERROR: a duplicate variant was accepted'
  exit 1
fi
cat duplicate.log

```

### 2.2 Remove a variant from a scratch copy

```bash
set -eu
cp release.lgx scratch.lgx
./lgx/bin/lgx remove scratch.lgx -v darwin-arm64 -y
./lgx/bin/lgx verify scratch.lgx

```

---

## Step 3: Sign the final package

These commands use project-local key directories so the exercise has its
own key and trust store. The `.jwk` file contains the private key: keep it
out of source control and never include it in a package. The `.pub` and
`.did` files are public. For a release, use your publisher's retained key
rather than generating a new identity each time.

### 3.1 `.gitignore`

```
keys/
trusted-keys/
*.lgx
*.sig
```

```bash
./lgx/bin/lgx keygen --name tutorial --output-dir ./keys
```

```bash
./lgx/bin/lgx sign release.lgx --key tutorial --keys-dir ./keys --name 'Tutorial Publisher'
```

```bash
set -eu
mkdir -p trusted-keys
./lgx/bin/lgx verify release.lgx --keyring-dir ./trusted-keys

```

Verification checks the content hashes and, when present, the Ed25519
signature over the manifest. **Exit 0 does not require a signature or
a trusted signer**: an unsigned package or a valid untrusted signature
can pass. Check the reported trust status when deciding whether to
install. A signer's display name is self-asserted.

```bash
set -eu
./lgx/bin/lgx keyring add tutorial "$(cat keys/tutorial.did)" --dir ./trusted-keys
./lgx/bin/lgx keyring list --dir ./trusted-keys
./lgx/bin/lgx verify release.lgx --keyring-dir ./trusted-keys

```

In this exercise you generated the key yourself. When trusting someone
else's publisher key, obtain the DID through a channel you already
trust; copying a DID from an unknown archive does not establish trust.

```bash
./lgx/bin/lgx signature release.lgx > manifest.sig
```

```bash
set -eu
./lgx/bin/lgx signature linux.lgx > unsigned.sig
test ! -s unsigned.sig

```

`signature` emits raw `manifest.sig` JSON. An unsigned package produces
an empty stream and exits 0. Editing or replacing content after signing
requires signing the resulting package again.

```bash
./lgx/bin/lgx keyring remove tutorial --dir ./trusted-keys
```

---

## Version helpers and distribution

`lgx semver` supplies version comparison, sorting and range matching; see
`lgx semver --help`. Use `lgpm install --file release.lgx` to install a
**real module package**, matching the runtime's dev or portable variant.
`lgpd` downloads published packages. `lgx publish` is currently a no-op;
it does not upload an archive.

```bash
./lgx/bin/lgx semver satisfies 1.4.0 '^1.2.0'
```

`satisfies` exits 0 for a match and 1 for a non-match; it prints no answer.

## Clean up the tutorial identity

```bash
rm -rf ./keys ./trusted-keys
```

These are the disposable directories created by this exercise. Keep
your real publisher key in your release signing environment.
