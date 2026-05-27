#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Tutorial Test Runner
#
# Replays a tutorial from a YAML test spec: scaffolds, writes files, builds,
# inspects, tests with logoscore, and verifies in basecamp.
#
# Usage:
#   run-tutorial-test.sh <spec.yaml> [OPTIONS]
#
# Options:
#   --phase <phases>    Comma-separated phases to run (default: all)
#                       Available: scaffold,files,build,inspect,logoscore,basecamp
#   --keep-workdir      Don't delete the temp working directory on exit
#   --workdir <path>    Use existing directory instead of creating a fresh one
#                       (skips scaffold+files phases unless explicitly requested)
#   --verbose           Print commands as they execute
#   --basecamp-bin <p>  Path to LogosBasecamp binary (for basecamp phase)
#   --qt-mcp <path>     Path to logos-qt-mcp package (for basecamp phase)
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

SPEC_FILE=""
PHASES=""
KEEP_WORKDIR=false
WORKDIR=""
VERBOSE=false
BASECAMP_BIN=""
QT_MCP_PATH=""
CALL_TIMEOUT=60

# ── Parse Arguments ───────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase)       PHASES="$2"; shift 2 ;;
        --keep-workdir) KEEP_WORKDIR=true; shift ;;
        --workdir)     WORKDIR="$2"; shift 2 ;;
        --verbose)     VERBOSE=true; shift ;;
        --basecamp-bin) BASECAMP_BIN="$2"; shift 2 ;;
        --qt-mcp)      QT_MCP_PATH="$2"; shift 2 ;;
        -*)            echo "Unknown option: $1" >&2; exit 2 ;;
        *)
            if [[ -z "$SPEC_FILE" ]]; then
                SPEC_FILE="$1"
            else
                echo "Unexpected argument: $1" >&2; exit 2
            fi
            shift ;;
    esac
done

if [[ -z "$SPEC_FILE" ]]; then
    echo "Usage: run-tutorial-test.sh <spec.yaml> [OPTIONS]" >&2
    exit 2
fi

if [[ ! -f "$SPEC_FILE" ]]; then
    echo "ERROR: Spec file not found: $SPEC_FILE" >&2
    exit 2
fi

SPEC_FILE="$(cd "$(dirname "$SPEC_FILE")" && pwd)/$(basename "$SPEC_FILE")"

# ── Platform Detection ────────────────────────────────────────────────────────

if [[ "$(uname -s)" == "Darwin" ]]; then
    EXT="dylib"
else
    EXT="so"
fi

# ── Phase Selection ───────────────────────────────────────────────────────────

ALL_PHASES="scaffold,files,build,inspect,logoscore,basecamp"

if [[ -z "$PHASES" ]]; then
    PHASES="$ALL_PHASES"
fi

should_run_phase() {
    echo ",$PHASES," | grep -q ",$1,"
}

# ── Check for yq ─────────────────────────────────────────────────────────────

if ! command -v yq &>/dev/null; then
    echo "ERROR: 'yq' is required but not found in PATH." >&2
    echo "       Install via: nix-shell -p yq-go --run 'yq --version'" >&2
    exit 2
fi

# ── Helper: read YAML field ───────────────────────────────────────────────────

yq_read() {
    yq eval "$1" "$SPEC_FILE"
}

# ── Working Directory Setup ───────────────────────────────────────────────────

if [[ -n "$WORKDIR" ]]; then
    if [[ ! -d "$WORKDIR" ]]; then
        echo "ERROR: --workdir path does not exist: $WORKDIR" >&2
        exit 2
    fi
    CREATED_WORKDIR=false
else
    WORKDIR="$(mktemp -d 2>/dev/null || mktemp -d -t 'tutorial-test')"
    CREATED_WORKDIR=true
fi

cleanup() {
    if [[ "$CREATED_WORKDIR" == "true" ]] && [[ "$KEEP_WORKDIR" == "false" ]]; then
        chmod -R u+w "$WORKDIR" 2>/dev/null || true
        rm -rf "$WORKDIR"
    fi
}
trap cleanup EXIT

# ── Counters ──────────────────────────────────────────────────────────────────

PASS=0
FAIL=0
SKIP=0
TOTAL=0
FAILURES=""

pass() {
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
    printf "  PASS  %s\n" "$1"
}

fail() {
    FAIL=$((FAIL + 1))
    TOTAL=$((TOTAL + 1))
    printf "  FAIL  %s\n" "$1"
    if [[ -n "${2:-}" ]]; then
        printf "        %s\n" "$2"
    fi
    FAILURES="${FAILURES}  FAIL  ${1}\n"
}

