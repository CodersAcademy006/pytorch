#!/usr/bin/env python3
"""Map changed files to which riscv64.yml suites actually need to run.

Conservative by design: any change that isn't recognized, or any failure to
compute a diff at all (shallow clone, new branch, manual dispatch), makes
every suite run. This only ever *skips* work it can positively justify
skipping; it never invents a reason to skip.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Suite -> path globs (relative to repo root) that suite's checks touch.
SUITE_PATTERNS: dict[str, list[str]] = {
    "cross": ["c10/*", "c10/**/*", "aten/src/ATen/core/*", "aten/src/ATen/core/**/*"],
    "kernels": ["aten/src/ATen/native/cpu/*", "aten/src/ATen/native/cpu/**/*"],
    "compiler": [
        "torch/_inductor/*",
        "torch/_inductor/**/*",
        "torch/_dynamo/*",
        "torch/_dynamo/**/*",
    ],
    "backend": [
        "third_party/triton/*",
        "third_party/triton/**/*",
        "third_party/*ilelang*/**/*",
    ],
}

# Changes here mean "the harness itself changed" -> every suite must run
# regardless of which suite-specific paths also changed, since the harness
# is shared code all suites depend on.
HARNESS_PATTERNS = [".ci/riscv/*", ".ci/riscv/**/*", ".github/workflows/riscv64.yml"]

# Changes here could affect a full cross-build (not this lightweight
# harness) -- surfaced as a suggestion, never auto-forced, since the user
# can always force it explicitly via workflow_dispatch.
FULL_BUILD_PATTERNS = [
    "CMakeLists.txt",
    "cmake/*",
    "cmake/**/*",
    "setup.py",
    "pyproject.toml",
    ".ci/pytorch/build.sh",
    ".ci/docker/ubuntu-cross-riscv/*",
    ".ci/docker/ubuntu-cross-riscv/**/*",
]


def changed_files(base: str, head: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
        return [line for line in out.splitlines() if line]
    except subprocess.CalledProcessError:
        return None


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def analyze(files: list[str] | None) -> dict[str, object]:
    if files is None:
        return {
            "mode": "unresolvable-diff",
            "run": dict.fromkeys(SUITE_PATTERNS, True),
            "suggest_full_build": True,
            "changed_files": [],
        }

    harness_changed = any(matches_any(f, HARNESS_PATTERNS) for f in files)
    run = {}
    for suite, patterns in SUITE_PATTERNS.items():
        run[suite] = harness_changed or any(matches_any(f, patterns) for f in files)

    # A change matching none of the known categories (e.g. docs, an
    # unrelated test file) is not a reason to skip everything -- but a
    # change matching *some* category and nothing else legitimately lets
    # the others skip. If literally nothing recognized changed at all
    # (e.g. a README-only diff), still run everything: absence of a
    # recognized pattern is not proof of absence of relevance.
    if not any(run.values()) and not harness_changed:
        run = dict.fromkeys(SUITE_PATTERNS, True)
        mode = "unrecognized-changes-default-all"
    else:
        mode = "targeted"

    suggest_full_build = harness_changed or any(
        matches_any(f, FULL_BUILD_PATTERNS) for f in files
    )

    return {
        "mode": mode,
        "run": run,
        "suggest_full_build": suggest_full_build,
        "changed_files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--force-full", action="store_true")
    args = parser.parse_args()

    if args.force_full:
        result = {
            "mode": "forced",
            "run": dict.fromkeys(SUITE_PATTERNS, True),
            "suggest_full_build": True,
            "changed_files": [],
        }
    else:
        result = analyze(changed_files(args.base, args.head))

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.writelines(
                f"run_{suite}={'true' if should_run else 'false'}\n"
                for suite, should_run in result["run"].items()
            )
            fh.write(
                f"suggest_full_build={'true' if result['suggest_full_build'] else 'false'}\n"
            )

    lines = [
        "# RISC-V impact analysis",
        "",
        f"- Mode: `{result['mode']}`",
        f"- Suggest full cross-build: `{result['suggest_full_build']}`",
        "",
        "| Suite | Run |",
        "|---|---|",
    ]
    for suite, should_run in result["run"].items():
        lines.append(f"| `{suite}` | {'run' if should_run else 'skipped'} |")
    if result["changed_files"]:
        lines.append("")
        lines.append(
            f"<details><summary>{len(result['changed_files'])} changed file(s)</summary>\n"
        )
        lines.extend(f"- `{f}`" for f in result["changed_files"][:200])
        lines.append("\n</details>")
    report = "\n".join(lines) + "\n"

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    else:
        print(report)

    print(json.dumps(result, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
