# Build129 Prefill Profiling Implementation Plan

**Goal:** Measure the production context without replacing it or changing its inference configuration.
**Architecture:** A dedicated diagnostic session owns the existing inference/vision admission lease. The actor drains the loaded context, checks native ABI, resets and enables scoped counters, runs one text request with production flags, drains and disables counters in all exit paths, and publishes explicitly scoped evidence. Unsupported isolation fails closed.
**Spec:** docs/superpowers/specs/2026-10-27-build129-prefill-profiling-design.md

## Constraints
Source begins at 5804c5089087445f365b03a926c48167cbd07468; keep Q8_0, 16K, B8/UB8, 56 GPU layers, 6 threads, unified KV, existing production native flags. Never bypass interruption quarantine or safety guards. No automatic retry after uncertain requests. Compare instrumented and uninstrumented behavior; no speed claim without actual device evidence.

## Tasks
1. Audit all inference and MLX entry points, session admission, drain guarantees, and native counter availability; identify a testable isolation contract and fail-closed behavior.
2. Write and run focused failing tests for the diagnostic session lease, context identity, counter lifecycle and error paths; implement minimal changes, then run the focused checks and appropriate existing regression checks.
3. Build an identifiable derived iOS diagnostic artifact and verify its source, build and native symbol identities. Preserve Build129 for baseline comparisons.
4. Confirm device identity, model SHA, context parameters, resource state, response quality, and collect bounded request-level profiling and overhead evidence. Record raw data and hashes. Stop on uncertainty or resource guards.
5. Select a single candidate only if the measurements identify a useful bottleneck; compare with interleaved real workloads and retain only a reproducible end-to-end improvement.
