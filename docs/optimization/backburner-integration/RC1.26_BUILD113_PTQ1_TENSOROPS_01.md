# RC1.26 Build113 PTQ1_0 Metal TensorOps Candidate

Status: implementation candidate; runtime Metal compilation, M5 dispatch completion, numerical behavior and performance require M5 A/B evidence.

## Frozen inputs

- App baseline: Build112 functional baseline; the build embeds the exact source SHA.
- Prism source: adfffbe41b2cabcd51fff326ab045662265062bb.
- Build83–89 inherited patches: KV layer sharding, native-context trace, scheduler trace, crash forensics, scheduler-context trace, mmap recovery and compact scheduler metadata. These do not implement a PTQ1_0 matrix-multiplication kernel.
- Main model remains Ternary-Bonsai-2-27B-PTQ1_0.gguf. The candidate does not require PQ2_0.

## Source-grounded PTQ1_0 representation and baseline path

At the pinned Prism revision, GGML_TYPE_PTQ1_0 is the actual GGML weight-type enum 143. Its block size is 128 values: 24 bytes qs, 2 bytes qh and one fp16 scale (28 bytes total). GGUF general.file_type is a separate model-level metadata field; it cannot replace the runtime tensor-type gate.

Prism already instantiates kernel_mul_mm_ptq1_0_f32 and uses dequantize_ptq1_0 to stage decoded half weights for cooperative TensorOps. The app's default policy disables the Tensor API. The existing NAX route remains gated to GGML_TYPE_PQ2_0. The model-gated experimental control selects PTQ1_0 only when the PTQ1_0 model and one-shot 16K/B16/UBatch16 trial are active; all other models and shapes remain on the prior policy.

## Candidate engine change

The opt-in kernel_mul_mm_ptq1_tensorops_0_f32 reuses only the 16x128 cooperative-MMA tile and accumulation structure. It replaces the PQ2 packed-bit decoder with Prism's actual ptq1_0_lut helper. This lookup-table decoder decodes the PTQ1_0 base-3 packing order into a half4 register vector, avoiding the custom kernel's decoded-weight threadgroup staging. This is a testable hypothesis, not a claimed speedup.

Host dispatch requires M5 TensorOps/SIMD-group-matrix capability, actual src0.type == GGML_TYPE_PTQ1_0, actual src1.type == GGML_TYPE_F32, F32 output, non-transposed contiguous layout, K divisible by 128, M >= 16 and divisible by 16, N >= 128, and singleton batch dimensions. The candidate additionally requires the explicit model-gated PTQ1_0 16K/B16/UBatch16 A/B opt-in. The runtime exports only allow-listed PTQ1 route/pipeline/dispatch markers through /debug/prefill; dispatch-enqueued is explicitly not reported as GPU completion. Default Governor and default Tensor-disabled behavior are unchanged.

If custom pipeline compilation fails, the failure is traced and the op returns to inherited Prism dispatch. A queued dispatch is not treated as GPU completion; the harness pairs its route/pipeline/dispatch markers with a later successful HTTP inference. Runtime GPU errors are never reported as successful candidate runs.

## A/B protocol

BASELINE and CANDIDATE use the same App source SHA, PTQ1_0 model, 16K Context, Batch 16, UBatch 16, exact calibrated prompts, temperature 0, seed 112 and max_tokens 128. Input targets are 512, 2048 and 8192 actual prompt tokens. Calibration and warmups are excluded; require at least three valid measured requests per target and arm.

Each raw sample records actual input/output token counts, TTFT, prefill time/tokens per second, decode time/tokens per second, source/model/runtime identity, actual route/pipeline/dispatch markers, request completion, output hashes, Metal allocation/headroom and thermal state.

Promotion requires all tested lengths to show at least 15% Prefill improvement and 10% TTFT improvement, no more than 5% Decode throughput regression, no more than 1 GiB Metal allocation increase, matching deterministic output hashes, and complete runtime evidence. Otherwise report CANDIDATE_NO_GAIN or BLOCKED_NEEDS_ENGINE_EVIDENCE.

## Limits

Codec reference parity tests do not execute GPU code. Static binary linkage does not prove runtime Metal compilation. Only an M5 run with the PTQ1_0 route marker, ready pipeline, dispatch marker and successful completed inference establishes M5_CANDIDATE_EXECUTION_VERIFIED. Only measured A/B meeting every threshold establishes M5_PERFORMANCE_GAIN_VERIFIED.