skip() {
    SKIP=$((SKIP + 1))
    printf "  SKIP  %s  (%s)\n" "$1" "$2"
}

# ── Platform placeholder replacement ─────────────────────────────────────────

expand_ext() {
    echo "${1//\{ext\}/$EXT}"
}

# Platform-specific shared library flags
if [[ "$(uname -s)" == "Darwin" ]]; then
    SHARED_FLAGS="-dynamiclib"
else
    SHARED_FLAGS="-shared -fPIC"
fi

expand_platform() {
    local s="${1//\{ext\}/$EXT}"
    echo "${s//\{shared_flags\}/$SHARED_FLAGS}"
}

# ── Banner ────────────────────────────────────────────────────────────────────

TUTORIAL_NAME=$(yq_read '.name')
echo "================================================================="
echo " Tutorial Test: $TUTORIAL_NAME"
echo "================================================================="
echo ""
echo "  spec     : $SPEC_FILE"
echo "  workdir  : $WORKDIR"
echo "  platform : $(uname -s) (ext=$EXT)"
echo "  phases   : $PHASES"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0: Scaffold
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "scaffold"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: scaffold"
    echo "-----------------------------------------------------------------"

    TEMPLATE=$(yq_read '.scaffold.template')
    if [[ "$TEMPLATE" == "null" ]] || [[ -z "$TEMPLATE" ]]; then
        skip "scaffold" "no scaffold.template defined"
    else
        cd "$WORKDIR"
        printf "  Running: nix flake init -t %s\n" "$TEMPLATE"
        if nix flake init -t "$TEMPLATE" 2>&1; then
            pass "scaffold from template"
        else
            fail "scaffold from template" "nix flake init failed"
        fi
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: Write Files
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "files"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: files"
    echo "-----------------------------------------------------------------"

    cd "$WORKDIR"
    FILE_COUNT=$(yq_read '.files | length')

    if [[ "$FILE_COUNT" == "0" ]] || [[ "$FILE_COUNT" == "null" ]]; then
        skip "write files" "no files defined"
    else
        for i in $(seq 0 $((FILE_COUNT - 1))); do
            FILE_PATH=$(yq_read ".files[$i].path")
            FILE_PATH=$(expand_ext "$FILE_PATH")
            FILE_ENCODING=$(yq_read ".files[$i].encoding")

            mkdir -p "$(dirname "$FILE_PATH")"

            if [[ "$FILE_ENCODING" == "base64" ]]; then
                yq_read ".files[$i].content" | base64 -d > "$FILE_PATH"
            else
                yq_read ".files[$i].content" > "$FILE_PATH"
            fi

            if [[ -f "$FILE_PATH" ]]; then
                printf "  wrote   %s\n" "$FILE_PATH"
            else
                fail "write $FILE_PATH" "file was not created"
            fi
        done
        pass "wrote $FILE_COUNT files"
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: Build
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "build"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: build"
    echo "-----------------------------------------------------------------"

    cd "$WORKDIR"
    BUILD_COUNT=$(yq_read '.build | length')

    if [[ "$BUILD_COUNT" == "0" ]] || [[ "$BUILD_COUNT" == "null" ]]; then
        skip "build" "no build steps defined"
    else
        for i in $(seq 0 $((BUILD_COUNT - 1))); do
            STEP_NAME=$(yq_read ".build[$i].name")
            STEP_RUN=$(yq_read ".build[$i].run")
            STEP_CHECK=$(yq_read ".build[$i].check_file")

            if [[ "$STEP_RUN" != "null" ]] && [[ -n "$STEP_RUN" ]]; then
                STEP_RUN=$(expand_platform "$STEP_RUN")
                [[ "$VERBOSE" == "true" ]] && printf "        cmd: %s\n" "$STEP_RUN"
                if (cd "$WORKDIR" && eval "$STEP_RUN") 2>&1; then
                    pass "$STEP_NAME"
                else
                    fail "$STEP_NAME" "command failed with exit code $?"
                fi
            elif [[ "$STEP_CHECK" != "null" ]] && [[ -n "$STEP_CHECK" ]]; then
                STEP_CHECK=$(expand_platform "$STEP_CHECK")
                if compgen -G "$WORKDIR/$STEP_CHECK" > /dev/null 2>&1; then
                    pass "$STEP_NAME"
                else
                    fail "$STEP_NAME" "file not found: $STEP_CHECK"
                fi
            else
                skip "$STEP_NAME" "no run or check_file defined"
            fi
        done
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: Inspect
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "inspect"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: inspect"
    echo "-----------------------------------------------------------------"

    cd "$WORKDIR"
    INSPECT_COUNT=$(yq_read '.inspect | length')

    if [[ "$INSPECT_COUNT" == "0" ]] || [[ "$INSPECT_COUNT" == "null" ]]; then
        skip "inspect" "no inspect steps defined"
    else
        for i in $(seq 0 $((INSPECT_COUNT - 1))); do
            STEP_NAME=$(yq_read ".inspect[$i].name")
            STEP_RUN=$(yq_read ".inspect[$i].run")
            STEP_RUN=$(expand_platform "$STEP_RUN")

            [[ "$VERBOSE" == "true" ]] && printf "        cmd: %s\n" "$STEP_RUN"
            output=$(cd "$WORKDIR" && eval "$STEP_RUN" 2>&1) && rc=0 || rc=$?

            if [[ $rc -ne 0 ]]; then
                fail "$STEP_NAME" "command failed with exit code $rc"
                continue
            fi

            EXPECT_COUNT=$(yq_read ".inspect[$i].expect_contains | length")
            all_found=true
            for j in $(seq 0 $((EXPECT_COUNT - 1))); do
                expected=$(yq_read ".inspect[$i].expect_contains[$j]")
                if ! printf '%s' "$output" | grep -qF "$expected"; then
                    fail "$STEP_NAME" "expected '$expected' not found in output"
                    all_found=false
                    break
                fi
            done
            if [[ "$all_found" == "true" ]]; then
                pass "$STEP_NAME"
            fi
        done
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: Logoscore
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "logoscore"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: logoscore"
    echo "-----------------------------------------------------------------"

    cd "$WORKDIR"

    # Check if logoscore section exists in YAML
    LOGOSCORE_SECTION=$(yq_read '.logoscore')
    if [[ "$LOGOSCORE_SECTION" == "null" ]]; then
        skip "logoscore" "no logoscore section in spec"
    elif ! command -v logoscore &>/dev/null; then
        skip "logoscore" "logoscore not in PATH (add workspace scripts to PATH)"
    else
        # Run setup commands
        SETUP_COUNT=$(yq_read '.logoscore.setup | length')
        setup_ok=true
        if [[ "$SETUP_COUNT" != "0" ]] && [[ "$SETUP_COUNT" != "null" ]]; then
            echo "  -- Setup --"
            for i in $(seq 0 $((SETUP_COUNT - 1))); do
                cmd=$(yq_read ".logoscore.setup[$i]")
                cmd=$(expand_platform "$cmd")
                [[ "$VERBOSE" == "true" ]] && printf "        cmd: %s\n" "$cmd"
                if ! (cd "$WORKDIR" && eval "$cmd") 2>&1; then
                    fail "logoscore setup: $cmd" "setup command failed"
                    setup_ok=false
                    break
                fi
            done
            if [[ "$setup_ok" == "true" ]]; then
                printf "  setup completed\n"
            fi
        fi

        if [[ "$setup_ok" == "true" ]]; then
            echo "  -- Tests --"
            TEST_COUNT=$(yq_read '.logoscore.tests | length')
            MODULE_NAME=$(yq_read '.files[] | select(.path == "metadata.json") | .content' | yq eval '.name' -)

            for i in $(seq 0 $((TEST_COUNT - 1))); do
                TEST_NAME=$(yq_read ".logoscore.tests[$i].name")
                TEST_CALL=$(yq_read ".logoscore.tests[$i].call")
                TEST_EXPECT=$(yq_read ".logoscore.tests[$i].expect")

                QUIT_FLAG=""
                if logoscore --help 2>&1 | grep -q "quit-on-finish"; then
                    QUIT_FLAG="--quit-on-finish"
                fi

                cmd="timeout $CALL_TIMEOUT logoscore $QUIT_FLAG -m ./modules -l $MODULE_NAME -c \"$TEST_CALL\""
                [[ "$VERBOSE" == "true" ]] && printf "        cmd: %s\n" "$cmd"

                output=$(cd "$WORKDIR" && eval "$cmd" 2>&1) && rc=0 || rc=$?

                if [[ $rc -ne 0 ]]; then
                    fail "$TEST_NAME" "logoscore exit code $rc"
                    [[ "$VERBOSE" == "true" ]] && printf "        output: %s\n" "$output"
                elif printf '%s' "$output" | grep -qF "$TEST_EXPECT"; then
                    pass "$TEST_NAME"
                else
                    fail "$TEST_NAME" "expected '$TEST_EXPECT' in output, got: $output"
                fi
            done
        fi
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: Basecamp UI
# ═══════════════════════════════════════════════════════════════════════════════

