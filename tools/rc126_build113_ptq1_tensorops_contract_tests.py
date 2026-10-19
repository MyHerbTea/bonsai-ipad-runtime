#!/usr/bin/env python3
"""Source contracts for the opt-in PTQ1_0 TensorOps candidate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/rc126_build113_patch_prism_ptq1_tensorops.py"
ENGINE = ROOT / "BonsaiLab/BonsaiEngine.swift"
POLICY = ROOT / "BonsaiLab/Build113MetalTensorPolicy.swift"
PRODUCTION = ROOT / "BonsaiLab/ProductionView.swift"
SERVER = ROOT / "BonsaiLab/LocalOpenAIServer.swift"
BRIDGE = ROOT / "BonsaiLab/MTMDProbeBridge.h"
BINARY_VERIFY = ROOT / "tools/rc126_build113_verify_ptq1_tensorops_binary.sh"
AB_RUNNER = ROOT / "tools/BUILD112_QUICK_TESTKIT/PTQ1_TENSOROPS_AB/ptq1_tensorops_ab.py"
WORKFLOW = ROOT / ".github/workflows/build112-b16-default.yml"
DOC = ROOT / "docs/optimization/backburner-integration/RC1.26_BUILD113_PTQ1_TENSOROPS_01.md"

patch = PATCH.read_text(encoding="utf-8")
engine = ENGINE.read_text(encoding="utf-8")
policy = POLICY.read_text(encoding="utf-8")
production = PRODUCTION.read_text(encoding="utf-8")
server = SERVER.read_text(encoding="utf-8")
bridge = BRIDGE.read_text(encoding="utf-8")
binary_verify = BINARY_VERIFY.read_text(encoding="utf-8")
ab_runner = AB_RUNNER.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")

for needle in (
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "GGML_TYPE_PTQ1_0",
    "op->src[1]->type == GGML_TYPE_F32",
    "op->src[0]->nb[0] == ggml_type_size(GGML_TYPE_PTQ1_0)",
    "props_dev->device_id >= GGML_METAL_DEVICE_M5",
    "ne00 % BONSAI_M5_PTQ1_TENSOROPS_QK == 0",
    "ne11 >= BONSAI_M5_PTQ1_TENSOROPS_BM",
    "ne11 % BONSAI_M5_PTQ1_TENSOROPS_BM == 0",
    "ne01 >= BONSAI_M5_PTQ1_TENSOROPS_BN",
    "ptq1_0_lut[b]",
    "kernel_mul_mm_ptq1_tensorops_0_f32",
    "ptq1_tensorops_pipeline_failed.store(true",
    "BUILD113_PTQ1_TENSOROPS_INPUT_TYPE_OBSERVED",
    "BUILD113_PTQ1_TENSOROPS_ROUTE_SELECTED",
    "BUILD113_PTQ1_TENSOROPS_PIPELINE_READY",
    "BUILD113_PTQ1_TENSOROPS_DISPATCH_ENQUEUED",
    "BUILD113_PTQ1_TENSOROPS_FALLBACK_TO_PRISM",
):
    assert needle in patch, f"PTQ1 candidate contract missing: {needle}"
assert "dequantize_ptq1_0_t4" not in patch
assert "block_pq2_0" in patch and "block_ptq1_0" in patch
assert "allowNAXCandidate" in policy and "launchArmRawValue == \"CANDIDATE\"" in policy
assert "BonsaiBuild113PTQ1TensorOpsAB16Enabled" in engine
assert "config.context == 16_384" in engine
assert "config.batch == 16" in engine and "config.ubatch == 16" in engine
assert "enableBuild113PTQ1TensorTrace" in engine
assert "allowPTQ1TensorOpsCandidateForCurrentModel" in engine
assert "GGML_METAL_PTQ1_TENSOROPS_DISABLE" in engine
assert "allowPTQ1TensorOpsCandidate: Bool = false" in engine
assert "allowPTQ1TensorOpsCandidate" in engine
startup_start = production.index("private func startAPIServer()")
ptq1_gate_start = production.index("let allowPTQ1TensorOpsCandidateForModel =", startup_start)
ptq1_gate_end = production.index("RC126APIStartupLifecycle.begin(", ptq1_gate_start)
startup_gate = production[ptq1_gate_start:ptq1_gate_end]
assert "selectedModelIsPTQ1" in startup_gate
assert "selectedAPIContext == 16_384" in startup_gate
assert "shapeTrialForThisStart" in startup_gate
assert "allowPTQ1TensorOpsCandidate: allowPTQ1TensorOpsCandidateForModel" in production
assert "verify_reference_ptq1_lut" in patch
assert "PINNED_PRISM_PTQ1_0_LUT_PARITY" in patch
assert "BonsaiReadPTQ1TensorOpsCounters" in patch and "BonsaiReadPTQ1TensorOpsCounters" in bridge
assert '"_BonsaiReadPTQ1TensorOpsCounters"' in binary_verify
for counter in ("route_selected_count", "pipeline_ready_count", "dispatch_enqueued_count", "fallback_count"):
    assert counter in server, f"missing native PTQ1 counter in debug evidence: {counter}"
for evidence in ("route_selected_delta", "pipeline_ready_delta", "dispatch_enqueued_delta", "fallback_delta", "backend_evidence_valid", "build79_kv_cache_type", 'kv_cache_type != "Q4_0"', "target_tokens"):
    assert evidence in ab_runner, f"missing fail-closed A/B evidence: {evidence}"
assert "实验：PTQ1_0 A/B 固定 16K / B16（下次启动）" in production
assert "Phase2CMetalTensorLaunchLatch.scheduleNext(" in production
assert "Phase2DPrefillBatchLaunchLatch.apply(to: &apiRuntime)" in production
optimization = (ROOT / "BonsaiLab/RuntimeOptimization.swift").read_text(encoding="utf-8")
assert "runtime.batch = 16" in optimization and "runtime.ubatch = 16" in optimization
assert "ptq1_tensorops_trace" in server
assert "metal_current_allocated_bytes" in server
assert "metal_working_set_headroom_bytes" in server and "thermal_state" in server
assert "ptq1_0_lut" in doc
assert "rc126_build113_patch_prism_ptq1_tensorops.py" in workflow
assert "rc126_build113_ptq1_tensorops_codec_tests.py" in workflow
assert "verify_ptq1_tensorops_binary.sh" in workflow
assert "kernel_mul_mm_ptq1_tensorops_0_f32" in workflow
assert "test_contracts.py" in workflow and "test_ab_logic.py" in workflow
print("BUILD113_PTQ1_TENSOROPS_CONTRACT: PASS")
