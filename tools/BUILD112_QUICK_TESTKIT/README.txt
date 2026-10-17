Bonsai Build112 M5 NAX-PQ2 Long-Prefill TestKit 1.2

Purpose
- Verify the exact Build112 App source SHA separately from the TestKit source commit.
- Check /health, /debug/build, /v1/models and /debug/prefill.
- Require explicit CANDIDATE + backend Tensor API evidence, the expected PQ2_0 model filename hint, API context 32768, and a successfully created native context with batch/ubatch capable of 16-row prefill.
- Send one deterministic 512-1024-token long-prefill request with temperature=0, max_tokens=16 and a fixed response marker.
- Capture /debug/prefill before and after the request and classify route, pipeline, dispatch and inference independently.

Run
1. Install the IPA built from the App source SHA pinned in EXPECTED_APP_SOURCE_SHA.txt.
2. In Bonsai > Advanced & Diagnostics, enable “实验：M5 NAX-PQ2 Tensor 候选（下次启动）”.
3. Fully quit and reopen Bonsai, then start the API on the configured 32768 context.
4. Run RUN_BUILD112_QUICK_TEST.cmd once and enter the API URL and API key when prompted.
5. Send the single ZIP under RESULTS to ChatGPT.

Result classifications include PASS_CANDIDATE_ROUTE_AND_INFERENCE, BLOCKED_SHAPE_PRECONDITION, FAIL_TENSOR_API_NOT_ENABLED, FAIL_ROUTE_NOT_SELECTED, FAIL_PIPELINE_NOT_READY, FAIL_DISPATCH_NOT_ENQUEUED, FAIL_INFERENCE and INCOMPLETE_API_NOT_REACHABLE.

The script does not send a long request when shape prerequisites fail. In that case it records the before/after snapshots and returns BLOCKED_SHAPE_PRECONDITION.
The API key is never saved. The result ZIP includes request metadata, response/error, usage, startup diagnostics, before/after snapshots, stage report and SHA-256 manifest.
The model quantization precheck is explicitly labelled a filename hint. Actual PQ2_0 route selection is proven only by the runtime route marker.
Dispatch-enqueued is not proof of completed GPU execution, numerical correctness or performance improvement. This package is not a performance A/B or device certification.
