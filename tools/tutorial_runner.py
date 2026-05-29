#!/usr/bin/env python3
"""
Tutorial Runner & Markdown Generator

Executes YAML tutorial specs (write files, run commands, build, inspect, test)
and generates .md documentation from them.

Usage:
    tutorial_runner.py run <spec.yaml> [OPTIONS]
    tutorial_runner.py generate <spec.yaml> [-o output.md]

Run options:
    --output-dir <dir>    Run into <dir> and keep it (created if missing, never
                          deleted). Chained tutorials write each project to
                          <dir>/<project_name>/; standalone specs use <dir> directly.
    --keep-workdir        Don't delete the temp working directory on exit
    --workdir <path>      Use existing directory instead of creating a fresh one
                          (standalone only; requires: chains are not run)
    --report <path>       Write a two-column HTML report (rendered tutorial +
                          the commands actually run and their output) to <path>
    --tui                 Run in an interactive two-column TUI (needs 'rich')
    --iterative           With --tui, advance one step per keypress (arrow/space)
    --verbose             Print commands as they execute
    --basecamp-bin <path> Path to LogosBasecamp binary (for basecamp sections)
    --qt-mcp <path>       Path to logos-qt-mcp package (for basecamp/ui_test sections)
    --call-timeout <sec>  Timeout for logoscore calls (default: 60)
    --continue-on-fail    Don't stop at the first failure (default: stop)

Generate options:
    -o <path>             Output file (default: uses spec's 'output' field)
"""

import argparse
import base64
import glob
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap

import yaml

# ── Platform Detection ────────────────────────────────────────────────────────

IS_MACOS = platform.system() == "Darwin"
LIB_EXT = "dylib" if IS_MACOS else "so"
SHARED_FLAGS = "-dynamiclib" if IS_MACOS else "-shared -fPIC"


# ── Colors ────────────────────────────────────────────────────────────────────

USE_COLOR = sys.stdout.isatty()


def _c(code, text):
    if USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


def green(t):
    return _c("32", t)


def red(t):
    return _c("31", t)


def yellow(t):
    return _c("33", t)


def bold(t):
    return _c("1", t)


def dim(t):
    return _c("2", t)


# ── Result Tracking ──────────────────────────────────────────────────────────

class StopEarly(Exception):
    """Raised when fail-fast is enabled and a test fails."""


class Results:
    def __init__(self, fail_fast=True):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []
        self.fail_fast = fail_fast

    @property
    def total(self):
        return self.passed + self.failed + self.skipped

    def pass_(self, name):
        self.passed += 1
        print(f"  {green('PASS')}  {name}")

    def fail(self, name, reason=""):
        self.failed += 1
        self.failures.append((name, reason))
        print(f"  {red('FAIL')}  {name}")
        if reason:
            print(f"        {dim(reason)}")
        if self.fail_fast:
            raise StopEarly()

    def skip(self, name, reason=""):
        self.skipped += 1
        print(f"  {yellow('SKIP')}  {name}  ({reason})")

    def summary(self):
        print()
        print("=" * 65)
        print(f" Results: {self.passed} passed, {self.failed} failed, "
              f"{self.skipped} skipped (of {self.total} run)")
        print("=" * 65)

        if self.failures:
            print()
            print("Failures:")
            for name, reason in self.failures:
                print(f"  {red('FAIL')}  {name}")
                if reason:
                    print(f"        {reason}")
        print()
        return self.failed == 0


# ── Execution capture for --report ────────────────────────────────────────────

# When `run --report <path>` is active this holds a ReportCollector; otherwise
# it stays None and the handlers' recording calls are cheap no-ops. It's a
# module global (like RELEASE_TAG) so the existing handler signatures don't all
# have to grow a parameter.
_REPORT = None


class ReportCollector:
    """Accumulates what each step actually executed, keyed by the identity of
    the step dict so the report builder (which walks the same spec objects) can
    line up real execution against rendered markdown. Spec objects are held in
    `specs` so their step dicts stay alive and their ids stay stable/unique."""

    def __init__(self):
        self.specs = []          # [{spec, spec_path, workdir, meta}] in run order
        self._by_step = {}       # id(step) -> [exec record dict, ...]

    def begin_spec(self, spec, spec_path, workdir, meta):
        self.specs.append({
            "spec": spec, "spec_path": spec_path,
            "workdir": workdir, "meta": meta,
        })

    def record(self, step, **rec):
        """Attach one execution record to a step. `rec` keys: kind, cmd,
        status (pass|fail|info), exit_code, output, note."""
        self._by_step.setdefault(id(step), []).append(rec)

    def execs_for(self, step):
        return self._by_step.get(id(step), [])


def _describe_ui_actions(tests):
    """One-line-per-action human summary of a ui_test's test list."""
    lines = []
    for t in tests:
        action = t.get("action", "")
        name = t.get("name", "")
        if action == "wait_for":
            detail = f"wait for {t.get('texts', [])}"
        elif action == "expect_texts":
            detail = f"expect {t.get('texts', [])}"
        elif action == "click":
            detail = f"click {t.get('target', '')!r}"
        elif action == "set_text":
            detail = f"set {t.get('find_by','')}={t.get('find_value','')!r} to {t.get('value','')!r}"
        elif action == "sleep":
            detail = f"sleep {t.get('ms', 0)}ms"
        else:
            detail = action
        lines.append(f"- {name + ': ' if name else ''}{detail}")
    return "\n".join(lines)


def _rec_ui(step, launch_cmd, tests, status, note, output):
    """Record a ui_test execution: the launch command, the action list, and the
    captured output/log."""
    if not _REPORT:
        return
    cmd = launch_cmd + "\n\n# test actions:\n" + _describe_ui_actions(tests)
    _REPORT.record(step, kind="ui_test", cmd=cmd, status=status,
                   output=output, note=note)


# ── Variable Expansion ────────────────────────────────────────────────────────

RELEASE_TAG = ""

# Directory where ui_test screenshots are written. Set by cmd_run when an output
# directory is known so captures land beside the generated .md (output_dir/images);
# left None for ephemeral temp runs, where handle_ui_test falls back to workdir.
_IMAGES_DIR = None


def set_release(tag):
    global RELEASE_TAG
    RELEASE_TAG = f"/{tag}" if tag else ""


def expand_vars(s):
    """Replace {ext}, {shared_flags}, and {release} with resolved values."""
    s = s.replace("{ext}", LIB_EXT)
    s = s.replace("{shared_flags}", SHARED_FLAGS)
    s = s.replace("{release}", RELEASE_TAG)
    return s


# ── Nix Override Injection ────────────────────────────────────────────────────

def parse_build_overrides(spec, spec_dir):
    """Parse build_overrides from spec into --override-input flags string."""
    overrides = spec.get("build_overrides", {})
    if not overrides:
        return ""
    flags = []
    for key, rel_path in overrides.items():
        abs_path = os.path.normpath(os.path.join(spec_dir, rel_path))
        if os.path.isdir(abs_path):
            flags.append(f"--override-input {key} path:{abs_path}")
        else:
            print(f"  WARNING: build_overrides.{key} path not found: {abs_path}")
    return " ".join(flags)


def inject_nix_overrides(cmd, override_flags):
    """Append nix override flags to nix build commands."""
    if override_flags and "nix build" in cmd:
        return f"{cmd} {override_flags}"
    return cmd


# ── Command Execution ─────────────────────────────────────────────────────────

