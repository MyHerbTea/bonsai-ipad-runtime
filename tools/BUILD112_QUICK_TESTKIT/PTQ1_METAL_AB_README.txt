Bonsai PTQ1_0 Metal TensorOps A/B TestKit

Purpose
- Reuse the existing Quick TestKit 2.1 environment and authentication handling without changing API auth policy.
- Measure the original PTQ1_0 path versus the explicit PTQ1_0 TensorOps candidate on the same installed IPA, model, source SHA, Context=16384, Batch=16, UBatch=16, prompts, sampling parameters and device.
- Calibrate exact prompt-token counts from API usage. Default targets are 512 and 2048; pass -Include8192 to add 8192 tokens.
- Require three valid measured requests per target and arm, with one separate warmup per target. Warmups and prompt calibration are excluded from measurements.
- Record TTFT, Prefill milliseconds/tokens per second, Decode milliseconds/tokens per second, actual token counts, source/model/runtime identity, actual native operand types, route/pipeline/dispatch evidence, live Metal allocation/headroom, thermal state and output hashes.
- Generate summary.json, samples.jsonl, samples.csv, route snapshots, a SHA-256 manifest and a result ZIP.

Before running
1. Install the new PTQ1-Metal-AB IPA and select Ternary-Bonsai-2-27B-PTQ1_0.gguf.
2. In Advanced & Diagnostics, enable "PTQ1_0 A/B fixed 16K / B16". This option is experimental and must remain ON for both arms.
3. Set the "Metal TensorOps candidate (next launch)" toggle OFF, fully quit Bonsai, relaunch it and start the API. Keep the app in the foreground and prevent screen lock.
4. Double-click RUN_PTQ1_METAL_AB.cmd. Enter the API base URL. The script reads /health.auth_required first and asks for a key only when required. Keys and headers are never saved.
5. The script runs BASELINE first. When prompted, turn the candidate toggle ON, keep the PTQ1 16K/B16 toggle ON, fully quit/relaunch Bonsai, start the API and press Enter. The script verifies the source SHA, model and runtime shape are unchanged before measuring CANDIDATE.
6. Keep the iPad awake during the entire run. Do not use other model requests during measurements. If the app does not become ready or route evidence is missing, the script records a blocked result rather than claiming success.

Safety
- The test kit never changes API authentication, Governor defaults, Context, model format or Text KV Reuse.
- It refuses to benchmark if Text KV Reuse is enabled, if Context/Batch/UBatch is not 16384/16/16, or if actual prompt/output token counts are not exact.
- The runtime trace must report actual weight_type=143, activation_type=0 and output_type=0. GGUF general.file_type is recorded only as metadata and is not used to choose the kernel.
- Route selected, pipeline ready and dispatch enqueued are not sufficient alone. The warmup must also complete successfully with HTTP 200 and 128 output tokens.
- Output hashes are compared between matching baseline/candidate samples. A mismatch blocks performance promotion.
- No API key, Authorization header, or full generated text is saved; only output SHA-256 hashes are retained.

Performance gates
- Prefill throughput improvement >= 15%.
- TTFT improvement >= 10%.
- Decode throughput regression <= 5%.
- Additional Metal allocation <= 1 GiB.
- Matching deterministic output hashes and complete native route evidence.

Status meanings
- M5_PERFORMANCE_GAIN_VERIFIED: all measurements and gates passed.
- CANDIDATE_NO_GAIN: candidate executed and measurements completed, but one or more performance gates failed.
- BLOCKED_NEEDS_ENGINE_EVIDENCE: startup, identity, route, token-count, numerical-parity or sample-completeness evidence was missing or invalid.

The script derives Decode total milliseconds from actual completion_tokens / measured tokens_per_second. This derived value is labeled accordingly in the raw sample schema. A PASS in the test kit is not a substitute for separate engine correctness review.
