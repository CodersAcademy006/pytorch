# Fork CI mirror: what we can and can't reproduce

This fork mirrors as much of upstream pytorch/pytorch's CI as free GitHub-hosted
hardware (+ the RISE riscv64 native runner) allows: `fork-ci-mirror-fast.yml`
(lint/codegen/mypy-equivalent via lintrunner, cmake-configure, public GHCR
image pull sanity) and `fork-ci-mirror-build.yml` (real
`pip install -e . -v --no-build-isolation` builds: Linux gcc/clang x
Python 3.10-3.13, Linux ARM64, Windows, macOS, docs build). RISC-V lives in
`riscv64.yml` / `riscv-pr-comment.yml`.

Everything below is a real gap, checked against upstream's actual workflow
files (`.github/workflows/*.yml`), not a guess -- so when someone asks "why
isn't this running here," this is the factual answer.

| Job / category | Why it can't run on this fork |
|---|---|
| CUDA (all `*cuda*` jobs) | Upstream uses `linux.g6.4xlarge.nvidia.gpu` / `linux.g4dn.*` self-hosted GPU fleet. No free NVIDIA GPU on GitHub-hosted runners or the RISE app. |
| ROCm | Upstream uses `linux.rocm.gpu.gfx950.*` self-hosted. No free AMD GPU runner exists anywhere we have access to. |
| XPU (Intel) | Upstream uses `linux.idc.xpu` self-hosted. No free Intel accelerator runner available. |
| Everything else upstream runs (build/test/lint on Linux/Windows/macOS/ARM) | Upstream runs these on its own self-hosted AWS/Mac-mini fleet (`linux.4xlarge`, `windows.4xlarge.nonephemeral`, `macos-m1-stable`, `linux.arm64.m8g.4xlarge`, etc.) purely for cost/performance/fleet-management reasons, not because the work itself needs special hardware. We mirror the actual commands (`build.sh`, `test/run_test.py`, `lintrunner`) on GitHub-hosted equivalents instead (`ubuntu-latest`, `windows-latest`, `macos-14`, `ubuntu-24.04-arm`). |
| Docker image builds (pushed to AWS ECR) | Upstream's `docker-builds.yml` pushes to a private ECR (`308535385114.dkr.ecr.us-east-1.amazonaws.com`), which needs an AWS IAM role we don't have. **Not actually a blocker in practice**: every image is also mirrored to public `ghcr.io/pytorch/ci-image` with no auth required, which is what this fork pulls and uses directly (see `ghcr-image-sanity` job). |
| Multi-node distributed jobs | Need a private multi-machine cluster upstream provisions per-job. No equivalent available. |
| `inductor-benchmarks` / `vllm` / `pallas` / `tpu` / `executorch` docker variants | Downstream-project-specific images tied to accelerator hardware above (CUDA/ROCm/TPU) -- same root cause, not a separate gap. |

Anything not in this table is either already mirrored, or genuinely
reproducible and just hasn't been wired up yet -- ask and it'll get added if
it's feasible on free hardware.