def run_cmd(cmd, workdir, verbose=False, capture=False, timeout=None):
    """Run a shell command. Returns (exit_code, stdout) if capture=True."""
    if verbose:
        print(f"        cmd: {dim(cmd)}")

    actual_cmd = cmd
    if cmd.rstrip().endswith("&"):
        actual_cmd = cmd.rstrip().rstrip("&") + " >/dev/null 2>&1 &"

    try:
        if capture:
            result = subprocess.run(
                actual_cmd,
                shell=True,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout or ""
        else:
            result = subprocess.run(
                actual_cmd,
                shell=True,
                cwd=workdir,
                timeout=timeout,
            )
            return result.returncode, ""
    except subprocess.TimeoutExpired:
        return 124, "command timed out"
    except Exception as e:
        return 1, str(e)


# ── Step Handlers ─────────────────────────────────────────────────────────────

def handle_file(step, workdir, results, verbose):
    file_spec = step.get("file", {})
    path = file_spec.get("path", "")
    if not path:
        return
    path = expand_vars(path)
    content = expand_vars(file_spec.get("content", ""))
    encoding = file_spec.get("encoding", "")

    full_path = os.path.join(workdir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if encoding == "base64":
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(content))
    else:
        with open(full_path, "w") as f:
            f.write(content)

    if os.path.isfile(full_path):
        print(f"  wrote   {path}")
        if _REPORT:
            _REPORT.record(step, kind="file", cmd=f"write {path}",
                           status="pass", note=f"Wrote {path}")
    else:
        if _REPORT:
            _REPORT.record(step, kind="file", cmd=f"write {path}",
                           status="fail", note="file was not created")
        results.fail(f"write {path}", "file was not created")


def _exec_run(cmd, title, workdir, results, verbose, override_flags,
              expect_contains=None, step=None):
    """Execute a single run command with optional output assertions."""
    cmd = expand_vars(cmd)
    cmd = inject_nix_overrides(cmd, override_flags)
    expect_contains = expect_contains or []

    rc, output = run_cmd(cmd, workdir, verbose, capture=True)

    def _rec(status, note=""):
        if _REPORT:
            _REPORT.record(step, kind="run", cmd=cmd, status=status,
                           exit_code=rc, output=output, note=note)

    if rc != 0:
        if output and output.strip():
            lines = output.strip().split("\n")
            tail = lines[-20:]
            if len(lines) > 20:
                print(f"        {dim(f'... ({len(lines) - 20} lines omitted)')}")
            for line in tail:
                print(f"        {dim(line)}")
        _rec("fail", f"exit code {rc}")
        results.fail(title, f"command failed with exit code {rc}")
        return

    if expect_contains:
        all_found = True
        for expected in expect_contains:
            if expected not in output:
                trimmed = output.strip()
                out_msg = trimmed[:500] if trimmed else "(empty)"
                _rec("fail", f"expected '{expected}' not found in output")
                results.fail(title, f"expected '{expected}' not found in output\n        actual:   {out_msg}")
                all_found = False
                break
        if all_found:
            _rec("pass")
            results.pass_(title)
    else:
        _rec("pass")
        results.pass_(title)


def handle_run(step, workdir, results, verbose, override_flags):
    cmd = step.get("run", "")
    if not cmd:
        return
    title = step.get("title", cmd)
    _exec_run(cmd, title, workdir, results, verbose, override_flags,
              step.get("expect_contains", []), step=step)

    extra = step.get("extra_run", {})
    if extra:
        extra_cmd = extra.get("run", "")
        if extra_cmd:
            _exec_run(extra_cmd, f"{title} (verify)", workdir, results, verbose,
                      override_flags, extra.get("expect_contains", []), step=step)


def handle_check_file(step, workdir, results, verbose):
    pattern = step.get("check_file", "")
    if not pattern:
        return
    title = step.get("title", f"check {pattern}")
    pattern = expand_vars(pattern)
    full_pattern = os.path.join(workdir, pattern)
    matches = glob.glob(full_pattern)
    if matches:
        if _REPORT:
            _REPORT.record(step, kind="check_file", cmd=f"check file: {pattern}",
                           status="pass", note=f"Found: {matches[0]}")
        results.pass_(title)
    else:
        if _REPORT:
            _REPORT.record(step, kind="check_file", cmd=f"check file: {pattern}",
                           status="fail", note=f"file not found: {pattern}")
        results.fail(title, f"file not found: {pattern}")


def handle_logoscore(section, workdir, results, verbose, override_flags,
                     call_timeout, module_name):
    logoscore_spec = section.get("logoscore", {})
    if not logoscore_spec:
        return

    setup_cmds = logoscore_spec.get("setup", [])
    tests = logoscore_spec.get("tests", [])

    setup_ok = True
    if setup_cmds:
        print("  -- Setup --")
        for cmd in setup_cmds:
            cmd = expand_vars(cmd)
            cmd = inject_nix_overrides(cmd, override_flags)
            rc, output = run_cmd(cmd, workdir, verbose, capture=verbose)
            if rc != 0:
                results.fail(f"logoscore setup: {cmd}", "setup command failed")
                setup_ok = False
                break
        if setup_ok:
            print("  setup completed")

    logoscore_bin = ""
    candidate = os.path.join(workdir, "logos", "bin", "logoscore")
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        logoscore_bin = candidate
    elif shutil.which("logoscore"):
        logoscore_bin = "logoscore"

    if not logoscore_bin:
        results.skip("logoscore", "logoscore not found (build it in setup or add to PATH)")
        return

    if not setup_ok:
        return

    print("  -- Tests --")
    for test in tests:
        name = test.get("name", "")
        call = test.get("call", "")
        expect = test.get("expect", "")

        cmd = f"timeout {call_timeout} {logoscore_bin} -m ./modules -l {module_name} -c \"{call}\""
        rc, output = run_cmd(cmd, workdir, verbose, capture=True)

        if rc != 0:
            results.fail(name, f"logoscore exit code {rc}")
            if verbose:
                print(f"        output: {dim(output[:300])}")
        elif expect in output:
            results.pass_(name)
        else:
            results.fail(name, f"expected '{expect}' in output")
            if verbose:
                print(f"        output: {dim(output[:300])}")


def handle_basecamp(section, workdir, results, verbose, override_flags,
                    basecamp_bin, qt_mcp_path, spec_dir, section_count, spec):
    basecamp_spec = section.get("basecamp", {})
    if not basecamp_spec:
        return

    if not basecamp_bin:
        results.skip("basecamp", "no --basecamp-bin provided")
        return
    if not os.path.isfile(basecamp_bin) or not os.access(basecamp_bin, os.X_OK):
        results.skip("basecamp", f"basecamp binary not found: {basecamp_bin}")
        return

    qt_mcp = qt_mcp_path or os.environ.get("LOGOS_QT_MCP", "")
    if not qt_mcp:
        results.skip("basecamp", "no --qt-mcp or LOGOS_QT_MCP provided")
        return

    install_as = basecamp_spec.get("install_as", "")
    tests = basecamp_spec.get("tests", [])

    user_dir = tempfile.mkdtemp(dir=workdir, prefix="basecamp-data-")
    env = {
        **os.environ,
        "LOGOS_USER_DIR": user_dir,
        "QT_QPA_PLATFORM": "offscreen",
        "QT_FORCE_STDERR_LOGGING": "1",
        "QT_LOGGING_RULES": "qt.*.debug=false;default.debug=true",
        "LOGOS_QT_MCP": qt_mcp,
    }

    # Install core deps if specified
    core_deps = basecamp_spec.get("core_deps", [])
    if core_deps:
        os.makedirs(os.path.join(user_dir, "modules"), exist_ok=True)
        for dep_path in core_deps:
            full_dep = os.path.join(spec_dir, dep_path)
            if os.path.isdir(full_dep):
                print(f"  Installing core dependency: {dep_path}")
                install_dir = tempfile.mkdtemp()
                cmd = f"nix build '.#install' -o {install_dir}/result"
                rc, _ = run_cmd(cmd, full_dep, verbose)
                if rc == 0:
                    src = os.path.join(install_dir, "result", "modules")
                    if os.path.isdir(src):
                        for item in os.listdir(src):
                            shutil.copytree(
                                os.path.join(src, item),
                                os.path.join(user_dir, "modules", item),
                                dirs_exist_ok=True
                            )

    if install_as:
        print("  Building install package...")
        cmd = f"nix build '.#install' -o result-install"
        cmd = inject_nix_overrides(cmd, override_flags)
        rc, _ = run_cmd(cmd, workdir, verbose)
        if rc == 0:
            if install_as == "core":
                src = os.path.join(workdir, "result-install", "modules")
                dst = os.path.join(user_dir, "modules")
                os.makedirs(dst, exist_ok=True)
                if os.path.isdir(src):
                    for item in os.listdir(src):
                        shutil.copytree(
                            os.path.join(src, item),
                            os.path.join(dst, item),
                            dirs_exist_ok=True
                        )
            elif install_as == "ui":
                for subdir in ["plugins", "modules"]:
                    src = os.path.join(workdir, "result-install", subdir)
                    dst = os.path.join(user_dir, "plugins")
                    os.makedirs(dst, exist_ok=True)
                    if os.path.isdir(src):
                        for item in os.listdir(src):
                            shutil.copytree(
                                os.path.join(src, item),
                                os.path.join(dst, item),
                                dirs_exist_ok=True
                            )
                        break
        else:
            results.fail("basecamp install", "nix build '.#install' failed")
            return

    mjs_path = generate_mjs_tests(
        tests, qt_mcp, f"{spec.get('name', 'tutorial')}: basecamp UI verification",
        os.path.join(workdir, "basecamp-test.mjs")
    )

    cmd = f'node "{mjs_path}" --ci "{basecamp_bin}" --verbose'
    rc, output = run_cmd(cmd, workdir, verbose, capture=True)
    if rc == 0:
        results.pass_("basecamp UI tests")
    else:
        results.fail("basecamp UI tests", "test runner exited with non-zero")
        if verbose:
            print(f"        {dim(output[:500])}")


# ── Shared .mjs test generation ──────────────────────────────────────────────

def _screenshot_filename(raw):
    """Normalize a spec's `screenshot:` value to a safe PNG basename."""
    name = os.path.basename(str(raw).strip())
    if not name:
        return ""
    if not name.lower().endswith(".png"):
        name += ".png"
    return name


def _screenshot_md_lines(ui_test_spec, images_dir=None):
    """Markdown image embeds for any ui_test action carrying a `screenshot:`
    field.

    With no `images_dir` (the published-tutorial generator), emit a relative
    link `images/<file>.png` so it resolves from the generated .md in outputs/.
    With an `images_dir` (the self-contained HTML report), inline the captured
    PNG as a base64 `data:` URI when the file exists — so the report stays a
    single portable file that renders the screenshots even when served from
    GitHub Pages; fall back to the relative link if the capture is missing."""
    import base64 as _base64
    lines = []
    for t in ui_test_spec.get("tests", []):
        fname = _screenshot_filename(t.get("screenshot", ""))
        if not fname:
            continue
        alt = t.get("name") or os.path.splitext(fname)[0]
        src = f"images/{fname}"
        if images_dir:
            path = os.path.join(images_dir, fname)
            try:
                with open(path, "rb") as fh:
                    b64 = _base64.b64encode(fh.read()).decode("ascii")
                src = f"data:image/png;base64,{b64}"
            except OSError:
                pass  # capture missing (e.g. step failed) — keep relative link
        lines.append(f"![{alt}]({src})")
    return lines


def generate_mjs_tests(tests, qt_mcp_path, test_name, output_path, images_dir=None):
    """Generate a .mjs test file from YAML test actions for logos-qt-mcp.

    If an action carries a `screenshot:` field (a filename), the generated test
    captures the headless app via `app.screenshot()` right after that action and
    writes the decoded PNG into `images_dir`.
    """
    import json as _json

    with open(output_path, "w") as f:
        f.write('import { resolve } from "node:path";\n')
        f.write('import { writeFileSync } from "node:fs";\n')
        f.write(f'const qtMcpRoot = "{qt_mcp_path}";\n')
        f.write('const { test, run } = await import(resolve(qtMcpRoot, "test-framework/framework.mjs"));\n\n')
        f.write(f'test("{test_name}", async (app) => {{\n')

        def emit_screenshot(t):
            fname = _screenshot_filename(t.get("screenshot", ""))
            if not fname or not images_dir:
                return
            dest = _json.dumps(os.path.join(images_dir, fname))
            label = _json.dumps(fname)
            f.write(f'  {{\n')
            f.write(f'    const shot = await app.screenshot();\n')
            f.write(f'    if (shot && shot.image) {{\n')
            f.write(f'      writeFileSync({dest}, Buffer.from(shot.image, "base64"));\n')
            f.write(f'    }} else {{\n')
            f.write(f'      throw new Error("screenshot " + {label} + ": no image returned");\n')
            f.write(f'    }}\n')
            f.write(f'  }}\n')

        for t in tests:
            action = t.get("action", "")
            if action == "click":
                target = t.get("target", "")
                f.write(f'  await app.click("{target}", {{ exact: true }});\n')
            elif action == "expect_texts":
                texts = _json.dumps(t.get("texts", []))
                f.write(f'  await app.expectTexts({texts});\n')
            elif action == "wait_for":
                texts = _json.dumps(t.get("texts", []))
                timeout = t.get("timeout", 10000)
                name = t.get("name", "")
                f.write(f'  await app.waitFor(\n')
                f.write(f'    async () => {{ await app.expectTexts({texts}); }},\n')
                f.write(f'    {{ timeout: {timeout}, interval: 500, description: "{name}" }}\n')
                f.write(f'  );\n')
            elif action == "set_text":
                prop = t.get("find_by", "")
                val = t.get("find_value", "")
                set_val = t.get("value", "")
                f.write(f'  {{\n')
                f.write(f'    const found = await app.inspector.send("findByProperty", {{ property: "{prop}", value: "{val}" }});\n')
                f.write(f'    if (!found.matches || found.matches.length === 0) throw new Error("set_text: element not found");\n')
                f.write(f'    await app.inspector.send("setProperty", {{ objectId: found.matches[0].id, property: "text", value: "{set_val}" }});\n')
                f.write(f'  }}\n')
            elif action == "sleep":
                ms = t.get("ms", 1000)
                f.write(f'  await new Promise(r => setTimeout(r, {ms}));\n')

            emit_screenshot(t)

        f.write('});\n\nrun();\n')

    return output_path


# ── UI Test Handler ──────────────────────────────────────────────────────────

import signal
import socket
import time


def _wait_for_inspector(host="localhost", port=3768, timeout=60, proc=None):
    """Poll until the QML inspector TCP port accepts connections.

    Returns "ok" once the port is connectable. If `proc` is given and the app
    exits before the port opens, returns "died" immediately (no point waiting
    out the full timeout for a process that is gone). Returns "timeout" if the
    deadline passes while the app is still running (e.g. a slow cold-cache
    `nix run` build that hasn't finished compiling the app yet).
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return "died"
        try:
            with socket.create_connection((host, port), timeout=2):
                return "ok"
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return "timeout"


def _kill_process_tree(pid):
    """Kill a process and its children."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def handle_ui_test(step, workdir, results, verbose, override_flags, qt_mcp_cli, spec):
    """Run headless UI tests via logos-qt-mcp test framework.

    Supports two modes:
      - launch mode: runs the app as a background process, connects tests to it
      - binary mode: uses --ci flag to let the test framework manage the app

    YAML format (launch mode — preferred):
        ui_test:
          launch: "nix run ."
          qt_mcp: "result-mcp"
          setup:
            - "nix build 'github:logos-co/logos-qt-mcp' -o result-mcp"
          tests:
            - name: "Title visible"
              action: wait_for
              texts: ["My App"]
              timeout: 15000

    YAML format (binary mode):
        ui_test:
          build: "nix build"
          binary: "nix-app"
          qt_mcp: "result-mcp"
          setup: [...]
          tests: [...]
    """
    ui_spec = step.get("ui_test", {})
    if not ui_spec:
        return

    tests = ui_spec.get("tests", [])
    if not tests:
        return

    title = step.get("title", "UI tests")

    qt_mcp = ui_spec.get("qt_mcp", "") or qt_mcp_cli or os.environ.get("LOGOS_QT_MCP", "")

    # Run setup commands
    for cmd in ui_spec.get("setup", []):
        cmd = expand_vars(cmd)
        cmd = inject_nix_overrides(cmd, override_flags)
        print(f"  Setup: {cmd}")
        rc, _ = run_cmd(cmd, workdir, verbose)
        if rc != 0:
            results.fail(title, f"setup command failed: {cmd}")
            return

    # Resolve qt_mcp path
    if qt_mcp and not os.path.isabs(qt_mcp):
        qt_mcp = os.path.join(workdir, qt_mcp)
    if not qt_mcp or not os.path.isdir(qt_mcp):
        results.fail(title, f"logos-qt-mcp not found: {qt_mcp}")
        return

    # Generate .mjs test file. Screenshots (actions with a `screenshot:` field)
    # are written into the shared images dir alongside the generated .md so the
    # published tutorial can embed them; falls back to the workdir for ephemeral
    # temp runs.
    images_dir = _IMAGES_DIR or os.path.join(workdir, "images")
    os.makedirs(images_dir, exist_ok=True)
    test_name = f"{spec.get('name', 'tutorial')}: {title}"
    mjs_path = generate_mjs_tests(
        tests, qt_mcp, test_name,
        os.path.join(workdir, "ui-test.mjs"),
        images_dir=images_dir,
    )

    launch_cmd = ui_spec.get("launch", "")

    if launch_cmd:
        # Launch mode: start app in background, run tests against it, kill it
        launch_cmd = expand_vars(launch_cmd)
        launch_cmd = inject_nix_overrides(launch_cmd, override_flags)

        env = {
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "QT_FORCE_STDERR_LOGGING": "1",
            "QT_LOGGING_RULES": "qt.*.debug=false;default.debug=true",
        }

        # Pre-build the app before starting the inspector clock. `nix run .`
        # builds the app closure on first use; on a cold cache (e.g. an x86_64
        # CI runner with no binary cache) that compile can take minutes and
        # would otherwise be counted against the inspector timeout — the app
        # never even boots before we give up. Building first (best effort)
        # means the subsequent launch only has to boot, not compile. Output is
        # streamed with -L so a real build failure is visible in CI logs.
        if launch_cmd.lstrip().startswith("nix run"):
            warm_cmd = "nix build" + launch_cmd.lstrip()[len("nix run"):]
            if " -L" not in warm_cmd:
                warm_cmd += " -L"
            build_timeout = ui_spec.get("build_timeout", 1800)
            print(f"  Pre-building app: {warm_cmd}")
            wrc, _ = run_cmd(warm_cmd, workdir, verbose, timeout=build_timeout)
            if wrc != 0:
                print(f"        {yellow('pre-build returned non-zero; launching anyway')}")

        app_log_path = os.path.join(workdir, "ui-test-app.log")
        app_log = open(app_log_path, "w")

        print(f"  Launching: {launch_cmd}")
        app_proc = subprocess.Popen(
            launch_cmd, shell=True, cwd=workdir, env=env,
            stdout=app_log, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )

        def _dump_app_log(reason):
            app_log.flush()
            try:
                with open(app_log_path) as f:
                    tail = f.read().strip()[-1500:]
            except OSError:
                tail = ""
            print(f"        {dim(reason)}")
            print(f"        {dim('app output (' + app_log_path + '):')}")
            print(f"        {dim(tail if tail else '(no output captured)')}")

        def _app_log_tail():
            app_log.flush()
            try:
                with open(app_log_path) as f:
                    return f.read().strip()[-1500:]
            except OSError:
                return ""

        try:
            port = ui_spec.get("inspector_port", 3768)
            timeout = ui_spec.get("launch_timeout", 120)
            print(f"  Waiting for inspector on port {port} (timeout {timeout}s)...")
            status = _wait_for_inspector(port=port, timeout=timeout, proc=app_proc)
            if status == "died":
                _rec_ui(step, launch_cmd, tests, "fail",
                        f"app exited (code {app_proc.returncode}) before inspector opened on port {port}",
                        _app_log_tail())
                results.fail(title, f"app exited (code {app_proc.returncode}) before inspector opened on port {port}")
                _dump_app_log("app process exited before opening the inspector port")
                return
            if status == "timeout":
                _rec_ui(step, launch_cmd, tests, "fail",
                        f"inspector not available on port {port} after {timeout}s",
                        _app_log_tail())
                results.fail(title, f"inspector not available on port {port} after {timeout}s")
                _dump_app_log("inspector port never opened (app still running — likely slow boot or wrong port)")
                return

            print(f"  Running UI tests ({len(tests)} actions)...")
            cmd = f'node "{mjs_path}" --verbose'
            rc, output = run_cmd(cmd, workdir, verbose, capture=True, timeout=120)
            if rc == 0:
                _rec_ui(step, launch_cmd, tests, "pass", "", output)
                results.pass_(title)
            else:
                _rec_ui(step, launch_cmd, tests, "fail", "UI tests failed",
                        (output or "") + "\n\n--- app log ---\n" + _app_log_tail())
                results.fail(title, "UI tests failed")
                trimmed = output.strip()[-800:] if output else "(no output)"
                print(f"        {dim(trimmed)}")
                _dump_app_log("app output during test run")
        finally:
            try:
                os.killpg(os.getpgid(app_proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                app_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            app_log.close()

    else:
        # Binary mode: use --ci flag (test framework manages the app)
        build_cmd = ui_spec.get("build", "")
        if build_cmd:
            build_cmd = expand_vars(build_cmd)
            build_cmd = inject_nix_overrides(build_cmd, override_flags)
            print(f"  Build: {build_cmd}")
            rc, _ = run_cmd(build_cmd, workdir, verbose)
            if rc != 0:
                results.fail(title, "build failed")
                return

        binary = ui_spec.get("binary", "")
        if not binary:
            results.fail(title, "no binary or launch command specified in ui_test")
            return

        if binary == "nix-app":
            print(f"  Resolving app binary from flake...")
            try:
                proc = subprocess.run(
                    'nix eval .#apps."$(nix eval --impure --expr builtins.currentSystem --raw)".default.program --raw',
                    shell=True, cwd=workdir, capture_output=True, text=True, timeout=60
                )
                binary_path = (proc.stdout or "").strip()
                if proc.returncode != 0 or not binary_path:
                    results.fail(title, f"failed to resolve nix app binary: {(proc.stderr or '').strip()}")
                    return
            except Exception as e:
                results.fail(title, f"nix eval failed: {e}")
                return
        else:
            binary_path = os.path.join(workdir, binary)

        if not os.path.isfile(binary_path):
            results.fail(title, f"binary not found: {binary_path}")
            return

        env_prefix = "QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1"
        cmd = f'{env_prefix} node "{mjs_path}" --ci "{binary_path}" --verbose'
        print(f"  Running UI tests ({len(tests)} actions)...")
        rc, output = run_cmd(cmd, workdir, verbose, capture=True, timeout=120)
        if rc == 0:
            _rec_ui(step, cmd, tests, "pass", "", output)
            results.pass_(title)
        else:
            _rec_ui(step, cmd, tests, "fail", "UI tests failed", output)
            results.fail(title, "UI tests failed")
            trimmed = output.strip()[-800:] if output else "(no output)"
            print(f"        {dim(trimmed)}")


# ── Find module name from spec ────────────────────────────────────────────────

def find_module_name(spec):
    """Extract module name from the metadata.json file step in the spec."""
    for section in spec.get("sections", []):
        for step in section.get("steps", []):
            file_spec = step.get("file", {})
            if file_spec.get("path") == "metadata.json":
                content = file_spec.get("content", "")
                try:
                    import json
                    meta = json.loads(content)
                    return meta.get("name", "")
                except (json.JSONDecodeError, TypeError):
                    pass
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# RUN COMMAND
# ══════════════════════════════════════════════════════════════════════════════

def _dispatch_step(step, workdir, results, args, override_flags, spec):
    """Execute one step via the appropriate handler. Returns True if the step
    was an executable action (file/run/ui_test/check_file), False if it was
    prose-only. Shared by the normal run loop and the TUI so execution logic
    never diverges between them."""
    if step.get("file"):
        handle_file(step, workdir, results, args.verbose)
    elif step.get("run"):
        handle_run(step, workdir, results, args.verbose, override_flags)
    elif step.get("ui_test"):
        handle_ui_test(step, workdir, results, args.verbose,
                       override_flags, args.qt_mcp, spec)
    elif step.get("check_file"):
        handle_check_file(step, workdir, results, args.verbose)
    else:
        return False
    return True


def run_single_spec(spec, spec_path, workdir, args, results):
    """Run a single tutorial spec in the given workdir. May raise StopEarly."""
    spec_dir = os.path.dirname(spec_path)

    release = args.release if args.release is not None else spec.get("release", "")
    set_release(release)

    override_flags = parse_build_overrides(spec, spec_dir)
    module_name = find_module_name(spec)

    tutorial_name = spec.get("name", "tutorial")
    print("=" * 65)
    print(f" Tutorial Test: {bold(tutorial_name)}")
    print("=" * 65)
    print()
    print(f"  spec     : {spec_path}")
    print(f"  workdir  : {workdir}")
    print(f"  platform : {platform.system()} (ext={LIB_EXT})")
    print(f"  release  : {release or '(none)'}")
    if override_flags:
        print(f"  overrides: {override_flags}")
    print()

    if _REPORT:
        _REPORT.begin_spec(spec, spec_path, workdir, {
            "name": tutorial_name,
            "platform": f"{platform.system()} (ext={LIB_EXT})",
            "release": release or "(none)",
        })

    # In TUI mode, hand off to the rich-driven two-column view. It walks the
    # same spec and uses the same _dispatch_step path, so execution is identical.
    if getattr(args, "tui", False):
        run_tui(_REPORT, spec, spec_path, workdir, args, results, override_flags)
        return

    sections = spec.get("sections", [])

    for si, section in enumerate(sections):
        sec_title = section.get("title", f"Section {si + 1}")

        print("-" * 65)
        print(f" Section: {bold(sec_title)}")
        print("-" * 65)

        # Handle logoscore sections
        if section.get("logoscore"):
            handle_logoscore(
                section, workdir, results, args.verbose,
                override_flags, args.call_timeout, module_name
            )
            print()
            continue

        # Handle basecamp sections
        if section.get("basecamp"):
            handle_basecamp(
                section, workdir, results, args.verbose,
                override_flags, args.basecamp_bin, args.qt_mcp,
                spec_dir, len(sections), spec
            )
            print()
            continue

        steps = section.get("steps", [])
        if not steps:
            if args.verbose:
                print(f"  {dim('(prose-only section, skipping)')}")
            print()
            continue

        for step in steps:
            if _dispatch_step(step, workdir, results, args, override_flags, spec):
                continue
            if args.verbose:
                title = step.get("title", "untitled")
                print(f"  {dim(f'(prose-only step: {title})')}")

        print()


def cmd_run(args):
    spec_path = os.path.abspath(args.spec)
    spec_dir = os.path.dirname(spec_path)

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    requires = spec.get("requires", [])
    fail_fast = not args.continue_on_fail
    results = Results(fail_fast=fail_fast)

    tui = getattr(args, "tui", False)

    if getattr(args, "iterative", False) and not tui:
        print("ERROR: --iterative only applies with --tui", file=sys.stderr)
        sys.exit(2)
    if tui:
        try:
            import rich  # noqa: F401
        except ImportError:
            print("ERROR: --tui requires the 'rich' package. Install it with:\n"
                  "  pip3 install rich", file=sys.stderr)
            sys.exit(2)
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("ERROR: --tui requires an interactive terminal (a TTY).",
                  file=sys.stderr)
            sys.exit(2)

    global _REPORT, _IMAGES_DIR
    # The TUI reads per-step execution records from the collector, so it needs
    # one active even without --report.
    if getattr(args, "report", None) or tui:
        _REPORT = ReportCollector()

    output_dir = getattr(args, "output_dir", None)

    # When the caller picks a persistent output directory, write ui_test
    # screenshots into <output_dir>/images so they sit beside the generated .md
    # (which references them as images/<file>.png). Temp runs leave this None and
    # fall back to the workdir.
    if output_dir:
        _IMAGES_DIR = os.path.join(os.path.abspath(output_dir), "images")

    if output_dir:
        # --output-dir: run into a persistent directory the caller chooses,
        # never deleted. For a chained tutorial it becomes the chain root and
        # each project lands in its own subdir (output_dir/<project_name>/);
        # standalone, the project is written directly into output_dir.
        out = os.path.abspath(output_dir)
        os.makedirs(out, exist_ok=True)
        if requires:
            project_name = spec.get("project_name")
            if not project_name:
                print(f"ERROR: spec with requires: must also have project_name", file=sys.stderr)
                sys.exit(2)
            root_dir = out
            created_root = True
            workdir = os.path.join(root_dir, project_name)
            os.makedirs(workdir, exist_ok=True)
        else:
            root_dir = None
            created_root = False
            workdir = out
    elif args.workdir:
        workdir = os.path.abspath(args.workdir)
        if not os.path.isdir(workdir):
            print(f"ERROR: --workdir path does not exist: {workdir}", file=sys.stderr)
            sys.exit(2)
        root_dir = None
        created_root = False
    elif requires:
        root_dir = tempfile.mkdtemp(prefix="tutorial-chain-")
        created_root = True

        project_name = spec.get("project_name")
        if not project_name:
            print(f"ERROR: spec with requires: must also have project_name", file=sys.stderr)
            sys.exit(2)

        workdir = os.path.join(root_dir, project_name)
        os.makedirs(workdir, exist_ok=True)
    else:
        workdir = tempfile.mkdtemp(prefix="tutorial-test-")
        root_dir = None
        created_root = False

    def cleanup():
        # --output-dir is an explicit, caller-owned location: never auto-delete.
        if not args.keep_workdir and not output_dir:
            target = root_dir if created_root else workdir
            if target:
                shutil.rmtree(target, ignore_errors=True)

    try:
        # Run prerequisite tutorials first, resolved transitively. requires: is
        # walked depth-first in post-order, so if A requires B and B requires C,
        # the run order is C, then B, then A. Shared prerequisites run once
        # (deduped by spec path) and cycles are reported rather than looping.
        if requires and created_root:
            ordered = []          # spec paths in dependency order (deepest first)
            ran = set()           # spec paths already added to `ordered`
            in_progress = set()   # spec paths on the current DFS stack (cycle guard)

            def resolve(req_path, referenced_by):
                req_path = os.path.abspath(req_path)
                if req_path in ran:
                    return
                if req_path in in_progress:
                    print(f"ERROR: circular requires: detected at {req_path} "
                          f"(referenced by {referenced_by})", file=sys.stderr)
                    sys.exit(2)
                if not os.path.isfile(req_path):
                    print(f"ERROR: required spec not found: {req_path} "
                          f"(referenced by {referenced_by})", file=sys.stderr)
                    sys.exit(2)

                with open(req_path) as f:
                    req_spec = yaml.safe_load(f)

                if not req_spec.get("project_name"):
                    print(f"ERROR: required spec {req_path} has no project_name field",
                          file=sys.stderr)
                    sys.exit(2)

                in_progress.add(req_path)
                req_dir = os.path.dirname(req_path)
                for nested_rel in req_spec.get("requires", []):
                    resolve(os.path.join(req_dir, nested_rel), req_path)
                in_progress.discard(req_path)

                ran.add(req_path)
                ordered.append((req_path, req_spec))

            for req_rel in requires:
                resolve(os.path.join(spec_dir, req_rel), spec_path)

            for req_path, req_spec in ordered:
                req_workdir = os.path.join(root_dir, req_spec["project_name"])
                os.makedirs(req_workdir, exist_ok=True)
                run_single_spec(req_spec, req_path, req_workdir, args, results)

        # Run the main tutorial
        run_single_spec(spec, spec_path, workdir, args, results)

    except StopEarly:
        pass

    if output_dir:
        print(f"  output : {root_dir or workdir}")
    elif args.keep_workdir or args.workdir:
        print(f"  workdir: {root_dir or workdir}")

    ok = results.summary()

    # Build the HTML report before cleanup removes the working directories.
    if _REPORT is not None:
        try:
            report_path = os.path.abspath(args.report)
            write_html_report(_REPORT, report_path, results)
            print(f"  report : {report_path}")
        except Exception as e:
            print(f"  {yellow(f'report generation failed: {e}')}")

    try:
        cleanup()
    except Exception:
        pass

    sys.exit(0 if ok else 1)


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT (run --report)
# ══════════════════════════════════════════════════════════════════════════════

def _step_to_markdown(step, sec_num, sub_step, images_dir=None):
    """Render a single step to the same markdown the generator produces.
    Returns (markdown_str, next_sub_step). Mirrors the per-step block in
    cmd_generate so the report's left column matches the published tutorial.

    When `images_dir` is given, ui_test screenshots are inlined as base64
    `data:` URIs (for the self-contained report); otherwise they render as
    relative `images/<file>.png` links (for the published tutorial / TUI)."""
    out = []

    def emit(t=""):
        out.append(t)

    def emit_block(t):
        out.extend(t.rstrip("\n").split("\n"))

    title = step.get("title", "")
    if title:
        if sec_num is not None:
            emit(f"### {sec_num}.{sub_step} {title}")
            sub_step += 1
        else:
            emit(f"### {title}")
        emit()

    text = step.get("text", "")
    if text:
        emit_block(expand_vars(text))
        emit()

    file_spec = step.get("file", {})
    if file_spec:
        path = file_spec.get("path", "")
        encoding = file_spec.get("encoding", "")
        lang = lang_for_path(path, file_spec.get("language"))
        if encoding == "base64":
            emit(f"*Binary file: `{path}`*")
        else:
            emit(f"```{lang}")
            emit_block(expand_vars(file_spec.get("content", "")))
            emit("```")
        emit()

    run_cmd_str = step.get("run", "")
    if run_cmd_str:
        code_block = step.get("code_block", "")
        emit("```bash")
        if code_block:
            emit_block(expand_vars(code_block))
        else:
            emit(expand_vars(run_cmd_str))
        emit("```")
        emit()

    ui_test_spec = step.get("ui_test", {})
    if ui_test_spec:
        launch = ui_test_spec.get("launch", "")
        if launch:
            emit("```bash")
            emit(expand_vars(launch))
            emit("```")
            emit()
        for img in _screenshot_md_lines(ui_test_spec, images_dir):
            emit(img)
            emit()

    post_text = step.get("post_text", "")
    if post_text:
        emit_block(expand_vars(post_text))
        emit()

    extra = step.get("extra_run", {})
    if extra:
        extra_code = extra.get("code_block", "")
        extra_cmd = extra.get("run", "")
        emit("```bash")
        if extra_code:
            emit_block(expand_vars(extra_code))
        elif extra_cmd:
            emit(expand_vars(extra_cmd))
        emit("```")
        emit()
        extra_post = extra.get("post_text", "")
        if extra_post:
            emit_block(expand_vars(extra_post))
            emit()

    return "\n".join(out).strip(), sub_step


def _section_preamble_markdown(section, step_number, is_step):
    """Markdown for a section heading + its intro text (no steps)."""
    out = []
    title = section.get("title", "")
    if is_step:
        out.append(f"## Step {step_number}: {title}")
    else:
        out.append(f"## {title}")
    out.append("")
    sec_text = section.get("text", "")
    if sec_text:
        out.extend(expand_vars(sec_text).rstrip("\n").split("\n"))
    return "\n".join(out).strip()


def build_report_model(collector):
    """Turn the collector's per-spec execution data into a JSON-serializable
    model: a list of tutorials, each with rows. A row has rendered markdown
    (left column) and a list of execution records (right column)."""
    tutorials = []
    for entry in collector.specs:
        spec = entry["spec"]
        rows = []

        # Where this spec's ui_test screenshots were written, so they can be
        # inlined into the report. Mirrors handle_ui_test's resolution: the
        # global output images dir if set, else <workdir>/images. The report is
        # built before cleanup(), so these files still exist.
        spec_workdir = entry.get("workdir")
        images_dir = _IMAGES_DIR or (
            os.path.join(spec_workdir, "images") if spec_workdir else None
        )

        # ── Preamble row (title + intro + objectives + prerequisites) ──────
        pre = []
        pre.append(f"# {spec.get('name', 'Tutorial')}")
        pre.append("")
        if spec.get("intro"):
            pre.append(spec["intro"].rstrip("\n"))
            pre.append("")
        if spec.get("what_you_build"):
            pre.append(f"**What you'll build:** {spec['what_you_build']}")
            pre.append("")
        if spec.get("what_you_learn"):
            pre.append("**What you'll learn:**")
            pre.append("")
            for it in spec["what_you_learn"]:
                pre.append(f"- {it}")
            pre.append("")
        if spec.get("comparison"):
            pre.append(spec["comparison"].rstrip("\n"))
            pre.append("")
        if spec.get("prerequisites"):
            pre.append("## Prerequisites")
            pre.append("")
            for p in spec["prerequisites"]:
                pre.append(f"- {p}")
        rows.append({"md": "\n".join(pre).strip(), "execs": []})

        # ── Sections and steps ─────────────────────────────────────────────
        step_number = 1
        for section in spec.get("sections", []):
            is_step = section.get("step", False)
            rows.append({
                "md": _section_preamble_markdown(section, step_number, is_step),
                "execs": [],
            })
            if is_step:
                step_number += 1

            steps = section.get("steps", [])
            sec_num = (step_number - 1) if is_step else None
            sub_step = 1
            for step in steps:
                md, sub_step = _step_to_markdown(step, sec_num, sub_step, images_dir)
                execs = collector.execs_for(step)
                # Runner-only steps (e.g. check_file) render no markdown. Give
                # them a small left-column note so the row isn't visually empty.
                if not md and execs:
                    md = "*(verification step — not shown in the published tutorial)*"
                rows.append({"md": md, "execs": execs})

        tutorials.append({"meta": entry["meta"], "rows": rows})
    return tutorials


# ══════════════════════════════════════════════════════════════════════════════
# TUI (run --tui)
# ══════════════════════════════════════════════════════════════════════════════

def _read_single_key():
    """Block for one keypress, return a normalized name: 'next', 'quit', or ''.
    Arrow keys / space / enter advance; q / Ctrl-C quit."""
    import termios, tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":               # escape sequence (arrow keys)
            seq = sys.stdin.read(2)
            # Down (\x1b[B) / Right (\x1b[C) advance; others ignored
            if seq in ("[B", "[C"):
                return "next"
            return ""
        if ch in ("q", "Q", "\x03"):   # q or Ctrl-C
            return "quit"
        if ch in (" ", "\r", "\n", "j", "l"):
            return "next"
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _iter_tui_units(spec):
    """Yield render units for the TUI in execution order. Each unit is a dict:
      {kind: 'preamble'|'section'|'step', md: <markdown>, step: <step or None>}
    Mirrors build_report_model's walk so the left pane matches the tutorial."""
    units = []

    # Preamble (title + intro + objectives + prerequisites)
    pre = [f"# {spec.get('name', 'Tutorial')}", ""]
    if spec.get("intro"):
        pre += [spec["intro"].rstrip("\n"), ""]
    if spec.get("what_you_build"):
        pre += [f"**What you'll build:** {spec['what_you_build']}", ""]
    if spec.get("prerequisites"):
        pre += ["## Prerequisites", ""] + [f"- {p}" for p in spec["prerequisites"]]
    units.append({"kind": "preamble", "md": "\n".join(pre).strip(), "step": None})

    step_number = 1
    for section in spec.get("sections", []):
        is_step = section.get("step", False)
        units.append({
            "kind": "section",
            "md": _section_preamble_markdown(section, step_number, is_step),
            "step": None,
        })
        if is_step:
            step_number += 1
        sec_num = (step_number - 1) if is_step else None
        sub_step = 1
        for step in section.get("steps", []):
            md, sub_step = _step_to_markdown(step, sec_num, sub_step)
            if not md:
                md = "*(verification step)*"
            units.append({"kind": "step", "md": md, "step": step})
    return units


def _pending_commands(step):
    """What this step is *about* to execute, derived from the step dict (the
    collector only has records *after* a handler runs). Returns a list of
    (kind, command_text) so the right pane can show the actual command while
    it's still running, instead of a bare 'running…'."""
    cmds = []
    if step.get("file"):
        path = expand_vars(step["file"].get("path", ""))
        cmds.append(("file", f"write {path}"))
    if step.get("run"):
        cmds.append(("run", expand_vars(step["run"])))
        extra = step.get("extra_run", {})
        if extra.get("run"):
            cmds.append(("run", expand_vars(extra["run"])))
    if step.get("check_file"):
        cmds.append(("check_file", f"check file: {expand_vars(step['check_file'])}"))
    ui = step.get("ui_test", {})
    if ui:
        if ui.get("launch"):
            cmds.append(("ui_test", expand_vars(ui["launch"])))
        elif ui.get("build"):
            cmds.append(("ui_test", expand_vars(ui["build"])))
        n = len(ui.get("tests", []))
        if n:
            cmds.append(("ui_test", f"# then run {n} UI test action(s)"))
    return cmds


def _running_renderable(step):
    """Right-pane content shown *while* a step executes: a clear 'Running'
    banner followed by the exact command(s) about to run."""
    from rich.console import Group
    from rich.text import Text
    from rich.syntax import Syntax

    parts = [Text("running…", style="bold yellow")]
    pending = _pending_commands(step)
    if pending:
        for kind, cmd in pending:
            label = Text()
            label.append(" RUN ", style="bold black on yellow")
            label.append(f"  {kind}", style="dim")
            parts.append(label)
            parts.append(Syntax(cmd, "bash", theme="ansi_dark",
                                word_wrap=True, background_color="default"))
    else:
        parts.append(Text("(preparing…)", style="dim italic"))
    return Group(*parts)


def _execs_to_renderable(execs, running_label=None):
    """Build a rich renderable for the right pane from exec records."""
    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax

    parts = []
    if running_label is not None:
        parts.append(Text(running_label, style="bold yellow"))
    for e in execs:
        status = e.get("status", "info")
        color = {"pass": "green", "fail": "red"}.get(status, "yellow")
        head = Text()
        head.append(f" {status.upper()} ", style=f"bold white on {color}")
        head.append(f"  {e.get('kind', '')}", style="dim")
        if e.get("exit_code") is not None:
            head.append(f"  exit {e['exit_code']}", style="dim")
        parts.append(head)
        if e.get("note"):
            parts.append(Text(e["note"], style="italic dim"))
        if e.get("cmd"):
            parts.append(Syntax(e["cmd"], "bash", theme="ansi_dark",
                                word_wrap=True, background_color="default"))
        out = (e.get("output") or "").strip()
        if out:
            # Show a tail so long build logs don't blow past the pane.
            lines = out.splitlines()
            if len(lines) > 30:
                out = "...\n" + "\n".join(lines[-30:])
            parts.append(Text(out, style="grey70"))
        parts.append(Text(""))
    if not parts:
        parts.append(Text("(no commands for this step)", style="dim italic"))
    return Group(*parts)


def run_tui(collector, spec, spec_path, workdir, args, results, override_flags):
    """Drive execution of one spec inside a two-column rich TUI.

    Left pane: rendered markdown for the current unit. Right pane: the commands
    executed for the current step and their captured output. Execution goes
    through the same _dispatch_step path as a normal run; handler stdout/stderr
    is captured to a temp file so it doesn't corrupt the display."""
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    units = _iter_tui_units(spec)

    spec_rel = os.path.relpath(spec_path) if spec_path else "(spec)"
    tutorial_name = spec.get("name", "Tutorial")

    def make_layout(unit, right_renderable, footer, right_title="Executed"):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=1),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1),
        )
        header = Text()
        header.append(" spec: ", style="bold cyan")
        header.append(spec_rel, style="bold white")
        header.append(f"    {tutorial_name}", style="dim")
        layout["header"].update(header)
        layout["body"].split_row(
            Layout(Panel(Markdown(unit["md"] or ""), title="Tutorial",
                         border_style="cyan"), name="left"),
            Layout(Panel(right_renderable, title=right_title,
                         border_style="magenta"), name="right"),
        )
        layout["footer"].update(Text(footer, style="dim"))
        return layout

    iterative = getattr(args, "iterative", False)
    keyhint = "[↓/→/space] next   [q] quit" if iterative else "[q] quit   (auto-advancing)"
    quit_requested = {"v": False}

    with Live(console=console, screen=True, auto_refresh=False, transient=False) as live:
        for i, unit in enumerate(units):
            title = unit.get("md", "").splitlines()[0] if unit.get("md") else ""
            footer = f"{i + 1}/{len(units)}   {keyhint}"

            if unit["kind"] != "step" or unit["step"] is None:
                # Prose-only: show it, then advance (wait for key if iterative).
                live.update(make_layout(unit, Text("—", style="dim"), footer), refresh=True)
                if iterative and not _wait_or_quit(live, quit_requested):
                    break
                continue

            step = unit["step"]
            # Show the step with the actual command(s) about to run before
            # executing, so it's clear *what* is running (not just "running…").
            live.update(make_layout(unit, _running_renderable(step),
                                    footer, right_title="Running"), refresh=True)

            # Execute via the shared dispatch path, capturing handler output so
            # prints/subprocess noise don't corrupt the Live display.
            try:
                with _capture_fds():
                    _dispatch_step(step, workdir, results, args, override_flags, spec)
            except StopEarly:
                # Surface the failure in the pane, then stop.
                live.update(make_layout(unit, _execs_to_renderable(
                    collector.execs_for(step)), footer + "  — stopped (fail-fast)"),
                    refresh=True)
                if iterative:
                    _wait_or_quit(live, quit_requested)
                raise

            live.update(make_layout(unit, _execs_to_renderable(
                collector.execs_for(step)), footer), refresh=True)

            if iterative:
                if not _wait_or_quit(live, quit_requested):
                    break
            else:
                # Brief pause so fast steps are perceptible; longer if it failed.
                failed = any(e.get("status") == "fail" for e in collector.execs_for(step))
                time.sleep(1.2 if failed else 0.35)

        if not quit_requested["v"]:
            # Final summary screen.
            s = results
            summary = Text()
            summary.append(f"\n  {s.passed} passed", style="bold green")
            if s.failed:
                summary.append(f"   {s.failed} failed", style="bold red")
            if s.skipped:
                summary.append(f"   {s.skipped} skipped", style="bold yellow")
            summary.append("\n\n  Press any key to exit.", style="dim")
            live.update(Panel(summary, title="Done", border_style="cyan"), refresh=True)
            _read_single_key()


