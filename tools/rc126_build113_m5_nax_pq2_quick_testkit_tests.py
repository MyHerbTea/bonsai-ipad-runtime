#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1"
README = ROOT / "tools/BUILD112_QUICK_TESTKIT/README.txt"
WORKFLOW = ROOT / ".github/workflows/package-build112-quick-testkit.yml"
script = SCRIPT.read_text(encoding="utf-8")
readme = README.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")

for needle in (
    "EXPECTED_APP_SOURCE_SHA.txt", "testkit_source_commit", "expected_app_source_sha",
    "Test-ShapePreconditions", "native_context_created", "native_context_ubatch",
    "prefill-before.json", "prefill-after.json", "long-prefill-request.json",
    "long-prefill-response.json", "temperature = 0", "max_tokens = 16",
    "m5-nax-pq2-long-prefill-v1", "PASS_CANDIDATE_ROUTE_AND_INFERENCE",
    "BLOCKED_SHAPE_PRECONDITION", "FAIL_TENSOR_API_NOT_ENABLED", "FAIL_ROUTE_NOT_SELECTED",
    "FAIL_PIPELINE_NOT_READY", "FAIL_DISPATCH_NOT_ENQUEUED", "FAIL_INFERENCE",
    "INCOMPLETE_API_NOT_REACHABLE", "Get-NaxFinalClassification", "api_key_saved = $false", "Get-FileHash",
):
    assert needle in script, f"missing TestKit contract: {needle}"

assert "Dispatch-enqueued is not proof" in readme
assert "EXPECTED_APP_SOURCE_SHA.txt" in readme
assert "pwsh -File" in workflow
assert " -SelfTest" in workflow
assert "rc126_build113_m5_nax_pq2_quick_testkit_tests.py" in workflow
print("PASS Build112 Quick TestKit 1.2 static contract")
