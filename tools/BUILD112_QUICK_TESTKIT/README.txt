Bonsai Build112 NAX Quick TestKit

Purpose: verify the exact Build112 M5-NAX-PQ2 identity, API health, model listing, one fixed Smoke request, startup lifecycle, Phase2C compatibility and NAX diagnostics. One result ZIP is created with per-stage PASS / FAIL / INCOMPLETE status and SHA-256 manifest.

Run:
1. Extract the full ZIP into a writable folder.
2. Double-click RUN_BUILD112_QUICK_TEST.cmd.
3. Confirm the Base URL and enter the API key once. The key is held only in memory and never saved.
4. Send the generated ZIP from RESULTS for analysis.

Interpretation:
- PASS means health, exact app/source identity, /v1/models, fixed Smoke and diagnostic-schema checks passed.
- FAIL distinguishes authentication, build identity, health, model-list, request-configuration, inference and diagnostic failures.
- INCOMPLETE / API_NOT_REACHABLE means the listener could not be reached; this alone does not prove why the app failed to start.
- If the listener is down, the ZIP states that internal app diagnostics cannot be retrieved over HTTP. The app persists the last startup stage/error and exposes them under Advanced & Diagnostics > Refresh and copy full diagnostics.
- The short Smoke request does not exercise NAX dispatch. It records the NAX route/pipeline/dispatch fields honestly; dispatch-enqueued is not proof of completed GPU execution.
- Candidate mode must report Tensor API enabled; BASELINE must retain the safe default.

Privacy: no API key is written to disk. The ZIP contains build/runtime identity, endpoint results and allowlisted diagnostics only.
