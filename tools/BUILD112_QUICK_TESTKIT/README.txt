Bonsai Build112 PTQ1_0 Auth-Aware Startup Quick TestKit 2.0

Purpose
- Detect the actual IPA authentication setting from the unauthenticated GET /health field auth_required.
- Prompt for an API Key only when auth_required=true. If false, do not prompt and do not send Authorization or X-API-Key headers.
- When auth is enabled, verify that missing and incorrect keys receive HTTP 401 on /v1/models, /debug/build, /debug/prefill and /v1/chat/completions before asking for the real key.
- Verify the actual App source SHA independently from the TestKit source commit and confirm Build112 identity.
- Verify the loaded PTQ1_0 model filename, capture raw GGUF metadata as raw metadata, record API/native context and batch/ubatch, and collect persistent startup diagnostics.
- Run one real non-streaming smoke inference and validate the fixed response marker and usage counts.
- Verify that the experimental NAX Tensor API is not enabled for the PTQ1_0 mainline model.
- Create a single result ZIP with auth mode and endpoint status, model/runtime identity, startup stages/errors, smoke request/response, summary, and a per-file SHA-256 manifest.

Run
1. Install the IPA built from the App source SHA pinned in EXPECTED_APP_SOURCE_SHA.txt.
2. Keep the main model set to Ternary-Bonsai-2-27B-PTQ1_0.gguf. Do not switch to PQ2_0 for this test.
3. Start the API in Bonsai and keep the app in the foreground during the smoke request.
4. Run RUN_BUILD112_QUICK_TEST.cmd and enter the Base URL. The script reads /health first and asks for a key only if the IPA reports auth_required=true.
5. Send the single ZIP under RESULTS to ChatGPT.

Classification
- PASS_PTQ1_AUTH_AND_STARTUP_SMOKE: auth mode and protected-route behavior verified, app/build/model identity verified, NAX Tensor mode isolated, and PTQ1_0 smoke inference completed.
- FAIL_AUTH_MODE_UNDETERMINED: /health did not provide a trusted boolean auth_required field.
- FAIL_AUTH_POLICY_MISMATCH: protected routes did not return 401 for missing and incorrect keys while auth was enabled.
- FAIL_API_KEY_REQUIRED / AUTH_FAILED: auth was enabled but the key was absent or rejected.
- FAIL_MODEL_IDENTITY_MISMATCH: Build112 or the PTQ1_0 main model identity did not match.
- FAIL_NAX_ISOLATION: the NAX Tensor API was reported enabled for PTQ1_0.
- INCOMPLETE_API_NOT_REACHABLE: the health endpoint could not be reached; app-side diagnostics are reported as unavailable over HTTP.
- Other FAIL/INCOMPLETE classifications identify the failed stage.

Security and interpretation
- The API Key is held only in process memory for the test and is never written to reports, request artifacts, manifests or the ZIP.
- Request headers are not saved. Authentication probes record only endpoint, HTTP status and pass/fail.
- The script returns exit code 0 only for PASS; FAIL=1, INCOMPLETE=2, BLOCKED=3.
- CI and this smoke test are not proof of crash-free behavior on every M5 launch, numerical correctness, or performance improvement. A crash that terminates the app before /health returns still requires the persistent app/native diagnostic evidence from the next launch.
