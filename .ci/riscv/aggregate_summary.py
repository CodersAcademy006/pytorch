#!/usr/bin/env python3
"""Roll up all riscv64 matrix-leg artifacts into one job summary and one
canonical test-times.json, reusing tools/stats/generate_test_times_from_reports.py
(the same script PR #181109 added for external-arch CI) instead of
reimplementing JUnit aggregation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.stats.generate_test_times_from_reports import _build_payload, collect_times


def suite_counts(artifacts_dir: Path) -> list[dict[str, object]]:
    rows = []
    for xml_path in sorted(artifacts_dir.rglob("riscv-*.xml")):
        suite = ET.parse(xml_path).getroot()
        rows.append(
            {
                "name": suite.get("name", xml_path.stem),
                "tests": int(suite.get("tests", 0)),
                "failures": int(suite.get("failures", 0)),
                "skipped": int(suite.get("skipped", 0)),
                "time": float(suite.get("time", 0.0)),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--job-name", default="riscv64")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = suite_counts(args.artifacts_dir)

    module_times, class_times = collect_times(args.artifacts_dir)
    for name, path in (
        ("test-times.json", module_times),
        ("test-class-times.json", class_times),
    ):
        (args.output_dir / name).write_text(
            json.dumps(_build_payload(path, args.job_name, "default"), indent=2),
            encoding="utf-8",
        )

    total_tests = sum(r["tests"] for r in rows)
    total_fail = sum(r["failures"] for r in rows)
    total_skip = sum(r["skipped"] for r in rows)
    lines = [
        "# RISC-V CI rollup",
        "",
        f"- Suites: `{len(rows)}`",
        f"- Tests: `{total_tests}` (failed=`{total_fail}`, skipped=`{total_skip}`)",
        f"- test-times.json / test-class-times.json regenerated via "
        f"`tools/stats/generate_test_times_from_reports.py` from {len(rows)} JUnit report(s)",
        "",
        "| Suite | Tests | Failed | Skipped | Seconds |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['name']}` | {r['tests']} | {r['failures']} | {r['skipped']} | {r['time']:.3f} |"
        )
    report = "\n".join(lines) + "\n"
    (args.output_dir / "rollup.md").write_text(report, encoding="utf-8")

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as fh:
            fh.write(report)

    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
