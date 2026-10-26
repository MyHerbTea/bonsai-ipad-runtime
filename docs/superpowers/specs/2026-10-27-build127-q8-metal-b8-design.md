# Build127: Fixed-Q8 PTQ1 Metal B8 performance candidate

## Intent

Find a measurable prefill improvement on the already measured M5 16K + Q8_0 runtime while keeping the Q8 cache, model SHA, context, batch/ubatch, CPU SDOT, GPU-layer placement, threads, mmap, Flash Attention, and other runtime settings fixed. The candidate changes only an opt-in Metal PTQ1_0 small-batch B8 execution path. PTQ1_0 remains the model-weight format; Q8_0 remains the KV format.

## Evidence and approaches

- Build126 Quick measured allocated K/V tensors as Q8_0 on M5, with short 512/128 requests. It is a screening baseline only. Its timings are not directly comparable with Build125 because the runner and configuration differ.
- Build125 measured the paired CPU SDOT change at +0.576% end-to-end prefill versus single-row SDOT, below its 3% screen threshold; that report names Metal PTQ1 B8 small-batch mat-vec as the next source target.
- Directly changing Q8 KV attention/read kernels is deferred: current device data does not isolate KV attention as the limiting cost, and such a change would modify the format-specific path under investigation.
- Changing context, batch, threads, GPU layers, or model placement is excluded because it would confound the comparison.

## Chosen design

Add one explicit benchmark-only Metal candidate for PTQ1_0 B8 mul_mv_ext, using an opt-in native candidate bit and actual dispatch evidence. Keep the existing generic Prism path as the baseline and fallback. The Q8 performance mode permits only the same 16K/B8/Q8_0 configuration with the existing CPU SDOT enabled; A/B arms differ only by the Metal candidate bit. Candidate dispatch is limited to supported M5/PTQ1_0/F32 shapes. Unsupported shapes and pipeline failure use the existing generic path and are recorded; a missing candidate dispatch invalidates the candidate sample.

Use the repository's pinned Prism revision and current Build126 patch order. Add a bounded Quick runner using one fixed short workload and a small ABBA comparison. Require actual allocated KV tensor readback, candidate-route counts, identical source/model/config identities, output/logit parity within the existing numerical contract, restoration to Q8 baseline, idle API, and saved raw evidence. Screen for at least 3% prefill gain beyond observed drift, with no material decode, memory, thermal, or correctness regression. A negative screen ends this candidate without promotion.

## Non-goals and release boundary

Do not change KV type or Q8 policy, production defaults, model bytes, Metal TensorOps, CPU candidate math, Batch/UBatch, context, GPU layers, threads, Governor, API/authentication, or unrelated runtime code. Do not run the long 8K/16K Full workload in this performance screen. CI/IPA success is not M5 performance certification; no push, release, default change, or Certified Stable claim is included.
