# RC1.26 Build112 — M5-NAX-PQ2-01

## Status

**Experimental candidate. NOT DEVICE CERTIFIED.**

Base application/runtime remains Build112. This phase does not promote a new product version or change the user-facing API behavior. The existing read-only `/debug/prefill` response exposes only allowlisted M5-NAX-PQ2 trace evidence for automated collection.

**Important experiment scope:** the candidate kernel requires Metal TensorOps, but stock Build112 disables the Tensor API. This experimental branch therefore enables the Tensor API at backend initialization. The first device comparison measures the combined Tensor-enabled + NAX-PQ2 bundle against stock B16; generic TensorOps matmuls may also change. It is not an isolated estimate of the NAX kernel's contribution.

## Objective

Test one specific engine hypothesis:

> For large GGML_TYPE_PQ2_0 × F32 prefill matmuls on M5, directly dequantize PQ2 values into cooperative tensors and feed them to Metal TensorOps, removing the intermediate threadgroup-memory staging used by the existing Prism tensor kernel.

Apple's Metal documentation explicitly describes cooperative tensors as the mechanism for custom dequantization in registers/thread-private storage before matmul2d, avoiding a threadgroup-memory round trip. The M5 Programming Guide also recommends a 128-wide K working set as a starting point for explicit accumulation synchronization.

## Exact baseline

- Bonsai application baseline: Build112
- Prism checkout: adfffbe41b2cabcd51fff326ab045662265062bb
- Inherited Prism patches: Build83 through Build89
- Candidate branch: lab/m5-nax-pq2-01

## Candidate

### Scope

Only route operations matching all of:

- GGML_TYPE_PQ2_0
- activation type F32
- non-transposed operands
- K % 128 == 0
- prefill rows >= 16 and divisible by 16 (aligned to Build112's B16 ubatch)
- output channels >= 128
- single tensor batch dimensions
- contiguous F32 output

Operations that do not match the custom host-side NAX gate remain on Prism's existing Tensor-enabled kernels. Because enabling Tensor API also changes the generic matmul implementation, this experiment does not isolate NAX-only performance.

### Kernel

kernel_mul_mm_nax_pq2_0_f32

- output tile: 16 × 128
- simdgroups: 1 × 4
- threads: 128
- per-simdgroup tile: 16 × 32
- TensorOps fragment: 16 × 32 × 16
- K synchronization working set: 128
- PQ2 dequantization: exact existing 2-bit codec semantics
- no quantized-weight threadgroup staging

### Safety

The candidate can be disabled with:

GGML_METAL_PQ2_NAX_DISABLE

The candidate is otherwise automatically selected only when the narrow host-side gate matches.

## Deliberately unchanged

- Swift UI
- OpenAI-compatible API
- context configuration
- KV cache
- Vision
- batch governor
- Build112 recovery behavior
- model format
- B16 batch/ubatch values
- context and KV configuration
- PQ2 mathematical encoding

## Validation order

1. CI compiles the exact Prism base with Build83–89 patches plus this candidate.
2. CI builds the Bonsai iOS app.
3. CI verifies the final framework binary contains the embedded Metal kernel source, the host pipeline-getter symbol, and route/pipeline/dispatch trace markers. This is static linkage evidence only; the kernel is runtime-compiled by Metal, so CI does not certify runtime compilation or execution.
4. On the M5 iPad, run a 32K-context request with a sufficiently large prefill. The existing Quick test kit saves `/debug/prefill` as `prefill-after.json`; this response now includes `m5_nax_pq2_trace`, containing the trace header allowlist and only the three expected NAX markers. No separate manual trace export is required. The NAX markers use a dedicated low-volume trace path so Build84-89 scheduler tracing remains disabled during inference. The response also records `tensor_api_enabled`, backed by the pinned Prism backend-init log and the actual `GGML_METAL_TENSOR_DISABLE` environment state. The legacy `metal_tensor_prefill_effective` field is now true only when Tensor is enabled and the NAX route, ready pipeline, and dispatch-enqueued markers are all present; it still does not prove completed GPU execution. The expected one-per-process markers are `BUILD113_M5_NAX_PQ2_ROUTE_SELECTED`, `BUILD113_M5_NAX_PQ2_PIPELINE_READY ok=1`, and `BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED`. A missing route marker means the candidate gate was not observed; check shape eligibility before treating it as a failure. A route marker without `PIPELINE_READY ok=1` indicates the pipeline did not return ready. Dispatch-enqueued is not, by itself, proof of completed execution.
5. Compare the stock Build112 B16 path against this combined Tensor + NAX candidate using the same model, prompt set, context, and measurement harness; verify a successful completed request and numerical correctness. If the bundle meets promotion criteria, a subsequent Tensor-enabled baseline versus Tensor-enabled NAX A/B will isolate the NAX contribution.
6. Only after numerical correctness passes is performance promotion considered.

## Promotion criteria

The existing project target remains:

- Prefill: at least +15%
- TTFT: at least +10%
- Decode: no regression greater than 5%
- memory increase: no more than 1 GiB
- numerical correctness: no material change
- API behavior: unchanged

These are promotion gates, not current results.

## Important non-claim

This candidate has no real-device performance result yet. CI can establish compilation and packaging only. A passing CI build is not evidence that the M5 Neural Accelerator is faster for Bonsai PQ2.

## References

- Apple WWDC26 — Optimize custom machine learning operations with Metal tensors
- Apple Metal Performance Primitives Programming Guide, 2026-03-16
- Apple Tech Talk — Accelerate your machine learning workloads with the M5 and A19 GPUs
