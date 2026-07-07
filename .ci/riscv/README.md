# Personal RISC-V CI Lab

This directory contains fork-runnable RISC-V CI helpers for GitHub-hosted
runners. The workflows intentionally avoid PyTorch-owned runners, internal ECR
registries, AWS roles, and repository-owner guards.

The CI produces the same artifact classes expected by PyTorch infrastructure:
logs, JUnit XML, timing JSON, benchmark JSON, compiler output, generated IR,
generated kernels, and Markdown job summaries.

Physical RISC-V hardware is not required for correctness smoke coverage. The
push and pull request workflows use `riscv64-linux-gnu-*` cross compilers and
`qemu-riscv64`. Hardware-only validation, such as true RVV performance, remains
limited by runner availability.

## Suites

- `cross` -- compiles and runs a real c10 header (`ApproximateClock.h`) under
  the cross toolchain + QEMU. Always real, never skipped.
- `kernels` -- Phase 2 uKernel categories (gemm/conv/activation/reduction/
  softmax/layernorm/rmsnorm/pooling/embedding). Each category looks for a
  RISC-V/RVV-specific source file (`find_riscv_kernel_source` in
  `run_riscv_ci.py`); if none exists yet it is reported `skipped`, not faked
  green. The moment a real kernel file lands under
  `aten/src/ATen/native/cpu/**`, this suite starts compiling and running it.
- `compiler` -- a toolchain codegen smoke (compile+emit-LLVM a generated C++
  snippet), plus two real regression checks against current source:
  `torch/_inductor/cpp_builder.py`'s riscv64 arch-flag branch, and whether
  `torch/_dynamo` has any RISC-V-specific gating yet (skipped if not).
- `backend` -- reports whether `third_party/triton` or a vendored TileLang
  package has a RISC-V backend (both currently `skipped`: neither exists in
  this fork).

## Blocklist

`blocklist.json` lets you disable a whole suite+arch combination without
editing workflow YAML, e.g. if a specific matrix leg is flaky or a dependency
is temporarily broken:

```json
{
  "version": 1,
  "entries": [
    {"suite": "kernels", "arch": "rv64gcv"}
  ]
}
```

`suite`, `arch`, and `name` each default to matching anything (`"*"`); a
blocklisted suite+arch raises immediately before any suite code runs, so the
job fails fast with a clear reason instead of a confusing downstream error.

## Rollup

`aggregate_summary.py` runs once per workflow (in `riscv-summary` /
`nightly-summary`) after all matrix legs finish: it downloads every leg's
JUnit XML and regenerates a single canonical `test-times.json` /
`test-class-times.json` via `tools/stats/generate_test_times_from_reports.py`
(the same script from PR #181109), rather than reimplementing JUnit
aggregation. `upload-test-stats.yml` / `upload-test-stats-while-running.yml`
are not reused directly -- both are gated on
`github.repository_owner == 'pytorch'` and an AWS OIDC role this fork has no
trust relationship for, so they cannot run here at all. Artifact upload +
this rollup are the fork-runnable equivalent.
