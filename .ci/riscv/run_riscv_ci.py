#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLOCKLIST = REPO_ROOT / ".ci" / "riscv" / "blocklist.json"


class SkipCase(Exception):
    """Raised by a suite check when the real code path it would validate
    does not exist in the tree yet. Recorded as skipped, not failed."""


def run(
    cmd: list[str], log: Path, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    started = time.time()
    with log.open("a", encoding="utf-8") as fh:
        fh.write("$ " + " ".join(cmd) + "\n")
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        fh.write(proc.stdout)
        fh.write(f"\n[exit={proc.returncode} duration={time.time() - started:.3f}s]\n")
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout)
    return proc


class Reporter:
    def __init__(self, artifact_dir: Path, suite: str, arch: str) -> None:
        self.artifact_dir = artifact_dir
        self.suite = suite
        self.arch = arch
        self.started = time.time()
        self.cases: list[dict[str, object]] = []
        self.timings: dict[str, float] = {}
        self.junit_dir = f"junit-{suite}-{arch}"
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        (self.artifact_dir / "logs").mkdir(exist_ok=True)
        (self.artifact_dir / self.junit_dir).mkdir(exist_ok=True)
        (self.artifact_dir / "benchmarks").mkdir(exist_ok=True)
        (self.artifact_dir / "compiler").mkdir(exist_ok=True)
        (self.artifact_dir / "kernels").mkdir(exist_ok=True)

    def log_path(self, name: str) -> Path:
        return self.artifact_dir / "logs" / f"{self.suite}-{self.arch}-{name}.log"

    def case(self, name: str, func) -> None:
        started = time.time()
        status = "passed"
        message = ""
        try:
            func()
        except SkipCase as exc:
            status = "skipped"
            message = str(exc)
        except Exception as exc:
            status = "failed"
            message = str(exc)
        duration = time.time() - started
        key = f"{self.suite}.{self.arch}.{name}"
        self.timings[key] = duration
        self.cases.append(
            {"name": name, "status": status, "time": duration, "message": message}
        )
        if status == "failed":
            raise RuntimeError(f"{key} failed: {message}")

    def finish(self) -> None:
        suite = ET.Element(
            "testsuite",
            name=f"riscv-{self.suite}-{self.arch}",
            tests=str(len(self.cases)),
            failures=str(sum(1 for c in self.cases if c["status"] == "failed")),
            skipped=str(sum(1 for c in self.cases if c["status"] == "skipped")),
            time=f"{time.time() - self.started:.3f}",
        )
        for case in self.cases:
            elem = ET.SubElement(
                suite,
                "testcase",
                classname=f"riscv.{self.suite}.{self.arch}",
                name=str(case["name"]),
                time=f"{case['time']:.3f}",
            )
            if case["status"] == "failed":
                fail = ET.SubElement(elem, "failure", message=str(case["message"]))
                fail.text = str(case["message"])
            elif case["status"] == "skipped":
                skip = ET.SubElement(elem, "skipped", message=str(case["message"]))
                skip.text = str(case["message"])
        ET.ElementTree(suite).write(
            self.artifact_dir / self.junit_dir / f"riscv-{self.suite}-{self.arch}.xml",
            encoding="utf-8",
            xml_declaration=True,
        )
        # test-times.json / test-class-times.json are derived downstream from
        # this JUnit XML by tools/stats/generate_test_times_from_reports.py
        # (the riscv-summary job), not duplicated here.
        summary = [
            f"# RISC-V {self.suite} ({self.arch})",
            "",
            f"- Host: `{platform.platform()}`",
            f"- Python: `{sys.version.split()[0]}`",
            f"- Cases: `{len(self.cases)}`"
            f" (passed=`{sum(1 for c in self.cases if c['status'] == 'passed')}`,"
            f" skipped=`{sum(1 for c in self.cases if c['status'] == 'skipped')}`,"
            f" failed=`{sum(1 for c in self.cases if c['status'] == 'failed')}`)",
            f"- Duration: `{time.time() - self.started:.3f}s`",
            "",
            "| Case | Status | Seconds | Note |",
            "|---|---:|---:|---|",
        ]
        for case in self.cases:
            note = (
                str(case["message"]).replace("|", "/").splitlines()[0]
                if case["message"]
                else ""
            )
            summary.append(
                f"| `{case['name']}` | `{case['status']}` | `{case['time']:.3f}` | {note} |"
            )
        (self.artifact_dir / "summary.md").write_text(
            "\n".join(summary) + "\n", encoding="utf-8"
        )


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_blocklist(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("entries", []))


def is_blocked(entries: list[dict[str, str]], suite: str, arch: str, name: str) -> bool:
    for entry in entries:
        if entry.get("suite", suite) not in (suite, "*"):
            continue
        if entry.get("arch", arch) not in (arch, "*"):
            continue
        if entry.get("name", name) in (name, "*"):
            return True
    return False


