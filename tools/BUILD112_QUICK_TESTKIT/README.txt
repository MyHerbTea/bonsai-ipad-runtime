Bonsai Build112 PTQ1_0 Auth-Aware Startup Quick TestKit 2.1

Purpose
- Detect the effective IPA authentication mode from unauthenticated GET /health.auth_required.
- When auth_required=true, verify missing and incorrect keys return HTTP 401 on protected routes before prompting for the real key. auth_required=false means never prompt; send requests without Authorization or X-API-Key.
- Verify Build112/App source identity, the loaded PTQ1_0 model filename, runtime context/batch/ubatch, native-context evidence and one real Smoke inference.
- Read startup lifecycle evidence after Smoke. A changed last_engine_stage such as TEXT_99_PASS_FULL_PREFILL is a post-inference engine stage, not proof that API startup failed.
- Keep current API readiness, historical startup failures, and NAX experiment applicability as independent results.
- Preserve model filename, startup_attempt_id, timestamps, failure stage/reason, outcome and recovery linkage for future startup attempts. Older failures lacking model/attempt IDs remain UNATTRIBUTED_HISTORICAL_FAILURE.
- Create a result ZIP containing before/after startup snapshots, auth-route probes, model/runtime identity, Smoke evidence, summary and per-file SHA-256 manifest.

Run
1. Install the IPA built from the App source SHA pinned in EXPECTED_APP_SOURCE_SHA.txt.
2. Keep the main model set to Ternary-Bonsai-2-27B-PTQ1_0.gguf. Do not switch to PQ2_0 for this test.
3. Start the API in Bonsai and keep the app in the foreground during the Smoke request.
4. Run RUN_BUILD112_QUICK_TEST.cmd and enter the Base URL. The script reads /health first and prompts for a key only if the IPA reports auth_required=true.
5. Send the single ZIP under RESULTS for analysis.

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
