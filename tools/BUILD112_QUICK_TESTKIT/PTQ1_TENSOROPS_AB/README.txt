# PTQ1_0 Metal TensorOps A/B TestKit

## Purpose
Measure the current PTQ1_0 BASELINE or opt-in CANDIDATE arm on the M5 iPad. The TestKit does not change runtime settings or arm state. Run the same kit twice, once per arm, because Metal backend configuration is latched at process startup.

## Required preconditions
- Install the IPA packaged alongside this kit. Do not mix an IPA and kit from different ZIPs.
- Main model: Ternary-Bonsai-2-27B-PTQ1_0.gguf.
- API Context 16384, Q4 KV, Batch 16, UBatch 16.
- Both arms must report an active PTQ1_0 16K/B16/UBatch16 shape trial (Phase2D CANDIDATE16). The UI has two related toggles, so use the exact combinations below.
- For BASELINE: turn OFF the upper “实验：PTQ1_0 A/B 固定 16K / B16” candidate toggle, then turn ON the lower “实验：PTQ1_0 16K/B16 形状隔离” toggle. This keeps Phase2C on BASELINE while running the same B16/UBatch16 shape.
- For CANDIDATE: turn ON the upper “实验：PTQ1_0 A/B 固定 16K / B16” candidate toggle and leave the lower shape-isolation toggle OFF. This enables the custom route before backend prewarm.
- After either combination, completely quit and relaunch the iPad app, then start API once. Confirm /debug/phase2c/launch and /debug/phase2d/launch show the requested Phase2C arm and CANDIDATE16 shape before running the TestKit.
- Keep the screen awake. Do not change model, KV, context, sampling, or app build between arms.

## Run
1. Double-click RUN_PTQ1_TENSOROPS_AB.cmd.
2. Enter the iPad API URL, choose the arm currently active in the app, and enter an API key only if authentication is enabled.
3. First run: leave the previous ZIP field blank. It calibrates prompts to exactly 512 and 2048 actual input tokens, then performs a warmup preflight for every required length. Only if each warmup proves a completed 128-token inference and the correct route counters (candidate: route + pipeline + dispatch, zero fallback; baseline: zero candidate dispatch) does it collect at least three valid performance samples per length. Calibration, warmups and failed preflight attempts are excluded from performance statistics.
4. If preflight fails, the runner stops before performance sampling and still writes a blocked result ZIP with `warmups.json` evidence. Do not switch arms or treat it as an A/B result; fix the indicated startup/route issue first.
5. After a successful first-arm preflight and run, switch the app to the other arm, fully quit/relaunch, and start the API. Run the same kit again, select the previous first-arm ZIP, and keep the same input-length selection. It reuses the exact prompt bank and creates an A/B comparison ZIP.
5. 8192-token input is optional and increases runtime. Use it only if you want the longer test.

## Evidence and gates
- The runner fails closed unless TestKitIdentity.json pins the installed app source SHA, the API reports the requested Phase2C arm and matching backend-latched evidence, and Phase2D confirms active B16/UBatch16. A warmup route preflight for every target must pass before any performance measurements begin.
- Each measured request snapshots native route counters before and after inference. Candidate samples require positive route-selected, pipeline-ready and dispatch-enqueued counter deltas, zero fallback delta, one new completed inference observation and exactly 128 output tokens. BASELINE samples require zero candidate-route/dispatch deltas.
- Each sample records actual token counts, TTFT, Prefill ms/tok/s, Decode tok/s, identity, counter deltas, Metal allocation/headroom, thermal state and output hash.
- Comparison gates: Prefill improvement >=15%, TTFT improvement >=10%, Decode throughput regression <=5%, Metal allocation increase <=1 GiB, deterministic output hashes match, and all samples for each input length have the same stable (nominal/fair) thermal state across both arms. Missing memory telemetry, inconsistent TTFT reconstruction or thermal drift invalidates a sample/comparison.
- A previous-arm ZIP is accepted only if its internal SHA-256 manifest, identity, warmup evidence, prompt-bank hash, required target list and samples/warmups payload consistency validate. Missing targets or missing repeat hashes cannot pass comparison.
- If the route does not execute, the backend/shape arm is unverified, or there are fewer than three valid samples at any required length, the result is blocked/no-gain; it must not be reported as a performance win.
- Results are written to RESULTS as ZIP files with SHA-256 manifests. The runner stores output hashes, not generated output text or API keys.

## Limits
This is a measurement tool, not a GPU correctness proof. The native counter proves the candidate route/pipeline/dispatch path advanced during the measured request window; the subsequent successful inference is required, but the app does not expose an independent Metal command-buffer completion counter, so dispatch_completion_proof remains false. The first real M5 candidate run must still be inspected for runtime Metal compilation, successful inference, numerical/output parity and performance. CI and static linkage do not prove any of those device-level outcomes.