if should_run_phase "basecamp"; then
    echo "-----------------------------------------------------------------"
    echo " Phase: basecamp"
    echo "-----------------------------------------------------------------"

    cd "$WORKDIR"

    # Check prerequisites
    if [[ -z "$BASECAMP_BIN" ]]; then
        skip "basecamp" "no --basecamp-bin provided"
    elif [[ ! -x "$BASECAMP_BIN" ]]; then
        skip "basecamp" "basecamp binary not found or not executable: $BASECAMP_BIN"
    elif [[ -z "$QT_MCP_PATH" ]] && [[ -z "${LOGOS_QT_MCP:-}" ]]; then
        skip "basecamp" "no --qt-mcp or LOGOS_QT_MCP provided"
    else
        QT_MCP="${QT_MCP_PATH:-${LOGOS_QT_MCP}}"

        # Generate .mjs test file from YAML basecamp declarations
        MJS_FILE="$(mktemp "${WORKDIR}/basecamp-test-XXXXXX.mjs")"

        {
            echo 'import { resolve } from "node:path";'
            echo "const qtMcpRoot = \"$QT_MCP\";"
            echo 'const { test, run } = await import(resolve(qtMcpRoot, "test-framework/framework.mjs"));'
            echo ''
            echo "test(\"$TUTORIAL_NAME: basecamp UI verification\", async (app) => {"

            BC_TEST_COUNT=$(yq_read '.basecamp.tests | length')
            for i in $(seq 0 $((BC_TEST_COUNT - 1))); do
                ACTION=$(yq_read ".basecamp.tests[$i].action")
                TARGET=$(yq_read ".basecamp.tests[$i].target")
                TEXTS=$(yq_read ".basecamp.tests[$i].texts")
                TIMEOUT=$(yq_read ".basecamp.tests[$i].timeout")
                NAME=$(yq_read ".basecamp.tests[$i].name")

                case "$ACTION" in
                    click)
                        echo "  await app.click(\"$TARGET\", { exact: true });"
                        ;;
                    expect_texts)
                        TEXTS_JS=$(yq_read ".basecamp.tests[$i].texts | @json")
                        echo "  await app.expectTexts($TEXTS_JS);"
                        ;;
                    wait_for)
                        TEXTS_JS=$(yq_read ".basecamp.tests[$i].texts | @json")
                        TO="${TIMEOUT:-10000}"
                        echo "  await app.waitFor("
                        echo "    async () => { await app.expectTexts($TEXTS_JS); },"
                        echo "    { timeout: $TO, interval: 500, description: \"$NAME\" }"
                        echo "  );"
                        ;;
                    set_text)
                        FIND_PROP=$(yq_read ".basecamp.tests[$i].find_by")
                        FIND_VAL=$(yq_read ".basecamp.tests[$i].find_value")
                        SET_VAL=$(yq_read ".basecamp.tests[$i].value")
                        echo "  {"
                        echo "    const found = await app.inspector.send(\"findByProperty\", { property: \"$FIND_PROP\", value: \"$FIND_VAL\" });"
                        echo "    if (!found.matches || found.matches.length === 0) throw new Error('set_text: element not found with $FIND_PROP=$FIND_VAL');"
                        echo "    await app.inspector.send(\"setProperty\", { objectId: found.matches[0].id, property: \"text\", value: \"$SET_VAL\" });"
                        echo "  }"
                        ;;
                    sleep)
                        SLEEP_MS=$(yq_read ".basecamp.tests[$i].ms")
                        echo "  await new Promise(r => setTimeout(r, ${SLEEP_MS:-1000}));"
                        ;;
                esac
            done

            echo '});'
            echo ''
            echo 'run();'
        } > "$MJS_FILE"

        [[ "$VERBOSE" == "true" ]] && echo "  Generated test file: $MJS_FILE"

        # Set up a clean user directory for basecamp
        BASECAMP_USER_DIR="$(mktemp -d "${WORKDIR}/basecamp-data-XXXXXX")"
        export LOGOS_USER_DIR="$BASECAMP_USER_DIR"
        export QT_QPA_PLATFORM=offscreen
        export QT_FORCE_STDERR_LOGGING=1
        export QT_LOGGING_RULES="qt.*.debug=false;default.debug=true"
        export LOGOS_QT_MCP="$QT_MCP"

        # Install core dependencies first (other modules this plugin depends on)
        SCRIPT_DIR="$(cd "$(dirname "$SPEC_FILE")" && pwd)"
        CORE_DEPS_COUNT=$(yq_read '.basecamp.core_deps | length')
        if [[ "$CORE_DEPS_COUNT" != "0" && "$CORE_DEPS_COUNT" != "null" ]]; then
            mkdir -p "$BASECAMP_USER_DIR/modules"
            for i in $(seq 0 $((CORE_DEPS_COUNT - 1))); do
                DEP_PATH=$(yq_read ".basecamp.core_deps[$i]")
                DEP_FULL_PATH="$SCRIPT_DIR/$DEP_PATH"
                if [[ -d "$DEP_FULL_PATH" ]]; then
                    echo "  Installing core dependency: $DEP_PATH"
                    DEP_INSTALL="$(mktemp -d)"
                    if (cd "$DEP_FULL_PATH" && nix build '.#install' -o "$DEP_INSTALL/result" 2>&1); then
                        cp -r "$DEP_INSTALL"/result/modules/* "$BASECAMP_USER_DIR/modules/" 2>/dev/null || true
                        [[ "$VERBOSE" == "true" ]] && echo "    Installed to $BASECAMP_USER_DIR/modules/"
                    else
                        echo "  WARNING: Failed to build core dep: $DEP_PATH"
                    fi
                    rm -rf "$DEP_INSTALL"
                else
                    echo "  WARNING: core_dep path not found: $DEP_FULL_PATH"
                fi
            done
        fi

        # Install the module into basecamp's directory using `nix build .#install`
        INSTALL_AS=$(yq_read '.basecamp.install_as')
        if [[ "$INSTALL_AS" != "null" ]]; then
            echo "  Building install package..."
            if (cd "$WORKDIR" && nix build '.#install' -o result-install 2>&1); then
                if [[ "$INSTALL_AS" == "core" ]]; then
                    mkdir -p "$BASECAMP_USER_DIR/modules"
                    cp -r "$WORKDIR"/result-install/modules/* "$BASECAMP_USER_DIR/modules/"
                    [[ "$VERBOSE" == "true" ]] && echo "  Installed core module(s) to: $BASECAMP_USER_DIR/modules/"
                    [[ "$VERBOSE" == "true" ]] && ls "$BASECAMP_USER_DIR/modules/"
                elif [[ "$INSTALL_AS" == "ui" ]]; then
                    mkdir -p "$BASECAMP_USER_DIR/plugins"
                    cp -r "$WORKDIR"/result-install/plugins/* "$BASECAMP_USER_DIR/plugins/" 2>/dev/null || \
                    cp -r "$WORKDIR"/result-install/modules/* "$BASECAMP_USER_DIR/plugins/" 2>/dev/null || true
                    [[ "$VERBOSE" == "true" ]] && echo "  Installed UI plugin(s) to: $BASECAMP_USER_DIR/plugins/"
                    [[ "$VERBOSE" == "true" ]] && ls "$BASECAMP_USER_DIR/plugins/"
                fi
            else
                fail "basecamp install" "nix build '.#install' failed"
            fi
        fi

        [[ "$VERBOSE" == "true" ]] && echo "  LOGOS_USER_DIR=$BASECAMP_USER_DIR"
        [[ "$VERBOSE" == "true" ]] && echo "  QT_QPA_PLATFORM=offscreen"

        # Run the generated test (--ci launches basecamp, runs tests, kills it)
        if node "$MJS_FILE" --ci "$BASECAMP_BIN" --verbose 2>&1; then
            pass "basecamp UI tests"
        else
            fail "basecamp UI tests" "test runner exited with non-zero"
        fi

        rm -f "$MJS_FILE"
    fi
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════

echo "================================================================="
echo " Results: $PASS passed, $FAIL failed, $SKIP skipped (of $TOTAL run)"
echo "================================================================="

if [[ "$KEEP_WORKDIR" == "true" ]] || [[ "$CREATED_WORKDIR" == "false" ]]; then
    echo ""
    echo "  workdir: $WORKDIR"
fi

if [[ $FAIL -gt 0 ]]; then
    echo ""
    echo "Failures:"
    printf "%b" "$FAILURES"
    echo ""
    exit 1
fi

echo ""
echo "All tests passed."
exit 0
