#!/usr/bin/env bash
#
# Build the full tutorial chain (Part 1 -> 2 -> 3) into ./outputs/, then strip
# the per-project git repos and build artifacts so what's left is just the
# generated source trees — safe to inspect or check in.
#
# Each outputs/<project>/ is created with its own `git init` by the tutorial
# steps (nix flakes only see git-tracked files), and the build produces nix
# out-link symlinks (lm, logos, pm, result*) plus compiled binaries. None of
# that is portable, so we remove it here.
#
set -euo pipefail

# Run from the repo root regardless of where the script is invoked from.
cd "$(dirname "$0")"

OUTPUT_DIR="./outputs"

# Start from a clean slate. `nix flake init` (the scaffold step) refuses to
# overwrite existing files, so a leftover outputs/ from a previous run makes the
# second run fail. Wipe it first. outputs/ is fully regenerated below, so this
# is safe.
echo "==> Clearing previous ${OUTPUT_DIR}/"
rm -rf "${OUTPUT_DIR}"

echo "==> Running tutorial chain into ${OUTPUT_DIR}/"
python3 tools/tutorial_runner.py run tests/tutorial-cpp-ui-app.test.yaml \
  --verbose \
  --output-dir "${OUTPUT_DIR}/"

echo "==> Generating .md tutorials into ${OUTPUT_DIR}/"
mkdir -p "${OUTPUT_DIR}"
for spec in tests/*.test.yaml; do
  name="$(basename "${spec%.test.yaml}")"
  python3 tools/tutorial_runner.py generate "${spec}" \
    -o "${OUTPUT_DIR}/${name}.md"
done

if [ ! -d "${OUTPUT_DIR}" ]; then
  echo "==> No ${OUTPUT_DIR}/ produced; nothing to clean."
  exit 0
fi

echo "==> Removing nested .git directories"
find "${OUTPUT_DIR}" -type d -name .git -prune -exec rm -rf {} +

echo "==> Removing nix out-link symlinks (lm, logos, pm, result*)"
find "${OUTPUT_DIR}" \( -name lm -o -name logos -o -name pm \
  -o -name 'result' -o -name 'result-*' \) -exec rm -rf {} +

echo "==> Removing build output: modules/ directories"
find "${OUTPUT_DIR}" -type d -name modules -prune -exec rm -rf {} +

echo "==> Removing compiled libraries (*.dylib, *.so)"
find "${OUTPUT_DIR}" -type f \( -name '*.dylib' -o -name '*.so' \) -delete

echo "==> Removing log files (*.log)"
find "${OUTPUT_DIR}" -type f -name '*.log' -delete

# The runner writes these .mjs files on the fly to drive headless UI tests; they
# embed an absolute, machine-specific path to result-mcp, so they must not be
# committed. The reader-facing test (tests/ui-tests.mjs) uses a relative path
# and is unaffected — these are only the runner's scratch copies.
echo "==> Removing runner-generated UI test scaffolds (ui-test.mjs, basecamp-test.mjs)"
find "${OUTPUT_DIR}" -type f \( -name 'ui-test.mjs' -o -name 'basecamp-test.mjs' \) -delete

echo "==> Done. Cleaned tutorial output is in ${OUTPUT_DIR}/"
