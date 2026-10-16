# RC1.26 Build112 — M5-NAX-PQ2-01

## Status

**Experimental candidate. NOT DEVICE CERTIFIED.**

Base application/runtime remains Build112. This phase does not promote a new product version and does not modify the Swift production path.

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
- batch/prefill rows >= 64
- output channels >= 128
- single tensor batch dimensions
- contiguous F32 output

Everything else remains on the inherited Prism path.

### Kernel

kernel_mul_mm_nax_pq2_0_f32

- output tile: 64 × 128
- simdgroups: 2 × 4
- threads: 256
- per-simdgroup tile: 32 × 32
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
- PQ2 mathematical encoding

## Validation order

1. CI compiles the exact Prism base with Build83–89 patches plus this candidate.
2. CI builds the Bonsai iOS app.
3. CI verifies the candidate kernel symbol is present in the framework.
4. Real M5 iPad validation compares the inherited Build112 path against this candidate using the same model, prompt set, context, and measurement harness.
5. Only after numerical correctness passes is performance promotion considered.

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
