#!/usr/bin/env bash
#
# Build the full tutorial chain (Part 1 -> 2 -> 3) into ./outputs/, generate the
# .md tutorials, then strip the per-project git repos and build artifacts so
# what's left is just the generated source trees — safe to inspect or check in.
#
# The runner and the artifact-cleaning logic live in the shared `doctest` CLI
# (https://github.com/logos-co/logos-doctest), invoked directly via its flake.
# `doctest clean` removes the per-project .git/ dirs (each tutorial git init's
# its project), the nix out-link symlinks (lm, logos, pm, result*), build output
# (modules/), compiled libraries (*.so/*.dylib), logs, machine-specific
# flake.lock files, and the runner's scratch *.mjs UI-test scaffolds.
#
# To run against a local logos-doctest checkout instead of the published flake,
# set DOCTEST, e.g.:  DOCTEST="nix run path:../logos-doctest --" ./run.sh
#
# Usage:
#   ./run.sh [--release TAG] [extra doctest args...]
#
# --release TAG pins every {release} placeholder in the specs' GitHub URLs to
# that git tag (passed to both `run` and `generate` so the executed commands and
# the generated Markdown agree). Any further args are forwarded verbatim to the
# `run` and `generate` invocations, so e.g. `--release-for REPO=REF` also works:
#   ./run.sh --release tutorial-v3
#   ./run.sh --release tutorial-v3 --release-for logos-basecamp=main
#
set -euo pipefail

# Run from the repo root regardless of where the script is invoked from.
cd "$(dirname "$0")"

# Collect pass-through args for run/generate (--release, --release-for, etc.).
DOCTEST_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --release)
      [ "$#" -ge 2 ] || { echo "error: --release requires a TAG argument" >&2; exit 2; }
      DOCTEST_ARGS+=("--release" "$2")
      shift 2
      ;;
    --release=*)
      DOCTEST_ARGS+=("--release" "${1#*=}")
      shift
      ;;
    *)
      # Forward anything else verbatim (e.g. --release-for REPO=REF).
      DOCTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

# The doctest CLI. Override by exporting DOCTEST (space-separated command).
read -r -a DOCTEST <<< "${DOCTEST:-nix run github:logos-co/logos-doctest --}"
OUTPUT_DIR="./outputs"

# Start from a clean slate. `nix flake init` (the scaffold step) refuses to
# overwrite existing files, so a leftover outputs/ from a previous run makes the
# second run fail. Wipe it first. outputs/ is fully regenerated below, so this
# is safe.
echo "==> Clearing previous ${OUTPUT_DIR}/"
rm -rf "${OUTPUT_DIR}"

echo "==> Running tutorial chain into ${OUTPUT_DIR}/"
"${DOCTEST[@]}" run tests/tutorial-cpp-ui-app.test.yaml \
  --verbose \
  --output-dir "${OUTPUT_DIR}/" \
  ${DOCTEST_ARGS[@]+"${DOCTEST_ARGS[@]}"}

echo "==> Generating .md tutorials into ${OUTPUT_DIR}/"
mkdir -p "${OUTPUT_DIR}"
for spec in tests/*.test.yaml; do
  name="$(basename "${spec%.test.yaml}")"
  "${DOCTEST[@]}" generate "${spec}" \
    -o "${OUTPUT_DIR}/${name}.md" \
    ${DOCTEST_ARGS[@]+"${DOCTEST_ARGS[@]}"}
done

if [ ! -d "${OUTPUT_DIR}" ]; then
  echo "==> No ${OUTPUT_DIR}/ produced; nothing to clean."
  exit 0
fi

echo "==> Cleaning build artifacts from ${OUTPUT_DIR}/"
"${DOCTEST[@]}" clean "${OUTPUT_DIR}" --verbose

echo "==> Done. Cleaned tutorial output is in ${OUTPUT_DIR}/"