def _wait_or_quit(live, quit_requested):
    """Block for a keypress in iterative mode. Returns False if the user quit."""
    key = _read_single_key()
    if key == "quit":
        quit_requested["v"] = True
        return False
    return True


import contextlib


@contextlib.contextmanager
def _capture_fds():
    """Redirect stdout+stderr (at the fd level, so subprocesses are caught too)
    to a temp file for the duration of the block. Keeps handler/subprocess
    output from corrupting the rich Live display."""
    import tempfile as _tf
    saved_out, saved_err = os.dup(1), os.dup(2)
    tmp = _tf.TemporaryFile(mode="w+b")
    try:
        os.dup2(tmp.fileno(), 1)
        os.dup2(tmp.fileno(), 2)
        yield tmp
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        tmp.close()


def write_html_report(collector, output_path, results):
    import json as _json
    model = build_report_model(collector)
    payload = {
        "generated_platform": f"{platform.system()}",
        "summary": {
            "passed": results.passed,
            "failed": results.failed,
            "skipped": results.skipped,
        },
        "tutorials": model,
    }
    data_json = _json.dumps(payload)
    # Close any literal </script> in the data so it can't terminate the tag.
    data_json = data_json.replace("</", "<\\/")

    html = _REPORT_HTML_TEMPLATE.replace("__DATA__", data_json)
    with open(output_path, "w") as f:
        f.write(html)


