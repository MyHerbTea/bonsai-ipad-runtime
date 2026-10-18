Bonsai Build112 PTQ1_0 Auth-Aware Startup Quick TestKit 2.1

Purpose
- Detect the effective IPA authentication mode from unauthenticated GET /health.auth_required.
- When auth_required=true, verify missing and incorrect keys return HTTP 401 on protected routes before prompting for the real key. auth_required=false means never prompt; send requests without Authorization or X-API-Key.
- Verify Build112/App source identity, the loaded PTQ1_0 model filename, runtime context/batch/ubatch, native-context evidence and one real Smoke inference.
- Read startup lifecycle evidence after Smoke. A changed last_engine_stage such as TEXT_99_PASS_FULL_PREFILL is a post-inference engine stage, not proof that API startup failed.
- Keep current API readiness, historical startup failures, and NAX experiment applicability as independent results.
- Preserve model filename, startup_attempt_id, timestamps, failure stage/reason, outcome and recovery linkage for future startup attempts. Older failures lacking model/attempt IDs remain UNATTRIBUTED_HISTORICAL_FAILURE.
- Create a result ZIP containing before/after startup snapshots, auth-route probes, model/runtime identity, Smoke evidence, summary and per-file SHA-256 manifest.

Run the PTQ1_0 16K/B16 shape-only diagnostic
1. Install the matching IPA built from the App source SHA pinned in EXPECTED_APP_SOURCE_SHA.txt. The matching IPA for this run is Build112, source SHA bc6ed119bc7127a6b0cd73ea9b94b3673e173aaf.
2. Keep the main model set to Ternary-Bonsai-2-27B-PTQ1_0.gguf. Do not switch to PQ2_0.
3. In Advanced & Diagnostics, set API Context to 16K with Q4 KV. Do not manually alter other runtime parameters.
4. Enable the exact one-shot toggle: “实验：PTQ1_0 16K/B16 形状隔离（TensorOps 关闭，单次）”. This automatically keeps the NAX Metal TensorOps candidate disabled. Fully terminate Bonsai and reopen it so the next-launch setting is applied.
5. Start the API once. The trial pins the following launch to safe B8 before native context creation. Do not repeatedly re-enable the trial.
6. If the API reaches READY, keep Bonsai in the foreground and run RUN_BUILD112_QUICK_TEST.cmd. Enter the API Base URL. If authentication is enabled, the tool asks for the key only after /health reports auth_required=true. The resulting ZIP should capture the real Smoke inference and the effective API/native batch and ubatch values; the candidate should report B16/UBatch16.
7. If Bonsai crashes or the API never becomes ready, reopen Bonsai but do NOT immediately start the API again. Open Advanced & Diagnostics and tap “复制完整原生崩溃追踪（当前及上次）”. Paste the entire copied text for analysis. The updated IPA arms the trace at API-start entry, before vision release, backend prewarm, and model mmap; it durably records Swift startup stages as well as native scheduler events. The trace header includes the app source SHA and intended context/batch/ubatch. If the current trace is still not_available, also tap “刷新并复制完整诊断” and include trace_setup_error.
8. The one-shot latch automatically pins the following process launch to B8. After an interrupted B16 attempt, reopening the app classifies the attempt and returns to B8. To repeat the candidate test after installing the diagnostic IPA, re-enable the one-shot toggle and fully restart the app before starting API.
9. This is a startup/shape-isolation test, not a performance benchmark. A successful one-shot run or an interrupted run automatically returns the next launch to B8.

Standard Quick Test
- For a normal PTQ1_0 B8 readiness check without the one-shot B16 experiment, install the same matching IPA, leave the shape-only toggle off, start the API, run RUN_BUILD112_QUICK_TEST.cmd and send the result ZIP under RESULTS.

Independent classifications
- CURRENT_STARTUP_READY: current /health is OK, API startup stage is READY, current startup error is clear, native context exists and Smoke inference passed.
- RECOVERED_AFTER_STARTUP_FAILURE: the recorded recovery points to a prior failed attempt with the same model identity.
- MODEL_SPECIFIC_STARTUP_FAILURE: historical failure has a model identity and attempt ID but is not linked to a same-model recovery.
- UNATTRIBUTED_HISTORICAL_FAILURE: historical failure exists but model identity or attempt association is missing.
- NOT_APPLICABLE_PTQ1_0_DEFAULT_PATH: NAX-PQ2 Tensor remains disabled on the PTQ1_0 mainline.
- FAIL_API_UNREACHABLE, AUTH_FAILED, FAIL_INFERENCE, FAIL_NAX_ISOLATION and BLOCKED_NEEDS_EVIDENCE identify distinct current failures/evidence gaps.

Overall result and exit codes
- PASS: exit code 0.
- PASS_WITH_WARNINGS: exit code 0; current API Smoke passed, but historical failure attribution or current diagnostics needs attention.
- FAIL: exit code 1.
- INCOMPLETE: exit code 2.
- BLOCKED: exit code 3.

Security and interpretation
- API Key values and request headers are never written to result files. The key is held only in process memory during the test.
- Auth probes record only endpoint, HTTP status and pass/fail.
- This Quick TestKit is not proof of crash-free behavior on every M5 launch, numerical correctness, or performance improvement. A historical failure without model/attempt IDs cannot be attributed retroactively.
