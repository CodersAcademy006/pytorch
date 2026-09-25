# RISC-V PyTorch — Personal Tracker

Mirror of upstream tracking issue **[pytorch/pytorch#180975]** with *my* ownership status, PRs, and a focus queue.
Strategy: **own Phase 1 + Phase 3 (CI / build / native / validation / benchmark / tooling)**, defer Phase 2 kernels until RVV hardware. Kit today: M5 (llvm cross-tools) · native RISE runner (rv64, **no RVV**, U74) · QEMU · fork CI lab (`CodersAcademy006/pytorch`).

## Legend
**Ownership:** 🟢 own now · 🟡 own after learning subsystem · 🔴 blocked (needs RVV hardware / heavy kernel) · ⚫ external ecosystem dep
**Status:** ✅ landed · 🔵 PR in flight (mine) · ⬜ open, mine to take · ⏸ deferred · 🚫 blocked

---

## Phase 1 — CI Infrastructure & Validation  *(MY LANE)*

| Item | Own | Status | PR / Note |
|------|-----|--------|-----------|
| Cross-compile environment | 🟢 | ⬜ | improve toolchains/Docker/CMake; fork docker-lab already builds `ci-image` riscv64 |
| Native compile environment | 🟢 | ⬜ | RISE runner live; wire native build workflow |
| Build + validate riscv64 wheel | 🟢 | ⬜ | base build needs no RVV → runnable now |
| Disable CUDA bindings | 🟢 | ✅ | done (community) |
| Restrict MKL to x86 | 🟢 | ✅ | done (community) |
| **GitHub Actions CI** | 🟢 | 🔵 | most built in fork lab → upstream a slice; watch luhenry #182278 |
| Jenkins CI (OpenRuyi) | 🔴 | 🚫 | needs OpenRuyi access — not mine |
| Automated CI monitoring | 🟢 | ⬜ | GitHub API only; dashboard/bot |
| Maintain RISC-V test blocklist | 🟢 | ⬜ | run base suite on RISE runner → record real failures (cf RuyiAI-Stack#1) |
| **Fix architecture-specific bugs** | 🟢 | ✅🔵 | **#189000 rdtime clock LANDED** · **#188999 pause hint OPEN (credibility-gated)** |
| **`test_times.json`** | 🟢 | 🔵 | **#181109 LGTM'd, mergeable** — maintainer click |
| zlib dockerfile URL 404-fragility | 🟢 | ⬜ | **#175193** — `better-engineering`, 1-line github-releases fix → NEXT |

**Phase 1 verdict:** ~entirely mine. 2 landed, 2 PRs in flight, rest doable with current kit.

---

## Phase 2 — uKernel Library  *(DEFER — mostly RVV-blocked)*

### 2.1 Infrastructure
| Item | Own | Status |
|------|-----|--------|
| uKernel lib integration (ATen build) | 🟡 | ⏸ needs ATen knowledge |
| Runtime CPU feature detection (VLEN/RLEN) | 🟡 | ⏸ can scaffold detection w/o RVV runtime |
| Dispatch mechanism | 🟡 | ⏸ dispatcher internals |

### 2.2 GEMM
| Item | Own | | Item | Own |
|------|-----|--|------|-----|
| FP32 GEMM RVV | 🔴 | | RVFP4 GEMM | 🔴 |
| FP16 GEMM RVV | 🔴 | | GEMM Matrix Ext (RVM) | ⚫ |
| BF16 GEMM RVV | 🔴 | | Batched GEMM | 🟡 |
| FP8 GEMM RVV | 🔴 | | **GEMV** | 🟡 (easiest entry) |
| INT8 / INT4 GEMM | 🔴 | | | |

### 2.3 Conv — im2col 🟡 · Conv1d 🟡 · Direct Conv2d 🔴 · Depthwise 🔴
### 2.4 Activations (all 🟡 vector, Softmax 🔴) — ReLU/GELU/SiLU/Sigmoid/Add-Mul-Sub-Div/type-cast 🟡
### 2.5 Norm (all 🟡) — LayerNorm / RMSNorm / BatchNorm / reductions
### 2.6 Transformer — RoPE 🟡 · SDPA 🔴
### 2.7 Pooling/rearrange (all 🟡) — Max/Avg/AdaptiveAvg pool · Transpose · Embedding

**Phase 2 verdict:** ⏸ until RVV silicon/vector-QEMU. 🟡 items become reachable once Phase 1 credibility + infra understanding are in place.

---

## Phase 3 — torch.compile Backend  *(SECONDARY LANE)*

### 3.1 RVV native compile
| Item | Own | Status |
|------|-----|--------|
| Validate torch.compile backends | 🟢 | ⬜ CI-adjacent; RISE runner enough for correctness |
| Extend CPU vector-ISA abstraction | 🟡 | ⏸ Inductor internals |
| RVV variable-length semantics | 🔴 | 🚫 needs RVV |
| Expand operator/model coverage | 🟡 | ⏸ long-term |

### 3.2 Buddy compiler (buddy-mlir / MLIR RVV / Matrix / Gemmini) — all ⚫ external
### 3.3 Validation & benchmarking
| Item | Own | Status |
|------|-----|--------|
| Correctness verification | 🟢 | ⬜ RISE runner |
| Benchmark eager vs compiled (scalar) | 🟢 | ⬜ RISE runner |
| Profiling across backends | 🟢 | ⬜ |

---

## Phase 4 — Triton / TileLang  *(mostly external)*
Triton-RISCV ⚫ · TileLang-RISCV ⚫ · codegen ⚫ · backend interface 🟡 · autotuning 🟡 · **profiling 🟢 · validation 🟢**

## Phase 5 — vLLM / SGLang on RISC-V — 🔴/⚫ downstream, far out

---

## Summary (my capability)
| | Count | Meaning |
|---|---:|---|
| 🟢 start today | 12 | Phase 1 + 3.1 validate + 3.3 + P4 profiling/validation |
| 🟡 after learning | 18 | most Phase 2 vector kernels + Inductor abstraction |
| 🔴 hardware/kernel-blocked | 14 | RVV GEMM/conv/SDPA/softmax + RVV semantics |
| ⚫ external ecosystem | 7 | buddy-mlir, Triton/TileLang, Matrix ISA |

---

## 🎯 Focus queue (ordered, no hardware needed)
1. **#175193** zlib dockerfile → github-releases URL — *1-line, ship today*
2. **Nudge #188999** — post luhenry, cite #189000 land (ezyang's own merge) to break credibility-gate
3. **Nudge #181109** — LGTM'd/mergeable, maintainer click
4. **riscv64 wheel build** validated on RISE runner (Phase 1.1)
5. **Test blocklist** — run base suite on RISE runner, record real failures (Phase 1.3)
6. **Upstream a GHA-CI slice** from fork lab (Phase 1.2, align w/ luhenry #182278)
7. **CI monitoring bot** — GitHub-API dashboard (Phase 1.2)
8. **torch.compile validate + scalar benchmark** on RISE runner (Phase 3.1/3.3)

After 1–8: Phase 1 is effectively mine-complete; Phase 2 waits on RVV hardware.

*Upstream tracker body untouched since 2026-04-21; maintainers track via linked PRs, not checkbox ticks — this file is the real status.*