_REPORT_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tutorial Execution Report</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
    --pass: #2ea043; --fail: #f85149; --info: #d29922;
    --code-bg: #0b0f14;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 14px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  header {
    position: sticky; top: 0; z-index: 10; background: var(--panel);
    border-bottom: 1px solid var(--border); padding: 12px 20px;
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  .pill { padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .pill.pass { background: rgba(46,160,67,.15); color: var(--pass); }
  .pill.fail { background: rgba(248,81,73,.15); color: var(--fail); }
  .pill.skip { background: rgba(210,153,34,.15); color: var(--info); }
  select { background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 4px 8px; }
  main { max-width: 1600px; margin: 0 auto; padding: 16px; }
  .tutorial-title { font-size: 20px; font-weight: 700; margin: 24px 0 8px; color: #fff; }
  .row {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0;
    border: 1px solid var(--border); border-radius: 8px; margin: 10px 0; overflow: hidden;
  }
  .row.preamble, .row.section { grid-template-columns: 1fr; }
  .col { padding: 14px 18px; min-width: 0; }
  .col.left { border-right: 1px solid var(--border); }
  .row.preamble .col.left, .row.section .col.left { border-right: none; }
  .col.right { background: var(--panel); }
  /* A row containing any failed step is tinted red end-to-end so it's
     impossible to miss when scanning the report. */
  .row.has-fail { border-color: var(--fail); box-shadow: 0 0 0 1px var(--fail); }
  .row.has-fail .col.left { background: rgba(248,81,73,.07); border-right-color: var(--fail); }
  .row.has-fail .col.right { background: rgba(248,81,73,.12); }
  .col-label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 8px; }
  .md :first-child { margin-top: 0; }
  .md h1 { font-size: 22px; } .md h2 { font-size: 18px; } .md h3 { font-size: 15px; }
  .md pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 12px; overflow-x: auto; }
  .md code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; }
  .md :not(pre) > code { background: rgba(110,118,129,.2); padding: .15em .4em; border-radius: 4px; }
  .md table { border-collapse: collapse; margin: 8px 0; }
  .md th, .md td { border: 1px solid var(--border); padding: 5px 10px; }
  .md blockquote { border-left: 3px solid var(--border); margin: 8px 0; padding: 2px 12px; color: var(--muted); }
  .exec { margin-bottom: 14px; }
  .exec:last-child { margin-bottom: 0; }
  .exec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
  .badge { font-size: 11px; font-weight: 700; padding: 1px 8px; border-radius: 4px; }
  .badge.pass { background: rgba(46,160,67,.15); color: var(--pass); }
  .badge.fail { background: rgba(248,81,73,.15); color: var(--fail); }
  .badge.info { background: rgba(210,153,34,.15); color: var(--info); }
  .kind { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
  .note { color: var(--muted); font-size: 12.5px; margin-bottom: 6px; }
  pre.cmd { background: var(--code-bg); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 6px; padding: 10px 12px; margin: 0 0 6px; overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
  pre.output { background: #010409; border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; margin: 0; overflow-x: auto; max-height: 360px; overflow-y: auto; color: #b9c1ca; }
  pre.cmd, pre.output { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.45; }
  .empty { color: var(--muted); font-style: italic; font-size: 12.5px; }
  details summary { cursor: pointer; color: var(--accent); font-size: 12px; margin-bottom: 4px; }
</style>
</head>
<body>
<header>
  <h1>Tutorial Execution Report</h1>
  <span id="summary"></span>
  <label style="margin-left:auto; font-size:12px; color:var(--muted)">Tutorial
    <select id="picker"></select>
  </label>
</header>
<main id="main"></main>

<script id="report-data" type="application/json">__DATA__</script>
<script>
  const DATA = JSON.parse(document.getElementById("report-data").textContent);
  if (window.marked) { marked.setOptions({ gfm: true, breaks: false }); }
  const mdToHtml = (s) => window.marked ? marked.parse(s || "") : ("<pre>" + (s || "") + "</pre>");

  const sum = DATA.summary;
  document.getElementById("summary").innerHTML =
    `<span class="pill pass">${sum.passed} passed</span> ` +
    (sum.failed ? `<span class="pill fail">${sum.failed} failed</span> ` : "") +
    (sum.skipped ? `<span class="pill skip">${sum.skipped} skipped</span>` : "");

  const picker = document.getElementById("picker");
  DATA.tutorials.forEach((t, i) => {
    const o = document.createElement("option");
    o.value = i; o.textContent = t.meta.name; picker.appendChild(o);
  });

  function execHtml(e) {
    const badge = `<span class="badge ${e.status}">${e.status.toUpperCase()}</span>`;
    const kind = `<span class="kind">${e.kind}${e.exit_code !== undefined ? " · exit " + e.exit_code : ""}</span>`;
    let h = `<div class="exec"><div class="exec-head">${badge}${kind}</div>`;
    if (e.note) h += `<div class="note">${escapeHtml(e.note)}</div>`;
    if (e.cmd) h += `<pre class="cmd">${escapeHtml(e.cmd)}</pre>`;
    const out = (e.output || "").trim();
    if (out) {
      const long = out.split("\n").length > 12;
      if (long) {
        h += `<details><summary>output (${out.split("\n").length} lines)</summary><pre class="output">${escapeHtml(out)}</pre></details>`;
      } else {
        h += `<pre class="output">${escapeHtml(out)}</pre>`;
      }
    }
    h += `</div>`;
    return h;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  function render(idx) {
    const t = DATA.tutorials[idx];
    const main = document.getElementById("main");
    main.innerHTML = "";
    const h = document.createElement("div");
    h.className = "tutorial-title";
    h.textContent = t.meta.name + "  —  " + t.meta.platform;
    main.appendChild(h);

    t.rows.forEach(row => {
      const isStructural = row.execs.length === 0 &&
        (/^#\s|^##\s/.test(row.md.trim()));
      const div = document.createElement("div");
      const hasExec = row.execs.length > 0;
      const hasFail = row.execs.some(e => e.status === "fail");
      div.className = "row" + (hasExec ? "" : (isStructural ? " section" : " preamble")) +
        (hasFail ? " has-fail" : "");

      const left = document.createElement("div");
      left.className = "col left";
      left.innerHTML = `<div class="md">${mdToHtml(row.md)}</div>`;
      div.appendChild(left);

      if (hasExec || !isStructural) {
        const right = document.createElement("div");
        right.className = "col right";
        if (hasExec) {
          right.innerHTML = `<div class="col-label">Executed</div>` +
            row.execs.map(execHtml).join("");
        } else {
          right.innerHTML = `<div class="col-label">Executed</div>` +
            `<div class="empty">No commands run for this step.</div>`;
        }
        div.appendChild(right);
      }
      main.appendChild(div);
    });
  }

  picker.addEventListener("change", () => render(+picker.value));
  render(0);
</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE COMMAND
# ══════════════════════════════════════════════════════════════════════════════

LANG_MAP = {
    ".c": "c",
    ".h": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".json": "json",
    ".nix": "nix",
    ".qml": "qml",
    ".rep": "rep",
    ".mjs": "javascript",
    ".js": "javascript",
    ".cmake": "cmake",
}


def lang_for_path(path, explicit=None):
    if explicit:
        return explicit
    _, ext = os.path.splitext(path)
    if not ext and os.path.basename(path) == "CMakeLists.txt":
        return "cmake"
    return LANG_MAP.get(ext, "")


def cmd_generate(args):
    spec_path = os.path.abspath(args.spec)
    spec_dir = os.path.dirname(spec_path)

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    release = args.release if args.release is not None else spec.get("release", "")
    set_release(release)

    if args.output:
        output_path = os.path.abspath(args.output)
    else:
        output_name = spec.get("output", "")
        if not output_name:
            print("ERROR: No output file specified (use -o or set 'output:' in YAML)",
                  file=sys.stderr)
            sys.exit(2)
        output_path = os.path.normpath(os.path.join(spec_dir, "..", output_name))

    lines = []

    def emit(text=""):
        lines.append(text)

    def emit_block(text):
        for line in text.rstrip("\n").split("\n"):
            lines.append(line)

    # ── Title ─────────────────────────────────────────────────────────────
    emit(f"# {spec.get('name', 'Tutorial')}")
    emit()

    # ── Intro ─────────────────────────────────────────────────────────────
    intro = spec.get("intro", "")
    if intro:
        emit_block(intro)
        emit()

    # ── What you'll build ─────────────────────────────────────────────────
    what_build = spec.get("what_you_build", "")
    if what_build:
        emit(f"**What you'll build:** {what_build}")
        emit()

    # ── What you'll learn ─────────────────────────────────────────────────
    items = spec.get("what_you_learn", [])
    if items:
        emit("**What you'll learn:**")
        emit()
        for item in items:
            emit(f"- {item}")
        emit()

    # ── Comparison table ──────────────────────────────────────────────────
    comparison = spec.get("comparison", "")
    if comparison:
        emit_block(comparison)
        emit()

    # ── Prerequisites ─────────────────────────────────────────────────────
    prereqs = spec.get("prerequisites", [])
    if prereqs:
        emit("## Prerequisites")
        emit()
        for p in prereqs:
            emit(f"- {p}")
        emit()
        emit("---")
        emit()

    # ── Sections ──────────────────────────────────────────────────────────
    step_number = 1

    all_sections = spec.get("sections", [])
    for si, section in enumerate(all_sections):
        sec_title = section.get("title", "")
        is_step = section.get("step", False)
        is_last = (si == len(all_sections) - 1)
        show_sep = is_step and not is_last

        if is_step:
            emit(f"## Step {step_number}: {sec_title}")
            step_number += 1
        else:
            emit(f"## {sec_title}")
        emit()

        sec_text = section.get("text", "")
        if sec_text:
            emit_block(expand_vars(sec_text))
            emit()

        # ── Logoscore section ─────────────────────────────────────────
        logoscore_spec = section.get("logoscore")
        if logoscore_spec:
            setup_cmds = logoscore_spec.get("setup", [])
            tests = logoscore_spec.get("tests", [])

            if setup_cmds:
                emit("First, prepare the module for loading:")
                emit()
                emit("```bash")
                for cmd in setup_cmds:
                    emit(cmd)
                emit("```")
                emit()

            if tests:
                emit("Call methods and verify results:")
                emit()
                emit("```bash")
                for i, t in enumerate(tests):
                    call = t.get("call", "")
                    expect = t.get("expect", "")
                    emit(f'logoscore -m ./modules -l calc_module -c "{call}"')
                    emit(f"# Expected: {expect}")
                    if i < len(tests) - 1:
                        emit()
                emit("```")
                emit()

            if show_sep:
                emit("---")
                emit()
            continue

        # ── Basecamp section ──────────────────────────────────────────
        basecamp_spec = section.get("basecamp")
        if basecamp_spec:
            install_as = basecamp_spec.get("install_as", "")
            tests = basecamp_spec.get("tests", [])

            if install_as:
                emit(f"Install the module as a **{install_as}** module, then verify:")
                emit()

            if tests:
                for t in tests:
                    emit(f"- {t.get('name', '')}")
                emit()

            if show_sep:
                emit("---")
                emit()
            continue

        # ── Steps ─────────────────────────────────────────────────────
        steps = section.get("steps", [])
        if not steps:
            if show_sep:
                emit("---")
                emit()
            continue

        sub_step = 1
        sec_num = step_number - 1 if is_step else None

        for step in steps:
            title = step.get("title", "")
            if title:
                if sec_num is not None:
                    emit(f"### {sec_num}.{sub_step} {title}")
                    sub_step += 1
                else:
                    emit(f"### {title}")
                emit()

            text = step.get("text", "")
            if text:
                emit_block(expand_vars(text))
                emit()

            # file action
            file_spec = step.get("file", {})
            if file_spec:
                path = file_spec.get("path", "")
                encoding = file_spec.get("encoding", "")
                lang = lang_for_path(path, file_spec.get("language"))

                if encoding == "base64":
                    emit(f"*Binary file: `{path}`*")
                else:
                    emit(f"```{lang}")
                    content = file_spec.get("content", "")
                    emit_block(expand_vars(content))
                    emit("```")
                emit()

            # run action
            run_cmd_str = step.get("run", "")
            if run_cmd_str:
                code_block = step.get("code_block", "")
                emit("```bash")
                if code_block:
                    emit_block(expand_vars(code_block))
                else:
                    emit(expand_vars(run_cmd_str))
                emit("```")
                emit()

            # ui_test: render launch command if present
            ui_test_spec = step.get("ui_test", {})
            if ui_test_spec:
                launch = ui_test_spec.get("launch", "")
                if launch:
                    emit("```bash")
                    emit(expand_vars(launch))
                    emit("```")
                    emit()
                for img in _screenshot_md_lines(ui_test_spec):
                    emit(img)
                    emit()

            # check_file is runner-only verification, not rendered in markdown

            # post_text
            post_text = step.get("post_text", "")
            if post_text:
                emit_block(expand_vars(post_text))
                emit()

            # extra_run (continuation command under the same heading)
            extra = step.get("extra_run", {})
            if extra:
                extra_code = extra.get("code_block", "")
                extra_cmd = extra.get("run", "")
                emit("```bash")
                if extra_code:
                    emit_block(expand_vars(extra_code))
                elif extra_cmd:
                    emit(expand_vars(extra_cmd))
                emit("```")
                emit()
                extra_post = extra.get("post_text", "")
                if extra_post:
                    emit_block(expand_vars(extra_post))
                    emit()

        if show_sep:
            emit("---")
            emit()

    # Clean up triple+ blank lines to double
    output_text = "\n".join(lines).rstrip() + "\n"
    while "\n\n\n" in output_text:
        output_text = output_text.replace("\n\n\n", "\n\n")

    with open(output_path, "w") as f:
        f.write(output_text)

    print(f"Generated: {output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="tutorial_runner",
        description="Tutorial Runner & Markdown Generator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── run ───────────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser("run", help="Execute a tutorial spec")
    run_parser.add_argument("spec", help="Path to the YAML spec file")
    run_parser.add_argument("--keep-workdir", action="store_true",
                            help="Don't delete the temp working directory on exit")
    run_parser.add_argument("--workdir", default=None,
                            help="Use existing directory instead of creating a fresh one")
    run_parser.add_argument("--output-dir", default=None, metavar="DIR",
                            help="Run into DIR and keep the result (never deleted). "
                                 "For chained tutorials DIR becomes the chain root and "
                                 "each project lands in DIR/<project_name>/. Created if missing.")
    run_parser.add_argument("--verbose", action="store_true",
                            help="Print commands as they execute")
    run_parser.add_argument("--basecamp-bin", default="",
                            help="Path to LogosBasecamp binary")
    run_parser.add_argument("--qt-mcp", default="",
                            help="Path to logos-qt-mcp package")
    run_parser.add_argument("--call-timeout", type=int, default=60,
                            help="Timeout for logoscore calls (default: 60)")
    run_parser.add_argument("--continue-on-fail", action="store_true",
                            help="Don't stop at the first failure (default: stop)")
    run_parser.add_argument("--release", default=None,
                            help="Git tag for GitHub URLs (overrides spec's 'release' field)")
    run_parser.add_argument("--report", default=None, metavar="PATH",
                            help="Write a two-column HTML report (rendered tutorial + "
                                 "the commands actually run and their output) to PATH")
    run_parser.add_argument("--tui", action="store_true",
                            help="Run in an interactive two-column TUI (left: rendered "
                                 "tutorial, right: the command running and its output). "
                                 "Requires the 'rich' package.")
    run_parser.add_argument("--iterative", action="store_true",
                            help="With --tui, wait for a keypress (down/right arrow or "
                                 "space) before executing each step instead of "
                                 "auto-advancing")

    # ── generate ──────────────────────────────────────────────────────────
    gen_parser = subparsers.add_parser("generate", help="Generate markdown from a spec")
    gen_parser.add_argument("spec", help="Path to the YAML spec file")
    gen_parser.add_argument("-o", "--output", default=None,
                            help="Output file path (default: uses spec's 'output' field)")
    gen_parser.add_argument("--release", default=None,
                            help="Git tag for GitHub URLs (overrides spec's 'release' field)")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "generate":
        cmd_generate(args)


if __name__ == "__main__":
    main()
