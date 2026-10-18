#!/usr/bin/env python3
"""Contract checks for Build112 PTQ1_0 Auth-Aware Quick TestKit 2.1."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1"
PTQ1_AB_SCRIPT = ROOT / "tools/BUILD112_QUICK_TESTKIT/run_ptq1_metal_ab.ps1"
PTQ1_AB_README = ROOT / "tools/BUILD112_QUICK_TESTKIT/PTQ1_METAL_AB_README.txt"
README = ROOT / "tools/BUILD112_QUICK_TESTKIT/README.txt"
WORKFLOW = ROOT / ".github/workflows/package-build112-quick-testkit.yml"
SERVER = ROOT / "BonsaiLab/LocalOpenAIServer.swift"
PRODUCTION = ROOT / "BonsaiLab/ProductionView.swift"
AUTH_POLICY = ROOT / "BonsaiLab/APIKeyAuthenticationPolicy.swift"
AUTH_TESTS = ROOT / "tools/api_key_authentication_policy_tests.swift"

script = SCRIPT.read_text(encoding="utf-8")
ptq1_ab_script = PTQ1_AB_SCRIPT.read_text(encoding="utf-8")
ptq1_ab_readme = PTQ1_AB_README.read_text(encoding="utf-8")
readme = README.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
server = SERVER.read_text(encoding="utf-8")
production = PRODUCTION.read_text(encoding="utf-8")
auth_policy = AUTH_POLICY.read_text(encoding="utf-8")
auth_tests = AUTH_TESTS.read_text(encoding="utf-8")

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
    "startup-diagnostics-before.json",
    "startup-diagnostics.json",
    "startup_attempt_history",
    "api_startup_last_failure_attempt_id",
    "Get-StartupHistoryStatus",
    "Get-CurrentApiStatus",
    "Get-OverallStatus",
    "CURRENT_STARTUP_READY",
    "RECOVERED_AFTER_STARTUP_FAILURE",
    "UNATTRIBUTED_HISTORICAL_FAILURE",
    "MODEL_SPECIFIC_STARTUP_FAILURE",
    "PASS_WITH_WARNINGS",
    "NOT_APPLICABLE_PTQ1_0_DEFAULT_PATH",
    "Get-Field must read OrderedDictionary startup snapshots",
):
    assert needle in script, f"Quick TestKit missing contract: {needle}"

assert "FAIL_STARTUP_LIFECYCLE_NOT_READY" not in script, \
    "Old fail-closed lifecycle check must not be used for post-inference engine state."

for needle in (
    "auth_required=true",
    "auth_required=false",
    "without Authorization or X-API-Key",
    "PASS_WITH_WARNINGS: exit code 0",
    "API Key values and request headers are never written",
    "UNATTRIBUTED_HISTORICAL_FAILURE",
    "RECOVERED_AFTER_STARTUP_FAILURE",
    "PTQ1_0",
    "2.1",
):
    assert needle in readme, f"Quick TestKit README missing: {needle}"

for needle in (
    "build112_quick_testkit_contract_tests.py",
    "pwsh -File tools/BUILD112_QUICK_TESTKIT/run_build112_quick_test.ps1 -SelfTest",
    "run_ptq1_metal_ab.ps1 -SelfTest",
    "PTQ1_METAL_AB_README.txt",
    "BONSAI_BUILD112_PTQ1_AUTH_STARTUP_QUICK_TESTKIT_2_1.zip",
):
    assert needle in workflow, f"Quick TestKit workflow missing: {needle}"

# Source-level contract: the UI toggle persists the policy used by /health and
# by the real request guard. Behavior tests cover both modes and persistence.
assert "API Key 鉴权" in production
assert "apiServer.setAPIKeyAuthenticationEnabled($0)" in production
assert "LocalAPIAuthenticationPolicy.setRequired(enabled)" in server
assert '"auth_required": apiKeyAuthenticationEnabled' in server
for needle in (
    "New-ExactPrompt", "Assert-ActualPTQ1Type", "M5_PERFORMANCE_GAIN_VERIFIED",
    "CANDIDATE_NO_GAIN", "BLOCKED_NEEDS_ENGINE_EVIDENCE", "prompt_sha256",
    "metal_current_allocated_bytes", "metal_working_set_headroom_bytes",
    "route_selected", "pipeline_ready", "dispatch_enqueued", "output_sha256",
    "auth_key_saved = $false", "last_observation", "text_kv_reuse",
):
    assert needle in ptq1_ab_script, f"PTQ1 A/B harness missing: {needle}"
for needle in ("512", "2048", "8192", "16K", "B16", "PTQ1_0", "SHA-256", "M5_PERFORMANCE_GAIN_VERIFIED"):
    assert needle in ptq1_ab_readme, f"PTQ1 A/B README missing: {needle}"
assert "guard authorized(request) else" in server
assert "LocalAPIAuthenticationPolicy.isAuthorized(" in server
assert 'static let enabledDefaultsKey = "BonsaiLocalAPIKeyAuthEnabled"' in auth_policy
for needle in (
    "new installs must default to authentication enabled",
    "missing key must be rejected",
    "wrong key must be rejected",
    "disabled authentication must allow requests without headers",
    "disabled preference must persist",
    "re-enabled preference must persist",
):
    assert needle in auth_tests, f"API Key policy regression coverage missing: {needle}"

print("BUILD112_PTQ1_AUTH_STARTUP_TESTKIT_2_1_CONTRACT: PASS")
