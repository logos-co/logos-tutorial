#!/usr/bin/env python3
"""
Tutorial Runner & Markdown Generator

Executes YAML tutorial specs (write files, run commands, build, inspect, test)
and generates .md documentation from them.

Usage:
    tutorial_runner.py run <spec.yaml> [OPTIONS]
    tutorial_runner.py generate <spec.yaml> [-o output.md]

Run options:
    --keep-workdir        Don't delete the temp working directory on exit
    --workdir <path>      Use existing directory instead of creating a fresh one
    --verbose             Print commands as they execute
    --basecamp-bin <path> Path to LogosBasecamp binary (for basecamp sections)
    --qt-mcp <path>       Path to logos-qt-mcp package (for basecamp/ui_test sections)
    --call-timeout <sec>  Timeout for logoscore calls (default: 60)

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


# ── Variable Expansion ────────────────────────────────────────────────────────

RELEASE_TAG = ""


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
    else:
        results.fail(f"write {path}", "file was not created")


def _exec_run(cmd, title, workdir, results, verbose, override_flags, expect_contains=None):
    """Execute a single run command with optional output assertions."""
    cmd = expand_vars(cmd)
    cmd = inject_nix_overrides(cmd, override_flags)
    expect_contains = expect_contains or []

    rc, output = run_cmd(cmd, workdir, verbose, capture=True)

    if rc != 0:
        if output and output.strip():
            lines = output.strip().split("\n")
            tail = lines[-20:]
            if len(lines) > 20:
                print(f"        {dim(f'... ({len(lines) - 20} lines omitted)')}")
            for line in tail:
                print(f"        {dim(line)}")
        results.fail(title, f"command failed with exit code {rc}")
        return

    if expect_contains:
        all_found = True
        for expected in expect_contains:
            if expected not in output:
                trimmed = output.strip()
                out_msg = trimmed[:500] if trimmed else "(empty)"
                results.fail(title, f"expected '{expected}' not found in output\n        actual:   {out_msg}")
                all_found = False
                break
        if all_found:
            results.pass_(title)
    else:
        results.pass_(title)


def handle_run(step, workdir, results, verbose, override_flags):
    cmd = step.get("run", "")
    if not cmd:
        return
    title = step.get("title", cmd)
    _exec_run(cmd, title, workdir, results, verbose, override_flags,
              step.get("expect_contains", []))

    extra = step.get("extra_run", {})
    if extra:
        extra_cmd = extra.get("run", "")
        if extra_cmd:
            _exec_run(extra_cmd, f"{title} (verify)", workdir, results, verbose,
                      override_flags, extra.get("expect_contains", []))


def handle_check_file(step, workdir, results, verbose):
    pattern = step.get("check_file", "")
    if not pattern:
        return
    title = step.get("title", f"check {pattern}")
    pattern = expand_vars(pattern)
    full_pattern = os.path.join(workdir, pattern)
    matches = glob.glob(full_pattern)
    if matches:
        results.pass_(title)
    else:
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

def generate_mjs_tests(tests, qt_mcp_path, test_name, output_path):
    """Generate a .mjs test file from YAML test actions for logos-qt-mcp."""
    import json as _json

    with open(output_path, "w") as f:
        f.write('import { resolve } from "node:path";\n')
        f.write(f'const qtMcpRoot = "{qt_mcp_path}";\n')
        f.write('const { test, run } = await import(resolve(qtMcpRoot, "test-framework/framework.mjs"));\n\n')
        f.write(f'test("{test_name}", async (app) => {{\n')

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

        f.write('});\n\nrun();\n')

    return output_path


# ── UI Test Handler ──────────────────────────────────────────────────────────

import signal
import socket
import time


def _wait_for_inspector(host="localhost", port=3768, timeout=60):
    """Poll until the QML inspector TCP port accepts connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


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

    # Generate .mjs test file
    test_name = f"{spec.get('name', 'tutorial')}: {title}"
    mjs_path = generate_mjs_tests(
        tests, qt_mcp, test_name,
        os.path.join(workdir, "ui-test.mjs")
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

        print(f"  Launching: {launch_cmd}")
        app_proc = subprocess.Popen(
            launch_cmd, shell=True, cwd=workdir, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

        try:
            port = ui_spec.get("inspector_port", 3768)
            print(f"  Waiting for inspector on port {port}...")
            if not _wait_for_inspector(port=port, timeout=90):
                results.fail(title, f"inspector not available on port {port} after 90s")
                return

            print(f"  Running UI tests ({len(tests)} actions)...")
            cmd = f'node "{mjs_path}" --verbose'
            rc, output = run_cmd(cmd, workdir, verbose, capture=True, timeout=120)
            if rc == 0:
                results.pass_(title)
            else:
                results.fail(title, "UI tests failed")
                trimmed = output.strip()[-800:] if output else "(no output)"
                print(f"        {dim(trimmed)}")
        finally:
            try:
                os.killpg(os.getpgid(app_proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            app_proc.wait(timeout=10)

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
            results.pass_(title)
        else:
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
            if step.get("file"):
                handle_file(step, workdir, results, args.verbose)
            elif step.get("run"):
                handle_run(step, workdir, results, args.verbose, override_flags)
            elif step.get("ui_test"):
                handle_ui_test(step, workdir, results, args.verbose,
                               override_flags, args.qt_mcp, spec)
            elif step.get("check_file"):
                handle_check_file(step, workdir, results, args.verbose)
            elif args.verbose:
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

    if args.workdir:
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
        if not args.keep_workdir:
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

    if args.keep_workdir or args.workdir:
        print(f"  workdir: {root_dir or workdir}")

    ok = results.summary()

    try:
        cleanup()
    except Exception:
        pass

    sys.exit(0 if ok else 1)


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