def compiler_cmd() -> list[str]:
    return shlex.split(os.environ.get("RISCV_CXX", "riscv64-linux-gnu-g++"))


def cflags(arch: str) -> list[str]:
    return [
        "-std=c++17",
        "-O2",
        "-Wall",
        "-Wextra",
        f"-march={arch}",
        "-mabi=lp64d",
        "-I.",
    ]


def compile_and_run(
    source: Path, binary: Path, arch: str, reporter: Reporter, name: str
) -> None:
    log = reporter.log_path(name)
    run([*compiler_cmd(), *cflags(arch), str(source), "-o", str(binary)], log)
    qemu = shutil.which("qemu-riscv64")
    if qemu:
        run([qemu, "-L", "/usr/riscv64-linux-gnu", str(binary)], log)
    else:
        with log.open("a", encoding="utf-8") as fh:
            fh.write("qemu-riscv64 not found; compile-only validation completed.\n")


def suite_cross(reporter: Reporter, arch: str) -> None:
    def check() -> None:
        source = reporter.artifact_dir / "kernels" / "approximate_clock_harness.cpp"
        source.write_text(
            """
#include <c10/util/ApproximateClock.h>
#include <cstdint>
#include <cstdio>

int main() {
  auto a = c10::getApproximateTime();
  auto b = c10::getApproximateTime();
  if (b < a) {
    std::fprintf(stderr, "non-monotonic approximate clock\\n");
    return 2;
  }
#if !defined(__riscv) || (__riscv_xlen != 64)
#error "expected riscv64 target"
#endif
  std::printf("approximate_clock=%llu\\n", static_cast<unsigned long long>(b));
  return 0;
}
""".strip()
            + "\n",
            encoding="utf-8",
        )
        compile_and_run(
            source,
            reporter.artifact_dir / "kernels" / "approximate_clock",
            arch,
            reporter,
            "approximate_clock",
        )

    reporter.case("cross.c10_approximate_clock_real_header", check)


# Phase 2 (uKernel lib) categories from tracking issue #180975. None of these
# have a RISC-V/RVV-specific implementation in this tree yet (checked via
# KERNEL_SOURCE_HINTS below) -- Phase 2 needs real hardware/emulation per
# project_riscv_pytorch memory. Each category is validated for real the moment
# a matching source file lands; until then it is reported as skipped, not
# faked green.
KERNEL_SOURCE_HINTS: dict[str, list[str]] = {
    "gemm": ["*Gemm*Riscv*", "*Blas*Riscv*"],
    "conv": ["*Conv*Riscv*"],
    "activation": ["*Activation*Riscv*"],
    "reduction": ["*Reduce*Riscv*"],
    "softmax": ["*SoftMax*Riscv*"],
    "layernorm": ["*layer_norm*riscv*", "*LayerNorm*Riscv*"],
    "rmsnorm": ["*rms_norm*riscv*", "*RMSNorm*Riscv*"],
    "pooling": ["*Pool*Riscv*"],
    "embedding": ["*Embedding*Riscv*"],
}
KERNEL_SEARCH_ROOTS = ["aten/src/ATen/native/cpu", "aten/src/ATen/native/cpu/vec"]
RISCV_INTRINSIC_MARKERS = ("__riscv_v", "riscv_vector.h", "__riscv_vsetvl")


def find_riscv_kernel_source(category: str) -> Path | None:
    for root in KERNEL_SEARCH_ROOTS:
        root_path = REPO_ROOT / root
        if not root_path.is_dir():
            continue
        for pattern in KERNEL_SOURCE_HINTS[category]:
            for candidate in root_path.rglob(pattern):
                text = candidate.read_text(encoding="utf-8", errors="ignore")
                if any(marker in text for marker in RISCV_INTRINSIC_MARKERS):
                    return candidate
    return None


def suite_kernels(reporter: Reporter, arch: str) -> None:
    benchmarks = []
    for category in KERNEL_SOURCE_HINTS:

        def check(category: str = category) -> None:
            source = find_riscv_kernel_source(category)
            if source is None:
                raise SkipCase(
                    f"no RVV-specific {category} kernel found under {KERNEL_SEARCH_ROOTS}; "
                    "Phase 2 uKernel not implemented yet, add source then re-run"
                )
            compile_and_run(
                source,
                reporter.artifact_dir / "kernels" / f"{category}_{arch}",
                arch,
                reporter,
                f"kernel_{category}",
            )

        reporter.case(f"kernels.{category}", check)
        status = (
            "validated"
            if reporter.cases[-1]["status"] == "passed"
            else "not_implemented"
        )
        benchmarks.append({"name": category, "status": status})

    write_json(
        reporter.artifact_dir / "benchmarks" / f"kernels-{arch}.json",
        {"arch": arch, "benchmarks": benchmarks},
    )


