#!/usr/bin/env python3
"""Contract checks for the auth-aware Build112 PTQ1_0 Quick TestKit."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1"
README = ROOT / "tools/BUILD112_QUICK_TESTKIT/README.txt"
WORKFLOW = ROOT / ".github/workflows/package-build112-quick-testkit.yml"

script = SCRIPT.read_text(encoding="utf-8")
readme = README.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")

for needle in (
    "Resolve-AuthRequired",
    "auth_required",
    "New-RequestHeaders",
    "NO_API_KEY_REQUIRED",
    "INCOMPLETE_API_NOT_REACHABLE",
    "FAIL_AUTH_MODE_UNDETERMINED",
    "FAIL_AUTH_POLICY_MISMATCH",
    "FAIL_API_KEY_REQUIRED",
    "FAIL_MODEL_IDENTITY_MISMATCH",
    "FAIL_NAX_ISOLATION",
    "PTQ1_0",
    "/v1/models",
    "/debug/build",
    "/debug/prefill",
    "/v1/chat/completions",
    "Get-ExitCodeForStatus",
    "ExitCode:",
    "api_key_saved = $false",
    "auth-route-probes.json",
    "startup-diagnostics.json",
    "runtime-diagnostics.json",
    "manifest.json",
    "PASS_PTQ1_AUTH_AND_STARTUP_SMOKE",
):
    assert needle in script, f"Quick TestKit missing contract: {needle}"

for needle in (
    "auth_required=true",
    "auth_required=false",
    "without Authorization or X-API-Key",
    "Exit codes: PASS=0, FAIL=1, INCOMPLETE=2, BLOCKED=3",
    "PTQ1_0",
    "API Key is held only in process memory for the test",
    "never written to reports, request artifacts, manifests or the ZIP",
):
    assert needle in readme, f"Quick TestKit README missing: {needle}"

for needle in (
    "build112_quick_testkit_contract_tests.py",
    "pwsh -File tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1 -SelfTest",
    "BONSAI_BUILD112_PTQ1_AUTH_STARTUP_QUICK_TESTKIT_2_0.zip",
):
    assert needle in workflow, f"Quick TestKit workflow missing: {needle}"

print("BUILD112_PTQ1_AUTH_STARTUP_TESTKIT_CONTRACT: PASS")
