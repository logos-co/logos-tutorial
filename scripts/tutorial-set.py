#!/usr/bin/env python3
"""Read tutorial-set.json: the repos the specs build against, and what CI runs.

Every `github:<owner>/<repo>{release}` URL in tests/*.test.yaml is pinned by
this file. A repo with an empty `ref` tracks its default branch (or a global
`--release TAG`); a non-empty `ref` (tag or commit) is passed to doctest as
`--release-for <repo>=<ref>`.

An override file — a JSON object of {repo: ref} — replaces individual refs.
logos-release-set uses it to run the tutorial against the versions it pins.

    python3 scripts/tutorial-set.py check
    python3 scripts/tutorial-set.py doctest-args [--override FILE]
    python3 scripts/tutorial-set.py pins [--override FILE] [--format markdown|json]
    python3 scripts/tutorial-set.py matrix
"""

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNERS = {
    "linux-x86_64": "ubuntu-latest",
    "linux-arm64": "ubuntu-24.04-arm",
    "macos-arm64": "macos-latest",
}

# Same shape doctest matches: the repo segment is whatever precedes {release}.
PINNED_URL = re.compile(r"github:([^/\s]+)/([^/\s{]+)\{release\}")
ANY_URL = re.compile(r"github:([^/\s\"'`]+)/([A-Za-z0-9_.-]+)(\{release\})?")
REF = re.compile(r"^[A-Za-z0-9_./-]*$")


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_override(path):
    if not path:
        return {}
    override = load(path)
    if not isinstance(override, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in override.items()):
        sys.exit(f"error: {path} must be a JSON object of {{repo: ref}} strings")
    return override


def effective_pins(spec, override):
    """[(name, repo, ref, source)] with the override applied."""
    pins = []
    for item in spec["repos"]:
        if item["name"] in override:
            pins.append((item["name"], item["repo"], override[item["name"]], "override"))
        else:
            pins.append((item["name"], item["repo"], item["ref"], "tutorial-set.json"))
    unknown = sorted(set(override) - {item["name"] for item in spec["repos"]})
    if unknown:
        print(f"note: override names repos the tutorial does not use: {', '.join(unknown)}",
              file=sys.stderr)
    return pins


def spec_files():
    return sorted(glob.glob(os.path.join(ROOT, "tests", "*.test.yaml")))


def check(spec):
    errors = []
    repos = {item["name"]: item for item in spec["repos"]}
    for item in spec["repos"]:
        if item["repo"].split("/")[-1] != item["name"]:
            errors.append(f"repos[{item['name']}]: name must be the repo's last path segment")
        if not REF.match(item["ref"]):
            errors.append(f"repos[{item['name']}]: ref {item['ref']!r} is not a tag or commit")

    for name in spec["specs"]:
        if not os.path.exists(os.path.join(ROOT, "tests", f"{name}.test.yaml")):
            errors.append(f"specs: tests/{name}.test.yaml does not exist")
    for platform in spec["platforms"]:
        if platform not in RUNNERS:
            errors.append(f"platforms: unknown {platform!r}; known: {', '.join(RUNNERS)}")

    used = set()
    for path in spec_files():
        rel = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                for owner, name, pinned in ANY_URL.findall(line):
                    if name not in repos:
                        if pinned:
                            errors.append(f"{rel}:{lineno}: github:{owner}/{name}{{release}} "
                                          f"is not listed in tutorial-set.json")
                        continue
                    if f"{owner}/{name}" != repos[name]["repo"]:
                        continue
                    if pinned:
                        used.add(name)
                    else:
                        # A pinned repo referenced without {release} silently
                        # builds the default branch whatever the pin says.
                        errors.append(f"{rel}:{lineno}: github:{owner}/{name} has no "
                                      f"{{release}}, so its pin does not apply")
    for name in sorted(set(repos) - used):
        errors.append(f"repos[{name}]: no spec references github:{repos[name]['repo']}{{release}}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "doctest-args", "pins", "matrix"))
    parser.add_argument("--set", default=os.path.join(ROOT, "tutorial-set.json"))
    parser.add_argument("--override", default=None,
                        help="JSON object of {repo: ref} that replaces individual pins")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()

    spec = load(args.set)

    if args.command == "check":
        errors = check(spec)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if errors:
            return 1
        print(f"{os.path.relpath(args.set)}: OK", file=sys.stderr)
        return 0

    if args.command == "matrix":
        # `id` drops the tutorial- prefix: it names the CI jobs and report URLs.
        include = [{"spec": s, "id": s.removeprefix("tutorial-"),
                    "platform": p, "runner": RUNNERS[p]}
                   for s in spec["specs"] for p in spec["platforms"]]
        print(json.dumps({"include": include}))
        return 0

    pins = effective_pins(spec, load_override(args.override))
    for name, _, ref, source in pins:
        if not REF.match(ref):
            sys.exit(f"error: {source} pins {name} to {ref!r}, which is not a tag or commit")

    if args.command == "doctest-args":
        # One line, space-separated: refs never contain whitespace.
        print(" ".join(f"--release-for={name}={ref}" for name, _, ref, _ in pins if ref))
    elif args.format == "json":
        print(json.dumps([{"name": n, "repo": r, "ref": ref, "source": s}
                          for n, r, ref, s in pins], indent=2))
    else:
        print("| Repo | Ref | From |\n|---|---|---|")
        for name, repo, ref, source in pins:
            shown = f"`{ref}`" if ref else "default branch"
            print(f"| [{name}](https://github.com/{repo}) | {shown} | {source} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