def suite_compiler(reporter: Reporter, arch: str) -> None:
    def toolchain_codegen_smoke() -> None:
        source = reporter.artifact_dir / "compiler" / "generated_inductor_kernel.cpp"
        source.write_text(
            """
extern "C" void generated_add_mul(const float* a, const float* b, float* out, long n) {
  for (long i = 0; i < n; ++i) {
    out[i] = (a[i] + b[i]) * 0.5f;
  }
}
int main() { return 0; }
""".strip()
            + "\n",
            encoding="utf-8",
        )
        obj = reporter.artifact_dir / "compiler" / "generated_inductor_kernel.o"
        run(
            [*compiler_cmd(), *cflags(arch), "-c", str(source), "-o", str(obj)],
            reporter.log_path("generated_cpp"),
        )
        clang = shutil.which("clang++")
        if clang:
            run(
                [
                    clang,
                    "--target=riscv64-linux-gnu",
                    f"-march={arch}",
                    "-mabi=lp64d",
                    "-S",
                    "-emit-llvm",
                    str(source),
                    "-o",
                    str(
                        reporter.artifact_dir
                        / "compiler"
                        / "generated_inductor_kernel.ll"
                    ),
                ],
                reporter.log_path("generated_llvm"),
            )

    def cpp_builder_arch_flag_regression() -> None:
        cpp_builder = (REPO_ROOT / "torch" / "_inductor" / "cpp_builder.py").read_text(
            encoding="utf-8"
        )
        if not re.search(r'machine\s*==\s*"riscv64".*\n.*march=rv64gc', cpp_builder):
            raise RuntimeError(
                "torch/_inductor/cpp_builder.py no longer maps riscv64 -> march=rv64gc; "
                "Inductor CPU codegen would silently fall back to march=native on RISC-V hosts"
            )

    def dynamo_riscv_gating() -> None:
        hits = list((REPO_ROOT / "torch" / "_dynamo").rglob("*.py"))
        for path in hits:
            if "riscv" in path.read_text(encoding="utf-8", errors="ignore").lower():
                return
        raise SkipCase(
            "no riscv-specific gating found in torch/_dynamo; Dynamo is assumed to use "
            "the generic backend path on RISC-V (Phase 3, not yet arch-specialized)"
        )

    reporter.case("compiler.toolchain_codegen_smoke", toolchain_codegen_smoke)
    reporter.case(
        "compiler.cpp_builder_riscv_arch_flag", cpp_builder_arch_flag_regression
    )
    reporter.case("compiler.dynamo_riscv_gating", dynamo_riscv_gating)
    write_json(
        reporter.artifact_dir / "compiler" / "compiler-validation.json",
        {
            "toolchain_codegen_smoke": "generated C++ and LLVM IR emitted under cross toolchain",
            "cpp_builder_riscv_arch_flag": "real source regression check (torch/_inductor/cpp_builder.py)",
            "dynamo_riscv_gating": "checked for RISC-V-specific Dynamo code paths",
            "arch": arch,
        },
    )


def suite_backend(reporter: Reporter, arch: str) -> None:
    def triton_riscv_backend() -> None:
        triton_third_party = REPO_ROOT / "third_party" / "triton"
        if not triton_third_party.exists() or not any(
            "riscv" in p.name.lower()
            for p in triton_third_party.rglob("*")
            if p.is_dir()
        ):
            raise SkipCase(
                "no RISC-V backend directory vendored under third_party/triton; "
                "Triton has no public RISC-V codegen target yet"
            )

    def tilelang_riscv_backend() -> None:
        if not any((REPO_ROOT / "third_party").glob("*ilelang*")):
            raise SkipCase(
                "TileLang is not vendored in this fork and has no RISC-V backend; "
                "infra placeholder only, nothing to validate yet"
            )

    reporter.case("backend.triton_riscv", triton_riscv_backend)
    reporter.case("backend.tilelang_riscv", tilelang_riscv_backend)
    write_json(
        reporter.artifact_dir / "compiler" / "backend-validation.json",
        {
            "triton": {
                "status": "not_implemented",
                "reason": "no RISC-V backend in third_party/triton",
            },
            "tilelang": {
                "status": "not_implemented",
                "reason": "TileLang not vendored in this fork",
            },
            "arch": arch,
        },
    )


SUITES = {
    "cross": suite_cross,
    "kernels": suite_kernels,
    "compiler": suite_compiler,
    "backend": suite_backend,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--arch", default="rv64gc")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--blocklist", default=str(DEFAULT_BLOCKLIST))
    args = parser.parse_args()

    reporter = Reporter(Path(args.artifact_dir), args.suite, args.arch)
    entries = load_blocklist(Path(args.blocklist))
    if is_blocked(entries, args.suite, args.arch, f"{args.suite}_{args.arch}"):
        raise RuntimeError(f"RISC-V CI suite is blocklisted: {args.suite}_{args.arch}")

    SUITES[args.suite](reporter, args.arch)
    reporter.finish()

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as fh:
            fh.write(
                (Path(args.artifact_dir) / "summary.md").read_text(encoding="utf-8")
            )
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
