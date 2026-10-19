# PTQ1_0 Metal TensorOps A/B TestKit

## Purpose
Measure the current PTQ1_0 BASELINE or opt-in CANDIDATE arm on the M5 iPad. The TestKit does not change runtime settings or arm state. Run the same kit twice, once per arm, because Metal backend configuration is latched at process startup.

## Required preconditions
- Install the IPA packaged alongside this kit. Do not mix an IPA and kit from different ZIPs.
- Main model: Ternary-Bonsai-2-27B-PTQ1_0.gguf.
- API Context 16384, Q4 KV, Batch 16, UBatch 16.
- For BASELINE: select the PTQ1_0 16K/B16 shape trial with the Metal TensorOps candidate switch OFF.
- For CANDIDATE: select the model-gated PTQ1_0 A/B 16K/B16 candidate switch ON.
- Completely quit and relaunch the iPad app after changing arms, then start API once.
- Keep the screen awake. Do not change model, KV, context, sampling, or app build between arms.

## Run
1. Double-click RUN_PTQ1_TENSOROPS_AB.cmd.
2. Enter the iPad API URL, choose the arm currently active in the app, and enter an API key only if authentication is enabled.
3. First run: leave the previous ZIP field blank. It calibrates prompts to exactly 512 and 2048 actual input tokens, runs a warmup, then collects at least three valid 128-token samples per length. Calibration and warmups are excluded.
4. Switch the app to the other arm, fully quit/relaunch, and start the API. Run the same kit again, select the previous first-arm ZIP, and keep the same input-length selection. It reuses the exact prompt bank and creates an A/B comparison ZIP.
5. 8192-token input is optional and increases runtime. Use it only if you want the longer test.

## Evidence and gates
- The runner verifies app source SHA, PTQ1_0 model identity, Context/Batch/UBatch and the selected arm where exposed by the API.
- Each valid sample records actual token counts, TTFT, Prefill ms/tok/s, Decode tok/s and derived decode ms, model/source identity, route/pipeline/dispatch markers, Metal allocation/headroom, thermal state, output hash and raw sample data.
- A candidate sample is rejected unless the PTQ1 route was selected, the pipeline reported ready, dispatch was enqueued, and the API inference completed with exactly 128 output tokens. Dispatch-enqueued alone is not completion proof.
- Comparison gates: Prefill improvement >=15%, TTFT improvement >=10%, Decode throughput regression <=5%, Metal allocation increase <=1 GiB, and deterministic output hashes match.
- If the route does not execute or there are fewer than three valid samples, the result is blocked/no-gain; it must not be reported as a performance win.
- Results are written to RESULTS as ZIP files with SHA-256 manifests. The runner stores output hashes, not generated output text or API keys.

## Limits
This is a measurement tool, not a GPU correctness proof. The first real M5 candidate run must be inspected for route, pipeline, dispatch, successful inference and numerical/output parity. CI and static linkage do not prove Metal runtime compilation or speedup.
